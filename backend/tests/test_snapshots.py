"""Recorded-data fixtures verify reads and API integration without provider access."""

from datetime import UTC, datetime

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.model.contracts import StationObservation
from app.schemas.routes import Coordinate, LineString
from app.services.snapshots import CA, PollutionSnapshot, load_snapshot
from app.services.walking import WalkingRoute, WalkingStep

TIME = datetime(2026, 10, 7, 12, tzinfo=UTC)
MANIFEST = {
    "snapshot_id": "synthetic-replay",
    "data_version": "synthetic-v1",
    "data_mode": "replay",
    "observed_to": TIME,
    "fetched_at": TIME,
}


def rows():
    return [
        {
            "provider_id": "synthetic",
            "station_id": index,
            "sensor_id": index,
            "observed_at": TIME,
            "fetched_at": TIME,
            "pm25_micrograms_per_m3": 80.0,
            "metadata": {"latitude": 28.6 + delta, "longitude": 77.2},
        }
        for index, delta in enumerate([0, 0.001, -0.001], start=1)
    ]


class ReadConnection:
    def __init__(self, manifest=MANIFEST, readings=None):
        self.manifest = manifest
        self.readings = rows() if readings is None else readings
        self.read_only = False
        self.queries = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, query, parameters=None):
        assert self.read_only
        self.queries.append((query, parameters))
        return self

    def fetchone(self):
        return self.manifest

    def fetchall(self):
        return self.readings


def test_snapshot_read_is_read_only_verified_tls_and_mode_scoped(monkeypatch):
    connection = ReadConnection()

    def connect(url, **options):
        assert url == "private-url"
        assert options["sslmode"] == "verify-full"
        assert options["sslrootcert"] == str(CA)
        assert CA.is_file()
        assert options["connect_timeout"] == 3
        return connection

    monkeypatch.setattr("app.services.snapshots.psycopg.connect", connect)
    result, warnings = load_snapshot(
        Settings(database_url="private-url", _env_file=None), "replay", "synthetic-replay"
    )
    assert not warnings
    assert result.snapshot_id == "synthetic-replay"
    assert len(result.observations) == 3
    assert result.observations[0].location == Coordinate(lat=28.6, lng=77.2)
    assert connection.queries[0] == ("SET LOCAL statement_timeout = 3000", None)
    assert connection.queries[1][1] == ("replay", "synthetic-replay", "synthetic-replay")
    assert "data_mode=%s" in connection.queries[1][0]
    assert connection.queries[2][1] == ("synthetic-replay",)
    assert "JOIN" not in connection.queries[2][0]  # Uses immutable observation coordinates.


def test_unknown_snapshot_does_not_fall_back_to_another_mode(monkeypatch):
    connection = ReadConnection(manifest=None)
    monkeypatch.setattr("app.services.snapshots.psycopg.connect", lambda *a, **k: connection)
    result, warnings = load_snapshot(
        Settings(database_url="private-url", _env_file=None), "live", "unknown"
    )
    assert result is None
    assert "No matching live" in warnings[0]
    assert connection.queries[1][1] == ("live", "unknown", "unknown")
    assert len(connection.queries) == 2


def test_invalid_stored_values_are_excluded_with_a_warning(monkeypatch):
    readings = rows()
    readings[1]["metadata"] = {}
    readings[2]["pm25_micrograms_per_m3"] = -1.0
    monkeypatch.setattr(
        "app.services.snapshots.psycopg.connect", lambda *a, **k: ReadConnection(readings=readings)
    )
    result, warnings = load_snapshot(
        Settings(database_url="private-url", _env_file=None), "replay", None
    )
    assert len(result.observations) == 1
    assert warnings == ["Excluded 2 invalid stored observations."]


def test_database_failure_keeps_private_connection_details_out_of_response(monkeypatch):
    def fail(*args, **kwargs):
        raise psycopg.OperationalError("private-url with private-password")

    monkeypatch.setattr("app.services.snapshots.psycopg.connect", fail)
    result, warnings = load_snapshot(
        Settings(database_url="private-url", _env_file=None), "live", None
    )
    assert result is None
    assert "private" not in " ".join(warnings)
    assert "walking routes remain available" in warnings[0]


def test_oversized_snapshot_is_not_silently_truncated_and_scored(monkeypatch):
    monkeypatch.setattr(
        "app.services.snapshots.psycopg.connect",
        lambda *a, **k: ReadConnection(readings=[rows()[0]] * 10001),
    )
    result, warnings = load_snapshot(
        Settings(database_url="private-url", _env_file=None), "replay", None
    )
    assert result is None
    assert "observation limit" in warnings[0]


@pytest.mark.parametrize("mode", ["live", "replay"])
def test_api_consumes_explicit_snapshot_mode_and_serializes_scoring(monkeypatch, mode):
    geometry = LineString(coordinates=[(77.2, 28.6), (77.2001, 28.6001)])
    route = WalkingRoute(
        id="synthetic-route",
        geometry=geometry,
        duration=1200.0,
        distance=15.0,
        steps=[WalkingStep(geometry=geometry, duration=1200.0, distance=15.0)],
    )
    monkeypatch.setattr("app.api.routes.walking_candidates", lambda *args: [route])
    calls = []

    def snapshot(settings, requested_mode, identity):
        calls.append((requested_mode, identity))
        readings = [
            StationObservation(
                location=Coordinate(lat=r["metadata"]["latitude"], lng=77.2),
                **{k: v for k, v in r.items() if k != "metadata"},
            )
            for r in rows()
        ]
        return PollutionSnapshot(**{**MANIFEST, "data_mode": mode}, observations=readings), []

    monkeypatch.setattr("app.api.routes.load_snapshot", snapshot)
    client = TestClient(create_app(Settings(mapbox_token="private-token", _env_file=None)))
    payload = {
        "origin": {"lat": 28.6, "lng": 77.2},
        "destination": {"lat": 28.6001, "lng": 77.2001},
        "max_detour_minutes": 5,
        "snapshot_id": "synthetic-replay",
    }
    if mode == "replay":
        payload["data_mode"] = "replay"
    response = client.post("/api/routes/compare", json=payload)
    assert response.status_code == 200
    assert calls == [(mode, "synthetic-replay")]
    result = response.json()
    assert result["data_quality"]["data_mode"] == mode
    assert result["data_quality"]["snapshot_id"] == "synthetic-replay"
    assert result["data_quality"]["model_version"].startswith("idw-v1-")
    assert result["estimated_reduction_percent"] is None
    if mode == "replay":
        assert result["status"] == "single_candidate"
        assert result["candidates"][0]["estimated_exposure"] == pytest.approx(1600)
        assert result["data_quality"]["station_count"] == 3
        assert result["data_quality"]["reference_time"] == "2026-10-07T12:00:00Z"
    else:
        # Old data, even tagged live, cannot score the current journey.
        assert result["status"] == "limited_data"
        assert result["candidates"][0]["estimated_exposure"] is None
        assert result["data_quality"]["station_count"] == 0
