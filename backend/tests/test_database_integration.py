"""Opt-in live schema tests. Every migration and fixture write is rolled back."""

import os
from uuid import uuid4

import psycopg
import pytest

from app.core.config import get_settings
from scripts.migrate_database import CA, migrate

pytestmark = pytest.mark.skipif(
    os.environ.get("AEROROUTE_RUN_DB_TESTS") != "1", reason="Opt-in database integration test"
)


def test_schema_constraints_spatial_lookup_and_repeat_migration():
    url = get_settings().database_url
    assert url is not None, "Configure the ignored backend environment first."
    try:
        connection = psycopg.connect(
            url.get_secret_value(),
            sslmode="verify-full",
            sslrootcert=str(CA),
            connect_timeout=10,
            autocommit=True,
        )
    except psycopg.Error:
        pytest.fail("Database connection failed; credentials are omitted.", pytrace=False)
    with connection, connection.transaction(force_rollback=True):
        migrate(connection, apply=True)
        assert migrate(connection, apply=True) == []
        provider = "synthetic-test-" + uuid4().hex
        snapshot = "synthetic-test-" + uuid4().hex
        connection.execute(
            "INSERT INTO aeroroute.stations (provider_id, station_id, name, latitude, longitude) "
            "VALUES (%s, 1, 'Synthetic rollback fixture', 28.6, 77.2)",
            (provider,),
        )
        count = connection.execute(
            "SELECT count(*) FROM aeroroute.stations WHERE provider_id=%s "
            "AND gis.ST_DWithin(location, "
            "gis.ST_SetSRID(gis.ST_MakePoint(77.2, 28.6),4326)::gis.geography, 10)",
            (provider,),
        ).fetchone()[0]
        assert count == 1
        connection.execute(
            "INSERT INTO aeroroute.snapshots "
            "(snapshot_id,data_version,data_mode,observed_from,observed_to,"
            "fetched_at,source_manifest) "
            "VALUES (%s,'synthetic-test','replay',now(),now(),now(),'{}')",
            (snapshot,),
        )
        observation_sql = (
            "INSERT INTO aeroroute.observations "
            "(snapshot_id,provider_id,station_id,sensor_id,observed_at,fetched_at,"
            "pm25_micrograms_per_m3,source_unit) VALUES (%s,%s,1,1,now(),now(),%s,'µg/m³')"
        )
        for invalid in (-1.0, float("nan"), float("inf")):
            with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
                connection.execute(observation_sql, (snapshot, provider, invalid))
        connection.execute(observation_sql, (snapshot, provider, 42.0))
        with pytest.raises(psycopg.errors.UniqueViolation), connection.transaction():
            connection.execute(observation_sql, (snapshot, provider, 42.0))
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            connection.execute(
                "UPDATE aeroroute.observations SET unit='ppm' WHERE snapshot_id=%s", (snapshot,)
            )
        cache_sql = (
            "INSERT INTO aeroroute.route_comparison_cache "
            "(cache_key,origin_latitude,origin_longitude,destination_latitude,destination_longitude,"
            "mode,time_bucket,max_detour_minutes,snapshot_id,data_version,model_version,response,"
            "expires_at) VALUES (%s,28.6,77.2,28.61,77.21,'walking',now(),%s,%s,"
            "'synthetic-test','test-model','{}',now()+interval '5 minutes')"
        )
        connection.execute(cache_sql, (uuid4().hex, 5.0, snapshot))
        connection.execute(cache_sql, (uuid4().hex, 6.0, snapshot))
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            connection.execute(cache_sql, (uuid4().hex, -1.0, snapshot))
        with pytest.raises(psycopg.errors.ForeignKeyViolation), connection.transaction():
            connection.execute(
                "UPDATE aeroroute.route_comparison_cache SET data_version='wrong-version' "
                "WHERE snapshot_id=%s",
                (snapshot,),
            )
        rows = connection.execute(
            "SELECT relrowsecurity FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='aeroroute' AND c.relkind='r'"
        ).fetchall()
        assert rows and all(row[0] for row in rows)
        assert connection.execute(
            "SELECT has_schema_privilege('anon','aeroroute','USAGE'), "
            "has_schema_privilege('authenticated','aeroroute','USAGE')"
        ).fetchone() == (False, False)


def test_ingestion_idempotent_and_original_timestamps_preserved():
    from app.services.ingestion import ingest_snapshot, prepare_snapshot

    url = get_settings().database_url
    assert url is not None
    try:
        connection = psycopg.connect(
            url.get_secret_value(),
            sslmode="verify-full",
            sslrootcert=str(CA),
            connect_timeout=10,
            autocommit=True,
        )
    except psycopg.Error:
        pytest.fail("Database connection failed; credentials omitted.", pytrace=False)
    raw = {
        "source": "OpenAQ v3",
        "fetched_at": "2026-10-08T10:00:00Z",
        "limitations": ["Synthetic integration fixture; always rolled back"],
        "stations": [
            {
                "station_id": 999999999,
                "name": "Synthetic rollback fixture",
                "coordinates": {"latitude": 28.6, "longitude": 77.2},
                "measurements": [
                    {
                        "sensor_id": 999999999,
                        "value": 42.0,
                        "unit": "ug/m3",
                        "observed_at": "2016-10-08T10:00:00Z",
                    }
                ],
            }
        ],
    }
    prepared = prepare_snapshot(raw, "replay")
    with connection, connection.transaction(force_rollback=True):
        assert ingest_snapshot(connection, prepared)
        assert not ingest_snapshot(connection, prepared)
        row = connection.execute(
            "SELECT o.observed_at,o.source_unit,s.data_mode FROM aeroroute.observations o "
            "JOIN aeroroute.snapshots s USING (snapshot_id) WHERE snapshot_id=%s",
            (prepared["snapshot_id"],),
        ).fetchone()
        assert row[0].year == 2016
        assert row[1:] == ("ug/m3", "replay")
        assert (
            connection.execute(
                "SELECT count(*) FROM aeroroute.observations WHERE snapshot_id=%s",
                (prepared["snapshot_id"],),
            ).fetchone()[0]
            == 1
        )
