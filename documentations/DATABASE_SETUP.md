# Database access handoff

On 8 October 2026 the `aeroroute` Supabase project was created in the AeroRoute free
organization. The dashboard reports it healthy in Tokyo (`ap-northeast-1`). PostGIS 3.3.7
is enabled in schema `gis`. Backend connectivity still requires local password entry and
a successful check; no station/observation/cache tables have been created yet.

## Configure locally

From `backend/`, install the locked dependencies, then open Supabase > Connect > Direct >
Session pooler. Use the host and user shown there. The session pooler is an IPv4-compatible
alternative to the direct IPv6 connection, without the dedicated IPv4 add-on.

```bash
python -m pip install -r requirements.lock
python -m scripts.configure_database --host YOUR_POOLER_HOST --user YOUR_POOLER_USER
python -m scripts.check_database
```

The first script prompts for the existing database password using hidden input, percent-encodes
special characters, and writes `AEROROUTE_DATABASE_URL` to ignored `backend/.env` with restricted
permissions. It preserves other environment settings. Run it from `backend/`. Do not paste
the password into chat, command arguments, GitHub or browser frontend settings.

The check uses certificate/hostname-verified TLS, a 10-second connection timeout, a read-only
transaction and a 10-second statement timeout. It verifies PostGIS is installed outside
`public`; it does not apply migrations or verify application tables. Connection errors are
sanitized so they do not expose the connection URL or password.

Exit codes: `0` = connected with PostGIS in a dedicated schema; `1` = connection or PostGIS
check failed; `2` = database URL unconfigured. Check host, username, password, pooler/network
availability and TLS if the check fails. Keep provider health separate from `/health`.

## Next after access passes

Add versioned migrations for stations, observations, snapshot manifests and route cache.
Keep credentials and database queries on the FastAPI backend. The initial bootstrap connection
uses the project database owner; establish an application role with only the needed table
permissions before production deployment.

References: [Supabase connection methods](https://supabase.com/docs/guides/database/connecting-to-postgres),
[PostGIS](https://supabase.com/docs/guides/database/extensions/postgis),
[Psycopg installation](https://www.psycopg.org/psycopg3/docs/basic/install.html).
