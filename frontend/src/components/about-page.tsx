"use client";

import Link from "next/link";
import { LandingShell } from "@/components/landing-shell";
import "./about-page.css";

export function AboutPage() {
  return <LandingShell page="about">
    <div className="about-content" tabIndex={0} role="region" aria-label="About AeroRoute">
      <section className="about-intro" aria-labelledby="about-title">
        <p className="about-eyebrow">About AeroRoute</p>
        <h1 className="hero-title" id="about-title">
          <span className="line line-one"><span className="line-reveal">A little more time.</span></span>
          <span className="line line-two"><span className="line-reveal">A clearer choice.</span></span>
        </h1>
        <div className="hero-copy">
          <p>The fastest route is only part of the picture. AeroRoute helps you compare travel time and estimated air-pollution exposure along your journey, with room for a detour that works for you.</p>
          <p>Walk, drive or take a motorcycle. Choose how much extra time you can spend, review the available routes, and make a more informed choice before you head out.</p>
        </div>
        <Link href="/journey" className="primary-cta">
          <span className="label">Get Started</span>
          <span className="arrow-box" aria-hidden="true"><svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M3 11 11 3M3 3h8v8" stroke="#fff" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
          </svg></span>
        </Link>
      </section>
      <section className="about-details" aria-labelledby="how-it-works">
        <p className="about-eyebrow">From plan to journey</p>
        <h2 id="how-it-works">How AeroRoute works</h2>
        <ol className="about-steps">
          <li>
            <span className="step-number" aria-hidden="true">01</span>
            <div><h3>Set your journey</h3><p>Choose your start and destination, a travel mode, and the maximum extra time you can spend.</p></div>
          </li>
          <li>
            <span className="step-number" aria-hidden="true">02</span>
            <div><h3>Compare with context</h3><p>Review time, distance and estimated outdoor PM2.5 exposure. Live readings and recorded observations are labelled separately.</p></div>
          </li>
          <li>
            <span className="step-number" aria-hidden="true">03</span>
            <div><h3>Start when you’re ready</h3><p>Plan and compare as a guest. Sign in with Google at Start journey, then follow GPS guidance with route updates along the way.</p></div>
          </li>
        </ol>
        <aside className="about-estimates" aria-label="Understanding the estimates">
          <h3>Estimates, with their limits.</h3>
          <p>Pollution estimates are provisional. A lower estimate does not establish a cleaner or healthier route. Missing or stale readings stay unavailable.</p>
          <p>Scores describe outdoor air, not cabin air. Motorcycle times currently use car-routing estimates.</p>
        </aside>
      </section>
    </div>
  </LandingShell>;
}
