import httpx
from pydantic import SecretStr

from app.core.config import Settings
from app.services.openaq import audit_locations
from scripts import audit_openaq


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


def test_rate_limit_reports_quota_without_saving_report_or_leaking_key(
    monkeypatch, tmp_path, capsys
):
    output = tmp_path / "audit.json"
    monkeypatch.setattr("sys.argv", ["audit", "--output", str(output)])
    monkeypatch.setattr(
        audit_openaq, "get_settings", lambda: Settings(openaq_api_key=SecretStr("private-key"))
    )

    def limited(*args):
        response = httpx.Response(
            429,
            headers={"x-ratelimit-reset": "60", "x-ratelimit-remaining": "0"},
            request=httpx.Request("GET", "https://api.openaq.org/v3/locations"),
        )
        response.raise_for_status()

    monkeypatch.setattr(audit_openaq, "audit_locations", limited)
    assert audit_openaq.main() == 1
    messages = capsys.readouterr().out
    assert "HTTP 429" in messages
    assert "x-ratelimit-reset: 60" in messages
    assert "private-key" not in messages
    assert not output.exists()
