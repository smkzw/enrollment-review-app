/**
 * 证据面板截图采集（供 Codex 视觉复核；本角色不做最终视觉验收）。
 * 打开个例全景、展开全部历时信息、打开证据面板，输出三档宽屏截图。
 */
import { expect, test } from "@playwright/test";
import {
  PROFILE_HASH,
  registerProfileRoutes,
} from "./profile-evidence-fixtures";

test("证据面板截图", async ({ page }, testInfo) => {
  await registerProfileRoutes(page);
  await page.goto(`/${PROFILE_HASH}`);
  await page.getByRole("heading", { name: "受试者与资料", level: 1 }).waitFor();
  await page.getByRole("button", { name: "全部历时信息" }).click();
  await page
    .getByRole("button", { name: /查看.基线血压 120\/80 mmHg.的原文证据/ })
    .click();
  await page.getByLabel("该条目的原文证据与定位").waitFor();
  const sourceImage = page.getByRole("img", { name: "第 1 页原始资料" });
  await sourceImage.waitFor();
  await expect
    .poll(() =>
      sourceImage.evaluate(
        (element) => element instanceof HTMLImageElement && element.complete && element.naturalWidth > 0,
      ),
    )
    .toBe(true);
  await page.screenshot({
    path: `e2e/screenshots/${testInfo.project.name}-profile-evidence-panel.png`,
    fullPage: false,
  });
  await page.getByRole("button", { name: "关闭原文证据" }).click();
  await page.waitForTimeout(300);
  await page.screenshot({
    path: `e2e/screenshots/${testInfo.project.name}-profile-two-column.png`,
    fullPage: false,
  });
});
