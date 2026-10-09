# Backend

FastAPI service with walking routes, versioned pollution ingestion, station interpolation and time-weighted exposure comparisons.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock
cp .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Health: `http://localhost:8000/health`. API documentation: `http://localhost:8000/docs`. Mapbox provides walking candidates; database snapshot reads enable exposure scoring when support is sufficient. Live mode rejects stale observations; replay requires an explicit request. See [API_CONTRACT.md](../documentations/API_CONTRACT.md). Copy the environment template only if `.env` does not already contain your settings.

Checks: `ruff check .`, `ruff format --check .`, `pytest -q`.

Run the [OpenAQ audit](../documentations/DATA_AUDIT.md) after configuring its key. Keep raw reports in ignored `data/`. Database connectivity and versioned migrations are available; see [migrations/README.md](migrations/README.md). OpenAQ report ingestion is available; see [INGESTION.md](../documentations/INGESTION.md). The [baseline handoff](../documentations/EXPOSURE_BASELINE.md) documents provisional parameters and validation limits. Caching, S3 and AWS deployment remain pending.

From the repository root, build with `docker build -t aeroroute-api backend`. The image listens on port 8000 and runs as a non-root user. Use `/health` as the Lightsail health-check path.

`requirements.lock` pins runtime and development tools for this setup. To deliberately refresh it, install `.[dev]` in the virtual environment and regenerate with `python -m pip freeze --exclude-editable > requirements.lock`, then rerun checks.
