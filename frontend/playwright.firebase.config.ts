import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./firebase-tests", testMatch: "**/*.spec.ts", fullyParallel: false, workers: 1,
  timeout: 60000, reporter: "list",
  use: { baseURL: "http://127.0.0.1:3101", trace: "retain-on-failure" },
  projects: [
    { name: "desktop", use: { browserName: "chromium", viewport: { width: 1440, height: 1000 } } },
    { name: "mobile", use: { browserName: "chromium", viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
  webServer: {
    command: "npm run dev -- --hostname 127.0.0.1 --port 3101", url: "http://127.0.0.1:3101",
    reuseExistingServer: false, timeout: 120000,
    env: {
      AEROROUTE_FIREBASE_TESTS: "true", NEXT_PUBLIC_FIREBASE_EMULATORS: "true",
      NEXT_PUBLIC_FIREBASE_API_KEY: "demo-key", NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN: "demo-aeroroute.firebaseapp.com",
      NEXT_PUBLIC_FIREBASE_PROJECT_ID: "demo-aeroroute", NEXT_PUBLIC_FIREBASE_APP_ID: "demo-app",
      NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID: "123456789",
      // Synthetic P-256 public key for the mocked Push API; never registers a real device.
      NEXT_PUBLIC_FIREBASE_VAPID_KEY: "BGsX0fLhLEJH-Lzm5WOkQPJ3A32BLeszoPShOUXYmMKWT-NC4v4af5uO5-tKfA-eFivOM1drMV7Oy7ZAaDe_UfU",
      NEXT_PUBLIC_MAPBOX_TOKEN: "", NEXT_PUBLIC_API_URL: "", NEXT_TELEMETRY_DISABLED: "1",
    },
    gracefulShutdown: { signal: "SIGTERM", timeout: 1000 },
  },
});
