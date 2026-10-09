# Deployment and rollback

The deployment configuration is implemented and locally checked. No AWS resources, Amplify build, public backend URL or S3 upload have been verified in this checkout. AWS credentials, region and service targets are unavailable. A successful `/health` response establishes process/version health; verify database reads and a genuine scored journey separately.

## Provisioning

Use an authorized AWS profile, AWS CLI v2, Docker and the official [Lightsail container plugin](https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-install-software.html). Python helpers use the SDK's normal credential chain. Keep access keys out of repository files.

The versioned [CloudFormation template](../backend/deployment/resources.json) defines a Lightsail container service with `nano` power/one instance and a private, encrypted, versioned S3 bucket. The bucket is retained on stack deletion. Service provisioning incurs AWS charges. Choose the account/region and check existing resources before applying; the following command has **not** been executed:

```bash
aws cloudformation deploy --template-file backend/deployment/resources.json --stack-name aeroroute-foundation --region REGION --parameter-overrides ServiceName=SERVICE
aws cloudformation describe-stacks --stack-name aeroroute-foundation --region REGION --query 'Stacks[0].Outputs'
```

The stack outputs identify the service and snapshot bucket. Reuse existing resources instead if provided. CloudFormation validation against AWS remains pending. The template uses the official [Lightsail container resource](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-lightsail-container.html).

## Backend release

Create GitHub's `production` environment, restrict its deployment branches to `main`, and configure an AWS OIDC role trusted for `repo:Shubh3155/AWS-DTU:environment:production`. Grant the role the Lightsail image-registration, registry-login, service-read and deployment permissions needed for the selected service. Provisioning and snapshot-upload permissions can be held by separate operators. Follow [GitHub's AWS OIDC guide](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws).

Configure these GitHub environment values:

| Name | Kind | Purpose |
| --- | --- | --- |
| `AWS_ROLE_ARN` | Secret | AWS OIDC role assumed by the workflow |
| `AEROROUTE_MAPBOX_TOKEN` | Secret | Backend walking-directions access |
| `AEROROUTE_DATABASE_URL` | Secret | Restricted backend database role with verified TLS |
| `AEROROUTE_OPENAQ_API_KEY` | Optional secret | Authenticated audit/history commands |
| `AEROROUTE_CORS_ORIGINS` | Variable | JSON list of explicit HTTPS frontend origins, such as `["https://APP.amplifyapp.com"]` |

Apply database migrations and provision the restricted runtime role using [DATABASE_SETUP.md](DATABASE_SETUP.md). Runtime reads need stations/observations/snapshots access; the cache additionally needs SELECT/INSERT/UPDATE/DELETE on `aeroroute.route_comparison_cache`. Use a separate migration/ingestion role for schema and observation writes. Provider/database settings are injected into the container without printing their values in workflow logs.

After merging a passing release to `main`, dispatch [deploy-backend.yml](../.github/workflows/deploy-backend.yml):

```bash
gh workflow run deploy-backend.yml --ref main -f region=REGION -f service=SERVICE
```

The workflow tests the backend, checks credentials/CORS configuration, assumes the AWS role, builds the image and registers it under a commit-specific label. It deploys the exact returned image version, serves port 8000, waits for the newly created deployment version to become active, and checks public HTTPS `/health` against the release's full Git SHA. It never deploys `latest`. Releases run serially and are not cancelled by a later dispatch. [Lightsail image registration](https://docs.aws.amazon.com/cli/latest/reference/lightsail/push-container-image.html), [deployment API](https://docs.aws.amazon.com/cli/latest/reference/lightsail/create-container-service-deployment.html).

For a local release, configure ignored `backend/.env`, then run from the repository root:

```bash
docker build --tag aeroroute-api:release backend
aws lightsail push-container-image --region REGION --service-name SERVICE --image aeroroute-api:release --label api-release --query containerImage.image --output text
```

From `backend/`, pass the **exact image string returned above** and its source commit:

