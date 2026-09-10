/**
 * 风险到证据 ≤3 次操作（合同 §6.2 / UAT-P1-07）：从今日工作 → 审核节点 →
 * 规则子项 → 证据详情，验证操作数与证据信息可见性。
 */

import { test, expect } from "@playwright/test";
import { openRoute } from "./helpers";
import {
  PROFILE_HASH,
  registerProfileRoutes,
} from "./profile-evidence-fixtures";

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

  test("受试者资料页事件 → 原文证据（≤3 次操作）", async ({ page }) => {
    await registerProfileRoutes(page);
    await page.goto(`/${PROFILE_HASH}&all=1`);
    await page.getByRole("heading", { name: /症状体征/ }).waitFor();
    // 操作 1：事件直接打开其自身原文，不借道其他规则或页面。
    await page
      .getByRole("button", { name: /查看.发热.的原文证据/ })
      .click();
    const panel = page.getByLabel("该条目的原文证据与定位");
    await expect(panel).toBeVisible();
    await expect(panel.getByText("体温 38.2°C，伴发热")).toBeVisible();
    await expect(panel.getByText("筛选病历.pdf")).toBeVisible();
    await expect(page.getByLabel(/^重点标注/)).toHaveCount(1);
  });

  test("事实与事件分别打开自身原文，不共用不相干的定位", async ({
    page,
  }) => {
    await registerProfileRoutes(page);
    await page.goto(`/${PROFILE_HASH}&all=1`);
    await page.getByRole("heading", { name: /人口学\/基线/ }).waitFor();

    await page
      .getByRole("button", { name: /查看.基线血压 120\/80 mmHg.的原文证据/ })
      .click();
    let panel = page.getByLabel("该条目的原文证据与定位");
    await expect(
      panel.locator(".profile-locator__excerpt", {
        hasText: "基线血压 120/80 mmHg",
      }),
    ).toBeVisible();
    await expect(panel.getByText("体温 38.2°C，伴发热")).toHaveCount(0);
    await page.getByRole("button", { name: "关闭原文证据" }).click();

    await page.getByRole("button", { name: /查看.发热.的原文证据/ }).click();
    panel = page.getByLabel("该条目的原文证据与定位");
    await expect(panel.getByText("体温 38.2°C，伴发热")).toBeVisible();
    await expect(
      panel.locator(".profile-locator__excerpt", {
        hasText: "基线血压 120/80 mmHg",
      }),
    ).toHaveCount(0);
  });
});
