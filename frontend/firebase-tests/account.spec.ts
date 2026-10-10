import { expect, test, type Page } from "@playwright/test";

async function login(page: Page, name: string, email: string) {
  const popupPromise = page.waitForEvent("popup");
  await page.getByRole("button", { name: "Sign in with Google", exact: true }).click();
  const popup = await popupPromise;
  await popup.waitForLoadState();
  const existing = popup.getByText(name, { exact: true });
  if (await existing.count()) await existing.click();
  else {
    await popup.getByRole("button", { name: "Add new account" }).click();
    await popup.locator("#email-input").fill(email);
    await popup.locator("#display-name-input").fill(name);
    await popup.locator("#sign-in").click();
  }
  await expect(page.getByRole("button", { name: "Log out", exact: true })).toBeVisible();
}

const response = {
  mode: "walking", routing_profile: "walking", status: "no_route", candidates: [], fastest_id: null,
  lowest_exposure_eligible_id: null, estimated_reduction_percent: null, warnings: ["Synthetic emulator route test"],
  data_quality: { data_mode: "replay", observed_from: null, observed_to: null, fetched_at: null,
    source_ids: [], provider_ids: [], data_version: null, model_version: null, snapshot_id: null,
    reference_time: null, station_count: 0, model_parameters: {} },
};

test("Google login, saved searches, refresh, reopening, deletion and account isolation", async ({ page }, info) => {
  const suffix = info.project.name;
  let requests = 0;
  await page.route("**/api/routes/compare", route => { requests += 1; return route.fulfill({ json: response }); });
  await page.goto("/");
  await login(page, "Alice " + suffix, "alice-" + suffix + "@example.test");
  await page.getByRole("button", { name: "Try recorded Delhi journey" }).click();
  await page.getByRole("button", { name: "Compare walking routes" }).click();
  const history = page.getByRole("region", { name: "Recent routes" });
  await expect(history.getByRole("button", { name: /Reopen Recorded Delhi start/ })).toHaveCount(1);
  await page.reload();
  await expect(page.getByRole("button", { name: "Log out", exact: true })).toBeVisible();
  await expect(history.getByRole("button", { name: /Reopen Recorded Delhi start/ })).toHaveCount(1);
  await history.getByRole("button", { name: /Reopen Recorded Delhi start/ }).click();
  await expect.poll(() => requests).toBe(2);
  await expect(history.getByRole("button", { name: /Reopen Recorded Delhi start/ })).toHaveCount(2);
  await history.getByRole("button", { name: "Delete route to Recorded Delhi destination", exact: true }).first().click();
  await expect(history.getByRole("button", { name: /Reopen Recorded Delhi start/ })).toHaveCount(1);
  await page.getByRole("button", { name: "Log out", exact: true }).click();
  await expect(page.getByRole("button", { name: "Sign in with Google", exact: true })).toBeVisible();
  await expect(history.getByRole("button", { name: /Reopen/ })).toHaveCount(0);
  await login(page, "Bob " + suffix, "bob-" + suffix + "@example.test");
  await expect(history.getByText("Your next route search will be saved here.")).toBeVisible();
  await expect(history.getByRole("button", { name: /Reopen/ })).toHaveCount(0);
  await page.getByRole("button", { name: "Log out", exact: true }).click();
  await login(page, "Alice " + suffix, "alice-" + suffix + "@example.test");
  await expect(history.getByRole("button", { name: /Reopen Recorded Delhi start/ })).toHaveCount(1);
  await history.getByRole("button", { name: "Clear all", exact: true }).click();
  await expect(history.getByRole("button", { name: /Reopen/ })).toHaveCount(0);
  const size = await page.evaluate(() => ({ width: document.documentElement.clientWidth, content: document.documentElement.scrollWidth }));
  expect(size.content).toBeLessThanOrEqual(size.width);
});