```bash
python -m scripts.deploy_lightsail --region REGION --service SERVICE --image ':SERVICE.api-release.VERSION_NUMBER' --version FULL_COMMIT_SHA
```

Keep the known-good image string and corresponding source SHA in the release record. The helper creates a deployment on an existing service; it does not create the service or migrate the database.

## Amplify frontend

Connect this repository and `main` in Amplify using authorized account access. Select the Next.js frontend with app root `frontend`, and set `AMPLIFY_MONOREPO_APP_ROOT=frontend` to match [amplify.yml](../amplify.yml). The build uses Node.js 22, the npm lockfile, lint/type checks and `.next` artifacts. Follow the official [monorepo configuration](https://docs.aws.amazon.com/amplify/latest/userguide/monorepo-configuration.html).

Set these variables **before building**, because Next.js rewrites and public variables are included at build time:

| Name | Value |
| --- | --- |
| `AEROROUTE_API_URL` | Verified Lightsail HTTPS origin; required by the build spec |
| `NEXT_PUBLIC_MAPBOX_TOKEN` | Intended public browser map token, if map interaction is enabled |
| `NEXT_PUBLIC_API_URL` | Leave empty for the same-origin proxy; optional direct backend origin requires matching CORS |

Redeploy the frontend after changing its backend URL. Set backend CORS to the deployed frontend origin. Verify **Check connection**, routing geometry, detour changes, replay notices and a supported genuine-data comparison at desktop/mobile widths. Fixture-based browser tests do not prove this deployed flow.

## Timestamped S3 snapshots

From `backend/`, configure `AEROROUTE_AWS_REGION`, `AEROROUTE_S3_BUCKET` and AWS credentials. Validate first; uploading requires the explicit flag:

```bash
python -m scripts.publish_snapshot --input data/delhi-combined-20251006-07.json --mode replay
python -m scripts.publish_snapshot --input data/delhi-combined-20251006-07.json --mode replay --apply
```

Objects are stored under `snapshots/YYYY/MM/DD/SNAPSHOT_ID/{report,manifest}.json`, dated by the **original latest observation**. The manifest retains mode, source files/hashes, report hash, observation range, fetch time, provider/license metadata and limitations. Archive-derived labels require replay mode. The report bytes are unchanged by publication.

Writes request AES256 encryption and use `If-None-Match: *`. An existing object is accepted only if its stored SHA256 metadata matches; different content is rejected. The uploader needs `s3:PutObject` and `s3:GetObject` (for HEAD) for the snapshot prefix. [S3 conditional writes](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html).

This CLI publishes snapshots; it does not ingest database rows, schedule refreshes or make the running API read S3. Those integrations and the first actual upload remain pending. A local manifest dry run passed for the genuine archive report.

## Release evidence and rollback

Record the frontend URL/build, backend URL, AWS region/service, exact image, full source SHA, database migration version, snapshot/data/model IDs, S3 object URIs and the CI/deployment run links after a real release. All public URLs/S3 URIs are currently **unavailable**.

Verify process health and then run the repeatable journey checker against the selected API:

```bash
python -m scripts.check_journey --api-url https://BACKEND_ORIGIN --request data/pilot-request.json --require-score --repeat 10 --output data/pilot-latency.json
```

Prepare `pilot-request.json` using [API_CONTRACT.md](API_CONTRACT.md) and an audited journey. The checker validates exact detour eligibility and records observed median/p95 latency by hit/miss/bypass; it creates no success report if scoring or requests fail. Inspect browser/map rendering separately. No real latency claim is available yet.

To roll back, redeploy the previously verified exact Lightsail image with its corresponding source SHA through `scripts.deploy_lightsail`, using the current valid runtime settings. Verify HTTPS health/version and the journey again. In Amplify, redeploy the recorded known-good frontend build/commit with the correct API URL. Keep database changes backward-compatible; reverting an application image does not revert migrations. Preserve versioned snapshots and existing credentials during rollback.
