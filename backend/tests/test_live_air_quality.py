"""Synthetic provider responses exercise live region coverage and failure semantics."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier, Event

import httpx
import pytest
from fastapi.testclient import TestClient
from test_comparison import NOW, request, walking

from app.core.config import Settings
from app.core.runtime_cache import RuntimeCache
from app.main import create_app
from app.model.baseline import BaselinePolicy
from app.schemas.routes import Coordinate, LineString
from app.services.comparison import compare_routes
from app.services.live_air_quality import (
    MAX_LOCATIONS,
    AirQualitySample,
    LiveAirQuality,
    LiveAirQualityCache,
    fetch_live_air_quality,
    region_key,
)
from scripts.check_release import verify_mode


def payload(lat=28.6, lng=77.2, value=50.0, timestamp=NOW, interval=3600):
    return {
        "latitude": lat,
        "longitude": lng,
        "utc_offset_seconds": 0,
        "current_units": {"pm2_5": "μg/m³", "time": "unixtime"},
        "current": {"time": timestamp.timestamp(), "interval": interval, "pm2_5": value},
    }


def provider(calls, transform=lambda item: item):
    def respond(req):
        calls.append(req)
        latitudes = req.url.params["latitude"].split(",")
        longitudes = req.url.params["longitude"].split(",")
        items = [
            transform(payload(float(lat), float(lng)))
            for lat, lng in zip(latitudes, longitudes, strict=True)
        ]
        return httpx.Response(200, json=items if len(items) > 1 else items[0])

    return respond


def fetch(routes, respond, cache=None, reference=NOW, policy=None):
    with httpx.Client(
        base_url="https://air-quality-api.open-meteo.com", transport=httpx.MockTransport(respond)
    ) as client:
        return fetch_live_air_quality(
            routes, policy or BaselinePolicy(), cache or RuntimeCache(), reference, client
        )


def test_requests_regions_along_the_actual_path_and_deduplicates_alternatives():
    route = walking()
    # Endpoints share a latitude; the route goes north before returning south.
    route.geometry = LineString(coordinates=[(77.2, 28.6), (77.22, 28.68), (77.24, 28.6)])
    route.steps[0].geometry = route.geometry
    calls = []
    data, warnings = fetch([route, route.model_copy(update={"id": "alternative"})], provider(calls))
    assert not warnings
    assert len(calls) == 1
    assert calls[0].url.path == "/v1/air-quality"
    assert calls[0].url.params["current"] == "pm2_5"
    assert calls[0].url.params["timeformat"] == "unixtime"
    assert calls[0].url.params["domains"] == "cams_global"
    assert max(key[0] for key in data.samples) >= 28.66
    assert len(data.samples) == len(set(data.samples))
    assert data.score(route, BaselinePolicy(), NOW).coverage_percent == 100
    assert data.score(route, BaselinePolicy(), NOW).exposure == pytest.approx(1000)


def test_forecast_metadata_does_not_invent_monitoring_stations_or_observation_times():
    data, _ = fetch([walking()], provider([]))
    result = compare_routes(
        [walking()], request(mode="live"), None, BaselinePolicy(), now=NOW, live_data=data
    )
    quality = result.data_quality
    assert quality.source_type == "model_forecast"
    assert quality.data_mode == "live"
    assert quality.station_count == 0 and quality.sample_count == 1
    assert quality.observed_from is quality.observed_to is quality.snapshot_id is None
    assert quality.valid_from == NOW and quality.valid_to == NOW + timedelta(hours=1)
    assert quality.spatial_resolution_km == 45
    assert "Open-Meteo" in quality.attribution and "CAMS" in quality.attribution
    assert result.candidates[0].estimated_exposure == pytest.approx(1000)
    assert result.estimated_reduction_percent is None
    verify_mode(request(mode="live"), result)


@pytest.mark.parametrize(
    "change",
    [
        {"current": {"time": NOW.timestamp(), "interval": 3600, "pm2_5": None}},
        {"current": {"time": NOW.timestamp(), "interval": 3600, "pm2_5": -1}},
        {"current": {"time": NOW.timestamp(), "interval": 3600, "pm2_5": True}},
        {"current_units": {"pm2_5": "ppm"}},
        {
            "current": {
                "time": (NOW - timedelta(hours=2)).timestamp(),
                "interval": 3600,
                "pm2_5": 50,
            }
        },
        {
            "current": {
                "time": (NOW + timedelta(hours=1)).timestamp(),
                "interval": 3600,
                "pm2_5": 50,
            }
        },
        {"latitude": 0.0, "longitude": 0.0},
        {"utc_offset_seconds": 19800},
    ],
)
def test_missing_invalid_or_wrong_time_region_data_cannot_support_a_route(change):
    data, warnings = fetch([walking()], provider([], lambda item: {**item, **change}))
    score = data.score(walking(), BaselinePolicy(), NOW)
    assert score.exposure is None and score.coverage_percent == 0
    assert data.quality(NOW, BaselinePolicy()).data_mode == "unavailable"
    assert any("missing, stale, or invalid" in warning for warning in warnings)


def test_partial_coverage_uses_travel_time_and_withholds_full_route_exposure():
    route = walking(600.0)
    route.duration = 1800.0
    route.steps.append(walking(1200.0, lng=77.24).steps[0])
    data, _ = fetch(
        [route],
        provider(
            [],
            lambda item: (
                {**item, "current": {**item["current"], "pm2_5": None}}
                if item["longitude"] > 77.22
                else item
            ),
        ),
    )
    score = data.score(route, BaselinePolicy(), NOW)
    assert score.coverage_percent == pytest.approx(100 / 3)
    assert score.exposure is None


def test_scores_each_region_with_its_preserved_step_time():
    route = walking(600.0)
    route.duration = 1800.0
    route.steps.append(walking(1200.0, lng=77.24).steps[0])
    data, _ = fetch(
        [route],
        provider(
            [],
            lambda item: {
                **item,
                "current": {**item["current"], "pm2_5": 80 if item["longitude"] < 77.22 else 25},
            },
        ),
    )
    assert data.score(route, BaselinePolicy(), NOW).exposure == pytest.approx(80 * 10 + 25 * 20)


def test_forecast_cache_reuses_regions_but_never_outlives_the_valid_interval():
    elapsed = [0]
    cache = RuntimeCache(clock=lambda: elapsed[0])
    calls = []
    respond = provider(calls, lambda item: {**item, "current": {**item["current"], "interval": 5}})
    first, _ = fetch([walking()], respond, cache)
    assert first.score(walking(), BaselinePolicy(), NOW).exposure is not None
    elapsed[0] = 4
    second, _ = fetch([walking()], respond, cache, NOW + timedelta(seconds=4))
    assert len(calls) == 1 and second.samples == first.samples
    elapsed[0] = 5
    third, warnings = fetch(
        [walking()], lambda req: httpx.Response(503), cache, NOW + timedelta(seconds=5)
    )
    assert not third.samples
    assert third.score(walking(), BaselinePolicy(), NOW + timedelta(seconds=5)).exposure is None
    assert any("API could not be read" in warning for warning in warnings)


def test_concurrent_cold_requests_share_one_regional_provider_read():
    cache = LiveAirQualityCache()
    ready = Barrier(3)
    entered, release = Event(), Event()
    calls = []

    def respond(req):
        calls.append(req)
        entered.set()
        assert release.wait(timeout=2)
        return httpx.Response(200, json=payload())

    def load():
        ready.wait(timeout=2)
        return fetch([walking()], respond, cache)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first, second = executor.submit(load), executor.submit(load)
        ready.wait(timeout=2)
        assert entered.wait(timeout=2)
        release.set()
        for future in (first, second):
            data, warnings = future.result(timeout=2)
            assert not warnings
            assert data.score(walking(), BaselinePolicy(), NOW).exposure == pytest.approx(1000)
    assert len(calls) == 1


def test_forecast_interval_that_changes_during_download_uses_response_time(monkeypatch):
    elapsed = [0]
    monkeypatch.setattr("app.services.live_air_quality.monotonic", lambda: elapsed[0])

    def respond(req):
        elapsed[0] = 1
        return httpx.Response(200, json=payload(timestamp=NOW + timedelta(seconds=1)))

    data, warnings = fetch([walking()], respond)
    assert not warnings
    quality = data.quality(NOW + timedelta(seconds=1), BaselinePolicy())
    assert quality.fetched_at == NOW + timedelta(seconds=1)
    assert data.score(walking(), BaselinePolicy(), NOW + timedelta(seconds=1)).exposure is not None


def test_rate_limits_back_off_without_discarding_supported_cached_regions():
    cache = RuntimeCache()
    fetch([walking()], provider([]), cache)
    calls = []

    def limited(req):
        calls.append(req)
        return httpx.Response(429)

    for _ in range(2):
        data, warnings = fetch([walking(), walking(lng=77.24)], limited, cache)
        assert data.score(walking(), BaselinePolicy(), NOW).exposure is not None
        assert data.score(walking(lng=77.24), BaselinePolicy(), NOW).exposure is None
        assert any("rate limited" in warning for warning in warnings)
    assert len(calls) == 1


def test_batch_limit_does_not_extrapolate_unrequested_regions():
    route = walking()
    route.geometry = LineString(coordinates=[(77.2, 28.6), (107.2, 28.6)])
    route.steps[0].geometry = route.geometry
    calls = []
    policy = BaselinePolicy(sampling_interval_metres=1000)
    data, warnings = fetch([route], provider(calls), policy=policy)
    assert len(data.samples) == MAX_LOCATIONS
    assert len(calls) == 1
    assert any("query limit" in warning for warning in warnings)
    score = data.score(route, policy, NOW)
    assert 0 < score.coverage_percent < 100 and score.exposure is None


def test_long_journeys_coarsen_queries_within_the_provider_resolution():
    route = walking()
    route.geometry = LineString(coordinates=[(77.2, 28.6), (79.2, 28.6)])
    route.steps[0].geometry = route.geometry
    calls = []
    data, warnings = fetch([route], provider(calls))
    assert not warnings and len(calls) == 1
    assert len(data.samples) <= MAX_LOCATIONS
    assert 0.02 < data.query_grid_degrees <= 0.4
    assert data.score(route, BaselinePolicy(), NOW).coverage_percent == 100


def test_malformed_batch_does_not_assign_the_wrong_region():
    data, warnings = fetch(
        [walking(), walking(lng=77.24)], lambda req: httpx.Response(200, json=payload())
    )
    assert not data.samples
    assert any("API could not be read" in warning for warning in warnings)


def test_dateline_queries_remain_local_and_zero_concentration_is_valid():
    route = walking(60.0)
    route.steps[0].geometry = LineString(coordinates=[(179.999, 0.0), (-179.999, 0.0)])
    data, _ = fetch(
        [route], provider([], lambda item: {**item, "current": {**item["current"], "pm2_5": 0}})
    )
    assert all(abs(key[1]) == 180 for key in data.samples)
    assert data.score(route, BaselinePolicy(), NOW).exposure == 0
    assert data.score(route, BaselinePolicy(), NOW).coverage_percent == 100


@pytest.mark.parametrize("mode", ["walking", "driving", "motorcycle"])
def test_live_api_never_reads_supabase_and_geometry_hits_still_recheck_forecasts(monkeypatch, mode):
    elapsed = [0]
    calls = []
    route_calls = []

    class Clock:
        @staticmethod
        def now(tz):
            return NOW + timedelta(seconds=elapsed[0])

    def forbidden(*args):
        raise AssertionError("Live pollution and routing must not use the snapshot database")

    def routes(*args):
        route_calls.append(args)
        return [walking()]

    def respond(req):
        calls.append(req)
        return (
            httpx.Response(200, json=payload(interval=5))
            if len(calls) == 1
            else httpx.Response(503)
        )

    monkeypatch.setattr("app.api.routes.datetime", Clock)
    monkeypatch.setattr("app.api.routes.load_snapshot", forbidden)
    monkeypatch.setattr("app.api.routes.read_routes", forbidden)
    monkeypatch.setattr("app.api.routes.store_routes", forbidden)
    monkeypatch.setattr("app.api.routes.walking_candidates", routes)
    monkeypatch.setattr("app.api.routes.vehicle_candidates", routes)
    monkeypatch.setattr(
        "app.api.routes.fetch_live_air_quality",
        lambda routes, policy, cache, reference: fetch(routes, respond, cache, reference, policy),
    )
    app = create_app(Settings(mapbox_token="private", _env_file=None))
    app.state.live_air_quality_cache = RuntimeCache(clock=lambda: elapsed[0])
    app.state.route_cache = RuntimeCache(clock=lambda: elapsed[0])
    client = TestClient(app)
    journey = request(mode="live").model_copy(update={"mode": mode}).model_dump()
    first = client.post("/api/routes/compare", json=journey)
    assert first.status_code == 200
    assert first.json()["candidates"][0]["estimated_exposure"] == pytest.approx(1000)
    assert first.json()["data_quality"]["source_type"] == "model_forecast"
    assert first.json()["data_quality"]["station_count"] == 0
    elapsed[0] = 6
    second = client.post("/api/routes/compare", json=journey)
    assert second.headers["X-AeroRoute-Cache"] == "hit"
    assert second.json()["status"] == "limited_data"
    assert second.json()["candidates"][0]["estimated_exposure"] is None
    assert len(route_calls) == 1 and len(calls) == 2


def test_live_forecasts_cannot_silently_score_recorded_replay():
    sample = AirQualitySample(
        50, NOW, NOW + timedelta(hours=1), NOW, Coordinate(lat=28.6, lng=77.2)
    )
    data = LiveAirQuality({region_key(Coordinate(lat=28.6, lng=77.2)): sample})
    result = compare_routes([walking()], request(), None, BaselinePolicy(), now=NOW, live_data=data)
    assert result.candidates[0].estimated_exposure is None
    assert result.data_quality.data_mode == "unavailable"
