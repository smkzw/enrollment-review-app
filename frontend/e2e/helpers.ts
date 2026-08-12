/**
 * e2e 共享断言：页面级横向溢出检查（合同 §3.2/§3.3）。
 */

import type { Page } from "@playwright/test";
import { expect } from "@playwright/test";

const baseViewportByPage = new WeakMap<
  Page,
  { width: number; height: number }
>();

/** 页面级无横向滚动：文档宽度不超出视口宽度（组件内滚动不检查）。 */
export async function expectNoPageOverflow(page: Page) {
  const metrics = await page.evaluate(() => {
    const doc = document.documentElement;
    return {
      scrollWidth: doc.scrollWidth,
      clientWidth: doc.clientWidth,
      bodyScrollWidth: document.body.scrollWidth,
    };
  });
  expect(
    metrics.scrollWidth,
    `页面级横向溢出：scrollWidth=${metrics.scrollWidth} clientWidth=${metrics.clientWidth}（body=${metrics.bodyScrollWidth}）`,
  ).toBeLessThanOrEqual(metrics.clientWidth + 1);
}

/** 打开 hash 路由页面 */
export async function openRoute(page: Page, hash: string) {
  await page.goto(`/#${hash}`);
  await page.waitForLoadState("networkidle");
  await expect(page.locator("#main-content h1").first()).toBeVisible();
  await expect(page.getByText("正在整理资料，请稍候", { exact: true })).toHaveCount(0);
}

/**
 * 以布局视口模拟浏览器缩放。1440px 屏幕在 150%/200% 缩放时分别提供
 * 960px/720px CSS 布局宽度，媒体查询行为与真实浏览器缩放一致。
 */
export async function setZoom(page: Page, factor: 1 | 1.5 | 2) {
  let baseViewport = baseViewportByPage.get(page);
  if (baseViewport === undefined) {
    const currentViewport = page.viewportSize();
    if (currentViewport === null) {
      throw new Error("当前浏览器未设置固定视口，无法检查缩放布局");
    }
    baseViewport = currentViewport;
    baseViewportByPage.set(page, baseViewport);
  }
  await page.setViewportSize({
    width: Math.round(baseViewport.width / factor),
    height: Math.round(baseViewport.height / factor),
  });
  await page.evaluate(
    () =>
      new Promise<void>((resolve) => {
        requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
      }),
  );
}
