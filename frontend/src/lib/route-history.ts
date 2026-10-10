import { collection, deleteDoc, doc, getDocs, limit, query, runTransaction, serverTimestamp, setDoc, writeBatch } from "firebase/firestore";
import type { User } from "firebase/auth";
import { getFirebase } from "@/lib/firebase";
import type { ComparisonRequest, ComparisonResponse } from "@/types/api";

export type SavedSearch = {
  id: string; origin: { label: string; lat: number; lng: number };
  destination: { label: string; lat: number; lng: number };
  mode: ComparisonRequest["mode"]; detourMinutes: number; dataMode: "live" | "replay";
  status: ComparisonResponse["status"]; selectedRouteId: string | null;
  dataVersion: string | null; modelVersion: string | null;
};

export function historyCollection(uid: string) {
  const firebase = getFirebase();
  if (!firebase) throw new Error("Route history is unavailable.");
  return collection(firebase.db, "users", uid, "recentSearches");
}

export async function saveSearch(user: User, search: SavedSearch) {
  const firebase = getFirebase();
  if (!firebase || firebase.auth.currentUser?.uid !== user.uid) throw new Error("Sign in again to save this route.");
  await runTransaction(firebase.db, async transaction => {
    const reference = doc(historyCollection(user.uid), search.id);
    const existing = await transaction.get(reference);
    if (!existing.exists()) {
      const { id, ...fields } = search;
      void id;
      transaction.set(reference, { ...fields, searchedAt: serverTimestamp() });
    }
  });
}

export async function saveProfile(user: User) {
  const firebase = getFirebase();
  if (!firebase || firebase.auth.currentUser?.uid !== user.uid) return;
  const reference = doc(firebase.db, "users", user.uid);
  await setDoc(reference, { displayName: (user.displayName || "").slice(0, 200),
    avatar: (user.photoURL || "").slice(0, 2048), updatedAt: serverTimestamp() }, { merge: true });
}

export async function deleteSearch(uid: string, id: string) {
  await deleteDoc(doc(historyCollection(uid), id));
}

export async function clearHistory(uid: string) {
  const firebase = getFirebase();
  if (!firebase) return;
  // Fetch and delete every page, including history beyond the visible first 20.
  for (;;) {
    if (firebase.auth.currentUser?.uid !== uid) throw new Error("Your account changed. Sign in again.");
    const page = await getDocs(query(historyCollection(uid), limit(200)));
    if (page.empty) return;
    const batch = writeBatch(firebase.db);
    page.docs.forEach(entry => batch.delete(entry.ref));
    await batch.commit();
  }
}
