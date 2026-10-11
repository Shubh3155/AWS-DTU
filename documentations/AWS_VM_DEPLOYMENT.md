# Lightsail VM release

The AWS Free plan account has $100 in credits as reviewed on 11 October 2026.
Its managed-container creation returned a non-adjustable quota error. The deployed
alternative is an Ubuntu 24.04 Lightsail instance named `aeroroute-api` in Mumbai,
1 GB RAM/40 GB disk, at $7/month charged against eligible credits. Keep the Free
plan unchanged; access ends when its free period or credits run out.

The attached static IP is `13.200.213.6`. Caddy terminates HTTPS for
`aeroroute-api.13.200.213.6.sslip.io` and proxies to Docker on `127.0.0.1:8000`.
The temporary hostname relies on sslip.io DNS; a project-owned domain can replace
it later. Internet rules expose SSH with key authentication, HTTP for certificate
issuance/HTTPS redirects and HTTPS. Port 8000 remains bound to localhost.

GitHub Amplify access is limited to `Shubh3155/AWS-DTU`. Frontend hosting follows
`main` with `frontend` as its monorepo root. Public Firebase configuration and the
public Mapbox token belong in Amplify; private credentials do not.

## Production environment

The [VM workflow](../.github/workflows/deploy-backend-vm.yml) uses the existing backend
secrets from [DEPLOYMENT.md](DEPLOYMENT.md), plus:

| Name | Kind | Purpose |
| --- | --- | --- |
| `AEROROUTE_DEPLOY_SSH_KEY` | Secret | Dedicated backend deployment key |
| `AEROROUTE_DEPLOY_HOST` | Variable | Static IPv4 address |
| `AEROROUTE_DEPLOY_KNOWN_HOSTS` | Variable | Verified/pinned SSH host key |
| `AEROROUTE_BACKEND_URL` | Variable | HTTPS origin for release verification |

Restrict the `production` environment to `main`. Dispatch `deploy-backend-vm.yml`
from `main` after CI passes. The runner builds the exact commit image, transfers
it and a private validated env file over pinned SSH, and activates it under a
deployment lock. The container runs as the image's non-root user with no extra
capabilities, a read-only root filesystem and a private temporary mount. Logs are
bounded. Failed local readiness restores the previous container if available.
The final check verifies HTTPS health against the source SHA. Verify genuine
database-backed routing separately; health does not prove provider support.

The production database login is `aeroroute_runtime_aws`. Its grants and scoped
row-security policies are in [runtime_role.sql](../backend/deployment/runtime_role.sql).
It can read stations, observations and snapshots, and read/write cache entries.
It cannot ingest data or migrate schemas. Keep the database owner credential local
for separate maintenance. No passwords/private keys belong in tracked files.

Revoke the dedicated SSH key and production secrets when retiring this deployment.
Maintain OS security updates. The VM needs operator maintenance, unlike the managed
container service. Neither credits nor hosting replace the MVP accuracy and
real-device validation limits in [AWS_READINESS.md](AWS_READINESS.md).
