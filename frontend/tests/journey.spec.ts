import { expect, test, type Page } from "@playwright/test";
import type { ComparisonResponse } from "../src/types/api";

test.beforeEach(async ({ page }) => {
  // Browser fixtures never contact Mapbox. Individual search tests override this route.
  await page.route("**/api.mapbox.com/**", route => route.abort());
});

function comparison(status: ComparisonResponse["status"] = "uncertain_difference"): ComparisonResponse {
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

async function journey(page: Page) {
  await page.goto("/");
  await page.getByRole("button", { name: "Try recorded Delhi journey" }).click();
  await page.getByRole("checkbox", { name: "Use recorded pollution observations" }).uncheck();
}

test("recorded demo preset fills the verified journey and explicitly selects replay", async ({ page }) => {
  let request: Record<string, unknown> = {};
  await page.route("**/api/routes/compare", async route => {
    request = route.request().postDataJSON();
    await route.fulfill({ json: comparison() });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Try recorded Delhi journey" }).click();
  await expect(page.getByRole("textbox", { name: "origin location" })).toHaveValue("Recorded Delhi start");
  await expect(page.getByRole("textbox", { name: "destination location" })).toHaveValue("Recorded Delhi destination");
  await expect(page.getByRole("checkbox", { name: "Use recorded pollution observations" })).toBeChecked();
  await expect(page.getByRole("slider", { name: "Maximum extra time" })).toHaveValue("5");
  await page.getByRole("button", { name: "Compare walking routes" }).click();
  await expect(page.getByText("Estimated exposure: 1250.0 µg·min/m³")).toBeVisible();
  expect(request).toMatchObject({ origin: { lat: 28.6315, lng: 77.2167 },
    destination: { lat: 28.628, lng: 77.241 }, data_mode: "replay", max_detour_minutes: 5 });
});

test("explicit replay shows scores, source times and uncertainty without overflow", async ({ page }) => {
  let mode = "";
  await page.route("**/api/routes/compare", async route => {
    mode = route.request().postDataJSON().data_mode;
    await route.fulfill({ json: comparison() });
  });
  await journey(page);
  await page.getByRole("checkbox", { name: "Use recorded pollution observations" }).check();
  await page.getByRole("button", { name: "Compare walking routes" }).click();
  await expect(page.getByText("Estimated exposure: 1250.0 µg·min/m³")).toBeVisible();
  expect(mode).toBe("replay");
  await expect(page.getByText(/Waypoint-generated candidate/)).toBeVisible();
  await expect(page.getByRole("heading", { name: /Recorded-data replay/ })).toBeVisible();
  await expect(page.getByText(/The difference is uncertain/)).toBeVisible();
  await expect(page.getByText(/Historical reference:/)).toContainText("IST");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: test.info().outputPath("replay.png"), fullPage: true });
});

test("live limited support never displays zero exposure", async ({ page }) => {
  let mode = "";
  await page.route("**/api/routes/compare", async route => {
    mode = route.request().postDataJSON().data_mode;
    await route.fulfill({ json: comparison("limited_data") });
  });
  await journey(page);
  await page.getByRole("button", { name: "Compare walking routes" }).click();
  await expect(page.getByText("Estimated exposure: Unavailable")).toHaveCount(2);
  expect(mode).toBe("live");
  await expect(page.getByText("Data support is insufficient to compare full-route exposures.")).toBeVisible();
});

test("changing allowance or replay mode clears old scores", async ({ page }) => {
  await page.route("**/api/routes/compare", route => route.fulfill({ json: comparison() }));
  await journey(page);
  await page.getByRole("button", { name: "Compare walking routes" }).click();
  await expect(page.getByText("Estimated exposure: 1600.0 µg·min/m³")).toBeVisible();
  await page.getByRole("slider", { name: "Maximum extra time" }).focus();
  await page.keyboard.press("Home");
  await expect(page.getByText("Waiting for a journey")).toBeVisible();
  await page.getByRole("button", { name: "Compare walking routes" }).click();
  await expect(page.getByText("Estimated exposure: 1600.0 µg·min/m³")).toBeVisible();
  await page.getByRole("checkbox", { name: "Use recorded pollution observations" }).check();
  await expect(page.getByText("Waiting for a journey")).toBeVisible();
});

test("no-route state provides a recoverable result", async ({ page }) => {
  await page.route("**/api/routes/compare", route => route.fulfill({ json: comparison("no_route") }));
  await journey(page);
  await page.getByRole("button", { name: "Compare walking routes" }).click();
  await expect(page.getByText("No route found")).toBeVisible();
});

test("provider error is shown and comparison can be retried", async ({ page }) => {
  await page.route("**/api/routes/compare", route => route.fulfill({ status: 503,
    json: { detail: { code: "routing_rate_limited", message: "Routing is rate limited; retry later." } } }));
  await journey(page);
  await page.getByRole("button", { name: "Compare walking routes" }).click();
  await expect(page.getByText("Routing is rate limited; retry later.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Compare walking routes" })).toBeEnabled();
});

