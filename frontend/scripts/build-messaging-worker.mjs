import { build } from "esbuild";
import nextEnv from "@next/env";

nextEnv.loadEnvConfig(process.cwd(), process.argv.includes("--development"));
const keys = ["API_KEY", "AUTH_DOMAIN", "PROJECT_ID", "APP_ID", "MESSAGING_SENDER_ID"];
const define = Object.fromEntries(keys.map(key => {
  const name = `NEXT_PUBLIC_FIREBASE_${key}`;
  return [`process.env.${name}`, JSON.stringify(process.env[name] || "")];
}));
await build({ entryPoints: ["src/workers/firebase-messaging-sw.ts"], outfile: "public/firebase-messaging-sw.js", bundle: true, minify: true, target: "es2020", define });
