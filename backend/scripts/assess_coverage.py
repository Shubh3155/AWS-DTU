"""Report live/replay support and prerequisites for held-out evaluation."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import get_settings
from app.model.baseline import BaselinePolicy, distance_metres, interpolate, usable_observations
from app.schemas.routes import Coordinate
from app.services.ingestion import prepare_snapshot
from app.services.snapshots import PollutionSnapshot, load_snapshot


def assess(
    snapshot: PollutionSnapshot, point: Coordinate, policy: BaselinePolicy, now: datetime
) -> dict:
    counts = {}
    for reading in snapshot.observations:
        counts.setdefault(reading.observed_at.isoformat(), set()).add(
            (reading.provider_id, reading.station_id)
        )
    windows = {}
    for mode, reference in [("live", now), ("replay", snapshot.observed_to)]:
        usable = usable_observations(snapshot.observations, reference, policy)
        nearby = {
            (r.provider_id, r.station_id)
            for r in usable
            if distance_metres(point, r.location) <= policy.station_radius_metres
        }
        windows[mode] = {
            "reference_time": reference.isoformat(),
            "time_filtered_stations": len({(r.provider_id, r.station_id) for r in usable}),
            "nearby_stations": len(nearby),
            "point_support_sufficient": interpolate(point, usable, policy).pm25_micrograms_per_m3
            is not None,
        }
    return {
        "snapshot_id": snapshot.snapshot_id,
        "data_version": snapshot.data_version,
        "point": point.model_dump(),
        "policy": policy.model_dump(),
        "windows": windows,
        "unique_observation_times": len(counts),
        "max_coincident_station_ids": max(map(len, counts.values()), default=0),
        "station_holdout_count_prerequisite": any(
            len(c) > policy.minimum_stations for c in counts.values()
        ),
        "temporal_holdout_count_prerequisite": len(counts) > 1,
        "pilot_approved": False,
        "limitations": [
            "Station IDs do not prove independent geography or instruments.",
            "Support at one point does not establish full-route coverage.",
            "Count prerequisites are not a validated evaluation split.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--snapshot-id")
    parser.add_argument("--mode", choices=("live", "replay"), default="replay")
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lng", type=float, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output exists; select a new filename")
    settings = get_settings()
    try:
        if args.input:
            prepared = prepare_snapshot(json.loads(args.input.read_text()), args.mode)
            snapshot = PollutionSnapshot(
                snapshot_id=prepared["snapshot_id"],
                data_version=prepared["data_version"],
                data_mode=args.mode,
                observed_to=max(r.observed_at for r in prepared["observations"]),
                fetched_at=prepared["fetched_at"],
                observations=prepared["observations"],
            )
        else:
            snapshot, warnings = load_snapshot(settings, args.mode, args.snapshot_id)
            if snapshot is None:
                print(" ".join(warnings))
                return 2
        report = assess(
            snapshot,
            Coordinate(lat=args.lat, lng=args.lng),
            BaselinePolicy(
                station_radius_metres=settings.baseline_station_radius_metres,
                max_age_hours=settings.baseline_max_age_hours,
            ),
            datetime.now(UTC),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        print("Coverage report saved. Pilot approval and independent validation remain separate.")
        return 0
    except (OSError, ValueError, KeyError, TypeError):
        print("Coverage assessment failed: invalid input or observation metadata.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
