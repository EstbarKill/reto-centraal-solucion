"""Tests for src/models.py — SensorEvent dataclass."""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime, timezone
from src.models import SensorEvent


class TestSensorEvent:
    def _make_event(self, **kwargs) -> SensorEvent:
        defaults = dict(
            machine_id="PUMP-1001",
            timestamp=datetime(2026, 4, 6, 10, 15, 0, tzinfo=timezone.utc),
            variable="temperature_c",
            value=78.4,
        )
        return SensorEvent(**{**defaults, **kwargs})

    def test_to_ndjson_dict_keys(self):
        event = self._make_event()
        d = event.to_ndjson_dict()
        assert set(d.keys()) == {"machine_id", "timestamp", "variable", "value"}

    def test_to_ndjson_dict_timestamp_is_iso_string(self):
        event = self._make_event()
        d = event.to_ndjson_dict()
        # Should be a string in UTC ISO format
        assert isinstance(d["timestamp"], str)
        assert "T" in d["timestamp"]

    def test_to_ndjson_dict_timestamp_normalised_to_utc(self):
        """Timestamp with non-UTC offset must be rendered as UTC in the dict."""
        from datetime import timedelta
        tz_plus5 = timezone(timedelta(hours=5))
        dt_local = datetime(2026, 4, 6, 15, 15, 0, tzinfo=tz_plus5)  # = 10:15 UTC
        event = self._make_event(timestamp=dt_local)
        d = event.to_ndjson_dict()
        # Must show UTC hour 10
        assert d["timestamp"].startswith("2026-04-06T10:15:00")

    def test_frozen_dataclass_immutable(self):
        event = self._make_event()
        with __import__("pytest").raises((AttributeError, TypeError)):
            event.value = 999.0  # type: ignore[misc]

    def test_machine_id_preserved(self):
        event = self._make_event(machine_id="COMPRESSOR-42")
        assert event.to_ndjson_dict()["machine_id"] == "COMPRESSOR-42"

    def test_value_preserved(self):
        event = self._make_event(value=3.14)
        assert event.to_ndjson_dict()["value"] == 3.14