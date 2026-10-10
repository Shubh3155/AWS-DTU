import { after, before, beforeEach, test } from "node:test";
import { readFile } from "node:fs/promises";
import { assertFails, assertSucceeds, initializeTestEnvironment } from "@firebase/rules-unit-testing";
import { collection, deleteDoc, doc, getDoc, getDocs, limit, orderBy, query, serverTimestamp, setDoc, updateDoc } from "firebase/firestore";

let environment;
before(async () => {
  environment = await initializeTestEnvironment({ projectId: "demo-aeroroute", firestore: {
    host: "127.0.0.1", port: 8085, rules: await readFile(new URL("../../firestore.rules", import.meta.url), "utf8"),
  } });
});
beforeEach(async () => environment.clearFirestore());
after(async () => environment.cleanup());

const search = (overrides = {}) => ({
  origin: { label: "Start", lat: 28.63, lng: 77.21 }, destination: { label: "End", lat: 28.62, lng: 77.23 },
  mode: "walking", detourMinutes: 5, dataMode: "live", status: "limited_data",
  selectedRouteId: "mapbox-example", dataVersion: null, modelVersion: null, searchedAt: serverTimestamp(), ...overrides,
});

test("owner can save, query newest history and delete; other accounts and guests cannot access it", async () => {
  const owner = environment.authenticatedContext("alice").firestore();
  const other = environment.authenticatedContext("bob").firestore();
  const guest = environment.unauthenticatedContext().firestore();
  const path = "users/alice/recentSearches/search-one";
  await assertSucceeds(setDoc(doc(owner, path), search()));
  await assertSucceeds(getDocs(query(collection(owner, "users/alice/recentSearches"), orderBy("searchedAt", "desc"), limit(20))));
  await assertFails(getDoc(doc(other, path)));
  await assertFails(getDocs(collection(other, "users/alice/recentSearches")));
  await assertFails(getDoc(doc(guest, path)));
  await assertFails(setDoc(doc(other, path), search()));
  await assertFails(deleteDoc(doc(other, path)));
  await assertSucceeds(deleteDoc(doc(owner, path)));
});

test("invalid coordinates, detour, timestamps, unknown fields and history edits are denied", async () => {
  const db = environment.authenticatedContext("alice").firestore();
  for (const invalid of [
    { origin: { label: "Out of range", lat: 91, lng: 77 } }, { detourMinutes: -1 }, { detourMinutes: "5" },
    { searchedAt: new Date("2025-01-01") }, { token: "credentials-do-not-belong-in-history" }, { mode: "flying" },
  ]) await assertFails(setDoc(doc(db, "users/alice/recentSearches/bad"), search(invalid)));
  await assertSucceeds(setDoc(doc(db, "users/alice/recentSearches/good"), search()));
  await assertFails(updateDoc(doc(db, "users/alice/recentSearches/good"), { detourMinutes: 10 }));
});

test("profiles validate fields; navigation and device records cannot be forged by clients", async () => {
  const db = environment.authenticatedContext("alice").firestore();
  await assertSucceeds(setDoc(doc(db, "users/alice"), { displayName: "Alice", avatar: "", updatedAt: serverTimestamp() }));
  await assertFails(updateDoc(doc(db, "users/alice"), { admin: true }));
  await assertFails(setDoc(doc(db, "users/alice/devices/browser"), { recipient: "someone-else", enabled: true }));
  await assertFails(setDoc(doc(db, "users/alice/navigationSessions/forged"), { active: true }));
  await assertFails(getDoc(doc(db, "pushBindings/private")));
  await assertFails(setDoc(doc(db, "arbitrary/open"), { value: true }));
});
