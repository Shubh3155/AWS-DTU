"""Fetch bounded hourly labels from sensors in a saved OpenAQ audit."""

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

import httpx

from app.core.config import get_settings
from app.services.history import download_hours
from app.services.ingestion import prepare_snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--from", dest="start", type=datetime.fromisoformat, required=True)
    parser.add_argument("--to", dest="end", type=datetime.fromisoformat, required=True)
    parser.add_argument("--max-sensors", type=int, default=10)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output exists; select a new filename")
    key = get_settings().openaq_api_key
    if key is None:
        print("History download not run: configure AEROROUTE_OPENAQ_API_KEY.")
        return 2
    try:
        audit = json.loads(args.audit.read_text())
        with httpx.Client(
            base_url="https://api.openaq.org",
            timeout=20,
            headers={"X-API-Key": key.get_secret_value()},
            event_hooks={"request": [lambda request: time.sleep(1.1)]},
        ) as client:
            report = download_hours(client, audit, args.start, args.end, args.max_sensors)
        prepared = prepare_snapshot(report, "replay")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        print(f"Saved {len(prepared['observations'])} usable hourly observations; review coverage.")
        return 0
    except httpx.HTTPStatusError as error:
        print(f"History download failed: HTTP {error.response.status_code}; no report saved.")
        return 1
    except (OSError, ValueError, KeyError, TypeError, httpx.RequestError):
        print("History download failed: check input, interval, units and provider availability.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
