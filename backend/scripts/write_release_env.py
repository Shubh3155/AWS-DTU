"""Write a validated, private Docker env file without displaying credentials."""

import os
import sys
from pathlib import Path

from app.core.config import get_settings
from scripts.deploy_lightsail import deployment


def write_release_env(path: Path, version: str) -> None:
    settings = get_settings()
    if not settings.firebase_project_id:
        raise ValueError("Configure Firebase before release")
    values = deployment(settings, "aeroroute-api", ":aeroroute-api.preflight.1", version)[
        "containers"
    ]["api"]["environment"]
    if "AEROROUTE_FIREBASE_CREDENTIALS_JSON" not in values:
        raise ValueError("Configure private Firebase Admin credentials")
    if any("\n" in value or "\r" in value for value in values.values()):
        raise ValueError("Deployment values must fit Docker env-file lines")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as output:
        output.write("".join(f"{key}={value}\n" for key, value in values.items()))


if __name__ == "__main__":
    try:
        write_release_env(Path(sys.argv[1]), sys.argv[2])
        print("Private release environment validated and written.")
    except (ValueError, OSError, IndexError):
        raise SystemExit("Release configuration is incomplete or invalid") from None
