"""Read-only genuine API smoke check for the historical MVP release."""

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from app.schemas.routes import ComparisonRequest, ComparisonResponse
from scripts.check_journey import verify_budget


def verify_mode(request, result):
    verify_budget(request, result)
    if request.data_mode == "replay":
        if (
            result.data_quality.data_mode != "replay"
            or result.data_quality.snapshot_id != request.snapshot_id
        ):
            raise ValueError("Replay must retain the selected snapshot")
        if any(r.estimated_exposure is None for r in result.candidates):
            raise ValueError("The historical demo lacks full support")
        if len({r.id for r in result.candidates}) < 2:
            raise ValueError("The historical demo lacks distinct alternatives")
    else:
        if result.data_quality.data_mode == "replay":
            raise ValueError("Live mode must never silently use replay")
        if result.data_quality.station_count < 3 and any(
            r.estimated_exposure is not None for r in result.candidates
        ):
            raise ValueError("Insufficient live stations must withhold scores")
    if result.estimated_reduction_percent is not None:
        raise ValueError("The provisional release must withhold reduction claims")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--snapshot-id", required=True)
    parser.add_argument("--expected-version")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Select a new output filename")
    try:
        checks = []
        with httpx.Client(base_url=args.api_url.rstrip("/"), timeout=30) as client:
            health = client.get("/health")
            health.raise_for_status()
            if args.expected_version and health.json()["version"] != args.expected_version:
                raise ValueError("The served release version differs")
            pilot = client.get("/api/pilot")
            pilot.raise_for_status()
            if pilot.json()["status"] != "historical_demo":
                raise ValueError("The historical demo boundary is unavailable")
            for mode, allowance in [("replay", 0), ("replay", 5), ("replay", 15), ("live", 5)]:
                request = ComparisonRequest(
                    origin={"lat": 28.6315, "lng": 77.2167},
                    destination={"lat": 28.628, "lng": 77.241},
                    max_detour_minutes=allowance,
                    data_mode=mode,
                    snapshot_id=args.snapshot_id if mode == "replay" else None,
                )
                started = time.perf_counter()
                response = client.post("/api/routes/compare", json=request.model_dump())
                seconds = time.perf_counter() - started
                response.raise_for_status()
                result = ComparisonResponse.model_validate(response.json())
                verify_mode(request, result)
                checks.append(
                    {
                        "mode": mode,
                        "allowance_minutes": allowance,
                        "seconds": seconds,
                        "cache": response.headers.get("X-AeroRoute-Cache"),
                        "result": result.model_dump(
                            mode="json", exclude={"candidates": {"__all__": {"geometry"}}}
                        ),
                    }
                )
        report = {
            "checked_at": datetime.now(UTC).isoformat(),
            "health": health.json(),
            "pilot": pilot.json(),
            "checks": checks,
            "passed": True,
            "limitations": [
                "This checks API behavior, not route-level field accuracy.",
                "Inspect desktop/mobile rendering separately.",
            ],
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x") as output:
            output.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
        print("Historical MVP and live-data safety checks passed; release report saved.")
        return 0
    except (OSError, ValueError, KeyError, httpx.HTTPError):
        print("Release check failed; verify API, snapshot, served version and data support.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
