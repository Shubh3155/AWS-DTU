/// <reference lib="webworker" />
import { initializeApp } from "firebase/app";
import { getMessaging, onBackgroundMessage } from "firebase/messaging/sw";
import { validDirectionAlert, type ActiveGuidance } from "../lib/notification-policy";

declare const self: ServiceWorkerGlobalScope;
const cacheName = "aeroroute-active-guidance-v1";
const stateUrl = new URL("/.aeroroute-active-guidance", self.location.origin).href;
let serial: Promise<unknown> = Promise.resolve();
function exclusive(operation: () => Promise<void>) {
  serial = serial.catch(() => {}).then(operation);
  return serial;
}
async function getState(): Promise<ActiveGuidance | null> {
  return (await (await caches.open(cacheName)).match(stateUrl))?.json() ?? null;
}
async function setState(value: ActiveGuidance | null) {
  const cache = await caches.open(cacheName);
  if (value) await cache.put(stateUrl, new Response(JSON.stringify(value)));
  else await cache.delete(stateUrl);
}
async function closeNotifications() {
  (await self.registration.getNotifications({ tag: "aeroroute-directions" })).forEach(notification => notification.close());
}
async function closeExpiredNotifications() {
  (await self.registration.getNotifications({ tag: "aeroroute-directions" })).forEach(notification => {
    if (Number(notification.data?.expiresAt) <= Date.now()) notification.close();
  });
}

self.addEventListener("install", event => event.waitUntil(self.skipWaiting()));
self.addEventListener("activate", event => event.waitUntil(self.clients.claim()));
self.addEventListener("message", event => {
  const source = event.source;
  if (!source || !("url" in source) || new URL(source.url).origin !== self.location.origin) return;
  if (event.data?.type !== "guidance-state") return;
  event.waitUntil(exclusive(async () => {
    const old = await getState();
    const value = event.data.active as ActiveGuidance | null;
    // Clearing one tab must not clear a newer journey claimed by another tab.
    if (!value && event.data.journeyId && old?.journeyId !== event.data.journeyId) return;
    if (value && (typeof value.journeyId !== "string" || typeof value.routeVersion !== "string" || !Number.isFinite(value.expiresAt))) return;
    const sameRoute = value && old?.journeyId === value.journeyId && old.routeVersion === value.routeVersion;
    await setState(value ? { ...value, clientId: source.id, lastDisplayedSequence: sameRoute ? old.lastDisplayedSequence : 0 } : null);
    if (!sameRoute) await closeNotifications();
    else await closeExpiredNotifications();
    event.ports[0]?.postMessage({ ok: true });
  }));
});

// Install the click handler before Firebase's handlers so every click revalidates guidance.
self.addEventListener("notificationclick", event => {
  event.stopImmediatePropagation(); event.notification.close();
  event.waitUntil((async () => {
    const active = await getState();
    const data = event.notification.data;
    if (!active || active.expiresAt <= Date.now() || Number(data?.expiresAt) <= Date.now() || active.journeyId !== data?.journeyId || active.routeVersion !== data?.routeVersion || Number(data?.sequence) !== active.lastDisplayedSequence) return;
    const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    const existing = windows.find(client => new URL(client.url).origin === self.location.origin);
    if (existing) { await existing.focus(); existing.postMessage({ type: "refresh-guidance" }); }
    else await self.clients.openWindow("/");
  })());
});

const config = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
};
if (Object.values(config).every(Boolean)) {
  const messaging = getMessaging(initializeApp(config));
  onBackgroundMessage(messaging, async payload => {
    let shown = false;
    await exclusive(async () => {
      const active = await getState();
      if (!validDirectionAlert(payload.data, active)) return;
      const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      if (windows.some(client => client.id === active?.clientId && client.visibilityState === "visible")) return;
      await setState({ ...active!, lastDisplayedSequence: Number(payload.data.sequence) });
      await self.registration.showNotification("AeroRoute · next direction", {
        body: payload.data.instruction, tag: "aeroroute-directions",
        data: { journeyId: payload.data.journeyId, routeVersion: payload.data.routeVersion,
          sequence: payload.data.sequence, expiresAt: payload.data.expiresAt },
      });
      shown = true;
    });
    if (shown) {
      // Keep the push event alive briefly without blocking stop/reroute messages.
      await new Promise(resolve => setTimeout(resolve, Math.max(0, Number(payload.data?.expiresAt) - Date.now())));
      await exclusive(closeExpiredNotifications);
    }
  });
}
