"use client";

import { useEffect, useRef, useState } from "react";
import mapboxgl from "mapbox-gl";
import { routeColor } from "@/lib/route-colors";
import type { Coordinate, RouteCandidate } from "@/types/api";

type Props = {
  routes: RouteCandidate[];
  origin: Coordinate | null;
  destination: Coordinate | null;
  activePoint: "origin" | "destination";
  onSelect: (coordinate: Coordinate) => void;
};

export function JourneyMap({ origin, destination, activePoint, onSelect, routes }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<mapboxgl.Map | null>(null);
  const callback = useRef(onSelect);
  const routeRef = useRef(routes);
  const [failed, setFailed] = useState(false);
  const token = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;

  function showRoutes(instance: mapboxgl.Map, candidates: RouteCandidate[]) {
    const data = { type: "FeatureCollection" as const, features: candidates.map((route, index) => ({
      type: "Feature" as const, geometry: route.geometry, properties: { color: routeColor(index), width: 9 - index * 3, order: index },
    })) };
    const source = instance.getSource("walking-routes") as mapboxgl.GeoJSONSource | undefined;
    if (source) source.setData(data);
    else {
      instance.addSource("walking-routes", { type: "geojson", data });
      instance.addLayer({ id: "walking-routes", type: "line", source: "walking-routes",
        layout: { "line-sort-key": ["get", "order"], "line-cap": "round", "line-join": "round" }, paint: {
        "line-color": ["get", "color"],
        "line-width": ["get", "width"], "line-opacity": 1,
      } });
    }
    if (candidates.length) {
      const bounds = new mapboxgl.LngLatBounds();
      candidates.forEach((route) => route.geometry.coordinates.forEach((point) => bounds.extend(point)));
      instance.fitBounds(bounds, { padding: 60, maxZoom: 16 });
    }
  }

  useEffect(() => {
    routeRef.current = routes;
    if (map.current?.isStyleLoaded()) showRoutes(map.current, routes);
  }, [routes]);

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
      instance.on("load", () => { if (instance) showRoutes(instance, routeRef.current); });
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
      {token && !failed && routes.length > 0 && (
        <div className="route-legend" aria-label="Route colours">
          {routes.map((route, index) => <span key={route.id}><i aria-hidden="true" style={{ backgroundColor: routeColor(index) }} />Route {index + 1}</span>)}
        </div>
      )}
      {token && !failed && <div className="map-instruction">Click the map to set your {activePoint}.</div>}
    </section>
  );
}
