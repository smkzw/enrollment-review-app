/**
 * Phase 5.6 宽屏 Patient Profile 与原文证据面板（worker_03）。
 * 真实浏览器 + 干净合成 V2 数据（路由拦截 /api/v2/**）：在 1080P、2K、4K
 * 三个最大化桌面视口各执行一次，验证：
 * - 流体三栏/详情布局在展开证据面板时不产生页面级横向滚动；
 * - 首屏只展示后端 highlights，"全部历时信息"展开 13 条泳道；
 * - 只有真实 bbox 定位画出唯一单框，页内摘录/仅页码定位不画框；
 * - 定位详情与原件滚动联动，无运行时错误；
 * - 不出现 Phase 6/7 入排结论、行动数、负责方或通过/不通过语言。
 */

import { expect, test } from "@playwright/test";
import {
  collectRuntimeErrors,
  expectNoPageOverflow,
} from "./helpers";
import {
  PROFILE_HASH,
  registerProfileRoutes,
} from "./profile-evidence-fixtures";

test("宽屏 Profile 证据面板：三栏无溢出、单真实 bbox、无入排结论", async ({ page }) => {
  const runtimeErrors = collectRuntimeErrors(page);
  await registerProfileRoutes(page);

  await page.goto(`/${PROFILE_HASH}`);
  await expect(
    page.getByRole("heading", { name: "受试者与资料", level: 1 }),
  ).toBeVisible();
  // 首屏只展示 highlights 首屏重点，不展开全部泳道。
  await expect(page.getByRole("heading", { name: /首屏重点/ })).toBeVisible();
  await expect(page.getByRole("button", { name: "全部历时信息" })).toBeVisible();
  await expectNoPageOverflow(page);

  // 展开全部历时信息，13 条泳道按稳定顺序出现。
  await page.getByRole("button", { name: "全部历时信息" }).click();
  await expect(page.getByRole("button", { name: "返回首屏" })).toBeVisible();
  await expect(page.getByRole("heading", { name: /人口学\/基线/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: /证据冲突与资料质量/ })).toBeVisible();
  await expectNoPageOverflow(page);

  // 点击有真实 bbox 定位的条目的“查看原文”，打开证据面板。
  await page
    .getByRole("button", { name: /查看.基线血压 120\/80 mmHg.的原文证据/ })
    .click();
  const panel = page.getByLabel("该条目的原文证据与定位");
  await expect(panel).toBeVisible();
  await expect(panel.getByText("筛选病历.pdf")).toBeVisible();
  await expect(panel.getByText("2 页连续查看")).toBeVisible();

  const sourceImage = panel.getByRole("img", { name: "第 1 页原始资料" });
  await expect(sourceImage).toBeVisible();
  await expect
    .poll(() =>
      sourceImage.evaluate(
        (element) => element instanceof HTMLImageElement && element.complete && element.naturalWidth > 0,
      ),
    )
    .toBe(true);

  // 只有真实 bbox 定位画出唯一单框，且没有合成坐标文本。
  const boxes = page.getByLabel(/^重点标注/);
  await expect(boxes).toHaveCount(1);
  await expect(boxes.first()).toHaveClass(/original-evidence-page__box--selected/);
  const placement = await boxes.first().evaluate((box) => {
    const image = box.parentElement?.querySelector("img");
    if (!(image instanceof HTMLImageElement)) return null;
    const boxRect = box.getBoundingClientRect();
    const imageRect = image.getBoundingClientRect();
    return {
      centerX: (boxRect.left + boxRect.width / 2 - imageRect.left) / imageRect.width,
      centerY: (boxRect.top + boxRect.height / 2 - imageRect.top) / imageRect.height,
    };
  });
  expect(placement).not.toBeNull();
  expect(placement?.centerX).toBeGreaterThan(0.1);
  expect(placement?.centerX).toBeLessThan(0.35);
  expect(placement?.centerY).toBeGreaterThan(0.24);
  expect(placement?.centerY).toBeLessThan(0.32);
  const panelText = await panel.innerText();
  expect(panelText).not.toMatch(/x0|y0|x1|y1/);

  // 三栏布局：受试者列表、Profile、证据面板并存且无页面级横向滚动。
  await expect(page.getByLabel("受试者列表")).toBeVisible();
  await expectNoPageOverflow(page);
  expect(runtimeErrors).toEqual([]);

  // 键盘关闭后恢复两栏布局，并把焦点送回触发按钮。
  const closeButton = page.getByRole("button", { name: "关闭原文证据" });
  await closeButton.focus();
  await page.keyboard.press("Enter");
  await expect(panel).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: /查看.基线血压 120\/80 mmHg.的原文证据/ }),
  ).toBeFocused();
  await expectNoPageOverflow(page);
});

test("宽屏 Profile 证据面板：仅页码定位不画框，诚实说明定位能力", async ({ page }) => {
  const runtimeErrors = collectRuntimeErrors(page);
  await registerProfileRoutes(page);

  await page.goto(`/${PROFILE_HASH}`);
  await expect(
    page.getByRole("heading", { name: "受试者与资料", level: 1 }),
  ).toBeVisible();

  // 展开全部历时信息，选择用药暴露条目（仅页码定位）。
  await page.getByRole("button", { name: "全部历时信息" }).click();
  await expect(page.getByRole("heading", { name: /药物暴露/ })).toBeVisible();
  await page.getByRole("button", { name: /查看.阿司匹林.的原文证据/ }).click();
  const panel = page.getByLabel("该条目的原文证据与定位");
  await expect(panel).toBeVisible();
  // 仅页码定位仍可打开所在页，但不画任何框。
  await expect(panel.getByText(/只能确定到所在页/)).toBeVisible();
  await expect(panel.getByRole("button", { name: "当前页" })).toBeVisible();
  const sourceImage = panel.getByRole("img", { name: "第 1 页原始资料" });
  await expect
    .poll(() =>
      sourceImage.evaluate(
        (element) => element instanceof HTMLImageElement && element.complete && element.naturalWidth > 0,
      ),
    )
    .toBe(true);
  await expect(page.getByLabel(/^重点标注/)).toHaveCount(0);
  await expectNoPageOverflow(page);
  expect(runtimeErrors).toEqual([]);

  // 全文不含入排结论/通过/不通过语言。
  const pageText = await page.locator("#main-content").innerText();
  expect(pageText).not.toMatch(/入排结论|行动数量|负责方|通过|不通过/);
});
