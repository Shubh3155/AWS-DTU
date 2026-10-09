# Friday exposure baseline — 9 October 2026

The next Friday implementation slice is complete: route segmentation, provisional station interpolation, cumulative exposure scoring, exact-budget ranking, read-only snapshot loading and frontend quality notices. These checks establish calculation and integration behavior using synthetic fixtures. They do not establish Delhi street-level accuracy or a successful real-data journey.

## Implemented behavior

1. Mapbox step durations are distributed over geometry by length, using midpoint samples no more than 100 metres apart. Total duration is preserved; disagreements exceeding one second or 0.1% of route duration withhold scoring. Positive-duration stationary steps contribute exposure; zero-duration steps contribute none. Step durations are seconds in the [Mapbox Directions API](https://docs.mapbox.com/api/navigation/directions/).
2. A read-only, verified-TLS database transaction selects one snapshot in the requested mode. Optional `snapshot_id` selects an exact snapshot; otherwise the newest fetched snapshot in that mode is used. Stored observation coordinates are used rather than mutable station coordinates. Lookup failures leave walking routes available. The container includes the public database CA certificate.
3. Live mode uses the current UTC time. Replay uses the selected snapshot's latest observation time and is explicitly historical. Fetching an old observation today never makes it fresh. OpenAQ's latest resource alone does not establish fresh or complete coverage; see [OpenAQ latest](https://docs.openaq.org/resources/latest).
4. Each station contributes its newest reading time within the window. Multiple sensors at that time share one spatial vote by averaging their values. A station with conflicting coordinates is excluded from interpolation. Distinct provider/station IDs are counted; colocation is not proof of independent validation.
5. Midpoint concentrations use inverse-distance squared weights with a one-metre distance floor. Exposure is `sum(PM2.5 in µg/m³ × segment seconds / 60)`, in **µg·min/m³**. This is a time-integrated ambient concentration model, not an inhaled dose measurement.
6. At least three distinct nearby stations must support every sample for a full-route exposure. Missing values remain `null`. `coverage_percent` reports supported travel time as a percentage; it does not report measured geographic accuracy. Partial support never produces an artificially low full-route score.
7. Eligibility uses unrounded seconds: `duration <= fastest_duration + 60 × max_detour_minutes`. All eligible routes need valid full scores before a lowest estimate is selected; unsupported routes outside the budget do not block that comparison. Ties favor shorter duration, then a stable ID.
8. A lower alternative estimate returns `uncertain_difference`. No percentage reduction is emitted until held-out validation and spatial ranking sensitivity checks are completed. `single_candidate`, `no_lower_exposure_candidate`, `limited_data` and `no_route` remain explicit states.

## Provisional policy

| Parameter | Default | Configuration |
| --- | --- | --- |
| Sampling interval | 100 metres | Versioned `BaselinePolicy` |
| Station search radius | 10,000 metres | `AEROROUTE_BASELINE_STATION_RADIUS_METRES`, 500–25,000 |
| Observation age window | 2 hours before reference | `AEROROUTE_BASELINE_MAX_AGE_HOURS`, 0.25–24 |
| Minimum spatial support | 3 distinct provider/station IDs | Versioned `BaselinePolicy` |
| Stations used per sample | Nearest 5 within radius | Versioned `BaselinePolicy` |
| Weight | `1 / max(distance_metres, 1)²` | Baseline implementation |

These parameters remain provisional after the [historical point/radius review](HISTORICAL_COVERAGE.md); actual route coverage and sensitivity testing remain open. Model IDs hash the policy (`idw-v1-…`); responses include parameters, snapshot/data version, observation range, fetch time, reference time, provider/sensor IDs and time-filtered station count. At most 10,000 observations and 10,000 route samples are accepted; larger inputs withhold scoring. Runtime caching retains steps and re-scores freshness on every hit; see [API_CONTRACT.md](API_CONTRACT.md).

## Run against stored data

Configure the ignored backend `AEROROUTE_MAPBOX_TOKEN` and `AEROROUTE_DATABASE_URL`; run both apps using the root README. Provider/database secrets stay on the backend. The UI defaults to live mode. Select **Use recorded pollution observations** to request the newest replay snapshot. The historical reference, original observation times and fetch time appear with the result.

For an exact reproducible replay, POST this shape to `/api/routes/compare` (coordinates are illustrative, not an approved pilot):

```json
{
  "origin": {"lat": 28.6139, "lng": 77.2090},
  "destination": {"lat": 28.6200, "lng": 77.2200},
  "max_detour_minutes": 5,
  "mode": "walking",
  "data_mode": "replay",
  "snapshot_id": "openaq-replay-46cd01cb63376650e653c334bf8824ae5b10007cdec0e993d8f21b2c0e9958ca"
}
```

Walking directions remain current in replay; only pollution observations are recorded. The previous snapshot contains observations of widely different ages. Only readings near its reference time survive the window, so replay may still produce `limited_data`.

## Verification and remaining Friday work

- Local backend checks: Ruff lint and formatting; **83 tests passed, 2 opt-in database tests skipped**. Tests cover exposure arithmetic, timing, support, freshness/replay, exact detour/ranking, snapshot reads, cache invalidation/TTL/re-scoring, hourly/archive conversion, provenance and deployment/S3 contracts. Cloud/provider tests use controlled responses.
- Synthetic arithmetic: 20 minutes at 80 gives 1,600; 25 minutes at 70 gives 1,750; 25 minutes at 50 gives 1,250 µg·min/m³. These are fixtures, not measured reductions.
- Frontend lint, TypeScript, production build and **10 desktop/mobile browser tests** pass. Browser tests use explicitly synthetic responses and screenshots were inspected. Hosted CI also checks the backend container build; Docker is unavailable locally.
- This checkout has no provider/database credentials configured. No current database rows, real-data exposure score, map rendering or deployed AWS endpoint were reverified in this work. The 8 October snapshot report remains historical evidence in [INGESTION.md](INGESTION.md).

Next tasks:

1. Review the surviving stations and their geographic spread, choose a pilot, and run a supported journey end to end with genuine observations. Keep live coverage open if no fresh observations qualify.
2. Evaluate held-out stations/time periods; test radius/window and spatially varying concentration perturbations. Record results before accepting any improvement claim.
3. Measure actual database cache hit/miss latency and freshness behavior with the repeatable journey checker; cache implementation/tests are complete.
4. Apply the prepared Amplify/Lightsail/S3 configuration and verify deployed health, genuine database reads and upload. Instructions are in [DEPLOYMENT.md](DEPLOYMENT.md).
5. Verify genuine map/provider/scored browser integration; scored/limited fixture states already pass at desktop/mobile widths.

See [FRIDAY_HANDOFF.md](FRIDAY_HANDOFF.md) for the current checklist percentage and external access requirements.
