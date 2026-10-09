"use client";

import { useEffect, useRef, useState } from "react";
import mapboxgl from "mapbox-gl";
import { ROUTE_COLOR } from "@/lib/route-colors";
import type { Coordinate, RouteCandidate } from "@/types/api";

type Props = {
  routes: RouteCandidate[];
  activeRouteId: string | null;
  origin: Coordinate | null;
  destination: Coordinate | null;
  activePoint: "origin" | "destination";
  onSelect: (coordinate: Coordinate) => void;
};

export function JourneyMap({ origin, destination, activePoint, onSelect, routes, activeRouteId }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<mapboxgl.Map | null>(null);
  const callback = useRef(onSelect);
  const routeRef = useRef(routes);
  const activeRouteRef = useRef(activeRouteId);
  const [failed, setFailed] = useState(false);
  const token = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;

  function showRoutes(instance: mapboxgl.Map, candidates: RouteCandidate[], activeId: string | null, fit = false) {
    const data = { type: "FeatureCollection" as const, features: candidates.filter(route => route.id === activeId).map(route => ({
      type: "Feature" as const, geometry: route.geometry, properties: {},
    })) };
    const source = instance.getSource("walking-routes") as mapboxgl.GeoJSONSource | undefined;
    if (source) source.setData(data);
    else {
      instance.addSource("walking-routes", { type: "geojson", data });
      instance.addLayer({ id: "walking-routes", type: "line", source: "walking-routes",
        layout: { "line-cap": "round", "line-join": "round" }, paint: {
        "line-color": ROUTE_COLOR,
        "line-width": 5, "line-opacity": 1,
      } });
    }
    if (fit && candidates.length) {
      const bounds = new mapboxgl.LngLatBounds();
      candidates.forEach((route) => route.geometry.coordinates.forEach((point) => bounds.extend(point)));
      instance.fitBounds(bounds, { padding: 60, maxZoom: 16 });
    }
  }

  useEffect(() => {
    routeRef.current = routes;
    if (map.current?.isStyleLoaded()) showRoutes(map.current, routes, activeRouteRef.current, true);
  }, [routes]);

  useEffect(() => {
    activeRouteRef.current = activeRouteId;
    if (map.current?.isStyleLoaded()) showRoutes(map.current, routeRef.current, activeRouteId);
  }, [activeRouteId]);

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
      instance.on("load", () => { if (instance) showRoutes(instance, routeRef.current, activeRouteRef.current, true); });
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
    if (destination) markers.push(new mapboxgl.Marker({ color: "#65846e" }).setLngLat([destination.lng, destination.lat]).addTo(map.current));
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
      {token && !failed && routes.length > 0 && (
        <div className="route-legend" aria-label="Route preview" aria-live="polite">
          <span><i aria-hidden="true" style={{ backgroundColor: ROUTE_COLOR }} />Viewing route {routes.findIndex(route => route.id === activeRouteId) + 1}</span>
          <span className="route-preview-hint">Hover a card to preview · tap to select</span>
        </div>
      )}
      {token && !failed && <div className="map-instruction">Click the map to set your {activePoint}.</div>}
    </section>
  );
}
