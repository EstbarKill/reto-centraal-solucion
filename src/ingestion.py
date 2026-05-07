from __future__ import annotations

import json
import logging
import os

import azure.functions as func

from azure.storage.queue import QueueClient
from azure.core.exceptions import ResourceExistsError

from .validation import parse_sensor_payload

logger = logging.getLogger(__name__)

_QUEUE_NAME = "sensor-events"


def _get_queue_client() -> QueueClient:
    conn_str = os.environ.get("AzureWebJobsStorage")
    if not conn_str:
        raise RuntimeError("AzureWebJobsStorage no está configurado")
    return QueueClient.from_connection_string(conn_str=conn_str, queue_name=_QUEUE_NAME)


def handle_put_sensor(req: func.HttpRequest) -> func.HttpResponse:
    logger.info("--- Ingesta: recibida petición PUT /api/sensors ---")

    # 1. Parse body
    try:
        body = req.get_json()
    except ValueError:
        logger.info("Ingesta: rechazo — cuerpo no es JSON válido.")
        return func.HttpResponse(
            json.dumps({"error": "Cuerpo debe ser JSON"}),
            status_code=400,
            mimetype="application/json",
        )
    if not isinstance(body, dict):
        logger.info("Ingesta: rechazo — JSON raíz debe ser objeto.")
        return func.HttpResponse(
            json.dumps({"error": "JSON debe ser un objeto"}),
            status_code=400,
            mimetype="application/json",
        )

    # 2. Validate
    try:
        event = parse_sensor_payload(body)
    except ValueError as e:
        logger.info("Ingesta: validación fallida — %s", e)
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=400,
            mimetype="application/json",
        )

    # 3. Enqueue — send raw JSON string (queue_worker reads it the same way)
    try:
        queue = _get_queue_client()
        try:
            queue.create_queue()
        except ResourceExistsError:
            pass

        queue.send_message(json.dumps(body, ensure_ascii=False))
        logger.info(
            "Ingesta: evento encolado — machine_id=%s variable=%s ts=%s",
            event.machine_id,
            event.variable,
            event.timestamp.isoformat(),
        )
    except Exception as e:
        logger.error("Ingesta: error al escribir en cola — %s", e, exc_info=True)
        return func.HttpResponse(
            json.dumps({"error": "Error en cola", "detail": str(e)}),
            status_code=500,
            mimetype="application/json",
        )

    return func.HttpResponse(
        json.dumps(
            {"status": "ok", "machine_id": event.machine_id},
            ensure_ascii=False,
        ),
        status_code=200,
        mimetype="application/json",
    )