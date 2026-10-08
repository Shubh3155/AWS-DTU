import type { NextConfig } from "next";

const backendUrl = (process.env.AEROROUTE_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${backendUrl}/api/:path*` },
      { source: "/health", destination: `${backendUrl}/health` },
    ];
  },
};

export default nextConfig;
