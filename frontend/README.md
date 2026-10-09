# Frontend

Next.js 15 walking-route and exposure preview using TypeScript, Tailwind CSS and Mapbox GL JS.

Map-click selection is available when a browser token is configured. With backend Mapbox access configured, route cards show genuine walking geometry, duration, distance and detour eligibility. Supported pollution scores include units, time-weighted station support and source times in IST. Recorded observations require the explicit replay checkbox; current air quality is never inferred from historical data. Lower model estimates are labelled uncertain until validation.

```bash
npm ci
cp .env.example .env.local
npm run dev
```

Open `http://localhost:3000`. Start the backend and use **Check connection**. The default same-origin proxy uses server-side `AEROROUTE_API_URL` (`http://127.0.0.1:8000`). Set optional `NEXT_PUBLIC_API_URL` for direct browser calls with backend CORS configured; the map token is optional for initial form testing. Copy environment templates only if the destination does not already contain your settings.

Checks: `npm run lint`, `npm run typecheck`, `npm run build`.

Real-data integration, mobile/browser checks and deployment remain in the [implementation plan](../documentations/IMPLEMENTATION_PLAN.md). See the [baseline handoff](../documentations/EXPOSURE_BASELINE.md) for the scoring policy and next tasks.
