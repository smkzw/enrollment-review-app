/**
 * 界面试用复位往返（worker_03 / 成功条件 3、6）。
 * - 取消复位不改变任何状态；确认复位只删除登记在册的四个键，保留无关键，并回到今日工作。
 * - 在四个页面分别制造“已修改”会话状态，经帮助页复位后逐页核对回到初始状态：
 *   新建项目、方案草稿、人工操作与任务状态均复位。
 * - 直接从中央清单导入键名与版本号，不复制键名字符串，防止测试与实现漂移。
 */

import { test, expect } from "@playwright/test";
import {
  UAT_PAGE_VERSION,
  UAT_KEY_MANUAL_ACTIONS,
  UAT_KEY_CREATED_PROJECT,
  UAT_KEY_PROTOCOL_DRAFT_SAVED,
  UAT_KEY_TASK_PROGRESS,
} from "../src/app/uatTrialState";
import {
  collectRuntimeErrors,
  expectNoPageOverflow,
  openRoute,
} from "./helpers";

const runtimeErrorsByPage = new WeakMap<Page, string[]>();

const REGISTERED_KEYS = [
  UAT_KEY_MANUAL_ACTIONS,
  UAT_KEY_CREATED_PROJECT,
  UAT_KEY_PROTOCOL_DRAFT_SAVED,
  UAT_KEY_TASK_PROGRESS,
];

function sessionDump(page: Page): Promise<Record<string, string | null>> {
  return page.evaluate(() => {
    const all: Record<string, string | null> = {};
    for (let index = 0; index < window.sessionStorage.length; index += 1) {
      const key = window.sessionStorage.key(index);
      if (key !== null) all[key] = window.sessionStorage.getItem(key);
    }
    return all;
  });
}

