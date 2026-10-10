# Firebase setup and verification

The app implements Google sign-in, session restoration/logout, private recent route
searches and opt-in cloud direction alerts. Guest comparisons and foreground GPS
guidance remain available. Auth/Firestore emulator checks exercise desktop and
mobile layouts; they do not verify real Google OAuth or FCM delivery.

Google sign-in and the owner-only Firestore rules/indexes were deployed to
`aeroroute-auth-2026` on 10 October 2026. The TTL policy was omitted because billing
is disabled. `localhost` and `127.0.0.1` are authorized sign-in domains. The local
VAPID key and backend Admin credential are configured for the same project. Live
Auth lookup, Firestore read/write/delete and FCM validation pass. Actual Google
OAuth and notification delivery on a supported device remain manual verification gates.

## Configure the frontend

In `frontend/.env.local` (or the hosting environment), copy the public web-app
configuration from Firebase Project settings. The selected local project is
`aeroroute-auth-2026`. All frontend and backend Firebase settings must use the same
project.

```dotenv
NEXT_PUBLIC_FIREBASE_API_KEY=
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=
NEXT_PUBLIC_FIREBASE_PROJECT_ID=
NEXT_PUBLIC_FIREBASE_APP_ID=
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=
NEXT_PUBLIC_FIREBASE_VAPID_KEY=
```

The VAPID value is the public key under Project settings → Cloud Messaging → Web
Push certificates. Firebase Admin credentials belong exclusively on the backend.
Run `npm run build` after public configuration changes: `prebuild` bundles the
messaging worker at `public/firebase-messaging-sw.js`. `npm run dev` builds it too;
do not edit or commit that generated file.

