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


@pytest.fixture
def admin_account():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return {
        "type": "service_account",
        "project_id": "test-project",
        "client_email": "synthetic@test-project.iam.gserviceaccount.com",
        "token_uri": "https://oauth2.googleapis.com/token",
        "private_key": key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode(),
    }


def test_aws_exports_admin_json_not_a_local_path(admin_account, tmp_path):
    path = tmp_path / "admin.json"
    path.write_text(json.dumps(admin_account))
    for source in [
        {"firebase_credentials_path": str(path)},
        {"firebase_credentials_json": json.dumps(admin_account)},
    ]:
        config = Settings(
            mapbox_token="synthetic",
            database_url="synthetic",
            cors_origins=["https://frontend.example"],
            firebase_project_id="test-project",
            _env_file=None,
            **source,
        )
        env = deployment(config, "aeroroute-api", ":aeroroute-api.api.1", "revision")["containers"][
            "api"
        ]["environment"]
        assert env["AEROROUTE_FIREBASE_PROJECT_ID"] == "test-project"
        assert json.loads(env["AEROROUTE_FIREBASE_CREDENTIALS_JSON"]) == admin_account
        assert "AEROROUTE_FIREBASE_CREDENTIALS_PATH" not in env
        if config.firebase_credentials_json:
            assert admin_account["private_key"] not in repr(config)


def test_bad_or_incomplete_admin_credentials_block_release(admin_account):
    for source in [
        {"firebase_project_id": "test-project"},
        {"firebase_credentials_json": json.dumps(admin_account)},
        {
            "firebase_project_id": "other-project",
            "firebase_credentials_json": json.dumps(admin_account),
        },
        {"firebase_project_id": "test-project", "firebase_credentials_json": "not-json"},
    ]:
        config = Settings(
            mapbox_token="synthetic",
            database_url="synthetic",
            cors_origins=["https://frontend.example"],
            _env_file=None,
            **source,
        )
        with pytest.raises(ValueError):
            deployment(config, "aeroroute-api", ":aeroroute-api.api.1", "revision")


def test_admin_runtime_uses_environment_json_without_a_file(admin_account, monkeypatch):
    from app.core.firebase import FirebaseGateway

    config = Settings(
        firebase_project_id="test-project",
        firebase_credentials_json=json.dumps(admin_account),
        _env_file=None,
    )
    calls = []
    monkeypatch.setattr(
        "app.core.firebase.firebase_admin.initialize_app",
        lambda credential, options, **kwargs: calls.append((credential, options)) or "app",
    )
    monkeypatch.setattr("app.core.firebase.firestore.client", lambda **kwargs: "database")
    gateway = FirebaseGateway(config)
    gateway.initialize()
    assert gateway.database == "database"
    assert calls[0][0].project_id == "test-project"
    assert calls[0][1]["projectId"] == "test-project"


def test_vm_env_file_keeps_admin_json_on_one_private_line(admin_account, tmp_path, monkeypatch):
    from scripts.write_release_env import write_release_env

    config = Settings(
        mapbox_token="synthetic",
        database_url="synthetic",
        cors_origins=["https://frontend.example"],
        firebase_project_id="test-project",
        firebase_credentials_json=json.dumps(admin_account),
        _env_file=None,
    )
    monkeypatch.setattr("scripts.write_release_env.get_settings", lambda: config)
    path = tmp_path / "release.env"
    write_release_env(path, "revision")
    values = dict(line.split("=", 1) for line in path.read_text().splitlines())
    assert json.loads(values["AEROROUTE_FIREBASE_CREDENTIALS_JSON"]) == admin_account
    assert values["AEROROUTE_APP_VERSION"] == "revision"
    assert path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        write_release_env(path, "other")


def test_vm_env_file_rejects_injected_docker_environment_lines(
    admin_account, tmp_path, monkeypatch
):
    from scripts.write_release_env import write_release_env

    config = Settings(
        mapbox_token="synthetic\nOTHER_SETTING=bad",
        database_url="synthetic",
        cors_origins=["https://frontend.example"],
        firebase_project_id="test-project",
        firebase_credentials_json=json.dumps(admin_account),
        _env_file=None,
    )
    monkeypatch.setattr("scripts.write_release_env.get_settings", lambda: config)
    path = tmp_path / "release.env"
    with pytest.raises(ValueError):
        write_release_env(path, "revision")
    assert not path.exists()
