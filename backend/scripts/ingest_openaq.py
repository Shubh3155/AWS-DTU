"""Validate a saved OpenAQ audit; optionally ingest it into the backend database."""

import argparse
import json
from pathlib import Path

import psycopg

from app.core.config import get_settings
from app.services.ingestion import ingest_snapshot, prepare_snapshot
from scripts.migrate_database import CA


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--mode", choices=("live", "replay"), required=True)
    parser.add_argument(
        "--apply", action="store_true", help="Write the validated snapshot atomically"
    )
    args = parser.parse_args()
    try:
        prepared = prepare_snapshot(json.loads(args.input.read_text()), args.mode)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        print("Snapshot rejected: check report structure, units, timestamps and usable readings.")
        return 1
    readings = prepared["observations"]
    print(f"Validated {len(readings)} observations from {len(prepared['stations'])} stations.")
    print(f"Excluded rows: {prepared['rejected']}")
    print(
        f"Observation range: {min(r.observed_at for r in readings).isoformat()} to "
        f"{max(r.observed_at for r in readings).isoformat()}"
    )
    print("Freshness and geographic coverage still require review before scoring.")
    if not args.apply:
        print("Dry run; no database writes. Use --apply to ingest.")
        return 0
    url = get_settings().database_url
    if url is None:
        print("Database URL is unconfigured.")
        return 2
    try:
        with psycopg.connect(
            url.get_secret_value(), connect_timeout=10, sslmode="verify-full", sslrootcert=str(CA)
        ) as connection:
            inserted = ingest_snapshot(connection, prepared)
        print("Snapshot ingested." if inserted else "Snapshot already exists; no rows changed.")
        print(f"Snapshot ID: {prepared['snapshot_id']}")
        return 0
    except psycopg.Error as error:
        print(
            f"Ingestion failed (SQLSTATE {error.sqlstate or 'connection'}); no changes committed."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
