/**
 * Production repository acceptance over real HTTP/SQLite/background execution.
 * The protocol is synthetic; no raw clinical material is read or changed.
 */
import { execFileSync } from "node:child_process";
import { rmSync } from "node:fs";
import { test, expect } from "@playwright/test";
import { collectRuntimeErrors, expectNoPageOverflow, openRoute } from "./helpers";

const fixturePath = "/tmp/enrollment-review-protocol-real-e2e-input/protocol.docx";

test.skip(
  process.env.PROTOCOL_REAL_E2E !== "1",
  "真实 HTTP 专项仅由 playwright.real.config.ts 启用",
);

test.beforeAll(() => {
  execFileSync(
    "uv",
    ["run", "python", "-m", "tests.v2.api.protocol_playwright_fixture", fixturePath],
    { cwd: "..", stdio: "inherit" },
  );
});

test.afterAll(() => {
  rmSync("/tmp/enrollment-review-protocol-real-e2e-input", { recursive: true, force: true });
});

test("首次发布后可显式选择项目并完成原文纠错重新发布", async ({ page, viewport }) => {
  const errors = collectRuntimeErrors(page);
  const width = viewport?.width ?? 1920;
  const protocolCode = `E2E-${width}`;
  const projectName = `真实联调测试研究-${width}`;

  await openRoute(page, "/protocols?mode=first");
  await page.locator('input[type="file"]').setInputFiles(fixturePath);
  await expect(page.getByRole("heading", { name: "核对方案信息与研究期别" })).toBeVisible({ timeout: 60_000 });

  await page.getByLabel("方案编号").fill(protocolCode);
  await page.getByLabel("项目名称").fill(projectName);
  await page.getByLabel("项目代号（可不填）").fill(`${protocolCode}-II`);
  await page.getByLabel("正式版本").fill("V1.0");
  await page.getByLabel("版本日期").fill("2026-08-17");
  await page.getByRole("radio", { name: /^II 期 / }).check();
  await page.getByRole("button", { name: "确认并继续解构" }).click();

  await expect(page.getByRole("heading", { name: "审阅解构草稿" })).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText("完整性检查", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "发布" })).toBeEnabled();
  await page.getByRole("button", { name: "发布" }).click();
  await expect(page.getByRole("dialog", { name: "确认发布新规则版本" })).toContainText("建立正式项目");
  await page.getByRole("button", { name: "确认发布" }).click();
  await expect(page.getByRole("heading", { name: "发布完成" })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("第 1 版", { exact: true })).toBeVisible();

  await openRoute(page, "/protocols?mode=redo");
  await expect(page.locator(".protocol-redo__project--selected")).toHaveCount(0);
  const project = page.getByRole("button", { name: new RegExp(projectName) });
  await project.click();
  await expect(project).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "不上传文件，按反馈修订" }).click();

  await expect(page.getByRole("heading", { name: /并列比较差异/ })).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "基于反馈修订" }).click();
  await page.getByRole("radio", { name: /原文理解纠错/ }).check();
  await page.getByPlaceholder(/例如：EX-04/).fill("请按方案原文重新核对该条标题与结构。");
  await page.getByRole("button", { name: "提交反馈修订" }).click();
  await expect(page.getByRole("dialog", { name: "基于反馈修订草稿" })).toHaveCount(0);
  await expect(page.getByText(/已按方案原文核对/).first()).toBeVisible();

  await page.getByRole("button", { name: "保存草稿" }).click();
  await expect(page.getByText("可以发布", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "发布" })).toBeEnabled();
  await page.getByRole("button", { name: "发布" }).click();
  await page.getByRole("button", { name: "确认发布" }).click();
  await expect(page.getByRole("heading", { name: "发布完成" })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("第 2 版", { exact: true })).toBeVisible();

  await expectNoPageOverflow(page);
  expect(errors).toEqual([]);
});
