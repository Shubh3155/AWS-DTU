# AWS deployment readiness — 11 October 2026

The current MVP can proceed to AWS staging after the configuration gates below.
This review does not provision AWS resources or establish a production accuracy guarantee.

## Verified in this checkout

- Updated locked dependencies install; frontend lint/types/production build pass.
- Backend lint/format and 146 tests pass; three integration checks need their explicit
  database/emulator environment and are skipped in the default suite.
- Four production-config tests cover missing settings, invalid/local HTTPS origins,
  emulator/test configuration and private browser map tokens.
- Supabase connects over certificate/hostname-verified TLS; migrations are current.
- The frontend production dependency audit reports zero vulnerabilities after compatible
  overrides for `@grpc/grpc-js` 1.14.6 and PostCSS 8.5.29. This is the production npm tree,
  not a claim that all development tooling or Python packages have been audited.
- Base commit `9bff899` passed GitHub CI: 58 regular browser tests, 32 Firebase browser
  tests, Firestore rule checks, the Admin emulator flow and the backend container build.
  The readiness-fix PR must pass the same full CI before release.

## Fixed release issues

- Lightsail releases now receive the Firebase project and private Admin JSON. The server
  supports JSON environment credentials, validates matching projects and private keys,
  and avoids reliance on a developer's host file path. The workflow blocks missing settings.
- Amplify validates complete web app configuration before building; it rejects local or
  non-HTTPS/credential-bearing API URLs, private browser Mapbox tokens and emulator/test mode.
- Hosting/Firebase environment names and verification gates are documented in
  [DEPLOYMENT.md](DEPLOYMENT.md) and [FIREBASE_SETUP.md](FIREBASE_SETUP.md).

## Required before a full-feature AWS release

1. Select/authenticate the AWS account and region. Provision/reuse the Lightsail service
   and connect Amplify to `main` with `frontend` as app root. No AWS CLI or Docker runtime
   is installed in this host; GitHub CI provides the container build path.
2. Replace the local Supabase owner connection with a restricted application role for the
   production secret. The review confirmed that the current local connection uses `postgres`.
   Migrate/ingest with a separate role. See [DATABASE_SETUP.md](DATABASE_SETUP.md).
3. Configure a valid private Firebase Admin credential in GitHub's `production` environment.
   The current local setting points to a file that does not exist here; live Admin access
   is therefore not verified in this checkout. Never put Admin JSON in frontend variables.
4. Set the AWS OIDC role, backend secrets, Firebase project and explicit HTTPS CORS origins
   listed in the deployment guide. Configure all Amplify public Firebase/Mapbox settings
   and the verified backend HTTPS URL before building.
5. Authorize the deployed frontend hostname in Firebase Auth and intended Mapbox browser
   token restrictions. Verify the deployed Google sign-in, session/history access and
   service-worker registration; verify actual push delivery on a supported device.
6. Verify deployed HTTPS health/version, database reads, genuine walking/vehicle comparisons,
   guest and signed-in flows, GPS/rerouting/traffic updates and desktop/mobile layouts.
   Record exact image/source SHA and frontend build for rollback.

## MVP limits that remain visible

Pollution station interpolation is provisional and uses explicitly labelled historical data
when replay is selected; live coverage may be insufficient. Traffic-profile access is verified,
but the Delhi sample had unknown congestion. Motorcycle routes/times remain car approximations.
GPS and cloud alerts need real-device field validation; foreground browser suspension can halt
updates. These limits do not prevent deploying the labelled MVP, but deployment does not resolve
or validate them.

S3 snapshot publication/ingestion refresh scheduling is separate from the running database-backed
API and remains an optional unfinished integration. See the deployment guide for its scope.
