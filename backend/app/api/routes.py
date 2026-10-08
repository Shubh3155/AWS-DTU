import httpx
from fastapi import APIRouter, HTTPException, Request

from app.schemas.routes import (
    ComparisonRequest,
    ComparisonResponse,
    DataQuality,
    PilotResponse,
    RouteCandidate,
)
from app.services.walking import RoutingError, walking_routes

router = APIRouter(prefix="/api")


@router.get("/pilot", response_model=PilotResponse)
def pilot() -> PilotResponse:
    return PilotResponse()


@router.post("/routes/compare", response_model=ComparisonResponse)
def compare(request: ComparisonRequest, http_request: Request) -> ComparisonResponse:
    token = http_request.app.state.settings.mapbox_token
    if token is None:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "routing_unconfigured",
                "message": "Walking route access is not configured.",
            },
        )
    try:
        with httpx.Client(base_url="https://api.mapbox.com", timeout=8) as client:
            routes = walking_routes(
                client, token.get_secret_value(), request.origin, request.destination
            )
    except RoutingError as error:
        raise HTTPException(
            status_code=error.status, detail={"code": error.code, "message": error.message}
        ) from None
    fastest = min(routes, key=lambda route: (route.duration, route.id)) if routes else None
    return ComparisonResponse(
        status="limited_data" if routes else "no_route",
        candidates=[
            RouteCandidate(
                id=route.id,
                geometry=route.geometry,
                distance_metres=route.distance,
                duration_seconds=route.duration,
                within_budget=route.duration <= fastest.duration + 60 * request.max_detour_minutes,
                coverage_percent=0,
            )
            for route in routes
        ],
        fastest_id=fastest.id if fastest else None,
        lowest_exposure_eligible_id=None,
        estimated_reduction_percent=None,
        warnings=[
            "Pollution coverage and scoring are pending; no exposure recommendation is available."
        ]
        if routes
        else ["No walking route was found for these locations."],
        data_quality=DataQuality(data_mode="unavailable"),
    )
