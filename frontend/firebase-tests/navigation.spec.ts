import { expect, test, type Page } from "@playwright/test";
import { closePlanner, compareRoutes, comparison, journey, mockMap, openPlanner, trafficComparison } from "../tests/helpers/journey";
import { login } from "./helpers";

// GPS navigation now requires authentication; retain all navigation coverage with real emulator sessions.
test.beforeEach(async ({ page }, info) => {
  await mockMap(page);
  await page.goto("/journey");
  await login(page, "Navigator " + info.project.name, "navigator-" + info.project.name + "@example.test");
});

test("GPS journey follows updates, collapses planning until arrival or Stop and restores it", async ({ page, context }, info) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await context.grantPermissions(["geolocation"]);
  await context.setGeolocation({ latitude: 28.6, longitude: 77.2, accuracy: 5 });
  const data = comparison();
  data.candidates[1].maneuvers = [
    { instruction: "Turn left onto Example Street", type: "turn", modifier: "left", location: [77.21, 28.605] },
    { instruction: "You have arrived", type: "arrive", modifier: null, location: [77.22, 28.61] },
  ];
  await page.route("**/api/routes/compare", route => route.fulfill({ json: data }));
  await journey(page);
  await compareRoutes(page, "walking");
  await page.getByRole("button", { name: /Start journey/ }).click();
  await expect(page.getByRole("heading", { name: "Turn left onto Example Street" })).toBeVisible();
  await expect(page.locator(".app-shell")).toHaveClass(/is-navigating/);
  await expect(page.locator(".planner-body")).not.toBeVisible();
  await expect(page.locator(".primary-button")).toBeDisabled();
  await expect(page.locator(".show-route").first()).toBeDisabled();
  if (info.project.name === "mobile") {
    await expect(page.locator(".topbar")).not.toBeVisible();
    await expect(page.locator(".result-previews")).not.toBeVisible();
    const bounds = await page.locator(".map-panel").boundingBox();
    expect(bounds).toMatchObject({ x: 0, y: 0, width: 390, height: 844 });
    await expect(page.getByRole("button", { name: "Stop journey" })).toBeInViewport();
    await page.setViewportSize({ width: 844, height: 390 });
    expect(await page.locator(".map-panel").boundingBox()).toMatchObject({ x: 0, y: 0, width: 844, height: 390 });
    await expect(page.getByRole("button", { name: "Stop journey" })).toBeInViewport();
    await page.setViewportSize({ width: 390, height: 844 });
  }
  await page.screenshot({ path: test.info().outputPath("active-journey.png"), fullPage: true });
  await page.getByRole("button", { name: /Route overview/ }).click();
  await expect(page.getByText("Map paused · recenter to follow")).toBeVisible();
  await page.getByRole("button", { name: /Recenter/ }).click();
  await expect(page.getByText("Following your location")).toBeVisible();
  await context.setGeolocation({ latitude: 28.61, longitude: 77.22, accuracy: 5 });
  await expect(page.getByRole("heading", { name: "You have reached your destination" })).toBeVisible();
  await expect(page.locator(".app-shell")).not.toHaveClass(/is-navigating/);
  await openPlanner(page);
  await expect(page.getByRole("button", { name: "Compare walking routes" })).toBeEnabled();
  await closePlanner(page);
  await context.setGeolocation({ latitude: 28.6, longitude: 77.2, accuracy: 5 });
  await page.getByRole("button", { name: /Start journey/ }).click();
  await page.getByRole("button", { name: "Stop journey" }).click();
  await expect(page.getByRole("button", { name: "Stop journey" })).toHaveCount(0);
  await openPlanner(page);
  await expect(page.locator(".planner-body")).toBeVisible();
  await expect(page.locator('input[aria-label="origin location"]')).toHaveValue("Recorded Delhi start");
});

test("navigation requests GPS only after Start and clears the watcher on Stop", async ({ page }) => {
  await page.addInitScript(() => {
    const calls = { started: 0, stopped: 0 };
    Object.defineProperty(window, "gpsCalls", { value: calls });
    Object.defineProperty(navigator, "geolocation", { value: {
      watchPosition: () => { calls.started += 1; return 42; },
      clearWatch: (id: number) => { if (id === 42) calls.stopped += 1; },
    } });
  });
  await page.route("**/api/routes/compare", route => route.fulfill({ json: comparison() }));
  await journey(page);
  await compareRoutes(page, "walking");
  const calls = () => page.evaluate(() => (window as unknown as { gpsCalls: { started: number; stopped: number } }).gpsCalls);
  expect((await calls()).started).toBe(0);
  await page.getByRole("button", { name: /Start journey/ }).click();
  await expect.poll(async () => (await calls()).started).toBe(1);
  await page.getByRole("button", { name: "Stop journey" }).click();
  await expect.poll(async () => (await calls()).stopped).toBe(1);
});

