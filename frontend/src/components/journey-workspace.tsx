"use client";

import { useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import { routeColor } from "@/lib/route-colors";
import { JourneyMap } from "@/components/journey-map";
import { checkHealth, compareJourney } from "@/lib/api";
import type { Coordinate, ComparisonResponse } from "@/types/api";

type PointFields = { lat: string; lng: string };
const blankPoint: PointFields = { lat: "", lng: "" };

function coordinate(fields: PointFields): Coordinate | null {
  if (!fields.lat.trim() || !fields.lng.trim()) return null;
  const lat = Number(fields.lat), lng = Number(fields.lng);
  return Number.isFinite(lat) && Number.isFinite(lng) && Math.abs(lat) <= 90 && Math.abs(lng) <= 180
    ? { lat, lng } : null;
}

function observationTime(value: string | null) {
  if (!value) return "Unavailable";
  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Kolkata",
  }).format(new Date(value)) + " IST";
}

export function JourneyWorkspace() {
  const [origin, setOrigin] = useState<PointFields>(blankPoint);
  const [destination, setDestination] = useState<PointFields>(blankPoint);
  const [activePoint, setActivePoint] = useState<"origin" | "destination">("origin");
  const [detour, setDetour] = useState(5);
  const [useReplay, setUseReplay] = useState(false);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [connection, setConnection] = useState("Connection not checked");
  const [checking, setChecking] = useState(false);

  const [result, setResult] = useState<ComparisonResponse | null>(null);
  const requestId = useRef(0);

  function invalidate() {
    requestId.current += 1;
    setResult(null);
    setBusy(false);
    setMessage("");
  }

  function selectPoint(point: Coordinate) {
    const fields = { lat: point.lat.toFixed(5), lng: point.lng.toFixed(5) };
    if (activePoint === "origin") { setOrigin(fields); setActivePoint("destination"); }
    else setDestination(fields);
    invalidate();
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const from = coordinate(origin), to = coordinate(destination);
    if (!from || !to) { setMessage("Enter valid coordinates for both locations, or select them on the map."); return; }
    const id = ++requestId.current;
    setBusy(true);
    setResult(null);
    setMessage("");
    try {
      const response = await compareJourney({ origin: from, destination: to, max_detour_minutes: detour, mode: "walking", data_mode: useReplay ? "replay" : "live" });
      if (id === requestId.current) { setResult(response); setMessage(response.warnings.join(" ")); }
    } catch (error) {
      if (id === requestId.current) setMessage(error instanceof TypeError ? "Could not connect to the route service. Start it and try again." : error instanceof Error ? error.message : "Please try again.");
    } finally { if (id === requestId.current) setBusy(false); }
  }

  async function testConnection() {
    setChecking(true);
    try { await checkHealth(); setConnection("Service connected"); }
    catch { setConnection("Service unavailable — start the backend and retry"); }
    finally { setChecking(false); }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <Link href="/" className="brand"><span className="brand-mark" aria-hidden="true">↗</span>AeroRoute</Link>
        <span className="preview-badge">Exposure baseline preview</span>
      </header>
      <main>
        <div className="page-intro">
          <p className="eyebrow">A little more time. A more informed walk.</p>
          <h1>Choose your walk<br /><span>within your time budget.</span></h1>
          <p>Compare journey time and estimated air-pollution exposure, with room for a detour that works for you.</p>
        </div>
        <div className="workspace">
          <aside className="journey-panel">
            <div className="panel-title"><h2>Plan a journey</h2><span>Walking</span></div>
            <form onSubmit={submit}>
              {(["origin", "destination"] as const).map((name) => {
                const fields = name === "origin" ? origin : destination;
                const update = name === "origin" ? setOrigin : setDestination;
                return (
                  <fieldset key={name} disabled={busy}>
                    <legend>{name === "origin" ? "Where are you starting?" : "Where are you going?"}</legend>
                    <button type="button" className={`point-picker ${activePoint === name ? "selected" : ""}`} onClick={() => setActivePoint(name)} aria-pressed={activePoint === name}>Select {name} on map</button>
                    <div className="coordinate-inputs">
                      <label>Latitude<input required aria-label={`${name} latitude`} type="number" step="any" min="-90" max="90" placeholder="28.6139" value={fields.lat} onChange={(event) => { update({ ...fields, lat: event.target.value }); invalidate(); }} /></label>
                      <label>Longitude<input required aria-label={`${name} longitude`} type="number" step="any" min="-180" max="180" placeholder="77.2090" value={fields.lng} onChange={(event) => { update({ ...fields, lng: event.target.value }); invalidate(); }} /></label>
                    </div>
                  </fieldset>
                );
              })}
              <div className="detour-heading"><label htmlFor="detour">Maximum extra time</label><output htmlFor="detour">{detour} min</output></div>
              <input id="detour" type="range" min="0" max="30" step="1" value={detour} disabled={busy} onChange={(event) => { setDetour(Number(event.target.value)); invalidate(); }} />
              <div className="range-labels"><span>No detour</span><span>30 minutes</span></div>
              <div className="replay-option">
                <label><input type="checkbox" checked={useReplay} disabled={busy} onChange={(event) => { setUseReplay(event.target.checked); invalidate(); }} />Use recorded pollution observations</label>
                <p>{useReplay ? "Historical estimates only. This does not describe current air quality." : "Live mode accepts recent observations only; stale data stays unavailable."}</p>
              </div>
              <button className="primary-button" disabled={busy} type="submit">{busy ? "Checking journey…" : "Compare walking routes"}<span aria-hidden="true">→</span></button>
              <p className="form-message" role="status" aria-live="polite">{message || "Compare evaluated walking routes. Estimates require sufficient nearby station support."}</p>
            </form>
          </aside>
          <div className="map-and-results">
            <JourneyMap origin={coordinate(origin)} destination={coordinate(destination)} activePoint={activePoint} onSelect={selectPoint} routes={result?.candidates ?? []} />
            <div className="result-previews" aria-label="Walking route results" aria-live="polite">
              {result ? result.candidates.length ? result.candidates.map((route, index) => (
                <div className="result-card" key={route.id} style={{ borderTopColor: routeColor(index) }}>
                  <p className="eyebrow"><span className="route-swatch" aria-hidden="true" style={{ backgroundColor: routeColor(index) }} />Route {index + 1} · {route.id === result.fastest_id ? "Fastest evaluated route" : `Walking alternative ${index + 1}`}</p>
                  {route.id === result.lowest_exposure_eligible_id && <p className="estimate-label">Lowest model estimate within your allowance</p>}
                  <h3>{(route.duration_seconds / 60).toFixed(1)} min · {(route.distance_metres / 1000).toFixed(2)} km</h3>
                  {route.via && <p>Waypoint-generated candidate · via {route.via.lat.toFixed(4)}, {route.via.lng.toFixed(4)}</p>}
                  <p>{route.within_budget ? "Within your time allowance" : "Outside your time allowance"}</p>
                  <p>Estimated exposure: {route.estimated_exposure === null ? "Unavailable" : `${route.estimated_exposure.toFixed(1)} ${route.exposure_unit}`}</p>
                  <p>Modeled-time support: {route.coverage_percent.toFixed(0)}%</p>
                </div>
              )) : <div className="result-card"><h3>No walking route found</h3><p>Try different starting and destination points.</p></div> : (
                <div className="result-card"><p className="eyebrow">Walking candidates</p><h3>Waiting for a journey</h3><p>Route distance, duration and time-budget eligibility will appear here.</p></div>
              )}
            </div>
          </div>
        </div>
        <section className="data-notice"><span className="notice-dot" aria-hidden="true" /><div>
          <h2>{result?.data_quality.data_mode === "replay" ? "Recorded-data replay · historical air observations" : "Data quality comes with the comparison."}</h2>
          {result ? <>
            <p>Observations: {observationTime(result.data_quality.observed_from)} to {observationTime(result.data_quality.observed_to)}.</p>
            <p>Snapshot fetched: {observationTime(result.data_quality.fetched_at)}. Time-filtered stations: {result.data_quality.station_count}.</p>
            {result.data_quality.provider_ids.length > 0 && <p>Observation sources: {result.data_quality.provider_ids.join(", ")}.</p>}
            {result.data_quality.data_mode === "replay" && <p>Historical reference: {observationTime(result.data_quality.reference_time)}. Walking directions are current; pollution observations are recorded.</p>}
            {result.status === "uncertain_difference" && <p className="uncertainty-notice">The difference is uncertain. A lower model estimate is not a reliable improvement recommendation.</p>}
            {result.status === "single_candidate" && <p>Only one walking candidate is available; no alternative-route improvement is claimed.</p>}
            {result.status === "no_lower_exposure_candidate" && <p>No eligible candidate has a lower estimated exposure than the fastest evaluated route.</p>}
            {result.status === "limited_data" && <p>Data support is insufficient to compare full-route exposures.</p>}
            {result.data_quality.model_version && <p className="model-caption">Model: {result.data_quality.model_version}. Sampling support is not measured street-level accuracy.</p>}
          </> : <p>Walking routes come from Mapbox. Station interpolation is a provisional model; source times and coverage appear with results. No improvement percentages are claimed before validation.</p>}
        </div></section>
      </main>
      <footer><p>Ambient exposure estimates · walking only · field validation still needed</p><div><span role="status">{connection}</span><button onClick={testConnection} disabled={checking}>{checking ? "Checking…" : "Check connection"}</button></div></footer>
    </div>
  );
}
