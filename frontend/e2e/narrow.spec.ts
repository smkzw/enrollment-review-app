/**
 * 窄屏验收（合同 §3.3 窄屏样本）：菜单抽屉、工作台标签切换、资料页堆叠，
 * 页面级无横向滚动，当前选择跨标签切换保持。
 */

import { test, expect, type Page } from "@playwright/test";
import { expectNoPageOverflow, openRoute } from "./helpers";
import { UAT_PAGE_VERSION, UAT_TRIAL_STATE_KEYS } from "../src/app/uatTrialState";

/** 会话存储全量导出：复位边界断言直接引用中央清单，不在测试中复制存储键。 */
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

test.describe("窄屏（390px）", () => {
  test.skip(({ viewport }) => viewport?.width !== 390, "仅窄屏项目执行");

  test("侧栏为抽屉：菜单按钮打开，Escape 关闭", async ({ page }) => {
    await openRoute(page, "/today");
    const menu = page.getByRole("button", { name: "打开菜单" });
    await expect(menu).toBeVisible();
    await menu.click();
    await expect(page.getByRole("link", { name: "项目看板" })).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(menu).toHaveAttribute("aria-expanded", "false");
    await expect(page.locator(".side-nav__scrim")).toHaveCount(0);
    await expectNoPageOverflow(page);
  });

  test("入排工作台通过标签切换规则/判断/证据，选择保持", async ({ page }) => {
    await openRoute(
      page,
      "/workbench?episode=episode-uat-03-screening-gap_conflict&component=component-ex-01",
    );
    // 默认规则标签
    await expect(page.locator(".workbench-col--rules")).toBeVisible();
    // 风险深链已展开 EX-01 并选中 EX-01a。
    await expect(page
      .getByRole("button", { name: /EX-01a 实验室异常与研究者风险的复合条件/ })
    ).toHaveAttribute("aria-current", "true");
    // 切到证据标签
    await page.getByRole("tab", { name: "证据" }).click();
    await expect(page.locator(".workbench-col--evidence")).toBeVisible();
    await expect(page.getByLabel("定位精度说明")).toBeVisible();
    // 回到规则标签，选中仍为 EX-01a
    await page.getByRole("tab", { name: "规则" }).click();
    await expect(
      page.getByRole("button", { name: /EX-01a 实验室异常与研究者风险的复合条件/ }),
    ).toHaveAttribute("aria-current", "true");
    await expectNoPageOverflow(page);
  });

  test("受试者与资料页：紧凑选择器可切换，Profile 无横向滚动", async ({ page }) => {
    await openRoute(page, "/subjects");
    const picker = page.getByLabel("受试者", { exact: true });
    await expect(picker).toBeVisible();
    await picker.selectOption("subject-uat-03-gap_conflict");
    await expect(page.getByRole("heading", { name: "UAT-03" })).toBeVisible();
    await expect(page.getByText("应备证据覆盖")).toBeVisible();
    await expectNoPageOverflow(page);
  });

  test("窄屏受试者页：紧凑选择器首屏可见，Profile 无需滚过完整列表", async ({
    page,
  }) => {
    await openRoute(page, "/subjects");
    // 完整列表收起，紧凑下拉可见
    await expect(page.locator(".subjects-list")).toBeHidden();
    const picker = page.getByLabel("受试者", { exact: true });
    await expect(picker).toBeVisible();
    // Profile 首屏可见（顶缘在视口内）
    const profileTop = await page
      .locator(".profile")
      .evaluate((el) => el.getBoundingClientRect().top);
    expect(profileTop).toBeLessThan(844);
    // 切换受试者 → Profile 更新
    await picker.selectOption("subject-uat-03-gap_conflict");
    await expect(page.getByRole("heading", { name: "UAT-03" })).toBeVisible();
    await expectNoPageOverflow(page);
  });

  test("窄屏顶栏：标题单行可读、无原始项目代号、上下文隐藏、帮助为图标", async ({
    page,
  }) => {
    await openRoute(page, "/today");
    // 标题单行（不换行、不裁切）
    const titleHeight = await page
      .locator(".topbar__position strong")
      .evaluate((el) => el.getBoundingClientRect().height);
    expect(titleHeight).toBeLessThan(32);
    // 项目/方案上下文移出窄屏顶栏
    await expect(page.locator(".topbar__context")).toBeHidden();
    // 不暴露原始项目代号
    await expect(page.getByText("SYNTHETIC")).toHaveCount(0);
    await expect(page.getByText("SYNTHETIC-001-III")).toHaveCount(0);
    // 帮助仍为紧凑图标入口（中文可访问名）
    await expect(
      page.getByRole("link", { name: "打开系统帮助" }),
    ).toBeVisible();
    await expectNoPageOverflow(page);
  });

  test("窄屏行动中心：摘要与状态徽标不重叠", async ({ page }) => {
    await openRoute(page, "/actions");
    const hasOverlap = await page
      .locator(".action-row")
      .first()
      .evaluate((row) => {
        const els = Array.from(
          row.querySelectorAll<HTMLElement>(
            ".action-row__main, .action-row__state, .status-badge",
          ),
        );
        const rects = els.map((el) => el.getBoundingClientRect());
        for (let i = 0; i < rects.length; i++) {
          for (let j = i + 1; j < rects.length; j++) {
            const a = rects[i];
            const b = rects[j];
            if (
              a.width > 0 &&
              b.width > 0 &&
              a.right > b.left + 1 &&
              a.left < b.right - 1 &&
              a.bottom > b.top + 1 &&
              a.top < b.bottom - 1
            ) {
              return true;
            }
          }
        }
        return false;
      });
    expect(hasOverlap).toBe(false);
    await expectNoPageOverflow(page);
  });

  test("行动中心与任务页在窄屏可操作", async ({ page }) => {
    await openRoute(page, "/actions");
    await expect(page.getByRole("heading", { name: "行动中心" })).toBeVisible();
    await expectNoPageOverflow(page);
    await openRoute(page, "/tasks");
    await expect(page.getByRole("heading", { name: "任务与系统" })).toBeVisible();
    await expectNoPageOverflow(page);
  });

  test("帮助页复位：滚动到入口并取消，状态不变且焦点回到触发按钮", async ({
    page,
  }) => {
    // 先加载应用源（sessionStorage 按源生效），再注入登记键与无关键
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await page.evaluate(() => window.sessionStorage.clear());
    await page.evaluate((keys) => {
      for (const key of keys) window.sessionStorage.setItem(key, "narrow-x");
      window.sessionStorage.setItem("unrelated:preference", "keep");
    }, UAT_TRIAL_STATE_KEYS);

    await openRoute(page, "/help");
    const trigger = page.getByRole("button", { name: "开始新的界面试用" });
    await trigger.scrollIntoViewIfNeeded();
    await trigger.click();
    const dialog = page.getByRole("dialog", { name: "开始新的界面试用" });
    await expect(dialog).toBeVisible();
    await expect(dialog).toContainText(UAT_PAGE_VERSION);
    await expectNoPageOverflow(page);

    await page.getByRole("button", { name: "先不要" }).click();
    await expect(dialog).toHaveCount(0);
    // 取消后登记键与无关键均不变
    const after = await sessionDump(page);
    for (const key of UAT_TRIAL_STATE_KEYS) {
      expect(after[key] ?? null, `取消不应改变 ${key}`).toBe("narrow-x");
    }
    expect(after["unrelated:preference"]).toBe("keep");
    // 焦点回到触发按钮，且未离开帮助页
    await expect(trigger).toBeFocused();
    await expect(page).toHaveURL(/\/help$/);
    await expectNoPageOverflow(page);
  });

  test("帮助页复位：确认只清除登记键、保留无关键并返回今日工作，无横向溢出", async ({
    page,
  }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await page.evaluate(() => window.sessionStorage.clear());
    await page.evaluate((keys) => {
      for (const key of keys) window.sessionStorage.setItem(key, "narrow-y");
      window.sessionStorage.setItem("unrelated:preference", "keep");
      window.sessionStorage.setItem("eligibility-review:other", "keep2");
      window.sessionStorage.setItem("plain-key", "keep3");
    }, UAT_TRIAL_STATE_KEYS);

    await openRoute(page, "/help");
    const trigger = page.getByRole("button", { name: "开始新的界面试用" });
    await trigger.scrollIntoViewIfNeeded();
    await trigger.click();
    await expect(
      page.getByRole("dialog", { name: "开始新的界面试用" }),
    ).toBeVisible();
    // 确认界面自身无页面级横向溢出
    await expectNoPageOverflow(page);

    await page.getByRole("button", { name: "确认并回到今日工作" }).click();
    await expect(page).toHaveURL(/\/today$/);
    await expect(
      page.getByRole("heading", { name: "今日工作", level: 1 }),
    ).toBeVisible();

    // 状态边界：只删除登记在册的键，其余会话数据保留
    const after = await sessionDump(page);
    for (const key of UAT_TRIAL_STATE_KEYS) {
      expect(after[key] ?? null, `确认后应删除登记键 ${key}`).toBeNull();
    }
    expect(after["unrelated:preference"]).toBe("keep");
    expect(after["eligibility-review:other"]).toBe("keep2");
    expect(after["plain-key"]).toBe("keep3");
    // 返回的今日工作页无横向溢出
    await expectNoPageOverflow(page);
  });
});
