"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { journeyProgress, type LocationFix } from "@/lib/navigation";
import type { Coordinate, RouteCandidate } from "@/types/api";
import { useAuth } from "@/components/auth-provider";

export function useJourneyNavigation(route: RouteCandidate | undefined, onChange: (active: boolean) => void,
  onReroute: (coordinate: Coordinate, signal: AbortSignal) => Promise<void>) {
  const { registerCleanup } = useAuth();
  const [running, setRunning] = useState(false);
  const [fix, setFix] = useState<LocationFix | null>(null);
  const [message, setMessage] = useState("");
  const [arrived, setArrived] = useState(false);
  const callback = useRef(onChange);
  const rerouteCallback = useRef(onReroute);
  const pending = useRef<AbortController | null>(null);
  const offRouteSince = useRef<number | null>(null);
  const lastAttempt = useRef<number | null>(null);
  const lastTrafficRefresh = useRef(0);
  const rerouteError = useRef("");
  const previous = useRef(0);
  const latestTimestamp = useRef(0);
  useEffect(() => { callback.current = onChange; }, [onChange]);
  useEffect(() => { rerouteCallback.current = onReroute; }, [onReroute]);
  const stop = useCallback(() => {
    if (pending.current) setMessage("Rerouting canceled.");
    pending.current?.abort(); pending.current = null;
    offRouteSince.current = null;
    setRunning(false); setFix(null); callback.current(false);
  }, []);
  useEffect(() => registerCleanup(stop), [registerCleanup, stop]);
  function start() {
    if (!route) return;
    if (!navigator.geolocation) { setMessage("Location is unavailable in this browser."); return; }
    previous.current = 0; latestTimestamp.current = 0;
    offRouteSince.current = null; lastAttempt.current = null; rerouteError.current = "";
    lastTrafficRefresh.current = Date.now();
    setFix(null); setArrived(false); setMessage("Waiting for GPS permission and a location fix…");
    setRunning(true); callback.current(true);
  }
  // A replacement route resets progress while continuing the active GPS journey.
  useEffect(() => {
    setFix(null); setArrived(false); setMessage(""); previous.current = 0;
    offRouteSince.current = null; rerouteError.current = "";
    lastTrafficRefresh.current = Date.now();
    if (!route) stop();
  }, [route, stop]);
  useEffect(() => () => {
    pending.current?.abort(); pending.current = null; callback.current(false);
  }, []);

  useEffect(() => {
    if (!running || !route) return;
    let active = true;
    const id = navigator.geolocation.watchPosition(position => {
      if (!active) return;
      const { latitude, longitude, accuracy, heading } = position.coords;
      if (!Number.isFinite(latitude) || !Number.isFinite(longitude) || !Number.isFinite(accuracy)
        || accuracy < 0 || Math.abs(latitude) > 90 || Math.abs(longitude) > 180
        || !Number.isFinite(position.timestamp) || Math.abs(Date.now() - position.timestamp) > 15000 || position.timestamp < latestTimestamp.current) {
        setMessage("Waiting for a fresh, valid GPS location…"); return;
      }
      latestTimestamp.current = position.timestamp;
      const next: LocationFix = { lat: latitude, lng: longitude, accuracy,
        heading: heading !== null && Number.isFinite(heading) && heading >= 0 && heading < 360 ? heading : null, timestamp: position.timestamp };
      const progress = journeyProgress(route, next, previous.current);
      if (progress.reliable && !progress.offRoute) previous.current = progress.progress;
      setFix(next);
      if (!progress.offRoute) rerouteError.current = "";
      if (!pending.current) setMessage(rerouteError.current);
      if (progress.arrived) { setArrived(true); stop(); setFix(next); return; }
      // Two accurate fixes separated by eight seconds confirm deviation. Weak GPS
      // and returning to the path reset confirmation; requests are 30 seconds apart.
      const trafficRefresh = !!route.traffic && !progress.offRoute && accuracy <= 30
        && position.timestamp - lastTrafficRefresh.current >= 120000;
      if (!progress.offRoute || accuracy > 30) offRouteSince.current = null;
      else if (offRouteSince.current === null) offRouteSince.current = position.timestamp;
      const confirmedDeviation = offRouteSince.current !== null && position.timestamp - offRouteSince.current >= 8000;
      if ((!confirmedDeviation && !trafficRefresh) || pending.current
        || (lastAttempt.current !== null && position.timestamp - lastAttempt.current < 30000)) return;
      const controller = new AbortController();
      pending.current = controller; lastAttempt.current = position.timestamp;
      lastTrafficRefresh.current = position.timestamp;
      setMessage(trafficRefresh ? "Refreshing traffic and routes…" : "Rerouting from your current location…");
      void rerouteCallback.current({ lat: latitude, lng: longitude }, controller.signal)
        .catch(() => {
          if (!controller.signal.aborted) {
            rerouteError.current = trafficRefresh ? "Could not refresh traffic. Keeping the previous estimate; retrying on a later update."
              : "Could not reroute. Keeping the previous route; retrying when GPS confirms you are still off route.";
            setMessage(rerouteError.current);
          }
        }).finally(() => { if (pending.current === controller) pending.current = null; });
    }, error => {
      if (!active) return;
      setMessage(error.code === 1 ? "Location permission denied. Allow location access to start following this route."
        : "GPS signal unavailable. Waiting for your location…");
      if (error.code === 1) stop();
    }, { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 });
    return () => { active = false; navigator.geolocation.clearWatch(id); };
  }, [running, route, stop]);
  const progress = fix && route ? journeyProgress(route, fix, previous.current) : null;
  return { running, fix, message, arrived, progress, start, stop };
}
