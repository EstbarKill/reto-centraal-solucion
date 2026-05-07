"""Tests for src/storage.py — blob path construction and NDJSON parsing."""
from __future__ import annotations

import json
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from src.storage import _blob_path_for_date, _download_ndjson_lines
from src.models import SensorEvent


# ---------------------------------------------------------------------------
# _blob_path_for_date
# ---------------------------------------------------------------------------

class TestBlobPathForDate:
    def test_basic_path_format(self):
        d = date(2026, 4, 6)
        path = _blob_path_for_date("PUMP-1001", d)
        assert path == "machine_id=PUMP-1001/year=2026/month=04/day=06/events.ndjson"

    def test_single_digit_month_and_day_zero_padded(self):
        d = date(2026, 1, 5)
        path = _blob_path_for_date("PUMP-X", d)
        assert "month=01" in path
        assert "day=05" in path

    def test_machine_id_embedded_correctly(self):
        d = date(2026, 6, 15)
        path = _blob_path_for_date("COMPRESSOR-007", d)
        assert "machine_id=COMPRESSOR-007" in path

    def test_ends_with_events_ndjson(self):
        d = date(2026, 12, 31)
        path = _blob_path_for_date("PUMP-1", d)
        assert path.endswith("events.ndjson")

    def test_year_four_digits(self):
        d = date(2026, 4, 6)
        path = _blob_path_for_date("PUMP-1", d)
        assert "year=2026" in path


# ---------------------------------------------------------------------------
# _download_ndjson_lines (mocked blob client)
# ---------------------------------------------------------------------------

class TestDownloadNdjsonLines:
    def _make_blob_mock(self, content: str):
        """Return a mocked container client where blob exists and contains `content`."""
        blob_mock = MagicMock()
        blob_mock.exists.return_value = True
        download_mock = MagicMock()
        download_mock.readall.return_value = content.encode("utf-8")
        blob_mock.download_blob.return_value = download_mock
        return blob_mock

    def test_valid_ndjson_lines_parsed(self):
        lines = (
            '{"machine_id": "PUMP-1", "variable": "temperature_c", "value": 70.0, "timestamp": "2026-04-06T10:00:00Z"}\n'
            '{"machine_id": "PUMP-1", "variable": "vibration_mm_s", "value": 3.5, "timestamp": "2026-04-06T10:01:00Z"}\n'
        )
        blob_mock = self._make_blob_mock(lines)
        container_mock = MagicMock()
        container_mock.get_blob_client.return_value = blob_mock

        with patch("src.storage._service_client") as sc_mock:
            sc_mock.return_value.get_container_client.return_value = container_mock
            result = _download_ndjson_lines("some/path/events.ndjson")

        assert len(result) == 2
        assert result[0]["variable"] == "temperature_c"
        assert result[1]["value"] == 3.5

    def test_non_existent_blob_returns_empty(self):
        blob_mock = MagicMock()
        blob_mock.exists.return_value = False
        container_mock = MagicMock()
        container_mock.get_blob_client.return_value = blob_mock

        with patch("src.storage._service_client") as sc_mock:
            sc_mock.return_value.get_container_client.return_value = container_mock
            result = _download_ndjson_lines("any/path")

        assert result == []

    def test_invalid_json_lines_skipped(self):
        content = (
            'INVALID JSON LINE\n'
            '{"machine_id": "PUMP-1", "variable": "temperature_c", "value": 65.0, "timestamp": "2026-04-06T10:00:00Z"}\n'
            '{broken\n'
        )
        blob_mock = self._make_blob_mock(content)
        container_mock = MagicMock()
        container_mock.get_blob_client.return_value = blob_mock

        with patch("src.storage._service_client") as sc_mock:
            sc_mock.return_value.get_container_client.return_value = container_mock
            result = _download_ndjson_lines("some/path")

        # Only the valid line should be returned
        assert len(result) == 1
        assert result[0]["machine_id"] == "PUMP-1"

    def test_empty_blob_returns_empty(self):
        blob_mock = self._make_blob_mock("")
        container_mock = MagicMock()
        container_mock.get_blob_client.return_value = blob_mock

        with patch("src.storage._service_client") as sc_mock:
            sc_mock.return_value.get_container_client.return_value = container_mock
            result = _download_ndjson_lines("some/path")

        assert result == []

    def test_blank_lines_skipped(self):
        content = (
            '\n'
            '{"machine_id": "PUMP-1", "variable": "load_pct", "value": 75.0, "timestamp": "2026-04-06T10:00:00Z"}\n'
            '\n'
            '\n'
        )
        blob_mock = self._make_blob_mock(content)
        container_mock = MagicMock()
        container_mock.get_blob_client.return_value = blob_mock

        with patch("src.storage._service_client") as sc_mock:
            sc_mock.return_value.get_container_client.return_value = container_mock
            result = _download_ndjson_lines("some/path")

        assert len(result) == 1