"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { browserLocalPersistence, browserSessionPersistence, getRedirectResult, GoogleAuthProvider, onIdTokenChanged,
  setPersistence, signInWithPopup, signInWithRedirect, signOut, type User } from "firebase/auth";
import { getFirebase, firebaseConfigured } from "@/lib/firebase";
import { authMessage } from "@/lib/auth-errors";

type Cleanup = (user: User | null) => void | Promise<void>;
type AuthState = {
  user: User | null; ready: boolean; configured: boolean; busy: boolean; error: string;
  login: (remember: boolean, redirect?: boolean) => Promise<User | null>;
  logout: () => Promise<void>;
  registerCleanup: (cleanup: Cleanup) => () => void;
};
const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(!firebaseConfigured);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const current = useRef<User | null>(null);
  const cleanups = useRef(new Set<Cleanup>());
  const registerCleanup = useCallback((cleanup: Cleanup) => {
    cleanups.current.add(cleanup);
    return () => { cleanups.current.delete(cleanup); };
  }, []);
  const clear = useCallback(async (oldUser: User | null) => {
    await Promise.allSettled([...cleanups.current].map(cleanup => cleanup(oldUser)));
  }, []);

  useEffect(() => {
    const firebase = getFirebase();
    if (!firebase) return;
    let mounted = true;
    const unsubscribe = onIdTokenChanged(firebase.auth, next => {
      if (!mounted) return;
      const old = current.current;
      if (old && old.uid !== next?.uid) void clear(old);
      current.current = next;
      setUser(next); setReady(true);
    }, () => { if (mounted) { setError("Could not restore your session. Sign in again."); setReady(true); } });
    void getRedirectResult(firebase.auth).catch(error => { if (mounted) setError(authMessage(error)); });
    return () => { mounted = false; unsubscribe(); };
  }, [clear]);

  const login = useCallback(async (remember: boolean, redirect = false) => {
    const firebase = getFirebase();
    if (!firebase) { setError("Sign-in is not configured yet. You can still compare routes."); return null; }
    setBusy(true); setError("");
    try {
      await setPersistence(firebase.auth, remember ? browserLocalPersistence : browserSessionPersistence);
      const provider = new GoogleAuthProvider();
      provider.setCustomParameters({ prompt: "select_account" });
      if (redirect) { await signInWithRedirect(firebase.auth, provider); return null; }
      const result = await signInWithPopup(firebase.auth, provider);
      return result.user;
    } catch (error) { setError(authMessage(error)); return null; }
    finally { setBusy(false); }
  }, []);

  const logout = useCallback(async () => {
    setBusy(true); setError("");
    const old = current.current;
    // Clear private UI immediately; cleanup callbacks still have the old user's ID token.
    current.current = null; setUser(null);
    try {
      await clear(old);
      const firebase = getFirebase();
      if (firebase) await signOut(firebase.auth);
    } catch { setError("Logout could not finish. Check your connection and try again."); }
    finally { setBusy(false); }
  }, [clear]);

  return <AuthContext.Provider value={{ user, ready, configured: firebaseConfigured, busy, error, login, logout, registerCleanup }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("AuthProvider is required.");
  return value;
}
