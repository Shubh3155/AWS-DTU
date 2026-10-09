import httpx
from fastapi import APIRouter, HTTPException, Request

from app.model.baseline import BaselinePolicy
from app.schemas.routes import ComparisonRequest, ComparisonResponse, PilotResponse
from app.services.comparison import compare_routes
from app.services.snapshots import load_snapshot
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
    settings = http_request.app.state.settings
    snapshot, warnings = (
        load_snapshot(settings, request.data_mode, request.snapshot_id) if routes else (None, [])
    )
    return compare_routes(
        routes,
        request,
        snapshot,
        BaselinePolicy(
            station_radius_metres=settings.baseline_station_radius_metres,
            max_age_hours=settings.baseline_max_age_hours,
        ),
        warnings=warnings,
    )
