# Frontend

Next.js 15 journey-route and exposure preview using TypeScript, Tailwind CSS and Mapbox GL JS.

Choose a location by Mapbox place search, browser current location (permission required), or explicit map-click selection. Map/search access requires a browser Mapbox token. With backend Mapbox access configured, route cards show genuine provider geometry, duration, distance and detour eligibility. Supported pollution scores include units, time-weighted station support and source times in IST. Recorded observations require the explicit replay checkbox; current air quality is never inferred from historical data. Lower model estimates are labelled uncertain until validation.

```bash
npm ci
cp .env.example .env.local
npm run dev
```

Open `http://localhost:3000` for the landing page; **Get Started** opens the product at `/journey`. Start the backend and use **Check connection**. The default same-origin proxy uses server-side `AEROROUTE_API_URL` (`http://127.0.0.1:8000`). Set optional `NEXT_PUBLIC_API_URL` for direct browser calls with backend CORS configured; the map token is optional for initial form testing. Copy environment templates only if the destination does not already contain your settings.

The landing is a Next.js page with the specified CloudFront background video, a bottom-left hero, responsive glass navigation and a one-shot entrance sequence. It has no demo card or page scroll; the journey page retains its normal scrolling. Reference Sans and Reference Display webfont files were not supplied: the CSS uses locally installed originals when available, otherwise its explicit Arial fallback. Supply the licensed webfonts to complete the exact typography match.

**About** opens `/about`, an explanation of the project using the same video, navigation, glass styling and entrance motion. It covers route comparison, time allowances, travel modes, Google sign-in and GPS guidance, alongside the limitations of the pollution and motorcycle estimates. Smaller screens can scroll the explanation inside the page while the background and header stay fixed.

