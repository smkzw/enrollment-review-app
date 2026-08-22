import { expect, test } from "@playwright/test";
import { collectRuntimeErrors, expectNoPageOverflow } from "./helpers";

const baseUrl = process.env.EVIDENCE_LIVE_BASE_URL;
const sourceFile = process.env.EVIDENCE_LIVE_SOURCE_FILE;
const subjectId = process.env.EVIDENCE_LIVE_SUBJECT_ID;
const episodeId = process.env.EVIDENCE_LIVE_EPISODE_ID;
const enabled = [baseUrl, sourceFile, subjectId, episodeId].every(Boolean);

test.skip(
  !enabled,
  "仅在显式提供清洁后端地址、合成资料和受试者审核节点时运行。",
);

test("真实后端完成资料上传、核对、生成与启用", async ({ page }, testInfo) => {
  test.setTimeout(150_000);
  const runtimeErrors = collectRuntimeErrors(page);
  const url = `${baseUrl}/#/subjects/${subjectId}/evidence?episode=${episodeId}`;

  await page.goto(url);
  await expect(
    page.getByRole("heading", { name: "证据工作台", level: 1 }),
  ).toBeVisible();
  await expect(page.getByLabel("当前资料上下文")).toContainText("S-BARRIER");

  await page.getByRole("radio", { name: "建立完整资料快照" }).click();
  await page.setInputFiles("#evidence-file-input", sourceFile as string);
  const preview = page.getByLabel("确认前复核");
  await expect(preview).toBeVisible();
  await expect(preview.getByText("synthetic_screening_record.pdf")).toBeVisible();
  await preview.getByRole("button", { name: "确认上传" }).click();

  await expect(page.getByLabel("资料快照")).toBeVisible();
  await page.getByRole("link", { name: "查看本次资料整理进度" }).click();
  await expect(page.getByRole("heading", { name: "资料处理详情", level: 1 })).toBeVisible();
  await page.getByRole("link", { name: "返回该受试者资料" }).click();
  await expect(
    page.getByRole("heading", { name: "证据工作台", level: 1 }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "检查核对结果并生成资料版本" }),
  ).toBeVisible({ timeout: 60_000 });

  const fileRow = page
    .getByLabel("文件清单")
    .getByRole("button", { name: /synthetic_screening_record\.pdf/ });
  await fileRow.click();
  const metadata = page.getByLabel("核对资料信息");
  await expect(metadata.getByText("系统建议，待核对")).toBeVisible();
  await metadata
    .getByRole("textbox", { name: "核对说明" })
    .fill("已核对文件标题与正文内容");
  await metadata.getByRole("button", { name: "保存核对结果" }).click();
  await expect(page.getByText("资料类型与提供方已保存，将纳入下一次生成的资料版本。"))
    .toBeVisible();
  await expect(metadata.getByText("已人工核对")).toBeVisible({ timeout: 15_000 });

  await expect(page.getByRole("heading", { name: "原始识别 / 校对后文本" }))
    .toBeVisible({ timeout: 30_000 });
  await expect(
    page.getByText(/受试者否认近期发热、咳嗽及其他活动性/).first(),
  ).toBeVisible();
  await expect(page.getByAltText("第 1 页原始资料")).toBeVisible();

  await page.getByRole("link", { name: "返回资料页" }).click();
  await expect(page.getByText("资料已上传，尚待整理和确认")).toBeVisible();
  await page.getByRole("link", { name: "打开筛选证据工作台" }).click();
  await expect(
    page.getByRole("heading", { name: "证据工作台", level: 1 }),
  ).toBeVisible();

  await page.screenshot({
    path: `e2e/screenshots/evidence-live-before-build-${testInfo.project.name}.png`,
    fullPage: true,
  });

  await page
    .getByRole("button", { name: "检查核对结果并生成资料版本" })
    .click();

  for (let pass = 0; pass < 30; pass += 1) {
    const activate = page.getByRole("button", { name: "启用这个资料版本" });
    if (await activate.isVisible().catch(() => false)) break;

    const saveButton = page.getByRole("button", { name: "保存核对" }).first();
    if (!(await saveButton.isVisible().catch(() => false))) {
      await page.waitForTimeout(500);
      continue;
    }
    const item = saveButton.locator(
      "xpath=ancestor::*[contains(@class,'evidence-risk-item')]",
    );
    const reviewedBefore = await page.getByText(/^已核对：/).count();
    await item.getByRole("textbox").fill("已逐字对照原始资料，确认识别内容无误");
    await saveButton.click();
    await expect(page.getByText(/^已核对：/)).toHaveCount(reviewedBefore + 1, {
      timeout: 15_000,
    });
  }

  const activate = page.getByRole("button", { name: "启用这个资料版本" });
  await expect(activate).toBeVisible({ timeout: 90_000 });

  // 候选资料版本必须由服务端恢复，不能只依赖当前浏览器内存。
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "证据工作台", level: 1 }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "启用这个资料版本" }),
  ).toBeVisible({ timeout: 30_000 });
  await expect(
    page.getByRole("button", { name: "检查核对结果并生成资料版本" }),
  ).toHaveCount(0);

  await page.getByRole("button", { name: "启用这个资料版本" }).click();
  await expect(page.getByLabel("当前资料上下文")).toContainText("当前有效");
  await expect(page.getByRole("heading", { name: "原始识别 / 校对后文本" }))
    .toBeVisible({ timeout: 30_000 });
  await expect(page.getByAltText("第 1 页原始资料")).toBeVisible();

  await page.screenshot({
    path: `e2e/screenshots/evidence-live-active-${testInfo.project.name}.png`,
    fullPage: true,
  });
  await expectNoPageOverflow(page);
  expect(runtimeErrors.filter((entry) => entry.startsWith("页面脚本："))).toEqual([]);
});
