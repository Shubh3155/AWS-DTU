"""Project fresh GPS onto provider geometry; use provider maneuver instructions."""

import math


def wrap(degrees):
    return (degrees + 540) % 360 - 180


def distance(a, b):
    lat1, lat2 = math.radians(a[1]), math.radians(b[1])
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(math.radians(wrap(b[0] - a[0])) / 2) ** 2
    )
    return 12742000 * math.asin(min(1, math.sqrt(h)))


def project(points, position, previous=0):
    travelled, progress, nearest = 0, 0, math.inf
    scale = 111195 * math.cos(math.radians(position[1]))
    for a, b in zip(points, points[1:], strict=False):
        ax, ay = wrap(a[0] - position[0]) * scale, (a[1] - position[1]) * 111195
        dx, dy = wrap(b[0] - a[0]) * scale, (b[1] - a[1]) * 111195
        squared = dx * dx + dy * dy
        fraction = max(0, min(1, -(ax * dx + ay * dy) / squared)) if squared else 0
        offset = math.hypot(ax + fraction * dx, ay + fraction * dy)
        length = distance(a, b)
        candidate = travelled + fraction * length
        if offset < nearest - 3 or (
            abs(offset - nearest) <= 3 and abs(candidate - previous) < abs(progress - previous)
        ):
            nearest, progress = offset, candidate
        travelled += length
    return progress, travelled, nearest


def next_direction(route, fix, previous=0):
    points = route["geometry"]["coordinates"]
    position = (fix.lng, fix.lat)
    progress, total, offset = project(points, position, previous)
    if fix.accuracy > 60 or offset > max(40, fix.accuracy * 2):
        return None, previous, False
    arrived = fix.accuracy <= 30 and distance(position, points[-1]) <= 25 and total - progress <= 35
    if arrived:
        return ("arrival", "You have arrived at your destination"), progress, True
    for index, maneuver in enumerate(route.get("maneuvers", [])):
        at, _, _ = project(points, maneuver["location"], progress)
        remaining = at - progress
        if remaining > 12:
            if remaining <= 80:
                instruction = (
                    "Destination ahead" if maneuver["type"] == "arrive" else maneuver["instruction"]
                )
                return (
                    (str(index), f"In {round(remaining / 10) * 10} m, {instruction}"),
                    progress,
                    False,
                )
            break
    return None, progress, False
