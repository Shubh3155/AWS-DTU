"use client";

import { useEffect, useRef, useState } from "react";
import mapboxgl from "mapbox-gl";
import type { Coordinate } from "@/types/api";

type Props = {
  origin: Coordinate | null;
  destination: Coordinate | null;
  activePoint: "origin" | "destination";
  onSelect: (coordinate: Coordinate) => void;
};

export function JourneyMap({ origin, destination, activePoint, onSelect }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<mapboxgl.Map | null>(null);
  const callback = useRef(onSelect);
  const [failed, setFailed] = useState(false);
  const token = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;

  useEffect(() => { callback.current = onSelect; }, [onSelect]);

  useEffect(() => {
    if (!token || !container.current) return;
    let instance: mapboxgl.Map | undefined;
    try {
      instance = new mapboxgl.Map({
        container: container.current,
        accessToken: token,
        style: "mapbox://styles/mapbox/light-v11",
        center: [77.209, 28.6139], // Delhi viewport only; not a selected pilot boundary.
        zoom: 12,
      });
      map.current = instance;
      instance.addControl(new mapboxgl.NavigationControl(), "top-right");
      instance.on("click", ({ lngLat }) => callback.current({ lat: lngLat.lat, lng: lngLat.lng }));
      instance.on("error", () => setFailed(true));
    } catch {
      setFailed(true);
    }
    return () => { instance?.remove(); map.current = null; };
  }, [token]);

  useEffect(() => {
    if (!map.current) return;
    const markers: mapboxgl.Marker[] = [];
    if (origin) markers.push(new mapboxgl.Marker({ color: "#25614b" }).setLngLat([origin.lng, origin.lat]).addTo(map.current));
    if (destination) markers.push(new mapboxgl.Marker({ color: "#ad7040" }).setLngLat([destination.lng, destination.lat]).addTo(map.current));
    return () => { markers.forEach((marker) => marker.remove()); };
  }, [origin, destination]);

  return (
    <section className="map-panel" aria-label="Journey map">
      {token && <div ref={container} className="map-canvas" />}
      {(!token || failed) && (
        <div className="map-placeholder">
          <span className="map-pin" aria-hidden="true">↗</span>
          <h2>{failed ? "Map unavailable" : "Your journey starts here"}</h2>
          <p>{failed ? "You can still enter coordinates in the journey form." : "Enter two locations to prepare your walk. The interactive map will appear when map access is configured."}</p>
          <span className="map-caption">Delhi · pilot area pending data checks</span>
        </div>
      )}
      {token && !failed && <div className="map-instruction">Click the map to set your {activePoint}.</div>}
    </section>
  );
}
