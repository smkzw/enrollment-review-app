/**
 * Playwright 配置：真实浏览器验收（合同 §3.3 视口矩阵 + §8 状态验收）。
 * - webServer 启动 vite preview（构建产物），避免 dev server 与测试竞争。
 * - 1080P、2K、4K 三个最大化桌面项目；axe 检查与溢出检查在 spec 中执行。
 * - 截图输出到 e2e/screenshots/（供 Codex 视觉复核，本角色不做最终视觉验收）。
 * - Phase 5.8 真实隔离验收（phase5-real-acceptance.spec.ts）默认 skip；
 *   仅当显式设置 PHASE5_ISOLATED_DATASET_ROOT（及配套 BASE_URL/DATA_DIR/
 *   ROLE=independent_tester）时由独立测试者启用，禁止 fixture 路由冒充。
 */

import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  outputDir: "./e2e/test-results",
  timeout: 45_000,
  fullyParallel: true,
  forbidOnly: true,
  retries: 1,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:4173",
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
  webServer: {
    command: "npm run build:e2e && npm run preview -- --host 127.0.0.1 --port 4173 --strictPort",
    url: "http://127.0.0.1:4173",
    reuseExistingServer: true,
    timeout: 120_000,
  },
});
