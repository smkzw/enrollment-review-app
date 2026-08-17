/**
 * 14 项正式 UAT 任务指定目标从界面可达（worker_03 / 成功条件 4、设计 §UAT-P1-xx）。
 * - 每项只验证任务卡“指定对象/目标”能否从用户可见入口到达，不验证判定结果。
 * - 断言用户可见中文文本与固定对象（受试者代号、规则编号、行动、证据定位词）。
 * - 与 `user-uat-runbook.md` 的 起始页/对象/目标 对应；不放宽选择器、不替实现打补丁。
 */

import { test, expect } from "@playwright/test";
import {
  collectRuntimeErrors,
  expectNoPageOverflow,
  openRoute,
} from "./helpers";

const runtimeErrorsByPage = new WeakMap<Page, string[]>();

test.describe("14 项任务目标可达性", () => {
  test.beforeEach(async ({ page }) => {
    test.skip((page.viewportSize()?.width ?? 0) < 1000, "桌面项目执行");
    runtimeErrorsByPage.set(page, collectRuntimeErrors(page));
  });

  test.afterEach(async ({ page }) => {
    await page.waitForTimeout(0);
    expect(runtimeErrorsByPage.get(page) ?? []).toEqual([]);
  });

  test("UAT-P1-01：今日工作首屏无登录直达，含对象/风险/下一步入口", async ({
    page,
  }) => {
    await openRoute(page, "/today");
    await expect(page.getByRole("heading", { name: "今日工作", level: 1 })).toBeVisible();
    await expect(page.getByText(/^界面试用：/)).toBeVisible();
    // 对象与审核节点
    await expect(page.getByText("UAT-03").first()).toBeVisible();
    await expect(page.getByText("筛选期").first()).toBeVisible();
    // 风险/缺口与下一步入口
    await expect(page.getByText("阻断", { exact: true }).first()).toBeVisible();
    await expect(page.getByRole("link", { name: /打开.*审核/ }).first()).toBeVisible();
    await expectNoPageOverflow(page);
  });

  test("UAT-P1-02：项目看板顶部有「从方案新建项目」入口并进入确认流程", async ({
    page,
  }) => {
    await openRoute(page, "/board");
    const createLink = page.getByRole("link", { name: "从方案新建项目" });
    await expect(createLink).toBeVisible();
    await createLink.click();
    await expect(page.getByRole("dialog", { name: "确认方案信息" })).toBeVisible();
    await expect(
      page.getByText(/本次试用数据仅用于体验操作/).first(),
    ).toBeVisible();
    await expectNoPageOverflow(page);
  });

  test("UAT-P1-03：方案工作台展示示例草稿规则树与保存草稿入口", async ({
    page,
  }) => {
    await openRoute(page, "/protocols");
    await expect(page.getByRole("heading", { name: "方案工作台" })).toBeVisible();
    await expect(page.getByRole("heading", { name: /首次解构新方案/ })).toBeVisible();
    await page.getByRole("link", { name: /继续审阅示例草稿/ }).click();
    await expect(page.getByRole("heading", { name: "审阅解构草稿" })).toBeVisible();
    await expect(page.getByRole("tree", { name: "方案规则树" })).toContainText("IN-01");
    await expect(page.getByRole("tree", { name: "方案规则树" })).toContainText("EX-01");
    await expect(page.getByRole("button", { name: /IN-01a/ })).toBeVisible();
    await expect(page.getByRole("button", { name: "保存草稿" })).toBeVisible();
    await expectNoPageOverflow(page);
  });

  test("UAT-P1-04：看板可按筛选期筛选并显示阻断程度排序入口", async ({
    page,
  }) => {
    await openRoute(page, "/board?stage=screening");
    await expect(page.getByText(/当前范围：筛选期/)).toBeVisible();
    // 六名筛选期受试者
    await expect(page.getByRole("cell", { name: "UAT-01" }).first()).toBeVisible();
    await expect(page.getByRole("cell", { name: "UAT-06" }).first()).toBeVisible();
    // 排序入口（列头/按钮）
    await expect(page.getByRole("button", { name: /阻断程度/ }).first()).toBeVisible();
    await expectNoPageOverflow(page);
  });

  test("UAT-P1-05：看板直达 UAT-03 筛选期审核并显示阶段与快照", async ({
    page,
  }) => {
    await openRoute(page, "/board?stage=screening");
    await page.getByRole("link", { name: /打开 UAT-03 筛选期审核/ }).click();
    await expect(page.locator(".workbench-episode__subject")).toHaveText("UAT-03");
    await expect(page.locator(".workbench-episode__stage")).toHaveText("筛选期");
    await expect(page.locator(".page-head__note")).toContainText("方案 V1.0");
    await expect(page.locator(".page-head__note")).toContainText(/资料快照第 \d+ 版/);
    await expectNoPageOverflow(page);
  });

  test("UAT-P1-06：受试者资料页首屏风险视图可切换完整明细并返回", async ({
    page,
  }) => {
    await openRoute(page, "/subjects?subject=subject-uat-03-gap_conflict&stage=screening");
    await expect(page.getByRole("heading", { name: /关键事件与风险/ })).toBeVisible();
    await expect(page.getByRole("button", { name: "完整明细" })).toBeVisible();
    await page.getByRole("button", { name: "完整明细" }).click();
    await expect(page.getByRole("heading", { name: /完整明细/ })).toBeVisible();
    await page.getByRole("button", { name: "返回风险视图" }).click();
    await expect(page.getByRole("heading", { name: /关键事件与风险/ })).toBeVisible();
    await expectNoPageOverflow(page);
  });

  test("UAT-P1-07：工作台展开父规则 EX-01、选中子项 EX-01a 并打开证据", async ({
    page,
  }) => {
    await openRoute(
      page,
      "/workbench?episode=episode-uat-03-screening-gap_conflict&component=component-ex-01",
    );
    await expect(
      page.getByRole("button", { name: /EX-01 排除条件，共 1 个子项/ }),
    ).toBeVisible();
    const child = page.getByRole("button", {
      name: /EX-01a 实验室异常与研究者风险的复合条件/,
    });
    await expect(child).toHaveAttribute("aria-current", "true");
    if (await page.locator(".workbench-tabs").isVisible()) {
      await page.getByRole("tab", { name: "证据" }).click();
    }
    await expect(page.getByText("合成筛选资料.pdf").first()).toBeVisible();
    await page.getByRole("button", { name: /打开证据：合成筛选资料/ }).first().click();
    await expect(page.getByRole("dialog", { name: "原始资料证据" })).toBeVisible();
    await expectNoPageOverflow(page);
  });

  test("UAT-P1-08：UAT-02 与 UAT-03 两条证据的定位精度均可见", async ({
    page,
  }) => {
    // UAT-02：页内摘录
    await openRoute(page, "/workbench?episode=episode-uat-02-screening-barrier&component=component-ex-01");
    if (await page.locator(".workbench-tabs").isVisible()) {
      await page.getByRole("tab", { name: "证据" }).click();
    }
    await expect(page.getByText("页内摘录").first()).toBeVisible();
    // UAT-03：仅页码（降级）
    await openRoute(page, "/workbench?episode=episode-uat-03-screening-gap_conflict&component=component-ex-01");
    if (await page.locator(".workbench-tabs").isVisible()) {
      await page.getByRole("tab", { name: "证据" }).click();
    }
    await expect(page.getByText("仅页码").first()).toBeVisible();
    await expectNoPageOverflow(page);
  });

  test("UAT-P1-09：行动中心三类待办均可从界面到达", async ({ page }) => {
    await openRoute(page, "/actions");
    const detail = page.getByRole("complementary", { name: "行动详情" });
    await expect(detail).toBeVisible();
    // 当前节点资料缺口
    await expect(page.getByText(/缺口：记录不完整/).first()).toBeVisible();
    // 需研究者专业判断
    await expect(page.getByText(/缺口：待研究者判断/).first()).toBeVisible();
    // 溯源待办（不阻断）
    await expect(page.getByText(/溯源待办/).first()).toBeVisible();
    await expect(detail.getByText("谁负责")).toBeVisible();
    await expect(detail.getByText("什么资料可以关闭")).toBeVisible();
    await expect(detail.getByText("到期节点")).toBeVisible();
    await expectNoPageOverflow(page);
  });

  test("UAT-P1-10：UAT-03 专业判断行动可到达并允许人工确认", async ({
    page,
  }) => {
    await openRoute(page, "/actions?action=action-uat-03-screening-gap-professional");
    const detail = page.getByRole("complementary", { name: "行动详情" });
    await expect(detail).toContainText("UAT-03");
    await expect(detail.getByText("确认理由（必填）")).toBeVisible();
    await expect(page.getByRole("button", { name: "核对确认内容" })).toBeVisible();
    await expectNoPageOverflow(page);
  });

  test("UAT-P1-11：看板可勾选 UAT-03 与 UAT-04 并打开批量范围确认", async ({
    page,
  }) => {
    await openRoute(page, "/board");
    await page.getByRole("checkbox", { name: "选择 UAT-03" }).check();
    await page.getByRole("checkbox", { name: "选择 UAT-04" }).check();
    await expect(page.getByText(/已选择 2 位受试者/)).toBeVisible();
    await page.getByRole("button", { name: "批量回看审核摘要" }).click();
    const confirm = page.getByRole("dialog", { name: "确认批量操作范围" });
    await expect(confirm).toBeVisible();
    await expect(confirm).toContainText("UAT-03");
    await expect(confirm).toContainText("UAT-04");
    await expectNoPageOverflow(page);
  });

  test("UAT-P1-12：任务页可区分已完成/未处理/失败并继续", async ({ page }) => {
    await openRoute(page, "/tasks");
    await expect(page.getByText(/已整理 \d+ \/ 3 项资料/)).toBeVisible();
    await expect(page.getByText("已完成，继续时不会重复").first()).toBeVisible();
    await expect(page.getByText("上次处理失败，可稍后再试").first()).toBeVisible();
    await page.getByRole("button", { name: "继续" }).click();
    await expect(page.getByRole("button", { name: "完成一项资料" })).toBeVisible();
    await expectNoPageOverflow(page);
  });

  test("UAT-P1-13：窄窗口三区切换（桌面项目验证标签模式入口存在）", async ({
    page,
  }) => {
    await openRoute(
      page,
      "/workbench?episode=episode-uat-03-screening-gap_conflict&component=component-ex-01",
    );
    await expect(page.getByText("UAT-03").first()).toBeVisible();
    await expect(page.getByText("筛选期").first()).toBeVisible();
    // 窄屏降级能力由 narrow.spec.ts 全覆盖；此处只验证三个工作区标识可达
    const tabsVisible = await page.locator(".workbench-tabs").isVisible();
    if (tabsVisible) {
      await expect(page.getByRole("tab", { name: "规则" })).toBeVisible();
      await expect(page.getByRole("tab", { name: "判断" })).toBeVisible();
      await expect(page.getByRole("tab", { name: "证据" })).toBeVisible();
    } else {
      await expect(page.locator(".workbench-pane--tree")).toBeVisible();
      await expect(page.locator(".judgment-pane")).toBeVisible();
      await expect(page.locator(".evidence-pane")).toBeVisible();
    }
    await expectNoPageOverflow(page);
  });

  test("UAT-P1-14：UAT-02 个例风险 → 证据入口可达（缩放由真实浏览器专项覆盖）", async ({
    page,
  }) => {
    await openRoute(page, "/subjects?subject=subject-uat-02-barrier&stage=screening");
    await expect(page.getByText("关键事件与风险")).toBeVisible();
    await expect(
      page.getByRole("link", { name: /查看判断依据/ }).first(),
    ).toBeVisible();
    await expectNoPageOverflow(page);
  });
});
