/** Real HTTP acceptance: production frontend repository + isolated V2 API. */
import { defineConfig } from "@playwright/test";

const dataRoot = "/tmp/enrollment-review-protocol-real-e2e";
process.env.PROTOCOL_REAL_E2E = "1";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "protocol-workbench-real.spec.ts",
  globalTeardown: "./e2e/protocol-real-teardown.ts",
  outputDir: "/tmp/enrollment-review-protocol-real-e2e-results",
  timeout: 120_000,
  fullyParallel: false,
  retries: 0,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:4191",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "real-1080p", use: { viewport: { width: 1920, height: 1080 } } },
    { name: "real-2k", use: { viewport: { width: 2560, height: 1440 } } },
    { name: "real-4k", use: { viewport: { width: 3840, height: 2160 } } },
  ],
  webServer: [
    {
      command: `rm -rf ${dataRoot} && ENROLLMENT_V2_DATA_DIR=${dataRoot} uv run uvicorn tests.v2.api.protocol_playwright_app:create_playwright_app --factory --host 127.0.0.1 --port 8903`,
      cwd: "..",
      url: "http://127.0.0.1:8903/docs",
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: "VITE_V2_API_PROXY_TARGET=http://127.0.0.1:8903 npm run build && VITE_V2_API_PROXY_TARGET=http://127.0.0.1:8903 npm run preview -- --host 127.0.0.1 --port 4191 --strictPort",
      url: "http://127.0.0.1:4191",
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
