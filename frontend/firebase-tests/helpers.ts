import { expect, type Page } from "@playwright/test";
import { closePlanner } from "../tests/helpers/journey";

export async function login(page: Page, name: string, email: string) {
  await closePlanner(page);
  const popupPromise = page.waitForEvent("popup");
  await page.getByRole("button", { name: "Sign in with Google", exact: true }).click();
  const popup = await popupPromise;
  await completeGooglePopup(popup, name, email);
  await expect(page.getByRole("button", { name: "Log out", exact: true })).toBeVisible();
}

export async function completeGooglePopup(popup: Page, name: string, email: string) {
  await popup.waitForLoadState();
  const existing = popup.getByText(name, { exact: true });
  if (await existing.count()) await existing.click();
  else {
    await popup.getByRole("button", { name: "Add new account" }).click();
    await popup.locator("#email-input").fill(email);
    await popup.locator("#display-name-input").fill(name);
    await popup.locator("#sign-in").click();
  }
}
