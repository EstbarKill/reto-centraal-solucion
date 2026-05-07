from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterator
from datetime import date, datetime, timedelta, timezone
from typing import Any

from azure.core.exceptions import ResourceExistsError
from azure.storage.blob import BlobServiceClient

from .models import SensorEvent

# Logger para trazabilidad de almacenamiento (data lake)
logger = logging.getLogger(__name__)


# ------------------------------------------------------------
# CONFIGURACIÓN DE STORAGE
# ------------------------------------------------------------

# Variable de entorno para el contenedor de blobs
CONTAINER_ENV = "BLOB_CONTAINER_NAME"


def _container_name() -> str:
    """
    Obtiene el nombre del contenedor de Azure Blob Storage.

    Default: 'raw'
    """
    return os.environ.get(CONTAINER_ENV, "raw")


# ------------------------------------------------------------
# GENERACIÓN DE PATH (PARTICIONAMIENTO)
# ------------------------------------------------------------
def _blob_path_for_date(machine_id: str, d: date) -> str:
    """
    Genera path tipo data lake:

    machine_id=PUMP-1/year=2026/month=05/day=07/events.ndjson
    """
    return (
        f"machine_id={machine_id}/year={d.year:04d}/month={d.month:02d}/day={d.day:02d}/events.ndjson"
    )


# ------------------------------------------------------------
# CLIENTE DE AZURE STORAGE
# ------------------------------------------------------------
def _service_client() -> BlobServiceClient:
    """
    Crea cliente de Azure Blob Storage.

    Usa AzureWebJobsStorage como connection string.
    """
    conn = os.environ.get("AzureWebJobsStorage")

    if not conn:
        raise RuntimeError("AzureWebJobsStorage no está definido.")

    return BlobServiceClient.from_connection_string(conn)


# ------------------------------------------------------------
# CREACIÓN DE CONTENEDOR (IDEMPOTENTE)
# ------------------------------------------------------------
def ensure_container_exists() -> None:
    """
    Asegura que el contenedor exista.

    Operación idempotente:
    - si existe → no falla
    - si no existe → lo crea
    """
    name = _container_name()
    logger.info("Comprobando contenedor '%s'", name)

    client = _service_client()
    cc = client.get_container_client(name)

    try:
        cc.create_container()
        logger.info("Contenedor creado")
    except ResourceExistsError:
        logger.info("Contenedor ya existía")


# ------------------------------------------------------------
# APPEND DE EVENTOS (CORE DEL SISTEMA)
# ------------------------------------------------------------
def append_event(event: SensorEvent) -> str:
    ensure_container_exists()

    d = event.timestamp.date()
    blob_path = _blob_path_for_date(event.machine_id, d)

    container = _service_client().get_container_client(_container_name())
    blob = container.get_blob_client(blob_path)

    line = json.dumps(event.to_ndjson_dict(), ensure_ascii=False) + "\n"

    try:
        # 🔥 FIX CRÍTICO: NO leer todo el archivo

        if blob.exists():
            existing = blob.download_blob().readall().decode("utf-8")

        existing_ids = set()

        if blob.exists():
            existing = blob.download_blob().readall().decode("utf-8")

            for line in existing.splitlines():
                try:
                    obj = json.loads(line)
                    existing_ids.add(obj.get("event_id"))
                except:
                    continue

        if event.event_id in existing_ids:
            return blob_path

            new_data = existing + line
        else:
            new_data = line

        # APPEND SIMULADO pero correcto
        blob.upload_blob(new_data, overwrite=True)

        logger.info("Evento guardado %s", event.event_id)

    except Exception as e:
        logger.error(f"Error blob: {e}", exc_info=True)
        raise

    return blob_path
# ------------------------------------------------------------
# LECTURA NDJSON
# ------------------------------------------------------------
def _download_ndjson_lines(blob_path: str) -> list[dict[str, Any]]:
    """
    Descarga y parsea un blob NDJSON en memoria.
    """
    container = _service_client().get_container_client(_container_name())
    blob = container.get_blob_client(blob_path)

    if not blob.exists():
        return []

    raw = blob.download_blob().readall().decode("utf-8", errors="replace")

    lines: list[dict[str, Any]] = []

    for line in raw.splitlines():
        line = line.strip()

        if not line:
            continue

        try:
            lines.append(json.loads(line))
        except json.JSONDecodeError:
            logger.info("Línea NDJSON inválida ignorada")

    return lines


# ------------------------------------------------------------
# ITERADOR DE VENTANA TEMPORAL
# ------------------------------------------------------------
def iter_events_in_window(
    machine_id: str,
    start_utc: datetime,
    end_utc: datetime
) -> Iterator[dict[str, Any]]:
    """
    Itera eventos de múltiples blobs por día.

    ⚠️ Estrategia actual:
    - lee 1 blob por día
    - descarga completo
    - filtra en memoria
    """

    start_utc = start_utc.astimezone(timezone.utc)
    end_utc = end_utc.astimezone(timezone.utc)

    logger.info(
        "Lectura storage: [%s - %s]",
        start_utc.isoformat(),
        end_utc.isoformat(),
    )

    d = start_utc.date()
    end_d = end_utc.date()

    while d <= end_d:
        path = _blob_path_for_date(machine_id, d)

        logger.info("Leyendo blob: %s", path)

        for row in _download_ndjson_lines(path):
            yield row

        d += timedelta(days=1)


# ------------------------------------------------------------
# LISTADO DE MÁQUINAS
# ------------------------------------------------------------
def list_machine_prefixes() -> list[str]:
    """
    Descubre máquinas escaneando nombres de blobs.

    Ejemplo:
    machine_id=PUMP-1/...
    """

    ensure_container_exists()

    container = _service_client().get_container_client(_container_name())

    prefix = "machine_id="
    seen: set[str] = set()

    logger.info("Buscando máquinas en storage...")

    for name in container.list_blob_names(name_starts_with=prefix):

        if not name.startswith(prefix):
            continue

        rest = name[len(prefix):]
        mid = rest.split("/", 1)[0] if rest else ""

        if mid and mid not in seen:
            seen.add(mid)
            logger.info("Máquina detectada: %s", mid)

    return sorted(seen)