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

logger = logging.getLogger(__name__)


CONTAINER_ENV = "BLOB_CONTAINER_NAME"

def _container_name() -> str:
    return os.environ.get(CONTAINER_ENV, "raw")


def _blob_path_for_date(machine_id: str, d: date) -> str:
    return (
        f"machine_id={machine_id}/year={d.year:04d}/month={d.month:02d}/day={d.day:02d}/events.ndjson"
    )


def _service_client() -> BlobServiceClient:
    conn = os.environ.get("AzureWebJobsStorage")

    if not conn:
        raise RuntimeError("AzureWebJobsStorage no está definido.")

    return BlobServiceClient.from_connection_string(conn)


def ensure_container_exists() -> None:
    name = _container_name()
    logger.info("Comprobando contenedor de blobs '%s' (crear si no existe).", name)
    client = _service_client()
    cc = client.get_container_client(name)
    try:
        cc.create_container()
        logger.info("Contenedor '%s' creado.", name)
    except ResourceExistsError:
        logger.info("Contenedor '%s' ya existía.", name)


def append_event(event: SensorEvent) -> str:
    ensure_container_exists()

    d = event.timestamp.date()

    blob_path = _blob_path_for_date(event.machine_id, d)

    container = _service_client().get_container_client(_container_name())

    blob = container.get_blob_client(blob_path)

    line = json.dumps(event.to_ndjson_dict(), ensure_ascii=False) + "\n"

    try:
        existing = ""
        existing_ids = set()

        if blob.exists():
            existing = blob.download_blob().readall().decode("utf-8")

            for raw_line in existing.splitlines():
                raw_line = raw_line.strip()

                if not raw_line:
                    continue

                try:
                    row = json.loads(raw_line)

                    if "event_id" in row:
                        existing_ids.add(row["event_id"])

                except Exception:
                    logger.info("Línea inválida ignorada en deduplicación")

        # DEDUPLICACIÓN
        if event.event_id in existing_ids:
            logger.info(
                "Evento duplicado detectado — event_id=%s",
                event.event_id,
            )

            return blob_path

        blob.upload_blob(existing + line, overwrite=True)

        logger.info(
            "Evento guardado correctamente en blob — event_id=%s",
            event.event_id,
        )

    except Exception as e:
        logger.error(f"Error escribiendo blob: {e}", exc_info=True)
        raise

    return blob_path
    
def _download_ndjson_lines(blob_path: str) -> list[dict[str, Any]]:
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
            logger.info("Línea NDJSON ignorada (JSON inválido) en %s.", blob_path)
    return lines


def iter_events_in_window(machine_id: str, start_utc: datetime, end_utc: datetime) -> Iterator[dict[str, Any]]:
    """Yield event dicts from NDJSON blobs whose calendar day overlaps the query window."""
    start_utc = start_utc.astimezone(timezone.utc)
    end_utc = end_utc.astimezone(timezone.utc)
    logger.info(
        "Lectura storage: machine_id=%s ventana UTC [%s, %s].",
        machine_id,
        start_utc.isoformat(),
        end_utc.isoformat(),
    )
    d = start_utc.date()
    end_d = end_utc.date()
    while d <= end_d:
        path = _blob_path_for_date(machine_id, d)
        logger.info("Leyendo blob candidato: %s", path)
        for row in _download_ndjson_lines(path):
            yield row
        d += timedelta(days=1)


def list_machine_prefixes() -> list[str]:
    """Return machine_id values discovered from blob paths machine_id=<id>/..."""
    ensure_container_exists()
    container = _service_client().get_container_client(_container_name())
    prefix = "machine_id="
    seen: set[str] = set()
    logger.info("Recorriendo nombres de blob con prefijo '%s' para descubrir máquinas.", prefix)
    for name in container.list_blob_names(name_starts_with=prefix):
        if not name.startswith(prefix):
            continue
        rest = name[len(prefix) :]
        mid = rest.split("/", 1)[0] if rest else ""
        if mid and mid not in seen:
            seen.add(mid)
            logger.info("Máquina detectada en storage: %s", mid)
    return sorted(seen)
