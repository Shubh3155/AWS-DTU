import json

import httpx
import pytest

from app.schemas.routes import Coordinate
from scripts.audit_mapbox import audit_walking


def test_walking_request_order_options_and_snapshot():
    def handler(request):
        assert request.url.path.endswith("/77.209,28.6139;77.22,28.62")
        assert request.url.params["alternatives"] == "true"
        assert request.url.params["steps"] == "true"
        assert request.url.params["geometries"] == "geojson"
        assert request.url.params["overview"] == "full"
        return httpx.Response(200, json={"code": "Ok", "routes": [{"duration": 120}]})

    with httpx.Client(
        base_url="https://api.mapbox.com", transport=httpx.MockTransport(handler)
    ) as c:
        report = audit_walking(
            c,
            "private-token",
            Coordinate(lat=28.6139, lng=77.209),
            Coordinate(lat=28.62, lng=77.22),
        )
    assert report["candidate_count"] == 1
    assert report["response"]["routes"][0]["duration"] == 120
    assert "private-token" not in json.dumps(report)


@pytest.mark.parametrize("code", ["NoRoute", "NoSegment"])
def test_no_route_is_not_fabricated(code):
    with httpx.Client(
        base_url="https://api.mapbox.com",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"code": code})),
    ) as c:
        report = audit_walking(c, "key", Coordinate(lat=1, lng=2), Coordinate(lat=3, lng=4))
    assert report["candidate_count"] == 0


def test_auth_failure_raises_instead_of_saving_a_success():
    with (
        httpx.Client(
            base_url="https://api.mapbox.com",
            transport=httpx.MockTransport(lambda r: httpx.Response(401)),
        ) as c,
        pytest.raises(httpx.HTTPStatusError),
    ):
        audit_walking(c, "key", Coordinate(lat=1, lng=2), Coordinate(lat=3, lng=4))
