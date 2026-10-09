# Setup and implementation handoff

## Latest progress — 9 October 2026

The historical MVP now has a demo preset, a genuine local release check at 0/5/15
minute allowances, and a [deployment handoff](RELEASE_HANDOFF.md). A fixed median
challenger was checked across 1,400 labels in three periods and failed its strict
adoption gate; production remains unchanged. See [ESTIMATOR_EXPERIMENT.md](ESTIMATOR_EXPERIMENT.md).

Current local checks: **116 backend tests pass, two optional database checks skip**;
frontend lint, types and build pass. Genuine multi-route replay and current live
limited-data behavior are verified. Path screening removes five backtracking
alternatives from eighteen saved candidates. A Central Delhi historical demo area
is reviewed across two periods. November station errors are substantially worse;
only one station is fresh in the new live audit. See [DATA_CREDIBILITY.md](DATA_CREDIBILITY.md),
[ROUTE_QUALITY.md](ROUTE_QUALITY.md) and [DATABASE_PERFORMANCE.md](DATABASE_PERFORMANCE.md).
AWS work is deferred; hosting and the final recording remain unfinished.

### Earlier Friday checkpoint (superseded)
- Implemented time-preserving segmentation, provisional interpolation, exact-detour exposure ranking, read-only snapshot loading and frontend scores/IST/replay notices. Missing support withholds full scores; reduction percentages remain unavailable pending validation.
- Added versioned runtime cache, bounded hourly/public archive downloads, coverage assessment, immutable S3 publication, exact-version Lightsail deployment helper/workflow, infrastructure template and Amplify build spec.
- Downloaded 462 genuine derived station-hour labels from ten Delhi locations, dated 6–7 October 2025 IST. Coverage review and limitations are in [HISTORICAL_COVERAGE.md](HISTORICAL_COVERAGE.md). They are historical replay, with zero live support.
- Backend Ruff checks pass: **83 tests passed, 2 opt-in database tests skipped**. Frontend lint/types/production build and **10 desktop/mobile Playwright tests** pass. Browser responses are synthetic fixtures. Ingestion and S3-manifest dry runs passed for the real archive report.
- **Friday: 11/14 items complete (79%); required Sunday MVP: approximately 65% complete.** Provider/database/AWS credentials and deployment targets remain unavailable. Real scored browser journey, deployed health and S3 upload remain open. Retrospective station/time capacity is reviewed; executing validation/sensitivity remains Saturday's work.

See [FRIDAY_HANDOFF.md](FRIDAY_HANDOFF.md) for current evidence/remaining work and [DEPLOYMENT.md](DEPLOYMENT.md) for cloud and rollback instructions. Earlier sections below are historical setup records.

## Previous progress — 8 October 2026

- Mapbox walking access is verified; provider-access PR #1 is merged.
- OpenAQ request pacing and sanitized quota diagnostics are merged in PR #2. The resumed audit succeeded: 118 readings from 77 stations were ingested as replay.
  None were under 24 hours old at fetch; fresh live coverage/pilot selection remain pending.
- Supabase verified TLS and PostGIS access are merged in PR #3.
- Migration `001_initial.sql` is applied: backend-only stations, observations, snapshots
  and comparison cache tables. Read-only migration status reports up to date.
- Backend lint/format checks and 37 tests pass, including live schema checks with all
  synthetic fixture writes rolled back.
- Actual walking candidates now reach the frontend; geometry, duration and detour eligibility
  are implemented. Scoring remains unavailable. See [INGESTION.md](INGESTION.md).
- Next: pilot/coverage review, segmentation/interpolation/scoring, then AWS account and
  deployment configuration. A restricted backend database role remains a production prerequisite.

## Initial foundation record

The foundation portion of Thursday's work is implemented across each project part. This does not mean half of the full four-day prototype is complete.

| Part | Implemented foundation | Remaining today |
| --- | --- | --- |
| Frontend | Next.js 15, TypeScript, Tailwind, responsive form, detour control, optional map selection, result placeholders, API connection check | Verify map access; agree an audited pilot; inspect a real routing response |
| Backend | FastAPI, settings, health/pilot endpoints, request validation, OpenAPI contract, local CORS, environment template | Provider access checks; real walking request; database connectivity |
| Data/model | Observation/estimate contracts and OpenAQ coverage-audit command | Run authenticated audit; select pilot; save genuine snapshot; define interpolation parameters |
| AWS/container | Non-root container definition, health check and successful CI build | Deployment checks; account/region verification; Supabase and S3 access |
| CI | Passing hosted frontend, backend and container-build jobs | Add the deployment workflow in the later integration step |
| Documentation | Setup/run instructions, API contract, audit checklist and updated plan | Record provider findings and pilot evidence |

Use Node.js 22 and Python 3.12. Docker is needed only for local container builds; CI also builds the container. The apps start without provider credentials. Live routing, scoring, database integrations and AWS deployment are pending.

Next.js 15 is pinned because the chosen [Amplify documentation](https://docs.aws.amazon.com/amplify/latest/userguide/ssr-amplify-support.html) lists support through version 15. Dependencies are recorded in `frontend/package-lock.json` and `backend/requirements.lock`.

## Verified locally

- Frontend lint, TypeScript check and production build pass.
- Backend lint/format checks and 11 API/audit tests pass.
- Both development servers start; the page and health endpoint return HTTP 200.
- The pilot remains unselected and valid comparison requests return the documented HTTP 503.
- The audit command exits explicitly without a report when its key is missing.
- Documentation links resolve and the original proposal checksum is unchanged.

The [setup CI run](https://github.com/Shubh3155/AWS-DTU/actions/runs/37794286232) passed for commit `55cbdca`, including the container build. Docker is not installed on the local machine. Live provider access, actual map loading and cloud deployment are not verified by these checks.

## Original Thursday next actions (historical)

1. Follow the root README to start both apps; use **Check connection** to verify the browser-to-API path.
2. Configure provider values locally. Private credentials belong in the backend environment.
3. Run the audit and complete `DATA_AUDIT.md`; agree the pilot and freshness/coverage policies.
4. Make the first genuine walking request and save source snapshots with timestamps.
5. Implement interpolation, segmentation, scoring and real result rendering using `API_CONTRACT.md` on Friday.

The latest Friday handoff above supersedes this original next-action list.
