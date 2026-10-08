# Backend

Initial FastAPI service with configuration, health/pilot endpoints, journey validation and a coverage-audit command.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock
cp .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Health: `http://localhost:8000/health`. API documentation: `http://localhost:8000/docs`. Valid comparison requests return HTTP 503 pending integration; see [API_CONTRACT.md](../documentations/API_CONTRACT.md). Copy the environment template only if `.env` does not already contain your settings.

Checks: `ruff check .`, `ruff format --check .`, `pytest -q`.

Run the [OpenAQ audit](../documentations/DATA_AUDIT.md) after configuring its key. Keep raw reports in ignored `data/`. Interpolation, segmentation, database access and AWS deployment remain pending.

From the repository root, build with `docker build -t aeroroute-api backend`. The image listens on port 8000 and runs as a non-root user. Use `/health` as the Lightsail health-check path.

`requirements.lock` pins runtime and development tools for this setup. To deliberately refresh it, install `.[dev]` in the virtual environment and regenerate with `python -m pip freeze --exclude-editable > requirements.lock`, then rerun checks.
