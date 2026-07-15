import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  retries: 0,
  reporter: "line",
  use: {
    baseURL: process.env.DEPLOYMENT_URL ?? "http://127.0.0.1:4173",
    trace: "retain-on-failure",
  },
  webServer: process.env.DEPLOYMENT_URL
    ? undefined
    : {
        command: "pnpm start",
        url: "http://127.0.0.1:4173",
        reuseExistingServer: false,
      },
  projects: [
    { name: "chromium-desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "chromium-mobile", use: { ...devices["Pixel 7"] } },
  ],
});
