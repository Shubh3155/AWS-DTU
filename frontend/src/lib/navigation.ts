import type { Coordinate, RouteCandidate } from "@/types/api";

const metres = 111195;
const wrap = (degrees: number) => ((degrees + 540) % 360) - 180;
export function distance(a: Coordinate, b: Coordinate) {
  const lat1 = a.lat * Math.PI / 180, lat2 = b.lat * Math.PI / 180;
  const h = Math.sin((lat2 - lat1) / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(wrap(b.lng - a.lng) * Math.PI / 360) ** 2;
  return 12742000 * Math.asin(Math.min(1, Math.sqrt(h)));
}

export function projectOnRoute(points: [number, number][], position: Coordinate, previous = 0) {
  let travelled = 0, progress = 0, nearest = Infinity;
  const scale = metres * Math.cos(position.lat * Math.PI / 180);
  for (let index = 1; index < points.length; index += 1) {
    const a = { lng: points[index - 1][0], lat: points[index - 1][1] };
    const b = { lng: points[index][0], lat: points[index][1] };
    const ax = wrap(a.lng - position.lng) * scale, ay = (a.lat - position.lat) * metres;
    const dx = wrap(b.lng - a.lng) * scale, dy = (b.lat - a.lat) * metres;
    const squared = dx * dx + dy * dy;
    const fraction = squared ? Math.max(0, Math.min(1, -(ax * dx + ay * dy) / squared)) : 0;
    const offset = Math.hypot(ax + fraction * dx, ay + fraction * dy);
    const length = distance(a, b), candidate = travelled + fraction * length;
    // At crossings/overlapping roads, favour the part nearest previous progress.
    if (offset < nearest - 3 || (Math.abs(offset - nearest) <= 3 && Math.abs(candidate - previous) < Math.abs(progress - previous))) {
      nearest = offset; progress = candidate;
    }
    travelled += length;
  }
  return { progress, total: travelled, offset: nearest };
}

export type LocationFix = Coordinate & { accuracy: number; heading: number | null; timestamp: number };
export function journeyProgress(route: RouteCandidate, fix: LocationFix, previous = 0) {
  const points = route.geometry.coordinates;
  const projected = projectOnRoute(points, fix, previous);
  const fraction = projected.total ? projected.progress / projected.total : 0;
  const offRoute = projected.offset > Math.max(40, fix.accuracy * 2);
  const reliable = fix.accuracy <= 60;
  const end = { lng: points.at(-1)![0], lat: points.at(-1)![1] };
  const arrived = reliable && fix.accuracy <= 30 && !offRoute && distance(fix, end) <= 25 && projected.total - projected.progress <= 35;
  const maneuvers = (route.maneuvers ?? []).map(maneuver => ({ ...maneuver,
    at: projectOnRoute(points, { lng: maneuver.location[0], lat: maneuver.location[1] }, projected.progress).progress,
  }));
  const next = maneuvers.find(maneuver => maneuver.at > projected.progress + 12);
  return { ...projected, fraction, offRoute, reliable, arrived,
    remainingMetres: Math.max(0, route.distance_metres * (1 - fraction)),
    remainingSeconds: Math.max(0, route.duration_seconds * (1 - fraction)),
    instruction: next?.type === "arrive" ? "Destination ahead" : next?.instruction ?? "Follow the highlighted route",
    turnMetres: next ? Math.max(0, next.at - projected.progress) : null,
  };
}

export function routeFeatures(routes: RouteCandidate[], activeId: string | null) {
  return { type: "FeatureCollection" as const, features: routes.map(route => ({
    type: "Feature" as const, geometry: route.geometry, properties: { active: route.id === activeId },
  })) };
}
