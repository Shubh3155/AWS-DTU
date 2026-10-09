# Retrospective baseline validation — 9 October 2026

The fixed IDW baseline was evaluated against 462 genuine derived station-hour labels from ten Delhi stations on 6–7 October 2025 (IST). All 20 downloaded archive files have the same SHA-256 hashes as the earlier [source audit](HISTORICAL_SOURCES.json). This is a historical experiment, not current pollution coverage.

Each target excludes its entire provider/station identity from donors at all timestamps. Donors must be observed at or before the target timestamp and within two hours; the production interpolation function selects the nearest five stations within 10 km and requires three. Multiple sensors at a target timestamp share one averaged label. No parameters were fitted or tuned.

The previously documented cutoff **2025-10-06T19:30:00+00:00** divides targets into early and later blocks of 231 labels. This tests fixed-policy interpolation using contemporaneous neighbours, not forecasting. [Machine-readable results](VALIDATION_RESULTS.json) include per-station coverage and errors, policy version, snapshot identity and input hash. Per-target predictions and unsupported cases remain in the generated local report.

| Block | Targets | Supported | Unsupported | Coverage | MAE µg/m³ | RMSE µg/m³ | Bias µg/m³ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Early | 231 | 181 | 50 | 78.35% | 10.57 | 14.70 | +0.30 |
| Later | 231 | 183 | 48 | 79.22% | 10.59 | 27.27 | +0.60 |

Errors describe supported targets only; missing targets remain in the coverage denominator. Anand Vihar (235) and Punjabi Bagh (50) have zero held-out coverage. Two additional early targets lack support. The higher later RMSE warrants inspection of large errors before tuning or expanding the pilot.

## Reproduce

From `backend/`, with the virtual environment active:

```bash
python -m scripts.fetch_archive \
  --locations 8118 11607 17 235 5610 5630 6960 50 8239 5627 \
  --dates 2025-10-06 2025-10-07 \
  --output data/delhi-validation-20251006-07.json
python -m scripts.validate_baseline \
  --input data/delhi-validation-20251006-07.json \
  --cutoff 2025-10-06T19:30:00+00:00 \
  --output data/baseline-validation-20251006-07.json
```

Both tools refuse to overwrite existing output files. Raw archives, source readings and per-target results remain under ignored `backend/data/`; use new filenames to rerun.

Two days and ten stations do not establish generalization across seasons or neighbourhoods. Station errors do not validate street-level exposure or route ranking. Reduction percentages remain withheld. Sensitivity checks, longer independent periods, route-level observations, pilot boundary approval and actual AWS deployment remain open.

Verification: 87 backend tests pass, two optional tests skip; Ruff lint and formatting pass. Tests exercise whole-station exclusion, future-donor exclusion, unsupported denominators and temporal split requirements.

## Genuine integration check

The recreated snapshot was atomically ingested into Supabase. A real Mapbox journey from (28.6139, 77.209) to (28.6200, 77.2200) returned one candidate with 100% modeled-time support and a historical exposure estimate. Live mode correctly returned `limited_data` with null exposure. This is an exploratory journey, not an approved pilot or a route-ranking validation.

Ten repeated API requests verified exact time-budget eligibility: one cache miss and nine hits. Cache-hit median was 4.85 seconds and p95 was 12.02 seconds; the miss took 6.42 seconds. The five-second response target is not established. See [measured evidence](GENUINE_JOURNEY_CHECK.json). Remote database connection latency remains a performance investigation.

Frontend lint, type checking and production build pass. Local automated browser tests could not launch Chromium because the macOS sandbox denied its Mach-port registration; the hosted CI browser checks must pass before merging. The in-app browser separately verified the genuine replay page, map, 1245.6 µg·min/m³ estimate, 100% modeled-time support and historical timestamps.
