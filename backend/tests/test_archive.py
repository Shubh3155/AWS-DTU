import csv
import gzip
import io

import pytest

from app.schemas.routes import Coordinate
from app.services.ingestion import ARCHIVE_SOURCE, prepare_snapshot
from scripts.fetch_archive import station_hours


def archive(rows):
    stream = io.StringIO()
    writer = csv.DictWriter(
        stream,
        fieldnames=[
            "location_id",
            "sensors_id",
            "location",
            "datetime",
            "lat",
            "lon",
            "parameter",
            "units",
            "value",
        ],
    )
    writer.writeheader()
    for changes in rows:
        writer.writerow(
            {
                "location_id": 1,
                "sensors_id": 2,
                "location": "Synthetic archive test",
                "datetime": "2025-10-07T10:15:00+00:00",
                "lat": 28.6,
                "lon": 77.2,
                "parameter": "pm25",
                "units": "µg/m³",
                "value": 20,
                **changes,
            }
        )
    return gzip.compress(stream.getvalue().encode())


def convert(rows, radius=10000):
    return station_hours(archive(rows), 1, Coordinate(lat=28.6, lng=77.2), radius)


def test_derived_hour_deduplicates_and_preserves_actual_time_and_provenance():
    station = convert([{}, {}, {"datetime": "2025-10-07T10:45:00+00:00", "value": 60}])
    reading = station["measurements"][0]
    assert reading["value"] == 40
    assert reading["source_count"] == 2
    assert reading["observed_at"] == "2025-10-07T10:45:00+00:00"
    report = {
        "source": ARCHIVE_SOURCE,
        "fetched_at": "2026-10-09T00:00:00Z",
        "stations": [station],
        "source_files": [{"url": "https://example.test/source.csv.gz", "sha256": "fixture"}],
    }
    prepared = prepare_snapshot(report, "replay")
    assert prepared["source_manifest"]["source_files"] == report["source_files"]
    metadata = next(iter(prepared["observation_metadata"].values()))
    assert metadata["aggregation"] == reading["aggregation"]
    assert metadata["period"] == reading["period"]
    with pytest.raises(ValueError, match="restricted"):
        prepare_snapshot(report, "live")


def test_conflicting_timestamp_and_station_movement_require_review():
    with pytest.raises(RuntimeError, match="Conflicting"):
        convert([{}, {"value": 60}])
    with pytest.raises(ValueError, match="coordinates vary"):
        convert([{}, {"datetime": "2025-10-07T11:15:00Z", "lat": 28.61}])


def test_invalid_units_values_time_and_outside_radius_do_not_create_support():
    assert (
        convert(
            [
                {"units": "ppm"},
                {"value": -1},
                {"value": "nan"},
                {"datetime": "2025-10-07T10:15:00"},
                {"parameter": "no2"},
            ]
        )
        is None
    )
    assert convert([{"lat": 29.6}], radius=1000) is None
    assert convert([{}, {"units": "ppm"}])["rejected_rows"] == 1


def test_hourly_api_report_retains_coverage_metadata():
    station = convert([{}])
    station["measurements"][0]["coverage"] = {"percentComplete": 50}
    prepared = prepare_snapshot(
        {
            "source": "OpenAQ v3 hourly",
            "fetched_at": "2026-10-09T00:00:00Z",
            "stations": [station],
            "interval": {"from": "2025-10-07T10:00:00Z", "to": "2025-10-07T11:00:00Z"},
        },
        "replay",
    )
    assert next(iter(prepared["observation_metadata"].values()))["coverage"] == {
        "percentComplete": 50
    }
    assert prepared["source_manifest"]["interval"]["to"].endswith("11:00:00Z")
