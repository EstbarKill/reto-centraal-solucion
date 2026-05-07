from __future__ import annotations

import json
import logging
import math
from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from typing import Any

import azure.functions as func

from .storage import iter_events_in_window, list_machine_prefixes
from .validation import ALLOWED_VARIABLES

logger = logging.getLogger(__name__)

# Umbrales orientativos (por encima aumenta riesgo). Ajustables por máquina en el futuro.
NOMINAL_MAX: dict[str, float] = {
    "vibration_mm_s": 7.0,
    "temperature_c": 70.0,
    "current_a": 50.0,
    "pressure_bar": 12.0,
    "load_pct": 85.0,
}


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _parse_ts(row: dict[str, Any]) -> datetime | None:
    ts = row.get("timestamp")
    if not ts:
        return None
    s = str(ts).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _load_events_in_window(machine_id: str, hours: int = 24) -> list[dict[str, Any]]:
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=24)
    logger.info(f"VENTANA: {start.isoformat()} - {end.isoformat()}")
    logger.info(
        "Predicción: cargando eventos para %s en ventana [%s - %s].",
        machine_id,
        start.isoformat(),
        end.isoformat(),
    )
    rows: list[dict[str, Any]] = []
    for row in iter_events_in_window(machine_id, start, end):
        ts = _parse_ts(row)
        logger.info(f"TS EVENTO: {ts}")
        logger.info(f"RAW EVENT: {row}")
        if ts is None:
            logger.info("Predicción: fila sin timestamp válido, omitida.")
            continue
        if ts < start or ts > end:
            logger.info(
                "Predicción: evento fuera de ventana (ts=%s), omitido para el cálculo.",
                ts.isoformat(),
            )
            continue
        
        var = row.get("variable")
        if var not in ALLOWED_VARIABLES:
            logger.info("Predicción: variable desconocida '%s', omitida.", var)
            continue
        try:
            float(row.get("value"))
        except (TypeError, ValueError):
            logger.info("Predicción: value no numérico, fila omitida.")
            continue
        rows.append(row)
        if len(rows) > 5000:
            break
        logger.info(f"EVENTOS FINALES: {len(rows)}")
    logger.info("Predicción: %s eventos válidos en ventana para %s.", len(rows), machine_id)
    return rows


def _features_by_variable(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, float]]:
    by_var: dict[str, list[tuple[datetime, float]]] = defaultdict(list)
    for row in rows:
        ts = _parse_ts(row)
        if ts is None:
            continue
        by_var[str(row["variable"])].append((ts, float(row["value"])))
    out: dict[str, dict[str, float]] = {}
    for var, pairs in by_var.items():
        pairs.sort(key=lambda x: x[0])
        vals = [v for _, v in pairs]
        last = pairs[-1][1]
        mean_v = sum(vals) / len(vals)
        max_v = max(vals)
        out[var] = {"last": last, "mean": mean_v, "max": max_v, "count": float(len(vals))}
    logger.info(
        "Predicción: agregados por variable calculados para %s variables.",
        len(out),
    )
    return out


def _score_and_risk(features: dict[str, dict[str, float]]) -> tuple[float, list[str]]:
    """Score lineal por variable (máximo pesa más que media/último) y factores explicables."""
    risk: list[str] = []
    score = 0.0
    for var, agg in features.items():
        cap = NOMINAL_MAX.get(var)
        if cap is None:
            continue
        denom = max(cap, 1e-6)
        max_v, mean_v, last_v = agg["max"], agg["mean"], agg["last"]
        em = max(0.0, (max_v - cap) / denom)
        e_mean = max(0.0, (mean_v - cap) / denom)
        e_last = max(0.0, (last_v - cap) / denom)
        if em:
            risk.append(
                f"{var}: máximo {max_v:.2f} supera umbral nominal {cap:.2f} (exceso relativo {em:.3f})"
            )
        if e_mean:
            risk.append(
                f"{var}: media {mean_v:.2f} por encima del umbral {cap:.2f} (exceso relativo {e_mean:.3f})"
            )
        if e_last:
            risk.append(
                f"{var}: último valor {last_v:.2f} por encima del umbral {cap:.2f} (exceso relativo {e_last:.3f})"
            )
        score += 1.0 * em + 0.45 * e_mean + 0.25 * e_last
    logger.info(
        "Predicción: score bruto ponderado=%.4f; %s líneas de factor de riesgo.",
        score,
        len(risk),
    )
    return score, risk


def compute_prediction_for_machine(machine_id: str, hours: int = 24) -> dict[str, Any]:
    logger.info("=== Inicio cálculo predicción para machine_id=%s ===", machine_id)
    rows = _load_events_in_window(machine_id, hours=hours)
    if not rows:
        logger.info(
            "Predicción: sin datos en ventana — devolviendo probabilidad base baja y sin factores."
        )
        return {
            "machine_id": machine_id,
            "failure_probability_24h": round(_sigmoid(-2.0), 4),
            "risk_factors": ["Sin eventos en las últimas 24h; riesgo no estimable con datos"],
            "window_hours": hours,
            "events_considered": 0,
            "features_by_variable": {},
        }
    features = _features_by_variable(rows)
    raw_score, risk_factors = _score_and_risk(features)
    # Centrar sigmoide: score bajo → prob baja
    z = 2.5 * (raw_score - 0.35)
    prob = _sigmoid(z)
    logger.info(
        "Predicción: aplicada sigmoid(score): raw_score=%.4f z=%.4f → failure_probability_24h=%.4f",
        raw_score,
        z,
        prob,
    )
    if not risk_factors:
        risk_factors = ["Ningún agregado supera umbrales nominales en la ventana"]
    result = {
        "machine_id": machine_id,
        "failure_probability_24h": round(min(1.0, max(0.0, prob)), 4),
        "risk_factors": risk_factors,
        "window_hours": hours,
        "events_considered": len(rows),
        "features_by_variable": {
            k: {kk: round(vv, 4) for kk, vv in v.items()} for k, v in features.items()
        },
    }
    logger.info("=== Fin cálculo predicción para %s (eventos=%s) ===", machine_id, len(rows))
    return result


def handle_get_machine_prediction(req: func.HttpRequest, machine_id: str) -> func.HttpResponse:
    logger.info("Consulta predicción: GET máquina '%s'.", machine_id)
    mid = (machine_id or "").strip()
    if not mid:
        return func.HttpResponse(
            json.dumps({"error": "machine_id requerido"}),
            status_code=400,
            mimetype="application/json",
        )
    try:
        payload = compute_prediction_for_machine(mid)
    except Exception as e:
        logger.info("Consulta predicción: error — %s", e, exc_info=True)
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json",
        )
    return func.HttpResponse(
        json.dumps(payload, ensure_ascii=False),
        status_code=200,
        mimetype="application/json",
    )


def handle_get_all_predictions(req: func.HttpRequest) -> func.HttpResponse:
    logger.info("Consulta predicción: GET /api/predictions (todas las máquinas con datos).")
    try:
        machines = list_machine_prefixes()
    except Exception as e:
        logger.info("Listado máquinas: error — %s", e, exc_info=True)
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json",
        )
    logger.info("Se calcularán predicciones para %s máquina(s): %s.", len(machines), machines)
    predictions: list[dict[str, Any]] = []
    for mid in machines:
        predictions.append(compute_prediction_for_machine(mid))
    body = {"predictions": predictions, "machines_scanned": len(machines)}
    logger.info("GET /api/predictions completado; respuesta con %s entradas.", len(predictions))
    return func.HttpResponse(
        json.dumps(body, ensure_ascii=False),
        status_code=200,
        mimetype="application/json",
    )
