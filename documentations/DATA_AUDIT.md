# Data audit — prepared, live verification pending

No Delhi station counts, freshness claims or pilot boundary have been established. No genuine monitoring snapshot has been fetched. The map's Delhi viewport is only an initial view.

From `backend/`, with its virtual environment active and `AEROROUTE_OPENAQ_API_KEY` configured in `.env`:

```bash
python -m scripts.audit_openaq --output data/openaq-audit-2026-10-08.json
```

The command searches stationary reference PM2.5 monitors and saves their latest readings and metadata. Use `--lat`, `--lng` and `--radius` for another search area; the default Delhi search radius is 25 km. Reports go in the ignored `backend/data/` folder; existing files are not overwritten.

Reports preserve provider/license metadata, sensor units, observation timestamps and fetch time, and flag pagination caps. Observation age does not establish that data is current. Missing credentials and failed requests produce an explicit failure without a report.

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

Keys are configured locally in the ignored backend environment. On 8 October 2026:

- Mapbox returned one genuine walking candidate for the illustrative journey above:
  3,462.667 metres, 2,540.128 seconds, 167 geometry points and 38 steps.
  Step durations sum to 2,540.130 seconds (0.002 seconds of provider rounding).
  The local response is saved at `backend/data/mapbox-audit-2026-10-08.json`.
  This establishes routing access, not pollution support or an approved pilot.
- The OpenAQ audit encountered HTTP 429 (rate limiting) and saved no report.
  Retry after the provider's quota window resets; do not infer station counts or
  freshness from this incomplete attempt. Monitoring coverage and pilot selection
  remain unverified.

Keys and local snapshots are ignored by Git. Synthetic automated tests verify request
behavior separately and provide no evidence about Delhi monitoring coverage.

- [ ] Confirm real provider access and review the saved report.
- [ ] Count usable PM2.5 sensors and verify units, values and coordinates.
- [ ] Inspect observation ages and missingness; agree a freshness policy.
- [ ] Check spatial support for walking journeys and justify the pilot boundary.
- [ ] Query historical station-hour labels and record time ranges, missingness and independent stations available for evaluation.
- [ ] Save a genuine versioned snapshot with original times and source/license attribution.
- [ ] Confirm Mapbox walking access, alternatives and step timings.

Record findings here after checking them. Synthetic stations appear only in automated tests and are not pilot evidence.
