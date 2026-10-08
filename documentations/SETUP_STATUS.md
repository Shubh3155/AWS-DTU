# Thursday initial setup handoff

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

## Next team actions

1. Follow the root README to start both apps; use **Check connection** to verify the browser-to-API path.
2. Configure provider values locally. Private credentials belong in the backend environment.
3. Run the audit and complete `DATA_AUDIT.md`; agree the pilot and freshness/coverage policies.
4. Make the first genuine walking request and save source snapshots with timestamps.
5. Implement interpolation, segmentation, scoring and real result rendering using `API_CONTRACT.md` on Friday.
