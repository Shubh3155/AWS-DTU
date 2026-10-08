"use client";

import { useRef, useState, type FormEvent } from "react";
import Link from "next/link";
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

export function JourneyWorkspace() {
  const [origin, setOrigin] = useState<PointFields>(blankPoint);
  const [destination, setDestination] = useState<PointFields>(blankPoint);
  const [activePoint, setActivePoint] = useState<"origin" | "destination">("origin");
  const [detour, setDetour] = useState(5);
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
      const response = await compareJourney({ origin: from, destination: to, max_detour_minutes: detour, mode: "walking" });
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
        <span className="preview-badge">Walking route preview</span>
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
              <button className="primary-button" disabled={busy} type="submit">{busy ? "Checking journey…" : "Compare walking routes"}<span aria-hidden="true">→</span></button>
              <p className="form-message" role="status" aria-live="polite">{message || "Find walking routes within your allowance. Pollution estimates are pending data validation."}</p>
            </form>
          </aside>
          <div className="map-and-results">
            <JourneyMap origin={coordinate(origin)} destination={coordinate(destination)} activePoint={activePoint} onSelect={selectPoint} routes={result?.candidates ?? []} />
            <div className="result-previews" aria-label="Walking route results" aria-live="polite">
              {result ? result.candidates.length ? result.candidates.map((route, index) => (
                <div className="result-card" key={route.id}>
                  <p className="eyebrow">{route.id === result.fastest_id ? "Fastest evaluated route" : `Walking alternative ${index + 1}`}</p>
                  <h3>{(route.duration_seconds / 60).toFixed(1)} min · {(route.distance_metres / 1000).toFixed(2)} km</h3>
                  <p>{route.within_budget ? "Within your time allowance" : "Outside your time allowance"}</p>
                  <p>Estimated exposure: {route.estimated_exposure === null ? "Unavailable" : `${route.estimated_exposure.toFixed(1)} ${route.exposure_unit}`}</p>
                </div>
              )) : <div className="result-card"><h3>No walking route found</h3><p>Try different starting and destination points.</p></div> : (
                <div className="result-card"><p className="eyebrow">Walking candidates</p><h3>Waiting for a journey</h3><p>Route distance, duration and time-budget eligibility will appear here.</p></div>
              )}
            </div>
          </div>
        </div>
        <section className="data-notice"><span className="notice-dot" aria-hidden="true" /><div><h2>Data quality comes with the comparison.</h2><p>Walking routes come from Mapbox. Pollution coverage and scoring are still being verified, so this preview does not recommend a lower-exposure route.</p></div></section>
      </main>
      <footer><p>Ambient exposure estimates · walking only · field validation still needed</p><div><span role="status">{connection}</span><button onClick={testConnection} disabled={checking}>{checking ? "Checking…" : "Check connection"}</button></div></footer>
    </div>
  );
}
