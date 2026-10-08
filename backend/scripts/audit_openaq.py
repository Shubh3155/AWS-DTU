import argparse
import json
from pathlib import Path

import httpx

from app.core.config import get_settings
from app.services.openaq import audit_locations


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect Delhi PM2.5 station coverage via OpenAQ.")
    parser.add_argument("--lat", type=float, default=28.6139)
    parser.add_argument("--lng", type=float, default=77.2090)
    parser.add_argument("--radius", type=int, default=25000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not (-90 <= args.lat <= 90 and -180 <= args.lng <= 180):
        parser.error("Coordinates are outside the supported latitude/longitude range.")
    if not 0 < args.radius <= 25000:
        parser.error("Radius must be between 1 and 25000 metres.")
    if args.output.exists():
        parser.error("Output already exists; choose a new timestamped filename.")
    key = get_settings().openaq_api_key
    if key is None:
        print("OpenAQ audit not run: configure AEROROUTE_OPENAQ_API_KEY in backend/.env.")
        return 2
    try:
        with httpx.Client(
            base_url="https://api.openaq.org",
            headers={"X-API-Key": key.get_secret_value()},
            timeout=20,
        ) as client:
            report = audit_locations(client, args.lat, args.lng, args.radius)
    except httpx.HTTPStatusError as error:
        print(f"OpenAQ audit failed: HTTP {error.response.status_code}; no report saved.")
        return 1
    except (httpx.RequestError, ValueError, KeyError):
        print("OpenAQ audit failed: network error or unexpected response; no report saved.")
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    print(f"Audit saved: {report['station_count']} candidate stations; review coverage before use.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
