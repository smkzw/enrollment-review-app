/**
 * 风险到证据 ≤3 次操作（合同 §6.2 / UAT-P1-07）：从今日工作 → 审核节点 →
 * 规则子项 → 证据详情，验证操作数与证据信息可见性。
 */

import { test, expect } from "@playwright/test";
import { openRoute } from "./helpers";

test.describe("风险到证据路径", () => {
  test("今日工作冲突 → 对应规则 → 证据（不超过 3 次操作）", async ({ page }) => {
    await openRoute(page, "/today");
    // 操作 1：从冲突区进入 UAT-03 筛选审核，深链直接选中冲突子项。
    const conflictSection = page.locator(
      "section[aria-labelledby='today-conflict-title']",
    );
    await conflictSection
      .getByRole("link", { name: /打开 UAT-03 筛选期审核/ })
      .first()
      .click();
    await expect(page.locator(".workbench-episode__subject")).toHaveText("UAT-03");
    await expect(page)
      .toHaveURL(/component=component-ex-01/);
    await expect(page
      .getByRole("button", { name: /EX-01a 实验室异常与研究者风险的复合条件/ })
    ).toHaveAttribute("aria-current", "true");
    // 操作 2：标签模式下切到证据标签（三区并列模式无需此步）。
    if (await page.locator(".workbench-tabs").isVisible()) {
      await page.getByRole("tab", { name: "证据" }).click();
    }
    // 证据卡已可见：文件、页码、定位精度
    await expect(
      page.getByText("合成筛选资料.pdf").first(),
    ).toBeVisible();
    await expect(page.getByText("仅页码").first()).toBeVisible();
    // 操作 3：打开证据详情，验证来源与降级原因。
    await page
      .getByRole("button", { name: /打开证据：合成筛选资料/ })
      .first()
      .click();
    const dialog = page.getByRole("dialog", { name: "原始资料证据" });
    await expect(dialog).toBeVisible();
    await expect(dialog).toContainText("第 4 页");
    await expect(dialog).toContainText("来源方：研究者方");
    await expect(dialog).toContainText("扫描页无法稳定定位字符或坐标");
  });

  test("受试者资料页事件 → 证据直达（URL 定位，≤3 次操作）", async ({ page }) => {
    await openRoute(page, "/subjects?subject=subject-uat-03-gap_conflict&stage=screening");
    // 操作 1：点击汇总事件的“查看判断依据”直达工作台证据区
    await page
      .getByRole("link", { name: /查看判断依据：资料缺口与冲突待处理/ })
      .first()
      .click();
    // 证据卡自动定位（高亮）且文件/页码/精度可见
    await expect(page.locator(".workbench-episode__subject")).toHaveText("UAT-03");
    await expect(page.locator(".evidence-pane__item--focus")).toBeVisible();
    await expect(
      page.getByText("合成筛选资料.pdf").first(),
    ).toBeVisible();
  });

  test("个例事件只提供与证据关系相符的入口，不用共享片段冒充原始依据", async ({
    page,
  }) => {
    await openRoute(
      page,
      "/subjects?subject=subject-uat-01-clear&stage=screening&all=1",
    );
    const surgery = page
      .getByRole("heading", { name: "阑尾切除术" })
      .locator("xpath=ancestor::article");
    await expect(surgery).toContainText("尚无该事件的独立原始资料定位");
    await expect(surgery.getByRole("link")).toHaveCount(0);

    await openRoute(
      page,
      "/subjects?subject=subject-uat-03-gap_conflict&stage=screening",
    );
    const summaryLink = page.getByRole("link", {
      name: "查看判断依据：资料缺口与冲突待处理",
    });
    await expect(summaryLink).toHaveAttribute("href", /component=component-ex-01/);
    await summaryLink.click();
    await expect(page).toHaveURL(/component=component-ex-01/);
    await expect(page.locator(".workbench-episode__subject")).toHaveText("UAT-03");
    if (await page.locator(".workbench-tabs").isVisible()) {
      await page.getByRole("tab", { name: "规则" }).click();
    }
    await expect(
      page.getByRole("button", {
        name: /EX-01a 实验室异常与研究者风险的复合条件/,
      }),
    ).toHaveAttribute("aria-current", "true");

    await openRoute(
      page,
      "/subjects?subject=subject-uat-03-gap_conflict&stage=screening",
    );
    await expect(
      page.getByRole("link", {
        name: "查看关联规则资料：合并用药时间轴待核对",
      }),
    ).toBeVisible();
  });
});
