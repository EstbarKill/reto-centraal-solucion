"""
Azure Functions (modelo programático v2):

Este archivo es el ENTRYPOINT del sistema serverless.
Define:
- HTTP APIs (ingesta y predicción)
- Queue Trigger (worker asíncrono)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import azure.functions as func

# ------------------------------------------------------------
# CONFIGURACIÓN DE PATH PARA IMPORTS LOCALES
# ------------------------------------------------------------
# Permite usar imports tipo `src.*` sin instalación de paquete
_root = Path(__file__).resolve().parent

if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


# ------------------------------------------------------------
# IMPORTACIÓN DE LÓGICA DE NEGOCIO
# ------------------------------------------------------------
from src.ingestion import handle_put_sensor
from src.prediction import (
    handle_get_all_predictions,
    handle_get_machine_prediction
)

from src.queue_worker import process_queue_message

# Logger global del runtime Azure Functions
logger = logging.getLogger(__name__)

# App principal de Azure Functions (modelo v2)
app = func.FunctionApp()


# ------------------------------------------------------------
# ENDPOINT: INGESTA DE SENSORES
# ------------------------------------------------------------
@app.route(
    route="sensors",
    methods=["PUT"],
    auth_level=func.AuthLevel.ANONYMOUS
)
def sensors_put(req: func.HttpRequest) -> func.HttpResponse:
    """
    Endpoint:
    PUT /api/sensors

    Responsabilidad:
    - recibir datos de sensores
    - validar
    - encolar evento (async processing)
    """
    logger.info("HTTP: ingesta sensores activada")
    return handle_put_sensor(req)


# ------------------------------------------------------------
# ENDPOINT: PREDICCIÓN POR MÁQUINA
# ------------------------------------------------------------
@app.route(
    route="machines/{machine_id}/prediction",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def machine_prediction(req: func.HttpRequest) -> func.HttpResponse:
    """
    Endpoint:
    GET /api/machines/{id}/prediction

    Responsabilidad:
    - calcular riesgo de fallo por máquina
    """
    machine_id = req.route_params.get("machine_id", "")

    logger.info(
        "HTTP: predicción máquina=%s",
        machine_id,
    )

    return handle_get_machine_prediction(req, machine_id)


# ------------------------------------------------------------
# ENDPOINT: TODAS LAS PREDICCIONES
# ------------------------------------------------------------
@app.route(
    route="predictions",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS
)
def all_predictions(req: func.HttpRequest) -> func.HttpResponse:
    """
    Endpoint:
    GET /api/predictions

    Responsabilidad:
    - calcular predicción para todas las máquinas detectadas
    """
    logger.info("HTTP: listado de predicciones global")
    return handle_get_all_predictions(req)


# ------------------------------------------------------------
# WORKER ASÍNCRONO (QUEUE TRIGGER)
# ------------------------------------------------------------
@app.function_name(name="queue_worker")
@app.queue_trigger(
    arg_name="msg",
    queue_name="sensor-events",
    connection="AzureWebJobsStorage"
)
def queue_handler(msg: func.QueueMessage):
    """
    Trigger de cola:

    Flujo:
    Queue Message → process_queue_message → storage

    Responsabilidad:
    - procesar eventos asincrónicos
    - persistir en Blob Storage
    """
    process_queue_message(msg)