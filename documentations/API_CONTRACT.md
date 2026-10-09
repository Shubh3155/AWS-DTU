# API contract

Local API: `http://localhost:8000`. Interactive OpenAPI documentation: `/docs`. Machine-readable schema: `/openapi.json`.

## Implemented endpoints

`GET /health` returns process health without requiring provider credentials:

```json
{
  "status": "ok",
  "service": "aeroroute-api",
  "version": "0.1.0",
  "environment": "development"
}
```

This does not claim that monitoring data, routing, database or AWS access is verified.

`GET /api/pilot` returns the unselected pilot state:

```json
{
  "status": "pending_data_audit",
  "boundary": null,
  "supported_mode": "walking",
  "data_mode": "unavailable",
  "warning": "A Delhi pilot boundary will be selected after monitoring coverage is verified."
}
```

`POST /api/routes/compare` accepts this request shape. The coordinates below are illustrative inputs, not a verified pilot journey:

```json
{
  "origin": { "lat": 28.6139, "lng": 77.2090 },
  "destination": { "lat": 28.6200, "lng": 77.2200 },
  "max_detour_minutes": 5,
  "mode": "walking",
  "data_mode": "live"
}
```

Coordinates must be finite JSON numbers within latitude/longitude bounds. Extra time must be a finite non-negative number; booleans and numeric strings are rejected. Only walking is accepted. Unknown request fields are rejected.

`data_mode` accepts `live` (default) or `replay`. Optional `snapshot_id` selects an exact snapshot in that mode; otherwise the newest fetched matching snapshot is read. No matching snapshot or failed database access leaves scores unavailable; the API never silently switches modes. Replay measures historical observations relative to the snapshot's latest observation time, while live mode uses the current UTC time. Walking directions remain current in both modes.

With Mapbox configured, valid requests return **HTTP 200** with walking candidates and exact time-budget eligibility. Complete station support enables full exposure estimates. Missing/stale/partial support returns `limited_data` and null full scores where unsupported. No-route responses return `no_route` and an empty candidate list. See [EXPOSURE_BASELINE.md](EXPOSURE_BASELINE.md) for the prototype policy and [INGESTION.md](INGESTION.md) for historical data evidence.

If Mapbox is unconfigured, requests return **HTTP 503**:

```json
{
  "detail": {
    "code": "routing_unconfigured",
    "message": "Walking route access is not configured."
  }
}
```

Invalid requests return **HTTP 422** with FastAPI validation details. The frontend displays the pending message and does not substitute fabricated results.

## Comparison contract

`backend/app/schemas/routes.py` defines the response schema in OpenAPI:

- `status`: `uncertain_difference`, `no_lower_exposure_candidate`, `single_candidate`, `limited_data` or `no_route`. `comparison_available` is reserved for a validated future policy and is not emitted by this baseline.
- `candidates`: ID, GeoJSON LineString, `distance_metres`, `duration_seconds`, nullable `estimated_exposure`, `exposure_unit`, `within_budget` and `coverage_percent`.
- `fastest_id`, `lowest_exposure_eligible_id` and nullable `estimated_reduction_percent`.
- `warnings` and `data_quality`: data mode, snapshot ID, reference time, time-filtered observation range, fetch time, source/provider IDs, time-filtered station count, data/model versions and model parameters.

GeoJSON uses `[longitude, latitude]`; request objects use named `lat` and `lng` fields. Exposure uses `µg·min/m³`. API timestamps must include timezones. Missing exposure remains `null`.

`coverage_percent` is the percentage of route travel time with sufficient station support at sampled midpoints. It does not measure street-level accuracy. All eligible candidates require full scores before `lowest_exposure_eligible_id` is selected. A lower alternative model estimate returns `uncertain_difference`; `estimated_reduction_percent` is always `null` until validation and ranking sensitivity are implemented.

`backend/app/model/contracts.py` defines normalized station observations with location, provenance and timezone-aware timestamps. `backend/app/model/baseline.py` implements segmentation, time filtering, interpolation and exposure arithmetic. The frontend displays timestamps in IST and historical replay explicitly.

## Runtime cache

Successful comparison responses include `X-AeroRoute-Cache: hit`, `miss` or `bypass`.
`bypass` means no usable database snapshot was selected; it does not imply cached scoring.
The cache key includes exact coordinates, allowance, walking/data mode, actual snapshot and
data/model versions, five-minute time bucket and routing contract. TTL defaults to 120 seconds
and is configurable from 1–600 with `AEROROUTE_CACHE_TTL_SECONDS`. Equivalent explicit/default
selection of the same snapshot shares a key.

Cached walking routes retain step geometry/timing. Every hit recomputes exposure and quality
using the freshly loaded snapshot and current live time (or explicit historical replay
reference). Stored comparison JSON is diagnostic metadata and is never returned as a stale
score. Failed/expired/invalid cache entries fall back to the provider; writes occur after
the response and are optional. Real database hit/miss and latency measurements remain
pending. Use the journey checker in [DEPLOYMENT.md](DEPLOYMENT.md) to record them.
