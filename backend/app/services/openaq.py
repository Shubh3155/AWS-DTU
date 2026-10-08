from datetime import UTC, datetime
from typing import Any

import httpx


def audit_locations(
    client: httpx.Client, lat: float, lng: float, radius: int, max_pages: int = 5
) -> dict[str, Any]:
    """Inspect stationary PM2.5 monitors; this does not select or validate a pilot."""
    fetched_at = datetime.now(UTC)
    locations: list[dict[str, Any]] = []
    capped = False
    for page in range(1, max_pages + 1):
        response = client.get(
            "/v3/locations",
            params={
                "coordinates": f"{lat:.4f},{lng:.4f}",
                "radius": radius,
                "parameters_id": 2,
                "mobile": "false",
                "monitor": "true",
                "limit": 100,
                "page": page,
            },
        )
        response.raise_for_status()
        results = response.json()["results"]
        locations.extend(results)
        if len(results) < 100:
            break
        if page == max_pages:
            capped = True

    stations = []
    for location in locations:
        sensors = {
            sensor["id"]: sensor
            for sensor in location.get("sensors", [])
            if sensor.get("parameter", {}).get("name") == "pm25"
        }
        latest = client.get(f"/v3/locations/{location['id']}/latest")
        latest.raise_for_status()
        measurements = []
        for reading in latest.json()["results"]:
            sensor = sensors.get(reading.get("sensorsId"))
            if sensor is None:
                continue
            observed_at = reading.get("datetime", {}).get("utc")
            age_hours = None
            if observed_at:
                try:
                    observed = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
                    if observed.tzinfo is not None:
                        age_hours = (fetched_at - observed).total_seconds() / 3600
                except ValueError:
                    pass
            measurements.append(
                {
                    "sensor_id": sensor["id"],
                    "value": reading.get("value"),
                    "unit": sensor["parameter"].get("units"),
                    "observed_at": observed_at,
                    "observation_age_hours": age_hours,
                }
            )
        stations.append(
            {
                "station_id": location["id"],
                "name": location.get("name"),
                "coordinates": location.get("coordinates"),
                "provider": location.get("provider"),
                "licenses": location.get("licenses"),
                "measurements": measurements,
            }
        )
    return {
        "source": "OpenAQ v3",
        "fetched_at": fetched_at.isoformat(),
        "search": {"lat": lat, "lng": lng, "radius_metres": radius},
        "pagination_capped": capped,
        "station_count": len(stations),
        "stations": stations,
        "limitations": [
            "Search coordinates are not an approved pilot boundary.",
            "Latest readings do not establish complete historical coverage.",
            "Units, freshness and spatial support must be reviewed before interpolation.",
        ],
    }
