"use client";

import Link from "next/link";
import { LandingShell } from "@/components/landing-shell";

export function LandingPage() {
  return <LandingShell>
    <section className="hero" aria-labelledby="hero-title">
      <div className="hero-content">
        <h1 className="hero-title" id="hero-title">
          <span className="line line-one"><span className="line-reveal">Know Your Route.</span></span>
          <span className="line line-two"><span className="line-reveal">Before You Head Out.</span></span>
        </h1>
        <p className="hero-copy">Your journey is more than the quickest way there.<br />
          AeroRoute compares time and estimated air pollution,<br />
          so you can choose within your time budget.</p>
        <Link href="/journey" className="primary-cta">
          <span className="label">Get Started</span>
          <span className="arrow-box" aria-hidden="true"><svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M3 11 11 3M3 3h8v8" stroke="#fff" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
          </svg></span>
        </Link>
      </div>
    </section>
  </LandingShell>;
}
