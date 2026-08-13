/**
 * Phase 1.5 构建者预试：覆盖正式 UAT 中容易被静态页面误判为“已实现”的交互闭环。
 * 正式用户完成率、用时和主观负担仍必须由真实用户记录。
 */

import type { Page } from "@playwright/test";
import { test, expect } from "@playwright/test";
import {
  collectRuntimeErrors,
  expectNoPageOverflow,
  openRoute,
  setLayoutStressFactor,
} from "./helpers";

const runtimeErrorsByPage = new WeakMap<Page, string[]>();

test.describe("Phase 1.5 交互预试", () => {
  test.beforeEach(async ({ page }) => {
    test.skip((page.viewportSize()?.width ?? 0) < 1000, "交互预试在桌面项目执行");
    runtimeErrorsByPage.set(page, collectRuntimeErrors(page));
  });

  test.afterEach(async ({ page }) => {
    await page.waitForTimeout(0);
    expect(runtimeErrorsByPage.get(page) ?? []).toEqual([]);
  });

  test("UAT-P1-05：从筛选范围直达审核并返回后保留筛选与排序", async ({ page }) => {
    await openRoute(page, "/board?stage=screening&status=gap&sort=blocking");
    await page.getByRole("link", { name: "打开 UAT-03 筛选期审核" }).click();
    await expect(page.locator(".workbench-episode__subject")).toHaveText("UAT-03");
    await expect(page.locator(".workbench-episode__stage")).toHaveText("筛选期");
    await page.goBack();
    await expect(page).toHaveURL(/stage=screening/);
    await expect(page).toHaveURL(/status=gap/);
    await expect(page).toHaveURL(/sort=blocking/);
    await expect(page.getByText(/当前范围：筛选期/)).toBeVisible();
  });

  test("UAT-P1-06：个例首屏风险优先，完整资料与未提及/明确否认不混淆", async ({ page }) => {
    await openRoute(page, "/subjects?subject=subject-uat-03-gap_conflict&stage=screening");
    await expect(page.getByRole("heading", { name: /关键事件与风险/ })).toBeVisible();
    await expect(page.getByRole("heading", { name: "完整明细" })).toHaveCount(0);
    await page.getByRole("button", { name: "完整明细" }).click();
    await expect(page.getByRole("heading", { name: /完整明细/ })).toBeVisible();
    await expect(page.getByText(/未记录按资料缺口处理，不等于“正常”或“否认”/).first()).toBeVisible();
    await page.getByRole("button", { name: "返回风险视图" }).click();
    await expect(page.getByRole("heading", { name: /关键事件与风险/ })).toBeVisible();
    await expect(page.getByText(/当前资料缺少记录，不等于明确否认/).first()).toBeVisible();
  });

  test("UAT-P1-07：父子层级和全部满足逻辑可辨，三步内到原始证据", async ({ page }) => {
    await openRoute(page, "/workbench?episode=episode-uat-03-screening-gap_conflict&component=component-ex-01");
    await expect(page.getByRole("button", { name: /EX-01 排除条件，共 1 个子项/ })).toBeVisible();
    const child = page.getByRole("button", { name: /EX-01a 实验室异常与研究者风险的复合条件/ });
    await expect(child).toHaveAttribute("aria-current", "true");
    if (await page.locator(".workbench-tabs").isVisible()) {
      await page.getByRole("tab", { name: "判断" }).click();
    }
    await expect(page.getByText(/全部满足/).first()).toBeVisible();
    if (await page.locator(".workbench-tabs").isVisible()) {
      await page.getByRole("tab", { name: "证据" }).click();
    }
    await expect(page.getByText("合成筛选资料.pdf").first()).toBeVisible();
    await expect(page.getByText("仅页码").first()).toBeVisible();
    await page.getByRole("button", { name: /打开证据：合成筛选资料/ }).first().click();
    await expect(page.getByRole("dialog", { name: "原始资料证据" })).toContainText("第 4 页");
  });

  test("UAT-P1-08：页内摘录与仅页码均诚实显示实际定位能力", async ({ page }) => {
    await openRoute(page, "/workbench?episode=episode-uat-02-screening-barrier&component=component-ex-01");
    if (await page.locator(".workbench-tabs").isVisible()) {
      await page.getByRole("tab", { name: "证据" }).click();
    }
    await expect(page.getByText("页内摘录").first()).toBeVisible();
    await page.getByRole("button", { name: /打开证据/ }).first().click();
    let dialog = page.getByRole("dialog", { name: "原始资料证据" });
    await expect(dialog).toContainText("可定位到页内摘录区域");
    await page.getByRole("button", { name: "关闭证据" }).click();

    await openRoute(page, "/workbench?episode=episode-uat-03-screening-gap_conflict&component=component-ex-01");
    if (await page.locator(".workbench-tabs").isVisible()) {
      await page.getByRole("tab", { name: "证据" }).click();
    }
    await expect(page.getByText("仅页码").first()).toBeVisible();
    await page.getByRole("button", { name: /打开证据/ }).first().click();
    dialog = page.getByRole("dialog", { name: "原始资料证据" });
    await expect(dialog).toContainText("只能确定到整页");
    await expect(dialog).toContainText("扫描页无法稳定定位字符或坐标");
  });

  test("UAT-P1-10：人工确认先核对范围，追加记录且不把规则直接改为通过", async ({ page }) => {
    await openRoute(page, "/actions?action=action-uat-03-screening-gap-professional");
    await page.getByLabel("确认理由（必填）").fill("研究者已补充书面判断，并完成签名和日期。");
    await page.getByRole("button", { name: "核对确认内容" }).click();
    const confirm = page.getByRole("dialog", { name: "确认本次人工处理" });
    await expect(confirm).toContainText("关闭行动不等于规则通过");
    await expect(confirm).toContainText("研究者已补充书面判断");
    await page.getByRole("button", { name: "确认关闭并重新核对" }).click();
    await expect(page.getByText("本次确认前后差异")).toBeVisible();
    await expect(page.getByText(/不等于规则自动通过/)).toBeVisible();
    await page.getByRole("button", { name: "重新打开", exact: true }).click();
    const record = page.getByRole("heading", { name: /人工操作记录/ }).locator("..");
    await expect(record).toContainText("确认关闭");
    await expect(record).toContainText("重新打开");
  });

  test("UAT-P1-09：当前缺口、专业判断与溯源待办分别给出责任和关闭条件", async ({ page }) => {
    const cases = [
      {
        id: "action-uat-03-screening-gap-age",
        responsible: "研究者方",
        due: "筛选期",
        evidence: "可定位、具日期且能够回答本条要求的完整病历记录。",
        blocking: "阻断当前节点",
      },
      {
        id: "action-uat-03-screening-gap-professional",
        responsible: "研究者方",
        due: "筛选期",
        evidence: "具名、具日期并直接关联本条要求的研究者判断。",
        blocking: "阻断当前节点",
      },
      {
        id: "action-uat-01-screening-clear-provenance",
        responsible: "CRA",
        due: "筛选期",
        evidence: "原始来源，或具名、具日期的溯源核对记录。",
        blocking: "不阻断",
      },
    ] as const;

    for (const item of cases) {
      await openRoute(page, `/actions?action=${item.id}`);
      const detail = page.locator(".action-detail");
      await expect(detail).toContainText(`谁负责${item.responsible}`);
      await expect(detail).toContainText(`什么资料可以关闭${item.evidence}`);
      await expect(detail).toContainText(`到期节点${item.due}`);
      await expect(detail).toContainText(item.blocking);
    }
  });

  test("UAT-P1-11：批量范围只含两位，排序后不扩大", async ({ page }) => {
    await openRoute(page, "/board");
    await page.getByRole("checkbox", { name: "选择 UAT-03" }).check();
    await page.getByRole("checkbox", { name: "选择 UAT-04" }).check();
    await page.getByRole("button", { name: "批量回看审核摘要" }).click();
    const confirm = page.getByRole("dialog", { name: "确认批量操作范围" });
    await expect(confirm).toContainText("UAT-03");
    await expect(confirm).toContainText("UAT-04");
    await expect(confirm).not.toContainText("UAT-01");
    await page.getByRole("button", { name: "确认回看" }).click();
    const result = page.getByText("批量操作完成").locator("..");
    await expect(result).toContainText("UAT-03、UAT-04");
    await page.getByRole("button", { name: "阻断程度" }).click();
    await expect(page.getByText("已选择 2 位受试者（只处理明确勾选对象）")).toBeVisible();
  });

  test("UAT-P1-12：离开页面再进入后继续进度，不重复已完成资料", async ({ page }) => {
    await openRoute(page, "/tasks");
    await expect(page.getByText("已完成，继续时不会重复")).toBeVisible();
    await page.getByRole("button", { name: "继续" }).click();
    await page.getByRole("button", { name: "完成一项资料" }).click();
    const files = page.getByRole("list", { name: "资料处理范围" });
    await expect(files.getByText("实验室检查.pdf").locator("..")).toContainText("已完成，继续时不会重复");
    await expect(files.getByText("既往用药记录.pdf").locator("..")).toContainText("上次处理失败，可稍后再试");
    await openRoute(page, "/today");
    await openRoute(page, "/tasks");
    await expect(page.getByText("已整理 2 / 3 项资料")).toBeVisible();
    await expect(page.getByText("正在整理资料")).toBeVisible();
    const restoredFiles = page.getByRole("list", { name: "资料处理范围" });
    await expect(restoredFiles.getByText("筛选病历.pdf").locator("..")).toContainText("已完成，继续时不会重复");
    await expect(restoredFiles.getByText("实验室检查.pdf").locator("..")).toContainText("已完成，继续时不会重复");
    await expect(restoredFiles.getByText("既往用药记录.pdf").locator("..")).toContainText("上次处理失败，可稍后再试");
  });

  test("UAT-P1-14 自动化补充：三档布局压力均可完成 Profile、规则和证据路径", async ({ page }) => {
    test.skip(page.viewportSize()?.width !== 1440, "仅 1440 项目执行三档布局压力检查");
    for (const factor of [1, 1.5, 2] as const) {
      await setLayoutStressFactor(page, factor);
      await openRoute(page, "/subjects?subject=subject-uat-02-barrier&stage=screening");
      await expect(page.getByText("关键事件与风险")).toBeVisible();
      const evidenceLink = page.getByRole("link", { name: /打开证据/ }).first();
      await evidenceLink.click();
      if (await page.locator(".workbench-tabs").isVisible()) {
        await page.getByRole("tab", { name: "证据" }).click();
      }
      await expect(page.getByText("页内摘录").first()).toBeVisible();
      await page.getByRole("button", { name: /打开证据/ }).first().click();
      await expect(page.getByRole("dialog", { name: "原始资料证据" })).toBeVisible();
      await page.getByRole("button", { name: "关闭证据" }).click();
      await expectNoPageOverflow(page);
    }
  });
});
