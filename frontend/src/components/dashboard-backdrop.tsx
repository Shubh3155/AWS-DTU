"use client";

import { useEffect, useRef } from "react";

export function DashboardBackdrop() {
  const video = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
    function updateMotion() {
      if (reduced.matches) video.current?.pause();
      else void video.current?.play().catch(() => {});
    }
    updateMotion();
    reduced.addEventListener("change", updateMotion);
    return () => reduced.removeEventListener("change", updateMotion);
  }, []);

  return <div className="dashboard-backdrop" aria-hidden="true">
    <video ref={video} autoPlay muted loop playsInline disablePictureInPicture>
      <source src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260808_064556_051587f1-74a1-4336-8c05-4dde3594ed05.mp4" type="video/mp4" />
    </video>
  </div>;
}
