"""Check configured Firebase access without sending notifications or retaining probe data."""

import argparse
import json
import os
from uuid import uuid4

import firebase_admin
from firebase_admin import auth, messaging

from app.core.config import Settings
from app.core.firebase import FirebaseGateway


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write-check",
        action="store_true",
        help="Create/read/delete one isolated Firestore probe document to check write access.",
    )
    args = parser.parse_args()
    if os.getenv("FIREBASE_AUTH_EMULATOR_HOST") or os.getenv("FIRESTORE_EMULATOR_HOST"):
        parser.error("This command checks live Firebase. Unset emulator variables first.")
    gateway = FirebaseGateway(Settings())
    reference = None
    try:
        gateway.initialize()
        probe = "aeroroute-config-check-" + uuid4().hex
        gateway.get("users/" + probe)
        print("Firestore authenticated read: passed")
        try:
            auth.get_user(probe, app=gateway.app)
        except auth.UserNotFoundError:
            pass
        print("Firebase Auth user lookup: passed")
        if args.write_check:
            reference = gateway.database.collection("configurationChecks").document(probe)
            reference.set({"purpose": "temporary-access-check"}, timeout=8, retry=None)
            if reference.get(timeout=8, retry=None).to_dict() != {
                "purpose": "temporary-access-check"
            }:
                raise RuntimeError("Firestore write/read verification failed.")
            reference.delete(timeout=8, retry=None)
            reference = None
            print("Firestore write/read/delete: passed")
        # validate_only: no topic subscriber or device receives a message.
        messaging.send(
            messaging.Message(
                topic="aeroroute-configuration-check",
                data={"diagnostic": "configuration-check"},
                webpush=messaging.WebpushConfig(headers={"TTL": "15", "Urgency": "high"}),
            ),
            dry_run=True,
            app=gateway.app,
        )
        print("FCM authenticated validation (no delivery): passed")
        print(json.dumps({"project": gateway.app.project_id, "live_access": "verified"}))
        return 0
    except Exception as error:
        # Do not emit credential files, signed tokens or full HTTP response bodies.
        code = getattr(error, "code", None)
        print(
            json.dumps({"live_access": "failed", "error_type": type(error).__name__, "code": code})
        )
        return 1
    finally:
        if reference is not None:
            reference.delete(timeout=8, retry=None)
        if gateway.app is not None:
            firebase_admin.delete_app(gateway.app)


if __name__ == "__main__":
    raise SystemExit(main())
