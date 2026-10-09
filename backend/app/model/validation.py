"""Retrospective station holdout evaluation using contemporaneous neighbours."""

import math
from collections import defaultdict
from datetime import datetime

from app.model.baseline import BaselinePolicy, interpolate, usable_observations
from app.model.contracts import StationObservation


def metrics(rows: list[dict]) -> dict:
    errors = [row["error"] for row in rows if row["error"] is not None]
    return {
        "targets": len(rows),
        "supported": len(errors),
        "unsupported": len(rows) - len(errors),
        "coverage_percent": 100 * len(errors) / len(rows) if rows else None,
        "mae": math.fsum(abs(e) / len(errors) for e in errors) if errors else None,
        "rmse": math.sqrt(math.fsum(e * e / len(errors) for e in errors)) if errors else None,
        "bias": math.fsum(e / len(errors) for e in errors) if errors else None,
    }


def evaluate(
    observations: list[StationObservation],
    cutoff: datetime,
    policy: BaselinePolicy,
    *,
    estimator=None,
) -> dict:
    if cutoff.tzinfo is None:
        raise ValueError("The temporal cutoff must include a timezone.")
    grouped = defaultdict(list)
    for reading in observations:
        grouped[(reading.provider_id, reading.station_id, reading.observed_at)].append(reading)
    rows = []
    for (provider, station, observed), targets in sorted(grouped.items()):
        if any(t.location != targets[0].location for t in targets):
            raise ValueError("Target station coordinates disagree.")
        donors = usable_observations(
            [r for r in observations if (r.provider_id, r.station_id) != (provider, station)],
            observed,
            policy,
        )
        estimate = (estimator or interpolate)(targets[0].location, donors, policy)
        actual = math.fsum(t.pm25_micrograms_per_m3 / len(targets) for t in targets)
        predicted = estimate.pm25_micrograms_per_m3
        rows.append(
            {
                "provider_id": provider,
                "station_id": station,
                "observed_at": observed.isoformat(),
                "split": "early" if observed < cutoff else "later",
                "actual": actual,
                "predicted": predicted,
                "error": predicted - actual if predicted is not None else None,
                "supporting_sensor_ids": estimate.supporting_sensor_ids,
                "warnings": estimate.warnings,
            }
        )
    if not all(any(r["split"] == split for r in rows) for split in ("early", "later")):
        raise ValueError("Both temporal blocks must contain targets.")
    return {
        "method": "leave-one-station-out, fixed-policy contemporaneous interpolation",
        "cutoff": cutoff.isoformat(),
        "policy": policy.model_dump(),
        "model_version": policy.version,
        "units": "micrograms/m3",
        "summary": {s: metrics([r for r in rows if r["split"] == s]) for s in ("early", "later")},
        "by_station": [
            {
                "provider_id": p,
                "station_id": s,
                "summary": {
                    block: metrics(
                        [
                            r
                            for r in rows
                            if r["provider_id"] == p
                            and r["station_id"] == s
                            and r["split"] == block
                        ]
                    )
                    for block in ("early", "later")
                },
            }
            for p, s in sorted({(r.provider_id, r.station_id) for r in observations})
        ],
        "limitations": [
            "The entire target station is excluded at every timestamp.",
            "Donors are observed at or before each target time; this is not forecasting.",
            "Errors describe supported targets only; "
            "unsupported targets remain in coverage counts.",
            "Station interpolation errors do not validate street-level exposure or route rankings.",
        ],
        "rows": rows,
    }
