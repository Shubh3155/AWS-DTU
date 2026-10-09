import copy

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.schemas.routes import Coordinate
from app.services.walking import RoutingError, walking_routes


def route(duration):
    geometry = {"type": "LineString", "coordinates": [[77.2, 28.6], [77.21, 28.61]]}
    return {
        "geometry": geometry,
        "duration": duration,
        "distance": 1000.0,
        "legs": [{"steps": [{"geometry": geometry, "duration": duration, "distance": 1000.0}]}],
    }


def test_api_fastest_not_provider_order_and_exact_detour(monkeypatch):
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, json={"code": "Ok", "routes": [route(900.0), route(600.0), route(900.01)]}
        )
    )
    original = httpx.Client
    monkeypatch.setattr(
        "app.api.routes.httpx.Client", lambda **kwargs: original(transport=transport, **kwargs)
    )
    client = TestClient(create_app(Settings(mapbox_token="private", _env_file=None)))
    payload = {
        "origin": {"lat": 28.6, "lng": 77.2},
        "destination": {"lat": 28.61, "lng": 77.21},
        "max_detour_minutes": 5,
    }
    response = client.post("/api/routes/compare", json=payload)
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "limited_data"
    assert result["fastest_id"] == result["candidates"][1]["id"]
    assert [r["within_budget"] for r in result["candidates"]] == [True, True, False]
    assert all(r["estimated_exposure"] is None for r in result["candidates"])
    assert result["lowest_exposure_eligible_id"] is None


@pytest.mark.parametrize(
    "status,code", [(429, "routing_rate_limited"), (401, "routing_provider_error")]
)
def test_errors_do_not_disclose_token(status, code):
    with httpx.Client(
        base_url="https://api.mapbox.com",
        transport=httpx.MockTransport(lambda request: httpx.Response(status)),
    ) as client:
        with pytest.raises(RoutingError) as error:
            walking_routes(
                client,
                "secret-token",
                Coordinate(lat=28.6, lng=77.2),
                Coordinate(lat=28.61, lng=77.21),
            )
    assert error.value.code == code
    assert "secret-token" not in str(error.value)


def test_no_route_and_bad_geometry_are_not_fabricated():
    for payload in ({"code": "NoRoute"}, {"code": "NoSegment"}):
        with httpx.Client(
            base_url="https://api.mapbox.com",
            transport=httpx.MockTransport(
                lambda request, payload=payload: httpx.Response(200, json=payload)
            ),
        ) as client:
            assert (
                walking_routes(
                    client,
                    "secret",
                    Coordinate(lat=28.6, lng=77.2),
                    Coordinate(lat=28.61, lng=77.21),
                )
                == []
            )
    raw = copy.deepcopy(route(600.0))
    raw["geometry"]["coordinates"][0][0] = 181
    with (
        httpx.Client(
            base_url="https://api.mapbox.com",
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json={"code": "Ok", "routes": [raw]})
            ),
        ) as client,
        pytest.raises(RoutingError),
    ):
        walking_routes(
            client, "secret", Coordinate(lat=28.6, lng=77.2), Coordinate(lat=28.61, lng=77.21)
        )


def test_single_route_probes_real_waypoints_and_deduplicates_geometry():
    from app.services.walking import walking_candidates

    calls = []

    def provider(request):
        calls.append(request)
        raw = route(600.0)
        if len(calls) == 2:
            raw["geometry"]["coordinates"].insert(1, [77.205, 28.608])
            raw["legs"][0]["steps"][0]["geometry"] = raw["geometry"]
            raw["duration"] = 720.0
            raw["legs"][0]["steps"][0]["duration"] = 720.0
        return httpx.Response(200, json={"code": "Ok", "routes": [raw]})

    with httpx.Client(
        base_url="https://api.mapbox.com", transport=httpx.MockTransport(provider)
    ) as client:
        results = walking_candidates(
            client, "secret", Coordinate(lat=28.6, lng=77.2), Coordinate(lat=28.61, lng=77.21)
        )
    assert len(calls) == 3
    assert len(results) == 2
    assert results[0].via is None
    assert results[1].via is not None
    assert calls[1].url.path.count(";") == 2
    assert calls[1].url.params["radiuses"] == "50;100;50"
    assert sum(step.duration for step in results[1].steps) == 720


def test_failed_optional_probes_keep_original_route():
    from app.services.walking import walking_candidates

    count = 0

    def provider(request):
        nonlocal count
        count += 1
        return (
            httpx.Response(200, json={"code": "Ok", "routes": [route(600.0)]})
            if count == 1
            else httpx.Response(429)
        )

    with httpx.Client(
        base_url="https://api.mapbox.com", transport=httpx.MockTransport(provider)
    ) as client:
        result = walking_candidates(
            client, "secret", Coordinate(lat=28.6, lng=77.2), Coordinate(lat=28.61, lng=77.21)
        )
    assert len(result) == 1
    assert count == 2


def test_existing_provider_alternatives_do_not_trigger_probes():
    from app.services.walking import walking_candidates

    calls = []

    def provider(request):
        calls.append(request)
        return httpx.Response(200, json={"code": "Ok", "routes": [route(600.0), route(650.0)]})

    with httpx.Client(
        base_url="https://api.mapbox.com", transport=httpx.MockTransport(provider)
    ) as client:
        result = walking_candidates(
            client, "secret", Coordinate(lat=28.6, lng=77.2), Coordinate(lat=28.61, lng=77.21)
        )
    assert len(result) == 2
    assert len(calls) == 1
