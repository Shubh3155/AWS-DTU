# Pollution data and historical demo review — 9 October 2026

## Separate-period evaluation

The existing fixed interpolation policy was evaluated on 465 additional derived
station-hour labels from the same ten locations on 6–7 November 2025 IST. The
earlier evaluation used 462 labels on 6–7 October. No radius, window or scoring
parameters were changed to improve the new result. Entire target stations remain
excluded from their own contemporaneous donor sets.

| Period/block | Targets | Supported | Coverage | MAE µg/m³ | RMSE µg/m³ |
| --- | ---: | ---: | ---: | ---: | ---: |
| October early | 231 | 181 | 78.35% | 10.57 | 14.70 |
| October later | 231 | 183 | 79.22% | 10.59 | 27.27 |
| November early | 230 | 180 | 78.26% | 55.67 | 83.45 |
| November later | 235 | 186 | 79.15% | 63.45 | 100.60 |

The later November errors are much larger. Its five largest errors account for
33.77% of squared error, compared with 87.64% in October; poor performance is not
explained by only the same single extreme hour. The model is not established as
reliable across pollution regimes. These are station holdouts, not measurements
along streets or validation of route exposure. Two short periods and one station
cohort remain a limited experiment. The frontend discloses this variability, lower
estimates remain uncertain, and percentage-reduction claims stay suppressed.

[Evaluation and source review results](DATA_REVIEW_RESULTS.json) retain split
metrics, per-station summaries, hashes and current-audit counts. Reproduction:

```bash
cd backend
python -m scripts.fetch_archive --locations 8118 11607 17 235 5610 5630 6960 50 8239 5627 --dates 2025-11-06 2025-11-07 2026-10-07 2026-10-08 --output data/new-periods.json
python -m scripts.validate_baseline --input data/new-periods.json --cutoff 2025-11-06T19:30:00+00:00 --output data/new-validation.json
```

The twenty November archive files returned HTTP 200. The twenty requested
7–8 October 2026 archive objects returned 404. This means those objects were
unavailable, not that no current readings exist elsewhere. Raw downloads and
per-target errors remain ignored local data. Source URLs/hashes are included in
the pilot evidence below.

## Extreme October reading review

Original gzip hashes match the earlier source audit. At 2025-10-07 11:45 UTC,
station 5610's derived hourly label averages four source readings. One 15-minute
sample is 889.7 µg/m³, contributing 79.23% of the hour's total; the hourly mean is
280.725. Station 5630 has four much steadier samples averaging 22.4 in the same
UTC hour. Both derived means match the original CSV. Correct conversion from the
CSV's IST timestamps is important: the spike occurs at 17:00 IST, not 11:00 IST.

This is consistent with the large opposing holdout errors when nearby stations
disagree. The source has no quality flags, calibration or instrument diagnostics
to establish that the spike is invalid. No observations were removed, replaced,
winsorized or re-aggregated to make the result look better. Confirming instrument
or source errors remains external work.

## Historical demo boundary

The demo area is **28.624–28.638° N, 77.215–77.243° E**, containing all three
central-east demonstration paths. This is a reviewed historical area, not an
approved live-air or street-level-accuracy pilot.

A fixed 11×11 grid was checked using the existing three-station minimum and 10 km,
two-hour policy at every actual recorded timestamp:

- October: all 121 points supported at 106 of 107 reference times.
- November: all 121 points supported at 101 of 102 reference times.
- Each dataset's first timestamp is unsupported; both final references have at
  least seven nearby stations throughout the grid.

Sampling does not guarantee coverage between grid points or at other dates.
Each requested route is still scored independently, including full-path support.
The API publishes a `historical_demo` polygon; endpoints or paths outside it get
a warning without fabricated support. The map opens on this area.

[Pilot evidence](PILOT_REVIEW_RESULTS.json) records bounds, source hashes,
unsupported references and grid summaries. Reproduce with:

```bash
python -m scripts.review_pilot --inputs data/delhi-validation-20251006-07.json data/new-periods.json --output data/new-pilot-review.json
```

## Current coverage and route benefit

A new authenticated audit queried 79 candidate locations and validated 118
observations from 77 stations. At review time, only one distinct station met the
two-hour freshness rule: location 8118, observed at 2026-10-09 14:30 UTC. That is
below the three-station requirement. The audit was ingested as an explicit live
snapshot, and a genuine API check returned three walking candidates, one usable
station and null exposure scores. Freshness changes with time; this is a dated
finding, not a permanent statement about station availability.

The six existing exploratory journeys were also scored against the new November
snapshot after path filtering, keeping their original allowances and fixed policy.
Five retain the fastest as the lowest eligible estimate; one has a sole candidate.
[Results](INDEPENDENT_ROUTE_REVIEW.json) show no positive cleaner-detour example.
The November snapshot remains offline evaluation data; the established October
replay is still the application's demonstration snapshot.

Remaining evidence gaps: sufficient fresh stations, source/instrument quality
confirmation, longer periods and different station cohorts, route-level field
measurements, and a robust positive detour case. AWS configuration is deferred.