test("Remember me restores login across browser contexts; session login does not", async ({ page, browser }, info) => {
  await page.goto("/");
  await page.getByLabel("Remember me").check();
  await login(page, "Remember " + info.project.name, "remember-" + info.project.name + "@example.test");
  const storage = await page.context().storageState({ indexedDB: true });
  const restored = await browser.newContext({ storageState: storage });
  const next = await restored.newPage();
  await next.goto("http://127.0.0.1:3101");
  await expect(next.getByRole("button", { name: "Log out", exact: true })).toBeVisible();
  await restored.close();
  await page.getByRole("button", { name: "Log out", exact: true }).click();
  await page.getByLabel("Remember me").uncheck();
  await login(page, "Session " + info.project.name, "session-" + info.project.name + "@example.test");
  const sessionStorage = await page.context().storageState({ indexedDB: true });
  const guest = await browser.newContext({ storageState: sessionStorage });
  const guestPage = await guest.newPage();
  await guestPage.goto("http://127.0.0.1:3101");
  await expect(guestPage.getByRole("button", { name: "Sign in with Google", exact: true })).toBeVisible();
  await guest.close();
});

test("Denied notifications preserve GPS guidance and logout stops tracking", async ({ page }, info) => {
  await page.addInitScript(() => {
    const calls = { stopped: 0 };
    Object.defineProperty(window, "gpsCalls", { value: calls });
    Object.defineProperty(navigator, "geolocation", { value: {
      watchPosition: () => 42,
      clearWatch: (id: number) => { if (id === 42) calls.stopped += 1; },
    } });
    Object.defineProperty(Notification, "requestPermission", { value: async () => "denied" });
  });
  const candidate = {
    id: "synthetic-route", navigation_token: "a".repeat(32),
    geometry: { type: "LineString", coordinates: [[77.2167, 28.6315], [77.241, 28.628]] },
    distance_metres: 2400, duration_seconds: 1800, within_budget: true,
    estimated_exposure: null, exposure_unit: "µg·min/m³", coverage_percent: 0,
  };
  await page.route("**/api/routes/compare", route => route.fulfill({ json: {
    ...response, status: "limited_data", candidates: [candidate], fastest_id: candidate.id,
  } }));
  await page.goto("/");
  await login(page, "GPS " + info.project.name, "gps-" + info.project.name + "@example.test");
  await page.getByRole("button", { name: "Try recorded Delhi journey" }).click();
  await page.getByRole("button", { name: "Compare walking routes" }).click();
  await page.getByRole("button", { name: /Start journey/ }).click();
  await page.getByRole("button", { name: "Enable direction alerts", exact: true }).click();
  await expect(page.getByText("Notifications are off. You can follow the on-screen directions.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Stop journey", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Log out", exact: true }).click();
  await expect.poll(() => page.evaluate(() => (window as unknown as { gpsCalls: { stopped: number } }).gpsCalls.stopped)).toBe(1);
  await expect(page.getByRole("button", { name: "Stop journey", exact: true })).toHaveCount(0);
});

test("Loaded history stays complete when a new search arrives and Clear all removes every page", async ({ page }, info) => {
  let requests = 0;
  await page.route("**/api/routes/compare", route => { requests += 1; return route.fulfill({ json: response }); });
  await page.goto("/");
  await login(page, "Pages " + info.project.name, "pages-" + info.project.name + "@example.test");
  await page.getByRole("button", { name: "Try recorded Delhi journey" }).click();
  const history = page.getByRole("region", { name: "Recent routes" });
  const rows = history.getByRole("button", { name: /Reopen Recorded Delhi start/ });
  for (let index = 1; index <= 21; index++) {
    await page.getByRole("button", { name: "Compare walking routes" }).click();
    await expect.poll(() => requests).toBe(index);
    await expect(page.getByRole("button", { name: "Compare walking routes" })).toBeEnabled();
    await expect(rows).toHaveCount(Math.min(index, 20));
  }
  await history.getByRole("button", { name: "Load older searches" }).click();
  await expect(rows).toHaveCount(21);
  await page.getByRole("button", { name: "Compare walking routes" }).click();
  await expect(rows).toHaveCount(22);
  await history.getByRole("button", { name: "Delete route to Recorded Delhi destination", exact: true }).last().click();
  await expect(rows).toHaveCount(21);
  await history.getByRole("button", { name: "Clear all", exact: true }).click();
  await expect(rows).toHaveCount(0);
  await page.reload();
  await expect(history.getByText("Your next route search will be saved here.")).toBeVisible();
});

test("FCM confirms the installation before backend registration and logout unregisters it", async ({ page }, info) => {
  let fid = "", registered = false, removed = false, deviceRemoved = false;
  let device: { recipient?: string; recipient_kind?: string } = {};
  await page.addInitScript(() => {
    Object.defineProperty(Notification, "permission", { get: () => "granted" });
    Object.defineProperty(Notification, "requestPermission", { value: async () => "granted" });
    const subscription = {
      endpoint: "https://push.example.test/synthetic-subscription",
      getKey: (name: string) => new Uint8Array(name === "auth" ? 16 : 65).buffer,
      unsubscribe: async () => true,
    };
    Object.defineProperty(PushManager.prototype, "getSubscription", { value: async () => subscription });
    Object.defineProperty(PushManager.prototype, "subscribe", { value: async () => subscription });
  });
  await page.route("https://firebaseinstallations.googleapis.com/**", route => {
    if (route.request().url().endsWith("/authTokens:generate")) {
      return route.fulfill({ json: { token: "synthetic-installation-token", expiresIn: "604800s" } });
    }
    const body = route.request().postDataJSON();
    fid = body.fid || fid;
    return route.fulfill({ json: {
      fid, refreshToken: "synthetic-installation-refresh",
      authToken: { token: "synthetic-installation-token", expiresIn: "604800s" },
    } });
  });
  await page.route("https://fcmregistrations.googleapis.com/**", route => {
    if (route.request().method() === "DELETE") {
      removed = true;
      return route.fulfill({ json: {} });
    }
    registered = true;
    return route.fulfill({ json: { name: "projects/demo-aeroroute/registrations/" + fid } });
  });
  await page.route("**/api/me/devices/*", route => {
    if (route.request().method() === "DELETE") deviceRemoved = true;
    else {
      expect(registered).toBe(true);
      expect(route.request().headers().authorization).toMatch(/^Bearer /);
      device = route.request().postDataJSON();
    }
    return route.fulfill({ status: 204 });
  });
  const candidate = {
    id: "synthetic-push-route", navigation_token: "a".repeat(32),
    geometry: { type: "LineString", coordinates: [[77.2167, 28.6315], [77.241, 28.628]] },
    distance_metres: 2400, duration_seconds: 1800, within_budget: true,
    estimated_exposure: null, exposure_unit: "µg·min/m³", coverage_percent: 0,
  };
  await page.route("**/api/routes/compare", route => route.fulfill({ json: {
    ...response, status: "limited_data", candidates: [candidate], fastest_id: candidate.id,
  } }));
  await page.goto("/");
  await login(page, "Push " + info.project.name, "push-" + info.project.name + "@example.test");
  await page.getByRole("button", { name: "Try recorded Delhi journey" }).click();
  await page.getByRole("button", { name: "Compare walking routes" }).click();
  await page.getByRole("button", { name: "Enable direction alerts", exact: true }).click();
  await expect(page.getByRole("button", { name: "Disable direction alerts", exact: true })).toBeVisible();
  expect(fid).toMatch(/^[cdef][\w-]{21}$/);
  expect(device).toEqual({ recipient: fid, recipient_kind: "fid" });
  await page.getByRole("button", { name: "Log out", exact: true }).click();
  await expect.poll(() => removed && deviceRemoved).toBe(true);
});
