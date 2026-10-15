import { expect, test } from "@playwright/test";
import { collectRuntimeErrors, expectNoPageOverflow } from "./helpers";

const baseUrl = process.env.EVIDENCE_LIVE_BASE_URL;
const subjectId = process.env.EVIDENCE_LIVE_SUBJECT_ID;
const episodeId = process.env.EVIDENCE_LIVE_EPISODE_ID;
const enabled = [baseUrl, subjectId, episodeId].every(Boolean);

test.skip(!enabled, "仅在显式提供已启用的清洁真实后端时运行。");

test("已启用资料在宽屏中保持原文、原件与真实红框对应", async ({
  page,
}, testInfo) => {
  const runtimeErrors = collectRuntimeErrors(page);
  await page.goto(
    `${baseUrl}/#/subjects/${subjectId}/evidence?episode=${episodeId}`,
  );

  await expect(page.getByLabel("当前资料上下文")).toContainText("当前有效");
  await expect(
    page.getByRole("heading", { name: "原始识别 / 校对后文本" }),
  ).toBeVisible();
  await expect(page.getByText("当前有效资料可在下方查看。")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "补充或重建资料" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "需要修订识别文字" }),
  ).toBeVisible();
  await expect(
    page.getByRole("textbox", { name: "校对后文本" }),
  ).toHaveCount(0);
  await expect(page.getByText(/资料状态：待发布/)).toHaveCount(0);
  const image = page.getByAltText("第 1 页原始资料");
  await expect(image).toBeVisible();
  await expect(page.getByLabel(/^重点标注/)).toHaveCount(0);

  await page
    .getByRole("button", { name: /查看 \d+ 处原件定位/ })
    .click();
  await page.getByRole("button", { name: "在原件中查看" }).first().click();
  await expect(
    page.locator(".original-evidence-page__box--selected"),
  ).toHaveCount(1);

  const geometry = await page.evaluate(() => {
    const source = document.querySelector<HTMLImageElement>(
      'img[alt="第 1 页原始资料"]',
    );
    const highlights = Array.from(
      document.querySelectorAll<HTMLElement>(
        '[aria-label^="重点标注"]',
      ),
    );
    if (source === null || highlights.length === 0) return null;
    const imageRect = source.getBoundingClientRect();
    return {
      imageWidth: imageRect.width,
      imageHeight: imageRect.height,
      count: highlights.length,
      allInside: highlights.every((highlight) => {
        const box = highlight.getBoundingClientRect();
        const tolerance = 1;
        return (
          box.left >= imageRect.left - tolerance &&
          box.top >= imageRect.top - tolerance &&
          box.right <= imageRect.right + tolerance &&
          box.bottom <= imageRect.bottom + tolerance
        );
      }),
    };
  });
  expect(geometry).not.toBeNull();
  expect(geometry!.imageWidth).toBeGreaterThan(250);
  expect(geometry!.imageHeight).toBeGreaterThan(350);
  expect(geometry!.count).toBeGreaterThan(0);
  expect(geometry!.allInside).toBe(true);

  expect(geometry!.count).toBe(1);
  await expectNoPageOverflow(page);
  expect(runtimeErrors.filter((entry) => entry.startsWith("页面脚本："))).toEqual(
    [],
  );

  await page.screenshot({
    path: `e2e/screenshots/evidence-live-active-${testInfo.project.name}.png`,
    fullPage: true,
  });
});
