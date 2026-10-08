"""Save a genuine walking response for access/geometry/timing review, without its token."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

from app.core.config import get_settings
from app.schemas.routes import Coordinate


def audit_walking(
    client: httpx.Client, token: str, origin: Coordinate, destination: Coordinate
) -> dict:
    coordinates = f"{origin.lng},{origin.lat};{destination.lng},{destination.lat}"
    response = client.get(
        f"/directions/v5/mapbox/walking/{coordinates}",
        params={
            "access_token": token,
            "alternatives": "true",
            "steps": "true",
            "geometries": "geojson",
            "overview": "full",
        },
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") not in ("Ok", "NoRoute", "NoSegment"):
        raise ValueError("Unexpected provider response")
    routes = payload.get("routes", [])
    if not isinstance(routes, list) or (payload["code"] == "Ok" and not routes):
        raise ValueError("Invalid provider route list")
    return {
        "source": "Mapbox Directions v5",
        "fetched_at": datetime.now(UTC).isoformat(),
        "mode": "walking",
        "origin": origin.model_dump(),
        "destination": destination.model_dump(),
        "candidate_count": len(routes),
        "response": payload,
        "limitations": [
            "This access check does not select a pilot or estimate pollution exposure.",
            "Alternatives are requested but not guaranteed.",
            "Route and step durations are in seconds; distances are in metres.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit a real Mapbox walking journey.")
    parser.add_argument("--origin", nargs=2, type=float, metavar=("LAT", "LNG"), required=True)
    parser.add_argument("--destination", nargs=2, type=float, metavar=("LAT", "LNG"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        origin = Coordinate(lat=args.origin[0], lng=args.origin[1])
        destination = Coordinate(lat=args.destination[0], lng=args.destination[1])
    except ValueError:
        parser.error("Coordinates must be finite and within latitude/longitude bounds.")
    if args.output.exists():
        parser.error("Output already exists; choose a new timestamped filename.")
    token = get_settings().mapbox_token
    if token is None:
        print("Mapbox audit not run: configure AEROROUTE_MAPBOX_TOKEN in backend/.env.")
        return 2
    try:
        with httpx.Client(base_url="https://api.mapbox.com", timeout=20) as client:
            report = audit_walking(client, token.get_secret_value(), origin, destination)
    except httpx.HTTPStatusError as error:
        print(f"Mapbox audit failed: HTTP {error.response.status_code}; no report saved.")
        return 1
    except (httpx.RequestError, ValueError, KeyError):
        # Request exception strings can include access_token; never print them.
        print("Mapbox audit failed: network error or unexpected response; no report saved.")
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as output:
        output.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(
        f"Saved {report['candidate_count']} walking candidates; review geometry and step timings."
    )
    return 0 if report["candidate_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
