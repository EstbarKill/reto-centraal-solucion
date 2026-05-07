from __future__ import annotations

import json
import logging
import azure.functions as func

from src.storage import append_event
from src.validation import parse_sensor_payload

logger = logging.getLogger(__name__)


def process_queue_message(msg: func.QueueMessage) -> None:

    logger.info("Worker: mensaje recibido")

    try:
        body = json.loads(msg.get_body().decode("utf-8"))

        event = parse_sensor_payload(body)

        # 🔥 FIX: usar event_id ya validado
        blob_path = append_event(event)

        logger.info(f"Guardado en {blob_path}")

    except Exception as e:
        logger.error(f"ERROR WORKER: {e}", exc_info=True)
        raise