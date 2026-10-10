import { expect, test } from "@playwright/test";
import { distance, journeyProgress, projectOnRoute, routeFeatures } from "../src/lib/navigation";
import type { RouteCandidate } from "../src/types/api";
const route: RouteCandidate = { id: "fixture", geometry: { type: "LineString", coordinates: [[77.2,28.6],[77.21,28.6],[77.21,28.61]] },
  distance_metres: 2000, duration_seconds: 1200, within_budget: true, coverage_percent: 0, estimated_exposure: null, exposure_unit: "µg·min/m³" };

test("route progress projects onto ordered segments and clamps past endpoints", () => {
  const halfway = projectOnRoute(route.geometry.coordinates, { lng: 77.205, lat: 28.6 });
  expect(halfway.offset).toBeLessThan(1);
  expect(halfway.progress).toBeGreaterThan(450);
  expect(halfway.progress).toBeLessThan(510);
  const end = projectOnRoute(route.geometry.coordinates, { lng: 77.21, lat: 28.615 });
  expect(end.progress).toBeCloseTo(end.total);
  const before = projectOnRoute(route.geometry.coordinates, { lng: 77.195, lat: 28.6 });
  expect(before.progress).toBe(0);
});

test("off-route or imprecise GPS cannot mark a trip as arrived", () => {
  const fix = { lng: 77.21, lat: 28.61, accuracy: 5, heading: null, timestamp: Date.now() };
  expect(journeyProgress(route, fix).arrived).toBe(true);
  expect(journeyProgress(route, { ...fix, accuracy: 500 }).arrived).toBe(false);
  expect(journeyProgress(route, { ...fix, lat: 28.62 }).offRoute).toBe(true);
  expect(journeyProgress(route, { ...fix, lat: 28.62 }).arrived).toBe(false);
});

test("date-line distances stay local and alternate geometry stays in the map data", () => {
  expect(distance({ lng: 179.999, lat: 0 }, { lng: -179.999, lat: 0 })).toBeLessThan(230);
  const features = routeFeatures([route, { ...route, id: "alternative" }], "alternative");
  expect(features.features).toHaveLength(2);
  expect(features.features.map(feature => feature.properties.active)).toEqual([false, true]);
});
