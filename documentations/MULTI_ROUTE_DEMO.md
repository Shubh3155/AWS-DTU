# Step 1: genuine walking-route comparison

On 9 October 2026, eighteen exploratory central Delhi journeys returned only one Mapbox walking candidate each despite requesting alternatives. Six subsequent waypoint experiments produced distinct real walking paths with recorded pollution support. These are discovery cases, not an approved pilot or a representative sample of all journeys.

The API now retains native provider alternatives when available. When there is one direct route, it probes at most two nearby intermediate points, perpendicular to the origin/destination midpoint. Offset is the smaller of 400 metres or a quarter of endpoint separation. Probes are limited to 0.5–10 km endpoint separation and excluded near poles/dateline. Each candidate comes from Mapbox's walking network with actual geometry and step durations; we do not draw fabricated paths or reuse driving routes.

Requested waypoint snapping is bounded to 100 metres, endpoints to 50 metres. Duplicate geometry is discarded. Optional probe failures retain the direct route and stop further probing. At most three candidates reach the scorer. Waypoint-generated candidates retain `via` metadata and are labelled in the page. These candidates are not exhaustive, necessarily sensible detours, or validated cleaner routes; the model only compares the retrieved set. This provisional candidate policy needs route-quality review and sensitivity checks. Cache contract was bumped to invalidate older route sets.

## Verified demo

Origin: **28.6315, 77.2167**. Destination: **28.6280, 77.2410**. Select **Use recorded pollution observations**. The replay uses genuine station observations from October 2025; walking directions are current.

| Candidate | Walking time | Historical estimated exposure µg·min/m³ | Support | Eligible with +5 min |
| --- | ---: | ---: | ---: | --- |
| Direct provider route | 37.48 min | 1351.77 | 100% | Yes |
| Waypoint candidate 2 | 40.53 min | 1449.00 | 100% | Yes |
| Waypoint candidate 3 | 50.85 min | 1832.94 | 100% | No |

At +0 minutes, only the fastest candidate is eligible. At +5, the second becomes eligible. At +15, all three are eligible. The fastest remains the lowest model estimate in each case: **extra walking does not produce a modeled exposure benefit here**. The API checked exact second-level eligibility; displayed times are rounded. [Machine-readable evidence](MULTI_ROUTE_EVIDENCE.json) preserves requests, versions, snapshot identity and results without route geometry.

This proves genuine multi-candidate scoring and allowance enforcement. It does not demonstrate a reliable lower-exposure detour, measured exposure reduction, or current air quality. No reduction percentage is displayed. A positive case remains to be found and evaluated without choosing settings solely to make it look beneficial.

## Verification and next step

- Backend: 90 tests pass; two optional database tests skip. Ruff passes.
- Frontend: lint, type checking and production build pass. Browser fixtures verify the waypoint label on desktop/mobile; hosted CI runs Chromium because local launch is sandbox-blocked.
- Genuine API: three supported candidates at 0, 5 and 15 minute allowances.
- Genuine in-app browser: map, three cards, waypoint provenance, eligibility and replay timestamps verified at +5 minutes.

Next: inspect candidate path quality and vary radius, freshness window and sampling interval. Report ranking stability and unsupported cases before making cleaner-route claims. Two additional provider requests can increase cold-request latency; the AWS deployment and response-time target remain open.