The journey dashboard shares the landing's reference font families, subdued video background,
charcoal glass surfaces and white primary actions. Its [dark basemap](https://docs.mapbox.com/map-styles/reference/dark/)
uses bright green routes and green/cyan endpoint pins. The workspace keeps normal page scrolling,
responsive controls and visible keyboard focus. Reduced motion pauses the video and skips its
entrance effects; reduced transparency supplies solid panel backgrounds.

On desktop and tablet, the map measures half the expanded planner's height and adapts when
the form or route history changes. Starting a journey collapses the planner until Stop,
arrival or denied GPS permission restores planning. On mobile, the planner opens in a modal side drawer
from the [Bootstrap three-line menu icon](https://icons.getbootstrap.com/icons/list/);
Escape, the close button and a tap outside dismiss it. Comparing closes the drawer to show
the routes. Active mobile journeys fill the viewport with the map, GPS guidance and Stop
controls; locations and preferences remain available when planning resumes. Icon licensing
is recorded in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Guests can choose places, travel modes and time budgets, then compare routes. **Start journey** opens Google sign-in only when needed and starts GPS after successful authentication. Cancelling or failing login preserves the plan; editing the selected route while login is open cancels that pending start. Landing **Sign Up** opens Google directly and then enters the product with the same session. Existing signed-in users start navigation immediately.

Checks: `npm run lint`, `npm run typecheck`, `npm run build`. Then `npx playwright install chromium` and `npm run test:e2e`. CI installs Chromium/system dependencies and retains screenshots/traces as browser artifacts.

Browser fixtures run at desktop (1440 px) and mobile (390 px) widths: explicit replay/IST times, scored and limited states, detour/mode resets, no-route, recoverable provider failure and no horizontal overflow. Their responses are synthetic fixtures; local real-provider checks verify selected-location pins, route rendering and a scored historical journey. Amplify uses the repository-root build spec and `frontend` app root; follow [DEPLOYMENT.md](../documentations/DEPLOYMENT.md). See the [Friday handoff](../documentations/FRIDAY_HANDOFF.md) for remaining tasks.

## Travel modes

Walk uses Mapbox walking directions and the reviewed local walking-alternative policy.
Car uses Mapbox driving-traffic directions and native provider alternatives, with preserved step times.
Motorcycle currently uses the same traffic profile and car travel-time estimates, clearly labelled
in the UI and API warnings. Mapbox has no motorcycle profile: two-wheeler-only access rules,
restrictions and speeds are not modeled. No cycling profile or fabricated speed multiplier is used.
Vehicle times use available current/historical traffic estimates. Scores represent time-integrated outdoor ambient PM2.5,
not cabin air, ventilation, inhaled dose, emissions or an accuracy/safety guarantee.
The recorded preset resets to the reviewed walking journey. Switching travel modes clears old
results; each mode has a separate cache key. Apply backend migration `002_travel_modes.sql`
before deployment. Existing historical route-quality reviews cover walking only.

Routing source: [Mapbox Directions profiles](https://docs.mapbox.com/api/navigation/directions/).

## GPS journey controls

After comparing, the lowest modeled-exposure eligible route is selected, with fastest as
fallback when exposures are unavailable. Its line is green; alternative geometries stay grey.
A model-estimated difference does not establish a cleaner or healthier route.

After sign-in, Start journey requests browser GPS permission and locks the chosen route. The map follows
fresh locations; dragging/zooming or Route overview pauses the camera, while Recenter resumes
following. North up/Travel direction controls orientation when GPS heading is available.
Provider maneuver text and approximate remaining distance/time are derived from actual route
geometry. Stop, denial, arrival and component cleanup clear the GPS watch;
Stop also removes the live-location marker and cancels pending rerouting requests.

Automatic rerouting confirms off-route movement with accurate fixes (at most ±30 m)
separated by at least eight seconds. Returning to the path or weak GPS resets confirmation.
Only one comparison request runs at a time, with at least 30 seconds between attempts.
The off-route GPS coordinate is posted to the route service and Mapbox as the new origin;
the destination, travel mode, extra-time allowance and live/replay setting are preserved.
The lowest estimated-exposure eligible replacement is selected, with fastest as fallback;
GPS navigation continues without another Start. Failure/no route keeps the previous route
and retries on a later confirmed fix. The allowance applies to the remaining journey.
The Start panel explains this location sharing. Ordinary GPS fixes stay in browser memory;
map rendering still uses Mapbox map services. Route-service caching retains request coordinates
according to its configured cache/storage behavior.

Tracking requires a secure context (HTTPS or localhost), permission and browser/OS GPS support.
Background tabs can suspend updates. This is foreground browser guidance with approximate
projection/arrival logic, not field-tested navigation. No voice prompts, offline navigation
or vehicle-cabin exposure model is included. Off-route and
imprecise fixes are flagged rather than treated as reliable progress.

Sources: [browser GPS watching](https://developer.mozilla.org/en-US/docs/Web/API/Geolocation/watchPosition),
[Mapbox maneuver data](https://docs.mapbox.com/api/navigation/directions/).

## Traffic estimates

Vehicle requests use `driving-traffic` with distance/congestion annotations. Provider route and
step durations drive route ranking, time allowances and modeled exposure; typical durations
are only a comparison label. Reported congestion coverage and heavy/severe share are weighted
by route distance. Missing/unknown annotations never mean clear roads. The requested timestamp
is a local fetch time, not the provider's traffic-observation timestamp.

With accurate GPS (±30 m or better), active vehicle journeys refresh their remaining routes
approximately every two minutes. A refresh can select a different eligible replacement; it uses
the same route-update cancellation and error handling as off-route rerouting. The extra-time
allowance applies to the remaining journey. No reliable GPS means no traffic refresh; Stop
cancels updates. Between refreshes, remaining time is still a geometric approximation.
Vehicle cache entries expire within 60 seconds, and use one-minute identity buckets.

The Delhi demo returned traffic-profile times but only unknown congestion segments during
verification. This does not establish live traffic coverage in Delhi. See
[verification evidence](../documentations/TRAFFIC_VERIFICATION.md). Route/map indicators
explicitly show unknown congestion while keeping the selected route green and alternatives grey.

## Brand assets

The landing page, About page and dashboard share `src/components/app-logo.tsx`, which uses
`public/aeroroute-logo.png`. Root metadata supplies `public/favicon.ico` (16/32/48 px),
`public/icon.png` (512 px) and `public/apple-touch-icon.png` (180 px).
The original supplied image remains in `public/Gemini_Generated_Image_dxclnkdxclnkdxcl.png`.
The transparent cutout was prepared with the built-in imagegen tool; icon sizes were encoded
from that cutout with Sharp.

<details>
<summary>Final imagegen prompt</summary>

Edit ONLY the background of the attached image. This is an existing flat green/cyan logo, NOT a reference to redesign. Delete all white pixels to actual transparent alpha, including the white areas inside the logo. Delete the tiny faint sparkle at bottom right. Keep the original colored logo pixel-faithfully unchanged: same flat green sweeping ribbons, flat cyan pin outline, green ring with empty circular center, original shapes, proportions, edges, colors and shadows. Absolutely no glow, no halo, no blur, no neon, no black background, no filling the white areas with color. Return the same flat logo on a transparent background, centered with a small transparent margin.

</details>
