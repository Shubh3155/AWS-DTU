"""Transactional device/journey ownership, progress deduplication and FCM dispatch."""

import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

from fastapi import HTTPException
from firebase_admin import messaging

from app.schemas.navigation import NavigationSession, ProgressResult
from app.services.directions import next_direction


def device_path(uid, device_id):
    return f"users/{uid}/devices/{device_id}"


def session_path(uid, journey_id):
    return f"users/{uid}/navigationSessions/{journey_id}"


def binding_path(recipient):
    return "pushBindings/" + sha256(recipient.encode()).hexdigest()


class NavigationService:
    def __init__(self, gateway, issued_routes, now=None):
        self.gateway = gateway
        self.routes = issued_routes
        self.now = now or (lambda: datetime.now(UTC))

    def register(self, uid, device_id, registration):
        now = self.now()
        path = device_path(uid, device_id)
        binding = binding_path(registration.recipient)

        def operation(tx):
            current = tx.get(path)
            owner = tx.get(binding)
            old = tx.get(owner["path"]) if owner and owner["path"] != path else None
            limit_path = f"users/{uid}/alertLimits/current"
            limits = tx.get(limit_path)
            if limits and (now - limits["registeredAt"]).total_seconds() < 1:
                raise HTTPException(429, "Please wait before updating alerts again.")
            if current and (now - current["updatedAt"]).total_seconds() < 1:
                raise HTTPException(429, "Please wait before updating alerts again.")
            if old:
                tx.set(owner["path"], {**old, "enabled": False})
            # A new registration always invalidates any previous device-bound journey.
            tx.set(
                path,
                {
                    "recipient": registration.recipient,
                    "recipientKind": registration.recipient_kind,
                    "enabled": True,
                    "updatedAt": now,
                    "journeyId": None,
                },
            )
            tx.set(binding, {"path": path, "uid": uid})
            tx.set(limit_path, {"registeredAt": now})

        self.gateway.transact(operation)

    def unregister(self, uid, device_id):
        path = device_path(uid, device_id)

        def operation(tx):
            device = tx.get(path)
            session = (
                tx.get(session_path(uid, device["journeyId"]))
                if device and device.get("journeyId")
                else None
            )
            if device:
                tx.set(path, {**device, "enabled": False, "journeyId": None})
            if session:
                tx.set(session_path(uid, device["journeyId"]), {**session, "active": False})

        self.gateway.transact(operation)

    def start(self, uid, request):
        issued = self.routes.get(request.navigation_token)
        if issued is None:
            raise HTTPException(
                409, "This route has expired. Compare routes again to enable alerts."
            )
        now, journey_id = self.now(), uuid4().hex
        expires = now + timedelta(seconds=30)
        path = device_path(uid, request.device_id)

        def operation(tx):
            device = tx.get(path)
            if not device or not device["enabled"]:
                raise HTTPException(409, "Enable direction alerts for this device first.")
            binding = tx.get(binding_path(device["recipient"]))
            old = (
                tx.get(session_path(uid, device["journeyId"])) if device.get("journeyId") else None
            )
            if not binding or binding["path"] != path:
                raise HTTPException(409, "Alerts are active in another account.")
            if device.get("lastStartedAt") and (now - device["lastStartedAt"]).total_seconds() < 2:
                raise HTTPException(429, "Please wait before starting alerts again.")
            tx.set(
                session_path(uid, journey_id),
                {
                    "deviceId": request.device_id,
                    "routeJson": json.dumps(issued["route"]),
                    "routeId": issued["route"]["id"],
                    "routeVersion": request.navigation_token,
                    "active": True,
                    "sequence": 0,
                    "progress": 0,
                    "lastAlert": None,
                    "lastSeenAt": now,
                    "expiresAt": expires,
                },
            )
            tx.set(path, {**device, "journeyId": journey_id, "lastStartedAt": now})
            if old:
                tx.set(session_path(uid, device["journeyId"]), {**old, "active": False})

        self.gateway.transact(operation)
        return NavigationSession(
            journey_id=journey_id, route_version=request.navigation_token, expires_at=expires
        )

    def stop(self, uid, journey_id):
        path = session_path(uid, journey_id)

        def operation(tx):
            session = tx.get(path)
            if not session:
                return
            device = tx.get(device_path(uid, session["deviceId"]))
            tx.set(path, {**session, "active": False})
            if device and device.get("journeyId") == journey_id:
                tx.set(device_path(uid, session["deviceId"]), {**device, "journeyId": None})

        self.gateway.transact(operation)

    def progress(self, uid, journey_id, update):
        now = self.now()
        if abs((now - update.fix.timestamp).total_seconds()) > 15:
            raise HTTPException(422, "A fresh GPS fix is required for direction alerts.")
        path = session_path(uid, journey_id)
        replacement = self.routes.get(update.navigation_token)

        def operation(tx):
            session = tx.get(path)
            if not session:
                raise HTTPException(404, "Journey not found.")
            if not session["active"] or session["expiresAt"] <= now:
                raise HTTPException(
                    410, "Cloud guidance paused. Start alerts again with fresh GPS."
                )
            device = tx.get(device_path(uid, session["deviceId"]))
            binding = tx.get(binding_path(device["recipient"])) if device else None
            if (
                not device
                or not device["enabled"]
                or device.get("journeyId") != journey_id
                or not binding
                or binding["path"] != device_path(uid, session["deviceId"])
            ):
                raise HTTPException(410, "Direction alerts have been stopped on this device.")
            if update.sequence <= session["sequence"]:
                return None, device, ProgressResult(accepted=False)
            if (now - session["lastSeenAt"]).total_seconds() < 2 and session["sequence"]:
                raise HTTPException(429, "Location updates are too frequent.")
            if update.navigation_token != session["routeVersion"]:
                if replacement is None:
                    raise HTTPException(409, "The replacement route has expired. Compare again.")
                session = {
                    **session,
                    "routeJson": json.dumps(replacement["route"]),
                    "routeId": replacement["route"]["id"],
                    "routeVersion": update.navigation_token,
                    "progress": 0,
                    "lastAlert": None,
                }
            alert, progress, arrived = next_direction(
                json.loads(session["routeJson"]), update.fix, session["progress"]
            )
            key = f"{session['routeVersion']}:{alert[0]}" if alert else None
            fresh_alert = bool(alert and key != session["lastAlert"])
            tx.set(
                path,
                {
                    **session,
                    "sequence": update.sequence,
                    "progress": progress,
                    "lastSeenAt": now,
                    "expiresAt": now + timedelta(seconds=30),
                    "lastAlert": key if fresh_alert else session["lastAlert"],
                    "active": not arrived,
                },
            )
            data = (
                {
                    "journeyId": journey_id,
                    "routeVersion": session["routeVersion"],
                    "sequence": str(update.sequence),
                    "instruction": alert[1],
                    "issuedAt": str(int(now.timestamp() * 1000)),
                    "expiresAt": str(int((now + timedelta(seconds=15)).timestamp() * 1000)),
                }
                if fresh_alert
                else None
            )
            return data, device, ProgressResult(accepted=True, arrived=arrived)

        data, device, result = self.gateway.transact(operation)
        if not data:
            return result
        # Recheck stop/reroute/device state after the transaction and before FCM submission.
        current = self.gateway.get(path)
        live_device = self.gateway.get(device_path(uid, current["deviceId"])) if current else None
        if (
            not current
            or current["routeVersion"] != data["routeVersion"]
            or current["sequence"] != int(data["sequence"])
            or (not current["active"] and not result.arrived)
            or not live_device
            or not live_device["enabled"]
            or live_device.get("journeyId") != journey_id
        ):
            result.alert = "suppressed"
            return result
        try:
            self.gateway.send(device, data)
            result.alert = "sent"
        except messaging.UnregisteredError:
            self.unregister(uid, current["deviceId"])
            result.alert = "failed"
        except Exception:
            # Push failure cannot interrupt the existing foreground GPS guidance.
            result.alert = "failed"
            reserved_key = current["lastAlert"]

            def release(tx):
                latest = tx.get(path)
                if (
                    latest
                    and latest["active"]
                    and latest["routeVersion"] == data["routeVersion"]
                    and latest["lastAlert"] == reserved_key
                ):
                    tx.set(path, {**latest, "lastAlert": None})

            try:
                # A later fresh fix may retry a failed submission for the same maneuver.
                self.gateway.transact(release)
            except Exception:
                pass
        return result
