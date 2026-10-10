# Frontend

Next.js 15 journey-route and exposure preview using TypeScript, Tailwind CSS and Mapbox GL JS.

Choose a location by Mapbox place search, browser current location (permission required), or explicit map-click selection. Map/search access requires a browser Mapbox token. With backend Mapbox access configured, route cards show genuine provider geometry, duration, distance and detour eligibility. Supported pollution scores include units, time-weighted station support and source times in IST. Recorded observations require the explicit replay checkbox; current air quality is never inferred from historical data. Lower model estimates are labelled uncertain until validation.

```bash
npm ci
cp .env.example .env.local
npm run dev
```

Open `http://localhost:3000`. Start the backend and use **Check connection**. The default same-origin proxy uses server-side `AEROROUTE_API_URL` (`http://127.0.0.1:8000`). Set optional `NEXT_PUBLIC_API_URL` for direct browser calls with backend CORS configured; the map token is optional for initial form testing. Copy environment templates only if the destination does not already contain your settings.

Checks: `npm run lint`, `npm run typecheck`, `npm run build`. Then `npx playwright install chromium` and `npm run test:e2e`. CI installs Chromium/system dependencies and retains screenshots/traces as browser artifacts.

Browser fixtures run at desktop (1440 px) and mobile (390 px) widths: explicit replay/IST times, scored and limited states, detour/mode resets, no-route, recoverable provider failure and no horizontal overflow. Their responses are synthetic fixtures; local real-provider checks verify selected-location pins, route rendering and a scored historical journey. Amplify uses the repository-root build spec and `frontend` app root; follow [DEPLOYMENT.md](../documentations/DEPLOYMENT.md). See the [Friday handoff](../documentations/FRIDAY_HANDOFF.md) for remaining tasks.

## Travel modes

Walk uses Mapbox walking directions and the reviewed local walking-alternative policy.
Car uses Mapbox driving directions and native provider alternatives, with preserved step times.
Motorcycle currently uses the same driving profile and car travel-time estimates, clearly labelled
in the UI and API warnings. Mapbox has no motorcycle profile: two-wheeler-only access rules,
restrictions and speeds are not modeled. No cycling profile or fabricated speed multiplier is used.
Vehicle times exclude live traffic. Scores represent time-integrated outdoor ambient PM2.5,
not cabin air, ventilation, inhaled dose, emissions or an accuracy/safety guarantee.
The recorded preset resets to the reviewed walking journey. Switching travel modes clears old
results; each mode has a separate cache key. Apply backend migration `002_travel_modes.sql`
before deployment. Existing historical route-quality reviews cover walking only.

Routing source: [Mapbox Directions profiles](https://docs.mapbox.com/api/navigation/directions/).
