import type { Metadata, Viewport } from "next";
import { LandingPage } from "@/components/landing-page";

export const metadata: Metadata = {
  title: "Know Your Route. Before You Head Out. — AeroRoute",
  description: "Compare travel time and estimated air-pollution exposure, then choose a route within your time budget.",
};

export const viewport: Viewport = { themeColor: "#000000", colorScheme: "dark", viewportFit: "cover" };

export default function Home() {
  return <LandingPage />;
}
