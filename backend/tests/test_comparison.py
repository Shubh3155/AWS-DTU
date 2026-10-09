"""Synthetic comparison fixtures verify ranking and explicit live/replay semantics."""

from datetime import UTC, datetime, timedelta

import pytest

from app.model.baseline import BaselinePolicy
from app.model.contracts import StationObservation
from app.schemas.routes import ComparisonRequest, Coordinate, LineString
from app.services.comparison import compare_routes
from app.services.snapshots import PollutionSnapshot
from app.services.walking import WalkingRoute, WalkingStep

NOW = datetime(2026, 10, 9, 10, tzinfo=UTC)


def walking(duration=1200.0, lng=77.2, identity="fast"):
    geometry = LineString(coordinates=[(lng, 28.6), (lng + 0.0001, 28.6001)])
    return WalkingRoute(
        id=identity,
        geometry=geometry,
        duration=duration,
        distance=15.0,
        steps=[WalkingStep(geometry=geometry, duration=duration, distance=15.0)],
    )


def stations(value=80.0, lng=77.2, offset=0, observed=NOW):
    return [
        StationObservation(
            station_id=offset + index + 1,
            sensor_id=offset + index + 1,
            location=Coordinate(lat=28.6 + delta, lng=lng),
            pm25_micrograms_per_m3=value,
            observed_at=observed,
            fetched_at=NOW,
            provider_id="synthetic",
        )
        for index, delta in enumerate([0.0, 0.001, -0.001])
    ]


def snapshot(readings, mode="replay"):
    return PollutionSnapshot(
        snapshot_id="synthetic-snapshot",
        data_version="synthetic-v1",
        data_mode=mode,
        observed_to=max(reading.observed_at for reading in readings),
        fetched_at=NOW,
        observations=readings,
    )


def request(detour=5.0, mode="replay"):
    return ComparisonRequest(
        origin=Coordinate(lat=28.6, lng=77.2),
        destination=Coordinate(lat=28.61, lng=77.21),
        max_detour_minutes=detour,
        data_mode=mode,
    )


def test_live_freshness_uses_observation_time_not_fetch_time():
    old = stations(observed=NOW - timedelta(days=5))
    result = compare_routes(
        [walking()], request(mode="live"), snapshot(old, "live"), BaselinePolicy(), now=NOW
    )
    assert result.candidates[0].estimated_exposure is None
    assert result.data_quality.station_count == 0
    assert result.status == "limited_data"


def test_replay_is_explicit_and_excludes_years_old_readings():
    readings = stations(observed=NOW - timedelta(days=5)) + stations(
        offset=10, observed=NOW - timedelta(days=365)
    )
    result = compare_routes([walking()], request(), snapshot(readings), BaselinePolicy(), now=NOW)
    assert result.data_quality.data_mode == "replay"
    assert result.data_quality.reference_time == NOW - timedelta(days=5)
    assert result.data_quality.station_count == 3
    assert result.candidates[0].estimated_exposure == pytest.approx(1600)
    assert result.status == "single_candidate"
    assert result.estimated_reduction_percent is None


def test_replay_snapshot_can_never_silently_satisfy_live_request():
    result = compare_routes(
        [walking()], request(mode="live"), snapshot(stations()), BaselinePolicy(), now=NOW
    )
    assert result.data_quality.data_mode == "unavailable"
    assert result.candidates[0].estimated_exposure is None


def test_longer_lower_concentration_can_have_higher_exposure():
    readings = stations(80) + stations(70, lng=77.22, offset=10)
    routes = [walking(), walking(1500.0, 77.22, "slow")]
    result = compare_routes(
        routes, request(), snapshot(readings), BaselinePolicy(station_radius_metres=500)
    )
    assert [route.estimated_exposure for route in result.candidates] == pytest.approx([1600, 1750])
    assert result.lowest_exposure_eligible_id == "fast"
    assert result.status == "no_lower_exposure_candidate"


def test_lower_model_estimate_is_ranked_but_not_a_validated_reduction_claim():
    readings = stations(80) + stations(50, lng=77.22, offset=10)
    result = compare_routes(
        [walking(), walking(1500.0, 77.22, "slow")],
        request(),
        snapshot(readings),
        BaselinePolicy(station_radius_metres=500),
    )
    assert result.lowest_exposure_eligible_id == "slow"
    assert result.candidates[1].estimated_exposure == pytest.approx(1250)
    assert result.status == "uncertain_difference"
    assert result.estimated_reduction_percent is None


def test_budget_uses_unrounded_seconds():
    readings = stations(80) + stations(50, lng=77.22, offset=10)
    for seconds, eligible in [(1500.0, True), (1500.01, False)]:
        result = compare_routes(
            [walking(), walking(seconds, 77.22, "slow")],
            request(),
            snapshot(readings),
            BaselinePolicy(station_radius_metres=500),
        )
        assert result.candidates[1].within_budget is eligible
        assert result.lowest_exposure_eligible_id == ("slow" if eligible else "fast")


def test_missing_eligible_candidate_withholds_comparison():
    result = compare_routes(
        [walking(), walking(1500.0, 77.22, "slow")],
        request(),
        snapshot(stations()),
        BaselinePolicy(station_radius_metres=500),
    )
    assert result.candidates[0].estimated_exposure is not None
    assert result.lowest_exposure_eligible_id is None
    assert result.status == "limited_data"


def test_missing_outside_budget_candidate_does_not_block_supported_comparison():
    result = compare_routes(
        [walking(), walking(1500.01, 77.22, "slow")],
        request(),
        snapshot(stations()),
        BaselinePolicy(station_radius_metres=500),
    )
    assert result.candidates[1].estimated_exposure is None
    assert not result.candidates[1].within_budget
    assert result.lowest_exposure_eligible_id == "fast"


def test_equal_exposure_tie_favors_shorter_duration():
    result = compare_routes(
        [walking(), walking(2400.0, 77.22, "slow")],
        request(detour=20),
        snapshot(stations(80) + stations(40, lng=77.22, offset=10)),
        BaselinePolicy(station_radius_metres=500),
    )
    assert [route.estimated_exposure for route in result.candidates] == pytest.approx([1600, 1600])
    assert result.lowest_exposure_eligible_id == "fast"


def test_no_routes_and_policy_versions_are_reproducible():
    assert compare_routes([], request(), None, BaselinePolicy()).status == "no_route"
    assert BaselinePolicy().version == BaselinePolicy().version
    assert BaselinePolicy(max_age_hours=4).version != BaselinePolicy().version
