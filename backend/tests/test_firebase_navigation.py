from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.firebase import FirebaseGateway
from app.core.runtime_cache import RuntimeCache
from app.main import create_app
from app.schemas.navigation import DeviceRegistration, NavigationStart, NavigationUpdate
from app.services.notifications import NavigationService, device_path, session_path

NOW = datetime(2026, 10, 10, 12, tzinfo=UTC)
DEVICE = "browser-installation"
RECEIPT = "a" * 32
ROUTE = {
    "id": "provider-route",
    "geometry": {
        "type": "LineString",
        "coordinates": [[77.2, 28.6], [77.201, 28.6], [77.201, 28.601]],
    },
    "maneuvers": [
        {"instruction": "Depart", "type": "depart", "location": [77.2, 28.6]},
        {"instruction": "Turn left onto Test Street", "type": "turn", "location": [77.201, 28.6]},
        {"instruction": "Arrive", "type": "arrive", "location": [77.201, 28.601]},
    ],
}


class Transaction:
    def __init__(self, values):
        self.values, self.wrote = values, False

    def get(self, path):
        assert not self.wrote, "Firestore transactions must read before writing"
        return deepcopy(self.values.get(path))

    def set(self, path, data):
        self.wrote = True
        self.values[path] = deepcopy(data)


class Gateway:
    def __init__(self):
        self.values, self.messages = {}, []
        self.fail_send = False

    def transact(self, callback):
        staged = deepcopy(self.values)
        result = callback(Transaction(staged))
        self.values = staged
        return result

    def get(self, path):
        return deepcopy(self.values.get(path))

    def verify(self, token):
        if token not in ("alice", "bob"):
            raise HTTPException(401, "Expired or revoked session")
        return token

    def send(self, device, data):
        if self.fail_send:
            raise RuntimeError("Provider unavailable")
        self.messages.append((device, data))


@pytest.fixture
def flow():
    clock = [NOW]
    gateway = Gateway()
    routes = RuntimeCache()
    routes.put(RECEIPT, {"route": ROUTE, "mode": "walking"}, ttl=1800)
    service = NavigationService(gateway, routes, now=lambda: clock[0])
    service.register("alice", DEVICE, DeviceRegistration(recipient="registered-device-fid"))
    session = service.start("alice", NavigationStart(device_id=DEVICE, navigation_token=RECEIPT))
    return service, gateway, routes, session, clock


def update(clock, sequence=1, receipt=RECEIPT, **fix):
    return NavigationUpdate.model_validate(
        {
            "sequence": sequence,
            "navigation_token": receipt,
            "fix": {
                "lat": 28.6,
                "lng": 77.2003,
                "accuracy": 5.0,
                "timestamp": clock[0],
                **fix,
            },
        }
    )


def test_directions_use_provider_maneuvers_and_deduplicate_retries(flow):
    service, gateway, _, session, clock = flow
    first = service.progress("alice", session.journey_id, update(clock))
    assert first.alert == "sent"
    assert "Turn left onto Test Street" in gateway.messages[0][1]["instruction"]
    assert "In 70 m" in gateway.messages[0][1]["instruction"]
    assert service.progress("alice", session.journey_id, update(clock)).accepted is False
    clock[0] += timedelta(seconds=5)
    assert service.progress("alice", session.journey_id, update(clock, sequence=2)).alert == "none"
    assert len(gateway.messages) == 1


def test_reroute_replaces_authoritative_route_and_old_alert_key(flow):
    service, gateway, routes, session, clock = flow
    service.progress("alice", session.journey_id, update(clock))
    replacement = deepcopy(ROUTE)
    replacement["maneuvers"][1]["instruction"] = "Turn right onto New Street"
    routes.put("b" * 32, {"route": replacement, "mode": "walking"}, ttl=1800)
    clock[0] += timedelta(seconds=5)
    service.progress("alice", session.journey_id, update(clock, 2, "b" * 32))
    assert gateway.messages[-1][1]["routeVersion"] == "b" * 32
    assert "Turn right" in gateway.messages[-1][1]["instruction"]


def test_cross_user_progress_and_unissued_routes_are_rejected(flow):
    service, _, _, session, clock = flow
    with pytest.raises(HTTPException) as error:
        service.progress("bob", session.journey_id, update(clock))
    assert error.value.status_code == 404
    with pytest.raises(HTTPException) as error:
        service.start("alice", NavigationStart(device_id=DEVICE, navigation_token="f" * 32))
    assert error.value.status_code == 409


@pytest.mark.parametrize("operation", ["stop", "unregister", "expired"])
def test_stopped_logged_out_and_abandoned_journeys_cannot_send(flow, operation):
    service, gateway, _, session, clock = flow
    if operation == "stop":
        service.stop("alice", session.journey_id)
    elif operation == "unregister":
        service.unregister("alice", DEVICE)
    else:
        clock[0] += timedelta(seconds=31)
    with pytest.raises(HTTPException) as error:
        service.progress("alice", session.journey_id, update(clock))
    assert error.value.status_code == 410
    assert gateway.messages == []


