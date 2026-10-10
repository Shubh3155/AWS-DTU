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

`GET /api/pilot` identifies the reviewed historical demo area. This does not
approve current-air coverage or street-level accuracy:

```json
{
  "status": "historical_demo",
  "name": "Central Delhi historical demo area",
  "boundary": {
    "type": "Polygon",
    "coordinates": [[[77.215,28.624],[77.243,28.624],[77.243,28.638],[77.215,28.638],[77.215,28.624]]]
  },
  "supported_mode": "walking",
  "data_mode": "replay",
  "warning": "Reviewed with October and November 2025 observations. Historical support does not establish street-level accuracy or current air quality; each route is checked separately."
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

## Bounded waypoint candidates

Route candidates may include optional `via: {lat, lng} | null`. A non-null value identifies a real Mapbox walking route requested through an intermediate point, rather than a native provider alternative. The page labels this provenance. Single-route results can trigger at most two bounded waypoint probes; failed probes retain the original route. All candidates use their actual step travel times and exact allowance checks. See [candidate policy and genuine demo evidence](MULTI_ROUTE_DEMO.md).

## Authenticated cloud navigation

Guest comparison requires no login. Each candidate now includes an opaque
`navigation_token` for alert-session creation/rerouting. It identifies a provider
route held in the backend's bounded cache for 30 minutes; it conveys no user
permissions. Missing/expired receipts require a fresh comparison. Active sessions
persist their provider route in Firestore.

All endpoints below require `Authorization: Bearer <Firebase ID token>`. The
Admin SDK verifies signature, expiry and revocation, and derives the UID. The
client retries a 401 once with a refreshed token. Unconfigured Admin access returns
503. Unexpected body fields, client-supplied UID or instruction text are rejected.

| Endpoint | Request body | Result |
| --- | --- | --- |
| `PUT /api/me/devices/{device_id}` | `{"recipient":"<FID>","recipient_kind":"fid"}` | 204; binds the recipient to one account/device and invalidates its previous binding |
| `DELETE /api/me/devices/{device_id}` | None | 204; idempotently disables the owned device and its journey |
| `POST /api/navigation/sessions` | `{"device_id":"<registered-id>","navigation_token":"<candidate-token>"}` | Journey ID, route version and UTC expiry |
| `POST /api/navigation/sessions/{journey_id}/progress` | Sequenced fix below | Acceptance, arrival and alert-submission status |
| `DELETE /api/navigation/sessions/{journey_id}` | None | 204; idempotently stops an owned session |

Device IDs use 10–128 ASCII letters/digits/underscores/hyphens. Route/session tokens
are 32 lowercase hex characters. The browser generates a UUID device ID for each
registration attempt. The backend also supports legacy recipients with
`recipient_kind: "token"`; the pinned browser integration uses FIDs.

Session creation response:

```json
{
  "journey_id": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "route_version": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "expires_at": "2026-10-10T12:00:30Z"
}
```

Progress request (illustrative position, not a verified journey):

```json
{
  "sequence": 1,
  "navigation_token": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "fix": {
    "lat": 28.6,
    "lng": 77.2003,
    "accuracy": 5.0,
    "timestamp": "2026-10-10T12:00:05Z"
  }
}
```

`sequence` must be a strictly increasing positive integer. Duplicate/out-of-order
updates return `accepted: false` without resending. Fresh fix timestamps must be
within 15 seconds of server time. Accepted progress extends the session by 30
seconds; updates are throttled to at most one per two seconds. The browser normally
sends every five seconds. Registration is throttled per UID and session starts per
device. Rate limits return 429.

A new valid `navigation_token` atomically replaces the route on reroute and clears
the old alert key. Ownership/binding mismatch, stopped or expired sessions cannot
send. Another user's unknown journey returns 404; a stale session returns 410.
An invalid registration or expired route receipt returns 409.

Response:

```json
{ "accepted": true, "alert": "sent", "arrived": false }
```

`alert` is `none`, `sent`, `failed` or `suppressed`. `sent` means FCM accepted
submission, not confirmed delivery. Transient submission failure leaves foreground
guidance working and permits a retry on a later fresh fix while the session remains
active. The backend derives instructions from provider maneuvers, accepts no client
instruction text, and sends only within 80 metres with reliable on-route progress.
Arrival deactivates the session after its final alert.

Push payloads contain journey/route IDs, sequence, provider instruction and
millisecond `issuedAt`/`expiresAt`. Messages and receiver validity expire in 15
seconds. Stop/reroute/logout clear locally active guidance; an inactive receiver
does not display delayed messages. See [Firebase setup](FIREBASE_SETUP.md) for
configuration, document access, emulator checks and browser limitations.
