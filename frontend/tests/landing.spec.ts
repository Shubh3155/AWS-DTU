import { expect, test } from "@playwright/test";
import { closePlanner, openPlanner } from "./helpers/journey";

test.beforeEach(async ({ page }) => {
  await page.route("https://d8j0ntlcm91z4.cloudfront.net/**", route => route.abort());
});

test("landing uses the required video, omits the demo and opens guest planning", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveTitle("Know Your Route. Before You Head Out. — AeroRoute");
  await expect(page.getByRole("heading", { name: "Know Your Route. Before You Head Out." })).toBeVisible();
  await expect(page.locator("video source")).toHaveAttribute("src", "https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260808_064556_051587f1-74a1-4336-8c05-4dde3594ed05.mp4");
  await expect(page.getByText("Watch Demo")).toHaveCount(0);
  await expect(page.locator(".demo-card")).toHaveCount(0);
  const sizes = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth, width: innerWidth,
    scrollHeight: document.documentElement.scrollHeight, height: innerHeight,
    overflow: getComputedStyle(document.body).overflow,
    titleWeight: getComputedStyle(document.querySelector("h1")!).fontWeight,
  }));
  expect(sizes.scrollWidth).toBe(sizes.width);
  expect(sizes.scrollHeight).toBe(sizes.height);
  expect(sizes.overflow).toBe("hidden");
  expect(sizes.titleWeight).toBe("500");
  const popups: string[] = [];
  page.on("popup", popup => popups.push(popup.url()));
  await page.getByRole("link", { name: "Get Started" }).click();
  await expect(page).toHaveURL(/\/journey$/);
  await openPlanner(page);
  await page.getByRole("button", { name: "Car", exact: true }).click();
  await page.getByRole("textbox", { name: "origin location" }).fill("Delhi");
  await expect(page.getByRole("button", { name: "Car", exact: true })).toHaveAttribute("aria-pressed", "true");
  expect(popups).toEqual([]);
  await closePlanner(page);
  expect(await page.evaluate(() => getComputedStyle(document.body).overflow)).not.toBe("hidden");
});

test("compact menu manages focus, Escape, outside clicks and resizing", async ({ page }) => {
  await page.setViewportSize({ width: 768, height: 1024 });
  await page.goto("/");
  const toggle = page.getByRole("button", { name: "Open menu" });
  const panel = page.locator("#tablet-navigation");
  await expect(panel).toHaveAttribute("inert", "");
  await toggle.click();
  await expect(page.getByRole("link", { name: "Home", exact: true })).toBeFocused();
  await expect(page.getByRole("button", { name: "Close menu" })).toHaveAttribute("aria-expanded", "true");
  await page.keyboard.press("Escape");
  await expect(toggle).toBeFocused();
  await expect(panel).toHaveAttribute("inert", "");
  await toggle.click();
  await page.locator(".hero-title").click();
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await page.setViewportSize({ width: 1440, height: 900 });
  await expect(panel).not.toHaveAttribute("inert", "");
  await expect(page.getByRole("link", { name: "Plan", exact: true })).toBeVisible();
});

test("mobile and short landscape keep the hero and CTA inside the viewport", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  for (const size of [{ width: 320, height: 568 }, { width: 390, height: 844 }, { width: 844, height: 390 }, { width: 568, height: 320 }]) {
    await page.setViewportSize(size);
    await page.goto("/");
    for (const selector of [".hero-title .line-one", ".hero-title .line-two", ".hero-copy", ".primary-cta"]) {
      const bounds = await page.locator(selector).boundingBox();
      expect(bounds).not.toBeNull();
      expect(bounds!.x).toBeGreaterThanOrEqual(0);
      expect(bounds!.y).toBeGreaterThan(65);
      expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(size.width);
      expect(bounds!.y + bounds!.height).toBeLessThanOrEqual(size.height);
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(size.width);
  }
});

