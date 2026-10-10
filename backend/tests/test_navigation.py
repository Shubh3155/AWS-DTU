import httpx
from test_comparison import NOW, request, snapshot, stations
from test_walking import route

from app.model.baseline import BaselinePolicy
from app.schemas.routes import Coordinate
from app.services.comparison import compare_routes
from app.services.walking import walking_routes


def test_provider_maneuver_survives_parsing_cache_and_comparison_without_invented_turns():
    raw = route(600.0)
    maneuver = {
        "instruction": "Turn left onto Example Street",
        "type": "turn",
        "modifier": "left",
        "location": [77.2, 28.6],
        "bearing_after": 90,
    }
    raw["legs"][0]["steps"][0]["maneuver"] = maneuver
    with httpx.Client(
        base_url="https://api.mapbox.com",
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json={"code": "Ok", "routes": [raw]})
        ),
    ) as client:
        routes = walking_routes(
            client, "private", Coordinate(lat=28.6, lng=77.2), Coordinate(lat=28.61, lng=77.21)
        )
    restored = type(routes[0]).model_validate(routes[0].model_dump())
    result = compare_routes([restored], request(), snapshot(stations()), BaselinePolicy(), now=NOW)
    turn = result.candidates[0].maneuvers[0]
    assert turn.instruction == maneuver["instruction"]
    assert turn.location == (77.2, 28.6)
    assert turn.modifier == "left"
    assert restored.duration == 600
