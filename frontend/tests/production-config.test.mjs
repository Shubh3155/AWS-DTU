import { test } from "node:test";
import assert from "node:assert/strict";
import { checkProductionConfiguration } from "../scripts/check-production-config.mjs";
const valid = { AEROROUTE_API_URL: "https://api.example", NEXT_PUBLIC_MAPBOX_TOKEN: "pk.synthetic",
  NEXT_PUBLIC_FIREBASE_API_KEY: "public", NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN: "project.firebaseapp.com",
  NEXT_PUBLIC_FIREBASE_PROJECT_ID: "project", NEXT_PUBLIC_FIREBASE_APP_ID: "app",
  NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID: "sender", NEXT_PUBLIC_FIREBASE_VAPID_KEY: "public" };
test("complete production configuration passes", () => assert.doesNotThrow(() => checkProductionConfiguration(valid)));
test("missing Firebase settings fail with names instead of values", () => {
  assert.throws(() => checkProductionConfiguration({ ...valid, NEXT_PUBLIC_FIREBASE_PROJECT_ID: "" }), /NEXT_PUBLIC_FIREBASE_PROJECT_ID/);
});
test("local or credential-bearing backend URLs are rejected", () => {
  for (const url of ["http://api.example", "https://localhost", "https://user:secret@api.example", "https://api.example/api", "https://api.example?secret=x"])
    assert.throws(() => checkProductionConfiguration({ ...valid, AEROROUTE_API_URL: url }), /public HTTPS/);
});
test("emulator and private browser tokens cannot reach the production build", () => {
  for (const override of [{ NEXT_PUBLIC_FIREBASE_EMULATORS: "true" }, { NEXT_PUBLIC_FIREBASE_PROJECT_ID: "demo-project" }, { AEROROUTE_FIREBASE_TESTS: "true" }, { NEXT_PUBLIC_MAPBOX_TOKEN: "sk.private" }])
    assert.throws(() => checkProductionConfiguration({ ...valid, ...override }));
});
