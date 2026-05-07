from __future__ import annotations

import base64
import json
import logging

import azure.functions as func

from src.storage import append_event
from src.validation import parse_sensor_payload

logger = logging.getLogger(__name__)


def process_queue_message(msg: func.QueueMessage):
    logger.info("Worker: mensaje recibido desde queue")

    try:
        raw_body = msg.get_body().decode("utf-8")

        decoded = base64.b64decode(raw_body).decode("utf-8")

        logger.info(f"Worker decoded body: {decoded}")

        body = json.loads(decoded)

        event = parse_sensor_payload(body)

        append_event(event)

        logger.info("Worker: evento guardado en blob correctamente")

    except Exception as e:
        logger.error(f"Worker: error procesando mensaje: {e}", exc_info=True)