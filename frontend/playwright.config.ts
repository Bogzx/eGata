import { defineConfig, devices } from "@playwright/test";

// Both servers are expected to be running before invoking playwright:
//   backend:  uvicorn app.main:app --host 127.0.0.1 --port 8000
//   frontend: PORT=3030 npm run dev
//
// They are NOT auto-started by playwright because the autoresearch loop
// keeps the dev servers up across iterations — bouncing them per-run wastes
// 15-20 seconds of warm-up each time.
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  retries: 0,
  workers: 1,
  reporter: [["list"], ["json", { outputFile: "e2e-results.json" }]],
  use: {
    // E2E_BASE_URL points the suite at another frontend, e.g. the compose
    // stack on :3000 (CI). helpers.ts reads API_BASE for the backend.
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3030",
    headless: true,
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
    trace: "retain-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
