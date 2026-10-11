"""Fetch current CAMS PM2.5 for the regions crossed by genuine provider routes.

Forecast grid samples are not monitoring stations. They have a separate scoring
path and never enter the station-interpolation model or the snapshot database.
"""

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from time import monotonic

import httpx

from app.core.runtime_cache import RuntimeCache
from app.model.baseline import BaselinePolicy, RouteScore, distance_metres, segment_route
from app.schemas.routes import Coordinate, DataQuality
from app.services.walking import WalkingRoute

API_URL = "https://air-quality-api.open-meteo.com"
QUERY_GRID_DEGREES = 0.02
MAX_LOCATIONS = 64
CACHE_TTL_SECONDS = 180
PROVIDER = "Open-Meteo / Copernicus CAMS Global"
MODEL_VERSION = "cams-global-current-route-v1"
ATTRIBUTION = "Air quality data: Open-Meteo and Copernicus Atmosphere Monitoring Service (CAMS)."
SOURCE_URL = "https://open-meteo.com/en/docs/air-quality-api"


class LiveAirQualityCache(RuntimeCache):
    """Coalesce concurrent cold regional reads so they do not exhaust provider quota."""

    def __init__(self, clock=monotonic):
        super().__init__(capacity=256, clock=clock)
        self.refresh_lock = Lock()


def region_key(point: Coordinate, grid_degrees: float = QUERY_GRID_DEGREES) -> tuple[float, float]:
    """Share nearby queries without pretending that the 45 km field is street-level data."""
    return (
        max(-90.0, min(90.0, round(round(point.lat / grid_degrees) * grid_degrees, 4))),
        max(-180.0, min(180.0, round(round(point.lng / grid_degrees) * grid_degrees, 4))),
    )


@dataclass(frozen=True)
class AirQualitySample:
    concentration: float
    valid_at: datetime
    valid_to: datetime
    fetched_at: datetime
    grid_location: Coordinate

    def supports(self, reference: datetime) -> bool:
        return self.valid_at <= reference < self.valid_to


@dataclass(frozen=True)
class LiveAirQuality:
    samples: dict[tuple[float, float], AirQualitySample]
    query_grid_degrees: float = QUERY_GRID_DEGREES

    def quality(self, reference: datetime, policy: BaselinePolicy) -> DataQuality:
        usable = {key: sample for key, sample in self.samples.items() if sample.supports(reference)}
        if not usable:
            return DataQuality(data_mode="unavailable")
        version = hashlib.sha256(
            json.dumps(
                [
                    (key, sample.concentration, sample.valid_at.isoformat())
                    for key, sample in sorted(usable.items())
                ],
                allow_nan=False,
            ).encode()
        ).hexdigest()
        return DataQuality(
            data_mode="live",
            source_type="model_forecast",
            reference_time=reference,
            fetched_at=min(sample.fetched_at for sample in usable.values()),
            valid_from=min(sample.valid_at for sample in usable.values()),
            valid_to=max(sample.valid_to for sample in usable.values()),
            provider_ids=[PROVIDER],
            source_ids=sorted(
                {
                    f"cams-global:grid:{sample.grid_location.lat}:{sample.grid_location.lng}"
                    for sample in usable.values()
                }
            ),
            sample_count=len(usable),
            spatial_resolution_km=45,
            data_version="cams-current-" + version,
            model_version=MODEL_VERSION,
            model_parameters={
                "sampling_interval_metres": policy.sampling_interval_metres,
                "query_grid_degrees": self.query_grid_degrees,
            },
            attribution=ATTRIBUTION,
            source_url=SOURCE_URL,
        )

    def score(self, route: WalkingRoute, policy: BaselinePolicy, reference: datetime) -> RouteScore:
        try:
            segments = segment_route(route, policy)
        except (ValueError, OverflowError) as error:
            return RouteScore(warnings=[str(error)])
        supported_seconds = 0.0
        terms = []
        for segment in segments:
            sample = self.samples.get(region_key(segment.location, self.query_grid_degrees))
            if sample is not None and sample.supports(reference):
                supported_seconds += segment.duration_seconds
                terms.append(sample.concentration * segment.duration_seconds / 60)
        coverage = min(100.0, 100 * supported_seconds / route.duration)
        if len(terms) != len(segments):
            return RouteScore(
                coverage_percent=coverage,
                warnings=[
                    "Current air-quality forecasts do not support the entire route; "
                    "full-route exposure is unavailable."
                ],
            )
        try:
            exposure = math.fsum(terms)
        except OverflowError:
            exposure = float("inf")
        if not math.isfinite(exposure):
            return RouteScore(
                warnings=["Exposure calculation is outside the supported numeric range."]
            )
        return RouteScore(exposure=exposure, coverage_percent=100)


