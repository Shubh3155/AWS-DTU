# Historical MVP release handoff

## Ready locally

- Form, map selection, one-green-route preview, responsive route cards and demo preset.
- Genuine walking candidates, path screening and exact allowances.
- Reviewed historical demo boundary, recorded snapshot ingestion and exposure scoring.
- Live/replay isolation, insufficient-data handling, bounded pooling/cache expiry.
- Station validation across three periods; fixed robust-estimator experiment documented
  without silently replacing production or dropping inconvenient observations.
- Read-only release checker, demo script, deployment/container scaffold and CI.

Backend: **116 tests pass**, two optional database tests skip, Ruff lint/format pass.
Frontend lint/types/build pass; desktop/mobile browser checks run in hosted CI.
Startup now waits up to ten seconds for its first pooled connection. The genuine
release check was repeated after a restart and passed all four cases.
The [genuine local release check](LOCAL_RELEASE_CHECK.json) verifies recorded
allowances 0/5/15 and live insufficient-data behavior. It reports local process
version `0.1.0`; it is not evidence of a public deployment or a deployed Git SHA.

The selected genuine replay snapshot is:
`openaq-replay-14990a04a352f6863d374d9146bf50a9edb212a650b4c705a71fe42463852cf4`.
It is already in the configured Supabase database. November/December remain offline
evaluation reports, so they do not replace the established app demonstration.

## Remaining deployment session

Use [DEPLOYMENT.md](DEPLOYMENT.md) for the actual commands and configuration:

1. Sign in to the intended AWS account, select the region and provision/reuse the
   Lightsail service and private versioned S3 bucket.
2. Configure GitHub's production environment, AWS OIDC trust and required runtime
   secrets. Configure a restricted backend database role before public release,
   using [DATABASE_SETUP.md](DATABASE_SETUP.md); the local owner account is not the
   intended production credential.
3. Deploy the exact backend image/version, confirm HTTPS health and a genuine
   snapshot read. Publish the October snapshot to S3 with its source manifest.
   S3 stores the archival copy; the running API reads Supabase.
4. Connect Amplify to `main`, use app root `frontend`, set its backend HTTPS origin
   and browser map token, configure matching backend CORS, and build.
5. Run the release checker against the public backend, inspect desktop/mobile
   rendering, record release URLs/SHA and check rollback information.
6. Rehearse and record [DEMO_SCRIPT.md](DEMO_SCRIPT.md) with the public URLs.

Public API verification, from `backend/` (replace placeholders):

```bash
python -m scripts.check_release --api-url https://BACKEND_ORIGIN --expected-version FULL_GIT_SHA --snapshot-id openaq-replay-14990a04a352f6863d374d9146bf50a9edb212a650b4c705a71fe42463852cf4 --output data/public-release-check.json
```

The checker makes read-only API calls and requires at least two distinct returned
candidates with supported replay scores. It refuses silent live-to-replay
substitution, unsupported live scores, incorrect allowance flags and unvalidated
reduction percentages. No success report is saved after a failed check. Network,
provider or public configuration failures still require resolution during deployment.

## Scope decision and remaining research

The deployable deliverable is a **historical replay prototype**. Dependable live
coverage, stronger station/route accuracy and a robust positive cleaner-detour
example remain unresolved evidence gaps. They are disclosed limitations of this
release, not features we can mark complete because the code runs. They need not
block deployment of the labelled historical MVP. No AWS resources were configured
in this readiness session.
