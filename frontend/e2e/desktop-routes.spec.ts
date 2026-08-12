/**
 * 桌面路由验收（合同 §3.1）：九个一级入口全部可达，页面级无横向滚动，
 * 关键内容与界面试用标记可见。
 */

import { test, expect } from "@playwright/test";
import { expectNoPageOverflow, openRoute, setZoom } from "./helpers";

const ROUTES = [
  { hash: "today", title: "今日工作", key: "待处理事项" },
  { hash: "board", title: "项目看板", key: "受试者" },
  { hash: "protocols", title: "方案工作台", key: "当前使用版本" },
  { hash: "subjects", title: "受试者与资料", key: "应备证据覆盖" },
  { hash: "workbench", title: "入排工作台", key: "规则与判断状态" },
  { hash: "actions", title: "行动中心", key: "行动列表" },
  { hash: "reports", title: "报告", key: "生成报告" },
  { hash: "tasks", title: "任务与系统", key: "资料整理任务" },
  { hash: "help", title: "系统帮助", key: "从这里开始" },
];

test.describe("一级路由", () => {
  for (const route of ROUTES) {
    test(`${route.title} 可达且无页面级横向滚动`, async ({ page }) => {
      await openRoute(page, `/${route.hash}`);
      await expect(
        page.getByRole("heading", { name: route.title, level: 1 }),
      ).toBeVisible();
      await expect(page.getByText(route.key).first()).toBeVisible();
      await expectNoPageOverflow(page);
    });
  }

  test("入排工作台直达审核节点并展示三区", async ({ page }) => {
    await openRoute(
      page,
      "/workbench?episode=episode-uat-03-screening-gap_conflict",
    );
    await expect(page.locator(".workbench-episode__subject")).toHaveText("UAT-03");
    // 内容区 ≥1080px 时三区并列；更窄时（1280 桌面）为“规则/判断/证据”标签模式
    const tabsMode = await page.locator(".workbench-tabs").isVisible();
    if (tabsMode) {
      await expect(page.getByRole("tab", { name: "规则" })).toBeVisible();
      await expect(page.getByRole("tab", { name: "判断" })).toBeVisible();
      await expect(page.getByRole("tab", { name: "证据" })).toBeVisible();
      await expect(page.locator(".workbench-col--rules")).toBeVisible();
    } else {
      await expect(page.locator(".workbench-pane--tree")).toBeVisible();
      await expect(page.locator(".judgment-pane")).toBeVisible();
      await expect(page.locator(".evidence-pane")).toBeVisible();
    }
    await expectNoPageOverflow(page);
  });

  test("界面试用标记在今日工作可见", async ({ page }) => {
    await openRoute(page, "/today");
    await expect(page.getByText(/^界面试用：/)).toBeVisible();
  });

  test("今日工作待处理事项预览不超过六行且有行动中心入口", async ({ page }) => {
    await openRoute(page, "/today");
    const dueSection = page.locator("section[aria-labelledby='today-due-title']");
    await expect(dueSection.locator(".today-list > li")).toHaveCount(6);
    await expect(
      dueSection.getByRole("link", { name: "打开行动中心" }),
    ).toBeVisible();
  });

  test("行动中心无参数时默认选中首项并显示详情", async ({ page }) => {
    await openRoute(page, "/actions");
    const detail = page.getByRole("complementary", { name: "行动详情" });
    await expect(detail).toBeVisible();
    await expect(detail.getByText("什么资料可以关闭")).toBeVisible();
    await expect(detail).toContainText("UAT-03");
  });

  test("1440 物理宽度全部一级页面在 150%/200% 等效缩放下无页面级横向滚动", async ({ page }) => {
    test.skip(page.viewportSize()?.width !== 1440, "仅 1440 项目执行");
    for (const route of ROUTES) {
      await openRoute(page, `/${route.hash}`);
      await expect(
        page.getByRole("heading", { name: route.title, level: 1 }),
      ).toBeVisible();
      await expect(page.getByText(route.key).first()).toBeVisible();
      await setZoom(page, 1.5);
      await expectNoPageOverflow(page);
      await setZoom(page, 2);
      await expectNoPageOverflow(page);
      const visibleText = await page.locator("#main-content").innerText();
      expect(visibleText).not.toMatch(/\bREQ-/);
      expect(visibleText).not.toMatch(/\b(?:undefined|null|year|xULN)\b/);
    }
  });
});
