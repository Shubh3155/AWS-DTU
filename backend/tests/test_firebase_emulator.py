"""Integration with local Auth and Firestore, never a real Firebase project."""

import os
from datetime import UTC, datetime

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

pytestmark = pytest.mark.skipif(
    not os.getenv("FIREBASE_AUTH_EMULATOR_HOST") or not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason="Run through npm run test:firebase with the local Firebase emulators",
)


def test_real_admin_auth_and_firestore_navigation_transactions(monkeypatch):
    host = os.environ["FIREBASE_AUTH_EMULATOR_HOST"]
    signup = httpx.post(
        f"http://{host}/identitytoolkit.googleapis.com/v1/accounts:signUp?key=demo-key",
        json={
            "email": "backend-navigation@example.test",
            "password": "emulator-password",
            "returnSecureToken": True,
        },
    )
    signup.raise_for_status()
    account = signup.json()
    app = create_app(
        Settings(
            environment="test",
            firebase_project_id="demo-aeroroute",
            _env_file=None,
        )
    )
    headers = {"Authorization": f"Bearer {account['idToken']}"}
    client = TestClient(app)
    messages = []
    monkeypatch.setattr(app.state.firebase, "send", lambda device, data: messages.append(data))
    receipt = "a" * 32
    app.state.navigation_routes.put(
        receipt,
        {
            "route": {
                "id": "emulator-fixture",
                "geometry": {"coordinates": [[77.2, 28.6], [77.201, 28.6], [77.201, 28.601]]},
                "maneuvers": [
                    {"type": "turn", "instruction": "Turn left", "location": [77.201, 28.6]},
                ],
            },
            "mode": "walking",
        },
        ttl=1800,
    )
    device_id = "emulator-device"
    assert (
        client.put(
            f"/api/me/devices/{device_id}",
            headers=headers,
            json={
                "recipient": "local-test-registration",
                "recipient_kind": "fid",
            },
        ).status_code
        == 204
    )
    started = client.post(
        "/api/navigation/sessions",
        headers=headers,
        json={
            "device_id": device_id,
            "navigation_token": receipt,
        },
    )
    assert started.status_code == 200, started.text
    journey_id = started.json()["journey_id"]
    path = f"/api/navigation/sessions/{journey_id}"
    progress = client.post(
        path + "/progress",
        headers=headers,
        json={
            "sequence": 1,
            "navigation_token": receipt,
            "fix": {
                "lat": 28.6,
                "lng": 77.2003,
                "accuracy": 5,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        },
    )
    assert progress.status_code == 200, progress.text
    assert progress.json()["alert"] == "sent"
    assert len(messages) == 1
    stored = app.state.firebase.get(f"users/{account['localId']}/navigationSessions/{journey_id}")
    assert stored["sequence"] == 1 and "routeJson" in stored
    assert client.delete(path, headers=headers).status_code == 204
    assert client.delete(f"/api/me/devices/{device_id}", headers=headers).status_code == 204
