"""Bounded genuine OpenAQ hourly downloads retaining periods, units and coverage."""

from datetime import UTC, datetime

import httpx


def download_hours(
    client: httpx.Client,
    audit: dict,
    start: datetime,
    end: datetime,
    max_sensors: int = 10,
    max_pages: int = 5,
) -> dict:
    if start.tzinfo is None or end.tzinfo is None or not start < end:
        raise ValueError("Provide an increasing timezone-aware interval")
    if (end - start).total_seconds() > 7 * 86400 or end > datetime.now(UTC):
        raise ValueError("Request at most seven days ending in the past")
    if not 1 <= max_sensors <= 25 or not 1 <= max_pages <= 10:
        raise ValueError("Sensor/page limits are outside the prototype bounds")
    report = {
        "source": "OpenAQ v3 hourly",
        "fetched_at": datetime.now(UTC).isoformat(),
        "search": audit.get("search", {}),
        "stations": [],
        "pagination_capped": False,
        "interval": {"from": start.isoformat(), "to": end.isoformat()},
        "limitations": ["Hourly labels require coverage and leakage-safe split review."],
    }
    count = 0
    seen_sensors = set()
    for station in audit["stations"]:
        measurements = []
        for sensor in station["measurements"]:
            sensor_id = sensor["sensor_id"]
            if type(sensor_id) is not int or sensor_id <= 0:
                raise ValueError("Invalid sensor identity")
            if sensor_id in seen_sensors:
                continue
            if count >= max_sensors:
                report["sensor_selection_capped"] = True
                break
            seen_sensors.add(sensor_id)
            count += 1
            for page in range(1, max_pages + 1):
                response = client.get(
                    f"/v3/sensors/{sensor_id}/hours",
                    params={
                        "datetime_from": start.isoformat(),
                        "datetime_to": end.isoformat(),
                        "limit": 1000,
                        "page": page,
                    },
                )
                response.raise_for_status()
                results = response.json()["results"]
                for reading in results:
                    if reading["parameter"]["name"] != "pm25":
                        continue
                    observed = reading["period"]["datetimeTo"]["utc"]
                    timestamp = datetime.fromisoformat(observed.replace("Z", "+00:00"))
                    if timestamp.tzinfo is None or not start < timestamp <= end:
                        continue
                    measurements.append(
                        {
                            "sensor_id": sensor_id,
                            "value": reading["value"],
                            "unit": reading["parameter"]["units"],
                            "observed_at": observed,
                            "period": reading["period"],
                            "coverage": reading.get("coverage"),
                        }
                    )
                if len(results) < 1000:
                    break
                if page == max_pages:
                    report["pagination_capped"] = True
        if measurements:
            report["stations"].append({**station, "measurements": measurements})
    report["station_count"] = len(report["stations"])
    report["sensor_count"] = count
    report["fetched_at"] = datetime.now(UTC).isoformat()
    return report
