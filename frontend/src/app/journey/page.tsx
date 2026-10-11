import type { Viewport } from "next";
import { JourneyWorkspace } from "@/components/journey-workspace";

export const viewport: Viewport = { themeColor: "#000000", colorScheme: "dark", viewportFit: "cover" };

export default function Journey() {
  return <JourneyWorkspace />;
}
