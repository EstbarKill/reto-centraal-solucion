from datetime import datetime, timezone

from src.models import SensorEvent


def test_sensor_event_generates_event_id():
    event = SensorEvent(
        machine_id="PUMP-1001",
        timestamp=datetime(2026, 5, 7, 3, 0, tzinfo=timezone.utc),
        variable="temperature_c",
        value=71.8,
    )

    assert event.event_id is not None
    assert isinstance(event.event_id, str)
    assert len(event.event_id) == 64


def test_to_ndjson_dict_contains_expected_fields():
    event = SensorEvent(
        machine_id="PUMP-1001",
        timestamp=datetime(2026, 5, 7, 3, 0, tzinfo=timezone.utc),
        variable="temperature_c",
        value=71.8,
    )

    result = event.to_ndjson_dict()

    assert result["machine_id"] == "PUMP-1001"
    assert result["variable"] == "temperature_c"
    assert result["value"] == 71.8
    assert result["timestamp"] == "2026-05-07T03:00:00Z"
    assert "event_id" in result