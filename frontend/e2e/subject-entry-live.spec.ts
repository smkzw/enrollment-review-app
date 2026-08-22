import { expect, test } from "@playwright/test";
import { collectRuntimeErrors, expectNoPageOverflow } from "./helpers";

const baseUrl = process.env.EVIDENCE_LIVE_BASE_URL;
const enabled = Boolean(baseUrl);

test.skip(!enabled, "仅在显式提供清洁真实后端地址时运行。");

test("新增受试者后生成全部审核节点，并保持删除与返回边界", async ({
  page,
}, testInfo) => {
  const runtimeErrors = collectRuntimeErrors(page);
  const suffix = testInfo.project.name.replace(/[^a-z0-9]/gi, "-");
  const subjectCode = `V-${suffix}`;
  const emptySubjectCode = `E-${suffix}`;

  await page.goto(`${baseUrl}/#/subjects`);
  await expect(page.getByRole("heading", { name: "受试者与资料", level: 1 }))
    .toBeVisible();

  await page.getByRole("button", { name: "新增受试者" }).click();
  const createDialog = page.getByRole("dialog", { name: "新增受试者" });
  await createDialog.getByLabel(/受试者代号/).fill(subjectCode);
  await createDialog.getByLabel("中心编号").fill("31");
  await createDialog.getByLabel("中心名称").fill("河北省中医院");
  await createDialog.getByLabel("性别").selectOption({ label: "女" });
  await createDialog.getByLabel("年龄").fill("45");
  await createDialog.getByRole("button", { name: "确认新增" }).click();

  await expect(page.getByRole("heading", { name: subjectCode, level: 2 }))
    .toBeVisible();
  for (const [stage, window] of [
    ["预筛期审核", "签署知情同意前"],
    ["筛选期审核", "D-28至D-1"],
    ["导入/洗脱期审核", "筛选后至基线前"],
    ["基线/随机前审核", "D1随机前"],
  ]) {
    const article = page.locator("article.catalog-episode", { hasText: stage });
    await expect(article).toBeVisible();
    await expect(article).toContainText(`访视窗口：${window}`);
  }

  await page
    .locator("article.catalog-episode", { hasText: "筛选期审核" })
    .getByRole("link", { name: /打开筛选证据工作台/ })
    .click();
  await expect(page.getByLabel("当前资料上下文")).toContainText(subjectCode);
  await expect(page.getByLabel("当前资料上下文")).toContainText("筛选期审核");
  await page.getByRole("link", { name: "返回资料页" }).click();
  await expect(page.getByRole("heading", { name: subjectCode, level: 2 }))
    .toBeVisible();

  await page.getByRole("button", { name: "新增受试者" }).click();
  await page.getByRole("dialog", { name: "新增受试者" })
    .getByLabel(/受试者代号/).fill(emptySubjectCode);
  await page.getByRole("dialog", { name: "新增受试者" })
    .getByRole("button", { name: "确认新增" }).click();
  const emptyRow = page.locator("li.catalog-subject-item", { hasText: emptySubjectCode });
  await emptyRow.getByRole("button", { name: `删除受试者 ${emptySubjectCode}` }).click();
  await page.getByRole("dialog", { name: "确认删除受试者" })
    .getByRole("button", { name: "确认删除" }).click();
  await expect(page.getByText(emptySubjectCode, { exact: true })).toHaveCount(0);
  await expect(page.locator(".catalog-episodes h2")).not.toHaveText("审核节点");

  const protectedRow = page.locator("li.catalog-subject-item", { hasText: "S-BARRIER" });
  await protectedRow.getByRole("button", { name: "删除受试者 S-BARRIER" }).click();
  const deleteDialog = page.getByRole("dialog", { name: "确认删除受试者" });
  await deleteDialog.getByRole("button", { name: "确认删除" }).click();
  await expect(deleteDialog).toContainText("已有历史证据快照");
  await expect(deleteDialog).toContainText("删除会破坏不可变证据");
  await deleteDialog.getByRole("button", { name: "先不要" }).click();
  await expect(page.getByText("S-BARRIER", { exact: true })).toBeVisible();

  await expectNoPageOverflow(page);
  expect(runtimeErrors.filter((entry) => entry.startsWith("页面脚本："))).toEqual([]);
  await page.screenshot({
    path: `e2e/screenshots/subject-entry-${testInfo.project.name}.png`,
    fullPage: true,
  });
});
