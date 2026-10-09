"""Conservative geometry heuristics for optional local walking alternatives.

These are path-shape checks, not guarantees of pedestrian access or safety.
"""

import math
from collections import defaultdict

from app.schemas.routes import LineString

CELL = 20.0
TOLERANCE = 12.0


def samples(geometry: LineString, reference: tuple[float, float]) -> list[tuple]:
    longitude, latitude = reference
    scale = 111195 * math.cos(math.radians(latitude))
    points = [
        ((lng - longitude) * scale, (lat - latitude) * 111195) for lng, lat in geometry.coordinates
    ]
    result = []
    travelled = 0.0
    for a, b in zip(points, points[1:], strict=False):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        if length == 0:
            continue
        count = math.ceil(length / CELL)
        if len(result) + count > 10000:
            raise ValueError("Geometry exceeds route-quality sampling limit")
        for index in range(count):
            fraction = (index + 0.5) / count
            result.append(
                (
                    a[0] + dx * fraction,
                    a[1] + dy * fraction,
                    dx / length,
                    dy / length,
                    length / count,
                    travelled + length * fraction,
                )
            )
        travelled += length
    return result


def neighbours(index, point):
    x, y = math.floor(point[0] / CELL), math.floor(point[1] / CELL)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for other in index.get((x + dx, y + dy), ()):
                if math.hypot(point[0] - other[0], point[1] - other[1]) <= TOLERANCE:
                    yield other


def spatial_index(points):
    index = defaultdict(list)
    for point in points:
        add_point(index, point)
    return index


def add_point(index, point):
    cell = index[(math.floor(point[0] / CELL), math.floor(point[1] / CELL))]
    if len(cell) >= 128:
        raise ValueError("Geometry is too dense for bounded quality checks")
    cell.append(point)


def retraced_metres(points) -> float:
    index = defaultdict(list)
    repeated = 0.0
    for point in points:
        if any(
            point[5] - other[5] > 40 and point[2] * other[2] + point[3] * other[3] < -0.9
            for other in neighbours(index, point)
        ):
            repeated += point[4]
        add_point(index, point)
    return repeated


def returns_in_same_direction(points) -> bool:
    index = defaultdict(list)
    for point in points:
        if any(
            point[5] - other[5] > 200 and point[2] * other[2] + point[3] * other[3] > 0.9
            for other in neighbours(index, point)
        ):
            return True
        add_point(index, point)
    return False


def shared_fraction(points, others) -> float:
    length = math.fsum(point[4] for point in points)
    if length == 0:
        return 0.0
    index = spatial_index(others)
    return (
        math.fsum(point[4] for point in points if next(neighbours(index, point), None) is not None)
        / length
    )


def assess_alternative(candidate, baseline, accepted) -> str | None:
    """Return a rejection reason; never modify provider geometry or step timing."""
    if candidate.duration > 1.8 * baseline.duration or candidate.distance > 1.8 * baseline.distance:
        return "excessive_detour"
    reference = baseline.geometry.coordinates[0]
    try:
        points = samples(candidate.geometry, reference)
        length = math.fsum(point[4] for point in points)
        if retraced_metres(points) > max(80, 0.05 * length):
            return "backtracking"
        if returns_in_same_direction(points):
            return "loop"
        for route in accepted:
            others = samples(route.geometry, reference)
            if shared_fraction(points, others) >= 0.9 and shared_fraction(others, points) >= 0.9:
                return "near_duplicate"
    except ValueError:
        return "sampling_limit"
    return None


def filter_candidates(routes):
    if not routes:
        return []
    baseline = min(routes, key=lambda route: (route.duration, route.id))
    accepted = [baseline]
    for route in routes:
        if route.id != baseline.id and assess_alternative(route, baseline, accepted) is None:
            accepted.append(route)
    return accepted[:3]
