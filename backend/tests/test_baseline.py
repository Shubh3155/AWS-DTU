"""Synthetic arithmetic/support fixtures; these are not Delhi validation results."""

import math
from datetime import UTC, datetime, timedelta

import pytest

from app.model.baseline import (
    BaselinePolicy,
    distance_metres,
    interpolate,
    score_route,
    segment_route,
    usable_observations,
)
from app.model.contracts import StationObservation
from app.schemas.routes import Coordinate, LineString
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


def test_constant_concentration_uses_minutes_once():
    result = score_route(walking(), stations(), BaselinePolicy())
    assert result.exposure == pytest.approx(1600.0)
    assert result.coverage_percent == 100


def test_mixed_step_concentrations_use_each_steps_own_travel_time():
    route = walking(600.0)
    route.duration = 1800.0
    route.steps.append(walking(1200.0, lng=77.22).steps[0])
    readings = stations(80) + stations(50, lng=77.22, offset=10)
    result = score_route(route, readings, BaselinePolicy(station_radius_metres=500))
    assert result.exposure == pytest.approx(80 * 10 + 50 * 20)


def test_non_finite_exposure_is_withheld():
    result = score_route(walking(), stations(1e308), BaselinePolicy())
    assert result.exposure is None
    assert any("numeric range" in warning for warning in result.warnings)


def test_subdivision_preserves_step_and_route_duration_with_rounding():
    route = walking(1200.002)
    route.steps[0].duration = 1200.0
    segments = segment_route(route, BaselinePolicy(sampling_interval_metres=5))
    assert len(segments) > 1
    assert math.fsum(segment.duration_seconds for segment in segments) == pytest.approx(
        route.duration
    )
    assert all(segment.duration_seconds > 0 for segment in segments)


def test_waiting_and_repeated_coordinates_preserve_time():
    route = walking()
    point = (77.2, 28.6)
    route.steps[0].duration = 1190
    route.steps.append(
        WalkingStep(
            geometry=LineString(coordinates=[point, point]),
            duration=10.0,
            distance=0.0,
        )
    )
    assert math.fsum(s.duration_seconds for s in segment_route(route, BaselinePolicy())) == 1200
    assert score_route(route, stations(), BaselinePolicy()).exposure == pytest.approx(1600)


def test_bad_step_times_do_not_create_an_exposure():
    route = walking()
    route.steps[0].duration = 600
    score = score_route(route, stations(), BaselinePolicy())
    assert score.exposure is None
    assert any("disagree" in warning for warning in score.warnings)


def test_zero_duration_has_no_supported_exposure():
    assert score_route(walking(0.0), stations(), BaselinePolicy()).exposure is None


def test_too_few_stations_never_become_zero_pollution():
    result = score_route(walking(), stations()[:2], BaselinePolicy())
    assert result.exposure is None
    assert result.coverage_percent == 0


def test_many_sensors_at_one_station_are_not_independent_spatial_support():
    readings = stations()
    for reading in readings:
        reading.station_id = 1
        reading.location = readings[0].location
    assert (
        interpolate(
            Coordinate(lat=28.6, lng=77.2), readings, BaselinePolicy()
        ).pm25_micrograms_per_m3
        is None
    )


def test_partial_coverage_withholds_the_whole_score():
    route = walking()
    route.geometry = LineString(coordinates=[(77.2, 28.6), (77.3, 28.6)])
    route.steps[0].geometry = route.geometry
    result = score_route(route, stations(), BaselinePolicy(station_radius_metres=500))
    assert 0 < result.coverage_percent < 100
    assert result.exposure is None


def test_latest_station_time_replaces_older_sensor_time():
    newer = stations(value=50)
    older = stations(value=100, observed=NOW - timedelta(hours=1))
    assert usable_observations(newer + older, NOW, BaselinePolicy()) == newer


def test_distance_crosses_dateline_without_sampling_the_opposite_side():
    assert (
        distance_metres(Coordinate(lat=0.0, lng=179.999), Coordinate(lat=0.0, lng=-179.999)) < 300
    )
    route = walking(60.0)
    route.steps[0].geometry = LineString(coordinates=[(179.999, 0.0), (-179.999, 0.0)])
    assert all(abs(s.location.lng) > 179 for s in segment_route(route, BaselinePolicy()))
