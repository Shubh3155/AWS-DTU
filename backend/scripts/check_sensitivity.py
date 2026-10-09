"""Evaluate a fixed recorded walking-route set over a 27-policy sensitivity grid."""

import argparse
import hashlib
import itertools
import json
from pathlib import Path

from app.model.baseline import BaselinePolicy
from app.model.sensitivity import assess_ranking
from app.schemas.routes import ComparisonRequest
from app.services.ingestion import prepare_snapshot
from app.services.snapshots import PollutionSnapshot
from app.services.walking import WalkingRoute


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True, help="Genuine monitoring audit")
    parser.add_argument("--journey", type=Path, required=True, help="JSON with request and routes")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        source = args.snapshot.read_bytes()
        journey = args.journey.read_bytes()
        prepared = prepare_snapshot(json.loads(source), "replay")
        recorded = json.loads(journey)
        snapshot = PollutionSnapshot(
            snapshot_id=prepared["snapshot_id"],
            data_version=prepared["data_version"],
            data_mode="replay",
            observed_to=max(r.observed_at for r in prepared["observations"]),
            fetched_at=prepared["fetched_at"],
            observations=prepared["observations"],
        )
        request = ComparisonRequest.model_validate(recorded["request"])
        if request.snapshot_id and request.snapshot_id != snapshot.snapshot_id:
            raise ValueError("Recorded request and snapshot identities disagree.")
        policies = [
            BaselinePolicy(
                station_radius_metres=radius, max_age_hours=age, sampling_interval_metres=interval
            )
            for radius, age, interval in itertools.product(
                (5000, 10000, 15000), (1, 2, 4), (50, 100, 200)
            )
        ]
        report = assess_ranking(
            [WalkingRoute.model_validate(r) for r in recorded["routes"]],
            request,
            snapshot,
            policies,
        )
        report.update(
            snapshot_input_sha256=hashlib.sha256(source).hexdigest(),
            journey_input_sha256=hashlib.sha256(journey).hexdigest(),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x") as output:
            output.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
        print(json.dumps(report["summary"], indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError):
        print(
            "Sensitivity check failed; verify inputs, explicit replay and unused output filename."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
