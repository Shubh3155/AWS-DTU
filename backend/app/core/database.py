"""Small process-local pool: verified TLS, bounded leases and explicit transaction modes."""

from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.core.config import Settings

CA = Path(__file__).resolve().parents[2] / "certs" / "supabase-ca.crt"


def create_pool(settings: Settings) -> ConnectionPool | None:
    if settings.database_url is None:
        return None
    return ConnectionPool(
        conninfo=settings.database_url.get_secret_value(),
        kwargs={
            "connect_timeout": 10,
            "sslmode": "verify-full",
            "sslrootcert": str(CA),
            "row_factory": dict_row,
            "prepare_threshold": None,
        },
        min_size=1,
        max_size=4,
        max_waiting=8,
        timeout=3,
        open=False,
        check=ConnectionPool.check_connection,
        max_idle=60,
        max_lifetime=600,
        reconnect_timeout=30,
        name="aeroroute",
    )


@contextmanager
def database_connection(settings: Settings, pool: ConnectionPool | None = None, *, read_only=False):
    if settings.database_url is None:
        raise psycopg.OperationalError("Database access is unconfigured")
    lease = (
        pool.connection(timeout=3)
        if pool is not None
        else psycopg.connect(
            settings.database_url.get_secret_value(),
            connect_timeout=3,
            sslmode="verify-full",
            sslrootcert=str(CA),
            row_factory=dict_row,
        )
    )
    with lease as connection:
        # Every checkout specifies its mode; a prior read must not poison a later cache write.
        connection.read_only = read_only
        yield connection
