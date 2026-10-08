# Versioned database migrations

`001_initial.sql` creates backend-only `aeroroute` storage for stations, normalized PM2.5
observations, live/replay snapshot manifests and route comparison cache entries. PostGIS
must already exist in the `gis` schema. Station coordinates generate a spatial point with
a GiST index; observations deduplicate by snapshot/provider/sensor/time. Cache identity
includes coordinates, mode, time bucket, detour allowance and snapshot/data/model version.
A cache entry's data version must match its referenced snapshot.

From a repository checkout, in `backend/` with the dependencies installed:

```bash
python -m scripts.migrate_database          # read-only status and checksum validation
python -m scripts.migrate_database --apply  # apply pending SQL atomically
python -m scripts.migrate_database          # verify no migrations remain
```

Use the ignored backend environment configured by `scripts.configure_database`. The runner
verifies TLS, serializes concurrent runs with a transaction advisory lock, and records each
filename/SHA-256 checksum in `aeroroute.schema_migrations`. A failed migration rolls back the
whole batch. Applied files must never be edited; add the next sequential SQL migration.
The runner rejects changed/missing files and gaps in migration history. There is no automatic
destructive rollback command. It does not run on API startup. Run administrative migrations
from a complete repository checkout, not from the minimal API image.

All tables enable RLS without browser policies; schema/table privileges are revoked from
`PUBLIC`, `anon` and `authenticated`. Keep `aeroroute` out of Supabase's exposed API schemas.
This step creates no new users or credentials. The local bootstrap uses the database owner;
a restricted backend role is still required before production deployment.

Storage alone does not implement ingestion, route-cache reads or a freshness policy. Cache
consumers must recheck observation age/coverage at read time, even before cache expiry.
Original concentration units are retained; only normalized `µg/m³` values may be stored as
PM2.5. Missing, negative and non-finite readings must not be substituted with zero.

## Verification

```bash
pytest -q
AEROROUTE_RUN_DB_TESTS=1 pytest tests/test_database_integration.py -q
```

The opt-in test uses configured Supabase access and a forced-rollback transaction. It checks
migration repeatability, spatial lookup, observation deduplication, invalid concentrations,
wrong units, detour-specific cache identity, version consistency and browser-role isolation.
All synthetic fixtures and newly created objects roll back; none are monitoring evidence.
Do not run concurrently with an administrative migration.

References: [Psycopg transactions](https://www.psycopg.org/psycopg3/docs/basic/transactions.html),
[Supabase PostGIS](https://supabase.com/docs/guides/database/extensions/postgis).
