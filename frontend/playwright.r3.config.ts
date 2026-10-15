import { defineConfig } from "@playwright/test";
import base from "./playwright.config";

export default defineConfig({
  ...base,
  testMatch: "page-review-flow.spec.ts",
  outputDir: "./output/playwright/r3-page-review",
  use: { ...base.use, channel: "chrome", baseURL: "http://127.0.0.1:18911" },
  webServer: {
    command: "npm run preview -- --host 127.0.0.1 --port 18911 --strictPort",
    url: "http://127.0.0.1:18911", reuseExistingServer: false,
  },
});
