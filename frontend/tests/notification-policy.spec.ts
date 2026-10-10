import { expect, test } from "@playwright/test";
import { validDirectionAlert } from "../src/lib/notification-policy";

const now = 1800000000000;
const state = { journeyId: "active", routeVersion: "current", expiresAt: now + 30000, lastDisplayedSequence: 2 };
const alert = { journeyId: "active", routeVersion: "current", sequence: "3", instruction: "Turn left", issuedAt: String(now), expiresAt: String(now + 15000) };

test("only fresh alerts for the active journey and route pass", () => {
  expect(validDirectionAlert(alert, state, now)).toBe(true);
  for (const invalid of [
    { ...alert, journeyId: "stopped" }, { ...alert, routeVersion: "pre-reroute" },
    { ...alert, sequence: "2" }, { ...alert, sequence: "1" }, { ...alert, sequence: "NaN" },
    { ...alert, expiresAt: String(now - 1) }, { ...alert, issuedAt: String(now - 30000) },
    { ...alert, expiresAt: String(now + 60000) }, { ...alert, instruction: "" },
  ]) expect(validDirectionAlert(invalid, state, now)).toBe(false);
  expect(validDirectionAlert(alert, null, now)).toBe(false);
  expect(validDirectionAlert(alert, { ...state, expiresAt: now - 1 }, now)).toBe(false);
});
