"""Download bounded public OpenAQ CSV files and derive recorded station-hour labels."""

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx

from app.model.baseline import distance_metres
from app.schemas.routes import Coordinate
from app.services.ingestion import ARCHIVE_SOURCE, prepare_snapshot

BASE = "https://openaq-data-archive.s3.amazonaws.com/"


def station_hours(content: bytes, identity: int, centre: Coordinate, radius: float) -> dict | None:
    if len(content) > 5_000_000:
        raise ValueError("Compressed file exceeds download limit")
    with gzip.GzipFile(fileobj=io.BytesIO(content)) as stream:
        decoded = stream.read(20_000_001)
    if len(decoded) > 20_000_000:
        raise ValueError("CSV exceeds decompression limit")
    groups = defaultdict(list)
    coordinates = set()
    name = ""
    rejected = 0
    seen = {}
    for index, row in enumerate(csv.DictReader(io.StringIO(decoded.decode("utf-8")))):
        if index >= 100000:
            raise ValueError("CSV exceeds row limit")
        if row.get("parameter") != "pm25":
            continue
        try:
            if int(row["location_id"]) != identity:
                raise ValueError("Location identity mismatch")
            point = Coordinate(lat=float(row["lat"]), lng=float(row["lon"]))
            unit = row.get("units", row.get("unit"))
            if unit not in ("µg/m³", "ug/m3", "µg/m3", "μg/m³"):
                raise ValueError("Unsupported concentration unit")
            sensor = int(row.get("sensors_id", row.get("sensor_id")))
            timestamp = datetime.fromisoformat(row["datetime"])
            value = float(row["value"])
            if sensor <= 0 or timestamp.tzinfo is None or not math.isfinite(value) or value < 0:
                raise ValueError("Invalid observation")
            timestamp = timestamp.astimezone(UTC)
            key = (sensor, timestamp)
            current = (value, point.lat, point.lng)
            if key in seen:
                if seen[key] != current:
                    raise RuntimeError("Conflicting readings for one sensor timestamp")
                continue
            seen[key] = current
            coordinates.add((point.lat, point.lng))
            name = row["location"]
            groups[(sensor, timestamp.replace(minute=0, second=0, microsecond=0))].append(
                (timestamp, value, unit)
            )
        except (ValueError, KeyError, TypeError):
            rejected += 1
    if not groups:
        return None
    if len(coordinates) != 1:
        raise ValueError("Station coordinates vary; review before interpolation")
    lat, lng = coordinates.pop()
    if distance_metres(centre, Coordinate(lat=lat, lng=lng)) > radius:
        return None
    measurements = []
    for (sensor, hour), readings in sorted(groups.items()):
        # Preserve actual source time; the mean is explicitly derived, not a new measurement.
        measurements.append(
            {
                "sensor_id": sensor,
                "value": math.fsum(r[1] / len(readings) for r in readings),
                "unit": readings[0][2],
                "observed_at": max(r[0] for r in readings).isoformat(),
                "source_count": len(readings),
                "source_units": sorted({r[2] for r in readings}),
                "period": {"from": hour.isoformat(), "to": (hour + timedelta(hours=1)).isoformat()},
                "aggregation": "arithmetic mean of available archived observations within UTC hour",
            }
        )
    return {
        "station_id": identity,
        "name": name,
        "coordinates": {"latitude": lat, "longitude": lng},
        "provider": {"name": "OpenAQ public archive"},
        "licenses": [],
        "measurements": measurements,
        "rejected_rows": rejected,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--locations", type=int, nargs="+", required=True)
    parser.add_argument("--dates", type=date.fromisoformat, nargs="+", required=True)
    parser.add_argument("--lat", type=float, default=28.6139)
    parser.add_argument("--lng", type=float, default=77.2090)
    parser.add_argument("--radius", type=float, default=25000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if (
        args.output.exists()
        or len(args.locations) * len(args.dates) > 50
        or any(loc <= 0 for loc in args.locations)
    ):
        parser.error("Select a new output file, positive location IDs and at most 50 files")
    if not 1 <= args.radius <= 25000 or any(day >= datetime.now(UTC).date() for day in args.dates):
        parser.error("Use past dates and a search radius of 1–25,000 metres")
    try:
        centre = Coordinate(lat=args.lat, lng=args.lng)
        report = {
            "source": ARCHIVE_SOURCE,
            "fetched_at": datetime.now(UTC).isoformat(),
            "search": {"lat": centre.lat, "lng": centre.lng, "radius_metres": args.radius},
            "stations": [],
            "source_files": [],
            "download_statuses": {},
            "limitations": [
                "Recorded observations do not describe current air.",
                "Means use available samples; complete-hour coverage is not assumed.",
                "Original provider/license metadata is absent from CSV and requires review.",
                "Search bounds are exploratory and do not approve a pilot.",
            ],
        }
        combined = {}
        statuses = Counter()
        with httpx.Client(base_url=BASE, timeout=20) as client:
            for location in args.locations:
                for day in args.dates:
                    key = (
                        f"records/csv.gz/locationid={location}/year={day:%Y}/month={day:%m}/"
                        f"location-{location}-{day:%Y%m%d}.csv.gz"
                    )
                    response = client.get(key)
                    statuses[str(response.status_code)] += 1
                    if response.status_code == 404:
                        continue
                    response.raise_for_status()
                    station = station_hours(response.content, location, centre, args.radius)
                    digest = hashlib.sha256(response.content).hexdigest()
                    folder = args.output.parent / "archive"
                    folder.mkdir(parents=True, exist_ok=True)
                    (folder / f"{location}-{day:%Y%m%d}-{digest[:12]}.csv.gz").write_bytes(
                        response.content
                    )
                    report["source_files"].append(
                        {
                            "url": BASE + key,
                            "sha256": digest,
                            "included_pm25_station": station is not None,
                        }
                    )
                    if station:
                        if location not in combined:
                            combined[location] = station
                        else:
                            if station["coordinates"] != combined[location]["coordinates"]:
                                raise ValueError("Station coordinates changed between days")
                            combined[location]["measurements"].extend(station["measurements"])
        report["stations"] = list(combined.values())
        report["download_statuses"] = dict(statuses)
        report["station_count"] = len(combined)
        report["fetched_at"] = datetime.now(UTC).isoformat()
        prepared = prepare_snapshot(report, "replay")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        print(
            f"Saved {len(prepared['observations'])} genuine derived station-hour labels "
            f"from {len(combined)} stations; replay only."
        )
        return 0
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, httpx.HTTPError):
        print(
            "Archive download not completed; check available dates, units and station coordinates."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
