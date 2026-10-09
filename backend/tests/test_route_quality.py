from app.schemas.routes import LineString
from app.services.route_quality import assess_alternative, filter_candidates
from app.services.walking import WalkingRoute, WalkingStep


def route(identity, points, duration=600.0, distance=1000.0):
    geometry = LineString(coordinates=[(77.2 + x / 97500, 28.6 + y / 111195) for x, y in points])
    return WalkingRoute(
        id=identity,
        geometry=geometry,
        duration=duration,
        distance=distance,
        steps=[WalkingStep(geometry=geometry, duration=duration, distance=distance)],
    )


def test_rejects_out_and_back_while_preserving_provider_geometry():
    direct = route("direct", [(0, 0), (1000, 0)])
    detour = route("detour", [(0, 0), (500, 0), (500, 200), (500, 0), (1000, 0)], 800.0, 1400.0)
    before = detour.model_dump()
    assert assess_alternative(detour, direct, [direct]) == "backtracking"
    assert detour.model_dump() == before
    assert filter_candidates([detour, direct]) == [direct]


def test_rejects_closed_loop_returning_to_same_direction():
    direct = route("direct", [(0, 0), (1000, 0)])
    loop = route(
        "loop",
        [(0, 0), (400, 0), (400, 120), (520, 120), (520, -120), (280, -120), (280, 0), (1000, 0)],
        900.0,
        1720.0,
    )
    assert assess_alternative(loop, direct, [direct]) == "loop"


def test_near_duplicate_geometry_ignores_vertex_density():
    direct = route("direct", [(0, 0), (1000, 0)])
    duplicate = route("duplicate", [(0, 0), (250, 3), (500, 3), (750, 3), (1000, 0)], 650.0)
    distinct = route("distinct", [(0, 0), (300, 0), (500, 200), (700, 0), (1000, 0)], 750.0)
    assert assess_alternative(duplicate, direct, [direct]) == "near_duplicate"
    assert assess_alternative(distinct, direct, [direct]) is None


def test_excessive_detour_and_fastest_baseline_preservation():
    fastest = route("fastest", [(0, 0), (1000, 0)])
    long = route("long", [(0, 0), (500, 600), (1000, 0)], 1200.0, 2000.0)
    assert assess_alternative(long, fastest, [fastest]) == "excessive_detour"
    assert filter_candidates([long, fastest]) == [fastest]
    # A necessary provider path is retained even when it itself doubles back.
    sole = route("sole", [(0, 0), (500, 0), (500, 200), (500, 0), (1000, 0)])
    assert filter_candidates([sole]) == [sole]


def test_short_turn_and_parallel_alternative_are_not_classified_as_backtracking():
    direct = route("direct", [(0, 0), (1000, 0)])
    short = route("short", [(0, 0), (500, 0), (500, 30), (500, 0), (1000, 0)], 650.0)
    parallel = route("parallel", [(0, 0), (100, 50), (900, 50), (1000, 0)], 650.0)
    assert assess_alternative(short, direct, [direct]) == "near_duplicate"
    assert assess_alternative(parallel, direct, [direct]) is None


def test_sampling_limit_preserves_fastest_instead_of_spending_unbounded_work():
    direct = route("direct", [(0, 0), (1000, 0)])
    oversized = route("oversized", [(0, 0), (500000, 0), (1000, 0)], 700.0)
    assert assess_alternative(oversized, direct, [direct]) == "sampling_limit"
    assert filter_candidates([oversized, direct]) == [direct]
