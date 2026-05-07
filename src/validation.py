from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from .models import SensorEvent

# Logger para trazabilidad de validación de entrada
logger = logging.getLogger(__name__)


# ------------------------------------------------------------
# VARIABLES PERMITIDAS DEL SISTEMA
# ------------------------------------------------------------
# Define el "contrato de sensores válidos"
# Todo lo que no esté aquí se rechaza
ALLOWED_VARIABLES = frozenset(
    {
        "vibration_mm_s",
        "temperature_c",
        "current_a",
        "pressure_bar",
        "load_pct",
    }
)


# ------------------------------------------------------------
# PARSEO Y VALIDACIÓN DE PAYLOAD
# ------------------------------------------------------------
def parse_sensor_payload(body: dict[str, Any]) -> SensorEvent:
    """
    Valida y transforma el payload crudo en un SensorEvent.

    Responsabilidades:
    - Validar esquema mínimo
    - Normalizar tipos
    - Normalizar timestamps
    - Garantizar consistencia del evento
    """

    logger.info("Validando payload de sensor")

    # --------------------------------------------------------
    # 1. VALIDACIÓN DE CAMPOS OBLIGATORIOS
    # --------------------------------------------------------
    missing = [
        k for k in ("machine_id", "timestamp", "variable", "value")
        if k not in body
    ]

    if missing:
        logger.info("Faltan campos: %s", missing)
        raise ValueError(f"Campos requeridos faltantes: {', '.join(missing)}")

    # --------------------------------------------------------
    # 2. MACHINE ID
    # --------------------------------------------------------
    machine_id = str(body["machine_id"]).strip()

    if not machine_id:
        logger.info("machine_id vacío")
        raise ValueError("machine_id no puede estar vacío")

    # --------------------------------------------------------
    # 3. VARIABLE DEL SENSOR
    # --------------------------------------------------------
    variable = str(body["variable"]).strip()

    if variable not in ALLOWED_VARIABLES:
        logger.info("Variable inválida: %s", variable)
        raise ValueError(
            f"variable debe ser una de: {', '.join(sorted(ALLOWED_VARIABLES))}"
        )

    # --------------------------------------------------------
    # 4. VALUE NUMÉRICO
    # --------------------------------------------------------
    try:
        value = float(body["value"])
    except (TypeError, ValueError) as e:
        logger.info("value no numérico")
        raise ValueError("value debe ser numérico") from e

    # --------------------------------------------------------
    # 5. TIMESTAMP NORMALIZADO
    # --------------------------------------------------------
    ts_raw = body["timestamp"]

    if isinstance(ts_raw, datetime):
        # Si ya viene como datetime
        ts = ts_raw if ts_raw.tzinfo else ts_raw.replace(tzinfo=timezone.utc)

    else:
        # Parse string ISO8601
        s = str(ts_raw).strip()

        if s.endswith("Z"):
            s = s[:-1] + "+00:00"

        try:
            ts = datetime.fromisoformat(s)
        except ValueError as e:
            logger.info("timestamp inválido")
            raise ValueError(
                "timestamp debe ser ISO8601 (ej. 2026-04-06T10:15:00Z)"
            ) from e

        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

    # Normaliza a UTC absoluto
    ts = ts.astimezone(timezone.utc)

    # --------------------------------------------------------
    # 6. LOG DE VALIDACIÓN EXITOSA
    # --------------------------------------------------------
    logger.info(
        "Validación OK: machine_id=%s variable=%s value=%s ts_utc=%s",
        machine_id,
        variable,
        value,
        ts.isoformat(),
    )

    # --------------------------------------------------------
    # 7. RETORNO DEL MODELO ESTRUCTURADO
    # --------------------------------------------------------
    return SensorEvent(
        machine_id=machine_id,
        timestamp=ts,
        variable=variable,
        value=value
    )