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
    assert "/mapbox/driving/" in calls[0].url.path
    assert routes[0].duration == routes[0].steps[0].duration == 180
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
    assert result["routing_profile"] == "driving"
    assert result["candidates"][0]["duration_seconds"] == 180
    assert result["candidates"][0]["estimated_exposure"] is None
    assert any("live traffic" in warning for warning in result["warnings"])
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
