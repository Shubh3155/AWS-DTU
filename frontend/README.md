# Frontend

Initial Next.js 15 application using TypeScript, Tailwind CSS and Mapbox GL JS.

The form and detour control work now. Map-click selection is available when a browser token is configured. Route cards are explicitly pending; no invented route or pollution results are displayed.

```bash
npm ci
cp .env.example .env.local
npm run dev
```

Open `http://localhost:3000`. Start the backend and use **Check connection**. `NEXT_PUBLIC_API_URL` defaults to `http://localhost:8000`; the map token is optional for initial form testing. Copy environment templates only if the destination does not already contain your settings.

Checks: `npm run lint`, `npm run typecheck`, `npm run build`.

Real route rendering, freshness/coverage and uncertainty handling are next in the [implementation plan](../documentations/IMPLEMENTATION_PLAN.md).
