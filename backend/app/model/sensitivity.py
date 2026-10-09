"""Compare fixed route candidates across provisional pollution-model policies."""

from app.model.baseline import BaselinePolicy
from app.schemas.routes import ComparisonRequest
from app.services.comparison import compare_routes
from app.services.snapshots import PollutionSnapshot
from app.services.walking import WalkingRoute


def assess_ranking(
    routes: list[WalkingRoute],
    request: ComparisonRequest,
    snapshot: PollutionSnapshot,
    policies: list[BaselinePolicy],
) -> dict:
    if not routes or len({r.id for r in routes}) != len(routes):
        raise ValueError("Provide nonempty routes with unique identities.")
    if snapshot.data_mode != "replay" or request.data_mode != "replay":
        raise ValueError("This retrospective experiment requires explicit replay mode.")
    if not policies or len({p.version for p in policies}) != len(policies):
        raise ValueError("Provide nonempty, distinct policies.")
    baseline = compare_routes(routes, request, snapshot, BaselinePolicy())
    baseline_id = baseline.lowest_exposure_eligible_id
    rows = []
    for policy in policies:
        result = compare_routes(routes, request, snapshot, policy)
        selected = result.lowest_exposure_eligible_id
        rows.append(
            {
                "policy": policy.model_dump(),
                "model_version": policy.version,
                "status": result.status,
                "selected_id": selected,
                "agrees_with_baseline": selected == baseline_id
                if selected and baseline_id
                else None,
                "candidates": [
                    candidate.model_dump(exclude={"geometry"}) for candidate in result.candidates
                ],
            }
        )
    available = [r for r in rows if r["selected_id"] is not None]
    changed = sum(r["agrees_with_baseline"] is False for r in rows)
    stable = bool(baseline_id) and len(available) == len(rows) and changed == 0
    return {
        "request": request.model_dump(),
        "snapshot_id": snapshot.snapshot_id,
        "reference_time": snapshot.observed_to.isoformat(),
        "candidate_ids": [r.id for r in routes],
        "baseline_selected_id": baseline_id,
        "summary": {
            "configurations": len(rows),
            "ranking_available": len(available),
            "ranking_unavailable": len(rows) - len(available),
            "selection_changes_from_baseline": changed,
            "stable_across_all_tested_policies": stable,
        },
        "limitations": [
            "Geometry, candidate set, step timing and historical snapshot are held fixed.",
            "A missing ranking is not counted as agreement.",
            "Policy stability does not validate pollution estimates or measured exposure benefits.",
            "This checks a finite policy grid, not all plausible settings or route candidates.",
        ],
        "results": rows,
    }