test("navigation handles permission denial without locking the form", async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "geolocation", { value: {
      watchPosition: (_success: unknown, failure: (error: { code: number }) => void) => { failure({ code: 1 }); return 42; },
      clearWatch: () => {},
    } });
  });
  await page.route("**/api/routes/compare", route => route.fulfill({ json: comparison() }));
  await journey(page);
  await compareRoutes(page, "walking");
  await page.getByRole("button", { name: /Start journey/ }).click();
  await expect(page.getByText("Location permission denied. Allow location access to start following this route.")).toBeVisible();
  await expect(page.locator(".app-shell")).not.toHaveClass(/is-navigating/);
  await openPlanner(page);
  await expect(page.getByRole("button", { name: "Compare walking routes" })).toBeEnabled();
});

async function syntheticGPS(page: Page) {
  await page.clock.install();
  await page.addInitScript(() => {
    let listener: PositionCallback | null = null;
    Object.defineProperty(window, "emitGPS", { value: (lat: number, lng: number, accuracy: number) => listener?.({
      coords: { latitude: lat, longitude: lng, accuracy, heading: null }, timestamp: Date.now(),
    } as GeolocationPosition) });
    Object.defineProperty(navigator, "geolocation", { value: {
      watchPosition: (success: PositionCallback) => { listener = success; return 42; },
      clearWatch: () => { listener = null; },
    } });
  });
}
async function emitGPS(page: Page, lat = 28.62, lng = 77.2, accuracy = 5) {
  await page.evaluate(({ lat, lng, accuracy }) => {
    (window as unknown as { emitGPS: (lat: number, lng: number, accuracy: number) => void }).emitGPS(lat, lng, accuracy);
  }, { lat, lng, accuracy });
}
function replacement() {
  const data = comparison("limited_data");
  data.candidates.forEach(route => {
    route.id = `replacement-${route.id}`;
    route.geometry.coordinates = [[77.2, 28.62], [77.241, 28.628]];
    route.maneuvers = [{ instruction: "Turn right onto Replacement Road", type: "turn", modifier: "right", location: [77.22, 28.624] }];
  });
  data.fastest_id = "replacement-fast";
  return data;
}
async function startSyntheticJourney(page: Page) {
  await journey(page);
  await compareRoutes(page, "walking");
  await page.getByRole("button", { name: /Start journey/ }).click();
}

test("confirmed deviation reroutes from GPS, preserves preferences and continues navigation", async ({ page }) => {
  await syntheticGPS(page);
  const requests: Record<string, unknown>[] = [];
  await page.route("**/api/routes/compare", async route => {
    requests.push(route.request().postDataJSON());
    await route.fulfill({ json: requests.length === 1 ? comparison() : replacement() });
  });
  await journey(page);
  await openPlanner(page);
  await page.getByRole("button", { name: "Motorcycle", exact: true }).click();
  await openPlanner(page);
  await page.getByRole("checkbox", { name: "Use recorded pollution observations" }).check();
  await compareRoutes(page, "motorcycle");
  await page.getByRole("button", { name: /Start journey/ }).click();
  await emitGPS(page);
  expect(requests).toHaveLength(1);
  await page.clock.fastForward(9000);
  await emitGPS(page);
  await expect(page.locator('input[aria-label="origin location"]')).toHaveValue("Rerouted from GPS position");
  await emitGPS(page);
  await expect(page.getByRole("heading", { name: "Turn right onto Replacement Road" })).toBeVisible();
  expect(requests).toHaveLength(2);
  expect(requests[1]).toMatchObject({ origin: { lat: 28.62, lng: 77.2 }, destination: { lat: 28.628, lng: 77.241 },
    mode: "motorcycle", max_detour_minutes: 5, data_mode: "replay" });
  await expect(page.locator(".show-route").nth(0)).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("button", { name: "Stop journey" })).toBeVisible();
  await expect(page.locator(".primary-button")).toBeDisabled();
  await page.screenshot({ path: test.info().outputPath("rerouted.png"), fullPage: true });
});

test("weak GPS and returning to the route reset rerouting confirmation", async ({ page }) => {
  await syntheticGPS(page);
  let requests = 0;
  await page.route("**/api/routes/compare", route => { requests += 1; return route.fulfill({ json: comparison() }); });
  await startSyntheticJourney(page);
  await emitGPS(page);
  await page.clock.fastForward(9000);
  await emitGPS(page, 28.62, 77.2, 100);
  await expect(page.getByRole("heading", { name: /Weak GPS signal/ })).toBeVisible();
  await emitGPS(page);
  await page.clock.fastForward(9000);
  await emitGPS(page, 28.6, 77.2);
  await emitGPS(page);
  await expect(page.getByRole("heading", { name: /Off route/ })).toBeVisible();
  expect(requests).toBe(1);
});

