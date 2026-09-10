/**
 * 页面视觉核验的宽屏用户验收：状态、失败范围、恢复操作与页面溢出。
 */

import { expect, test } from "@playwright/test";
import { EPISODE_ID, SUBJECT_ID, registerEvidenceRoutes } from "./evidence-fixtures";

const EVIDENCE_HASH = `#/subjects/${SUBJECT_ID}/evidence?episode=${EPISODE_ID}`;

test("页面视觉核验在宽屏下可读且可恢复", async ({ page }, testInfo) => {
  await registerEvidenceRoutes(page, {
    activeReview: true,
    selectiveVisionTask: "failed_final",
  });

  await page.goto(`/${EVIDENCE_HASH}`);
  const panel = page.getByRole("region", { name: "页面视觉核验" });
  await expect(panel).toBeVisible();
  await expect(panel.getByText("未完成，需要处理")).toBeVisible();
  await expect(panel.getByText("需要核验的页面")).toBeVisible();
  await expect(panel.getByText("筛选期病历第 1页、检查报告第 2 页")).toBeVisible();
  await expect(panel.getByText(/model|payload|lease|job-selective/i)).toHaveCount(0);

  const overflow = await page.evaluate(() => ({
    document: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    panel: (() => {
      const element = document.querySelector<HTMLElement>("[aria-labelledby='selective-vision-task-title']");
      return element === null ? -1 : element.scrollWidth - element.clientWidth;
    })(),
  }));
  expect(overflow.document).toBeLessThanOrEqual(1);
  expect(overflow.panel).toBeLessThanOrEqual(1);

  await page.screenshot({
    path: `e2e/screenshots/selective-vision-${testInfo.project.name}.png`,
    fullPage: true,
  });

  await panel.getByRole("button", { name: "重新开始核验" }).click();
  await expect(panel.getByText("等待处理")).toBeVisible();
  await expect(panel.getByRole("button", { name: "停止核验" })).toBeVisible();
});
