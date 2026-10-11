import { expect, test } from "@playwright/test";
import { closePlanner, compareRoutes, comparison, journey, mockMap, openPlanner, trafficComparison } from "./helpers/journey";

test.beforeEach(async ({ page }) => { await mockMap(page); });

test("recorded demo preset fills the verified journey and explicitly selects replay", async ({ page }) => {
  let request: Record<string, unknown> = {};
  await page.route("**/api/routes/compare", async route => {
    request = route.request().postDataJSON();
    await route.fulfill({ json: comparison() });
  });
  await page.goto("/journey");
  await openPlanner(page);
  await page.getByRole("button", { name: "Try recorded Delhi journey" }).click();
  await expect(page.locator('input[aria-label="origin location"]')).toHaveValue("Recorded Delhi start");
  await expect(page.locator('input[aria-label="destination location"]')).toHaveValue("Recorded Delhi destination");
  await expect(page.getByRole("checkbox", { name: "Use recorded pollution observations" })).toBeChecked();
  await expect(page.getByRole("slider", { name: "Maximum extra time" })).toHaveValue("5");
  await compareRoutes(page, "walking");
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
  await openPlanner(page);
  await page.getByRole("checkbox", { name: "Use recorded pollution observations" }).check();
  await compareRoutes(page, "walking");
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
  await compareRoutes(page, "walking");
  await expect(page.getByText("Estimated exposure: Unavailable")).toHaveCount(2);
  expect(mode).toBe("live");
  await expect(page.getByText("Data support is insufficient to compare full-route exposures.")).toBeVisible();
});

