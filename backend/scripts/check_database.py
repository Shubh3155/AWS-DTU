"""Read-only database/PostGIS check; connection errors must not expose credentials."""

import certifi
import psycopg

from app.core.config import get_settings


def main() -> int:
    url = get_settings().database_url
    if url is None:
        print("Database not checked: configure AEROROUTE_DATABASE_URL in backend/.env.")
        return 2
    try:
        with psycopg.connect(
            url.get_secret_value(),
            connect_timeout=10,
            sslmode="verify-full",
            sslrootcert=certifi.where(),
        ) as connection:
            connection.read_only = True
            connection.execute("SET LOCAL statement_timeout = 10000")
            result = connection.execute(
                "SELECT e.extversion, n.nspname FROM pg_extension e "
                "JOIN pg_namespace n ON n.oid = e.extnamespace WHERE e.extname = 'postgis'"
            ).fetchone()
            if result is None or result[1] == "public":
                print("Database connected, but PostGIS is missing or installed in public.")
                return 1
            print(f"Database connected over verified TLS; PostGIS {result[0]} in {result[1]}.")
            return 0
    except psycopg.Error:
        print("Database check failed; check password, host, network access and TLS certificate.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
