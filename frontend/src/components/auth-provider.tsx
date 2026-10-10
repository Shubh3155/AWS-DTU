"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { FirebaseError } from "firebase/app";
import { browserLocalPersistence, browserSessionPersistence, getRedirectResult, GoogleAuthProvider, onIdTokenChanged,
  setPersistence, signInWithPopup, signInWithRedirect, signOut, type User } from "firebase/auth";
import { getFirebase, firebaseConfigured } from "@/lib/firebase";

type Cleanup = (user: User | null) => void | Promise<void>;
type AuthState = {
  user: User | null; ready: boolean; configured: boolean; busy: boolean; error: string;
  login: (remember: boolean, redirect?: boolean) => Promise<void>;
  logout: () => Promise<void>;
  registerCleanup: (cleanup: Cleanup) => () => void;
};
const AuthContext = createContext<AuthState | null>(null);

function authMessage(error: unknown) {
  if (!(error instanceof FirebaseError)) return "Could not sign in. Please try again.";
  const messages: Record<string, string> = {
    "auth/popup-closed-by-user": "Sign-in cancelled. You can keep planning as a guest.",
    "auth/popup-blocked": "Your browser blocked the sign-in window. Use Continue sign-in below.",
    "auth/unauthorized-domain": "Sign-in is not enabled for this website yet.",
    "auth/operation-not-allowed": "Google sign-in has not been enabled for this app yet.",
    "auth/network-request-failed": "Sign-in could not connect. Check your connection and try again.",
    "auth/account-exists-with-different-credential": "This account uses another sign-in method. Contact the app administrator.",
  };
  return messages[error.code] ?? "Could not sign in. Please try again.";
}

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
    if (!firebase) { setError("Sign-in is not configured yet. You can still compare routes."); return; }
    setBusy(true); setError("");
    try {
      await setPersistence(firebase.auth, remember ? browserLocalPersistence : browserSessionPersistence);
      const provider = new GoogleAuthProvider();
      provider.setCustomParameters({ prompt: "select_account" });
      if (redirect) await signInWithRedirect(firebase.auth, provider);
      else await signInWithPopup(firebase.auth, provider);
    } catch (error) { setError(authMessage(error)); }
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
