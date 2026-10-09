"""Check a fixed demo grid through every recorded timestamp without fitting policy."""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from app.core.pilot import EAST, NORTH, SOUTH, WEST
from app.model.baseline import BaselinePolicy, distance_metres, usable_observations
from app.schemas.routes import Coordinate
from app.services.ingestion import prepare_snapshot


def review(report, now):
    prepared = prepare_snapshot(report, "replay")
    observations = prepared["observations"]
    policy = BaselinePolicy()
    grid = [
        Coordinate(lat=SOUTH + (NORTH - SOUTH) * y / 10, lng=WEST + (EAST - WEST) * x / 10)
        for y in range(11)
        for x in range(11)
    ]
    references = sorted({r.observed_at for r in observations})
    checks = []
    for reference in [*references, now]:
        usable = usable_observations(observations, reference, policy)
        counts = [
            len(
                {
                    (r.provider_id, r.station_id)
                    for r in usable
                    if distance_metres(point, r.location) <= policy.station_radius_metres
                }
            )
            for point in grid
        ]
        checks.append(
            {
                "reference_time": reference.isoformat(),
                "minimum_nearby_stations": min(counts),
                "supported_grid_points": sum(n >= policy.minimum_stations for n in counts),
            }
        )
    return {
        "snapshot_id": prepared["snapshot_id"],
        "policy": policy.model_dump(),
        "grid_points": len(grid),
        "historical_references": len(references),
        "fully_supported_historical_references": sum(
            r["supported_grid_points"] == len(grid) for r in checks[:-1]
        ),
        "latest_recorded_reference": checks[-2],
        "current_reference": checks[-1],
        "references": checks[:-1],
        "sources": report["source_files"],
        "download_statuses": report["download_statuses"],
        "limitations": [
            "A sampled grid does not guarantee support between grid points.",
            "Station availability is not street-level accuracy.",
            "Each route is independently checked when scored.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Select a new output filename")
    now = datetime.now(UTC)
    results = []
    for path in args.inputs:
        content = path.read_bytes()
        result = review(json.loads(content), now)
        result["input_sha256"] = hashlib.sha256(content).hexdigest()
        results.append(result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as output:
        output.write(
            json.dumps(
                {
                    "reviewed_at": now.isoformat(),
                    "bounds": {"south": SOUTH, "north": NORTH, "west": WEST, "east": EAST},
                    "periods": results,
                },
                indent=2,
                allow_nan=False,
            )
            + "\n"
        )
    for result in results:
        print(
            json.dumps(
                {
                    k: result[k]
                    for k in (
                        "historical_references",
                        "fully_supported_historical_references",
                        "latest_recorded_reference",
                        "current_reference",
                    )
                }
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
