from datetime import timedelta

from fastapi.testclient import TestClient
from test_comparison import NOW, request, snapshot, stations, walking

from app.core.config import Settings
from app.core.runtime_cache import RuntimeCache
from app.main import create_app


def test_cache_expiry_capacity_and_caller_mutations():
    time = [0]
    cache = RuntimeCache(capacity=2, clock=lambda: time[0])
    value = {"items": [1]}
    cache.put("a", value, ttl=10)
    value["items"].append(2)
    cached = cache.get("a")
    cached["items"].append(3)
    assert cache.get("a") == {"items": [1]}
    cache.put("b", 2, ttl=10)
    cache.put("c", 3, ttl=10)
    assert cache.get("a") is None
    time[0] = 10
    assert cache.get("b") is None
    assert cache.get("c") is None
    cache.put("failed", None, ttl=10)
    assert not cache.values


def test_memory_hits_recheck_freshness_and_expiry_does_not_mask_database_failure(monkeypatch):
    elapsed = [0]

    class Clock:
        @staticmethod
        def now(tz):
            return NOW + timedelta(seconds=elapsed[0])

    monkeypatch.setattr("app.api.routes.datetime", Clock)
    data = snapshot(stations(observed=NOW - timedelta(hours=2) + timedelta(seconds=5)), "live")
    reads = []

    def load(*args):
        reads.append(args[1:3])
        if len(reads) == 1:
            return data, []
        return None, ["Pollution snapshot lookup failed; walking routes remain available."]

    monkeypatch.setattr("app.api.routes.load_snapshot", load)
    monkeypatch.setattr("app.api.routes.read_routes", lambda *a: [walking()])
    monkeypatch.setattr("app.api.routes.walking_candidates", lambda *a: [walking()])
    app = create_app(Settings(mapbox_token="private", _env_file=None))
    app.state.snapshot_cache = RuntimeCache(clock=lambda: elapsed[0])
    app.state.route_cache = RuntimeCache(clock=lambda: elapsed[0])
    client = TestClient(app)
    payload = request(mode="live").model_dump()
    first = client.post("/api/routes/compare", json=payload)
    assert first.json()["candidates"][0]["estimated_exposure"] is not None
    elapsed[0] = 6
    second = client.post("/api/routes/compare", json=payload)
    assert second.headers["X-AeroRoute-Cache"] == "hit"
    assert second.json()["candidates"][0]["estimated_exposure"] is None
    assert len(reads) == 1
    elapsed[0] = 11
    third = client.post("/api/routes/compare", json=payload)
    assert third.headers["X-AeroRoute-Cache"] == "bypass"
    assert third.json()["data_quality"]["data_mode"] == "unavailable"
    assert third.json()["candidates"][0]["estimated_exposure"] is None
    assert len(reads) == 2


def test_snapshot_cache_is_scoped_to_requested_mode_and_identity(monkeypatch):
    calls = []

    def load(settings, mode, identity, pool):
        calls.append((mode, identity))
        return snapshot(stations(), mode), []

    monkeypatch.setattr("app.api.routes.load_snapshot", load)
    monkeypatch.setattr("app.api.routes.read_routes", lambda *a: [walking()])
    client = TestClient(create_app(Settings(mapbox_token="private", _env_file=None)))
    for mode, identity in [("replay", None), ("live", None), ("replay", "other")]:
        payload = request(mode=mode).model_dump()
        payload["snapshot_id"] = identity
        assert client.post("/api/routes/compare", json=payload).status_code == 200
    assert calls == [("replay", None), ("live", None), ("replay", "other")]
