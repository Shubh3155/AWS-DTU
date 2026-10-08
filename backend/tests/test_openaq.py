import httpx

from app.services.openaq import audit_locations


def test_audit_filters_other_pollutants_and_preserves_observation_time():
    def respond(request):
        assert request.headers["X-API-Key"] == "test-key"
        if request.url.path == "/v3/locations":
            assert request.url.params["parameters_id"] == "2"
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": 1,
                            "name": "Synthetic test station",
                            "coordinates": {"latitude": 28.6},
                            "provider": {"id": 3},
                            "sensors": [
                                {"id": 10, "parameter": {"name": "pm25", "units": "µg/m³"}},
                                {"id": 11, "parameter": {"name": "no2", "units": "ppm"}},
                            ],
                        }
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "results": [
                    {"sensorsId": 10, "value": 80, "datetime": {"utc": "2026-01-01T10:00:00Z"}},
                    {"sensorsId": 11, "value": 1, "datetime": {"utc": "2026-01-01T10:00:00Z"}},
                ]
            },
        )

    with httpx.Client(
        base_url="https://api.openaq.org",
        headers={"X-API-Key": "test-key"},
        transport=httpx.MockTransport(respond),
    ) as client:
        report = audit_locations(client, 28.6, 77.2, 1000)
    assert report["station_count"] == 1
    assert report["pagination_capped"] is False
    readings = report["stations"][0]["measurements"]
    assert len(readings) == 1
    assert readings[0]["observed_at"] == "2026-01-01T10:00:00Z"
    assert readings[0]["unit"] == "µg/m³"
    assert readings[0]["observation_age_hours"] is not None
