# Friday completion and remaining access checks

Updated 9 October 2026. **11 of 14 Friday checklist items are complete (79%)**. The required Sunday MVP is approximately **65% complete**, based on effort rather than counting equally sized checkboxes. The Friday delivery gate remains unmet.

## Completed and checked

- Walking-provider client, database schema, validated ingestion, time-preserving segmentation, station interpolation, exact-detour ranking and frontend scores/quality states were already implemented.
- Runtime cache now retains walking steps and comparison metadata, with exact coordinates/allowance/mode, actual snapshot/data/model versions and five-minute buckets. TTL defaults to 120 seconds. Equivalent explicit/default snapshot selection uses one key. Every hit re-scores observation support using the current live reference; old scores are never replayed as fresh. Cache failures fall back to genuine provider requests. Writes happen after the response. Database cache behavior was tested with controlled connections; actual cache reads/writes await database access.
- Historical downloads now support authenticated OpenAQ hours and anonymous public archives. **462 genuine derived station-hour labels from ten Delhi locations** were downloaded. Public station metadata, spatial separation, time-filtered holdout donor support and earlier/later block counts were reviewed. Capacity is sufficient for a limited retrospective baseline evaluation; optional ML is deferred. See [HISTORICAL_COVERAGE.md](HISTORICAL_COVERAGE.md). The report is historical replay only.
- Desktop/mobile browser checks passed: **10 Playwright tests**, including replay scores/timestamps, uncertainty, limited data, detour/mode changes, no-route and recoverable provider error. Screenshots at 1440 and 390 px were inspected; no horizontal overflow. Responses are explicitly synthetic fixtures; real map/provider integration remains open. CI runs the tests and retains browser artifacts.
- Cloud preparation includes a monorepo Amplify build spec, Lightsail/S3 infrastructure template, manual main-only OIDC deployment workflow, exact-image/new-deployment health verification, immutable S3 publisher, measured-latency journey checker and [DEPLOYMENT.md](DEPLOYMENT.md). These are prepared configurations, not deployed infrastructure.
- Local checks: **83 backend tests passed, 2 opt-in database tests skipped**; Ruff lint/format passed. Frontend lint, TypeScript and production build passed. Browser checks passed against that production build. Snapshot ingestion and S3 manifest dry runs passed for the real archive report. Container build is covered by CI; Docker is unavailable locally.

## Remaining Friday items

| Checklist item | Completed portion | Required evidence still missing |
| --- | --- | --- |
| Amplify/Lightsail deployment and public health | Build spec, infrastructure template, deployment workflow/helper and version checks | Authorized AWS profile/OIDC role, region/service/app targets; actual deployment and public HTTPS health/version |
| S3 snapshots and deployment procedure | Private/versioned/encrypted bucket template, publisher, manifest dry run and instructions | Bucket/region/credentials and successful upload/object verification |
| Genuine local pilot journey and detour change | Comparison implementation, browser states and repeatable journey checker | Mapbox/database settings, audited journey/snapshot, real browser score/map and exact-budget check |

No backend `.env`, frontend map configuration or AWS profile was available. GitHub repository secret/variable listings were empty; production-environment metadata was inaccessible. Earlier access findings in the repository remain historical records, not a verification of today's environment. Credentials must be configured in ignored environment files/GitHub secrets, never in chat or commits.

## Progress estimate

This estimate excludes optional address search, weather/road features and ML. It weights the required MVP by expected effort, and does not count code scaffolding as deployed behavior:

| Required area | Weight | Completed estimate |
| --- | --- | --- |
| Repository, contract and local foundation | 10% | 10% |
| Walking routes and ingestion | 15% | 15% |
| Exposure calculation, ranking and cache | 20% | 18% |
| Frontend interaction and browser states | 15% | 13% |
| Genuine integration and model validation | 15% | 4% |
| AWS deployment and snapshot integration | 20% | 4% |
| Final handoff and recorded demonstration | 5% | 1% |
| **Total** | **100%** | **Approximately 65%** |

Next: restore provider/database/AWS access, complete the three runtime/cloud checks, then execute Saturday's documented held-out/sensitivity work. Keep reduction percentages unavailable until that evidence is established. Preserve the existing grouped-commit, branch-to-main merge workflow.
