import { getApp, getApps, initializeApp } from "firebase/app";
import { connectAuthEmulator, getAuth } from "firebase/auth";
import { connectFirestoreEmulator, initializeFirestore, memoryLocalCache } from "firebase/firestore";

export const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
};

export const firebaseConfigured = Object.values(firebaseConfig).every(Boolean);
let services: ReturnType<typeof createServices> | null = null;

function createServices() {
  const app = getApps().length ? getApp() : initializeApp(firebaseConfig);
  const auth = getAuth(app);
  const db = initializeFirestore(app, { localCache: memoryLocalCache() });
  if (process.env.NEXT_PUBLIC_FIREBASE_EMULATORS === "true") {
    // Explicit demo project prevents accidental use of production with emulators.
    if (!firebaseConfig.projectId?.startsWith("demo-")) throw new Error("Emulators require a demo Firebase project.");
    connectAuthEmulator(auth, "http://127.0.0.1:9099", { disableWarnings: true });
    connectFirestoreEmulator(db, "127.0.0.1", 8085);
  }
  return { app, auth, db };
}

export function getFirebase() {
  if (typeof window === "undefined" || !firebaseConfigured) return null;
  services ??= createServices();
  return services;
}
