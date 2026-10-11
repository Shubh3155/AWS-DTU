"use client";

import { useEffect, useLayoutEffect, useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import { AppLogo } from "@/components/app-logo";
import { DashboardBackdrop } from "@/components/dashboard-backdrop";
import { PlannerCloseIcon, PlannerMenuIcon } from "@/components/planner-icons";
import { LocationPicker, type JourneyLocation } from "@/components/location-picker";
import { JourneyMap } from "@/components/journey-map";
import { TrafficDetails } from "@/components/traffic-details";
import { AccountMenu } from "@/components/account-menu";
import { useAuth } from "@/components/auth-provider";
import { RecentRoutes } from "@/components/recent-routes";
import { saveSearch, type SavedSearch } from "@/lib/route-history";
import { checkHealth, compareJourney } from "@/lib/api";
import type { Coordinate, ComparisonResponse, TravelMode } from "@/types/api";

const blankPoint: JourneyLocation = { label: "", coordinate: null };

function observationTime(value: string | null) {
  if (!value) return "Unavailable";
  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Kolkata",
  }).format(new Date(value)) + " IST";
}

export function JourneyWorkspace() {
  const auth = useAuth();
  const { registerCleanup } = auth;
  const currentUser = useRef(auth.user);
  currentUser.current = auth.user;
  const [saving, setSaving] = useState<{ uid: string; search: SavedSearch; error: boolean } | null>(null);
  const [origin, setOrigin] = useState<JourneyLocation>(blankPoint);
  const [destination, setDestination] = useState<JourneyLocation>(blankPoint);
  const [activePoint, setActivePoint] = useState<"origin" | "destination" | null>(null);
  const [mode, setMode] = useState<TravelMode>("walking");
  const modeLabel = mode === "walking" ? "walking" : mode === "driving" ? "car" : "motorcycle";
  const [detour, setDetour] = useState(5);
  const [useReplay, setUseReplay] = useState(false);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [navigating, setNavigating] = useState(false);
  const [mobile, setMobile] = useState(false);
  const [plannerOpen, setPlannerOpen] = useState(false);
  const plannerPanel = useRef<HTMLElement>(null);
  const plannerDrawer = useRef<HTMLDialogElement>(null);
  const workspace = useRef<HTMLDivElement>(null);
  const [connection, setConnection] = useState("Connection not checked");
  const [checking, setChecking] = useState(false);

  const [result, setResult] = useState<ComparisonResponse | null>(null);
  const requestId = useRef(0);
  const [selectedRouteId, setSelectedRouteId] = useState<string | null>(null);
  const [hoverRouteId, setHoverRouteId] = useState<string | null>(null);
  const [focusRouteId, setFocusRouteId] = useState<string | null>(null);
  const candidates = result?.candidates ?? [];
  const modeledAir = result?.data_quality.source_type === "model_forecast";
  const selectedId = candidates.some(route => route.id === selectedRouteId) ? selectedRouteId : result?.lowest_exposure_eligible_id ?? result?.fastest_id ?? candidates[0]?.id ?? null;
  const previewId = navigating ? selectedId : hoverRouteId ?? focusRouteId ?? selectedId;
  const activeRouteId = candidates.some(route => route.id === previewId) ? previewId : selectedId;

  useLayoutEffect(() => {
    const query = window.matchMedia("(max-width: 680px), (max-width: 950px) and (max-height: 500px) and (orientation: landscape)");
    function update() { setMobile(query.matches); setPlannerOpen(false); }
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  useLayoutEffect(() => {
    const drawer = plannerDrawer.current;
    if (!drawer) return;
    if (mobile && plannerOpen && !navigating) {
      if (!drawer.open) drawer.showModal();
    } else if (drawer.open) drawer.close();
  }, [mobile, plannerOpen, navigating]);

  useLayoutEffect(() => {
    const panel = plannerPanel.current;
    if (!panel || mobile || navigating) return;
    // Cache the expanded planner's height; collapsing it must not shrink the map.
    function resize() {
      const height = panel!.getBoundingClientRect().height;
      if (height > 0) workspace.current?.style.setProperty("--planning-map-height", `${height / 2}px`);
    }
    const observer = new ResizeObserver(resize);
    observer.observe(panel);
    resize();
    return () => observer.disconnect();
  }, [mobile, navigating]);

  function focusMap() {
    requestAnimationFrame(() => document.getElementById("journey-map")?.scrollIntoView({
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth", block: "start",
    }));
  }

  function navigationChanged(active: boolean) {
    setNavigating(active); setHoverRouteId(null); setFocusRouteId(null);
    if (active) { setPlannerOpen(false); setActivePoint(null); focusMap(); }
  }

  function resetRouteSelection() {
    setSelectedRouteId(null); setHoverRouteId(null); setFocusRouteId(null);
  }

  function invalidate() {
    requestId.current += 1;
    setResult(null);
    resetRouteSelection();
    setBusy(false);
    setMessage("");
    setSaving(null);
  }

  useEffect(() => registerCleanup(() => {
    requestId.current += 1;
    setResult(null); setOrigin(blankPoint); setDestination(blankPoint);
    setSelectedRouteId(null); setHoverRouteId(null); setFocusRouteId(null);
    setBusy(false); setMessage(""); setSaving(null); setActivePoint(null);
  }), [registerCleanup]);

  function loadDemo() {
    invalidate();
    setOrigin({ label: "Recorded Delhi start", coordinate: { lat: 28.6315, lng: 77.2167 } });
    setDestination({ label: "Recorded Delhi destination", coordinate: { lat: 28.6280, lng: 77.2410 } });
    setMode("walking");
    setDetour(5);
    setUseReplay(true);
    setActivePoint(null);
  }

  function selectPoint(point: Coordinate) {
    if (!activePoint || busy || navigating) return;
    const location = { label: activePoint === "origin" ? "Pinned starting point" : "Pinned destination", coordinate: point };
    if (activePoint === "origin") setOrigin(location);
    else setDestination(location);
    setActivePoint(null);
    invalidate();
    if (mobile) setPlannerOpen(true);
  }

  async function searchJourney(fromLocation: JourneyLocation, toLocation: JourneyLocation, travelMode: TravelMode, allowance: number, replay: boolean) {
    const from = fromLocation.coordinate, to = toLocation.coordinate;
    if (!from || !to) { setMessage("Choose both locations from search results, your current location, or the map."); return; }
    const id = ++requestId.current;
    setSaving(null);
    setBusy(true);
    setResult(null);
    resetRouteSelection();
    setMessage("");
    const owner = currentUser.current;
    const searchId = crypto.randomUUID();
    try {
      const response = await compareJourney({ origin: from, destination: to, max_detour_minutes: allowance, mode: travelMode, data_mode: replay ? "replay" : "live" });
      if (id === requestId.current) {
        setResult(response); setMessage(response.warnings.join(" "));
        if (mobile) { setPlannerOpen(false); focusMap(); }
        if (owner && currentUser.current?.uid === owner.uid) {
          const search: SavedSearch = { id: searchId, origin: { ...from, label: fromLocation.label.slice(0, 500) },
            destination: { ...to, label: toLocation.label.slice(0, 500) }, mode: travelMode,
            detourMinutes: allowance, dataMode: replay ? "replay" : "live", status: response.status,
            selectedRouteId: response.lowest_exposure_eligible_id ?? response.fastest_id,
            dataVersion: response.data_quality.data_version, modelVersion: response.data_quality.model_version };
          void saveSearch(owner, search).then(() => {
            if (currentUser.current?.uid === owner.uid && id === requestId.current) setSaving(null);
          }).catch(() => {
            if (currentUser.current?.uid === owner.uid && id === requestId.current) setSaving({ uid: owner.uid, search, error: true });
          });
        }
      }
    } catch (error) {
      if (id === requestId.current) setMessage(error instanceof TypeError ? "Could not connect to the route service. Start it and try again." : error instanceof Error ? error.message : "Please try again.");
    } finally { if (id === requestId.current) setBusy(false); }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await searchJourney(origin, destination, mode, detour, useReplay);
  }

  function reopen(search: SavedSearch) {
    invalidate();
    const from = { label: search.origin.label, coordinate: { lat: search.origin.lat, lng: search.origin.lng } };
    const to = { label: search.destination.label, coordinate: { lat: search.destination.lat, lng: search.destination.lng } };
    setOrigin(from); setDestination(to); setMode(search.mode); setDetour(search.detourMinutes);
    setUseReplay(search.dataMode === "replay"); setActivePoint(null);
    void searchJourney(from, to, search.mode, search.detourMinutes, search.dataMode === "replay");
  }

  async function retrySave() {
    const owner = auth.user, pending = saving;
    if (!owner || !pending || pending.uid !== owner.uid) return;
    const id = requestId.current;
    setSaving({ ...pending, error: false });
    try { await saveSearch(owner, pending.search); if (currentUser.current?.uid === owner.uid && id === requestId.current) setSaving(null); }
    catch { if (currentUser.current?.uid === owner.uid && id === requestId.current) setSaving({ ...pending, error: true }); }
  }

  async function testConnection() {
    setChecking(true);
    try { await checkHealth(); setConnection("Service connected"); }
    catch { setConnection("Service unavailable — start the backend and retry"); }
    finally { setChecking(false); }
  }

  async function reroute(from: Coordinate, signal: AbortSignal) {
    const to = destination.coordinate;
    if (!to) throw new Error("Choose a destination before rerouting.");
    const response = await compareJourney({ origin: from, destination: to, max_detour_minutes: detour,
      mode, data_mode: useReplay ? "replay" : "live" }, signal);
    if (signal.aborted) return;
    if (!response.candidates.length) throw new Error("No replacement route found.");
    setOrigin({ label: "Rerouted from GPS position", coordinate: from });
    setResult(response);
    resetRouteSelection();
    setMessage(response.warnings.join(" "));
  }

  const planner = (
          <aside ref={plannerPanel} className={`journey-panel${navigating ? " is-collapsed" : ""}`} aria-labelledby="journey-planner-title">
            <div className="panel-title"><h2 id="journey-planner-title">Plan a journey</h2><span>{navigating ? "In progress" : modeLabel === "car" ? "Car" : modeLabel === "motorcycle" ? "Motorcycle" : "Walking"}</span>
              <button type="button" className="planner-close" aria-label="Close journey planner" onClick={() => setPlannerOpen(false)}><PlannerCloseIcon /></button>
            </div>
            <div className="planner-body" hidden={navigating} inert={navigating}>
            <button className="demo-button" type="button" onClick={loadDemo} disabled={busy || navigating}>Try recorded Delhi journey</button>
            <form onSubmit={submit}>
              <fieldset className="travel-mode" disabled={busy || navigating}>
                <legend>How are you travelling?</legend>
                <div role="group" aria-label="Travel mode">
                  {(["walking", "driving", "motorcycle"] as const).map(option => <button key={option} type="button"
                    aria-pressed={mode === option} onClick={() => { setMode(option); invalidate(); }}>
                    {option === "walking" ? "Walk" : option === "driving" ? "Car" : "Motorcycle"}
                  </button>)}
                </div>
                {mode !== "walking" && <p className="mode-note">{mode === "motorcycle"
                  ? "Car routing estimate · motorcycle restrictions and speeds are not modeled."
                  : "Outdoor air along your route · cabin filtration is not modeled."} Uses traffic-profile travel estimates where available; missing congestion is shown as unknown.</p>}
              </fieldset>
              {(["origin", "destination"] as const).map((name) => {
                return <LocationPicker key={name} name={name} value={name === "origin" ? origin : destination}
                  disabled={busy || navigating} picking={activePoint === name}
                  onPick={() => {
                    setActivePoint(activePoint === name ? null : name);
                    if (activePoint !== name) { setPlannerOpen(false); focusMap(); }
                  }}
                  onChange={location => {
                    if (name === "origin") setOrigin(location); else setDestination(location);
                    setActivePoint(null); invalidate();
                  }} />;
              })}
              <div className="detour-heading"><label htmlFor="detour">Maximum extra time</label><output htmlFor="detour">{detour} min</output></div>
              <input id="detour" type="range" min="0" max="30" step="1" value={detour} disabled={busy || navigating} onChange={(event) => { setDetour(Number(event.target.value)); invalidate(); }} />
              <div className="range-labels"><span>No detour</span><span>30 minutes</span></div>
              <div className="replay-option">
                <label><input type="checkbox" checked={useReplay} disabled={busy || navigating} onChange={(event) => { setUseReplay(event.target.checked); invalidate(); }} />Use recorded pollution observations</label>
                <p>{useReplay ? "Historical estimates only. This does not describe current air quality." : "Live mode accepts recent observations only; stale data stays unavailable."}</p>
              </div>
              <button className="primary-button" disabled={busy || navigating} type="submit">{busy ? "Checking journey…" : `Compare ${modeLabel} routes`}<span aria-hidden="true">→</span></button>
              <p className="form-message" role="status" aria-live="polite">{message || "Compare evaluated routes. Estimates require sufficient nearby station support."}</p>
            </form>
            {saving && saving.uid === auth.user?.uid && <p className="save-status" role="status">{saving.error ? <>Route not saved. <button type="button" onClick={() => void retrySave()}>Retry saving</button></> : "Saving route…"}</p>}
            <RecentRoutes disabled={busy || navigating} onReopen={reopen} />
            </div>
          </aside>
  );

  return (
    <div className={`app-shell${navigating ? " is-navigating" : ""}${mobile && plannerOpen ? " planner-open" : ""}`}>
      <DashboardBackdrop />
      <header className="topbar">
        <Link href="/" className="brand"><AppLogo className="brand-mark" />AeroRoute</Link>
        <div className="topbar-actions">
          <AccountMenu />
          <button type="button" className="planner-toggle" aria-label="Open journey planner" aria-controls="journey-planner-drawer"
            aria-expanded={plannerOpen} disabled={navigating} onClick={() => setPlannerOpen(true)}><PlannerMenuIcon /></button>
        </div>
      </header>
      <main>
        <div className="page-intro" id="about">
          <p className="eyebrow">A little more time. A more informed journey.</p>
          <h1>Choose your journey<br /><span>within your time budget.</span></h1>
          <p>Compare journey time and estimated air-pollution exposure, with room for a detour that works for you.</p>
        </div>
        <div ref={workspace} className={`workspace${navigating ? " is-navigating" : ""}`}>
          {mobile ? <dialog ref={plannerDrawer} id="journey-planner-drawer" className="planner-drawer"
            aria-labelledby="journey-planner-title" onClose={() => setPlannerOpen(false)} onCancel={() => setPlannerOpen(false)}
            onClick={event => {
              if (event.target !== event.currentTarget) return;
              const bounds = event.currentTarget.getBoundingClientRect();
              if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) setPlannerOpen(false);
            }}>{planner}</dialog> : planner}
          <div className="map-and-results">
            <JourneyMap origin={origin.coordinate} destination={destination.coordinate} activePoint={busy || navigating ? null : activePoint} onSelect={selectPoint} routes={candidates} activeRouteId={activeRouteId} selectedRouteId={selectedId}
              onReroute={reroute}
              onNavigationChange={navigationChanged}
              selectionReason={selectedId === result?.lowest_exposure_eligible_id ? "Lowest model estimate within your allowance" : selectedId === result?.fastest_id ? result.lowest_exposure_eligible_id ? "Fastest evaluated route" : "Fastest evaluated route · exposure unavailable" : "Manually selected route"} />
            <div className="result-previews" aria-label="Travel route results" aria-live="polite">
              {result ? result.candidates.length ? result.candidates.map((route, index) => (
                <div className={`result-card${route.id === activeRouteId ? " route-active" : ""}`} key={route.id}
                  onPointerMove={event => { if (!navigating && event.pointerType === "mouse") setHoverRouteId(route.id); }} onPointerLeave={() => setHoverRouteId(null)}
                  onFocus={() => { if (navigating) return; setFocusRouteId(route.id); setHoverRouteId(null); }} onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) setFocusRouteId(null); }}>
                  <p className="eyebrow">Route {index + 1} · {route.id === result.fastest_id ? "Fastest evaluated route" : `Alternative ${index + 1}`}</p>
                  {route.id === result.lowest_exposure_eligible_id && <p className="estimate-label">Lowest model estimate within your allowance</p>}
                  <h3>{(route.duration_seconds / 60).toFixed(1)} min · {(route.distance_metres / 1000).toFixed(2)} km</h3>
                  <TrafficDetails route={route} />
                  {route.via && <p>Waypoint-generated candidate · via {route.via.lat.toFixed(4)}, {route.via.lng.toFixed(4)}</p>}
                  <p>{route.within_budget ? "Within your time allowance" : "Outside your time allowance"}</p>
                  <p>Estimated exposure: {route.estimated_exposure === null ? "Unavailable" : `${route.estimated_exposure.toFixed(1)} ${route.exposure_unit}`}</p>
                  <p>Air-quality time coverage: {route.coverage_percent.toFixed(0)}%</p>
                  <button type="button" disabled={navigating} className="show-route" aria-label={`Show route ${index + 1} on map`} aria-pressed={route.id === selectedId} onClick={() => { setSelectedRouteId(route.id); setHoverRouteId(null); setFocusRouteId(route.id); }}>{route.id === activeRouteId ? "Showing on map" : "Show on map"}<span aria-hidden="true">↗</span></button>
                </div>
              )) : <div className="result-card"><h3>No route found</h3><p>Try different starting and destination points.</p></div> : (
                <div className="result-card"><p className="eyebrow">Route candidates</p><h3>Waiting for a journey</h3><p>Route distance, duration and time-budget eligibility will appear here.</p></div>
              )}
            </div>
          </div>
        </div>
        <section className="data-notice"><span className="notice-dot" aria-hidden="true" /><div>
          <h2>{result?.data_quality.data_mode === "replay" ? "Recorded-data replay · historical air observations" : modeledAir ? "Current regional air-quality forecast" : "Data quality comes with the comparison."}</h2>
          {result ? <>
            {modeledAir ? <>
              <p>Forecast valid: {observationTime(result.data_quality.valid_from ?? null)} to {observationTime(result.data_quality.valid_to ?? null)}.</p>
              <p>API fetched: {observationTime(result.data_quality.fetched_at)}. Route sampling regions: {result.data_quality.sample_count ?? 0}.</p>
              <p>Regional model resolution: approximately {result.data_quality.spatial_resolution_km ?? 45} km. Time coverage shows data availability, not accuracy or monitoring-station coverage.</p>
            </> : <>
              <p>Observations: {observationTime(result.data_quality.observed_from)} to {observationTime(result.data_quality.observed_to)}.</p>
              <p>Snapshot fetched: {observationTime(result.data_quality.fetched_at)}. Time-filtered stations: {result.data_quality.station_count}.</p>
            </>}
            {result.data_quality.provider_ids.length > 0 && <p>{modeledAir ? "Forecast sources" : "Observation sources"}: {result.data_quality.provider_ids.join(", ")}.</p>}
            {modeledAir && <p>Air quality data: <a href="https://open-meteo.com/en/docs/air-quality-api" target="_blank" rel="noreferrer">Open-Meteo</a> and <a href="https://atmosphere.copernicus.eu/" target="_blank" rel="noreferrer">Copernicus CAMS</a>.</p>}
            {result.data_quality.data_mode === "replay" && <p>Historical reference: {observationTime(result.data_quality.reference_time)}. Directions are current; pollution observations are recorded.</p>}
            {result.status === "uncertain_difference" && <p className="uncertainty-notice">The difference is uncertain. A lower model estimate is not a reliable improvement recommendation.</p>}
            {result.status === "single_candidate" && <p>Only one route candidate is available; no alternative-route improvement is claimed.</p>}
            {result.status === "no_lower_exposure_candidate" && <p>No eligible candidate has a lower estimated exposure than the fastest evaluated route.</p>}
            {result.status === "limited_data" && <p>Data support is insufficient to compare full-route exposures.</p>}
            {result.data_quality.model_version && <p className="model-caption">Model: {result.data_quality.model_version}. {modeledAir ? "The coarse regional forecast cannot reliably distinguish nearby streets. Exposure uses the current field throughout the journey; arrival-time changes are not predicted." : "Historical validation errors vary substantially between periods; station support does not establish street-level accuracy."}</p>}
          </> : <p>Routes come from Mapbox. Live mode fetches current regional PM2.5 forecasts along each route; recorded replay uses historical station observations. Source times and coverage appear with results.</p>}
        </div></section>
      </main>
      <footer><p>Ambient exposure estimates · field validation still needed</p><div><span role="status">{connection}</span><button onClick={testConnection} disabled={checking}>{checking ? "Checking…" : "Check connection"}</button></div></footer>
    </div>
  );
}
