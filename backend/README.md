# Backend

FastAPI service with travel routes, live regional PM2.5 forecasts, historical station
interpolation, and time-weighted exposure comparisons.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock
cp .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Health: `http://localhost:8000/health`. API documentation: `http://localhost:8000/docs`.
Mapbox supplies genuine travel routes. Live mode fetches current PM2.5 directly from
Open-Meteo / CAMS for route regions, with no pollution snapshot database read. Replay
requires an explicit request and uses stored OpenAQ observations. Both paths withhold
unsupported scores. See [LIVE_AIR_QUALITY.md](../documentations/LIVE_AIR_QUALITY.md) and
[API_CONTRACT.md](../documentations/API_CONTRACT.md). Copy the environment template only
if `.env` does not already contain your settings.

Checks: `ruff check .`, `ruff format --check .`, `pytest -q`.

Run the [OpenAQ audit](../documentations/DATA_AUDIT.md) after configuring its key. Keep raw reports in ignored `data/`. Database connectivity and versioned migrations are available; see [migrations/README.md](migrations/README.md). OpenAQ report ingestion is available; see [INGESTION.md](../documentations/INGESTION.md). The [baseline handoff](../documentations/EXPOSURE_BASELINE.md) documents provisional parameters and validation limits. Runtime caching reuses walking steps and re-scores freshness on every hit; TTL defaults to 120 seconds.

For bounded history and public archive downloads, follow [HISTORICAL_COVERAGE.md](../documentations/HISTORICAL_COVERAGE.md). Period/coverage/aggregation metadata and source-file hashes survive ingestion. Archive-derived reports are restricted to replay.

Deployment helpers, immutable S3 publication and rollback commands are documented in
[DEPLOYMENT.md](../documentations/DEPLOYMENT.md); the deployed VM/Amplify path is in
[AWS_VM_DEPLOYMENT.md](../documentations/AWS_VM_DEPLOYMENT.md). Current live-provider
verification and the pending live-forecast release are documented in
[LIVE_AIR_QUALITY.md](../documentations/LIVE_AIR_QUALITY.md). Publishing our own S3
snapshots remains a separate unfinished integration.

From the repository root, build with `docker build -t aeroroute-api backend`. The image listens on port 8000 and runs as a non-root user. Use `/health` as the Lightsail health-check path.

`requirements.lock` pins runtime and development tools for this setup. To deliberately refresh it, install `.[dev]` in the virtual environment and regenerate with `python -m pip freeze --exclude-editable > requirements.lock`, then rerun checks.
