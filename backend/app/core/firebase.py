"""Lazy Firebase Admin access. Guest routing starts without Firebase credentials."""

import os
from threading import Lock
from uuid import uuid4

import firebase_admin
from fastapi import HTTPException, Request
from firebase_admin import auth, credentials, exceptions, firestore, messaging
from google.auth.credentials import AnonymousCredentials
from google.auth.exceptions import DefaultCredentialsError

from app.core.config import Settings


class FirebaseTransaction:
    def __init__(self, database, transaction):
        self.database = database
        self.transaction = transaction

    def get(self, path):
        return (
            self.database.document(path)
            .get(transaction=self.transaction, timeout=8, retry=None)
            .to_dict()
        )

    def set(self, path, data):
        self.transaction.set(self.database.document(path), data)

    def delete(self, path):
        self.transaction.delete(self.database.document(path))


class EmulatorCredentials(credentials.Base):
    def get_credential(self):
        return AnonymousCredentials()


class FirebaseGateway:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.app = None
        self.database = None
        self.lock = Lock()

    def initialize(self):
        with self.lock:
            if self.app is not None:
                return
            if not self.settings.firebase_project_id:
                raise HTTPException(503, "Cloud alerts are not configured yet.")
            if self.settings.environment == "production" and (
                os.getenv("FIREBASE_AUTH_EMULATOR_HOST") or os.getenv("FIRESTORE_EMULATOR_HOST")
            ):
                raise HTTPException(503, "Firebase emulators cannot be used in production.")
            try:
                emulators = os.getenv("FIREBASE_AUTH_EMULATOR_HOST") and os.getenv(
                    "FIRESTORE_EMULATOR_HOST"
                )
                if emulators and not self.settings.firebase_project_id.startswith("demo-"):
                    raise HTTPException(503, "Emulators require a demo Firebase project.")
                credential = (
                    EmulatorCredentials()
                    if emulators
                    else (
                        credentials.Certificate(self.settings.firebase_credentials_path)
                        if self.settings.firebase_credentials_path
                        else credentials.ApplicationDefault()
                    )
                )
                app = firebase_admin.initialize_app(
                    credential,
                    {"projectId": self.settings.firebase_project_id, "httpTimeout": 8},
                    name=f"aeroroute-{uuid4().hex}",
                )
                database = firestore.client(app=app)
            except (DefaultCredentialsError, ValueError, OSError):
                raise HTTPException(
                    503, "Cloud alerts need backend Firebase credentials."
                ) from None
            self.app, self.database = app, database

    def verify(self, token):
        self.initialize()
        try:
            decoded = auth.verify_id_token(token, app=self.app, check_revoked=True)
            return decoded["uid"]
        except auth.CertificateFetchError:
            raise HTTPException(503, "Sign-in verification is temporarily unavailable.") from None
        except (exceptions.FirebaseError, ValueError, KeyError):
            raise HTTPException(401, "Your session has expired. Sign in again.") from None

    def transact(self, callback):
        self.initialize()

        @firestore.transactional
        def operation(transaction):
            return callback(FirebaseTransaction(self.database, transaction))

        return operation(self.database.transaction())

    def get(self, path):
        self.initialize()
        return self.database.document(path).get(timeout=8, retry=None).to_dict()

    def send(self, device, data):
        self.initialize()
        recipient = {device["recipientKind"]: device["recipient"]}
        return messaging.send(
            messaging.Message(
                data=data,
                webpush=messaging.WebpushConfig(headers={"TTL": "15", "Urgency": "high"}),
                **recipient,
            ),
            app=self.app,
        )


def signed_in_uid(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip() or len(token) > 8192:
        raise HTTPException(401, "Sign in to use cloud direction alerts.")
    return request.app.state.firebase.verify(token.strip())
