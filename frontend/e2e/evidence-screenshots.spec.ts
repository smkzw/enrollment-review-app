/**
 * 证据工作台真实浏览器截图（供 Codex 视觉复核，本角色不做最终视觉验收）。
 * 每个最大化桌面项目（1080P/2K/4K）各保存两张截图：
 * 确认前复核态与确认后快照态。
 */

import { test, expect } from "@playwright/test";
import { SELECTED_FILES, SUBJECT_ID, EPISODE_ID, registerEvidenceRoutes } from "./evidence-fixtures";

const EVIDENCE_HASH = `#/subjects/${SUBJECT_ID}/evidence?episode=${EPISODE_ID}`;

test("证据工作台截图：复核态与确认态", async ({ page }, testInfo) => {
  const viewportKey = `${testInfo.project.name}`;
  await registerEvidenceRoutes(page, { activeReview: true });

  await page.goto(`/${EVIDENCE_HASH}`);
  await expect(
    page.getByRole("heading", { name: "证据工作台", level: 1 }),
  ).toBeVisible();

  // 补充资料预览（复核态）
  await page.getByRole("button", { name: "补充或重建资料" }).click();
  await page.getByRole("radio", { name: "补充资料" }).click();
  await page.setInputFiles("#evidence-file-input", SELECTED_FILES);
  await expect(page.getByLabel("确认前复核")).toBeVisible();
  await page.screenshot({
    path: `e2e/screenshots/evidence-${viewportKey}-review.png`,
  });

  // 解决冲突并确认（确认态）
  await page.getByLabel("作为原资料的新版本").check();
  await page.getByRole("button", { name: "确认上传" }).click();
  await expect(
    page.getByText(/已建立资料快照/),
  ).toBeVisible();
  await page.screenshot({
    path: `e2e/screenshots/evidence-${viewportKey}-committed.png`,
  });

  await page.getByRole("link", { name: "查看本次资料整理进度" }).click();
  await expect(page.getByRole("heading", { name: "本次处理概况" })).toBeVisible();
  await expect(page.getByText("检查报告.pdf")).toBeVisible();
  await expect(page.getByText("整理原始资料")).toBeVisible();
  await expect(page.getByText("evidence_processing")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "继续未完成事项" })).toHaveCount(0);
  await expect(page.getByText("这些操作不会实际整理资料或启动审核")).toHaveCount(0);
  await page.screenshot({
    path: `e2e/screenshots/evidence-${viewportKey}-task-detail.png`,
    fullPage: true,
  });
});
