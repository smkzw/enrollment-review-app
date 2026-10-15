/**
 * 真实后端验收专用配置。
 *
 * 该配置不启动、不重新构建前端，避免试用版构建覆盖正在验收的
 * 正式产物。运行者必须先启动独立清洁数据库、真实 API 和正式前端，
 * 再显式提供 EVIDENCE_LIVE_* 环境变量。
 */

import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  outputDir: "./e2e/test-results-live",
  timeout: 45_000,
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  workers: 1,
  reporter: [["list"]],
  use: {
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "desktop-1080p",
      use: { viewport: { width: 1920, height: 1080 } },
    },
    {
      name: "desktop-2k",
      use: { viewport: { width: 2560, height: 1440 } },
    },
    {
      name: "desktop-4k",
      use: { viewport: { width: 3840, height: 2160 } },
    },
  ],
});
