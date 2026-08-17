/**
 * Phase 3 Slice 5 方案解构工作台验收：错误/空态/恢复、键盘焦点、
 * 工作区选择、页面级溢出与布局压力。
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

/** 标签可见时先切到编辑区。 */
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

  test("重新解构入口要求明确选择正式项目后才展示目标摘要", async ({ page }) => {
    await openRoute(page, "/protocols?mode=redo");
    await expect(page.getByRole("heading", { name: "重新解构已有项目" })).toBeVisible();
    await expect(page.locator(".protocol-redo__project--selected")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "选择新版方案文件" })).toBeDisabled();

    const firstProject = page.locator(".protocol-redo__project").first();
    await expect(firstProject).toContainText("TEST-001");
    await expect(firstProject).toContainText("正式版本");
    await firstProject.click();
    await expect(firstProject).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByRole("heading", { name: "目标项目与正式版本" })).toBeVisible();
    await expect(page.getByRole("button", { name: "选择新版方案文件" })).toBeEnabled();
    await expect(
      page.getByRole("button", { name: "不上传文件，按反馈修订" }),
    ).toBeVisible();
    await expectNoPageOverflow(page);
  });

  test("重新解构可不上传新文件并进入正式草稿反馈修订", async ({ page }) => {
    await openRoute(page, "/protocols?mode=redo");
    await page.locator(".protocol-redo__project").first().click();
    await page.getByRole("button", { name: "不上传文件，按反馈修订" }).click();
    await expect(page.getByRole("heading", { name: /并列比较差异/ })).toBeVisible();
    await expect(page.getByRole("button", { name: "基于反馈修订" })).toBeVisible();
    await expectNoPageOverflow(page);
  });

  test("重新解构任务并列展示规则变化工作台", async ({ page }) => {
    await openRoute(page, "/protocols?job=job-demo-redo");
    await expect(page.getByRole("heading", { name: /并列比较差异/ })).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "当前正式版本" }),
    ).toBeVisible();
    await expect(page.getByRole("heading", { name: "新草稿" })).toBeVisible();
    await expect(page.getByRole("button", { name: "保存草稿" })).toBeVisible();
    await expect(page.getByRole("button", { name: "基于反馈修订" })).toBeVisible();
    await expect(page.getByRole("button", { name: "发布" })).toBeVisible();
    await expectNoPageOverflow(page);
  });

  test("重新解构：反馈修订弹层可提交", async ({ page }) => {
    await openRoute(page, "/protocols?job=job-demo-redo");
    await page.getByRole("button", { name: "基于反馈修订" }).click();
    await expect(page.getByRole("dialog", { name: "基于反馈修订草稿" })).toBeVisible();
    await page
      .getByRole("radio", { name: /补充解释/ })
      .check();
    await page.getByPlaceholder(/例如：EX-04/).fill("核对版本差异后补充说明。");
    await page.getByRole("button", { name: "提交反馈修订" }).click();
    // 提交成功后弹层关闭，回到并列差异工作台
    await expect(page.getByRole("dialog", { name: "基于反馈修订草稿" })).toHaveCount(0);
    await expect(page.getByRole("heading", { name: /并列比较差异/ })).toBeVisible();
  });

  test("恢复示例展示横幅并可继续到草稿审阅", async ({ page }) => {
    await openProtocolHash(page, `/protocols?job=${RECOVERY_JOB}`);
    await expect(page.getByRole("heading", { name: "可从中断处继续" })).toBeVisible();
    await expect(page.locator(".protocol-recovery__action-text")).toContainText("生成草稿");
    await page.getByRole("button", { name: "继续任务" }).click();
    await expect(page.getByRole("heading", { name: "审阅解构草稿" })).toBeVisible();
    await expectNoPageOverflow(page);
  });

  test("身份确认阶段展示期别候选", async ({ page }) => {
    await openProtocolHash(page, `/protocols?job=${IDENTITY_JOB}`);
    await expect(
      page.getByRole("heading", { name: "核对方案信息与研究期别" }),
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

  test("1080P 草稿审阅在 1.5×/2× 布局压力下无页面级横向滚动", async ({ page }) => {
    test.skip(page.viewportSize()?.width !== 1920, "仅 1080P 桌面项目执行");
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
