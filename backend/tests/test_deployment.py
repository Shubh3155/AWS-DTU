import hashlib
import json

import boto3
import httpx
import pytest
from botocore.exceptions import ClientError
from botocore.stub import Stubber
from test_ingestion import report

from app.core.config import Settings
from scripts.deploy_lightsail import deploy, deployment
from scripts.publish_snapshot import publish, snapshot_objects


def settings():
    return Settings(
        mapbox_token="synthetic",
        database_url="synthetic",
        cors_origins=["https://frontend.example"],
        _env_file=None,
    )


def test_deployment_pins_image_version_ports_tls_health_and_app_version():
    payload = deployment(settings(), "aeroroute-api", ":aeroroute-api.api.1", "revision")
    assert payload["publicEndpoint"]["healthCheck"]["path"] == "/health"
    env = payload["containers"]["api"]["environment"]
    assert env["AEROROUTE_APP_VERSION"] == "revision"
    assert json.loads(env["AEROROUTE_CORS_ORIGINS"]) == ["https://frontend.example"]
    for image in [":aeroroute-api.api.latest", ":other.api.1", "nginx:latest"]:
        with pytest.raises(ValueError):
            deployment(settings(), "aeroroute-api", image, "revision")
    with pytest.raises(ValueError):
        deployment(Settings(_env_file=None), "aeroroute-api", ":aeroroute-api.api.1", "revision")
    for origin in ["https://", "https://frontend.example/path", "http://frontend.example"]:
        invalid = settings().model_copy(update={"cors_origins": [origin]})
        with pytest.raises(ValueError):
            deployment(invalid, "aeroroute-api", ":aeroroute-api.api.1", "revision")


def test_sdk_deploy_waits_for_exact_deployment_and_verifies_health(monkeypatch):
    client = boto3.client(
        "lightsail",
        region_name="ap-south-1",
        aws_access_key_id="synthetic",
        aws_secret_access_key="synthetic",
    )
    payload = deployment(settings(), "aeroroute-api", ":aeroroute-api.api.1", "revision")
    service = {
        "url": "https://backend.example",
        "currentDeployment": {
            "state": "ACTIVE",
            "version": 1,
            "containers": {"api": {"image": ":aeroroute-api.api.1"}},
        },
    }
    calls = []

    def health(url, **kwargs):
        calls.append(url)
        return httpx.Response(
            200, json={"status": "ok", "version": "revision"}, request=httpx.Request("GET", url)
        )

    monkeypatch.setattr("scripts.deploy_lightsail.httpx.get", health)
    with Stubber(client) as stub:
        stub.add_response(
            "get_container_services",
            {"containerServices": [service]},
            {"serviceName": "aeroroute-api"},
        )
        stub.add_response(
            "create_container_service_deployment",
            {"containerService": {"nextDeployment": {"version": 2}}},
            payload,
        )
        stub.add_response(
            "get_container_services",
            {"containerServices": [service]},
            {"serviceName": "aeroroute-api"},
        )
        service = {**service, "currentDeployment": {**service["currentDeployment"], "version": 2}}
        stub.add_response(
            "get_container_services",
            {"containerServices": [service]},
            {"serviceName": "aeroroute-api"},
        )
        assert (
            deploy(client, payload, "revision", attempts=2, pause=lambda _: None)
            == "https://backend.example"
        )
        stub.assert_no_pending_responses()
    assert calls == ["https://backend.example/health"]


def test_snapshot_manifest_keeps_original_times_units_and_source_hash():
    raw = (json.dumps(report()) + "\n").encode()
    objects = snapshot_objects(raw, "replay")
    manifest = json.loads(
        next(body for key, body in objects.items() if key.endswith("manifest.json"))
    )
    assert manifest["observed_to"].startswith("2026-10-07")
    assert manifest["fetched_at"].startswith("2026-10-08")
    assert manifest["report_sha256"] == hashlib.sha256(raw).hexdigest()
    assert manifest["data_mode"] == "replay"
    assert next(body for key, body in objects.items() if key.endswith("report.json")) == raw


def test_s3_publish_is_encrypted_conditional_and_immutable():
    calls = []

    class Client:
        def put_object(self, **kwargs):
            calls.append(kwargs)

        def head_object(self, **kwargs):
            return {}

    objects = {"snapshots/report.json": b"report"}
    assert publish(Client(), "private-bucket", objects) == [
        "s3://private-bucket/snapshots/report.json"
    ]
    assert calls[0]["IfNoneMatch"] == "*"
    assert calls[0]["ServerSideEncryption"] == "AES256"

    class Duplicate(Client):
        def put_object(self, **kwargs):
            raise ClientError({"Error": {"Code": "PreconditionFailed"}}, "PutObject")

        def head_object(self, **kwargs):
            return {"Metadata": {"sha256": hashlib.sha256(b"report").hexdigest()}}

    assert publish(Duplicate(), "private-bucket", objects)
    with pytest.raises(ValueError):
        publish(Duplicate(), "private-bucket", {"snapshots/report.json": b"changed"})
