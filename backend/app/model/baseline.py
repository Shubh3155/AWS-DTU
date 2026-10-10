"""Time-weighted ambient exposure baseline; parameters are not field-validated."""

import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field

from app.model.contracts import ConcentrationEstimate, StationObservation
from app.schemas.routes import Coordinate
from app.services.walking import WalkingRoute


class BaselinePolicy(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)
    sampling_interval_metres: float = Field(default=100, gt=0)
    station_radius_metres: float = Field(default=10000, gt=0)
    max_age_hours: float = Field(default=2, gt=0)
    minimum_stations: int = Field(default=3, ge=2, le=5)
    nearest_stations: int = Field(default=5, ge=5)

    @property
    def version(self) -> str:
        digest = hashlib.sha256(json.dumps(self.model_dump(), sort_keys=True).encode()).hexdigest()
        return "idw-v1-" + digest[:16]


class TimedSegment(BaseModel):
    location: Coordinate
    duration_seconds: float = Field(gt=0)


class RouteScore(BaseModel):
    exposure: float | None = None
    coverage_percent: float = 0
    warnings: list[str] = Field(default_factory=list)


def distance_metres(a: Coordinate, b: Coordinate) -> float:
    lat_a, lat_b = math.radians(a.lat), math.radians(b.lat)
    dlat, dlng = lat_b - lat_a, math.radians(b.lng - a.lng)
    haversine = (
        math.sin(dlat / 2) ** 2 + math.cos(lat_a) * math.cos(lat_b) * math.sin(dlng / 2) ** 2
    )
    return 2 * 6371008.8 * math.asin(math.sqrt(min(1.0, max(0.0, haversine))))


def segment_route(route: WalkingRoute, policy: BaselinePolicy) -> list[TimedSegment]:
    total_steps = math.fsum(step.duration for step in route.steps)
    if route.duration <= 0 or total_steps <= 0:
        raise ValueError("No positive travel duration is available for exposure scoring.")
    if abs(total_steps - route.duration) > max(1.0, route.duration * 0.001):
        raise ValueError("Route and step times disagree; exposure scoring is withheld.")
    scale = route.duration / total_steps
    segments: list[TimedSegment] = []
    for step in route.steps:
        if step.duration == 0:
            continue
        points = [Coordinate(lng=lng, lat=lat) for lng, lat in step.geometry.coordinates]
        edges = [(a, b, distance_metres(a, b)) for a, b in zip(points, points[1:], strict=False)]
        length = math.fsum(edge[2] for edge in edges)
        if length == 0:
            # A stationary/waiting step still contributes travel time and ambient exposure.
            if len(segments) >= 10000:
                raise ValueError("Route exceeds the prototype's sampling limit.")
            segments.append(
                TimedSegment(location=points[0], duration_seconds=step.duration * scale)
            )
            continue
        for start, end, distance in edges:
            if distance == 0:
                continue
            count = max(1, math.ceil(distance / policy.sampling_interval_metres))
            if len(segments) + count > 10000:
                raise ValueError("Route exceeds the prototype's sampling limit.")
            duration = step.duration * scale * (distance / length) / count
            delta_lng = (end.lng - start.lng + 180) % 360 - 180
            for index in range(count):
                fraction = (index + 0.5) / count
                point = Coordinate(
                    lat=start.lat + (end.lat - start.lat) * fraction,
                    lng=(start.lng + delta_lng * fraction + 180) % 360 - 180,
                )
                segments.append(TimedSegment(location=point, duration_seconds=duration))
    # Correct only floating-point/provider rounding, after rejecting substantive mismatches.
    segments[-1].duration_seconds += route.duration - math.fsum(
        s.duration_seconds for s in segments
    )
    return segments


def usable_observations(
    observations: list[StationObservation], reference: datetime, policy: BaselinePolicy
) -> list[StationObservation]:
    if reference.tzinfo is None:
        raise ValueError("The observation reference must include a timezone.")
    earliest = reference - timedelta(hours=policy.max_age_hours)
    candidates: dict[tuple[str, int], list[StationObservation]] = defaultdict(list)
    for observation in observations:
        if earliest <= observation.observed_at <= reference:
            candidates[(observation.provider_id, observation.station_id)].append(observation)
    # Use each station's latest time. Multiple sensors at that time share one spatial vote.
    return [
        observation
        for readings in candidates.values()
        for observation in readings
        if observation.observed_at == max(reading.observed_at for reading in readings)
    ]


def nearby_stations(
    point: Coordinate, observations: list[StationObservation], policy: BaselinePolicy
) -> list:
    stations: dict[tuple[str, int], list[StationObservation]] = defaultdict(list)
    for observation in observations:
        stations[(observation.provider_id, observation.station_id)].append(observation)
    nearby = []
    for identity, readings in stations.items():
        if any(reading.location != readings[0].location for reading in readings):
            continue
        distance = distance_metres(point, readings[0].location)
        if distance <= policy.station_radius_metres:
            concentration = math.fsum(r.pm25_micrograms_per_m3 / len(readings) for r in readings)
            nearby.append((distance, identity, concentration, readings))
    nearby.sort(key=lambda station: (station[0], station[1]))
    return nearby[: policy.nearest_stations]


def interpolate(
    point: Coordinate, observations: list[StationObservation], policy: BaselinePolicy
) -> ConcentrationEstimate:
    nearby = nearby_stations(point, observations, policy)
    if len(nearby) < policy.minimum_stations:
        return ConcentrationEstimate(
            warnings=["Too few distinct nearby stations for interpolation."]
        )
    weights = [1 / max(station[0], 1.0) ** 2 for station in nearby]
    total_weight = math.fsum(weights)
    value = math.fsum(
        station[2] * (weight / total_weight)
        for station, weight in zip(nearby, weights, strict=True)
    )
    return ConcentrationEstimate(
        pm25_micrograms_per_m3=value,
        supporting_sensor_ids=sorted({r.sensor_id for station in nearby for r in station[3]}),
    )


def score_route(
    route: WalkingRoute, observations: list[StationObservation], policy: BaselinePolicy
) -> RouteScore:
    try:
        segments = segment_route(route, policy)
    except (ValueError, OverflowError) as error:
        return RouteScore(warnings=[str(error)])
    supported_seconds = 0.0
    exposure_terms = []
    for segment in segments:
        try:
            estimate = interpolate(segment.location, observations, policy)
        except (ValueError, OverflowError):
            return RouteScore(warnings=["Interpolation is outside the supported numeric range."])
        if estimate.pm25_micrograms_per_m3 is not None:
            supported_seconds += segment.duration_seconds
            exposure_terms.append(estimate.pm25_micrograms_per_m3 * segment.duration_seconds / 60)
    coverage = min(100.0, 100 * supported_seconds / route.duration)
    if len(exposure_terms) != len(segments):
        return RouteScore(
            coverage_percent=coverage,
            warnings=[
                "Incomplete time-weighted station support; full-route exposure is unavailable."
            ],
        )
    try:
        exposure = math.fsum(exposure_terms)
    except OverflowError:
        exposure = float("inf")
    if not math.isfinite(exposure):
        return RouteScore(warnings=["Exposure calculation is outside the supported numeric range."])
    return RouteScore(exposure=exposure, coverage_percent=100)
