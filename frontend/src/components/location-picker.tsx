"use client";

import { useEffect, useRef, useState } from "react";
import type { Coordinate } from "@/types/api";

export type JourneyLocation = { label: string; coordinate: Coordinate | null };
type Place = { id: string; label: string; coordinate: Coordinate };
type Props = {
  name: "origin" | "destination";
  value: JourneyLocation;
  disabled: boolean;
  picking: boolean;
  onChange: (value: JourneyLocation) => void;
  onPick: () => void;
};

export function LocationPicker({ name, value, disabled, picking, onChange, onPick }: Props) {
  const [places, setPlaces] = useState<Place[]>([]);
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);
  const sequence = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const token = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;

  // Ignore requests from a previous query, a map pick, or a demo selection.
  useEffect(() => {
    sequence.current += 1;
    controller.current?.abort();
    setPlaces([]); setNotice(""); setLoading(false);
    return () => { sequence.current += 1; controller.current?.abort(); };
  }, [value, disabled, picking]);

  function cancel() {
    sequence.current += 1;
    controller.current?.abort();
    setPlaces([]); setNotice(""); setLoading(false);
  }

  async function search() {
    cancel();
    if (value.label.trim().length < 2) { setNotice("Enter at least two letters to search."); return; }
    if (!token) { setNotice("Place search is unavailable until map access is configured."); return; }
    const id = ++sequence.current;
    const abort = new AbortController();
    controller.current = abort;
    const timeout = setTimeout(() => abort.abort(), 10000);
    setLoading(true);
    try {
      const query = new URLSearchParams({ q: value.label.trim(), access_token: token,
        autocomplete: "false", limit: "5", language: "en", proximity: "77.229,28.631" });
      const response = await fetch(`https://api.mapbox.com/search/geocode/v6/forward?${query}`, { signal: abort.signal, cache: "no-store" });
      if (!response.ok) throw new Error("Search is unavailable. Try again or choose on the map.");
      const data = await response.json();
      const matches: Place[] = (data.features ?? []).flatMap((feature: {
        id: string; geometry?: { coordinates?: number[] }; properties?: { full_address?: string; name?: string };
      }) => {
        const [lng, lat] = feature.geometry?.coordinates ?? [];
        const label = feature.properties?.full_address ?? feature.properties?.name;
        return label && Number.isFinite(lat) && Number.isFinite(lng) && Math.abs(lat) <= 90 && Math.abs(lng) <= 180
          ? [{ id: feature.id, label, coordinate: { lat, lng } }] : [];
      });
      if (id !== sequence.current) return;
      setPlaces(matches);
      setNotice(matches.length ? "Choose a matching location below." : "No matches found. Try a street, neighbourhood or city, or choose on the map.");
    } catch {
      if (id === sequence.current) setNotice("Search is unavailable. Try again or choose on the map.");
    } finally {
      clearTimeout(timeout);
      if (id === sequence.current) setLoading(false);
    }
  }

  function locate() {
    cancel();
    if (!navigator.geolocation) { setNotice("This browser does not support location. Search or choose on the map instead."); return; }
    const id = ++sequence.current;
    setLoading(true); setNotice("Waiting for your location permission…");
    navigator.geolocation.getCurrentPosition(position => {
      if (id !== sequence.current) return;
      setLoading(false); setNotice("");
      onChange({ label: "Current location", coordinate: { lat: position.coords.latitude, lng: position.coords.longitude } });
    }, error => {
      if (id !== sequence.current) return;
      setLoading(false);
      setNotice(error.code === 1 ? "Location permission was denied. Search or choose on the map instead."
        : "Could not find your location. Try again, search or choose on the map.");
    }, { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 });
  }

  return <fieldset disabled={disabled} className="location-picker">
    <legend>{name === "origin" ? "Where are you starting?" : "Where are you going?"}</legend>
    <div className="location-search">
      <input aria-label={`${name} location`} placeholder={name === "origin" ? "Search starting location" : "Search destination"}
        value={value.label} autoComplete="off" maxLength={200}
        onChange={event => { cancel(); onChange({ label: event.target.value, coordinate: null }); }}
        onKeyDown={event => { if (event.key === "Enter") { event.preventDefault(); void search(); } if (event.key === "Escape") cancel(); }} />
      <button type="button" aria-label={`Search ${name}`} disabled={loading} onClick={() => void search()}>Search</button>
    </div>
    {places.length > 0 && <div className="place-results" aria-label={`${name} search results`}>
      {places.map(place => <button key={place.id} type="button" onClick={() => { cancel(); onChange(place); }}>{place.label}<span aria-hidden="true">↗</span></button>)}
      <a href="https://www.mapbox.com/about/maps/" target="_blank" rel="noreferrer">© Mapbox</a>
    </div>}
    <div className="location-actions">
      <button type="button" disabled={loading} onClick={locate} aria-label={`Use current location for ${name}`}>◎ Current location</button>
      <button type="button" className={picking ? "selected" : ""} aria-pressed={picking} onClick={() => { cancel(); onPick(); }}>↗ Choose {name} on map</button>
    </div>
    <p className="location-status" role="status">{loading ? notice || "Searching…" : notice || (picking ? "Tap the map to place your pin." : value.coordinate ? "✓ Location selected" : "Search and select a match, or place a pin.")}</p>
  </fieldset>;
}
