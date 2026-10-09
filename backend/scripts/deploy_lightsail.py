"""Deploy a registered, versioned image and verify its public HTTPS health endpoint."""

import argparse
import json
import re
import time
from urllib.parse import urlsplit

import boto3
import httpx
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import Settings, get_settings


def deployment(settings: Settings, service: str, image: str, version: str) -> dict:
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,61}", service):
        raise ValueError("Invalid service name")
    if not image.startswith(f":{service}.") or not re.search(r"\.\d+$", image):
        raise ValueError("Use an exact registered Lightsail image version")
    if not settings.mapbox_token or not settings.database_url:
        raise ValueError("Routing and database credentials are required for deployment")
    origins = [urlsplit(origin) for origin in settings.cors_origins]
    if not origins or any(
        origin.scheme != "https"
        or not origin.hostname
        or origin.username
        or origin.password
        or origin.path
        or origin.query
        or origin.fragment
        for origin in origins
    ):
        raise ValueError("Configure explicit production HTTPS frontend origins")
    env = {
        "AEROROUTE_ENVIRONMENT": "production",
        "AEROROUTE_APP_VERSION": version,
        "AEROROUTE_MAPBOX_TOKEN": settings.mapbox_token.get_secret_value(),
        "AEROROUTE_DATABASE_URL": settings.database_url.get_secret_value(),
        "AEROROUTE_CORS_ORIGINS": json.dumps(settings.cors_origins),
        "AEROROUTE_BASELINE_STATION_RADIUS_METRES": str(settings.baseline_station_radius_metres),
        "AEROROUTE_BASELINE_MAX_AGE_HOURS": str(settings.baseline_max_age_hours),
        "AEROROUTE_CACHE_TTL_SECONDS": str(settings.cache_ttl_seconds),
    }
    if settings.openaq_api_key:
        env["AEROROUTE_OPENAQ_API_KEY"] = settings.openaq_api_key.get_secret_value()
    return {
        "serviceName": service,
        "containers": {"api": {"image": image, "ports": {"8000": "HTTP"}, "environment": env}},
        "publicEndpoint": {
            "containerName": "api",
            "containerPort": 8000,
            "healthCheck": {
                "path": "/health",
                "successCodes": "200",
                "intervalSeconds": 10,
                "timeoutSeconds": 5,
                "healthyThreshold": 2,
                "unhealthyThreshold": 2,
            },
        },
    }


def deploy(client, payload: dict, version: str, attempts: int = 60, pause=time.sleep) -> str:
    services = client.get_container_services(serviceName=payload["serviceName"])[
        "containerServices"
    ]
    if not services:
        raise ValueError("Create the service first using the infrastructure template")
    created = client.create_container_service_deployment(**payload)
    target_version = created["containerService"]["nextDeployment"]["version"]
    for _ in range(attempts):
        service = client.get_container_services(serviceName=payload["serviceName"])[
            "containerServices"
        ][0]
        current = service.get("currentDeployment", {})
        if (
            current.get("state") == "ACTIVE"
            and current.get("version") == target_version
            and current.get("containers", {}).get("api", {}).get("image")
            == payload["containers"]["api"]["image"]
        ):
            url = service["url"].rstrip("/")
            if not url.startswith("https://"):
                raise ValueError("Public endpoint must use HTTPS")
            try:
                response = httpx.get(url + "/health", timeout=10)
                response.raise_for_status()
                health = response.json()
                if health.get("status") == "ok" and health.get("version") == version:
                    return url
            except (httpx.HTTPError, ValueError):
                pass  # Allow the new public endpoint to become ready within the polling limit.
        if service.get("nextDeployment", {}).get("state") == "FAILED":
            raise ValueError("Container deployment failed")
        pause(10)
    raise ValueError("Timed out waiting for the deployed image")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--service", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    try:
        payload = deployment(get_settings(), args.service, args.image, args.version)
        client = boto3.Session(region_name=args.region).client("lightsail")
        url = deploy(client, payload, args.version)
        print(f"Verified backend: {url}; app version: {args.version}")
        return 0
    except (ValueError, KeyError, IndexError, BotoCoreError, ClientError, httpx.HTTPError):
        print("Deployment not verified: check configuration, AWS access and service health.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
