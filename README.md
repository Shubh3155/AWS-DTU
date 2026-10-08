# AeroRoute

Walking-route comparisons using estimated PM2.5 exposure and a user-defined time budget.

The implementation window is **Thursday, 8 October to Sunday, 11 October 2026**, in India Standard Time. The initial frontend, backend, audit tooling and CI foundation are implemented. Live routing, scoring, pilot selection and cloud deployment are next.

- [Implementation plan and daily checklist](documentations/IMPLEMENTATION_PLAN.md)
- [Original revised proposal](documentations/AeroRoute_Revised_Proposal%20%281%29.pdf)
- [Setup handoff and remaining work](documentations/SETUP_STATUS.md)
- [API contract](documentations/API_CONTRACT.md)
- [Monitoring data audit](documentations/DATA_AUDIT.md)
- [Database access setup](documentations/DATABASE_SETUP.md)

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

The page is a setup preview with pending route cards. Valid comparison requests return HTTP 503 until routing and scoring are implemented. No live pollution readings or exposure estimates are displayed.

## Checks

From `frontend/`: `npm run lint`, `npm run typecheck`, `npm run build`.

From `backend/`, with the virtual environment active: `ruff check .`, `ruff format --check .`, `pytest -q`.

GitHub Actions runs these checks and a container build on pushes and pull requests. AWS deployment is not enabled by the initial CI workflow.

## Branch and merge rules

1. Create a new branch from the latest `main` for each task. Use names such as `feat/route-comparison`, `fix/detour-limit` or `docs/merge-rules`.
2. Make and commit task changes on that branch. Stage only the files belonging to the task.
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
