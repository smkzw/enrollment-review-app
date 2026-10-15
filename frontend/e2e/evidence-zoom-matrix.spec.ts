import { expect, test } from "@playwright/test";
import { expectNoPageOverflow, setLayoutStressFactor } from "./helpers";
import { EPISODE_ID, SUBJECT_ID, registerEvidenceRoutes } from "./evidence-fixtures";

const EVIDENCE_HASH = `#/subjects/${SUBJECT_ID}/evidence?episode=${EPISODE_ID}`;

function factorsForProject(name: string): ReadonlyArray<1 | 1.25 | 1.5 | 2> {
  if (name === "desktop-1080p") return [1, 1.25];
  if (name === "desktop-2k") return [1, 1.5];
  return [1, 1.5, 2];
}

test("连续原件和真实红框在宽屏缩放矩阵中保持对应", async ({ page }, testInfo) => {
  await registerEvidenceRoutes(page, { activeReview: true });
  await page.goto(`/${EVIDENCE_HASH}`);
  await expect(page.getByAltText("第 1 页原始资料")).toBeVisible();
  await expect(page.getByLabel(/^重点标注/)).toHaveCount(0);
  await page.getByRole("button", { name: /查看 \d+ 处原件定位/ }).click();
  await page.getByRole("button", { name: "在原件中查看" }).first().click();
  await expect(page.getByLabel(/^重点标注/)).toHaveCount(1);

  for (const factor of factorsForProject(testInfo.project.name)) {
    await setLayoutStressFactor(page, factor);
    await expectNoPageOverflow(page);
    const geometry = await page.evaluate(() => {
      const image = document.querySelector<HTMLImageElement>(
        'img[alt="第 1 页原始资料"]',
      );
      const box = document.querySelector<HTMLElement>('[aria-label^="重点标注"]');
      if (image === null || box === null) return null;
      const imageRect = image.getBoundingClientRect();
      const boxRect = box.getBoundingClientRect();
      return {
        imageWidth: imageRect.width,
        imageHeight: imageRect.height,
        leftRatio: (boxRect.left - imageRect.left) / imageRect.width,
        topRatio: (boxRect.top - imageRect.top) / imageRect.height,
        rightRatio: (boxRect.right - imageRect.left) / imageRect.width,
        bottomRatio: (boxRect.bottom - imageRect.top) / imageRect.height,
      };
    });
    expect(geometry).not.toBeNull();
    expect(geometry!.imageWidth).toBeGreaterThan(250);
    expect(geometry!.imageHeight).toBeGreaterThan(350);
    expect(geometry!.leftRatio).toBeCloseTo(120 / 1240, 2);
    expect(geometry!.topRatio).toBeCloseTo(440 / 1754, 2);
    expect(geometry!.rightRatio).toBeCloseTo(430 / 1240, 2);
    expect(geometry!.bottomRatio).toBeCloseTo(525 / 1754, 2);
    await page.screenshot({
      path: `e2e/screenshots/evidence-${testInfo.project.name}-zoom-${String(factor).replace(".", "_")}.png`,
    });
  }
});
