# Genuine historical coverage review — 9 October 2026

Downloaded twenty public OpenAQ daily CSV archives successfully and saved their unmodified gzip bytes in ignored `backend/data/archive/`. They describe **6–7 October 2025 in IST**, not current air. OpenAQ documents anonymous archive access and CSV fields in its [quick start](https://docs.openaq.org/aws/quick-start) and [archive reference](https://docs.openaq.org/aws/about).

The saved combined report is `backend/data/delhi-combined-20251006-07.json`, with the final download completed at `2026-10-09T09:23:19.525166Z`. Its raw-byte SHA256 is `e34c89b668452b46758b8506e5d516f6f2060623e49b19a56b18325c6a54fafe`. The normalized replay snapshot is `openaq-replay-67c76fa2c987a9f36d9e9afda5a8cb3a87d743d18ab66366563b260c19f29890`. Source URLs/hashes are recorded in [HISTORICAL_SOURCES.json](HISTORICAL_SOURCES.json); no raw pollution values or credentials are committed.

## Data and spatial support

After recognized µg/m³ units, finite nonnegative values, positive sensor/station IDs, aware timestamps, deduplication and coordinate checks, the report contains **462 derived station-hour labels from ten distinct sensors/locations**. Each label is the mean of available samples for one sensor/UTC hour, with source count, unit, period and actual latest source timestamp retained. Complete-hour coverage is not assumed. No rows were rejected in this download. Archive CSV lacks original provider/license/quality metadata; the source report preserves that absence. Explorer metadata was reviewed separately below; historical calibration and redistribution conditions still need review.

The observation range is `2025-10-05T19:30:00Z`–`2025-10-07T18:30:00Z`; IST day filenames do not imply UTC midnight boundaries. There are 48 distinct UTC hour bins and 107 exact observation timestamps. Thirty-one hour bins contain ten station IDs, sixteen contain nine and one contains eight. Different stations' original times are not forcibly aligned. The maximum exact-time overlap is nine station IDs.

| Location ID | Archive location | Latitude, longitude | Labels | Distance from review point | Other locations within 10 km |
| --- | --- | --- | --- | --- | --- |
| 8118 | [New Delhi](https://explore.openaq.org/locations/8118) | 28.635760, 77.224450 | 48 | 2,860 m | 6 |
| 11607 | [Lodhi Road, Delhi – IITM](https://explore.openaq.org/locations/11607) | 28.588333, 77.221667 | 47 | 3,100 m | 6 |
| 17 | [R K Puram, Delhi – DPCC](https://explore.openaq.org/locations/17) | 28.563262, 77.186937 | 48 | 6,029 m | 4 |
| 235 | [Anand Vihar, New Delhi – DPCC](https://explore.openaq.org/locations/235) | 28.646835, 77.316032 | 48 | 11,070 m | 2 |
| 5610 | [North Campus, DU, Delhi – IMD](https://explore.openaq.org/locations/5610) | 28.657381, 77.158545 | 48 | 6,901 m | 4 |
| 5630 | [Shadipur, Delhi – CPCB](https://explore.openaq.org/locations/5630) | 28.651478, 77.147311 | 48 | 7,329 m | 3 |
| 6960 | [Patparganj, Delhi – DPCC](https://explore.openaq.org/locations/6960) | 28.623748, 77.287205 | 48 | 7,712 m | 4 |
| 50 | [Punjabi Bagh, Delhi – DPCC](https://explore.openaq.org/locations/50) | 28.674045, 77.131023 | 48 | 10,131 m | 2 |
| 8239 | [Okhla Phase-2, Delhi – DPCC](https://explore.openaq.org/locations/8239) | 28.530785, 77.271255 | 31 | 11,062 m | 3 |
| 5627 | [CRRI Mathura Road, New Delhi – IMD](https://explore.openaq.org/locations/5627) | 28.551201, 77.273574 | 48 | 9,400 m | 4 |

The exploratory point is `(28.6139, 77.2090)`. Minimum separation between locations is approximately 1,278 m. The linked Explorer records classify these as stationary reference-grade locations: New Delhi lists AirNow, and the other nine list CPCB. This establishes a geographically separate station cohort for retrospective holdouts. Shared network/calibration errors can remain correlated; historical instrument metadata is not established by present Explorer descriptions.

At the last recorded timestamp, the current two-hour window retains all ten stations. A 5 km radius gives only two nearby stations at the review point, below the three-station requirement; 10 km gives seven and 15 km gives ten. Before geographic filtering, 0.25/0.5/1/2-hour age windows retain 8/10/10/10 stations across the dataset. The current 10 km/two-hour policy supports this **one historical point**. It remains provisional: broader coverage and actual route midpoints require review. Live assessment retains zero stations, correctly withholding a current-air score.

## Saturday validation prerequisites

The initial six-location download had inadequate holdout support at several targets. Four additional locations resolved most of those gaps. For each of the 462 labels, all observations at its target station were excluded and the remaining donors were filtered to the two-hour window ending at that label's actual time. **364 labels across eight stations have at least three valid nearby donors**; locations 235 and 50 have none under the current radius. Two early labels at 8118/11607 are also unsupported. Publish all targets and the supported fraction; do not silently drop unsupported cases. The exact count review is in [VALIDATION_PREREQUISITES.json](VALIDATION_PREREQUISITES.json).

For Saturday's station holdouts, exclude **all** readings/sensors for the target location. Reserve the later contiguous block beginning `2025-10-06T19:30:00Z`; there are 231 labels before it and 231 at/after it. Fix policy/tuning on the earlier block, and use only non-target donors at or before each test label's timestamp. Contemporaneous neighboring measurements are inputs to interpolation, not a forecast; test targets never become donor/training labels for their own predictions. Publish split membership, missingness, coverage and metrics on Saturday. Two days and ten locations do not establish useful regressor generalization; optional ML is deferred in favor of the required baseline evaluation.

Friday's station/time capacity check is complete for a limited retrospective baseline evaluation. No MAE/RMSE, calibrated uncertainty, street-level accuracy, reduction percentage or approved pilot is claimed. Saturday still needs to execute the evaluation and ranking sensitivity checks, including unsupported cases explicitly.

## Reproduce

From `backend/` with the virtual environment active; output files must be new:

```bash
python -m scripts.fetch_archive --locations 8118 11607 17 235 5610 5630 6960 50 8239 5627 --dates 2025-10-06 2025-10-07 --output data/delhi-combined-20251006-07.json
python -m scripts.assess_coverage --input data/delhi-combined-20251006-07.json --lat 28.6139 --lng 77.2090 --output data/delhi-combined-coverage-20261009.json
python -m scripts.ingest_openaq --input data/delhi-combined-20251006-07.json --mode replay
python -m scripts.publish_snapshot --input data/delhi-combined-20251006-07.json --mode replay
```

Downloads are bounded to 50 files, a 25 km exploratory radius, compressed/decompressed size and row limits. Conflicting sensor/timestamp values or moving coordinates require review. Archive-derived reports reject live ingestion. Actual database ingestion and S3 upload require configured access and `--apply`; only validation dry runs were executed today. New fetch timestamps change the report/snapshot hash; compare the preserved source-file hashes when reproducing.

An authenticated hourly path is also implemented:

```bash
python -m scripts.fetch_history --audit data/openaq-audit.json --from 2026-10-06T00:00:00Z --to 2026-10-08T00:00:00Z --max-sensors 10 --output data/openaq-hours.json
```

It uses the saved station audit, preserves API periods/coverage/provider/license metadata, bounds periods to seven days and caps sensor/page counts. Its network behavior was fixture-tested; no authenticated historical request was made in this checkout. [OpenAQ measurements resources](https://docs.openaq.org/resources/measurements).
