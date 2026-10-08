import type { ComparisonRequest, HealthResponse } from "@/types/api";

const baseUrl = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export async function checkHealth(): Promise<HealthResponse> {
  const response = await fetch(`${baseUrl}/health`, {
    signal: AbortSignal.timeout(5000),
    cache: "no-store",
  });
  if (!response.ok) throw new Error("The service is unavailable. Try again shortly.");
  return response.json();
}

export async function compareJourney(request: ComparisonRequest): Promise<void> {
  const response = await fetch(`${baseUrl}/api/routes/compare`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal: AbortSignal.timeout(10000),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail;
    throw new Error(
      typeof detail?.message === "string"
        ? detail.message
        : "This journey could not be compared. Check your locations and try again.",
    );
  }
  // Real result rendering is the next implementation step.
  throw new Error("Route results are not available in this setup preview yet.");
}
