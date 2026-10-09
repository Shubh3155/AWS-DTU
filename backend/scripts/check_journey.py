"""Verify a configured journey, exact eligibility and repeated comparison latency."""

import argparse
import json
import math
import statistics
import time
from pathlib import Path

import httpx

from app.schemas.routes import ComparisonRequest, ComparisonResponse


def verify_budget(request: ComparisonRequest, result: ComparisonResponse) -> None:
    if not result.candidates:
        raise ValueError("No walking candidate is available")
    fastest = min(result.candidates, key=lambda route: (route.duration_seconds, route.id))
    if result.fastest_id != fastest.id:
        raise ValueError("Fastest route ID is inconsistent")
    for candidate in result.candidates:
        eligible = (
            candidate.duration_seconds <= fastest.duration_seconds + 60 * request.max_detour_minutes
        )
        if candidate.within_budget != eligible:
            raise ValueError("Time-budget eligibility is inconsistent")
    if result.lowest_exposure_eligible_id:
        selected = next(
            route for route in result.candidates if route.id == result.lowest_exposure_eligible_id
        )
        if not selected.within_budget or selected.estimated_exposure is None:
            raise ValueError("Selected candidate is outside the allowance or unsupported")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--repeat", type=int, default=10)
    parser.add_argument("--require-score", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or not 10 <= args.repeat <= 50:
        parser.error("Select a new output file and 10–50 repetitions")
    try:
        payload = ComparisonRequest.model_validate_json(args.request.read_text())
        samples = []
        with httpx.Client(base_url=args.api_url.rstrip("/"), timeout=30) as client:
            for _ in range(args.repeat):
                started = time.perf_counter()
                response = client.post("/api/routes/compare", json=payload.model_dump())
                elapsed = time.perf_counter() - started
                response.raise_for_status()
                result = ComparisonResponse.model_validate(response.json())
                verify_budget(payload, result)
                if args.require_score and (
                    not result.lowest_exposure_eligible_id
                    or result.data_quality.data_mode == "unavailable"
                ):
                    raise ValueError("A supported genuine-data comparison is unavailable")
                samples.append(
                    {
                        "seconds": elapsed,
                        "cache": response.headers.get("X-AeroRoute-Cache", "unknown"),
                        "status": result.status,
                        "snapshot_id": result.data_quality.snapshot_id,
                    }
                )
        summaries = {}
        for mode in {sample["cache"] for sample in samples}:
            times = sorted(sample["seconds"] for sample in samples if sample["cache"] == mode)
            summaries[mode] = {
                "count": len(times),
                "median_seconds": statistics.median(times),
                "p95_seconds": times[math.ceil(0.95 * len(times)) - 1],
            }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(
                {
                    "request": payload.model_dump(),
                    "samples": samples,
                    "latency_by_cache": summaries,
                },
                indent=2,
            )
            + "\n"
        )
        print("Journey eligibility and measured latency report saved.")
        return 0
    except (OSError, ValueError, KeyError, StopIteration, httpx.HTTPError):
        print("Journey check failed; no success report saved. Check API access and data support.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
