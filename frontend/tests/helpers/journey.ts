import { expect, type Page } from "@playwright/test";
import type { ComparisonResponse } from "../../src/types/api";

export async function mockMap(page: Page) {
  await page.route("https://d8j0ntlcm91z4.cloudfront.net/**", route => route.abort());
  // Browser fixtures never contact Mapbox. Individual search tests override this route.
  await page.route("**/api.mapbox.com/**", route => {
    if (route.request().url().includes("/styles/v1/mapbox/dark-v11")) return route.fulfill({ json: {
      version: 8, sources: {}, layers: [{ id: "background", type: "background", paint: { "background-color": "#101719" } }],
    } });
    return route.abort();
  });
}

export async function openPlanner(page: Page) {
  // A comparison closes the mobile drawer when its response is committed.
  // Wait for that commit before reopening it to inspect or edit the plan.
  await expect(page.locator(".primary-button")).toBeEnabled();
  if (await page.locator(".planner-drawer").isVisible()) return;
  const toggle = page.getByRole("button", { name: "Open journey planner", exact: true });
  if (await toggle.isVisible()) {
    await toggle.click();
    await expect(page.getByRole("dialog", { name: "Plan a journey", exact: true })).toBeVisible();
  }
}

export async function closePlanner(page: Page) {
  if (await page.locator(".planner-drawer").isVisible()) {
    await page.getByRole("button", { name: "Close journey planner", exact: true }).click();
    await expect(page.locator(".planner-drawer")).not.toBeVisible();
  }
}

export async function compareRoutes(page: Page, mode = "walking") {
  await openPlanner(page);
  await page.getByRole("button", { name: `Compare ${mode} routes`, exact: true }).click();
  await expect(page.locator(".primary-button")).toBeEnabled();
}

export function comparison(status: ComparisonResponse["status"] = "uncertain_difference"): ComparisonResponse {
  const limited = status === "limited_data";
  return {
    mode: "walking", routing_profile: "walking", status, fastest_id: "fast", lowest_exposure_eligible_id: limited ? null : "slow",
    estimated_reduction_percent: null, warnings: ["Synthetic browser fixture; not Delhi observations."],
    candidates: status === "no_route" ? [] : [
      { id: "fast", geometry: { type: "LineString", coordinates: [[77.2, 28.6], [77.21, 28.61]] },
        duration_seconds: 1200, distance_metres: 1000, estimated_exposure: limited ? null : 1600,
        exposure_unit: "µg·min/m³", within_budget: true, coverage_percent: limited ? 0 : 100 },
      { id: "slow", geometry: { type: "LineString", coordinates: [[77.2, 28.6], [77.22, 28.61]] },
        duration_seconds: 1500, distance_metres: 1200, estimated_exposure: limited ? null : 1250,
        exposure_unit: "µg·min/m³", within_budget: true, coverage_percent: limited ? 0 : 100, via: { lat: 28.605, lng: 77.215 } },
    ],
    data_quality: {
      data_mode: limited ? "live" : "replay", observed_from: "2026-10-07T12:00:00Z",
      observed_to: "2026-10-07T13:00:00Z", fetched_at: "2026-10-08T12:00:00Z",
      reference_time: "2026-10-07T13:00:00Z", station_count: limited ? 0 : 3,
      source_ids: ["synthetic:sensor:1"], provider_ids: ["synthetic"],
      snapshot_id: "synthetic", data_version: "synthetic", model_version: "idw-v1-fixture",
      model_parameters: {},
    },
  };
}

export async function journey(page: Page) {
  await page.goto("/journey");
  await openPlanner(page);
  await page.getByRole("button", { name: "Try recorded Delhi journey" }).click();
  await page.getByRole("checkbox", { name: "Use recorded pollution observations" }).uncheck();
}

export function trafficComparison(coverage = 0) {
  const data = comparison();
  data.mode = "driving";
  data.routing_profile = "driving-traffic";
  data.candidates.forEach(route => { route.traffic = {
    fetched_at: "2026-10-10T08:00:00Z", typical_duration_seconds: 1800,
    coverage_percent: coverage, congested_percent: coverage ? 40 : 0,
  }; });
  return data;
}