test.describe("界面试用复位往返", () => {
  test.beforeEach(async ({ page }) => {
    test.skip((page.viewportSize()?.width ?? 0) < 1000, "桌面项目执行");
    runtimeErrorsByPage.set(page, collectRuntimeErrors(page));
    // 先加载应用页面（sessionStorage 只在应用源可用），再清空会话状态
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await page.evaluate(() => window.sessionStorage.clear());
  });

  test.afterEach(async ({ page }) => {
    await page.waitForTimeout(0);
    expect(runtimeErrorsByPage.get(page) ?? []).toEqual([]);
  });

  test("首次点击只打开确认界面，不改变任何状态", async ({ page }) => {
    await page.evaluate((keys) => {
      for (const key of keys) window.sessionStorage.setItem(key, "x");
      window.sessionStorage.setItem("unrelated:preference", "keep");
    }, REGISTERED_KEYS);
    await openRoute(page, "/help");
    await page.getByRole("button", { name: "开始新的界面试用" }).click();
    const dialog = page.getByRole("dialog", { name: "开始新的界面试用" });
    await expect(dialog).toBeVisible();
    await expect(dialog).toContainText(UAT_PAGE_VERSION);
    const after = await sessionDump(page);
    for (const key of REGISTERED_KEYS) {
      expect(after[key] ?? null, `首次点击不应改变 ${key}`).toBe("x");
    }
    expect(after["unrelated:preference"]).toBe("keep");
    await expect(page).toHaveURL(/\/help$/);
  });

  test("取消复位不改变任何状态，也不离开帮助页", async ({ page }) => {
    await page.evaluate((keys) => {
      for (const key of keys) window.sessionStorage.setItem(key, "y");
      window.sessionStorage.setItem("unrelated:preference", "keep");
    }, REGISTERED_KEYS);
    await openRoute(page, "/help");
    await page.getByRole("button", { name: "开始新的界面试用" }).click();
    await page.getByRole("button", { name: "先不要" }).click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    const after = await sessionDump(page);
    for (const key of REGISTERED_KEYS) {
      expect(after[key] ?? null, `取消不应改变 ${key}`).toBe("y");
    }
    expect(after["unrelated:preference"]).toBe("keep");
    await expect(page).toHaveURL(/\/help$/);
  });

  test("Escape 取消复位同样不改变状态", async ({ page }) => {
    await page.evaluate((keys) => {
      for (const key of keys) window.sessionStorage.setItem(key, "z");
    }, REGISTERED_KEYS);
    await openRoute(page, "/help");
    await page.getByRole("button", { name: "开始新的界面试用" }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toHaveCount(0);
    const after = await sessionDump(page);
    for (const key of REGISTERED_KEYS) {
      expect(after[key] ?? null).toBe("z");
    }
    await expect(page).toHaveURL(/\/help$/);
  });

  test("确认复位只删除登记键，保留无关键，并回到今日工作", async ({ page }) => {
    await page.evaluate((keys) => {
      for (const key of keys) window.sessionStorage.setItem(key, "x");
      window.sessionStorage.setItem("unrelated:preference", "keep");
      window.sessionStorage.setItem("eligibility-review:other", "keep2");
      window.sessionStorage.setItem("plain-key", "keep3");
    }, REGISTERED_KEYS);
    await openRoute(page, "/help");
    await page.getByRole("button", { name: "开始新的界面试用" }).click();
    await page.getByRole("button", { name: "确认并回到今日工作" }).click();
    await expect(page).toHaveURL(/\/today$/);
    await expect(page.getByRole("heading", { name: "今日工作", level: 1 })).toBeVisible();
    const after = await sessionDump(page);
    for (const key of REGISTERED_KEYS) {
      expect(
        after[key] ?? null,
        `确认后应删除登记键 ${key}`,
      ).toBeNull();
    }
    expect(after["unrelated:preference"]).toBe("keep");
    expect(after["eligibility-review:other"]).toBe("keep2");
    expect(after["plain-key"]).toBe("keep3");
    await expectNoPageOverflow(page);
  });

  test("复位后回到今日工作，四个登记状态均已恢复初始", async ({ page }) => {
    // 1) 行动中心：专业判断行动已人工确认关闭
    await openRoute(page, "/actions?action=action-uat-03-screening-gap-professional");
    await page.getByLabel("确认理由（必填）").fill("已核对书面判断并签名。");
    await page.getByRole("button", { name: "核对确认内容" }).click();
    await page.getByRole("button", { name: "确认关闭并重新核对" }).click();
    await expect(page.getByText("人工操作记录（本次试用）")).toBeVisible();
    await expect(page.getByText("本次确认前后差异")).toBeVisible();

    // 2) 新建项目：从方案创建并进入筛选期
    await openRoute(page, "/board");
    await page.getByRole("link", { name: "从方案新建项目" }).click();
    await page.getByRole("dialog", { name: "确认方案信息" }).getByRole("button", { name: "确认方案并继续" }).click();
    await page.getByRole("button", { name: "确认研究期别并继续" }).click();
    await page.getByRole("radio", { name: /筛选期/ }).check();
    await page.getByRole("button", { name: "创建项目并进入筛选期" }).click();
    await expect(page.getByRole("heading", { name: "项目已建立" })).toBeVisible();

    // 3) 方案工作台：保存草稿
    await openRoute(page, "/protocols");
    await page.getByRole("button", { name: "保存为草稿" }).click();
    await expect(page.getByRole("status")).toContainText("已保存为草稿");

    // 4) 任务页：完成一项资料
    await openRoute(page, "/tasks");
    await page.getByRole("button", { name: "继续" }).click();
    await page.getByRole("button", { name: "完成一项资料" }).click();
    await expect(page.getByText(/已整理 2 \/ 3 项资料/)).toBeVisible();

    // 复位前：四个键均存在
    const before = await sessionDump(page);
    for (const key of REGISTERED_KEYS) {
      expect(before[key] ?? null, `复位前 ${key} 应存在`).not.toBeNull();
    }

    // 经帮助页复位
    await openRoute(page, "/help");
    await page.getByRole("button", { name: "开始新的界面试用" }).click();
    await page.getByRole("button", { name: "确认并回到今日工作" }).click();
    await expect(page).toHaveURL(/\/today$/);

    // 复位后：任务页回到初始 1/3
    await openRoute(page, "/tasks");
    await expect(page.getByText(/已整理 1 \/ 3 项资料/)).toBeVisible();
    await expect(page.getByText("已完成，继续时不会重复").first()).toBeVisible();
    await expect(page.getByText("上次处理失败，可稍后再试").first()).toBeVisible();

    // 方案工作台回到未保存草稿
    await openRoute(page, "/protocols");
    await expect(page.getByRole("button", { name: "保存为草稿" })).toBeVisible();
    await expect(page.getByRole("status")).toHaveCount(0);

    // 新建项目回到“从方案确认”对话框
    await openRoute(page, "/projects/new");
    await expect(page.getByRole("dialog", { name: "确认方案信息" })).toBeVisible();

    // 行动中心回到未确认状态
    await openRoute(page, "/actions?action=action-uat-03-screening-gap-professional");
    await expect(page.getByText("人工操作记录（本次试用）")).toHaveCount(0);
    await expect(page.getByLabel("确认理由（必填）")).toBeVisible();
  });
});
