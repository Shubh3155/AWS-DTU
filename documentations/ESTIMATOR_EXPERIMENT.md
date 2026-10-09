# Fixed robust-estimator experiment

One challenger was defined before reading the December confirmation metrics:
the median concentration of the nearest usable distinct stations. It uses the
same 10 km radius, two-hour window, three-station minimum and five-station cap as
IDW. Duplicate sensors retain one station vote. Raw observations are preserved;
the median is an alternative estimate, not a declaration that extremes are invalid.

The adoption gate was lower MAE **and** RMSE, equal supported counts, in both
blocks of every tested period. October and November were already reviewed and
are development evidence. December was requested separately as confirmation.
No thresholds were retuned after seeing its results.

| Period/block | IDW MAE / RMSE | Median MAE / RMSE |
| --- | ---: | ---: |
| October early | 10.57 / 14.70 | 10.14 / 14.01 |
| October later | 10.59 / 27.27 | 7.57 / 21.22 |
| November early | 55.67 / 83.45 | 46.19 / 76.03 |
| November later | 63.45 / 100.60 | 53.96 / 89.82 |
| December early | 27.21 / 33.95 | 27.59 / 34.39 |
| December later | 25.71 / 34.23 | 24.10 / 32.38 |

Units are µg/m³. Coverage is identical between estimators. December contains 473
labels from ten stations; early support is 191/240 and later support is 185/233.
Across all three periods there are 1,400 derived station-hour labels.

The median improves five blocks, but worsens the December early block and
**fails the predeclared gate**. Production remains IDW. Neither estimator has
established street-level accuracy, calibrated uncertainty or a cleaner-detour
benefit. Broader independent evidence is required before choosing a new scorer.

[Machine-readable results](ESTIMATOR_COMPARISON_RESULTS.json) retain summaries,
per-station errors, input hashes, source hashes/URLs for December and the adoption
decision. Per-target predictions and original readings remain local. Reproduce:

```bash
cd backend
python -m scripts.fetch_archive --locations 8118 11607 17 235 5610 5630 6960 50 8239 5627 --dates 2025-12-06 2025-12-07 --output data/new-december.json
python -m scripts.compare_estimators --inputs data/delhi-validation-20251006-07.json data/delhi-independent-periods.json data/new-december.json --cutoffs 2025-10-06T19:30:00+00:00 2025-11-06T19:30:00+00:00 2025-12-06T19:30:00+00:00 --output data/new-estimator-comparison.json
```

Whole target stations and future donors are excluded identically for both
estimators. Synthetic tests verify those exclusions, one-station/multiple-sensor
support rules and preservation of an extreme input. The production scorer shares
its existing neighbour-selection logic with the experiment; its calculation and
model version are unchanged.
