from dataclasses import replace
from datetime import timedelta

import psycopg
from fastapi.testclient import TestClient
from test_comparison import NOW, request, snapshot, stations, walking

from app.core.config import Settings
from app.main import create_app
from app.model.baseline import BaselinePolicy
from app.services.cache import CONTRACT, cache_identity, read_routes, store_routes
from app.services.comparison import compare_routes


def test_cache_key_includes_allowance_points_modes_versions_and_time():
    journey, data, policy = request(), snapshot(stations()), BaselinePolicy()
    key, bucket = cache_identity(journey, data, policy, NOW)
    cases = [
        (request(detour=6), data, policy, NOW),
        (request(mode="live"), data, policy, NOW),
        (journey.model_copy(update={"destination": journey.origin}), data, policy, NOW),
        (journey, replace(data, snapshot_id="new-snapshot"), policy, NOW),
        (journey, replace(data, data_version="new-data"), policy, NOW),
        (journey, data, BaselinePolicy(max_age_hours=3), NOW),
        (journey, data, policy, NOW + timedelta(minutes=5)),
    ]
    assert all(cache_identity(*case)[0] != key for case in cases)
    explicit = journey.model_copy(update={"snapshot_id": data.snapshot_id})
    assert cache_identity(explicit, data, policy, NOW)[0] == key
    assert bucket.second == 0 and bucket.minute % 5 == 0


class Connection:
    read_only = False

    def __init__(self, payload=None):
        self.payload = payload
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, query, params=None):
        self.calls.append((query, params))
        return self

    def fetchone(self):
        return {"response": self.payload} if self.payload else None


def test_cache_read_preserves_steps_and_checks_expiry_in_read_only_query(monkeypatch):
    connection = Connection({"contract": CONTRACT, "walking_routes": [walking().model_dump()]})
    monkeypatch.setattr("app.services.cache.psycopg.connect", lambda *a, **k: connection)
    result = read_routes(
        Settings(database_url="private", _env_file=None),
        request(),
        snapshot(stations()),
        BaselinePolicy(),
        NOW,
    )
    assert result == [walking()]
    assert connection.read_only
    assert "expires_at>%s" in connection.calls[-1][0]
    assert connection.calls[-1][1][-1] == NOW


def test_invalid_or_failed_cache_is_a_miss(monkeypatch):
    settings = Settings(database_url="private", _env_file=None)
    for payload in [{"contract": "old"}, {"contract": CONTRACT, "walking_routes": [{}]}]:
        monkeypatch.setattr(
            "app.services.cache.psycopg.connect",
            lambda *a, payload=payload, **k: Connection(payload),
        )
        assert read_routes(settings, request(), snapshot(stations()), BaselinePolicy(), NOW) is None

    def fail(*args, **kwargs):
        raise psycopg.OperationalError("private-password")

    monkeypatch.setattr("app.services.cache.psycopg.connect", fail)
    assert read_routes(settings, request(), snapshot(stations()), BaselinePolicy(), NOW) is None


def test_cache_store_sets_ttl_and_contains_original_step_times(monkeypatch):
    connection = Connection()
    monkeypatch.setattr("app.services.cache.psycopg.connect", lambda *a, **k: connection)
    data = snapshot(stations())
    result = compare_routes([walking()], request(), data, BaselinePolicy())
    store_routes(
        Settings(database_url="private", cache_ttl_seconds=30, _env_file=None),
        request(),
        data,
        BaselinePolicy(),
        [walking()],
        result,
        NOW,
    )
    assert connection.calls[1][0].startswith("DELETE")
    params = connection.calls[-1][1]
    assert params[-1] == NOW + timedelta(seconds=30)
    assert params[-3].obj["walking_routes"][0]["steps"][0]["duration"] == 1200


def test_api_cache_hit_skips_provider_but_rechecks_current_freshness(monkeypatch):
    old = snapshot(stations(observed=NOW - timedelta(days=5)), "live")
    monkeypatch.setattr("app.api.routes.load_snapshot", lambda *a: (old, []))
    monkeypatch.setattr("app.api.routes.read_routes", lambda *a: [walking()])

    def provider(*args):
        raise AssertionError("A cache hit must skip the routing provider")

    monkeypatch.setattr("app.api.routes.walking_routes", provider)
    client = TestClient(create_app(Settings(mapbox_token="private", _env_file=None)))
    result = client.post("/api/routes/compare", json=request(mode="live").model_dump())
    assert result.status_code == 200
    assert result.headers["X-AeroRoute-Cache"] == "hit"
    assert result.json()["status"] == "limited_data"
    assert result.json()["candidates"][0]["estimated_exposure"] is None
