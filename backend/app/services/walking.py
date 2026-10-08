"""Mapbox walking candidates and preserved step timing for the later scorer."""

import hashlib
import json

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.routes import Coordinate, LineString


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


class RoutingError(Exception):
    def __init__(self, code: str, message: str, status: int = 502):
        self.code, self.message, self.status = code, message, status


def walking_routes(
    client: httpx.Client, token: str, origin: Coordinate, destination: Coordinate
) -> list[WalkingRoute]:
    try:
        response = client.get(
            f"/directions/v5/mapbox/walking/{origin.lng},{origin.lat};"
            f"{destination.lng},{destination.lat}",
            params={
                "access_token": token,
                "alternatives": "true",
                "steps": "true",
                "geometries": "geojson",
                "overview": "full",
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
