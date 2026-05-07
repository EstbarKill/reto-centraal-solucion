"""Tests for src/prediction.py — scoring, feature aggregation, sigmoid."""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import math
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

# We import internal helpers by importing the module and accessing them.
import src.prediction as pred_module
from src.prediction import (
    _sigmoid,
    _features_by_variable,
    _score_and_risk,
    compute_prediction_for_machine,
    NOMINAL_MAX,
)


# ---------------------------------------------------------------------------
# _sigmoid
# ---------------------------------------------------------------------------

class TestSigmoid:
    def test_zero_gives_half(self):
        assert _sigmoid(0) == pytest.approx(0.5)

    def test_large_positive_approaches_one(self):
        assert _sigmoid(100) == pytest.approx(1.0, abs=1e-6)

    def test_large_negative_approaches_zero(self):
        assert _sigmoid(-100) == pytest.approx(0.0, abs=1e-6)

    def test_output_always_in_0_1(self):
        for x in [-10, -1, 0, 1, 10]:
            result = _sigmoid(x)
            assert 0.0 <= result <= 1.0


# ---------------------------------------------------------------------------
# _features_by_variable
# ---------------------------------------------------------------------------

def _row(variable: str, value: float, hours_ago: float = 1.0) -> dict:
    ts = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return {
        "machine_id": "PUMP-X",
        "timestamp": ts.isoformat(),
        "variable": variable,
        "value": value,
    }


class TestFeaturesAggregation:
    def test_single_row_last_mean_max_equal(self):
        rows = [_row("temperature_c", 70.0)]
        features = _features_by_variable(rows)
        assert "temperature_c" in features
        f = features["temperature_c"]
        assert f["last"] == 70.0
        assert f["mean"] == 70.0
        assert f["max"] == 70.0
        assert f["count"] == 1.0

    def test_multiple_rows_aggregated_correctly(self):
        rows = [
            _row("temperature_c", 60.0, hours_ago=3),
            _row("temperature_c", 80.0, hours_ago=2),
            _row("temperature_c", 70.0, hours_ago=1),
        ]
        features = _features_by_variable(rows)
        f = features["temperature_c"]
        # Latest timestamp = hours_ago=1, value 70
        assert f["last"] == 70.0
        assert f["max"] == 80.0
        assert f["mean"] == pytest.approx((60 + 80 + 70) / 3)
        assert f["count"] == 3.0

    def test_multiple_variables_returned(self):
        rows = [_row("temperature_c", 65.0), _row("vibration_mm_s", 3.0)]
        features = _features_by_variable(rows)
        assert set(features.keys()) == {"temperature_c", "vibration_mm_s"}

    def test_empty_rows_returns_empty_dict(self):
        assert _features_by_variable([]) == {}

    def test_row_with_invalid_timestamp_skipped(self):
        rows = [
            {"machine_id": "X", "timestamp": "not-a-date", "variable": "temperature_c", "value": 90.0},
            _row("temperature_c", 65.0),
        ]
        features = _features_by_variable(rows)
        # Only the valid row counts
        assert features["temperature_c"]["count"] == 1.0
        assert features["temperature_c"]["last"] == 65.0


# ---------------------------------------------------------------------------
# _score_and_risk
# ---------------------------------------------------------------------------

class TestScoreAndRisk:
    def test_all_below_threshold_zero_score(self):
        features = {
            "temperature_c": {"last": 60.0, "mean": 60.0, "max": 65.0, "count": 5.0},
            "vibration_mm_s": {"last": 3.0, "mean": 3.0, "max": 4.0, "count": 5.0},
        }
        score, risk = _score_and_risk(features)
        assert score == pytest.approx(0.0)
        assert risk == []

    def test_temperature_above_threshold_generates_risk(self):
        # temperature_c nominal max is 70.0
        features = {
            "temperature_c": {"last": 85.0, "mean": 80.0, "max": 90.0, "count": 3.0},
        }
        score, risk = _score_and_risk(features)
        assert score > 0
        # Risk factors should mention temperature_c
        assert any("temperature_c" in r for r in risk)

    def test_exactly_at_threshold_no_risk(self):
        cap = NOMINAL_MAX["temperature_c"]  # 70.0
        features = {
            "temperature_c": {"last": cap, "mean": cap, "max": cap, "count": 1.0},
        }
        score, risk = _score_and_risk(features)
        assert score == pytest.approx(0.0)
        assert risk == []

    def test_score_proportional_to_excess(self):
        # Double the excess → roughly double the contribution
        cap = NOMINAL_MAX["temperature_c"]
        features_small = {"temperature_c": {"last": cap + 5, "mean": cap + 5, "max": cap + 5, "count": 1.0}}
        features_large = {"temperature_c": {"last": cap + 10, "mean": cap + 10, "max": cap + 10, "count": 1.0}}
        score_small, _ = _score_and_risk(features_small)
        score_large, _ = _score_and_risk(features_large)
        assert score_large > score_small

    def test_unknown_variable_ignored(self):
        features = {
            "mystery_variable": {"last": 9999.0, "mean": 9999.0, "max": 9999.0, "count": 1.0}
        }
        score, risk = _score_and_risk(features)
        assert score == pytest.approx(0.0)
        assert risk == []