def parse_sample(payload: dict, key: tuple[float, float], fetched_at: datetime) -> AirQualitySample:
    if not isinstance(payload, dict):
        raise ValueError("Invalid forecast response")
    if payload.get("utc_offset_seconds") != 0:
        raise ValueError("The provider response must use UTC")
    if payload["current_units"]["pm2_5"] not in {"μg/m³", "µg/m³", "ug/m3"}:
        raise ValueError("Unsupported PM2.5 unit")
    current = payload["current"]
    value, timestamp, interval = current["pm2_5"], current["time"], current["interval"]
    for number in (value, timestamp, interval, payload["latitude"], payload["longitude"]):
        if type(number) not in (int, float) or not math.isfinite(number):
            raise ValueError("Missing or invalid forecast value")
    if value < 0 or not 0 < interval <= 3600:
        raise ValueError("Invalid PM2.5 value or current interval")
    grid = Coordinate(lat=payload["latitude"], lng=payload["longitude"])
    if distance_metres(Coordinate(lat=key[0], lng=key[1]), grid) > 50000:
        raise ValueError("Provider grid is too far from the requested region")
    valid_at = datetime.fromtimestamp(timestamp, UTC)
    sample = AirQualitySample(
        concentration=float(value),
        valid_at=valid_at,
        valid_to=valid_at + timedelta(seconds=interval),
        fetched_at=fetched_at,
        grid_location=grid,
    )
    if not sample.supports(fetched_at):
        raise ValueError("Forecast does not cover the current time")
    return sample


def fetch_live_air_quality(
    routes: list[WalkingRoute],
    policy: BaselinePolicy,
    cache: RuntimeCache,
    reference: datetime,
    client: httpx.Client | None = None,
) -> tuple[LiveAirQuality, list[str]]:
    if isinstance(cache, LiveAirQualityCache):
        started = monotonic()
        with cache.refresh_lock:
            refreshed_reference = reference + timedelta(seconds=monotonic() - started)
            return _fetch_live_air_quality(routes, policy, cache, refreshed_reference, client)
    return _fetch_live_air_quality(routes, policy, cache, reference, client)


def _fetch_live_air_quality(
    routes: list[WalkingRoute],
    policy: BaselinePolicy,
    cache: RuntimeCache,
    reference: datetime,
    client: httpx.Client | None,
) -> tuple[LiveAirQuality, list[str]]:
    locations = []
    warnings = []
    for route in routes:
        try:
            locations.extend(segment.location for segment in segment_route(route, policy))
        except (ValueError, OverflowError) as error:
            warnings.append(str(error))
    grid_degrees = QUERY_GRID_DEGREES
    keys = {region_key(point, grid_degrees) for point in locations}
    while len(keys) > MAX_LOCATIONS and grid_degrees < 0.4:
        # Coarsen bounded queries on long journeys, up to the provider's 0.4-degree grid.
        grid_degrees = min(0.4, grid_degrees * 2)
        keys = {region_key(point, grid_degrees) for point in locations}
    ordered = sorted(keys)
    if len(ordered) > MAX_LOCATIONS:
        ordered = [
            ordered[round(i * (len(ordered) - 1) / (MAX_LOCATIONS - 1))]
            for i in range(MAX_LOCATIONS)
        ]
        warnings.append(
            "The route-region query limit was reached; unsampled regions remain unsupported."
        )
    samples = {}
    missing = []
    unavailable = 0
    for key in ordered:
        cached = cache.get(key)
        if isinstance(cached, AirQualitySample) and cached.supports(reference):
            samples[key] = cached
        elif cached is False:
            unavailable += 1
        else:
            missing.append(key)
    if unavailable:
        warnings.append(
            f"Current air-quality data remains unavailable for {unavailable} route regions."
        )
    if not missing:
        return LiveAirQuality(samples, grid_degrees), warnings
    failure = cache.get("provider-failure")
    if failure is not None:
        return LiveAirQuality(samples, grid_degrees), warnings + [failure]
    owned_client = client is None
    if client is None:
        client = httpx.Client(base_url=API_URL, timeout=6)
    try:
        started = monotonic()
        response = client.get(
            "/v1/air-quality",
            params={
                "latitude": ",".join(str(key[0]) for key in missing),
                "longitude": ",".join(str(key[1]) for key in missing),
                "current": "pm2_5",
                "domains": "cams_global",
                "timezone": "UTC",
                "timeformat": "unixtime",
                "forecast_days": 1,
            },
        )
        response.raise_for_status()
        fetched_at = reference + timedelta(seconds=monotonic() - started)
        payload = response.json()
        payloads = payload if isinstance(payload, list) else [payload]
        if len(payloads) != len(missing):
            raise ValueError("Wrong number of forecast locations")
        rejected = 0
        for key, item in zip(missing, payloads, strict=True):
            try:
                sample = parse_sample(item, key, fetched_at)
            except (ValueError, KeyError, TypeError, OverflowError, OSError):
                rejected += 1
                cache.put(key, False, ttl=15)
                continue
            samples[key] = sample
            ttl = min(CACHE_TTL_SECONDS, (sample.valid_to - fetched_at).total_seconds())
            cache.put(key, sample, ttl=ttl)
        if rejected:
            warnings.append(
                f"Current air-quality data was missing, stale, or invalid "
                f"for {rejected} route regions."
            )
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
        limited = isinstance(error, httpx.HTTPStatusError) and error.response.status_code == 429
        warning = (
            "The live air-quality provider is rate limited; retry shortly."
            if limited
            else "The live air-quality API could not be read; "
            "routes remain available without unsupported scores."
        )
        cache.put("provider-failure", warning, ttl=60 if limited else 15)
        warnings.append(warning)
    finally:
        if owned_client:
            client.close()
    return LiveAirQuality(samples, grid_degrees), warnings
