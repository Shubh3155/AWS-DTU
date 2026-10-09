# Database connections and repeated-comparison performance

## Implementation — 9 October 2026

FastAPI opens a process-local Psycopg pool at startup and closes it at shutdown.
Each worker has one initial connection, at most four connections and eight queued
leases. Lease acquisition waits up to three seconds; this is not a deadline for
the complete request. Background connection establishment uses a ten-second
connect timeout. Checkout checks connection health. Verified TLS and the existing
three-second statement timeout remain enabled. Reads explicitly use read-only
transactions; subsequent cache writes reset that mode.

The application also holds two bounded, thread-safe memory caches, each with at
most 32 entries. Successful snapshot reads last ten seconds and are isolated by
requested live/replay mode and snapshot identity. Newly ingested data can therefore
take up to ten seconds to become visible in a running worker. Failed reads are
never cached; after expiry, database failure withholds scores rather than using an
expired snapshot. Cached values are copied to prevent caller mutations.

Walking candidates use the existing versioned cache key, including snapshot,
model, endpoints, allowance and five-minute time bucket. Provider responses stay
in memory for the configured routing TTL (120 seconds by default); database hits
stay in memory for at most ten seconds. This can retain a database-loaded candidate
for up to ten seconds beyond its database expiry. Only walking candidates are
reused: observation freshness, support, eligibility and exposure are recalculated
for every response. No cached comparison score bypasses those checks.

## Local measurements

The genuine central-east Delhi journey used the same recorded OpenAQ snapshot
and three actual Mapbox walking candidates as the earlier demo. Historical
observations remain explicitly replay data. Each of ten sequential comparisons
passed exact time-budget checks and returned supported scores.

| Configuration | Samples | Median | Largest / empirical p95 |
| --- | ---: | ---: | ---: |
| Pool alone, database cache hits | 8 | 5.891 s | 11.990 s |
| Pool alone, cache misses | 2 | 5.512 s | 5.794 s |
| Pool + memory cache, first miss | 1 | 6.661 s | 6.661 s |
| Pool + memory cache, warm hits | 9 | 0.012 s | 0.018 s |

These are small local samples, not an AWS benchmark or a latency guarantee. The
pool alone did not establish a speed improvement. Memory hits avoid repeated
remote database reads, but cold requests and snapshot refreshes still incur
database latency. A pool cannot eliminate network outages. Live pollution
coverage remains unavailable; the faster replay demo does not establish current
air quality or a cleaner-route benefit.

Local ignored evidence files are `backend/data/pool-journey-check.json` and
`backend/data/runtime-cache-journey-check.json`. Reproduce with
`python -m scripts.check_journey --request <request.json> --repeat 10
--require-score --output <new-report.json>` against the running backend. Use a new
output filename. Keep a first miss separate from warm hits, and test after the
ten-second snapshot expiry as well.

Backend checks: Ruff lint/format, 102 passing tests and two optional database tests
skipped. New tests cover lifespan cleanup, read-to-write transaction modes, pool
exhaustion, cache eviction/copying/expiry, mode/identity isolation, freshness
crossing a boundary on a memory hit, and withholding scores when the database
fails after snapshot expiry. Existing desktop/mobile browser checks run in CI.
