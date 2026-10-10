"use client";

import { useEffect, useRef, useState } from "react";
import mapboxgl from "mapbox-gl";
import { useJourneyNavigation } from "@/components/use-journey-navigation";
import { useDirectionAlerts } from "@/components/use-direction-alerts";
import { useAuth } from "@/components/auth-provider";
import { TrafficDetails } from "@/components/traffic-details";
import { routeFeatures } from "@/lib/navigation";
import { scheduleRouteDraw } from "@/lib/map-redraw";
import { ROUTE_COLOR } from "@/lib/route-colors";
import type { Coordinate, RouteCandidate } from "@/types/api";

type Props = {
  routes: RouteCandidate[];
  activeRouteId: string | null;
  selectedRouteId: string | null;
  onNavigationChange: (active: boolean) => void;
  onReroute: (coordinate: Coordinate, signal: AbortSignal) => Promise<void>;
  selectionReason: string;
  origin: Coordinate | null;
  destination: Coordinate | null;
  activePoint: "origin" | "destination" | null;
  onSelect: (coordinate: Coordinate) => void;
};

export function JourneyMap({ origin, destination, activePoint, onSelect, routes, activeRouteId, selectedRouteId, onNavigationChange, onReroute, selectionReason }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<mapboxgl.Map | null>(null);
  const callback = useRef(onSelect);
  const routeRef = useRef(routes);
  const activeRouteRef = useRef(activeRouteId);
  const [following, setFollowing] = useState(true);
  const [headingUp, setHeadingUp] = useState(false);
  const chosenRoute = routes.find(route => route.id === selectedRouteId);
  const navigation = useJourneyNavigation(chosenRoute, onNavigationChange, onReroute);
  const { running, fix, progress } = navigation;
  const auth = useAuth();
  const alerts = useDirectionAlerts(chosenRoute, running, fix, navigation.arrived);
  const [failed, setFailed] = useState(false);
  const token = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;

  function showRoutes(instance: mapboxgl.Map, candidates: RouteCandidate[], activeId: string | null, fit = false) {
    const data = routeFeatures(candidates, activeId);
    const source = instance.getSource("walking-routes") as mapboxgl.GeoJSONSource | undefined;
    if (source) source.setData(data);
    else {
      instance.addSource("walking-routes", { type: "geojson", data });
      instance.addLayer({ id: "route-alternatives", type: "line", source: "walking-routes",
        filter: ["==", ["get", "active"], false],
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": "#b2b8b3", "line-width": 4, "line-opacity": 0.7 } });
      instance.addLayer({ id: "walking-routes", type: "line", source: "walking-routes",
        filter: ["==", ["get", "active"], true],
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
    const instance = map.current;
    if (instance) return scheduleRouteDraw(instance, () => showRoutes(instance, routeRef.current, activeRouteRef.current, true));
  }, [routes]);

  useEffect(() => {
    activeRouteRef.current = activeRouteId;
    const instance = map.current;
    if (instance) return scheduleRouteDraw(instance, () => showRoutes(instance, routeRef.current, activeRouteRef.current));
  }, [activeRouteId]);

  useEffect(() => { callback.current = onSelect; }, [onSelect]);
  useEffect(() => {
    if (map.current) map.current.getCanvas().style.cursor = activePoint ? "crosshair" : "";
  }, [activePoint]);

  useEffect(() => {
    if (!token || !container.current) return;
    let instance: mapboxgl.Map | undefined;
    try {
      instance = new mapboxgl.Map({
        container: container.current,
        accessToken: token,
        style: "mapbox://styles/mapbox/light-v11",
        center: [77.229, 28.631], // Reviewed historical demo area; live support is checked separately.
        zoom: 13,
      });
      map.current = instance;
      instance.on("load", () => { if (instance) showRoutes(instance, routeRef.current, activeRouteRef.current, true); });
      instance.addControl(new mapboxgl.NavigationControl(), "top-right");
      instance.on("dragstart", () => setFollowing(false));
      instance.on("zoomstart", event => { if ((event as { originalEvent?: Event }).originalEvent) setFollowing(false); });
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
    if (destination) markers.push(new mapboxgl.Marker({ color: "#a1ce8f" }).setLngLat([destination.lng, destination.lat]).addTo(map.current));
    markers.forEach((marker, index) => {
      const name = origin && index === 0 ? "Starting point" : "Destination";
      marker.getElement().setAttribute("aria-label", name);
      marker.getElement().setAttribute("title", name);
      marker.getElement().querySelector("circle")?.setAttribute("fill", origin && index === 0 ? "#a1ce8f" : "#25614b");
    });
    if (!routeRef.current.length) {
      const points = [origin, destination].filter((point): point is Coordinate => point !== null);
      if (points.length === 1) map.current.flyTo({ center: [points[0].lng, points[0].lat], zoom: 14 });
      else if (points.length === 2) {
        const bounds = new mapboxgl.LngLatBounds();
        points.forEach(point => bounds.extend([point.lng, point.lat]));
        map.current.fitBounds(bounds, { padding: 60, maxZoom: 16 });
      }
    }
    return () => { markers.forEach((marker) => marker.remove()); };
  }, [origin, destination]);

  useEffect(() => {
    if (!fix || !map.current) return;
    const element = document.createElement("div");
    element.className = "gps-position";
    element.setAttribute("aria-label", "Your current location");
    element.setAttribute("title", `Your location · accuracy ±${Math.round(fix.accuracy)} m`);
    const marker = new mapboxgl.Marker({ element }).setLngLat([fix.lng, fix.lat]).addTo(map.current);
    return () => { marker.remove(); };
  }, [fix]);

  useEffect(() => {
    if (!running || !following || !fix || !map.current) return;
    map.current.easeTo({ center: [fix.lng, fix.lat], zoom: Math.max(16, map.current.getZoom()),
      bearing: headingUp ? fix.heading ?? map.current.getBearing() : 0, duration: 600 });
  }, [running, following, fix, headingUp]);

  useEffect(() => { map.current?.resize(); }, [running]);

  function overview() {
    const instance = map.current;
    if (!instance || !chosenRoute) return;
    setFollowing(false);
    const bounds = new mapboxgl.LngLatBounds();
    chosenRoute.geometry.coordinates.forEach(point => bounds.extend(point));
    instance.fitBounds(bounds, { padding: 60, maxZoom: 16, bearing: 0 });
  }

  const guidance = navigation.arrived ? "You have reached your destination"
    : navigation.message || (!fix ? "Waiting for your GPS location…"
      : !progress?.reliable ? `Weak GPS signal · accuracy ±${Math.round(fix.accuracy)} m`
      : progress.offRoute ? "Off route · checking your location before rerouting"
      : progress.instruction);

  return (
    <div className="journey-map-container">
    <section id="journey-map" className={`map-panel${running ? " navigation-active" : ""}`} aria-label="Journey map">
      {token && <div ref={container} className="map-canvas" />}
      {(!token || failed) && (
        <div className="map-placeholder">
          <span className="map-pin" aria-hidden="true">↗</span>
          <h2>{failed ? "Map unavailable" : "Your journey starts here"}</h2>
          <p>{failed ? "Search for a location or use your current location in the journey form." : "Enter two locations to prepare your walk. The interactive map will appear when map access is configured."}</p>
          <span className="map-caption">Central Delhi · historical demo area</span>
        </div>
      )}
      {token && !failed && (routes.length > 0 || origin || destination) && (
        <div className="route-legend" aria-label="Route preview" aria-live="polite">
          {routes.length > 0 && <span><i aria-hidden="true" style={{ backgroundColor: ROUTE_COLOR }} />Viewing route {routes.findIndex(route => route.id === activeRouteId) + 1}</span>}
          {origin && <span className="point-legend"><i aria-hidden="true" style={{ backgroundColor: "#a1ce8f", border: "3px solid #25614b" }} />Start</span>}
          {destination && <span className="point-legend"><i aria-hidden="true" style={{ backgroundColor: "#25614b", border: "3px solid #a1ce8f" }} />Destination</span>}
          {routes.length > 1 && <span className="route-preview-hint">Hover a card to preview · tap to select</span>}
          {chosenRoute?.traffic && <span className="route-preview-hint">{chosenRoute.traffic.coverage_percent === 0 ? "Traffic unknown" : "Traffic-profile routing"}</span>}
        </div>
      )}
      {token && !failed && chosenRoute && <div className="map-actions">
        {running && <button type="button" disabled={!fix} onClick={() => { setFollowing(true); if (fix) map.current?.easeTo({ center: [fix.lng, fix.lat], zoom: 16, bearing: headingUp ? fix.heading ?? 0 : 0 }); }}>◎ Recenter</button>}
        {running && <button type="button" onClick={() => setHeadingUp(!headingUp)}>{headingUp ? "North up" : "Travel direction"}</button>}
        <button type="button" onClick={overview}>↗ Route overview</button>
      </div>}
      {token && !failed && (activePoint || !routes.length) && <div className="map-instruction" role="status">{activePoint ? `Tap the map to set your ${activePoint}.` : "Explore the map · choose a location in the journey panel"}</div>}
    </section>
    {chosenRoute && <section className={`journey-navigation${running ? " is-running" : ""}`} aria-label="Journey navigation">
      <div className="navigation-summary">
        <p className="eyebrow">{running ? (following ? "Following your location" : "Map paused · recenter to follow") : `Selected route ${routes.findIndex(route => route.id === selectedRouteId) + 1}`}</p>
        <h2 aria-live="polite">{running || navigation.arrived ? guidance : `${(chosenRoute.duration_seconds / 60).toFixed(0)} min · ${(chosenRoute.distance_metres / 1000).toFixed(2)} km`}</h2>
        {running && progress?.reliable && !progress.offRoute && !navigation.message && <p className="navigation-progress">
          {progress.turnMetres !== null && <span>Next instruction in {Math.round(progress.turnMetres)} m · </span>}
          ~{Math.ceil(progress.remainingSeconds / 60)} min · {(progress.remainingMetres / 1000).toFixed(2)} km remaining
        </p>}
        {!running && !navigation.arrived && <p>{selectionReason}. Model differences remain uncertain.</p>}
        <TrafficDetails route={chosenRoute} />
        {!running && navigation.message && <p role="status">{navigation.message}</p>}
        {running && <p className="gps-caption">GPS ±{fix ? Math.round(fix.accuracy) : "—"} m · time remaining is approximate</p>}
      </div>
      {running ? <button type="button" className="navigation-stop" onClick={navigation.stop}>Stop journey</button>
        : <button type="button" className="navigation-start" onClick={() => { setFollowing(true); navigation.start(); }}>Start journey <span aria-hidden="true">↗</span></button>}
      <p className="navigation-note">{running ? "Automatic rerouting is on. GPS positions are sent to the route service and Mapbox for route updates. Stop ends tracking and cancels updates." : "Start follows GPS and automatically reroutes when you leave the path. Route updates share your GPS position with the route service and Mapbox. Location permission is required."}{chosenRoute.traffic && " Vehicle routes refresh about every two minutes with accurate GPS. Traffic may change between updates."}</p>
      <div className="direction-alerts">
        <button type="button" disabled={alerts.busy || !auth.ready || auth.busy} onClick={() => void (alerts.enabled ? alerts.disable() : alerts.enable())}>{alerts.busy ? "Enabling alerts…" : alerts.enabled ? "Disable direction alerts" : "Enable direction alerts"}</button>
        <p role="status">{alerts.message || (auth.user ? "Optional cloud alerts for the next turn. Keep this page open for live directions." : "Sign in with Google to receive cloud direction alerts. On-screen directions work as a guest.")}</p>
      </div>
    </section>}
    </div>
  );
}