test("rerouting failure keeps the route and throttles retries", async ({ page }) => {
  await syntheticGPS(page);
  let requests = 0;
  await page.route("**/api/routes/compare", route => {
    requests += 1;
    return route.fulfill({ status: requests <= 2 ? 200 : 503, json: requests === 1 ? comparison() : requests === 2 ? comparison("no_route") : {} });
  });
  await startSyntheticJourney(page);
  await emitGPS(page);
  await page.clock.fastForward(9000);
  await emitGPS(page);
  await expect(page.getByRole("heading", { name: /Could not reroute/ })).toBeVisible();
  await page.clock.fastForward(10000);
  await emitGPS(page);
  expect(requests).toBe(2);
  await expect(page.locator(".show-route").nth(1)).toHaveAttribute("aria-pressed", "true");
  await page.clock.fastForward(21000);
  await emitGPS(page);
  await expect.poll(() => requests).toBe(3);
  await expect(page.getByRole("button", { name: "Stop journey" })).toBeVisible();
});

test("Stop cancels pending rerouting and rejects a late replacement", async ({ page }) => {
  await syntheticGPS(page);
  let requests = 0;
  let release: (() => void) | undefined;
  const gate = new Promise<void>(resolve => { release = resolve; });
  await page.route("**/api/routes/compare", async route => {
    requests += 1;
    if (requests === 1) return route.fulfill({ json: comparison() });
    await gate;
    await route.fulfill({ json: replacement() }).catch(() => {});
  });
  await startSyntheticJourney(page);
  await emitGPS(page);
  await page.clock.fastForward(9000);
  await emitGPS(page);
  await expect(page.getByRole("heading", { name: "Rerouting from your current location…" })).toBeVisible();
  await page.getByRole("button", { name: "Stop journey" }).click();
  release?.();
  await page.clock.fastForward(30000);
  await expect(page.getByRole("button", { name: /Start journey/ })).toBeVisible();
  await expect(page.locator('input[aria-label="origin location"]')).toHaveValue("Recorded Delhi start");
  await expect(page.locator(".show-route").nth(1)).toHaveAttribute("aria-pressed", "true");
  await openPlanner(page);
  await expect(page.getByRole("button", { name: "Compare walking routes" })).toBeEnabled();
  await closePlanner(page);
  await emitGPS(page);
  expect(requests).toBe(2);
});

test("traffic navigation periodically refreshes using accurate GPS and keeps following", async ({ page }) => {
  await syntheticGPS(page);
  const requests: Record<string, unknown>[] = [];
  await page.route("**/api/routes/compare", async route => {
    requests.push(route.request().postDataJSON());
    const data = trafficComparison();
    if (requests.length > 1) data.candidates.forEach(candidate => {
      candidate.id = `refreshed-${candidate.id}`;
      candidate.geometry.coordinates = [[77.21, 28.605], [77.241, 28.628]];
      candidate.maneuvers = [{ instruction: "Continue onto Updated Road", type: "turn", modifier: "straight", location: [77.22, 28.612] }];
    });
    if (requests.length > 1) { data.fastest_id = "refreshed-fast"; data.lowest_exposure_eligible_id = "refreshed-slow"; }
    await route.fulfill({ json: data });
  });
  await journey(page);
  await openPlanner(page);
  await page.getByRole("button", { name: "Car", exact: true }).click();
  await compareRoutes(page, "car");
  await page.getByRole("button", { name: /Start journey/ }).click();
  await emitGPS(page, 28.605, 77.21);
  await page.clock.fastForward(121000);
  await emitGPS(page, 28.605, 77.21, 100);
  expect(requests).toHaveLength(1);
  await emitGPS(page, 28.605, 77.21);
  await expect(page.locator('input[aria-label="origin location"]')).toHaveValue("Rerouted from GPS position");
  expect(requests).toHaveLength(2);
  expect(requests[1]).toMatchObject({ mode: "driving", origin: { lat: 28.605, lng: 77.21 }, destination: { lat: 28.628, lng: 77.241 } });
  await emitGPS(page, 28.605, 77.21);
  await expect(page.getByRole("heading", { name: "Continue onto Updated Road" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Stop journey" })).toBeVisible();
  await page.getByRole("button", { name: "Stop journey" }).click();
  await page.clock.fastForward(121000);
  await emitGPS(page, 28.605, 77.21);
  expect(requests).toHaveLength(2);
});
