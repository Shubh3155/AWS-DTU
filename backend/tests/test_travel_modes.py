import httpx
import pytest
from fastapi.testclient import TestClient
from test_comparison import NOW, request, snapshot, stations, walking
from test_walking import route

from app.core.config import Settings
from app.main import create_app
from app.model.baseline import BaselinePolicy
from app.schemas.routes import Coordinate
from app.services.cache import cache_identity
from app.services.comparison import compare_routes
from app.services.walking import vehicle_candidates


@pytest.mark.parametrize("mode", ["driving", "motorcycle"])
def test_vehicle_provider_uses_driving_steps_without_walking_probes(mode):
    calls = []

    def provider(request):
        calls.append(request)
        return httpx.Response(200, json={"code": "Ok", "routes": [route(180.0)]})

    with httpx.Client(
        base_url="https://api.mapbox.com", transport=httpx.MockTransport(provider)
    ) as client:
        routes = vehicle_candidates(
            client,
            "private",
            Coordinate(lat=28.6, lng=77.2),
            Coordinate(lat=28.61, lng=77.21),
            mode,
        )
    assert len(calls) == 1
    assert "/mapbox/driving-traffic/" in calls[0].url.path
    assert calls[0].url.params["annotations"] == "congestion,distance,duration"
    assert routes[0].duration == routes[0].steps[0].duration == 180
    assert routes[0].traffic.coverage_percent == 0
    assert routes[0].via is None


@pytest.mark.parametrize("mode", ["driving", "motorcycle"])
def test_api_dispatches_vehicle_mode_and_reports_ambient_limits(monkeypatch, mode):
    original = httpx.Client
    monkeypatch.setattr(
        "app.api.routes.httpx.Client",
        lambda **kwargs: original(
            transport=httpx.MockTransport(
                lambda r: httpx.Response(200, json={"code": "Ok", "routes": [route(180.0)]})
            ),
            **kwargs,
        ),
    )
    client = TestClient(create_app(Settings(mapbox_token="private", _env_file=None)))
    result = client.post(
        "/api/routes/compare",
        json={
            "origin": {"lat": 28.6, "lng": 77.2},
            "destination": {"lat": 28.61, "lng": 77.21},
            "max_detour_minutes": 5,
            "mode": mode,
        },
    ).json()
    assert result["mode"] == mode
    assert result["routing_profile"] == "driving-traffic"
    assert result["candidates"][0]["duration_seconds"] == 180
    assert result["candidates"][0]["estimated_exposure"] is None
    assert any("traffic" in warning for warning in result["warnings"])
    assert any(
        ("motorcycle access" if mode == "motorcycle" else "cabin air") in warning
        for warning in result["warnings"]
    )


def test_cache_separates_all_travel_modes():
    keys = {
        cache_identity(
            request().model_copy(update={"mode": mode}), snapshot(stations()), BaselinePolicy(), NOW
        )[0]
        for mode in ("walking", "driving", "motorcycle")
    }
    assert len(keys) == 3


def test_vehicle_exposure_uses_preserved_provider_time_not_speed_multiplier():
    data, policy = snapshot(stations()), BaselinePolicy()
    slower = compare_routes([walking(1200.0)], request(), data, policy, now=NOW)
    faster = compare_routes(
        [walking(600.0)], request().model_copy(update={"mode": "driving"}), data, policy, now=NOW
    )
    assert faster.candidates[0].estimated_exposure == pytest.approx(
        slower.candidates[0].estimated_exposure / 2
    )


def test_traffic_summary_weights_congestion_by_distance_and_preserves_unknowns():
    from app.services.walking import traffic_info

    raw = route(600.0)
    raw["duration_typical"] = 400.0
    raw["legs"][0]["annotation"] = {
        "distance": [100.0, 400.0, 500.0],
        "congestion": ["unknown", "heavy", "low"],
    }
    traffic = traffic_info(raw)
    assert traffic.coverage_percent == 90
    assert traffic.congested_percent == 40
    assert traffic.typical_duration_seconds == 400
    assert traffic.fetched_at.tzinfo is not None


@pytest.mark.parametrize(
    "annotation",
    [None, {"distance": [1000], "congestion": ["unknown"]}, {"distance": [1000], "congestion": []}],
)
def test_absent_unknown_or_mismatched_congestion_is_unavailable(annotation):
    from app.services.walking import traffic_info

    raw = route(600.0)
    if annotation is not None:
        raw["legs"][0]["annotation"] = annotation
    assert traffic_info(raw).coverage_percent == 0
    assert traffic_info(raw).congested_percent == 0


def test_traffic_cache_is_short_and_rotates_each_minute():
    from datetime import timedelta

    from app.services.cache import route_cache_ttl

    journey, data, policy = request(), snapshot(stations()), BaselinePolicy()
    vehicle = journey.model_copy(update={"mode": "driving"})
    settings = Settings(cache_ttl_seconds=600, _env_file=None)
    assert route_cache_ttl(settings, vehicle) == 60
    assert route_cache_ttl(settings, journey) == 600
    assert (
        cache_identity(vehicle, data, policy, NOW)[0]
        != cache_identity(vehicle, data, policy, NOW + timedelta(seconds=60))[0]
    )


def test_vehicle_uses_traffic_duration_for_budget_instead_of_typical_duration():
    from app.schemas.routes import TrafficInfo

    traffic = TrafficInfo(
        fetched_at=NOW, typical_duration_seconds=100, coverage_percent=0, congested_percent=0
    )
    slow = walking(960.0).model_copy(update={"id": "slow", "traffic": traffic})
    fast = walking(600.0).model_copy(update={"id": "fast", "traffic": traffic})
    result = compare_routes(
        [slow, fast],
        request().model_copy(update={"mode": "driving"}),
        snapshot(stations()),
        BaselinePolicy(),
        now=NOW,
    )
    assert result.fastest_id == "fast"
    assert result.candidates[0].within_budget is False
    assert result.candidates[0].traffic.typical_duration_seconds == 100
    assert result.candidates[0].estimated_exposure > result.candidates[1].estimated_exposure
    assert any("Unknown traffic" in warning for warning in result.warnings)