test("route hover previews, selection persists and a new request resets it", async ({ page }) => {
  await page.route("**/api/routes/compare", route => route.fulfill({ json: comparison() }));
  await journey(page);
  await page.getByRole("button", { name: "Compare walking routes" }).click();
  const first = page.getByRole("button", { name: "Show route 1 on map" });
  const second = page.getByRole("button", { name: "Show route 2 on map" });
  await expect(first).toHaveAttribute("aria-pressed", "true");
  await second.hover();
  await expect(second.locator("..")).toHaveClass(/route-active/);
  await expect(second).toHaveAttribute("aria-pressed", "false");
  await second.click();
  await page.mouse.move(0, 0);
  await expect(second).toHaveAttribute("aria-pressed", "true");
  await expect(second.locator("..")).toHaveClass(/route-active/);
  await first.focus();
  await expect(first.locator("..")).toHaveClass(/route-active/);
  await first.press("Enter");
  await expect(first).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("slider", { name: "Maximum extra time" }).focus();
  await page.keyboard.press("Home");
  await expect(page.getByText("Waiting for a journey")).toBeVisible();
  await page.getByRole("button", { name: "Compare walking routes" }).click();
  await expect(first).toHaveAttribute("aria-pressed", "true");
});


test("editing a selected place invalidates its coordinates and previous scores", async ({ page }) => {
  let calls = 0;
  await page.route("**/api/routes/compare", route => { calls += 1; return route.fulfill({ json: comparison() }); });
  await journey(page);
  await page.getByRole("button", { name: "Compare walking routes" }).click();
  await expect(page.getByText("Estimated exposure: 1600.0 µg·min/m³")).toBeVisible();
  await page.getByRole("textbox", { name: "origin location" }).fill("New Delhi");
  await expect(page.getByText("Waiting for a journey")).toBeVisible();
  await page.getByRole("button", { name: "Compare walking routes" }).click();
  await expect(page.getByText("Choose both locations from search results, your current location, or the map.")).toBeVisible();
  expect(calls).toBe(1);
});

test("current location uses permission and sends browser coordinates", async ({ page, context }) => {
  await context.grantPermissions(["geolocation"]);
  await context.setGeolocation({ latitude: 28.6, longitude: 77.2 });
  let request: Record<string, unknown> = {};
  await page.route("**/api/routes/compare", route => {
    request = route.request().postDataJSON(); return route.fulfill({ json: comparison() });
  });
  await journey(page);
  await page.getByRole("button", { name: "Use current location for origin" }).click();
  await expect(page.getByRole("textbox", { name: "origin location" })).toHaveValue("Current location");
  await page.getByRole("button", { name: "Compare walking routes" }).click();
  await expect(page.getByText("Estimated exposure: 1600.0 µg·min/m³")).toBeVisible();
  expect(request.origin).toEqual({ lat: 28.6, lng: 77.2 });
});

test("denied location is recoverable without discarding an existing place", async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "geolocation", { value: {
      getCurrentPosition: (_success: unknown, failure: (error: { code: number }) => void) => failure({ code: 1 }),
    } });
  });
  await journey(page);
  await page.getByRole("button", { name: "Use current location for origin" }).click();
  await expect(page.getByText("Location permission was denied. Search or choose on the map instead.")).toBeVisible();
  await expect(page.getByRole("textbox", { name: "origin location" })).toHaveValue("Recorded Delhi start");
});

test("search selects a matching place and sends its hidden coordinates", async ({ page }) => {
  let request: Record<string, unknown> = {};
  await page.route("**/api.mapbox.com/search/geocode/v6/forward?**", route => route.fulfill({ json: {
    features: [{ id: "fixture-place", geometry: { coordinates: [77.22, 28.62] }, properties: { full_address: "Fixture street, Delhi" } }],
  } }));
  await page.route("**/api/routes/compare", route => {
    request = route.request().postDataJSON(); return route.fulfill({ json: comparison() });
  });
  await journey(page);
  await page.getByRole("textbox", { name: "origin location" }).fill("Fixture street");
  await page.getByRole("textbox", { name: "origin location" }).press("Enter");
  await page.getByRole("button", { name: /Fixture street, Delhi/ }).click();
  await expect(page.getByRole("textbox", { name: "origin location" })).toHaveValue("Fixture street, Delhi");
  await page.getByRole("button", { name: "Compare walking routes" }).click();
  await expect(page.getByText("Estimated exposure: 1600.0 µg·min/m³")).toBeVisible();
  expect(request.origin).toEqual({ lat: 28.62, lng: 77.22 });
});


test("travel mode changes clear old routes and submit the selected provider mode", async ({ page }) => {
  const modes: string[] = [];
  await page.route("**/api/routes/compare", route => {
    const mode = route.request().postDataJSON().mode;
    modes.push(mode);
    return route.fulfill({ json: { ...comparison(), mode, routing_profile: mode === "walking" ? "walking" : "driving" } });
  });
  await journey(page);
  await page.getByRole("button", { name: "Compare walking routes" }).click();
  await expect(page.getByText("Estimated exposure: 1600.0 µg·min/m³")).toBeVisible();
  for (const [button, label] of [["Car", "car"], ["Motorcycle", "motorcycle"]]) {
    await page.getByRole("button", { name: button, exact: true }).click();
    await expect(page.getByText("Waiting for a journey")).toBeVisible();
    await page.getByRole("button", { name: `Compare ${label} routes` }).click();
    await expect(page.getByText("Estimated exposure: 1600.0 µg·min/m³")).toBeVisible();
  }
  expect(modes).toEqual(["walking", "driving", "motorcycle"]);
  await expect(page.getByText(/Car routing estimate/)).toBeVisible();
  await page.getByRole("button", { name: "Try recorded Delhi journey" }).click();
  await expect(page.getByRole("button", { name: "Walk", exact: true })).toHaveAttribute("aria-pressed", "true");
});
