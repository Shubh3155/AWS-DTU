import copy

import pytest

from app.services.ingestion import prepare_snapshot


def report():
    return {
        "source": "OpenAQ v3",
        "fetched_at": "2026-10-08T10:00:00Z",
        "stations": [
            {
                "station_id": 1,
                "name": "Synthetic fixture",
                "coordinates": {"latitude": 28.6, "longitude": 77.2},
                "measurements": [
                    {
                        "sensor_id": 2,
                        "value": 42.0,
                        "unit": "ug/m3",
                        "observed_at": "2026-10-07T10:00:00Z",
                    }
                ],
            }
        ],
    }


def test_snapshot_preserves_time_source_unit_and_repeat_identity():
    raw = report()
    snapshot = prepare_snapshot(raw, "replay")
    reading = snapshot["observations"][0]
    assert reading.observed_at.day == 7
    assert snapshot["mode"] == "replay"
    assert snapshot["source_units"][(reading.sensor_id, reading.observed_at)] == "ug/m3"
    assert prepare_snapshot(raw, "replay")["snapshot_id"] == snapshot["snapshot_id"]
    assert prepare_snapshot(raw, "live")["snapshot_id"] != snapshot["snapshot_id"]


@pytest.mark.parametrize(
    "change",
    [
        {"value": -1.0},
        {"value": True},
        {"unit": "ppm"},
        {"observed_at": "2026-10-09T10:00:00Z"},
        {"observed_at": "2026-10-07T10:00:00"},
        {"sensor_id": True},
    ],
)
def test_unusable_readings_cannot_create_snapshot(change):
    raw = report()
    raw["stations"][0]["measurements"][0].update(change)
    with pytest.raises(ValueError):
        prepare_snapshot(raw, "replay")


def test_duplicate_readings_deduplicate_but_conflicts_reject():
    raw = report()
    raw["stations"][0]["measurements"].append(copy.deepcopy(raw["stations"][0]["measurements"][0]))
    assert len(prepare_snapshot(raw, "replay")["observations"]) == 1
    raw["stations"][0]["measurements"][1]["value"] = 50.0
    with pytest.raises(ValueError):
        prepare_snapshot(raw, "replay")