test("live model scores show regional coverage and attribution without invented stations", async ({ page }) => {
  const data = comparison();
  data.data_quality = { ...data.data_quality, data_mode: "live", source_type: "model_forecast",
    observed_from: null, observed_to: null, snapshot_id: null, station_count: 0, sample_count: 4,
    valid_from: "2026-10-11T10:00:00Z", valid_to: "2026-10-11T11:00:00Z",
    spatial_resolution_km: 45, provider_ids: ["Open-Meteo / Copernicus CAMS Global"],
    model_version: "cams-global-current-route-v1" };
  await page.route("**/api/routes/compare", route => route.fulfill({ json: data }));
  await journey(page);
  await compareRoutes(page, "walking");
  await expect(page.getByText("Estimated exposure: 1600.0 µg·min/m³")).toBeVisible();
  await expect(page.getByText("Air-quality time coverage: 100%")).toHaveCount(2);
  await expect(page.getByRole("heading", { name: "Current regional air-quality forecast" })).toBeVisible();
  await expect(page.getByText(/Forecast valid:/)).toContainText("IST");
  await expect(page.getByText(/Route sampling regions: 4/)).toBeVisible();
  await expect(page.getByText(/Regional model resolution: approximately 45 km/)).toBeVisible();
  await expect(page.getByText(/Time-filtered stations:/)).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Open-Meteo", exact: true })).toHaveAttribute("href", "https://open-meteo.com/en/docs/air-quality-api");
  await expect(page.getByRole("link", { name: "Copernicus CAMS", exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("changing allowance or replay mode clears old scores", async ({ page }) => {
  await page.route("**/api/routes/compare", route => route.fulfill({ json: comparison() }));
  await journey(page);
  await compareRoutes(page, "walking");
  await expect(page.getByText("Estimated exposure: 1600.0 µg·min/m³")).toBeVisible();
  await openPlanner(page);
  await page.getByRole("slider", { name: "Maximum extra time" }).focus();
  await page.keyboard.press("Home");
  await closePlanner(page);
  await expect(page.getByText("Waiting for a journey")).toBeVisible();
  await compareRoutes(page, "walking");
  await expect(page.getByText("Estimated exposure: 1600.0 µg·min/m³")).toBeVisible();
  await openPlanner(page);
  await page.getByRole("checkbox", { name: "Use recorded pollution observations" }).check();
  await closePlanner(page);
  await expect(page.getByText("Waiting for a journey")).toBeVisible();
});

test("no-route state provides a recoverable result", async ({ page }) => {
  await page.route("**/api/routes/compare", route => route.fulfill({ json: comparison("no_route") }));
  await journey(page);
  await compareRoutes(page, "walking");
  await expect(page.getByText("No route found")).toBeVisible();
});

test("provider error is shown and comparison can be retried", async ({ page }) => {
  await page.route("**/api/routes/compare", route => route.fulfill({ status: 503,
    json: { detail: { code: "routing_rate_limited", message: "Routing is rate limited; retry later." } } }));
  await journey(page);
  await compareRoutes(page, "walking");
  await expect(page.getByText("Routing is rate limited; retry later.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Compare walking routes" })).toBeEnabled();
});

test("route hover previews, selection persists and a new request resets it", async ({ page }) => {
  await page.route("**/api/routes/compare", route => route.fulfill({ json: comparison() }));
  await journey(page);
  await compareRoutes(page, "walking");
  const first = page.getByRole("button", { name: "Show route 1 on map" });
  const second = page.getByRole("button", { name: "Show route 2 on map" });
  await expect(second).toHaveAttribute("aria-pressed", "true");
  await first.hover();
  await expect(first.locator("..")).toHaveClass(/route-active/);
  await expect(first).toHaveAttribute("aria-pressed", "false");
  await first.click();
  await page.mouse.move(0, 0);
  await expect(first).toHaveAttribute("aria-pressed", "true");
  await second.focus();
  await expect(second.locator("..")).toHaveClass(/route-active/);
  await second.press("Enter");
  await expect(second).toHaveAttribute("aria-pressed", "true");
  await openPlanner(page);
  await page.getByRole("slider", { name: "Maximum extra time" }).focus();
  await page.keyboard.press("Home");
  await closePlanner(page);
  await expect(page.getByText("Waiting for a journey")).toBeVisible();
  await compareRoutes(page, "walking");
  await expect(second).toHaveAttribute("aria-pressed", "true");
});


test("editing a selected place invalidates its coordinates and previous scores", async ({ page }) => {
  let calls = 0;
  await page.route("**/api/routes/compare", route => { calls += 1; return route.fulfill({ json: comparison() }); });
  await journey(page);
  await compareRoutes(page, "walking");
  await expect(page.getByText("Estimated exposure: 1600.0 µg·min/m³")).toBeVisible();
  await openPlanner(page);
  await page.getByRole("textbox", { name: "origin location" }).fill("New Delhi");
  await closePlanner(page);
  await expect(page.getByText("Waiting for a journey")).toBeVisible();
  await compareRoutes(page, "walking");
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
  await openPlanner(page);
  await page.getByRole("button", { name: "Use current location for origin" }).click();
  await expect(page.locator('input[aria-label="origin location"]')).toHaveValue("Current location");
  await compareRoutes(page, "walking");
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
  await openPlanner(page);
  await page.getByRole("button", { name: "Use current location for origin" }).click();
  await expect(page.getByText("Location permission was denied. Search or choose on the map instead.")).toBeVisible();
  await expect(page.locator('input[aria-label="origin location"]')).toHaveValue("Recorded Delhi start");
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
  await openPlanner(page);
  await page.getByRole("textbox", { name: "origin location" }).fill("Fixture street");
  await openPlanner(page);
  await page.getByRole("textbox", { name: "origin location" }).press("Enter");
  await page.getByRole("button", { name: /Fixture street, Delhi/ }).click();
  await expect(page.locator('input[aria-label="origin location"]')).toHaveValue("Fixture street, Delhi");
  await compareRoutes(page, "walking");
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
  await compareRoutes(page, "walking");
  await expect(page.getByText("Estimated exposure: 1600.0 µg·min/m³")).toBeVisible();
  for (const [button, label] of [["Car", "car"], ["Motorcycle", "motorcycle"]]) {
    await openPlanner(page);
    await page.getByRole("button", { name: button, exact: true }).click();
    await closePlanner(page);
    await expect(page.getByText("Waiting for a journey")).toBeVisible();
    await compareRoutes(page, label);
    await expect(page.getByText("Estimated exposure: 1600.0 µg·min/m³")).toBeVisible();
  }
  expect(modes).toEqual(["walking", "driving", "motorcycle"]);
  await openPlanner(page);
  await expect(page.getByText(/Car routing estimate/)).toBeVisible();
  await openPlanner(page);
  await page.getByRole("button", { name: "Try recorded Delhi journey" }).click();
  await expect(page.getByRole("button", { name: "Walk", exact: true })).toHaveAttribute("aria-pressed", "true");
});


test("vehicle traffic indicators distinguish missing coverage from clear roads", async ({ page }) => {
  await page.route("**/api/routes/compare", route => route.fulfill({ json: trafficComparison() }));
  await journey(page);
  await openPlanner(page);
  await page.getByRole("button", { name: "Car", exact: true }).click();
  await compareRoutes(page, "car");
  await expect(page.getByText("Congestion data unavailable · traffic is unknown")).toHaveCount(3);
  await expect(page.getByText(/0% heavy\/severe/)).toHaveCount(0);
  await expect(page.getByText("5.0 min faster than typical")).toHaveCount(2);
  await expect(page.getByText(/Vehicle routes refresh about every two minutes/)).toBeVisible();
  await page.route("**/api/routes/compare", route => route.fulfill({ json: trafficComparison(90) }));
  await compareRoutes(page, "car");
  await expect(page.getByText("90% of route has reported congestion data · 40% heavy/severe")).toHaveCount(3);
});
