from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response

from app.model.baseline import BaselinePolicy
from app.schemas.routes import ComparisonRequest, ComparisonResponse, PilotResponse
from app.services.cache import read_routes, store_routes
from app.services.comparison import compare_routes
from app.services.snapshots import load_snapshot
from app.services.walking import RoutingError, walking_candidates

router = APIRouter(prefix="/api")


@router.get("/pilot", response_model=PilotResponse)
def pilot() -> PilotResponse:
    return PilotResponse()


@router.post("/routes/compare", response_model=ComparisonResponse)
def compare(
    request: ComparisonRequest,
    http_request: Request,
    http_response: Response,
    background_tasks: BackgroundTasks,
) -> ComparisonResponse:
    token = http_request.app.state.settings.mapbox_token
    if token is None:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "routing_unconfigured",
                "message": "Walking route access is not configured.",
            },
        )
    settings = http_request.app.state.settings
    now = datetime.now(UTC)
    snapshot, warnings = load_snapshot(settings, request.data_mode, request.snapshot_id)
    policy = BaselinePolicy(
        station_radius_metres=settings.baseline_station_radius_metres,
        max_age_hours=settings.baseline_max_age_hours,
    )
    routes = read_routes(settings, request, snapshot, policy, now) if snapshot else None
    hit = routes is not None
    if routes is None:
        try:
            with httpx.Client(base_url="https://api.mapbox.com", timeout=8) as client:
                routes = walking_candidates(
                    client, token.get_secret_value(), request.origin, request.destination
                )
        except RoutingError as error:
            raise HTTPException(
                status_code=error.status, detail={"code": error.code, "message": error.message}
            ) from None
    result = compare_routes(
        routes,
        request,
        snapshot,
        policy,
        warnings=warnings,
        now=datetime.now(UTC),
    )
    http_response.headers["X-AeroRoute-Cache"] = "hit" if hit else "miss" if snapshot else "bypass"
    if snapshot and not hit:
        background_tasks.add_task(
            store_routes, settings, request, snapshot, policy, routes, result, datetime.now(UTC)
        )
    return result
