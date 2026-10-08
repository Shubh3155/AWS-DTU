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

- [ ] Confirm real provider access and review the saved report.
- [ ] Count usable PM2.5 sensors and verify units, values and coordinates.
- [ ] Inspect observation ages and missingness; agree a freshness policy.
- [ ] Check spatial support for walking journeys and justify the pilot boundary.
- [ ] Query historical station-hour labels and record time ranges, missingness and independent stations available for evaluation.
- [ ] Save a genuine versioned snapshot with original times and source/license attribution.
- [ ] Confirm Mapbox walking access, alternatives and step timings.

Record findings here after checking them. Synthetic stations appear only in automated tests and are not pilot evidence.
