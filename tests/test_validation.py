"""Tests for src/validation.py — parse_sensor_payload."""
from __future__ import annotations

import pytest
from datetime import datetime, timezone

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.validation import parse_sensor_payload, ALLOWED_VARIABLES
from src.models import SensorEvent


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestValidPayloads:
    def test_basic_valid_event(self):
        body = {
            "machine_id": "PUMP-1001",
            "timestamp": "2026-04-06T10:15:00Z",
            "variable": "temperature_c",
            "value": 78.4,
        }
        event = parse_sensor_payload(body)
        assert isinstance(event, SensorEvent)
        assert event.machine_id == "PUMP-1001"
        assert event.variable == "temperature_c"
        assert event.value == 78.4
        assert event.timestamp.tzinfo is not None

    def test_all_allowed_variables(self):
        base = {
            "machine_id": "PUMP-X",
            "timestamp": "2026-04-06T10:00:00Z",
            "value": 1.0,
        }
        for var in ALLOWED_VARIABLES:
            event = parse_sensor_payload({**base, "variable": var})
            assert event.variable == var

    def test_timestamp_without_z_gets_utc(self):
        body = {
            "machine_id": "PUMP-1001",
            "timestamp": "2026-04-06T10:15:00",
            "variable": "vibration_mm_s",
            "value": 3.5,
        }
        event = parse_sensor_payload(body)
        assert event.timestamp.tzinfo == timezone.utc

    def test_timestamp_with_offset(self):
        body = {
            "machine_id": "PUMP-1001",
            "timestamp": "2026-04-06T10:15:00+05:00",
            "variable": "vibration_mm_s",
            "value": 3.5,
        }
        event = parse_sensor_payload(body)
        # Should be converted to UTC
        assert event.timestamp.tzinfo == timezone.utc
        assert event.timestamp.hour == 5  # 10:15 +05:00 = 05:15 UTC

    def test_value_as_integer_is_coerced_to_float(self):
        body = {
            "machine_id": "PUMP-1001",
            "timestamp": "2026-04-06T10:00:00Z",
            "variable": "load_pct",
            "value": 75,
        }
        event = parse_sensor_payload(body)
        assert isinstance(event.value, float)
        assert event.value == 75.0

    def test_value_as_string_number(self):
        body = {
            "machine_id": "PUMP-1001",
            "timestamp": "2026-04-06T10:00:00Z",
            "variable": "current_a",
            "value": "10.5",
        }
        event = parse_sensor_payload(body)
        assert event.value == 10.5

    def test_machine_id_is_stripped(self):
        body = {
            "machine_id": "  PUMP-1001  ",
            "timestamp": "2026-04-06T10:00:00Z",
            "variable": "pressure_bar",
            "value": 3.0,
        }
        event = parse_sensor_payload(body)
        assert event.machine_id == "PUMP-1001"

    def test_datetime_object_as_timestamp(self):
        dt = datetime(2026, 4, 6, 10, 0, 0, tzinfo=timezone.utc)
        body = {
            "machine_id": "PUMP-1001",
            "timestamp": dt,
            "variable": "temperature_c",
            "value": 65.0,
        }
        event = parse_sensor_payload(body)
        assert event.timestamp == dt


# ---------------------------------------------------------------------------
# Missing / empty fields
# ---------------------------------------------------------------------------

class TestMissingFields:
    VALID = {
        "machine_id": "PUMP-1001",
        "timestamp": "2026-04-06T10:00:00Z",
        "variable": "temperature_c",
        "value": 70.0,
    }

    @pytest.mark.parametrize("field", ["machine_id", "timestamp", "variable", "value"])
    def test_missing_required_field_raises(self, field):
        body = {k: v for k, v in self.VALID.items() if k != field}
        with pytest.raises(ValueError, match=field):
            parse_sensor_payload(body)

    def test_empty_machine_id_raises(self):
        body = {**self.VALID, "machine_id": "   "}
        with pytest.raises(ValueError, match="machine_id"):
            parse_sensor_payload(body)


# ---------------------------------------------------------------------------
# Bad values
# ---------------------------------------------------------------------------

class TestInvalidValues:
    VALID = {
        "machine_id": "PUMP-1001",
        "timestamp": "2026-04-06T10:00:00Z",
        "variable": "temperature_c",
        "value": 70.0,
    }

    def test_unknown_variable_raises(self):
        body = {**self.VALID, "variable": "mystery_signal"}
        with pytest.raises(ValueError, match="variable"):
            parse_sensor_payload(body)

    def test_non_numeric_value_raises(self):
        body = {**self.VALID, "value": "hot"}
        with pytest.raises(ValueError, match="value"):
            parse_sensor_payload(body)

    def test_none_value_raises(self):
        body = {**self.VALID, "value": None}
        with pytest.raises(ValueError, match="value"):
            parse_sensor_payload(body)

    def test_bad_timestamp_raises(self):
        body = {**self.VALID, "timestamp": "not-a-date"}
        with pytest.raises(ValueError, match="timestamp"):
            parse_sensor_payload(body)

    def test_empty_timestamp_raises(self):
        body = {**self.VALID, "timestamp": ""}
        with pytest.raises(ValueError, match="timestamp"):
            parse_sensor_payload(body)


# ---------------------------------------------------------------------------
# ALLOWED_VARIABLES content check
# ---------------------------------------------------------------------------

def test_allowed_variables_contains_expected_set():
    expected = {"vibration_mm_s", "temperature_c", "current_a", "pressure_bar", "load_pct"}
    assert expected == set(ALLOWED_VARIABLES)