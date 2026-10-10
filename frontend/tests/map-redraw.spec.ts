import { expect, test } from "@playwright/test";
import { scheduleRouteDraw } from "../src/lib/map-redraw";

test("selected route redraws while an existing GeoJSON source is loading", () => {
  let drawn = 0;
  const map = { isStyleLoaded: () => false, getSource: () => ({}),
    once: () => { throw new Error("Should not wait on existing source"); }, off: () => {} };
  scheduleRouteDraw(map, () => { drawn += 1; });
  expect(drawn).toBe(1);
});

test("initial draw waits for readiness and can be cancelled on a new selection", () => {
  let listener: (() => void) | null = null;
  let drawn = 0;
  const map = { isStyleLoaded: () => false, getSource: () => undefined,
    once: (_event: "idle", callback: () => void) => { listener = callback; },
    off: (_event: "idle", callback: () => void) => { if (listener === callback) listener = null; } };
  const cancel = scheduleRouteDraw(map, () => { drawn += 1; });
  expect(drawn).toBe(0);
  cancel();
  expect(listener).toBeNull();
  scheduleRouteDraw(map, () => { drawn += 1; });
  (listener as unknown as () => void)();
  expect(drawn).toBe(1);
});
