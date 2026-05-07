from src.prediction import (
    _features_by_variable,
    _score_and_risk,
)


sample_rows = [
    {
        "machine_id": "PUMP-1001",
        "timestamp": "2026-05-07T03:00:00Z",
        "variable": "temperature_c",
        "value": 72.0,
    },
    {
        "machine_id": "PUMP-1001",
        "timestamp": "2026-05-07T04:00:00Z",
        "variable": "temperature_c",
        "value": 74.0,
    },
    {
        "machine_id": "PUMP-1001",
        "timestamp": "2026-05-07T05:00:00Z",
        "variable": "vibration_mm_s",
        "value": 3.8,
    },
]


def test_features_by_variable_returns_aggregates():
    result = _features_by_variable(sample_rows)

    assert "temperature_c" in result
    assert result["temperature_c"]["max"] == 74.0
    assert result["temperature_c"]["count"] == 2.0



def test_score_and_risk_detects_threshold_excess():
    features = {
        "temperature_c": {
            "last": 74.0,
            "mean": 73.0,
            "max": 74.0,
            "count": 2.0,
        }
    }

    score, risk = _score_and_risk(features)

    assert score > 0
    assert len(risk) > 0
    assert "supera umbral nominal" in risk[0]