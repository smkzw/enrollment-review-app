/**
 * 键盘路径验收（合同 §7.1）：跳过导航、规则树方向键、Enter 选择、
 * 证据弹窗打开/关闭与焦点返回。
 */

import { test, expect } from "@playwright/test";
import { openRoute } from "./helpers";

test.describe("键盘路径", () => {
  test("跳过链接可到达主要内容", async ({ page }) => {
    await openRoute(page, "/today");
    await page.keyboard.press("Tab");
    await expect(page.getByRole("link", { name: "跳到主要内容" })).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("main")).toBeFocused();
  });

  test("规则树键盘：Enter 展开、方向键移动、Enter 选中子项", async ({ page }) => {
    await openRoute(
      page,
      "/workbench?episode=episode-uat-03-screening-gap_conflict&component=component-in-01",
    );
    // EX-01 默认折叠：聚焦后 Enter 展开
    const rule = page.getByRole("button", { name: /EX-01 排除条件/ });
    await rule.focus();
    await page.waitForTimeout(120);
    await page.keyboard.press("Enter");
    await expect(
      page.getByRole("button", { name: /EX-01a 实验室异常与研究者风险的复合条件/ }),
    ).toBeVisible();
    // 方向键向下移动到子项并 Enter 选中
    await page.keyboard.press("ArrowDown");
    await expect(
      page.getByRole("button", { name: /EX-01a 实验室异常与研究者风险的复合条件/ }),
    ).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(
      page.getByRole("button", { name: /EX-01a 实验室异常与研究者风险的复合条件/ }),
    ).toHaveAttribute("aria-current", "true");
  });

  test("键盘打开证据弹窗，Escape 关闭并返回触发按钮", async ({ page }) => {
    await openRoute(
      page,
      "/workbench?episode=episode-uat-03-screening-gap_conflict&component=component-ex-01",
    );
    await expect(page
      .getByRole("button", { name: /EX-01a 实验室异常与研究者风险的复合条件/ })
    ).toHaveAttribute("aria-current", "true");
    // 工作区进入标签视图时，先切到证据标签
    if (await page.locator(".workbench-tabs").isVisible()) {
      await page.getByRole("tab", { name: "证据" }).click();
    }
    const openEvidence = page
      .getByRole("button", { name: /打开证据：合成筛选资料/ })
      .first();
    await openEvidence.focus();
    await page.waitForTimeout(120);
    await page.keyboard.press("Enter");
    await expect(
      page.getByRole("dialog", { name: "原始资料证据" }),
    ).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toBeHidden();
    await expect(openEvidence).toBeFocused();
  });
});
