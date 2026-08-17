/**
 * Phase 3 Slice 5 方案解构工作台验收：错误/空态/恢复、键盘焦点、
 * 窄屏标签共享选择、页面级溢出与布局压力。
 */

import { test, expect, type Page } from "@playwright/test";
import {
  collectRuntimeErrors,
  expectNoPageOverflow,
  openRoute,
  setLayoutStressFactor,
} from "./helpers";

const DEMO_JOB = "job-demo-review";
const RECOVERY_JOB = "job-demo-recovery";
const IDENTITY_JOB = "job-demo-identity";

async function openProtocolHash(page: Page, hash: string) {
  await page.goto(`/#${hash}`);
  await page.waitForLoadState("networkidle");
  await expect(page.getByText("正在整理资料，请稍候", { exact: true })).toHaveCount(0);
}

/** 标签模式下先切到编辑区（1280 等内容区较窄时与窄屏相同行为）。 */
async function showDraftEditPane(page: Page) {
  const tabs = page.locator(".protocol-draft-tabs");
  if (await tabs.isVisible()) {
    await page.getByRole("tab", { name: "编辑" }).click();
  }
}

test.describe("方案解构工作台（Slice 5）", () => {
  test("未知任务显示中文错误态并可返回首页", async ({ page }) => {
    const errors = collectRuntimeErrors(page);
    await openProtocolHash(page, `/protocols?job=does-not-exist`);
    await expect(page.getByRole("alert")).toContainText("未找到该解构任务");
    await page.getByRole("button", { name: "重试" }).click();
    await expect(page.getByRole("heading", { name: "方案工作台" })).toBeVisible();
    await expectNoPageOverflow(page);
    expect(errors).toEqual([]);
  });

  test("重新解构占位页展示中文空态", async ({ page }) => {
    await openRoute(page, "/protocols?mode=redo");
    await expect(page.getByRole("heading", { name: "重新解构已有项目" })).toBeVisible();
    await expect(page.getByText("重新解构流程尚未在本切片开放")).toBeVisible();
    await expectNoPageOverflow(page);
  });

  test("恢复示例展示横幅并可继续到草稿审阅", async ({ page }) => {
    await openProtocolHash(page, `/protocols?job=${RECOVERY_JOB}`);
    await expect(page.getByRole("heading", { name: "可从中断处继续" })).toBeVisible();
    await expect(page.locator(".protocol-recovery__detail")).toContainText("生成草稿");
    await page.getByRole("button", { name: "继续任务" }).click();
    await expect(page.getByRole("heading", { name: "审阅解构草稿" })).toBeVisible();
    await expectNoPageOverflow(page);
  });

  test("身份确认阶段展示期别候选", async ({ page }) => {
    await openProtocolHash(page, `/protocols?job=${IDENTITY_JOB}`);
    await expect(
      page.getByRole("heading", { name: "确认方案身份与期别" }),
    ).toBeVisible();
    await expect(page.getByText("II 期", { exact: true })).toBeVisible();
    await expect(page.getByText("III 期", { exact: true })).toBeVisible();
    await expectNoPageOverflow(page);
  });

  test("规则树键盘：Enter 选中子项", async ({ page }) => {
    await openRoute(page, `/protocols?job=${DEMO_JOB}`);
    const exChild = page.getByRole("button", { name: /EX-01a/ });
    await exChild.focus();
    await page.keyboard.press("Enter");
    await expect(exChild).toHaveAttribute("aria-selected", "true");
    await showDraftEditPane(page);
    await expect(page.getByRole("tabpanel", { name: /编辑/ })).toContainText(
      "ALT或AST≥1.5×ULN",
    );
  });

  test("窄屏标签切换共享 component 选择", async ({ page }) => {
    test.skip(page.viewportSize()?.width !== 390, "仅窄屏项目执行");
    await openRoute(page, `/protocols?job=${DEMO_JOB}`);
    await page.getByRole("button", { name: /IN-01a/ }).click();
    await page.getByRole("tab", { name: "编辑" }).click();
    await expect(page.getByRole("tabpanel", { name: /编辑/ })).toContainText("年龄要求");
    await page.getByRole("tab", { name: "来源定位" }).click();
    await expect(page.getByRole("tabpanel", { name: /来源定位/ })).toContainText(/第 12 页/);
    await page.getByRole("tab", { name: "规则树" }).click();
    await expect(page.getByRole("button", { name: /IN-01a/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    await expectNoPageOverflow(page);
  });

  test("1440 草稿审阅在 1.5×/2× 布局压力下无页面级横向滚动", async ({ page }) => {
    test.skip(page.viewportSize()?.width !== 1440, "仅 1440 项目执行");
    await openRoute(page, `/protocols?job=${DEMO_JOB}`);
    await expect(page.getByRole("heading", { name: "审阅解构草稿" })).toBeVisible();
    await setLayoutStressFactor(page, 1.5);
    await expectNoPageOverflow(page);
    await setLayoutStressFactor(page, 2);
    await expectNoPageOverflow(page);
    const text = await page.locator("#main-content").innerText();
    expect(text).not.toMatch(/\b(?:undefined|null|fixture|stub)\b/i);
  });
});
