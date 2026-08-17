/**
 * 截图收集（供 Codex 视觉复核；本角色不做最终视觉验收）。
 * 每个视口项目输出关键页面截图；1080P 项目额外输出两档布局压力截图。
 */

import { test, expect } from "@playwright/test";
import { openRoute, setLayoutStressFactor } from "./helpers";
import { UAT_TRIAL_STATE_KEYS } from "../src/app/uatTrialState";

const SHOT_PAGES = [
  { hash: "/today", name: "today" },
  { hash: "/board", name: "board" },
  { hash: "/projects/new", name: "project-create" },
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

  test("1080P 物理宽度工作台两档布局压力截图", async ({ page }) => {
    test.skip(
      test.info().project.name !== "desktop-1080p",
      "仅 1080P 项目执行布局压力截图",
    );
    await openRoute(
      page,
      "/workbench?episode=episode-uat-03-screening-gap_conflict",
    );
    await setLayoutStressFactor(page, 1.5);
    await page.waitForTimeout(200);
    await page.screenshot({
      path: "e2e/screenshots/desktop-1080p-workbench-layout-stress-1280.png",
    });
    await setLayoutStressFactor(page, 2);
    await page.waitForTimeout(200);
    await page.screenshot({
      path: "e2e/screenshots/desktop-1080p-workbench-layout-stress-960.png",
    });
  });

  test("1080P 关键确认弹窗截图", async ({ page }) => {
    const project = test.info().project.name;
    test.skip(
      project !== "desktop-1080p",
      "仅 1080P 项目执行确认弹窗截图",
    );

    await openRoute(page, "/board");
    await page.getByRole("checkbox", { name: "选择 UAT-03" }).check();
    await page.getByRole("checkbox", { name: "选择 UAT-04" }).check();
    await page.getByRole("button", { name: "批量回看审核摘要" }).click();
    await page.screenshot({ path: `e2e/screenshots/${project}-batch-confirm.png` });

    await openRoute(page, "/actions?action=action-uat-03-screening-gap-professional");
    await page.getByLabel("确认理由（必填）").fill("研究者已补充书面判断，并完成签名和日期。");
    await page.getByRole("button", { name: "核对确认内容" }).click();
    await page.screenshot({ path: `e2e/screenshots/${project}-manual-confirm.png` });
  });

  test("4K 帮助页复位确认界面与复位后今日工作截图", async ({ page }) => {
    test.skip(
      test.info().project.name !== "desktop-4k",
      "仅 4K 项目执行复位截图",
    );
    // 先注入登记键：截图必须来自真实复位路径，不得用首屏帮助页冒充复位证据。
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await page.evaluate((keys) => {
      for (const key of keys) window.sessionStorage.setItem(key, "shot");
    }, UAT_TRIAL_STATE_KEYS);

    await openRoute(page, "/help");
    const trigger = page.getByRole("button", { name: "开始新的界面试用" });
    await trigger.scrollIntoViewIfNeeded();
    await trigger.click();
    await expect(
      page.getByRole("dialog", { name: "开始新的界面试用" }),
    ).toBeVisible();
    await page.waitForTimeout(300);
    await page.screenshot({
      path: "e2e/screenshots/desktop-4k-help-reset-confirm.png",
      fullPage: false,
    });

    await page.getByRole("button", { name: "确认并回到今日工作" }).click();
    await expect(page).toHaveURL(/\/today$/);
    await page.waitForTimeout(500);
    await page.screenshot({
      path: "e2e/screenshots/desktop-4k-today-after-reset.png",
      fullPage: false,
    });

    // 与截图同帧证明复位真实生效：登记键已被清除。
    const cleared = await page.evaluate(
      (keys) => keys.every((key) => window.sessionStorage.getItem(key) === null),
      UAT_TRIAL_STATE_KEYS,
    );
    expect(cleared).toBe(true);
  });
});
