"""Synthetic support checks, not empirical Delhi ranking validation."""

from dataclasses import replace
from datetime import timedelta

import pytest

from app.model.baseline import BaselinePolicy
from app.model.sensitivity import assess_ranking
from app.schemas.routes import ComparisonRequest
from app.services.snapshots import PollutionSnapshot
from tests.test_baseline import NOW, stations, walking


def inputs():
    routes = [walking(identity="fast"), walking(duration=1500, identity="slow")]
    readings = stations(observed=NOW - timedelta(hours=1.5))
    snapshot = PollutionSnapshot(
        snapshot_id="synthetic",
        data_version="synthetic",
        data_mode="replay",
        observed_to=NOW,
        fetched_at=NOW,
        observations=readings,
    )
    request = ComparisonRequest(
        origin={"lat": 28.6, "lng": 77.2},
        destination={"lat": 28.61, "lng": 77.21},
        data_mode="replay",
        max_detour_minutes=5.0,
    )
    return routes, request, snapshot


def test_missing_support_prevents_stability_claim():
    result = assess_ranking(*inputs(), [BaselinePolicy(max_age_hours=1), BaselinePolicy()])
    assert result["summary"]["ranking_available"] == 1
    assert result["summary"]["ranking_unavailable"] == 1
    assert not result["summary"]["stable_across_all_tested_policies"]
    assert result["results"][0]["agrees_with_baseline"] is None


def test_constant_field_keeps_fastest_and_actual_budget_eligibility():
    routes, request, snapshot = inputs()
    request.max_detour_minutes = 0.0
    result = assess_ranking(
        routes, request, snapshot, [BaselinePolicy(), BaselinePolicy(max_age_hours=4)]
    )
    assert result["summary"]["stable_across_all_tested_policies"]
    assert result["summary"]["selection_changes_from_baseline"] == 0
    assert all(
        [r["within_budget"] for r in row["candidates"]] == [True, False]
        for row in result["results"]
    )


def test_live_mode_and_duplicate_policies_are_rejected():
    routes, request, snapshot = inputs()
    request.data_mode = "live"
    with pytest.raises(ValueError):
        assess_ranking(routes, request, snapshot, [BaselinePolicy()])
    request.data_mode = "replay"
    with pytest.raises(ValueError):
        assess_ranking(routes, request, snapshot, [BaselinePolicy(), BaselinePolicy()])


def test_older_nearby_stations_can_reverse_selection():
    routes, request, snapshot = inputs()
    routes[1] = walking(duration=1500, lng=77.22, identity="slow")
    old = stations(200, lng=77.22, offset=20, observed=NOW - timedelta(hours=3))
    for reading in old:
        reading.location.lat = 28.6
    snapshot = replace(
        snapshot, observations=stations(80) + stations(20, lng=77.22, offset=10) + old
    )
    result = assess_ranking(
        routes, request, snapshot, [BaselinePolicy(), BaselinePolicy(max_age_hours=4)]
    )
    assert result["baseline_selected_id"] == "slow"
    assert result["results"][1]["selected_id"] == "fast"
    assert result["summary"]["selection_changes_from_baseline"] == 1
    assert not result["summary"]["stable_across_all_tested_policies"]
