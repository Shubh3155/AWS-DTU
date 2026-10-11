import { expect, test } from "@playwright/test";
import { closePlanner, compareRoutes, comparison, mockMap, openPlanner } from "./helpers/journey";

test.beforeEach(async ({ page }) => {
  await mockMap(page);
  await page.emulateMedia({ reducedMotion: "reduce" });
});

test("desktop and tablet map height follows half the expanded planner, including mode changes", async ({ page }) => {
  for (const viewport of [{ width: 1440, height: 1000 }, { width: 768, height: 1024 }, { width: 1024, height: 768 }]) {
    await page.setViewportSize(viewport);
    await page.goto("/journey");
    for (const mode of ["Walk", "Motorcycle"]) {
      await page.getByRole("button", { name: mode, exact: true }).click();
      await expect.poll(async () => {
        const planner = await page.locator(".journey-panel").boundingBox();
        const map = await page.locator(".map-panel").boundingBox();
        return Math.abs(map!.height - planner!.height / 2);
      }).toBeLessThan(1);
    }
  }
});

test("mobile planner opens from the menu, preserves choices and supports Escape and outside dismissal", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/journey");
  const toggle = page.locator(".planner-toggle");
  const drawer = page.getByRole("dialog", { name: "Plan a journey", exact: true });
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await expect(drawer).not.toBeVisible();
  await openPlanner(page);
  await expect(toggle).toHaveAttribute("aria-expanded", "true");
  await expect(page.getByRole("button", { name: "Close journey planner" })).toBeFocused();
  await page.getByRole("textbox", { name: "origin location" }).fill("My starting point");
  await page.getByRole("button", { name: "Car", exact: true }).click();
  await page.keyboard.press("Escape");
  await expect(drawer).not.toBeVisible();
  await expect(toggle).toBeFocused();
  await openPlanner(page);
  await expect(page.getByRole("textbox", { name: "origin location" })).toHaveValue("My starting point");
  await expect(page.getByRole("button", { name: "Car", exact: true })).toHaveAttribute("aria-pressed", "true");
  await page.mouse.click(386, 420);
  await expect(drawer).not.toBeVisible();
  await openPlanner(page);
  await page.setViewportSize({ width: 768, height: 1024 });
  await expect(page.locator(".planner-drawer")).toHaveCount(0);
  await expect(page.getByRole("textbox", { name: "origin location" })).toHaveValue("My starting point");
  expect(await page.evaluate(() => getComputedStyle(document.body).overflow)).not.toBe("hidden");
});

test("comparison reveals mobile routes and reopening the planner retains the selected journey", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route("**/api/routes/compare", route => route.fulfill({ json: comparison() }));
  await page.goto("/journey");
  await openPlanner(page);
  await page.getByRole("button", { name: "Try recorded Delhi journey" }).click();
  await compareRoutes(page);
  await expect(page.locator(".planner-drawer")).not.toBeVisible();
  await expect(page.getByRole("button", { name: /Start journey/ })).toBeVisible();
  await expect(page.getByRole("button", { name: "Show route 2 on map" })).toHaveAttribute("aria-pressed", "true");
  await openPlanner(page);
  await expect(page.getByRole("textbox", { name: "origin location" })).toHaveValue("Recorded Delhi start");
  await expect(page.getByRole("checkbox", { name: "Use recorded pollution observations" })).toBeChecked();
  await closePlanner(page);
  await page.screenshot({ path: test.info().outputPath("mobile-map-and-routes.png"), fullPage: true });
});
