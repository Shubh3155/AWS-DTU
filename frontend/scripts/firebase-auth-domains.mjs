import { createRequire } from "node:module";
import nextEnv from "@next/env";

nextEnv.loadEnvConfig(process.cwd(), true);
const require = createRequire(import.meta.url);
const firebase = require("firebase-tools");
const { getAuthDomains, updateAuthDomains } = require("firebase-tools/lib/gcp/auth");
const project = process.argv[2];
const apply = process.argv.includes("--apply");
if (!project || project !== process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID || project.startsWith("demo-")) {
  throw new Error("Specify the same real project as NEXT_PUBLIC_FIREBASE_PROJECT_ID.");
}
const requested = ["localhost", "127.0.0.1", ...process.argv.slice(3).filter(argument => argument !== "--apply")];
if (requested.some(domain => !/^[a-z0-9][a-z0-9.-]*[a-z0-9]$/.test(domain) || domain.includes(".."))) {
  throw new Error("Provide hostnames without a scheme, port or path.");
}
// Authenticate through the installed CLI; never copy its credentials into app configuration.
await firebase.apps.list("WEB", { project, config: "../firebase.json", nonInteractive: true });
const existing = await getAuthDomains(project);
const missing = requested.filter(domain => !existing.includes(domain));
if (missing.length && apply) {
  const domains = await updateAuthDomains(project, [...new Set([...existing, ...requested])]);
  if (requested.some(domain => !domains.includes(domain))) throw new Error("Domain configuration was not confirmed.");
  console.log("Authorized sign-in domains added: " + missing.join(", "));
} else if (missing.length) {
  console.log("Missing sign-in domains: " + missing.join(", ") + ". Run again with --apply to add them.");
  process.exitCode = 1;
} else {
  console.log("Required sign-in domains are already authorized.");
}
