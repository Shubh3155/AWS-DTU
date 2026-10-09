from datetime import timedelta

import httpx
import pytest
from test_comparison import NOW, snapshot, stations

from app.model.baseline import BaselinePolicy
from app.schemas.routes import Coordinate
from app.services.history import download_hours
from scripts.assess_coverage import assess

HISTORY_END = NOW - timedelta(days=2)


def audit():
    return {
        "stations": [
            {
                "station_id": 1,
                "coordinates": {"latitude": 28.6, "longitude": 77.2},
                "provider": {"id": 1},
                "licenses": [{"name": "fixture"}],
                "measurements": [{"sensor_id": 5}, {"sensor_id": 6}],
            }
        ]
    }


def reading():
    return {
        "value": 80.0,
        "parameter": {"name": "pm25", "units": "µg/m³"},
        "period": {
            "datetimeFrom": {"utc": (HISTORY_END - timedelta(hours=1)).isoformat()},
            "datetimeTo": {"utc": HISTORY_END.isoformat()},
        },
        "coverage": {"percentComplete": 100},
    }


def test_hourly_download_preserves_provider_units_periods_and_limits():
    calls = []

    def provider(request):
        calls.append(request)
        return httpx.Response(200, json={"results": [reading()]})

    with httpx.Client(
        base_url="https://api.openaq.org", transport=httpx.MockTransport(provider)
    ) as client:
        result = download_hours(
            client, audit(), HISTORY_END - timedelta(days=1), HISTORY_END, max_sensors=1
        )
    assert len(calls) == 1
    assert calls[0].url.path == "/v3/sensors/5/hours"
    assert "datetime_from" in calls[0].url.params
    measurement = result["stations"][0]["measurements"][0]
    assert measurement["observed_at"] == HISTORY_END.isoformat()
    assert measurement["unit"] == "µg/m³"
    assert measurement["coverage"]["percentComplete"] == 100
    assert result["sensor_selection_capped"]


def test_history_rejects_unbounded_or_naive_intervals():
    with httpx.Client() as client:
        for start, end in [
            (NOW - timedelta(days=8), NOW),
            (NOW, NOW),
            (NOW.replace(tzinfo=None) - timedelta(days=1), NOW),
        ]:
            with pytest.raises(ValueError):
                download_hours(client, audit(), start, end)


def test_history_rate_limit_is_not_retried():
    calls = []

    def provider(request):
        calls.append(request)
        return httpx.Response(429)

    with httpx.Client(
        base_url="https://api.openaq.org", transport=httpx.MockTransport(provider)
    ) as client:
        with pytest.raises(httpx.HTTPStatusError):
            download_hours(client, audit(), HISTORY_END - timedelta(days=1), HISTORY_END)
    assert len(calls) == 1


def test_coverage_does_not_approve_pilot_or_invent_validation():
    old = stations(observed=NOW - timedelta(days=5))
    result = assess(snapshot(old), Coordinate(lat=28.6, lng=77.2), BaselinePolicy(), NOW)
    assert result["windows"]["live"]["nearby_stations"] == 0
    assert result["windows"]["replay"]["point_support_sufficient"]
    assert not result["station_holdout_count_prerequisite"]
    assert not result["temporal_holdout_count_prerequisite"]
    assert not result["pilot_approved"]


def test_coverage_records_count_prerequisites_without_accuracy_claims():
    readings = stations() + stations(offset=10) + stations(observed=NOW - timedelta(hours=1))
    result = assess(snapshot(readings), Coordinate(lat=28.6, lng=77.2), BaselinePolicy(), NOW)
    assert result["station_holdout_count_prerequisite"]
    assert result["temporal_holdout_count_prerequisite"]
    assert "mae" not in result
