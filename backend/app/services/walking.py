"""Mapbox walking candidates and preserved step timing for the later scorer."""

import hashlib
import json
import math

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.routes import Coordinate, LineString
from app.services.route_quality import assess_alternative, filter_candidates


class WalkingStep(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    geometry: LineString
    duration: float = Field(ge=0, strict=True)
    distance: float = Field(ge=0, strict=True)


class WalkingRoute(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    id: str
    geometry: LineString
    duration: float = Field(ge=0, strict=True)
    distance: float = Field(ge=0, strict=True)
    steps: list[WalkingStep]
    via: Coordinate | None = None


class RoutingError(Exception):
    def __init__(self, code: str, message: str, status: int = 502):
        self.code, self.message, self.status = code, message, status


def walking_routes(
    client: httpx.Client,
    token: str,
    origin: Coordinate,
    destination: Coordinate,
    via: Coordinate | None = None,
) -> list[WalkingRoute]:
    points = [origin, destination] if via is None else [origin, via, destination]
    coordinates = ";".join(f"{point.lng},{point.lat}" for point in points)
    try:
        response = client.get(
            f"/directions/v5/mapbox/walking/{coordinates}",
            params={
                "access_token": token,
                "alternatives": "true",
                "steps": "true",
                "geometries": "geojson",
                "overview": "full",
                **({"radiuses": "50;100;50"} if via is not None else {}),
            },
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") in ("NoRoute", "NoSegment"):
            return []
        if payload.get("code") != "Ok" or not payload.get("routes"):
            raise ValueError("Invalid route response")
        routes = []
        for raw in payload["routes"]:
            steps = [
                WalkingStep.model_validate(step) for leg in raw["legs"] for step in leg["steps"]
            ]
            if not steps:
                raise ValueError("Missing route steps")
            geometry = LineString.model_validate(raw["geometry"])
            identity = json.dumps(
                [geometry.model_dump(), raw["duration"], raw["distance"]],
                sort_keys=True,
                allow_nan=False,
            )
            routes.append(
                WalkingRoute(
                    id="mapbox-" + hashlib.sha256(identity.encode()).hexdigest()[:24],
                    geometry=geometry,
                    duration=raw["duration"],
                    distance=raw["distance"],
                    steps=steps,
                    via=via,
                )
            )
        return list({route.id: route for route in routes}.values())
    except httpx.HTTPStatusError as error:
        limited = error.response.status_code == 429
        raise RoutingError(
            "routing_rate_limited" if limited else "routing_provider_error",
            "Routing is temporarily unavailable. Try again later.",
            503 if limited else 502,
        ) from None
    except httpx.TimeoutException:
        raise RoutingError("routing_timeout", "Routing timed out. Try again.", 504) from None
    except (httpx.RequestError, ValueError, KeyError, TypeError, AttributeError):
        raise RoutingError(
            "routing_provider_error", "Routing returned no usable response."
        ) from None


def walking_candidates(
    client: httpx.Client, token: str, origin: Coordinate, destination: Coordinate
) -> list[WalkingRoute]:
    """Keep provider alternatives; probe at most two via points for a single route."""
    routes = walking_routes(client, token, origin, destination)
    if len(routes) != 1:
        return filter_candidates(routes)
    latitude = (origin.lat + destination.lat) / 2
    longitude_scale = 111195 * math.cos(math.radians(latitude))
    dy = (destination.lat - origin.lat) * 111195
    dx = (destination.lng - origin.lng) * longitude_scale
    length = math.hypot(dx, dy)
    # Keep this exploratory policy local and bounded; avoid polar/dateline arithmetic.
    if not 500 <= length <= 10000 or abs(latitude) > 75 or abs(destination.lng - origin.lng) > 180:
        return routes
    offset = min(400, length / 4)
    geometries = {json.dumps(routes[0].geometry.model_dump(), sort_keys=True)}
    for sign in (-1, 1):
        via = Coordinate(
            lat=latitude + sign * dx / length * offset / 111195,
            lng=(origin.lng + destination.lng) / 2 - sign * dy / length * offset / longitude_scale,
        )
        try:
            alternatives = walking_routes(client, token, origin, destination, via)
        except RoutingError:
            # Preserve the direct route and stop probing on throttling or provider failure.
            break
        for candidate in alternatives:
            geometry = json.dumps(candidate.geometry.model_dump(), sort_keys=True)
            if (
                geometry not in geometries
                and assess_alternative(candidate, routes[0], routes) is None
            ):
                geometries.add(geometry)
                routes.append(candidate)
                break
    return routes[:3]
