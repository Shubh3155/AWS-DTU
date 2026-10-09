from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from psycopg_pool import PoolTimeout, TooManyRequests

from app.core.config import Settings
from app.core.database import database_connection
from app.main import create_app
from app.services.snapshots import load_snapshot


def test_application_opens_pool_once_and_closes_on_shutdown(monkeypatch):
    events = []
    pool = SimpleNamespace(
        open=lambda: events.append("open"),
        wait=lambda timeout: events.append(("wait", timeout)),
        close=lambda: events.append("close"),
    )
    monkeypatch.setattr("app.main.create_pool", lambda settings: pool)
    application = create_app(Settings(_env_file=None))
    with TestClient(application) as client:
        assert application.state.database_pool is pool
        assert client.get("/health").status_code == 200
        assert events == ["open", ("wait", 10)]
    assert events == ["open", ("wait", 10), "close"]
    assert application.state.database_pool is None


def test_pooled_read_then_write_resets_transaction_mode_and_returns_failed_lease():
    connection = SimpleNamespace(read_only=False)
    returned = []

    class Pool:
        @contextmanager
        def connection(self, timeout):
            assert timeout == 3
            try:
                yield connection
            finally:
                returned.append(connection.read_only)

    settings = Settings(database_url="private-url", _env_file=None)
    pool = Pool()
    with database_connection(settings, pool, read_only=True) as leased:
        assert leased is connection
        assert leased.read_only
    with pytest.raises(ValueError):
        with database_connection(settings, pool) as leased:
            assert not leased.read_only
            raise ValueError("query failed")
    assert returned == [True, False]


@pytest.mark.parametrize("error", [PoolTimeout, TooManyRequests])
def test_pool_exhaustion_withholds_scores_without_leaking_connection_details(error):
    class Pool:
        @contextmanager
        def connection(self, timeout):
            raise error("private-url and password")
            yield

    snapshot, warnings = load_snapshot(
        Settings(database_url="private-url", _env_file=None), "live", None, Pool()
    )
    assert snapshot is None
    assert warnings == ["Pollution snapshot lookup failed; walking routes remain available."]


def test_unconfigured_application_starts_without_a_database():
    application = create_app(Settings(_env_file=None))
    with TestClient(application) as client:
        assert application.state.database_pool is None
        assert client.get("/health").status_code == 200


def test_initial_pool_timeout_keeps_service_available_and_closes_pool(monkeypatch):
    closed = []

    def wait(timeout):
        assert timeout == 10
        raise PoolTimeout("private connection details")

    pool = SimpleNamespace(open=lambda: None, wait=wait, close=lambda: closed.append(True))
    monkeypatch.setattr("app.main.create_pool", lambda settings: pool)
    with TestClient(create_app(Settings(_env_file=None))) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert "private" not in response.text
    assert closed == [True]
