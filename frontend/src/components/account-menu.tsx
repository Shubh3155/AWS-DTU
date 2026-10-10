"use client";

import { useState } from "react";
import { useAuth } from "@/components/auth-provider";

export function AccountMenu() {
  const auth = useAuth();
  const [remember, setRemember] = useState(false);
  return <div className="account-menu" aria-label="Your account">
    {!auth.ready ? <span role="status">Restoring session…</span> : auth.user ? <>
      <span className="account-name">{auth.user.displayName || "Signed in"}</span>
      <button type="button" disabled={auth.busy} onClick={() => void auth.logout()}>{auth.busy ? "Logging out…" : "Log out"}</button>
    </> : <>
      <label className="remember-me"><input type="checkbox" checked={remember} disabled={auth.busy} onChange={event => setRemember(event.target.checked)} />Remember me</label>
      <button type="button" disabled={auth.busy || !auth.configured} onClick={() => void auth.login(remember)}>{auth.busy ? "Signing in…" : "Sign in with Google"}</button>
      {!auth.configured && <span className="account-note">Sign-in unavailable · guest mode</span>}
    </>}
    {auth.error && <p className="account-error" role="status">{auth.error}{auth.error.includes("blocked") && <button type="button" onClick={() => void auth.login(remember, true)}>Continue sign-in</button>}</p>}
  </div>;
}
