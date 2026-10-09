"""Offline fixed median challenger; it does not change the running scorer."""

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from statistics import median

from app.model.baseline import BaselinePolicy, nearby_stations
from app.model.contracts import ConcentrationEstimate
from app.model.validation import evaluate
from app.services.ingestion import prepare_snapshot


def median_estimate(point, observations, policy):
    stations = nearby_stations(point, observations, policy)
    if len(stations) < policy.minimum_stations:
        return ConcentrationEstimate(
            warnings=["Too few distinct nearby stations for interpolation."]
        )
    return ConcentrationEstimate(
        pm25_micrograms_per_m3=float(median(station[2] for station in stations)),
        supporting_sensor_ids=sorted({r.sensor_id for station in stations for r in station[3]}),
    )


def compare(source, cutoff):
    prepared = prepare_snapshot(json.loads(source), "replay")
    policy = BaselinePolicy()
    outputs = {}
    for name, estimator in [("idw", None), ("median_nearest", median_estimate)]:
        result = evaluate(prepared["observations"], cutoff, policy, estimator=estimator)
        outputs[name] = {"summary": result["summary"], "by_station": result["by_station"]}
    improvements = []
    for split in ("early", "later"):
        baseline = outputs["idw"]["summary"][split]
        challenger = outputs["median_nearest"]["summary"][split]
        improvements.append(
            challenger["supported"] == baseline["supported"]
            and baseline["mae"] is not None
            and challenger["mae"] < baseline["mae"]
            and challenger["rmse"] < baseline["rmse"]
        )
    return {
        "input_sha256": hashlib.sha256(source).hexdigest(),
        "snapshot_id": prepared["snapshot_id"],
        "cutoff": cutoff.isoformat(),
        "policy": policy.model_dump(),
        "estimators": outputs,
        "improves_both_metrics_with_equal_support_in_both_blocks": all(improvements),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, nargs="+", required=True)
    parser.add_argument("--cutoffs", type=datetime.fromisoformat, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if len(args.inputs) != len(args.cutoffs) or args.output.exists():
        parser.error("Match each input with a cutoff and select a new output filename")
    try:
        results = [
            compare(path.read_bytes(), cutoff)
            for path, cutoff in zip(args.inputs, args.cutoffs, strict=True)
        ]
        report = {
            "experiment": "fixed median of nearest distinct station values",
            "periods": results,
            "passes_adoption_gate": all(
                r["improves_both_metrics_with_equal_support_in_both_blocks"] for r in results
            ),
            "adoption_gate": "Lower MAE and RMSE, equal support, both blocks of every period.",
            "production_changed": False,
            "limitations": [
                "Previously reviewed periods are development evidence.",
                "December was requested as a separate confirmation period.",
                "Station errors do not validate street-level route benefits.",
            ],
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x") as output:
            output.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
        print(
            json.dumps(
                {
                    "passes_adoption_gate": report["passes_adoption_gate"],
                    "later_metrics": [
                        {
                            name: result["summary"]["later"]
                            for name, result in r["estimators"].items()
                        }
                        for r in results
                    ],
                },
                indent=2,
            )
        )
        return 0
    except (OSError, ValueError, KeyError, TypeError):
        print("Estimator comparison failed; check inputs, cutoff and output filename.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
