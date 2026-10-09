from datetime import timedelta

import pytest
from test_baseline import NOW, stations

from app.model.baseline import BaselinePolicy
from app.model.validation import evaluate
from app.schemas.routes import Coordinate
from scripts.compare_estimators import median_estimate


def test_median_challenger_keeps_outlier_and_gives_each_station_one_vote():
    readings = stations(20)
    readings[0].pm25_micrograms_per_m3 = 1000
    result = median_estimate(Coordinate(lat=28.6, lng=77.2), readings, BaselinePolicy())
    assert result.pm25_micrograms_per_m3 == 20
    assert result.supporting_sensor_ids == [1, 2, 3]
    assert readings[0].pm25_micrograms_per_m3 == 1000
    for reading in readings:
        reading.station_id = 1
        reading.location = readings[0].location
    assert (
        median_estimate(
            Coordinate(lat=28.6, lng=77.2), readings, BaselinePolicy()
        ).pm25_micrograms_per_m3
        is None
    )


def test_experimental_evaluation_preserves_station_and_future_exclusion():
    early = NOW - timedelta(hours=1)
    targets = stations(100, offset=100, observed=early)[:1] + stations(100, offset=100)[:1]
    donors = stations(20, observed=early) + stations(999, observed=NOW + timedelta(hours=1))
    result = evaluate(targets + donors, NOW, BaselinePolicy(), estimator=median_estimate)
    rows = [row for row in result["rows"] if row["station_id"] == 101]
    assert len(rows) == 2
    assert all(row["predicted"] == pytest.approx(20) for row in rows)
    assert all(101 not in row["supporting_sensor_ids"] for row in rows)
