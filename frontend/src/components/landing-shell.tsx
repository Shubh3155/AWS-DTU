"use client";

import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/auth-provider";
import { AppLogo } from "@/components/app-logo";
import "./landing-page.css";

declare global {
  interface Window {
    __landingMotionTimer?: ReturnType<typeof setTimeout>;
    __landingEntranceStarted?: boolean;
  }
}

const compactQuery = "(max-width: 790px), (max-width: 1100px) and (orientation: portrait)";

function finishEntrance() {
  document.documentElement.classList.remove("motion-pending");
  window.clearTimeout(window.__landingMotionTimer);
}

export function LandingShell({ children, page = "home" }: { children: ReactNode; page?: "home" | "about" }) {
  const auth = useAuth();
  const router = useRouter();
  const header = useRef<HTMLElement>(null);
  const menuToggle = useRef<HTMLButtonElement>(null);
  const firstLink = useRef<HTMLAnchorElement>(null);
  const video = useRef<HTMLVideoElement>(null);
  const [compact, setCompact] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [showAuthError, setShowAuthError] = useState(false);

  useLayoutEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (!reduced.matches && !window.__landingEntranceStarted) {
      document.documentElement.classList.add("motion-pending");
      window.__landingMotionTimer = setTimeout(finishEntrance, 3500);
    }
    window.__landingEntranceStarted = true;
    function updateMotion() {
      if (reduced.matches) { finishEntrance(); video.current?.pause(); }
      else void video.current?.play().catch(() => {});
    }
    updateMotion();
    reduced.addEventListener("change", updateMotion);
    return () => {
      finishEntrance();
      window.__landingEntranceStarted = false;
      reduced.removeEventListener("change", updateMotion);
    };
  }, [page]);

  useEffect(() => {
    const query = window.matchMedia(compactQuery);
    function update() { setCompact(query.matches); if (!query.matches) setMenuOpen(false); }
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    if (!menuOpen) return;
    const focusFrame = requestAnimationFrame(() => firstLink.current?.focus({ preventScroll: true }));
    function outside(event: PointerEvent) {
      if (event.target instanceof Node && !header.current?.contains(event.target)) setMenuOpen(false);
    }
    function escape(event: KeyboardEvent) {
      if (event.key === "Escape") { setMenuOpen(false); menuToggle.current?.focus(); }
    }
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", escape);
    return () => {
      cancelAnimationFrame(focusFrame);
      document.removeEventListener("pointerdown", outside);
      document.removeEventListener("keydown", escape);
    };
  }, [menuOpen]);

  async function signUp() {
    setShowAuthError(true);
    if (auth.user || await auth.login(true)) router.push("/journey");
  }

  return <main className={`landing-viewport${page === "about" ? " about-viewport" : ""}`} onAnimationEnd={event => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    if (page === "home" && target.classList.contains("primary-cta") && event.animationName === "entrance-action") finishEntrance();
    if (page === "about" && target.classList.contains("about-details") && event.animationName === "entrance-panel") finishEntrance();
  }}>
    <section className="screen" id="screen" aria-label="AeroRoute">
      <video ref={video} className="background" autoPlay muted loop playsInline disablePictureInPicture aria-hidden="true">
        <source src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260808_064556_051587f1-74a1-4336-8c05-4dde3594ed05.mp4" type="video/mp4" />
      </video>
      <header ref={header} className={`header${menuOpen ? " menu-open" : ""}`}>
        <Link className="brand" href="/" aria-label="AeroRoute home" onClick={() => setMenuOpen(false)}>
          <AppLogo width={35} height={25} />
        </Link>
        <div className="header-actions" id="tablet-navigation" inert={compact && !menuOpen}>
          <nav className="nav" aria-label="Main navigation" onClick={() => setMenuOpen(false)}>
            <Link ref={firstLink} href="/" aria-current={page === "home" ? "page" : undefined}>Home</Link>
            <Link href="/journey">Plan</Link>
            <Link href="/journey#recent-routes">Routes</Link>
            <Link href="/about" aria-current={page === "about" ? "page" : undefined}>About</Link>
          </nav>
          <div className="time-panel">
            <span className="time-label">Timezone</span>
            <span className="time-value">9:47 PM&nbsp; • &nbsp;14 July 2026</span>
          </div>
          <button type="button" className="sign-up" disabled={!auth.ready || auth.busy} onClick={() => void signUp()}>
            <span>{auth.busy ? "Signing in…" : auth.user ? "Open App" : "Sign Up"}</span>
          </button>
        </div>
        <button ref={menuToggle} type="button" className="menu-toggle" aria-label={menuOpen ? "Close menu" : "Open menu"}
          aria-expanded={menuOpen} aria-controls="tablet-navigation" onClick={() => setMenuOpen(open => !open)}>
          <svg width="22" height="22" viewBox="0 0 22 22" fill="none" aria-hidden="true">
            <path className="menu-line-one" d="M3 7.5h16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            <path className="menu-line-two" d="M3 14.5h16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </button>
      </header>
      {children}
      {showAuthError && auth.error && <p className="landing-auth-error" role="status">{auth.error}</p>}
    </section>
  </main>;
}
