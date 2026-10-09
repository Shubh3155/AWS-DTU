"""Leakage and arithmetic checks; these fixtures are not empirical validation."""

from datetime import timedelta

import pytest

from app.model.baseline import BaselinePolicy
from app.model.validation import evaluate, metrics
from tests.test_baseline import NOW, stations


def test_station_holdout_excludes_target_history_and_future_donors():
    early = NOW - timedelta(hours=1)
    targets = stations(100, offset=100, observed=early)[:1] + stations(100, offset=100)[:1]
    donors = stations(20, observed=early) + stations(999, observed=NOW + timedelta(hours=1))
    result = evaluate(targets + donors, NOW, BaselinePolicy())
    target_rows = [r for r in result["rows"] if r["station_id"] == 101]
    assert len(target_rows) == 2
    assert all(r["predicted"] == pytest.approx(20) for r in target_rows)
    assert all(101 not in r["supporting_sensor_ids"] for r in target_rows)
    assert {r["split"] for r in target_rows} == {"early", "later"}


def test_unsupported_targets_remain_in_denominator():
    result = evaluate(
        stations(observed=NOW - timedelta(hours=1)) + stations(), NOW, BaselinePolicy()
    )
    for summary in result["summary"].values():
        assert summary["targets"] == 3
        assert summary["unsupported"] == 3
        assert summary["coverage_percent"] == 0
        assert summary["mae"] is None


def test_metrics_preserve_signed_bias_and_missing_count():
    result = metrics([{"error": -3}, {"error": 4}, {"error": None}])
    assert result["mae"] == 3.5
    assert result["rmse"] == pytest.approx((12.5) ** 0.5)
    assert result["bias"] == 0.5
    assert result["unsupported"] == 1


def test_cutoff_requires_timezone_and_two_blocks():
    with pytest.raises(ValueError):
        evaluate(stations(), NOW.replace(tzinfo=None), BaselinePolicy())
    with pytest.raises(ValueError):
        evaluate(stations(), NOW, BaselinePolicy())
