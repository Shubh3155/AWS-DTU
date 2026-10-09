"""Publish an immutable OpenAQ report and timestamp/source manifest to private S3."""

import argparse
import hashlib
import json
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import get_settings
from app.services.ingestion import prepare_snapshot


def snapshot_objects(raw: bytes, mode: str) -> dict[str, bytes]:
    report = json.loads(raw)
    prepared = prepare_snapshot(report, mode)
    observations = prepared["observations"]
    latest = max(r.observed_at for r in observations)
    prefix = f"snapshots/{latest:%Y/%m/%d}/{prepared['snapshot_id']}"
    manifest = {
        **prepared["source_manifest"],
        "snapshot_id": prepared["snapshot_id"],
        "data_version": prepared["data_version"],
        "data_mode": mode,
        "report_sha256": hashlib.sha256(raw).hexdigest(),
        "fetched_at": prepared["fetched_at"].isoformat(),
        "observed_from": min(r.observed_at for r in observations).isoformat(),
        "observed_to": latest.isoformat(),
        "observation_count": len(observations),
        "stations": [
            {
                "station_id": station["station_id"],
                "provider": station.get("provider"),
                "licenses": station.get("licenses"),
            }
            for station in report["stations"]
        ],
    }
    return {
        prefix + "/report.json": raw,
        prefix + "/manifest.json": (
            json.dumps(manifest, sort_keys=True, allow_nan=False) + "\n"
        ).encode(),
    }


def publish(client, bucket: str, objects: dict[str, bytes]) -> list[str]:
    uris = []
    for key, body in objects.items():
        digest = hashlib.sha256(body).hexdigest()
        try:
            client.put_object(
                Bucket=bucket,
                Key=key,
                Body=body,
                ContentType="application/json",
                ServerSideEncryption="AES256",
                IfNoneMatch="*",
                Metadata={"sha256": digest},
            )
        except ClientError as error:
            if error.response["Error"]["Code"] not in ("PreconditionFailed", "412"):
                raise
            existing = client.head_object(Bucket=bucket, Key=key)
            if existing.get("Metadata", {}).get("sha256") != digest:
                raise ValueError("Existing immutable object has different content") from None
        uris.append(f"s3://{bucket}/{key}")
    return uris


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--mode", choices=("live", "replay"), required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    try:
        objects = snapshot_objects(args.input.read_bytes(), args.mode)
        if not args.apply:
            print(f"Validated {len(objects)} snapshot objects; no upload. Use --apply to publish.")
            return 0
        if not settings.s3_bucket or not settings.aws_region:
            print("Upload not run: configure AEROROUTE_S3_BUCKET and AEROROUTE_AWS_REGION.")
            return 2
        client = boto3.Session(region_name=settings.aws_region).client("s3")
        uris = publish(client, settings.s3_bucket, objects)
        print("Snapshot report and manifest verified in S3:")
        print("\n".join(uris))
        return 0
    except (OSError, ValueError, KeyError, TypeError, BotoCoreError, ClientError):
        print("Snapshot publish failed: check report, AWS credentials and bucket permissions.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
