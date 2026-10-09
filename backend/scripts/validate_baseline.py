"""Evaluate an archived replay using a fixed policy and explicit temporal cutoff."""

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

from app.model.baseline import BaselinePolicy
from app.model.validation import evaluate
from app.services.ingestion import prepare_snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--cutoff", required=True, help="Timezone-aware ISO timestamp")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        content = args.input.read_bytes()
        prepared = prepare_snapshot(json.loads(content), "replay")
        report = evaluate(
            prepared["observations"], datetime.fromisoformat(args.cutoff), BaselinePolicy()
        )
        report.update(
            snapshot_id=prepared["snapshot_id"], input_sha256=hashlib.sha256(content).hexdigest()
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x") as output:
            output.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
        print(json.dumps(report["summary"], indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError):
        print("Validation failed: check input, cutoff and unused output filename.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
