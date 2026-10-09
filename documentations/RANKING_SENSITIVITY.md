# Step 2: retrospective route-selection sensitivity

The genuine three-candidate replay demonstration was checked against **27 policies**: station radius 5/10/15 km, maximum observation age 1/2/4 hours, and route sampling interval 50/100/200 metres. Minimum support remains three stations and the nearest-station cap remains five. Candidate geometry, step durations, time allowance and historical snapshot are held fixed. These exploratory settings were not chosen to manufacture a beneficial detour.

## Findings

| Radius | Supported policy checks | Unavailable | Selected route |
| --- | ---: | ---: | --- |
| 5 km | 0 of 9 | 9 | Withheld |
| 10 km | 9 of 9 | 0 | Fastest evaluated candidate |
| 15 km | 9 of 9 | 0 | Fastest evaluated candidate |

Across the supported policies, the selected candidate never changes. The result is **not stable across the complete tested grid**, because a smaller radius leaves insufficient station support. Missing rankings are not counted as agreements. At this snapshot's reference time, changing the age window does not change the available station set; this does not establish resilience to missing or differently timed observations.

Supported historical exposure ranges are 1351.58–1352.06, 1449.00–1449.28 and 1832.64–1832.94 µg·min/m³ for the three demo candidates respectively. The fastest remains the lowest estimate; this is not a positive cleaner-detour result.

Six earlier exploratory waypoint journeys were also evaluated on the same grid, giving 162 journey/policy checks. There are 108 supported selections, 54 unavailable selections and no selected-route changes among supported results. Each journey has the same support failure at 5 km. These exploratory cases are not independent field-validation journeys or an approved pilot.

[Machine-readable results](RANKING_SENSITIVITY_RESULTS.json) retain all 27 demo policy outcomes, candidate support/exposure, input hashes, policy versions and the six exploratory case summaries. The scorer and ingestion functions are reused rather than reimplemented.

## Large station-validation errors

The earlier station holdout report has later-block MAE 10.59 and RMSE 27.27 µg/m³. The five largest errors account for **87.64% of its squared error**. Two contemporaneous errors dominate: at 2025-10-07 11:45 UTC, held-out station 5610 has error −258.99 µg/m³ and station 5630 has error +212.55 µg/m³. This suggests strong local disagreement or problematic observations needing source/instrument inspection. It does not establish that either reading is invalid, so neither was removed or replaced. Their effect makes street-level claims particularly premature.

## Reproduce

From `backend/`, with the virtual environment active and the genuine archive report available, save a normalized journey file containing `request` and `routes`. `routes` must be the actual `WalkingRoute` objects returned by `walking_candidates`, including geometry, durations and step timings, not frontend-only candidates. Set request mode to replay and identify the corresponding snapshot. Hold this recorded route set fixed for every policy:

```bash
python -m scripts.check_sensitivity \
  --snapshot data/delhi-validation-20251006-07.json \
  --journey data/sensitivity-demo-journey.json \
  --output data/demo-ranking-sensitivity.json
```

The script refuses mismatched snapshot identities, live-mode input and existing output filenames. Provider responses and source readings remain ignored local data; teammates must record their own provider response to rerun, which may differ as routing data changes. The committed input hash identifies this experiment's original fixed route set.

Verification: 94 backend tests pass with two optional skips. Tests cover unavailable support, fixed-budget eligibility, actual selection reversal from older nearby donors, explicit replay mode and duplicate-policy rejection. Frontend lint/type checks/build pass; browser checks cover hovering, keyboard selection, tap-compatible buttons and reset after a new request.

## What this permits

The prototype can demonstrate allowance enforcement and report limited stability among supported settings. It cannot claim reliable lower exposure, measured health benefits, or comprehensive alternative-route search. Percentage reductions remain withheld. Next work is candidate path-quality review, source review of extreme readings, additional independent time periods, and a positive example evaluated without tuning to its desired outcome. AWS deployment and response-time work remain pending.
