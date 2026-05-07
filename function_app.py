"""
Azure Functions (modelo programático v2): APIs de ingesta y predicción.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import azure.functions as func

# Raíz del proyecto en sys.path para imports `src.*` al arrancar func host
_root = Path(__file__).resolve().parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


from src.ingestion import handle_put_sensor  # noqa: E402
from src.prediction import handle_get_all_predictions, handle_get_machine_prediction  # noqa: E402

from src.queue_worker import process_queue_message

logger = logging.getLogger(__name__)

app = func.FunctionApp()

@app.route(route="sensors", methods=["PUT"], auth_level=func.AuthLevel.ANONYMOUS)
def sensors_put(req: func.HttpRequest) -> func.HttpResponse:
    logger.info("Function HTTP disparada: ruta sensors método PUT (ingesta).")
    return handle_put_sensor(req)

@app.route(
    route="machines/{machine_id}/prediction",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def machine_prediction(req: func.HttpRequest) -> func.HttpResponse:
    machine_id = req.route_params.get("machine_id", "")
    logger.info(
        "Function HTTP disparada: predicción por máquina; route machine_id=%s",
        machine_id,
    )
    return handle_get_machine_prediction(req, machine_id)

@app.route(route="predictions", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def all_predictions(req: func.HttpRequest) -> func.HttpResponse:
    logger.info("Function HTTP disparada: listado GET predictions.")
    return handle_get_all_predictions(req)

@app.function_name(name="queue_worker")
@app.queue_trigger(
    arg_name="msg",
    queue_name="sensor-events",
    connection="AzureWebJobsStorage"
)
def queue_handler(msg: func.QueueMessage):
    process_queue_message(msg)