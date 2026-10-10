"""Score evaluated walking candidates with explicit live/replay data semantics."""

from datetime import UTC, datetime

from app.model.baseline import BaselinePolicy, score_route, usable_observations
from app.schemas.routes import ComparisonRequest, ComparisonResponse, DataQuality, RouteCandidate
from app.services.snapshots import PollutionSnapshot
from app.services.walking import WalkingRoute


def compare_routes(
    routes: list[WalkingRoute],
    request: ComparisonRequest,
    snapshot: PollutionSnapshot | None,
    policy: BaselinePolicy,
    warnings: list[str] | None = None,
    now: datetime | None = None,
) -> ComparisonResponse:
    notes = list(warnings or [])
    if request.mode == "driving":
        notes.append(
            "Car scores estimate outdoor ambient exposure along the route, not cabin air or "
            "inhaled dose. Driving times do not include live traffic."
        )
    elif request.mode == "motorcycle":
        notes.append(
            "Motorcycle uses Mapbox car routing and car travel-time estimates; motorcycle "
            "access restrictions and speeds are not modeled. Driving times do not include "
            "live traffic."
        )
        notes.append("Scores estimate outdoor ambient exposure along the route, not inhaled dose.")
    quality = DataQuality(data_mode="unavailable")
    observations = []
    if snapshot is not None:
        if snapshot.data_mode != request.data_mode:
            notes.append(
                "Snapshot mode does not match the requested data mode; scoring is withheld."
            )
        else:
            reference = (
                snapshot.observed_to if request.data_mode == "replay" else now or datetime.now(UTC)
            )
            observations = usable_observations(snapshot.observations, reference, policy)
            quality = DataQuality(
                data_mode=snapshot.data_mode,
                snapshot_id=snapshot.snapshot_id,
                reference_time=reference,
                fetched_at=snapshot.fetched_at,
                observed_from=min((r.observed_at for r in observations), default=None),
                observed_to=max((r.observed_at for r in observations), default=None),
                source_ids=sorted({f"{r.provider_id}:sensor:{r.sensor_id}" for r in observations}),
                provider_ids=sorted({r.provider_id for r in observations}),
                station_count=len({(r.provider_id, r.station_id) for r in observations}),
                data_version=snapshot.data_version,
                model_version=policy.version,
                model_parameters=policy.model_dump(),
            )
            if request.data_mode == "replay":
                notes.append(
                    "Recorded-data replay: estimates use historical observations, not current air."
                )
            if len(observations) < len(snapshot.observations):
                notes.append(
                    "Older or duplicate station readings were excluded from the reference window."
                )
            notes.append(
                "Interpolation parameters and street-level estimates are not field-validated."
            )
    if any(route.via is not None for route in routes):
        notes.append(
            "Waypoint candidates are real walking routes requested through nearby points; "
            "they are not exhaustive alternatives or validated cleaner routes."
        )
    fastest = min(routes, key=lambda route: (route.duration, route.id)) if routes else None
    candidates = []
    for route in routes:
        score = score_route(route, observations, policy)
        notes.extend(score.warnings)
        candidates.append(
            RouteCandidate(
                id=route.id,
                geometry=route.geometry,
                distance_metres=route.distance,
                duration_seconds=route.duration,
                estimated_exposure=score.exposure,
                within_budget=route.duration <= fastest.duration + 60 * request.max_detour_minutes,
                coverage_percent=score.coverage_percent,
                via=route.via,
            )
        )
    eligible = [candidate for candidate in candidates if candidate.within_budget]
    lowest = None
    status = "limited_data"
    if not routes:
        status = "no_route"
        notes.append("No route was found for these locations.")
    elif eligible and all(candidate.estimated_exposure is not None for candidate in eligible):
        lowest = min(eligible, key=lambda c: (c.estimated_exposure, c.duration_seconds, c.id))
        if len(candidates) == 1:
            status = "single_candidate"
        elif lowest.id == fastest.id:
            status = "no_lower_exposure_candidate"
        else:
            status = "uncertain_difference"
            notes.append("A lower model estimate is not yet a reliable improvement recommendation.")
    else:
        notes.append("Comparable exposure is unavailable for one or more eligible candidates.")
    return ComparisonResponse(
        mode=request.mode,
        routing_profile="walking" if request.mode == "walking" else "driving",
        status=status,
        candidates=candidates,
        fastest_id=fastest.id if fastest else None,
        lowest_exposure_eligible_id=lowest.id if lowest else None,
        # Reduction claims require held-out validation and ranking sensitivity checks first.
        estimated_reduction_percent=None,
        warnings=list(dict.fromkeys(notes)),
        data_quality=quality,
    )
