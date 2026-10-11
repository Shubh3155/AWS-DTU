import { expect, test } from "@playwright/test";
import { closePlanner, compareRoutes, comparison, mockMap, openPlanner } from "../tests/helpers/journey";
import { completeGooglePopup } from "./helpers";

test.beforeEach(async ({ page }) => {
  await mockMap(page);
  await page.route("https://d8j0ntlcm91z4.cloudfront.net/**", route => route.abort());
  await page.route("**/api/routes/compare", route => route.fulfill({ json: comparison() }));
  await page.addInitScript(() => {
    const calls = { started: 0, stopped: 0 };
    Object.defineProperty(window, "gpsCalls", { value: calls });
    Object.defineProperty(navigator, "geolocation", { value: {
      watchPosition: () => { calls.started++; return 42; },
      clearWatch: () => { calls.stopped++; },
    } });
  });
});

test("landing Sign Up opens Google directly and carries the session into the product", async ({ page }, info) => {
  await page.goto("/");
  const toggle = page.getByRole("button", { name: "Open menu" });
  if (await toggle.isVisible()) await toggle.click();
  const popupPromise = page.waitForEvent("popup");
  await page.getByRole("button", { name: "Sign Up", exact: true }).click();
  await completeGooglePopup(await popupPromise, "Landing " + info.project.name, "landing-" + info.project.name + "@example.test");
  await expect(page).toHaveURL(/\/journey$/);
  await expect(page.getByRole("button", { name: "Log out", exact: true })).toBeVisible();
  await page.getByRole("link", { name: "AeroRoute", exact: true }).click();
  await page.getByRole("link", { name: "Get Started" }).click();
  await expect(page.getByRole("button", { name: "Log out", exact: true })).toBeVisible();
});

test("guest plans freely; cancelling Start login preserves the plan; retry resumes GPS", async ({ page }, info) => {
  const popups: string[] = [];
  page.on("popup", popup => popups.push(popup.url()));
  await page.goto("/");
  await page.getByRole("link", { name: "Get Started" }).click();
  await openPlanner(page);
  await page.getByRole("button", { name: "Try recorded Delhi journey" }).click();
  await openPlanner(page);
  await page.getByRole("button", { name: "Car", exact: true }).click();
  await compareRoutes(page, "car");
  await expect(page.getByRole("button", { name: /Start journey/ })).toBeEnabled();
  expect(popups).toHaveLength(0);
  const started = () => page.evaluate(() => (window as unknown as { gpsCalls: { started: number } }).gpsCalls.started);
  expect(await started()).toBe(0);
  let popupPromise = page.waitForEvent("popup");
  await page.getByRole("button", { name: /Start journey/ }).click();
  const cancelled = await popupPromise;
  await cancelled.waitForLoadState();
  await cancelled.close();
  await expect(page.getByRole("button", { name: /Start journey/ })).toBeEnabled({ timeout: 15000 });
  expect(await started()).toBe(0);
  await expect(page.locator('input[aria-label="origin location"]')).toHaveValue("Recorded Delhi start");
  await openPlanner(page);
  await expect(page.getByRole("button", { name: "Car", exact: true })).toHaveAttribute("aria-pressed", "true");
  await closePlanner(page);
  popupPromise = page.waitForEvent("popup");
  await page.getByRole("button", { name: /Start journey/ }).click();
  await completeGooglePopup(await popupPromise, "Journey " + info.project.name, "journey-" + info.project.name + "@example.test");
  await expect(page.getByRole("button", { name: "Stop journey", exact: true })).toBeVisible();
  await expect.poll(started).toBe(1);
  await page.getByRole("button", { name: "Stop journey", exact: true }).click();
  await page.getByRole("button", { name: /Start journey/ }).click();
  await expect.poll(started).toBe(2);
  expect(popups).toHaveLength(2);
});

test("a route edited during Google login cannot start stale GPS guidance", async ({ page }, info) => {
  await page.goto("/journey");
  await openPlanner(page);
  await page.getByRole("button", { name: "Try recorded Delhi journey" }).click();
  await compareRoutes(page, "walking");
  const popupPromise = page.waitForEvent("popup");
  await page.getByRole("button", { name: /Start journey/ }).click();
  const popup = await popupPromise;
  await openPlanner(page);
  await page.getByRole("button", { name: "Motorcycle", exact: true }).click();
  await closePlanner(page);
  await completeGooglePopup(popup, "Changed " + info.project.name, "changed-" + info.project.name + "@example.test");
  await expect(page.getByRole("button", { name: "Log out", exact: true })).toBeVisible();
  expect(await page.evaluate(() => (window as unknown as { gpsCalls: { started: number } }).gpsCalls.started)).toBe(0);
  await expect(page.getByRole("button", { name: "Stop journey", exact: true })).toHaveCount(0);
});
