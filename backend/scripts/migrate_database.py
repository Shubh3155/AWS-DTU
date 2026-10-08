"""Versioned, transactional database migrations; status is read-only by default."""

import argparse
import hashlib
from pathlib import Path

import psycopg

from app.core.config import get_settings

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"
CA = Path(__file__).resolve().parents[1] / "certs" / "supabase-ca.crt"


def migration_files(directory: Path = MIGRATIONS) -> list[tuple[str, str, str]]:
    files = []
    for path in sorted(directory.glob("[0-9][0-9][0-9]_*.sql")):
        source = path.read_bytes()
        files.append((path.name, hashlib.sha256(source).hexdigest(), source.decode("utf-8")))
    versions = [name.split("_", 1)[0] for name, _, _ in files]
    if len(versions) != len(set(versions)):
        raise ValueError("Duplicate migration version.")
    return files


def validate_history(files: list[tuple[str, str, str]], applied: dict[str, str]) -> None:
    known = {name: checksum for name, checksum, _ in files}
    if any(known.get(name) != checksum for name, checksum in applied.items()):
        raise ValueError("Applied migration is missing or changed; restore original SQL.")
    names = [name for name, _, _ in files]
    if list(name for name in names if name in applied) != names[: len(applied)]:
        raise ValueError(
            "Migration history has a gap; do not insert migrations before applied ones."
        )


def migrate(connection: psycopg.Connection, *, apply: bool) -> list[str]:
    files = migration_files()
    if not files:
        raise ValueError("No migration files found; run from a complete repository checkout.")
    connection.execute("SET LOCAL statement_timeout = 30000")
    connection.execute("SET LOCAL lock_timeout = 5000")
    extension = connection.execute(
        "SELECT n.nspname FROM pg_extension e JOIN pg_namespace n ON n.oid=e.extnamespace "
        "WHERE e.extname='postgis'"
    ).fetchone()
    if extension != ("gis",):
        raise ValueError("PostGIS must be enabled in the gis schema before migration.")
    if apply:
        connection.execute("SELECT pg_advisory_xact_lock(7813155)")
        connection.execute("CREATE SCHEMA IF NOT EXISTS aeroroute")
        connection.execute("REVOKE ALL ON SCHEMA aeroroute FROM PUBLIC, anon, authenticated")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS aeroroute.schema_migrations "
            "(name text PRIMARY KEY, checksum text NOT NULL, "
            "applied_at timestamptz NOT NULL DEFAULT now())"
        )
        connection.execute("ALTER TABLE aeroroute.schema_migrations ENABLE ROW LEVEL SECURITY")
        connection.execute(
            "REVOKE ALL ON aeroroute.schema_migrations FROM PUBLIC, anon, authenticated"
        )
    exists = connection.execute("SELECT to_regclass('aeroroute.schema_migrations')").fetchone()[0]
    applied = (
        dict(connection.execute("SELECT name, checksum FROM aeroroute.schema_migrations"))
        if exists
        else {}
    )
    validate_history(files, applied)
    pending = [name for name, _, _ in files if name not in applied]
    if apply:
        for name, checksum, source in files:
            if name not in applied:
                connection.execute(source)
                connection.execute(
                    "INSERT INTO aeroroute.schema_migrations (name, checksum) VALUES (%s, %s)",
                    (name, checksum),
                )
    return pending


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Apply pending migrations atomically")
    args = parser.parse_args()
    url = get_settings().database_url
    if url is None:
        print("Database URL is unconfigured; run scripts.configure_database first.")
        return 2
    try:
        with psycopg.connect(
            url.get_secret_value(), connect_timeout=10, sslmode="verify-full", sslrootcert=str(CA)
        ) as connection:
            connection.read_only = not args.apply
            pending = migrate(connection, apply=args.apply)
        print(
            "Applied: " + ", ".join(pending)
            if args.apply and pending
            else "Database is up to date."
            if not pending
            else "Pending: " + ", ".join(pending)
        )
        return 0
    except ValueError as error:
        print(str(error))
        return 1
    except psycopg.Error as error:
        print(
            f"Migration failed (SQLSTATE {error.sqlstate or 'connection'}); no changes committed."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
