"use client";

import { useEffect, useRef, useState } from "react";
import { limit, onSnapshot, orderBy, query, type DocumentData, type QueryDocumentSnapshot } from "firebase/firestore";
import { useAuth } from "@/components/auth-provider";
import { clearHistory, deleteSearch, historyCollection, saveProfile, type SavedSearch } from "@/lib/route-history";

type Entry = SavedSearch & { date: string };
function entry(document: QueryDocumentSnapshot<DocumentData>): Entry {
  const data = document.data();
  return { ...data, id: document.id, date: data.searchedAt?.toDate?.().toLocaleDateString("en-IN", { day: "numeric", month: "short" }) ?? "Just now" } as Entry;
}

export function RecentRoutes({ disabled, onReopen }: { disabled: boolean; onReopen: (search: SavedSearch) => void }) {
  const { user, ready } = useAuth();
  const uid = user?.uid ?? null;
  const currentUid = useRef(uid);
  currentUid.current = uid;
  const [state, setState] = useState<{ uid: string | null; rows: Entry[]; error: string; loading: boolean; more: boolean }>({ uid: null, rows: [], error: "", loading: false, more: false });
  const [page, setPage] = useState({ uid, size: 20 });
  const pageSize = page.uid === uid ? page.size : 20;
  const [working, setWorking] = useState(false);
  const rows = state.uid === uid ? state.rows : [];

  useEffect(() => {
    if (!uid) return;
    const owner = uid;
    setState(previous => ({ uid: owner, rows: previous.uid === owner ? previous.rows : [], error: "", loading: true, more: false }));
    // Keep the loaded range live so inserts/deletions cannot leave gaps between pages.
    return onSnapshot(query(historyCollection(owner), orderBy("searchedAt", "desc"), limit(pageSize)), snapshot => {
      if (currentUid.current !== owner) return;
      setState({ uid: owner, rows: snapshot.docs.map(entry), error: "", loading: false, more: snapshot.size === pageSize });
    }, () => {
      if (currentUid.current === owner) setState(previous => ({ ...previous, loading: false, error: "Recent routes could not load. Check your connection or try signing in again." }));
    });
  }, [uid, pageSize]);

  useEffect(() => { if (user) void saveProfile(user).catch(() => {}); }, [user]);

  async function action(operation: () => Promise<void>) {
    const owner = uid;
    setWorking(true);
    try { await operation(); }
    catch { if (owner === currentUid.current) setState(previous => ({ ...previous, error: "Could not update your history. Please try again." })); }
    finally { setWorking(false); }
  }

  return <section className="recent-routes" aria-label="Recent routes">
    <div className="recent-heading"><h2>Recent routes</h2>{uid && rows.length > 0 && <button type="button" disabled={working || disabled} onClick={() => void action(() => clearHistory(uid))}>Clear all</button>}</div>
    {!ready ? <p role="status">Restoring your session…</p> : !uid ? <p>Sign in with Google to save and reopen your route searches.</p> : <>
      {state.uid === uid && state.loading && <p role="status">Loading recent routes…</p>}
      {state.uid === uid && state.error && <p role="status">{state.error}</p>}
      {!rows.length && !state.loading && !state.error && <p>Your next route search will be saved here.</p>}
      <ul>{rows.map(row => <li key={row.id}>
        <button type="button" className="reopen-route" disabled={disabled || working} onClick={() => onReopen(row)} aria-label={`Reopen ${row.origin.label} to ${row.destination.label}`}>
          <span>{row.origin.label || "Starting point"} <span aria-hidden="true">→</span> {row.destination.label || "Destination"}</span>
          <small>{row.date} · {row.mode === "driving" ? "Car" : row.mode === "motorcycle" ? "Motorcycle" : "Walk"} · {row.detourMinutes} min extra{row.dataMode === "replay" && " · Recorded observations"}</small>
        </button>
        <button type="button" className="delete-route" disabled={working || disabled} aria-label={`Delete route to ${row.destination.label}`} onClick={() => void action(() => deleteSearch(uid, row.id))}>×</button>
      </li>)}</ul>
      {state.uid === uid && state.more && <button type="button" disabled={working || state.loading} onClick={() => setPage({ uid, size: pageSize + 20 })}>Load older searches</button>}
      <p className="history-note">Reopening checks current directions and air-data availability.</p>
    </>}
  </section>;
}
