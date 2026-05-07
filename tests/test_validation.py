from src.validation import parse_sensor_payload


def test_parse_sensor_payload_valid():
    payload = {
        "machine_id": "PUMP-1001",
        "timestamp": "2026-05-07T03:00:00Z",
        "variable": "temperature_c",
        "value": 71.8,
    }

    event = parse_sensor_payload(payload)

    assert event.machine_id == "PUMP-1001"
    assert event.variable == "temperature_c"
    assert event.value == 71.8


def test_parse_sensor_payload_missing_field():
    payload = {
        "machine_id": "PUMP-1001",
        "variable": "temperature_c",
        "value": 71.8,
    }

    try:
        parse_sensor_payload(payload)
        assert False

    except ValueError as e:
        assert "Campos requeridos faltantes" in str(e)


def test_parse_sensor_payload_invalid_variable():
    payload = {
        "machine_id": "PUMP-1001",
        "timestamp": "2026-05-07T03:00:00Z",
        "variable": "invalid_variable",
        "value": 71.8,
    }

    try:
        parse_sensor_payload(payload)
        assert False

    except ValueError as e:
        assert "variable debe ser una de" in str(e)


def test_parse_sensor_payload_invalid_timestamp():
    payload = {
        "machine_id": "PUMP-1001",
        "timestamp": "invalid-date",
        "variable": "temperature_c",
        "value": 71.8,
    }

    try:
        parse_sensor_payload(payload)
        assert False

    except ValueError as e:
        assert "timestamp debe ser ISO8601" in str(e)