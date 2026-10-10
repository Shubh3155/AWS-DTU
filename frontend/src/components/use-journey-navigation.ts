"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { journeyProgress, type LocationFix } from "@/lib/navigation";
import type { RouteCandidate } from "@/types/api";

export function useJourneyNavigation(route: RouteCandidate | undefined, onChange: (active: boolean) => void) {
  const [running, setRunning] = useState(false);
  const [fix, setFix] = useState<LocationFix | null>(null);
  const [message, setMessage] = useState("");
  const [arrived, setArrived] = useState(false);
  const callback = useRef(onChange);
  const previous = useRef(0);
  const latestTimestamp = useRef(0);
  useEffect(() => { callback.current = onChange; }, [onChange]);
  const stop = useCallback(() => { setRunning(false); setFix(null); callback.current(false); }, []);
  function start() {
    if (!route) return;
    if (!navigator.geolocation) { setMessage("Location is unavailable in this browser."); return; }
    previous.current = 0; latestTimestamp.current = 0;
    setFix(null); setArrived(false); setMessage("Waiting for GPS permission and a location fix…");
    setRunning(true); callback.current(true);
  }
  // Changing/unmounting the selected route stops tracking and clears its progress.
  useEffect(() => {
    setFix(null); setArrived(false); setMessage(""); previous.current = 0;
    stop();
    return () => { callback.current(false); };
  }, [route?.id, stop]);

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
      setFix(next); setMessage("");
      if (progress.arrived) { setArrived(true); stop(); }
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