test("entrance runs once with the requested delays and clears its pending state", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.addInitScript(() => {
    const entrances: { name: string; duration: string; delay: string }[] = [];
    Object.defineProperty(window, "entrances", { value: entrances });
    document.addEventListener("animationstart", event => {
      if (!(event.target instanceof HTMLElement)) return;
      const style = getComputedStyle(event.target);
      entrances.push({ name: event.animationName, duration: style.animationDuration, delay: style.animationDelay });
    });
  });
  await page.goto("/");
  await expect(page.locator("html")).not.toHaveClass(/motion-pending/);
  const entrances = await page.evaluate(() => (window as unknown as { entrances: unknown[] }).entrances);
  expect(entrances).toEqual(expect.arrayContaining([
    { name: "entrance-brand", duration: "0.58s", delay: "0.06s" },
    { name: "entrance-line", duration: "0.8s", delay: "0.3s" },
    { name: "entrance-line", duration: "0.85s", delay: "0.44s" },
    { name: "entrance-copy", duration: "0.62s", delay: "0.74s" },
    { name: "entrance-action", duration: "0.56s", delay: "0.96s" },
  ]));
  await page.getByRole("link", { name: "Get Started" }).click();
  await page.getByRole("link", { name: "AeroRoute", exact: true }).click();
  await expect(page.locator(".primary-cta")).toBeVisible();
  await expect(page.locator("html")).not.toHaveClass(/motion-pending/);
});

test("reduced motion shows content immediately and pauses the background", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await expect(page.locator("html")).not.toHaveClass(/motion-pending/);
  await expect(page.getByRole("link", { name: "Get Started" })).toBeVisible();
  expect(await page.locator("video").evaluate(video => (video as HTMLVideoElement).paused)).toBe(true);
});

test("landing About opens the project explanation and its CTA preserves guest planning", async ({ page }) => {
  await page.goto("/");
  const toggle = page.getByRole("button", { name: "Open menu" });
  if (await toggle.isVisible()) await toggle.click();
  await page.getByRole("link", { name: "About", exact: true }).click();
  await expect(page).toHaveURL(/\/about$/);
  await expect(page).toHaveTitle("About AeroRoute — a more informed journey");
  await expect(page.getByRole("heading", { name: "How AeroRoute works" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Set your journey" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Start when you’re ready" })).toBeVisible();
  await expect(page.locator(".nav a[href='/about']")).toHaveAttribute("aria-current", "page");
  await expect(page.locator(".nav a[href='/']")).not.toHaveAttribute("aria-current", "page");
  await expect(page.locator("html")).not.toHaveClass(/motion-pending/);
  let popups = 0;
  page.on("popup", () => popups++);
  await page.getByRole("link", { name: "Get Started" }).click();
  await expect(page).toHaveURL(/\/journey$/);
  await openPlanner(page);
  await expect(page.getByRole("heading", { name: "Plan a journey", exact: true })).toBeVisible();
  expect(popups).toBe(0);
});

test("About content remains readable and reachable on small and landscape screens", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  for (const size of [{ width: 320, height: 568 }, { width: 390, height: 844 }, { width: 768, height: 1024 }, { width: 844, height: 390 }]) {
    await page.setViewportSize(size);
    await page.goto("/about");
    const content = page.getByRole("region", { name: "About AeroRoute", exact: true });
    const dimensions = await content.evaluate(element => ({ width: element.clientWidth, content: element.scrollWidth }));
    expect(dimensions.content).toBeLessThanOrEqual(dimensions.width);
    const intro = await page.locator(".about-intro").boundingBox();
    expect(intro!.y).toBeGreaterThan(65);
    await page.locator(".about-estimates").scrollIntoViewIfNeeded();
    await expect(page.getByRole("heading", { name: "Estimates, with their limits." })).toBeInViewport();
    await expect(page.getByText(/Motorcycle times currently use car-routing estimates/)).toBeInViewport();
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(size.width);
  }
});
