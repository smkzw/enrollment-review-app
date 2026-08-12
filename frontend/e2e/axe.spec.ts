/**
 * axe 无障碍扫描（PRD：axe-core 无 serious/critical 问题）。
 * 对全部一级路由执行 axe 规则；只断言 serious/critical 级违规为 0，
 * 轻微违规（minor）记录在报告中供 Codex 参考。
 */

import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { openRoute } from "./helpers";

const ROUTES = [
  { hash: "today", title: "今日工作" },
  { hash: "board", title: "项目看板" },
  { hash: "protocols", title: "方案工作台" },
  { hash: "subjects", title: "受试者与资料" },
  { hash: "workbench?episode=episode-uat-03-screening-gap_conflict", title: "入排工作台" },
  { hash: "actions", title: "行动中心" },
  { hash: "reports", title: "报告" },
  { hash: "tasks", title: "任务与系统" },
  { hash: "help", title: "系统帮助" },
];

test.describe("axe 扫描", () => {
  for (const route of ROUTES) {
    test(`${route.title} 无 serious/critical 违规`, async ({ page }) => {
      await openRoute(page, `/${route.hash}`);
      // 等待异步 stub 数据加载完成
      await page.waitForTimeout(400);
      const results = await new AxeBuilder({ page }).analyze();
      const severe = results.violations.filter(
        (violation) =>
          violation.impact === "serious" || violation.impact === "critical",
      );
      const summary = severe
        .map(
          (violation) =>
            `${violation.id}(${violation.impact})×${violation.nodes.length}`,
        )
        .join(", ");
      expect(severe, `serious/critical 违规：${summary}`).toEqual([]);
    });
  }
});
