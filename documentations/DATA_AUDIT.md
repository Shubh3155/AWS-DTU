# Data audit — live pilot verification pending

The newer [data credibility review](DATA_CREDIBILITY.md) supersedes the following
checkpoint: a historical demo boundary is reviewed, November validation is
complete, and the new live audit has one fresh station, insufficient for scores.

Genuine recorded observations have been retrieved. The latest Friday download contains 462 derived station-hour labels from ten Delhi locations for 6–7 October 2025 IST; radius/window and split prerequisites are reviewed in [HISTORICAL_COVERAGE.md](HISTORICAL_COVERAGE.md). It has no live support and is restricted to replay. Earlier Thursday findings are retained below. No live pilot boundary is approved; the map's Delhi viewport is an initial view.

From `backend/`, with its virtual environment active and `AEROROUTE_OPENAQ_API_KEY` configured in `.env`:

```bash
python -m scripts.audit_openaq --output data/openaq-audit-2026-10-08.json
```

The command searches stationary reference PM2.5 monitors and saves their latest readings and metadata. Use `--lat`, `--lng` and `--radius` for another search area; the default Delhi search radius is 25 km. Reports go in the ignored `backend/data/` folder; existing files are not overwritten.

Reports preserve provider/license metadata, sensor units, observation timestamps and fetch time, and flag pagination caps. Observation age does not establish that data is current. Missing credentials and failed requests produce an explicit failure without a report.

The CLI spaces requests by at least 1.1 seconds to stay below OpenAQ's documented
60 requests/minute limit for this process. Other users/processes sharing the key and the
hourly quota can still cause HTTP 429. On rate limiting it stops and prints numeric quota
headers when available; it does not retry automatically or save a partial success report.
Respect the reset window before trying again. [OpenAQ rate limits](https://docs.openaq.org/using-the-api/rate-limits).

The command uses [OpenAQ locations](https://docs.openaq.org/api/operations/locations_get_v3_locations_get), [latest readings](https://docs.openaq.org/resources/latest) and server-side [API-key authentication](https://docs.openaq.org/using-the-api/api-key). Latest readings alone do not establish complete historical coverage.

## Finish before selecting the pilot

### Walking access check

Configure `AEROROUTE_MAPBOX_TOKEN` in `backend/.env`, then run from `backend/`:

```bash
python -m scripts.audit_mapbox --origin 28.6139 77.2090 --destination 28.6200 77.2200 --output data/mapbox-audit-2026-10-08.json
```

These are illustrative Delhi coordinates, not an approved pilot journey. Inputs are latitude
then longitude; the provider request converts them to longitude then latitude. The command
requests walking alternatives, full GeoJSON and step timings and saves the genuine provider
response with fetch time. It never saves the request URL or token, and refuses to overwrite
an existing output. A no-route response is saved for inspection but exits unsuccessfully.
Missing credentials and failed HTTP requests produce no report.

Review candidate count, route geometry, leg/step durations and returned waypoint snapping.
One candidate is valid; alternatives are not guaranteed. This command does not score routes
or enable the comparison API. [Mapbox Directions reference](https://docs.mapbox.com/api/navigation/directions/).

### Access status

On 8 October 2026, keys were configured locally in the ignored backend environment. That environment is absent in the current Friday checkout. Historical findings:

- Mapbox returned one genuine walking candidate for the illustrative journey above:
  3,462.667 metres, 2,540.128 seconds, 167 geometry points and 38 steps.
  Step durations sum to 2,540.130 seconds (0.002 seconds of provider rounding).
  The local response is saved at `backend/data/mapbox-audit-2026-10-08.json`.
  This establishes routing access, not pollution support or an approved pilot.
- The OpenAQ audit encountered HTTP 429 (rate limiting) and saved no report.
  A second attempt also returned HTTP 429; request pacing and quota diagnostics were
  added afterward, and their live behavior remains unverified.
  Retry after the provider's quota window resets; do not infer station counts or
  freshness from this incomplete attempt. Monitoring coverage and pilot selection
  remain unverified.

Keys and local snapshots are ignored by Git. Synthetic automated tests verify request
behavior separately and provide no evidence about Delhi monitoring coverage.

- [ ] Confirm real provider access and review the saved report.
- [ ] Count usable PM2.5 sensors and verify units, values and coordinates.
- [ ] Inspect observation ages and missingness; agree a freshness policy.
- [ ] Check spatial support for walking journeys and justify the pilot boundary.
- [x] Query historical station-hour labels and record time ranges, missingness and geographically separate stations available for limited retrospective evaluation.
- [ ] Save a genuine versioned snapshot with original times and source/license attribution.
- [ ] Confirm Mapbox walking access, alternatives and step timings.

Record findings here after checking them. Synthetic stations appear only in automated tests and are not pilot evidence.

Friday follow-up: historical download/coverage checks are recorded in the linked review. Public station classification/provider metadata and target/time split capacity are reviewed; historical calibration/license details, fresh coverage, actual route support and evaluation metrics remain pending. Use `scripts.assess_coverage` for live/replay point support; a passing point/count check does not approve a pilot.

## Resumed audit — 8 October 2026

OpenAQ access succeeded. The genuine report contains 79 candidate stations and 118
valid PM2.5 readings from 77 stations. No latest reading was under 24 hours old at
fetch. Observation dates range from November 2016 to 7 October 2026; broad station
counts alone do not establish usable live coverage. The readings were ingested into
Supabase as explicit replay with original timestamps. No pilot boundary or freshness
policy is approved yet. See [INGESTION.md](INGESTION.md) for the manifest and commands.
