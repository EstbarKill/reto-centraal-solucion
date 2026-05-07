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

    return QueueClient.from_connection_string(
        conn_str=conn_str,
        queue_name=_QUEUE_NAME
    )


def handle_put_sensor(req: func.HttpRequest) -> func.HttpResponse:

    logger.info("--- Ingesta: PUT /api/sensors ---")

    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            json.dumps({"error": "JSON inválido"}),
            status_code=400,
            mimetype="application/json",
        )

    if not isinstance(body, dict):
        return func.HttpResponse(
            json.dumps({"error": "JSON debe ser objeto"}),
            status_code=400,
        )

    try:
        event = parse_sensor_payload(body)
    except ValueError as e:
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=400,
        )

    try:
        queue = _get_queue_client()

        try:
            queue.create_queue()
        except ResourceExistsError:
            pass

        # 🔥 FIX: incluir event_id en cola
        payload = {
            "event_id": event.event_id,
            **body
        }

        queue.send_message(json.dumps(payload, ensure_ascii=False))

    except Exception as e:
        return func.HttpResponse(
            json.dumps({"error": "cola error", "detail": str(e)}),
            status_code=500,
        )

    return func.HttpResponse(
        json.dumps({"status": "ok", "machine_id": event.machine_id}),
        status_code=200,
    )