def test_weak_off_route_or_stale_gps_never_triggers_direction_alerts(flow):
    service, gateway, _, session, clock = flow
    assert (
        service.progress("alice", session.journey_id, update(clock, accuracy=500.0)).alert == "none"
    )
    clock[0] += timedelta(seconds=5)
    assert (
        service.progress("alice", session.journey_id, update(clock, 2, lat=28.62)).alert == "none"
    )
    with pytest.raises(HTTPException) as error:
        service.progress(
            "alice", session.journey_id, update(clock, 3, timestamp=NOW - timedelta(minutes=1))
        )
    assert error.value.status_code == 422
    assert gateway.messages == []


def test_account_rebinding_invalidates_old_device_and_journey(flow):
    service, gateway, _, session, clock = flow
    clock[0] += timedelta(seconds=5)
    service.register("bob", DEVICE, DeviceRegistration(recipient="registered-device-fid"))
    assert gateway.values[device_path("alice", DEVICE)]["enabled"] is False
    with pytest.raises(HTTPException) as error:
        service.progress("alice", session.journey_id, update(clock))
    assert error.value.status_code == 410


def test_arrival_is_sent_once_and_stops_the_session(flow):
    service, gateway, _, session, clock = flow
    result = service.progress("alice", session.journey_id, update(clock, lat=28.601, lng=77.201))
    assert result.arrived and result.alert == "sent"
    assert gateway.messages[0][1]["instruction"] == "You have arrived at your destination"
    assert not gateway.values[session_path("alice", session.journey_id)]["active"]


def test_push_failure_does_not_fail_progress_and_rate_limits_work(flow):
    service, gateway, _, session, clock = flow
    gateway.fail_send = True
    assert service.progress("alice", session.journey_id, update(clock)).alert == "failed"
    clock[0] += timedelta(seconds=1)
    with pytest.raises(HTTPException) as error:
        service.progress("alice", session.journey_id, update(clock, 2))
    assert error.value.status_code == 429
    gateway.fail_send = False
    clock[0] += timedelta(seconds=4)
    assert service.progress("alice", session.journey_id, update(clock, 2)).alert == "sent"
    assert len(gateway.messages) == 1


def test_device_registration_and_session_creation_cannot_bypass_rate_limits(flow):
    service, _, _, _, clock = flow
    with pytest.raises(HTTPException) as error:
        service.register("alice", "another-browser", DeviceRegistration(recipient="another-fid"))
    assert error.value.status_code == 429
    with pytest.raises(HTTPException) as error:
        service.start("alice", NavigationStart(device_id=DEVICE, navigation_token=RECEIPT))
    assert error.value.status_code == 429
    clock[0] += timedelta(seconds=3)
    assert service.start("alice", NavigationStart(device_id=DEVICE, navigation_token=RECEIPT))


def test_protected_endpoints_verify_uid_and_reject_payload_overrides():
    app = create_app(Settings(environment="test", _env_file=None))
    app.state.firebase = Gateway()
    client = TestClient(app)
    url = f"/api/me/devices/{DEVICE}"
    payload = {"recipient": "valid-registration"}
    assert client.put(url, json=payload).status_code == 401
    assert (
        client.put(url, json=payload, headers={"Authorization": "Bearer revoked"}).status_code
        == 401
    )
    assert (
        client.put(
            url, json={**payload, "uid": "bob"}, headers={"Authorization": "Bearer alice"}
        ).status_code
        == 422
    )
    assert (
        client.put(url, json=payload, headers={"Authorization": "Bearer alice"}).status_code == 204
    )
    assert device_path("alice", DEVICE) in app.state.firebase.values
    assert device_path("bob", DEVICE) not in app.state.firebase.values


def test_admin_id_token_verification_checks_revocation(monkeypatch):
    gateway = FirebaseGateway(Settings(_env_file=None))
    monkeypatch.setattr(gateway, "initialize", lambda: None)
    calls = []
    monkeypatch.setattr(
        "app.core.firebase.auth.verify_id_token",
        lambda token, **kwargs: calls.append(kwargs) or {"uid": "verified-user"},
    )
    assert gateway.verify("firebase-token") == "verified-user"
    assert calls[0]["check_revoked"] is True


def test_private_cors_allows_auth_headers_and_device_methods():
    client = TestClient(create_app(Settings(environment="test", _env_file=None)))
    response = client.options(
        f"/api/me/devices/{DEVICE}",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code == 200
    assert "Authorization" in response.headers["access-control-allow-headers"]
