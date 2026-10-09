# AeroRoute

Walking-route comparisons using estimated PM2.5 exposure and a user-defined time budget.

The implementation window is **Thursday, 8 October to Sunday, 11 October 2026**, in India Standard Time. Walking routes, recorded OpenAQ ingestion, Supabase/PostGIS migrations, exposure scoring and versioned routing cache are implemented. Desktop/mobile browser checks pass; genuine historical labels and AWS deployment configuration are ready. Friday is **11/14 items complete (79%)**; the required Sunday MVP is approximately **65% complete**. Genuine journey verification, validation and actual AWS deployment remain open.

- [Implementation plan and daily checklist](documentations/IMPLEMENTATION_PLAN.md)
- [Original revised proposal](documentations/AeroRoute_Revised_Proposal%20%281%29.pdf)
- [Setup handoff and remaining work](documentations/SETUP_STATUS.md)
- [API contract](documentations/API_CONTRACT.md)
- [Monitoring data audit](documentations/DATA_AUDIT.md)
- [Database access setup](documentations/DATABASE_SETUP.md)
- [Friday exposure baseline and next tasks](documentations/EXPOSURE_BASELINE.md)
- [Friday completion and remaining checks](documentations/FRIDAY_HANDOFF.md)
- [Genuine historical coverage review](documentations/HISTORICAL_COVERAGE.md)
- [AWS deployment, snapshots and rollback](documentations/DEPLOYMENT.md)

```text
AWS-DTU/
├── frontend/            # Next.js, TypeScript, Tailwind CSS, Mapbox GL JS
├── backend/             # FastAPI, data processing, exposure model, database, AWS container
├── .github/
│   └── workflows/       # GitHub Actions for checks and deployment
└── documentations/      # Proposal, implementation plan, validation and demo documentation
```

Work is organized into frontend, data/model, and backend/AWS responsibilities. Assign tasks within the team as needed.

## Run locally

Use Node.js 22 and Python 3.12. Run the apps in separate terminals. Copy environment examples only if the destination does not already contain your settings.

Backend:

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock
cp .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend, from a second terminal at the repository root:

```bash
cd frontend
npm ci
cp .env.example .env.local
npm run dev
```

Visit `http://localhost:3000` and use **Check connection**. Backend health is at `http://localhost:8000/health`; API docs are at `http://localhost:8000/docs`. Both apps start without provider credentials. Add a browser Mapbox token for the map; private credentials belong only in `backend/.env`.

With Mapbox configured, the page displays actual walking routes, durations and detour eligibility. Database access enables PM2.5 scores when every route sample has sufficient recent station support. Live mode is the default; **Use recorded pollution observations** explicitly selects historical replay. Missing or stale readings keep exposure unavailable. Lower model estimates remain uncertain, and reduction percentages are withheld pending validation. Missing routing credentials return HTTP 503. See the [baseline handoff](documentations/EXPOSURE_BASELINE.md) and [recorded snapshot](documentations/INGESTION.md).

## Checks

From `frontend/`: `npm run lint`, `npm run typecheck`, `npm run build`. After the build, install Chromium with `npx playwright install chromium` and run `npm run test:e2e`. Browser checks use labelled synthetic responses at desktop/mobile widths.

From `backend/`, with the virtual environment active: `ruff check .`, `ruff format --check .`, `pytest -q`.

GitHub Actions runs these checks, browser tests and a container build on pushes and pull requests. The manual backend deployment workflow requires a configured production environment, AWS OIDC role and service targets; see [DEPLOYMENT.md](documentations/DEPLOYMENT.md). No public AWS endpoints are verified yet.

## Branch and merge rules

1. Create a new branch from the latest `main` for each task. Use names such as `feat/route-comparison`, `fix/detour-limit` or `docs/merge-rules`.
2. Make focused commits grouped by project part or a coherent change, such as the model, backend/API, frontend and documentation. Keep related tests with their code and preserve dependency order. Stage only that group's files; avoid combining all parts into one commit.
3. Before merging, bring the latest `origin/main` into your task branch, resolve conflicts there, review the changes and run the relevant checks. Once CI is configured, its required checks must pass.
4. Merge the completed branch into your local `main`, then push `main` to GitHub.
5. Keep `main` working. Avoid direct feature commits to `main` and never force-push it. If a push is rejected because someone else updated `main`, integrate their changes and rerun the relevant checks before pushing again.

For an empty repository, the team lead must create the initial setup commit on `main` and publish it with `git push -u origin main` before using this workflow.

### Example: update the README

Create the task branch:

```bash
git switch main
git pull --ff-only origin main
git switch -c docs/merge-rules
```

Edit the README, review the changes and commit:

```bash
git diff -- README.md
git add README.md
git commit -m "docs: add team merge rules"
```

Update the task branch with the latest shared changes:

```bash
git fetch origin
git merge origin/main
```

Resolve any conflicts on the task branch and run the relevant checks before continuing. Then merge and push:

```bash
git switch main
git pull --ff-only origin main
git merge --no-ff docs/merge-rules -m "Merge docs/merge-rules"
git push origin main
```

Use your own branch name, file paths and commit message for other tasks.
