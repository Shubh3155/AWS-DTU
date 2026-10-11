import type { Metadata, Viewport } from "next";
import { AboutPage } from "@/components/about-page";

export const metadata: Metadata = {
  title: "About AeroRoute — a more informed journey",
  description: "Learn how AeroRoute compares journey time and estimated outdoor air-pollution exposure within your extra-time allowance.",
};

export const viewport: Viewport = { themeColor: "#000000", colorScheme: "dark", viewportFit: "cover" };

export default function About() {
  return <AboutPage />;
}
