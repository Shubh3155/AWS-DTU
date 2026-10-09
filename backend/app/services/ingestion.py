"""Validate an OpenAQ audit before atomic ingestion. No missing values become zero."""

import hashlib
import json
from collections import Counter
from datetime import datetime
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from app.model.contracts import StationObservation
from app.schemas.routes import Coordinate

UNITS = {"µg/m³", "μg/m³", "ug/m3", "µg/m3", "μg/m3"}
ARCHIVE_SOURCE = "OpenAQ public archive, derived UTC station-hour means"
SOURCES = {"OpenAQ v3", "OpenAQ v3 hourly", ARCHIVE_SOURCE}


def prepare_snapshot(report: dict[str, Any], mode: str) -> dict[str, Any]:
    if report.get("source") not in SOURCES or mode not in ("live", "replay"):
        raise ValueError("Expected a supported OpenAQ report and explicit live/replay mode.")
    if report["source"] == ARCHIVE_SOURCE and mode != "replay":
        raise ValueError("Derived public archive labels are restricted to explicit replay.")
    fetched = datetime.fromisoformat(report["fetched_at"].replace("Z", "+00:00"))
    if fetched.tzinfo is None:
        raise ValueError("Fetch time must include a timezone.")
    digest = hashlib.sha256(
        json.dumps(report, sort_keys=True, allow_nan=False).encode()
    ).hexdigest()
    rejected: Counter[str] = Counter()
    observations: dict[tuple[int, datetime], StationObservation] = {}
    stations = {}
    source_units = {}
    observation_metadata = {}
    for raw_station in report["stations"]:
        try:
            location = Coordinate(
                lat=raw_station["coordinates"]["latitude"],
                lng=raw_station["coordinates"]["longitude"],
            )
            station_id = raw_station["station_id"]
            if type(station_id) is not int or station_id <= 0:
                raise ValueError("Invalid station ID")
        except (ValueError, KeyError, TypeError):
            rejected["invalid_station"] += 1
            continue
        for raw in raw_station.get("measurements", []):
            if raw.get("unit") not in UNITS:
                rejected["unsupported_unit"] += 1
                continue
            try:
                if type(raw["sensor_id"]) is not int or raw["sensor_id"] <= 0:
                    raise ValueError("Invalid sensor ID")
                observation = StationObservation(
                    sensor_id=raw["sensor_id"],
                    station_id=station_id,
                    location=location,
                    pm25_micrograms_per_m3=raw["value"],
                    observed_at=raw["observed_at"],
                    fetched_at=fetched,
                    provider_id="openaq",
                )
                if observation.observed_at > fetched:
                    raise ValueError("Future observation")
            except (ValueError, KeyError, TypeError):
                rejected["invalid_reading"] += 1
                continue
            key = (observation.sensor_id, observation.observed_at)
            if key in observations:
                if observations[key] != observation:
                    raise ValueError("Conflicting values/station mapping for one sensor timestamp.")
                rejected["duplicate_reading"] += 1
                continue
            observations[key] = observation
            source_units[key] = raw["unit"]
            observation_metadata[key] = {
                **{"latitude": location.lat, "longitude": location.lng},
                **{
                    field: raw[field]
                    for field in (
                        "period",
                        "coverage",
                        "aggregation",
                        "source_count",
                        "source_units",
                    )
                    if field in raw
                },
            }
            stations[station_id] = {
                "name": raw_station.get("name") or str(station_id),
                "location": location,
                "metadata": {key: raw_station.get(key) for key in ("provider", "licenses")},
            }
    if not observations:
        raise ValueError("No usable PM2.5 readings; no snapshot will be created.")
    return {
        "snapshot_id": f"openaq-{mode}-{digest}",
        "data_version": f"openaq-{digest}",
        "mode": mode,
        "fetched_at": fetched,
        "stations": stations,
        "observations": list(observations.values()),
        "source_units": source_units,
        "observation_metadata": observation_metadata,
        "rejected": dict(rejected),
        "source_manifest": {
            "source": report["source"],
            "sha256": digest,
            "search": report.get("search"),
            "pagination_capped": report.get("pagination_capped"),
            "source_files": report.get("source_files", []),
            "interval": report.get("interval"),
            "sensor_selection_capped": report.get("sensor_selection_capped", False),
            "limitations": report.get("limitations", []),
            "rejected": dict(rejected),
        },
    }


def ingest_snapshot(connection: psycopg.Connection, prepared: dict[str, Any]) -> bool:
    """Caller owns the transaction. Identical reports are idempotent."""
    connection.execute("SET LOCAL statement_timeout = 30000")
    # Serialize ingestions so duplicate report attempts cannot partly update stations.
    connection.execute("SELECT pg_advisory_xact_lock(7813156)")
    snapshot_id = prepared["snapshot_id"]
    if connection.execute(
        "SELECT 1 FROM aeroroute.snapshots WHERE snapshot_id=%s", (snapshot_id,)
    ).fetchone():
        return False
    readings = prepared["observations"]
    observed = [reading.observed_at for reading in readings]
    connection.execute(
        "INSERT INTO aeroroute.snapshots (snapshot_id,data_version,data_mode,"
        "observed_from,observed_to,fetched_at,source_manifest) VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (
            snapshot_id,
            prepared["data_version"],
            prepared["mode"],
            min(observed),
            max(observed),
            prepared["fetched_at"],
            Jsonb(prepared["source_manifest"]),
        ),
    )
    for station_id, station in prepared["stations"].items():
        point = station["location"]
        connection.execute(
            "INSERT INTO aeroroute.stations "
            "(provider_id,station_id,name,latitude,longitude,metadata) "
            "VALUES ('openaq',%s,%s,%s,%s,%s) ON CONFLICT (provider_id,station_id) "
            "DO UPDATE SET name=EXCLUDED.name,latitude=EXCLUDED.latitude,"
            "longitude=EXCLUDED.longitude,metadata=EXCLUDED.metadata,updated_at=now()",
            (station_id, station["name"], point.lat, point.lng, Jsonb(station["metadata"])),
        )
    for reading in readings:
        connection.execute(
            "INSERT INTO aeroroute.observations (snapshot_id,provider_id,station_id,sensor_id,"
            "observed_at,fetched_at,pm25_micrograms_per_m3,source_unit,metadata) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                snapshot_id,
                reading.provider_id,
                reading.station_id,
                reading.sensor_id,
                reading.observed_at,
                reading.fetched_at,
                reading.pm25_micrograms_per_m3,
                prepared["source_units"][(reading.sensor_id, reading.observed_at)],
                Jsonb(prepared["observation_metadata"][(reading.sensor_id, reading.observed_at)]),
            ),
        )
    return True
