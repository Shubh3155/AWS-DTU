"""Save an existing database password locally without putting it in shell history."""

import argparse
import getpass
import os
import tempfile
from pathlib import Path
from urllib.parse import quote


def connection_url(host: str, user: str, password: str) -> str:
    if not password or any(character in host for character in "/:@?#"):
        raise ValueError("A password and a plain database hostname are required")
    return f"postgresql://{quote(user, safe='')}:{quote(password, safe='')}@{host}:5432/postgres"


def save_url(path: Path, url: str) -> None:
    source = path.read_text() if path.exists() else Path(".env.example").read_text()
    lines = [line for line in source.splitlines() if not line.startswith("AEROROUTE_DATABASE_URL=")]
    lines.append(f"AEROROUTE_DATABASE_URL={url}")
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as output:
        output.write("\n".join(lines) + "\n")
        temporary = Path(output.name)
    temporary.chmod(0o600)
    os.replace(temporary, path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Configure the backend PostgreSQL connection.")
    parser.add_argument("--host", required=True)
    parser.add_argument("--user", required=True)
    args = parser.parse_args()
    password = getpass.getpass("Existing Supabase database password (hidden): ")
    save_url(Path(".env"), connection_url(args.host, args.user, password))
    print("Saved database connection in ignored backend/.env; credentials are not displayed.")


if __name__ == "__main__":
    main()
