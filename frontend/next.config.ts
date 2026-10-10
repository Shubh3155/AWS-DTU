import type { NextConfig } from "next";

const backendUrl = (process.env.AEROROUTE_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  distDir: process.env.AEROROUTE_FIREBASE_TESTS === "true" ? ".next-firebase-tests" : ".next",
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${backendUrl}/api/:path*` },
      { source: "/health", destination: `${backendUrl}/health` },
    ];
  },
  async headers() {
    return [{ source: "/firebase-messaging-sw.js", headers: [
      { key: "Cache-Control", value: "no-cache" },
      { key: "Service-Worker-Allowed", value: "/" },
    ] }];
  },
};

export default nextConfig;
