import type { RouteCandidate } from "@/types/api";

export function TrafficDetails({ route }: { route: RouteCandidate }) {
  const traffic = route.traffic;
  if (!traffic) return null;
  const difference = traffic.typical_duration_seconds === null ? null : (route.duration_seconds - traffic.typical_duration_seconds) / 60;
  return <div className="traffic-details">
    <p className="traffic-label">Traffic-profile estimate</p>
    <p>{traffic.coverage_percent === 0 ? "Congestion data unavailable · traffic is unknown" :
      `${traffic.coverage_percent.toFixed(0)}% of route has reported congestion data · ${traffic.congested_percent.toFixed(0)}% heavy/severe`}</p>
    {difference !== null && <p>{Math.abs(difference) < 0.5 ? "Similar to typical travel time" :
      `${Math.abs(difference).toFixed(1)} min ${difference > 0 ? "slower" : "faster"} than typical`}</p>}
    <p>Requested {new Intl.DateTimeFormat("en-IN", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Kolkata" }).format(new Date(traffic.fetched_at))} IST · current/historical provider estimate</p>
  </div>;
}
