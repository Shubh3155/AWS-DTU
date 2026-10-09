# Walking routes and OpenAQ ingestion

## Live walking API

Configure the ignored backend Mapbox token and start FastAPI. `/api/routes/compare` now
requests Mapbox walking alternatives, full GeoJSON geometry and step timings. It identifies
the fastest evaluated candidate by duration and applies the exact detour limit before any
display rounding. The frontend renders candidates and draws green eligible/brown ineligible
routes. Changing the journey clears old results and prevents a previous response from
replacing a newer one.

The comparison now reads one pollution snapshot and applies the provisional
[exposure baseline policy](EXPOSURE_BASELINE.md). Live mode is the default and rejects stale
readings. Explicit replay uses historical observations relative to the snapshot's observation
reference time. Missing or incomplete support returns `limited_data` with null full-route
exposure; missing values never become zero pollution.
A single provider candidate remains one candidate. `NoRoute`/`NoSegment` return `no_route`.
Missing configuration returns 503; provider rate limits return 503, timeouts 504, and other
provider failures or malformed geometry return 502. Errors omit credentials/provider URLs.
The frontend defaults to a same-origin proxy: set server-side `AEROROUTE_API_URL` to the
backend origin. Optional `NEXT_PUBLIC_API_URL` enables direct browser calls and requires
matching CORS. Configure these before the frontend build. Provider and database credentials
remain on the backend.

The API uses validated step geometry/durations for time-weighted scoring. It reads snapshots
with verified TLS in a read-only transaction. Runtime cache retains walking steps and
comparison metadata, but every hit re-scores current observation support. Exact journey,
allowance/mode, actual snapshot/data/model versions and five-minute bucket identify entries;
default TTL is 120 seconds. Cache failure falls back to genuine routing. Actual database
cache operations remain unverified without access.

## Obtain and ingest actual observations

From `backend/`:

```bash
python -m scripts.audit_openaq --output data/openaq-TIMESTAMP.json
python -m scripts.ingest_openaq --input data/openaq-TIMESTAMP.json --mode replay
python -m scripts.ingest_openaq --input data/openaq-TIMESTAMP.json --mode replay --apply
```

Choose `live` only deliberately; selecting it does not validate freshness or geographic
coverage. Old observations keep their original timestamps in either mode. The command
first validates locally; database writes require `--apply`. It accepts measured PM2.5 in
recognized microgram-per-cubic-metre spellings, stores normalized `µg/m³`, and retains the
source spelling, provider/license metadata, per-observation coordinates and available period,
coverage/aggregation/source-count metadata. Unknown units,
missing/negative/non-finite readings, invalid coordinates/timestamps and future observations
are excluded. A report with no usable readings is rejected. Conflicting readings for one
sensor/time reject the snapshot. Identical readings deduplicate.

A content hash identifies the report; explicit mode is part of snapshot identity. Station,
snapshot and observation writes commit together. Reingesting the same report/mode does not
change rows. Reports remain in ignored `backend/data`; do not commit provider keys or raw
reports. The manifest stores the report hash, source-file hashes, interval, search, caps,
limitations and rejected-row counts.
Snapshots are genuine inputs, not an approved pilot or evidence of exposure reduction.

## Verified 8 October 2026

- Live Mapbox API call: HTTP 200, one walking candidate, 2,540.1 seconds, `limited_data`.
- OpenAQ audit fetched at `2026-10-08T16:59:42.015591+00:00`: 79 candidate stations.
- 118 valid readings from 77 stations; every source unit was `µg/m³`.
- Observation range: `2016-11-09T16:30:00Z`–`2026-10-07T14:30:00Z`.
- No readings were younger than 24 hours at fetch time. This exploratory 24-hour check is
  not an approved scoring freshness threshold. Many stations have years-old latest values.
- Saved to Supabase as **replay**, snapshot
  `openaq-replay-46cd01cb63376650e653c334bf8824ae5b10007cdec0e993d8f21b2c0e9958ca`.
- A second ingestion reported the snapshot already exists and changed no rows.
- All 37 backend tests pass, including opt-in live schema and rollback ingestion tests.
- Frontend lint, TypeScript check and production build pass. The browser renders a
  genuine route (42.3 min, 3.46 km), clears old results when detour changes, and
  confirms backend health through the same-origin proxy. Exposure remains unavailable.

Friday update: segmentation, interpolation, exposure ranking, snapshot loading and caching
are implemented and fixture-tested. Historical archive labels were downloaded and their
coverage reviewed; see [HISTORICAL_COVERAGE.md](HISTORICAL_COVERAGE.md). Ingestion accepts
OpenAQ v3 audits/hourly reports and explicit replay-only archive-derived labels. Original
period/coverage/derivation metadata is retained. This checkout has no provider/database
credentials, so current database rows, actual cache operations and real-data route scoring
were not reverified. S3 publication tools and deployment instructions are ready; actual
upload/hosting remain pending. See [FRIDAY_HANDOFF.md](FRIDAY_HANDOFF.md).

References: [Mapbox Directions](https://docs.mapbox.com/api/navigation/directions/),
[OpenAQ latest](https://docs.openaq.org/resources/latest).
