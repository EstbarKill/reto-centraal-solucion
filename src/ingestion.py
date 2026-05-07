from __future__ import annotations

import json
import logging
import os
import base64

import azure.functions as func

from azure.storage.queue import QueueClient
from azure.core.exceptions import ResourceExistsError


from .validation import parse_sensor_payload

logger = logging.getLogger(__name__)


def handle_put_sensor(req: func.HttpRequest) -> func.HttpResponse:
    logger.info("--- Ingesta: recibida petición PUT /api/sensors ---")
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
    try:
        event = parse_sensor_payload(body)
    except ValueError as e:
        logger.info("Ingesta: validación fallida — %s", e)
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=400,
            mimetype="application/json",
        )   
    try:
        conn_str = os.environ.get("AzureWebJobsStorage")
        if not conn_str:
            raise ValueError("AzureWebJobsStorage no está configurado")

        queue = QueueClient.from_connection_string(
            conn_str=conn_str,
            queue_name="sensor-events"
        )

        try:
            queue.create_queue()

        except ResourceExistsError:
            pass
        
        message = base64.b64encode(
            json.dumps(body).encode("utf-8")
        ).decode("utf-8")

        queue.send_message(json.dumps(body))

        logger.info("Mensaje enviado a queue correctamente")
    except Exception as e:
        logger.error("Ingesta: error al escribir en storage — %s", e, exc_info=True)
        return func.HttpResponse(
            json.dumps({"error": "Error en cola", "detail": str(e)}),
            status_code=500,
            mimetype="application/json",
        )
    logger.info(
        "Ingesta: flujo completado — evento persistido; blob relativo=%s",
    )
    return func.HttpResponse(
        json.dumps(
            {
                "status": "ok",
                "machine_id": event.machine_id
            },
            ensure_ascii=False,
        ),
        status_code=200,
        mimetype="application/json",
    )
