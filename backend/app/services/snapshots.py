"""Read one coherent stored snapshot without altering database state."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

import psycopg
from psycopg_pool import ConnectionPool

from app.core.config import Settings
from app.core.database import CA as CA
from app.core.database import database_connection
from app.model.contracts import StationObservation
from app.schemas.routes import Coordinate


@dataclass(frozen=True)
class PollutionSnapshot:
    snapshot_id: str
    data_version: str
    data_mode: Literal["live", "replay"]
    observed_to: datetime
    fetched_at: datetime
    observations: list[StationObservation]


def load_snapshot(
    settings: Settings,
    mode: Literal["live", "replay"],
    identity: str | None,
    pool: ConnectionPool | None = None,
) -> tuple[PollutionSnapshot | None, list[str]]:
    if settings.database_url is None:
        return None, ["Pollution snapshot access is not configured; exposure is unavailable."]
    try:
        with database_connection(settings, pool, read_only=True) as connection:
            connection.execute("SET LOCAL statement_timeout = 3000")
            snapshot = connection.execute(
                "SELECT snapshot_id,data_version,data_mode,observed_to,fetched_at "
                "FROM aeroroute.snapshots WHERE data_mode=%s "
                "AND (%s::text IS NULL OR snapshot_id=%s) "
                "ORDER BY fetched_at DESC,snapshot_id LIMIT 1",
                (mode, identity, identity),
            ).fetchone()
            if snapshot is None:
                return None, [f"No matching {mode} snapshot is available; exposure is unavailable."]
            rows = connection.execute(
                "SELECT provider_id,station_id,sensor_id,observed_at,fetched_at,"
                "pm25_micrograms_per_m3,metadata FROM aeroroute.observations "
                "WHERE snapshot_id=%s ORDER BY provider_id,station_id,sensor_id,observed_at "
                "LIMIT 10001",
                (snapshot["snapshot_id"],),
            ).fetchall()
        if len(rows) > 10000:
            return None, [
                "Snapshot exceeds the prototype's observation limit; scoring is withheld."
            ]
        observations = []
        rejected = 0
        for row in rows:
            try:
                point = Coordinate(
                    lat=row["metadata"]["latitude"], lng=row["metadata"]["longitude"]
                )
                observations.append(
                    StationObservation(
                        location=point,
                        **{key: value for key, value in row.items() if key != "metadata"},
                    )
                )
            except (ValueError, KeyError, TypeError):
                rejected += 1
        warnings = [f"Excluded {rejected} invalid stored observations."] if rejected else []
        return PollutionSnapshot(observations=observations, **snapshot), warnings
    except psycopg.Error:
        return None, ["Pollution snapshot lookup failed; walking routes remain available."]
