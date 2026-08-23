import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e/visual",
  outputDir: "./test-results/visual",
  fullyParallel: false,
  retries: 0,
  workers: 1,
  reporter: [["list"]],
  snapshotPathTemplate: "{testDir}/__screenshots__/{projectName}/{arg}{ext}",
  expect: {
    timeout: 15_000,
    toHaveScreenshot: {
      animations: "disabled",
      caret: "hide",
      maxDiffPixelRatio: 0.001,
    },
  },
  use: {
    baseURL: "http://127.0.0.1:5173",
    colorScheme: "light",
    locale: "en-US",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium-win32",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 1000 },
      },
    },
  ],
  webServer: {
    command: "npm run dev -- --host 127.0.0.1",
    url: "http://127.0.0.1:5173",
    reuseExistingServer: true,
    timeout: 120_000,
  },
});
