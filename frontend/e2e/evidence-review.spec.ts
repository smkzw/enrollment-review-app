import { expect, test } from "@playwright/test";
import { collectRuntimeErrors, expectNoPageOverflow } from "./helpers";
import {
  EPISODE_ID,
  SUBJECT_ID,
  registerEvidenceRoutes,
} from "./evidence-fixtures";

const EVIDENCE_HASH = `#/subjects/${SUBJECT_ID}/evidence?episode=${EPISODE_ID}`;

test("活动资料版本的识别核对、冲突保留和被提及资料闭环", async ({ page }, testInfo) => {
  const runtimeErrors = collectRuntimeErrors(page);
  const log = await registerEvidenceRoutes(page, {
    activeReview: true,
    correctionConflict: true,
  });

  await page.goto(`/${EVIDENCE_HASH}`);
  await expect(page.getByLabel("当前资料上下文")).toContainText("当前有效");

  const pageIndex = page.getByLabel("识别页清单");
  await expect(pageIndex.getByText("筛选期病历.pdf").first()).toBeVisible();
  await expect(pageIndex.getByRole("button", { name: /第 2 页/ })).toBeEnabled();
  await expect(
    pageIndex.getByText("原始页面读取失败，请在后续恢复处理中重试。"),
  ).toBeVisible();

  await expect(page.getByText("患者否认近期发热，ALT 39 U/L。", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "校对后文本", exact: true })).toBeVisible();
  await expect(page.getByText("肯定/否定关系", { exact: true })).toBeVisible();
  await expect(page.getByAltText("第 1 页原始资料")).toBeVisible();
  await expect(page.getByLabel(/^重点标注/)).toHaveCount(0);
  await page.getByRole("button", { name: /查看 \d+ 处原件定位/ }).click();
  await expect(page.getByText(/当前资料无法稳定框出具体区域/)).toBeVisible();
  await page.getByRole("button", { name: "在原件中查看" }).first().click();
  await expect(page.getByLabel(/^重点标注/)).toHaveClass(
    /original-evidence-page__box--selected/,
  );
  await pageIndex.getByRole("button", { name: /第 2 页/ }).click();
  await expect(page.getByText("这一页尚未形成可核对的识别文本。")).toBeVisible();
  await expect(page.getByAltText("第 2 页原始资料")).toHaveCount(0);
  await pageIndex.getByRole("button", { name: /第 1 页/ }).click();
  await expect(page.getByRole("heading", { name: "校对后文本", exact: true })).toBeVisible();
  await expect(page.getByText("既往过敏原检测报告")).toBeVisible();
  await page.screenshot({
    path: `e2e/screenshots/evidence-review-initial-${testInfo.project.name}.png`,
    fullPage: true,
  });

  await page.getByRole("button", { name: "需要修订识别文字" }).click();
  const corrected = page.getByRole("textbox", { name: "校对后文本" });
  await page.getByRole("combobox", { name: "变化类别" }).selectOption("polarity");
  await corrected.fill("患者确认近期发热，ALT 39 U/L。");
  await page.getByRole("textbox", { name: "校对说明" }).fill("对照病历原文后修正");
  await page
    .getByRole("checkbox", {
      name: "我已逐字核对这项关键变化，并确认它会影响临床语义。",
    })
    .check();
  await page.getByRole("button", { name: "提交校对" }).click();
  const conflict = page.getByRole("alert", { name: "资料已发生变化" });
  await expect(conflict).toBeVisible();
  await expect(corrected).toHaveValue("患者确认近期发热，ALT 39 U/L。");
  await expect(conflict).toContainText("系统当前记录");
  await expect(conflict).not.toContainText("服务端");
  await expect(page.getByLabel("资料中提及但未提供").getByRole("alert")).toHaveCount(0);

  const referenced = page.getByLabel("资料中提及但未提供");
  await referenced.getByRole("textbox", { name: "本次操作说明" }).fill("已对照当前页原文");
  await referenced.getByRole("combobox", { name: "确认提及位置（当前页）" }).selectOption("locator-e2e-1");
  await referenced.getByRole("button", { name: "确认提及" }).click();
  await expect(referenced.getByText("已确认").first()).toBeVisible();

  await referenced.getByRole("combobox", { name: "关联当前有效资料" }).selectOption("version-e2e-active");
  await expect(referenced.getByText("已提供", { exact: true })).toBeVisible();
  await referenced.getByRole("button", { name: "解除资料关联" }).click();
  await expect(referenced.getByText("未提供").first()).toBeVisible();

  await page.screenshot({
    path: `e2e/screenshots/evidence-review-${testInfo.project.name}.png`,
    fullPage: true,
  });

  expect(log.some((entry) => /\/corrections$/.test(entry.url))).toBe(true);
  expect(log.some((entry) => /\/confirm$/.test(entry.url))).toBe(true);
  expect(log.some((entry) => /\/resolve$/.test(entry.url))).toBe(true);
  await expectNoPageOverflow(page);
  expect(runtimeErrors.filter((entry) => entry.startsWith("页面脚本："))).toEqual([]);
});
