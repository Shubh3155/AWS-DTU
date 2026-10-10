from datetime import UTC, datetime
from uuid import uuid4

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response

from app.core.pilot import contains, polygon
from app.model.baseline import BaselinePolicy
from app.schemas.routes import ComparisonRequest, ComparisonResponse, PilotResponse
from app.services.cache import cache_identity, read_routes, route_cache_ttl, store_routes
from app.services.comparison import compare_routes
from app.services.snapshots import load_snapshot
from app.services.walking import RoutingError, vehicle_candidates, walking_candidates

router = APIRouter(prefix="/api")


@router.get("/pilot", response_model=PilotResponse)
def pilot() -> PilotResponse:
    return PilotResponse(boundary=polygon())


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
                "message": "Route access is not configured.",
            },
        )
    settings = http_request.app.state.settings
    pool = http_request.app.state.database_pool
    now = datetime.now(UTC)
    snapshot_cache = http_request.app.state.snapshot_cache
    snapshot_key = (request.data_mode, request.snapshot_id)
    loaded = snapshot_cache.get(snapshot_key)
    if loaded is None:
        loaded = load_snapshot(settings, request.data_mode, request.snapshot_id, pool)
        if loaded[0] is not None:
            snapshot_cache.put(snapshot_key, loaded, ttl=10)
    snapshot, warnings = loaded
    warnings = list(warnings)
    if not all(contains(point.lat, point.lng) for point in (request.origin, request.destination)):
        warnings.append("This journey is outside the reviewed historical demo area.")
    policy = BaselinePolicy(
        station_radius_metres=settings.baseline_station_radius_metres,
        max_age_hours=settings.baseline_max_age_hours,
    )
    route_cache = http_request.app.state.route_cache
    route_key = cache_identity(request, snapshot, policy, now)[0] if snapshot else None
    routes = route_cache.get(route_key) if route_key else None
    if routes is None and snapshot:
        routes = read_routes(settings, request, snapshot, policy, now, pool)
        if routes is not None:
            # Database hits get at most ten seconds in memory, not a renewed full TTL.
            route_cache.put(route_key, routes, ttl=min(10, settings.cache_ttl_seconds))
    hit = routes is not None
    if routes is None:
        try:
            with httpx.Client(base_url="https://api.mapbox.com", timeout=8) as client:
                if request.mode == "walking":
                    routes = walking_candidates(
                        client, token.get_secret_value(), request.origin, request.destination
                    )
                else:
                    routes = vehicle_candidates(
                        client,
                        token.get_secret_value(),
                        request.origin,
                        request.destination,
                        request.mode,
                    )
        except RoutingError as error:
            raise HTTPException(
                status_code=error.status, detail={"code": error.code, "message": error.message}
            ) from None
    if any(not contains(lat, lng) for route in routes for lng, lat in route.geometry.coordinates):
        warnings.append("One or more evaluated paths leave the reviewed historical demo area.")
    result = compare_routes(
        routes,
        request,
        snapshot,
        policy,
        warnings=warnings,
        now=datetime.now(UTC),
    )
    # Opaque, short-lived receipts bind navigation to actual provider output.
    # Active sessions persist their route in Firestore after this receipt is used.
    for candidate in result.candidates:
        receipt = uuid4().hex
        http_request.app.state.navigation_routes.put(
            receipt, {"route": candidate.model_dump(mode="json"), "mode": request.mode}, ttl=1800
        )
        candidate.navigation_token = receipt
    http_response.headers["X-AeroRoute-Cache"] = "hit" if hit else "miss" if snapshot else "bypass"
    if snapshot and not hit:
        route_cache.put(route_key, routes, ttl=route_cache_ttl(settings, request))
        background_tasks.add_task(
            store_routes,
            settings,
            request,
            snapshot,
            policy,
            routes,
            result,
            datetime.now(UTC),
            pool,
        )
    return result
