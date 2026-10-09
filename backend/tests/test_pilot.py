from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.pilot import contains
from app.main import create_app
from app.schemas.routes import LineString
from app.services.walking import WalkingRoute, WalkingStep


def test_boundary_includes_demo_and_exact_edges():
    assert contains(28.6315, 77.2167)
    assert contains(28.628, 77.241)
    assert contains(28.624, 77.215)
    assert contains(28.638, 77.243)
    assert not contains(28.638001, 77.243)


def test_paths_leaving_area_are_warned_even_when_endpoints_are_inside(monkeypatch):
    geometry = LineString(coordinates=[(77.2167, 28.6315), (77.22, 28.65), (77.241, 28.628)])
    route = WalkingRoute(
        id="synthetic",
        geometry=geometry,
        duration=600.0,
        distance=1000.0,
        steps=[WalkingStep(geometry=geometry, duration=600.0, distance=1000.0)],
    )
    monkeypatch.setattr("app.api.routes.walking_candidates", lambda *a: [route])
    client = TestClient(create_app(Settings(mapbox_token="private", _env_file=None)))
    response = client.post(
        "/api/routes/compare",
        json={
            "origin": {"lat": 28.6315, "lng": 77.2167},
            "destination": {"lat": 28.628, "lng": 77.241},
            "max_detour_minutes": 5,
        },
    )
    assert response.status_code == 200
    assert (
        "One or more evaluated paths leave the reviewed historical demo area."
        in response.json()["warnings"]
    )
    assert response.json()["candidates"][0]["estimated_exposure"] is None
