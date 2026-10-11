import { pathToFileURL } from "node:url";
import nextEnv from "@next/env";

const required = ["AEROROUTE_API_URL", "NEXT_PUBLIC_MAPBOX_TOKEN", "NEXT_PUBLIC_FIREBASE_API_KEY",
  "NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN", "NEXT_PUBLIC_FIREBASE_PROJECT_ID", "NEXT_PUBLIC_FIREBASE_APP_ID",
  "NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID", "NEXT_PUBLIC_FIREBASE_VAPID_KEY"];
function httpsOrigin(value) {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && !url.username && !url.password && !url.search && !url.hash
      && (!url.pathname || url.pathname === "/") && !["localhost", "127.0.0.1", "[::1]"].includes(url.hostname);
  } catch { return false; }
}
export function checkProductionConfiguration(env) {
  const missing = required.filter(name => !env[name]?.trim());
  if (missing.length) throw new Error(`Missing production configuration: ${missing.join(", ")}`);
  if (!httpsOrigin(env.AEROROUTE_API_URL) || (env.NEXT_PUBLIC_API_URL && !httpsOrigin(env.NEXT_PUBLIC_API_URL)))
    throw new Error("Production API URLs must be public HTTPS origins without credentials, paths or queries.");
  if (!env.NEXT_PUBLIC_MAPBOX_TOKEN.startsWith("pk.")) throw new Error("Use an intended public Mapbox browser token.");
  if (env.NEXT_PUBLIC_FIREBASE_PROJECT_ID.startsWith("demo-")
    || (env.NEXT_PUBLIC_FIREBASE_EMULATORS && env.NEXT_PUBLIC_FIREBASE_EMULATORS !== "false")
    || env.AEROROUTE_FIREBASE_TESTS === "true") throw new Error("Production builds must not use Firebase emulators or test mode.");
  if (!/^[a-zA-Z0-9.-]+$/.test(env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN)) throw new Error("Firebase auth domain must be a hostname.");
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  nextEnv.loadEnvConfig(process.cwd(), false);
  try { checkProductionConfiguration(process.env); console.log("Production frontend configuration passed; verify deployed OAuth and push delivery separately."); }
  catch (error) { console.error(error.message); process.exitCode = 1; }
}