# ---------------------------------------------------------------------------
# compute_prediction_for_machine (with mocked storage)
# ---------------------------------------------------------------------------

class TestComputePrediction:
    def _normal_rows(self, machine_id: str = "PUMP-1001") -> list[dict]:
        """Rows with all variables well within thresholds."""
        vars_values = {
            "temperature_c": 65.0,
            "vibration_mm_s": 3.5,
            "current_a": 10.0,
            "pressure_bar": 3.0,
            "load_pct": 70.0,
        }
        rows = []
        for var, val in vars_values.items():
            rows.append(_row(var, val, hours_ago=1))
        return rows

    def test_no_events_returns_base_probability(self):
        with patch("src.prediction.iter_events_in_window", return_value=iter([])):
            with patch("src.prediction.list_machine_prefixes", return_value=[]):
                result = compute_prediction_for_machine("PUMP-UNKNOWN")

        assert result["machine_id"] == "PUMP-UNKNOWN"
        assert result["events_considered"] == 0
        assert result["failure_probability_24h"] < 0.3  # base low probability
        assert "Sin eventos" in result["risk_factors"][0]

    def test_normal_readings_low_probability(self):
        rows = self._normal_rows()
        with patch("src.prediction.iter_events_in_window", return_value=iter(rows)):
            result = compute_prediction_for_machine("PUMP-1001")

        assert result["failure_probability_24h"] < 0.5
        assert result["events_considered"] > 0

    def test_critical_temperature_high_probability(self):
        """Sustained temperatures well above threshold → high failure probability."""
        rows = []
        for h in range(1, 10):
            rows.append(_row("temperature_c", 95.0, hours_ago=h))
        with patch("src.prediction.iter_events_in_window", return_value=iter(rows)):
            result = compute_prediction_for_machine("PUMP-1001")

        assert result["failure_probability_24h"] > 0.5
        assert any("temperature_c" in rf for rf in result["risk_factors"])

    def test_result_structure_complete(self):
        rows = self._normal_rows()
        with patch("src.prediction.iter_events_in_window", return_value=iter(rows)):
            result = compute_prediction_for_machine("PUMP-1001")

        required_keys = {
            "machine_id",
            "failure_probability_24h",
            "risk_factors",
            "window_hours",
            "events_considered",
            "features_by_variable",
        }
        assert required_keys.issubset(result.keys())

    def test_probability_bounded_0_1(self):
        # Even with extreme values, probability must stay in [0, 1]
        extreme_rows = [_row("temperature_c", 10_000.0, hours_ago=h) for h in range(1, 5)]
        with patch("src.prediction.iter_events_in_window", return_value=iter(extreme_rows)):
            result = compute_prediction_for_machine("PUMP-X")

        prob = result["failure_probability_24h"]
        assert 0.0 <= prob <= 1.0

    def test_higher_values_mean_higher_probability(self):
        """More severe readings should produce higher probability than normal readings."""
        normal_rows = self._normal_rows()
        critical_rows = [_row("temperature_c", 95.0, hours_ago=h) for h in range(1, 5)]

        with patch("src.prediction.iter_events_in_window", return_value=iter(normal_rows)):
            normal_result = compute_prediction_for_machine("PUMP-1001")

        with patch("src.prediction.iter_events_in_window", return_value=iter(critical_rows)):
            critical_result = compute_prediction_for_machine("PUMP-1001")

        assert critical_result["failure_probability_24h"] > normal_result["failure_probability_24h"]

    def test_window_hours_returned(self):
        with patch("src.prediction.iter_events_in_window", return_value=iter([])):
            result = compute_prediction_for_machine("PUMP-1001", hours=24)
        assert result["window_hours"] == 24


# ---------------------------------------------------------------------------
# NOMINAL_MAX sanity check
# ---------------------------------------------------------------------------

def test_nominal_max_covers_all_allowed_variables():
    from src.validation import ALLOWED_VARIABLES
    # Every allowed variable should have a nominal max defined
    for var in ALLOWED_VARIABLES:
        assert var in NOMINAL_MAX, f"Missing NOMINAL_MAX entry for '{var}'"