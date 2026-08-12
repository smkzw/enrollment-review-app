/**
 * 截图收集（供 Codex 视觉复核；本角色不做最终视觉验收）。
 * 每个视口项目输出关键页面截图；1440 项目额外输出 150%/200% 缩放截图。
 */

import { test } from "@playwright/test";
import { openRoute, setZoom } from "./helpers";

const SHOT_PAGES = [
  { hash: "/today", name: "today" },
  { hash: "/board", name: "board" },
  { hash: "/subjects?subject=subject-uat-03-gap_conflict&stage=screening", name: "subjects-profile" },
  { hash: "/workbench?episode=episode-uat-03-screening-gap_conflict", name: "workbench" },
  { hash: "/actions", name: "actions" },
  { hash: "/tasks", name: "tasks" },
  { hash: "/protocols", name: "protocols" },
  { hash: "/reports", name: "reports" },
  { hash: "/help", name: "help" },
];

test.describe("截图收集", () => {
  for (const pageInfo of SHOT_PAGES) {
    test(`截图 ${pageInfo.name}`, async ({ page }) => {
      const project = test.info().project.name;
      await openRoute(page, pageInfo.hash);
      await page.waitForTimeout(500);
      await page.screenshot({
        path: `e2e/screenshots/${project}-${pageInfo.name}.png`,
        fullPage: false,
      });
    });
  }

  test("1440 物理宽度工作台 150%/200% 等效缩放截图", async ({ page }) => {
    test.skip(
      test.info().project.name !== "desktop-1440",
      "仅 1440 项目执行缩放截图",
    );
    await openRoute(
      page,
      "/workbench?episode=episode-uat-03-screening-gap_conflict",
    );
    await setZoom(page, 1.5);
    await page.waitForTimeout(200);
    await page.screenshot({
      path: "e2e/screenshots/desktop-1440-workbench-zoom150.png",
    });
    await setZoom(page, 2);
    await page.waitForTimeout(200);
    await page.screenshot({
      path: "e2e/screenshots/desktop-1440-workbench-zoom200.png",
    });
  });
});
