import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def client():
    return TestClient(create_app(Settings(environment="test", _env_file=None)))


def journey():
    return {
        "origin": {"lat": 28.6139, "lng": 77.2090},
        "destination": {"lat": 28.62, "lng": 77.22},
        "max_detour_minutes": 5,
        "mode": "walking",
    }


def test_health_does_not_require_provider_credentials(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["environment"] == "test"


def test_pilot_is_unselected_until_data_audit(client):
    response = client.get("/api/pilot")
    assert response.json()["boundary"] is None
    assert response.json()["data_mode"] == "unavailable"


def test_comparison_never_fakes_success(client):
    response = client.post("/api/routes/compare", json=journey())
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "routing_unconfigured"


@pytest.mark.parametrize("value", [-1, True, "5"])
def test_invalid_detour_is_rejected(client, value):
    payload = journey()
    payload["max_detour_minutes"] = value
    assert client.post("/api/routes/compare", json=payload).status_code == 422


@pytest.mark.parametrize("point", [{"lat": 91, "lng": 77}, {"lat": 28, "lng": -181}])
def test_out_of_range_coordinates_are_rejected(client, point):
    payload = journey()
    payload["origin"] = point
    assert client.post("/api/routes/compare", json=payload).status_code == 422


def test_local_frontend_cors_and_foreign_origin(client):
    headers = {"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"}
    response = client.options("/api/routes/compare", headers=headers)
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    headers["Origin"] = "https://unconfigured.example"
    assert (
        "access-control-allow-origin"
        not in client.options("/api/routes/compare", headers=headers).headers
    )


def test_empty_optional_credentials_are_accepted():
    settings = Settings(openaq_api_key="", database_url="", _env_file=None)
    assert settings.openaq_api_key is None
    assert settings.database_url is None


def test_unknown_data_mode_is_rejected(client):
    payload = {**journey(), "data_mode": "automatic"}
    assert client.post("/api/routes/compare", json=payload).status_code == 422
