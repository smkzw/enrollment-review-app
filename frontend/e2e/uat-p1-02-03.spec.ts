/**
 * UAT-P1-02/P1-03 聚焦浏览器预试：只验证本地演示状态与中文可操作路径。
 */

import type { Page } from "@playwright/test";
import { test, expect } from "@playwright/test";
import { collectRuntimeErrors, expectNoPageOverflow, openRoute } from "./helpers";

const runtimeErrorsByPage = new WeakMap<Page, string[]>();

test.describe("UAT-P1-02/P1-03", () => {
  test.beforeEach(async ({ page }) => {
    runtimeErrorsByPage.set(page, collectRuntimeErrors(page));
  });

  test.afterEach(async ({ page }) => {
    await page.waitForTimeout(0);
    expect(runtimeErrorsByPage.get(page) ?? []).toEqual([]);
  });

  test("P1-02 从项目看板进入新建项目，确认期别并独立进入筛选期", async ({ page }) => {
    await openRoute(page, "/board");
    await page.getByRole("link", { name: "从方案新建项目" }).click();

    const dialog = page.getByRole("dialog", { name: "确认方案信息" });
    await expect(dialog).toBeVisible();
    await dialog.getByRole("button", { name: "确认方案并继续" }).click();
    await page.getByRole("button", { name: "确认研究期别并继续" }).click();
    await page.getByRole("radio", { name: /筛选期/ }).check();
    await page.getByRole("button", { name: "创建项目并进入筛选期" }).click();

    await expect(page.getByRole("heading", { name: "项目已建立" })).toBeVisible();
    await expect(page.getByText("当前位置：筛选期")).toBeVisible();
    await expect(page.getByText("方案版本", { exact: true }).locator(".."))
      .toContainText("V1.0");
    await expect(page.getByText("研究期别", { exact: true }).locator(".."))
      .toContainText("Ⅲ期");
    await expect(page.getByText(/未带入旧项目或其他阶段资料/)).toBeVisible();
    await expect(page.getByText("UAT-01")).toHaveCount(0);
    await expectNoPageOverflow(page);

    await openRoute(page, "/today");
    await openRoute(page, "/projects/new");
    await expect(page.getByRole("heading", { name: "项目已建立" })).toBeVisible();
    await expect(page.getByRole("link", { name: "返回原项目看板" })).toBeVisible();

    await page.getByRole("button", { name: "恢复试用初始状态" }).click();
    await expect(page.getByRole("dialog", { name: "确认方案信息" })).toBeVisible();
  });

  test("P1-03 并列查看三类变化，定位原文后保存草稿并复位", async ({ page }) => {
    await openRoute(page, "/protocols");

    await expect(page.getByRole("heading", { name: "当前使用版本" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "新版本草稿" })).toBeVisible();
    await expect(page.getByRole("heading", { name: /新增/ })).toBeVisible();
    await expect(page.getByRole("heading", { name: /删除/ })).toBeVisible();
    await expect(page.getByRole("heading", { name: /逻辑或时间范围变化/ })).toBeVisible();

    await expect(page.getByRole("button", { name: /查看当前方案.*EX-05/ })).toHaveCount(0);
    await page.getByRole("button", { name: "查看新版本草稿第 12 页：EX-05" }).click();
    const sourceDialog = page.getByRole("dialog", { name: /EX-05/ });
    await expect(sourceDialog).toContainText("新版本草稿");
    await expect(sourceDialog).toContainText("第 12 页");
    await sourceDialog.getByRole("button", { name: "关闭方案原文定位" }).click();
    await expect(
      page.getByRole("button", { name: "查看当前方案第 10 页：必做-02" }),
    ).toBeVisible();
    const changed = page
      .getByRole("heading", { name: /逻辑或时间范围变化/ })
      .locator("..");
    await expect(changed).toContainText("查看当前方案第 10 页：EX-01");
    await expect(changed).toContainText("查看新版本草稿第 12 页：EX-01");

    await page.getByRole("button", { name: "保存为草稿" }).click();
    await expect(page.getByRole("status")).toContainText("已保存为草稿");
    await expect(page.locator(".protocol-version--current .protocol-version__name")).toHaveText("V1.0");
    await expect(page.getByText(/当前规则版本没有被覆盖/)).toBeVisible();

    await openRoute(page, "/today");
    await openRoute(page, "/protocols");
    await expect(page.getByRole("button", { name: "已保存为草稿" })).toBeVisible();
    await expect(page.getByText(/当前规则版本没有被覆盖/)).toBeVisible();

    await page.getByRole("button", { name: "恢复试用初始状态" }).click();
    await expect(page.getByRole("button", { name: "保存为草稿" })).toBeVisible();
    await expect(page.getByRole("status")).toHaveCount(0);
    await expectNoPageOverflow(page);
  });
});
