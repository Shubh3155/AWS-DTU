# Initial API contract

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
  "mode": "walking"
}
```

Coordinates must be finite JSON numbers within latitude/longitude bounds. Extra time must be a finite non-negative number; booleans and numeric strings are rejected. Only walking is accepted. Unknown request fields are rejected.

With Mapbox configured, valid requests now return **HTTP 200** with actual walking candidates, `limited_data`, exact time-budget eligibility, zero assessed pollution coverage and null exposure/recommendation. No-route responses return `no_route` and an empty candidate list. Pollution scoring remains pending. See [INGESTION.md](INGESTION.md).

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

## Next-step comparison contract

`backend/app/schemas/routes.py` defines the response schema in OpenAPI. Walking geometry/duration/eligibility are implemented; pollution scoring fields remain unavailable:

- `status`: comparison available, uncertain difference, no lower-exposure candidate, single candidate, limited data or no route.
- `candidates`: ID, GeoJSON LineString, `distance_metres`, `duration_seconds`, nullable `estimated_exposure`, `exposure_unit`, `within_budget` and `coverage_percent`.
- `fastest_id`, `lowest_exposure_eligible_id` and nullable `estimated_reduction_percent`.
- `warnings` and `data_quality`: data mode, observation/fetch times, source/provider IDs and data/model versions.

GeoJSON uses `[longitude, latitude]`; request objects use named `lat` and `lng` fields. Exposure uses `µg·min/m³`. API timestamps must include timezones. Missing exposure remains `null`.

`backend/app/model/contracts.py` defines normalized station observations with location, provenance and timezone-aware timestamps. Interpolation and route segmentation remain pending.
