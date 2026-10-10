"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { User } from "firebase/auth";
import { useAuth } from "@/components/auth-provider";
import { disableNotifications, enableNotifications, workerGuidance, type AlertDevice } from "@/lib/notifications";
import { privateApi, PrivateApiError } from "@/lib/private-api";
import { validDirectionAlert, type ActiveGuidance } from "@/lib/notification-policy";
import type { LocationFix } from "@/lib/navigation";
import type { RouteCandidate } from "@/types/api";

type Session = { journey_id: string; route_version: string };
type ProgressResponse = { accepted: boolean; arrived: boolean; alert: "none" | "sent" | "failed" | "suppressed" };

export function useDirectionAlerts(route: RouteCandidate | undefined, running: boolean, fix: LocationFix | null, arrived: boolean) {
  const { user, registerCleanup } = useAuth();
  const [enabled, setEnabled] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const device = useRef<AlertDevice | null>(null);
  const session = useRef<Session | null>(null);
  const active = useRef<ActiveGuidance | null>(null);
  const generation = useRef(0);
  const sequence = useRef(0);
  const completed = useRef(false);
  const arrivalTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const latest = useRef({ route, running, fix, user, arrived });
  latest.current = { route, running, fix, user, arrived };
  const broadcast = useRef<BroadcastChannel | null>(null);

  const endSession = useCallback(async (owner: User | null) => {
    const old = session.current;
    session.current = null; active.current = null; generation.current += 1;
    if (arrivalTimer.current) { clearTimeout(arrivalTimer.current); arrivalTimer.current = null; }
    if (device.current && old) await workerGuidance(device.current, null, old.journey_id);
    if (owner && old) await privateApi(owner, `/navigation/sessions/${old.journey_id}`, "DELETE").catch(() => {});
  }, []);

  const disable = useCallback(async (owner: User | null) => {
    const old = device.current;
    device.current = null; setEnabled(false);
    await endSession(owner);
    if (old) await disableNotifications(owner, old);
  }, [endSession]);

  useEffect(() => registerCleanup(disable), [registerCleanup, disable]);
  useEffect(() => {
    if (!("BroadcastChannel" in window)) return;
    const channel = new BroadcastChannel("aeroroute-direction-alerts");
    broadcast.current = channel;
    channel.onmessage = () => {
      // Release this tab without unregistering the shared subscription now owned by the claiming tab.
      const old = device.current;
      void endSession(latest.current.user);
      old?.unsubscribe(); device.current = null; setEnabled(false);
      setMessage("Direction alerts moved to another tab. In-app directions remain available.");
    };
    return () => { channel.close(); broadcast.current = null; };
  }, [endSession]);

  async function enable() {
    if (!user) { setMessage("Sign in with Google to enable cloud direction alerts."); return; }
    const owner = user;
    const version = ++generation.current;
    setBusy(true); setMessage("");
    try {
      const registration = await enableNotifications(owner, payload => {
        if (validDirectionAlert(payload, active.current)) {
          active.current!.lastDisplayedSequence = Number(payload.sequence);
          // Foreground GPS already displays the current instruction; do not duplicate it.
          setMessage("Cloud alerts connected. Follow the live instruction above.");
        }
      });
      if (generation.current !== version || latest.current.user?.uid !== owner.uid) { await disableNotifications(owner, registration); return; }
      device.current = registration; setEnabled(true);
      broadcast.current?.postMessage({ type: "claim" });
      setMessage("Direction alerts enabled. Keep this page open for live location updates.");
    } catch (error) { if (generation.current === version) setMessage(error instanceof Error ? error.message : "Could not enable alerts."); }
    finally { setBusy(false); }
  }

  useEffect(() => {
    if (!enabled) return;
    if (running) completed.current = false;
    if (!running && !arrived) { void endSession(latest.current.user); return; }
    let cancelled = false, pending = false;
    const controller = new AbortController();
    async function tick() {
      const { user: owner, route: currentRoute, fix: position, running: moving, arrived: atEnd } = latest.current;
      const registration = device.current;
      if (cancelled || pending || completed.current || !owner || !registration || !currentRoute?.navigation_token || (!moving && !atEnd) || !position || Date.now() - position.timestamp > 15000) return;
      pending = true;
      const version = generation.current;
      try {
        if (!session.current) {
          const created = await privateApi<Session>(owner, "/navigation/sessions", "POST", { device_id: registration.id, navigation_token: currentRoute.navigation_token }, controller.signal);
          if (cancelled || version !== generation.current) { await privateApi(owner, `/navigation/sessions/${created.journey_id}`, "DELETE").catch(() => {}); return; }
          session.current = created; sequence.current = 0;
        }
        const journey = session.current;
        if (!journey) return;
        const currentSequence = ++sequence.current;
        active.current = { journeyId: journey.journey_id, routeVersion: currentRoute.navigation_token, expiresAt: Date.now() + 30000, lastDisplayedSequence: active.current?.routeVersion === currentRoute.navigation_token ? active.current.lastDisplayedSequence : 0 };
        await workerGuidance(registration, active.current);
        const response = await privateApi<ProgressResponse>(owner, `/navigation/sessions/${journey.journey_id}/progress`, "POST", {
          sequence: currentSequence, navigation_token: currentRoute.navigation_token,
          fix: { lat: position.lat, lng: position.lng, accuracy: position.accuracy, timestamp: new Date(position.timestamp).toISOString() },
        }, controller.signal);
        if (cancelled || version !== generation.current) return;
        if (response.alert === "failed") setMessage("Cloud alert could not be delivered. Follow the on-screen directions.");
        if (response.arrived) {
          completed.current = true;
          setMessage("You have arrived. Direction alerts stopped.");
          // Keep the receiver alive only for the arrival message's short TTL.
          if (active.current) active.current.expiresAt = Date.now() + 15000;
          arrivalTimer.current = setTimeout(() => void endSession(owner), 15000);
        }
      } catch (error) {
        if (cancelled || version !== generation.current) return;
        if (error instanceof PrivateApiError && error.status === 410) {
          await endSession(owner);
          setMessage("Location updates paused. Reconnecting alerts with fresh GPS…");
        } else if (!(error instanceof PrivateApiError && error.status === 429)) {
          const message = error instanceof Error ? error.message : "Cloud alerts unavailable. Follow on-screen directions.";
          // Don't retry permanent auth/configuration/route errors every five seconds.
          if (error instanceof PrivateApiError && [401, 403, 409, 503].includes(error.status)) await disable(owner);
          setMessage(message);
        }
      } finally { pending = false; }
    }
    void tick();
    const timer = setInterval(() => void tick(), 5000);
    return () => { cancelled = true; controller.abort(); clearInterval(timer); };
  }, [enabled, running, arrived, endSession, disable]);

  useEffect(() => {
    if (!active.current || !device.current || !route?.navigation_token || active.current.routeVersion === route.navigation_token) return;
    active.current = { ...active.current, routeVersion: route.navigation_token, lastDisplayedSequence: 0 };
    void workerGuidance(device.current, active.current);
  }, [route?.navigation_token]);

  useEffect(() => () => {
    const old = session.current;
    const registration = device.current;
    if (arrivalTimer.current) clearTimeout(arrivalTimer.current);
    if (registration && old) void workerGuidance(registration, null, old.journey_id);
    if (latest.current.user && old) void privateApi(latest.current.user, `/navigation/sessions/${old.journey_id}`, "DELETE").catch(() => {});
    registration?.unsubscribe();
  }, []);

  return { enabled, busy, message, enable, disable: async () => { await disable(user); setMessage("Direction alerts disabled. On-screen directions remain available."); } };
}