In Firebase Authentication, enable Google and configure the support email. Add
`localhost`, `127.0.0.1` and the actual frontend hostname to Authorized domains.
If the fallback redirect flow is used on a hosted domain, follow Firebase's
[redirect deployment guidance](https://firebase.google.com/docs/auth/web/redirect-best-practices).
Test the deployed domain's Google popup and redirect flows before marking OAuth verified.

The pinned CLI can also check/add local or hosted sign-in domains while preserving
existing domains. From `frontend/`, with `firebase login` completed:

```bash
node scripts/firebase-auth-domains.mjs aeroroute-auth-2026
node scripts/firebase-auth-domains.mjs aeroroute-auth-2026 --apply
# Add the actual hosting hostname when it is available:
node scripts/firebase-auth-domains.mjs aeroroute-auth-2026 --apply your-frontend.example
```

The script validates the project against the frontend environment. `--apply`
modifies Authentication settings; the first command only checks them.

From `frontend/`, deploy the repository's private Firestore rules and indexes:

```bash
npx firebase deploy --config ../firebase.json --project aeroroute-auth-2026 --only auth,firestore:rules,firestore:indexes
```

This modifies the selected Firebase project. Rules default to deny, allow only the
authenticated owner to manage validated recent searches/profile fields, and prohibit
client writes to device/session records. Application expiry checks enforce the
30-second heartbeat. The project's billing is disabled, so the deployed index
configuration omits Firestore TTL; expired navigation records remain stored but
cannot send. If billing is enabled later, adding `ttl: true` to the `expiresAt`
field override enables asynchronous document cleanup independently of runtime expiry.

## Configure the backend for alerts

Install `backend/requirements.lock` and set:

```dotenv
AEROROUTE_FIREBASE_PROJECT_ID=aeroroute-auth-2026
AEROROUTE_FIREBASE_CREDENTIALS_PATH=/absolute/path/to/aeroroute-service-account.json
```

Alternatively, leave the credentials-path variable empty and use Application
Default Credentials through `GOOGLE_APPLICATION_CREDENTIALS` or the hosting
environment. The runtime identity needs Firestore document access, Firebase Auth
user lookup for revoked-token verification and FCM sending permissions. Keep the
credential file outside the repository and mount it securely on the server.
Restart FastAPI after changing its environment. Unconfigured cloud endpoints
return a visible configuration error; the guest routing service still starts.

The web SDK is pinned to 12.19.0 and Admin SDK to 7.7.x. Browser registration installs
`onRegistered` before calling `register`, then binds the confirmed installation ID
(FID) to the backend. It tracks FID changes and removes its observers on logout;
the server sends a data-only
`messaging.Message(fid=...)`. These matching APIs are intentional. Do not replace
only one side with the legacy token API.

To recheck live backend access, from `backend/` with its environment configured:

```bash
.venv/bin/python -m scripts.check_firebase --write-check
```

This checks Auth lookup and Firestore access, creates/reads/deletes one isolated
probe document, and validates an FCM message with `dry_run=True`. It sends no
notification and prints no credential or token values. The local private credential
is ignored by Git, excluded from Docker's build context and readable only by its owner.

## User flow and notification limits

- Google sign-in uses session persistence by default. **Remember me** preserves
  authentication across browser restarts; Firebase handles ID-token refresh.
- Each explicit completed comparison saves one history entry, including no-route
  and limited-data results. Reopening makes a fresh comparison. Delete and
  **Clear all** remove saved entries; logout preserves them for the next login.
- **Enable direction alerts** requests permission from a user click. **Start journey**
  starts foreground GPS; an authenticated cloud session starts on a fresh fix.
  Alerts follow provider maneuvers within 80 metres. An unreliable/off-route fix
  cannot generate a turn alert.
- Only one account/tab owns a browser's shared messaging installation. Stopping,
  disabling alerts, logout and account changes invalidate guidance. Arrival stops
  the session. Missing fresh progress for 30 seconds also expires it.
- Data messages expire after 15 seconds. Receivers reject stale routes, duplicate
  sequences and stopped journeys. Visible pages retain foreground guidance without
  a duplicate system notification. The worker attempts to close expired displayed
  alerts, and every notification click rechecks its expiry.
- Production push requires HTTPS and a browser with Push API/service-worker support.
  A suspended page may stop GPS updates; there is no continuous background-location
  guarantee. FCM submission success is not proof of delivery or timely directions.
  Follow the live on-screen instruction when the page is open.

Route receipts expire after 30 minutes and are held in the single-process backend's
bounded cache. Starting a session after expiry/restart requires a fresh comparison.
Active sessions keep their provider route in Firestore and survive backend restarts.
Recent-search documents contain search endpoints and metadata, not continuous GPS
traces or credential tokens. Navigation records keep a projected progress distance,
not a GPS trace.

## Checks

Use Node 22, Python 3.12 and Java 21 or later, with backend `.venv` and frontend
dependencies installed. From `frontend/`:

```bash
npx playwright install chromium
npm run test:firebase
```

This runs owner/isolation/validation rule tests, desktop/mobile Google-provider
emulator sign-in, persistence/history/logout/denied-permission browser tests, and
a real Admin SDK flow against the Auth/Firestore emulators. The project ID is
`demo-aeroroute`; no production data is used. FCM is mocked in backend tests because
the Emulator Suite does not emulate push delivery. CI runs the same suite.

Last local verification on 10 October: 143 backend tests passed (3 skipped), 54
production browser checks passed, and the Firebase suite passed 3 rule tests,
10 desktop/mobile user-flow tests and 1 Admin SDK emulator integration test.
Frontend lint, type checking and production build also passed.

For manual emulator development, start Auth/Firestore with project
`demo-aeroroute`, set all public Firebase variables to that demo project and
`NEXT_PUBLIC_FIREBASE_EMULATORS=true`. Backend emulators require both
`FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099` and
`FIRESTORE_EMULATOR_HOST=127.0.0.1:8085`, plus
`AEROROUTE_FIREBASE_PROJECT_ID=demo-aeroroute`. Production backend settings reject
emulators; never enable the frontend emulator flag in a production build.

Live verification still requires real Google sign-in on the authorized hostname
and a supported physical browser receiving an actual next-turn alert. Verify
rerouting, expiry, stop and logout there as well. AWS deployment remains deferred
at the user's request.
