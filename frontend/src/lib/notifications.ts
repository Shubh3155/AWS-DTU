import { getMessaging, isSupported, onMessage, onRegistered, register, unregister } from "firebase/messaging";
import type { User } from "firebase/auth";
import { getFirebase } from "@/lib/firebase";
import { privateApi } from "@/lib/private-api";
import type { ActiveGuidance, DirectionAlert } from "@/lib/notification-policy";

export type AlertDevice = { id: string; worker: ServiceWorkerRegistration; unsubscribe: () => void };
const registrationOwner = "aeroroute-alert-registration";
async function registrationLock<T>(operation: () => Promise<T>): Promise<T> {
  return navigator.locks ? navigator.locks.request("aeroroute-alert-registration", operation) : operation();
}

export async function enableNotifications(user: User, receive: (data: Partial<DirectionAlert> | undefined) => void): Promise<AlertDevice> {
  const firebase = getFirebase();
  const vapidKey = process.env.NEXT_PUBLIC_FIREBASE_VAPID_KEY;
  if (!firebase || !vapidKey) throw new Error("Cloud direction alerts are not configured yet. In-app directions are available.");
  if (!window.isSecureContext || !("Notification" in window) || !("serviceWorker" in navigator)) throw new Error("Push alerts are unavailable in this browser. Keep this page open for directions.");
  // Ask directly from the user's click, before support checks that may yield.
  const permission = await Notification.requestPermission();
  if (permission !== "granted") throw new Error("Notifications are off. You can follow the on-screen directions.");
  if (!await isSupported()) throw new Error("Push alerts are unsupported here. Keep this page open for directions.");
  const worker = await navigator.serviceWorker.register("/firebase-messaging-sw.js", { scope: "/" });
  await navigator.serviceWorker.ready;
  const messaging = getMessaging(firebase.app);
  return registrationLock(async () => {
    const id = crypto.randomUUID();
    let recipient = "", linked = false;
    let resolveRecipient: (fid: string) => void = () => {};
    const confirmedRecipient = new Promise<string>(resolve => { resolveRecipient = resolve; });
    // Required by the SDK: subscribe before register, and use the confirmed FID.
    const stopRegistered = onRegistered(messaging, fid => {
      const changed = recipient && recipient !== fid;
      recipient = fid; resolveRecipient(fid);
      if (linked && changed && firebase.auth.currentUser?.uid === user.uid && localStorage.getItem(registrationOwner) === id) {
        // Installation rotation invalidates the old journey; the next fix reconnects it.
        void privateApi(user, `/me/devices/${id}`, "PUT", { recipient: fid, recipient_kind: "fid" }).catch(() => {});
      }
    });
    try {
      const [, fid] = await Promise.all([register(messaging, { vapidKey, serviceWorkerRegistration: worker }), confirmedRecipient]);
      if (firebase.auth.currentUser?.uid !== user.uid) throw new Error("Your account changed. Enable alerts again.");
      await privateApi(user, `/me/devices/${id}`, "PUT", { recipient: fid, recipient_kind: "fid" });
      // A registration has a distinct owner per tab/attempt, even when FCM shares the installation.
      try { localStorage.setItem(registrationOwner, id); }
      catch {
        await privateApi(user, `/me/devices/${id}`, "DELETE").catch(() => {});
        throw new Error("This browser cannot save the alert registration. Follow the on-screen directions.");
      }
      linked = true;
      const stopMessage = onMessage(messaging, payload => receive(payload.data));
      return { id, worker, unsubscribe: () => { linked = false; stopRegistered(); stopMessage(); } };
    } catch (error) {
      stopRegistered();
      throw error;
    }
  });
}

export async function workerGuidance(device: AlertDevice, active: ActiveGuidance | null, journeyId?: string) {
  const worker = device.worker.active;
  if (!worker) return;
  const channel = new MessageChannel();
  await new Promise<void>(resolve => {
    const timeout = setTimeout(resolve, 1500);
    channel.port1.onmessage = () => { clearTimeout(timeout); resolve(); };
    worker.postMessage({ type: "guidance-state", active, journeyId }, [channel.port2]);
  });
  channel.port1.close();
}

export async function disableNotifications(user: User | null, device: AlertDevice) {
  device.unsubscribe();
  const firebase = getFirebase();
  await registrationLock(async () => {
    const ownsRegistration = localStorage.getItem(registrationOwner) === device.id;
    if (ownsRegistration) {
      await workerGuidance(device, null);
      localStorage.removeItem(registrationOwner);
    }
    await Promise.allSettled([
      user ? privateApi(user, `/me/devices/${device.id}`, "DELETE") : Promise.resolve(),
      firebase && ownsRegistration ? unregister(getMessaging(firebase.app)) : Promise.resolve(),
    ]);
  });
}
