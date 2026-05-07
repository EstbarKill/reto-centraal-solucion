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


NOMINAL_MAX: dict[str, float] = {
    "vibration_mm_s": 7.0,
    "temperature_c": 70.0,
    "current_a": 50.0,
    "pressure_bar": 12.0,
    "load_pct": 85.0,
}


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _load_events_in_window(machine_id: str, hours: int = 24):

    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)

    rows = []

    for row in iter_events_in_window(machine_id, start, end):

        var = row.get("variable")
        if var not in ALLOWED_VARIABLES:
            continue

        try:
            value = float(row.get("value"))
        except:
            continue

        # 🔥 FIX CRÍTICO: mantener timestamp
        ts = row.get("timestamp")

        if not ts:
            continue

        rows.append({
            "variable": var,
            "value": value,
            "timestamp": ts
        })

        if len(rows) > 5000:
            break

    return rows

def _features_by_variable(rows):

    by_var = defaultdict(list)

    for row in rows:

        try:
            ts = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))
        except:
            continue

        by_var[row["variable"]].append((ts, float(row["value"])))

    result = {}

    for var, pairs in by_var.items():

        pairs.sort(key=lambda x: x[0])
        vals = [v for _, v in pairs]

        result[var] = {
            "last": vals[-1],
            "mean": sum(vals) / len(vals),
            "max": max(vals),
            "count": len(vals),
        }

    return result
def _score_and_risk(features: dict[str, dict[str, float]]) -> tuple[float, list[str]]:
    risk = []
    score = 0.0

    for var, agg in features.items():
        cap = NOMINAL_MAX.get(var)
        if cap is None:
            continue

        max_v = agg["max"]
        mean_v = agg["mean"]
        last_v = agg["last"]

        em = max(0.0, (max_v - cap) / cap)
        e_mean = max(0.0, (mean_v - cap) / cap)
        e_last = max(0.0, (last_v - cap) / cap)

        if em:
            risk.append(f"{var}: max={max_v:.2f} > {cap}")

        score += em + 0.45 * e_mean + 0.25 * e_last

    return score, risk


def compute_prediction_for_machine(machine_id: str, hours: int = 24) -> dict[str, Any]:

    rows = _load_events_in_window(machine_id, hours)

    if not rows:
        return {
            "machine_id": machine_id,
            "failure_probability_24h": 0.1,
            "risk_factors": ["Sin datos"],
            "events_considered": 0,
        }

    features = _features_by_variable(rows)
    score, risk = _score_and_risk(features)

    prob = min(1.0, score / 3.0)

    return {
        "machine_id": machine_id,
        "failure_probability_24h": round(prob, 4),
        "risk_factors": risk,
        "events_considered": len(rows),
        "features_by_variable": features,
    }


def handle_get_machine_prediction(req: func.HttpRequest, machine_id: str) -> func.HttpResponse:
    try:
        return func.HttpResponse(
            json.dumps(compute_prediction_for_machine(machine_id)),
            status_code=200,
        )
    except Exception as e:
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
        )


def handle_get_all_predictions(req: func.HttpRequest) -> func.HttpResponse:

    machines = list_machine_prefixes()

    predictions = []

    for mid in machines:
        try:
            predictions.append(compute_prediction_for_machine(mid))
        except Exception:
            continue

    return func.HttpResponse(
        json.dumps({
            "predictions": predictions,
            "machines_scanned": len(machines)
        }),
        status_code=200,
    )