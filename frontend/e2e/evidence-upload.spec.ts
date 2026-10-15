/**
 * 证据工作台无辅助流程（任务 worker_03，Slice 4.2）。
 * 真实浏览器 + 合成干净 V2 数据（路由拦截 /api/v2/**）：用户不看帮助也能
 * 区分两种上传方式、发现完整资料遗漏、解决同名冲突、取消不建快照、
 * 确认正确的受试者/节点，且页面不跳顶、无横向滚动。
 * 在 1920×1080、2560×1440、3840×2160 三个最大化桌面视口各执行一次。
 */

import { test, expect } from "@playwright/test";
import {
  collectRuntimeErrors,
  expectNoPageOverflow,
} from "./helpers";
import {
  EPISODE_ID,
  SELECTED_FILES,
  SUBJECT_ID,
  registerEvidenceRoutes,
} from "./evidence-fixtures";

const EVIDENCE_HASH = `#/subjects/${SUBJECT_ID}/evidence?episode=${EPISODE_ID}`;

test("证据工作台无辅助流程", async ({ page }) => {
  const runtimeErrors = collectRuntimeErrors(page);
  const log = await registerEvidenceRoutes(page, { activeReview: true });

  await page.goto(`/${EVIDENCE_HASH}`);
  await expect(
    page.getByRole("heading", { name: "证据工作台", level: 1 }),
  ).toBeVisible();

  // 固定上下文带：项目、受试者、审核节点、方案版本、资料版本
  const band = page.getByLabel("当前资料上下文");
  await expect(band).toContainText("界面试用项目 · Ⅲ期");
  await expect(band).toContainText("UAT-01");
  await expect(band).toContainText("筛选期");
  await expect(band).toContainText("V1.0");
  // 本场景验证增量上传，前提是已有当前有效资料。
  await expect(band).toContainText("当前有效");

  await page.getByRole("button", { name: "补充或重建资料" }).click();

  // 两种上传方式 + 旁边中文说明，无内部术语
  await expect(
    page.getByRole("radio", { name: "补充资料" }),
  ).toBeVisible();
  await expect(
    page.getByRole("radio", { name: "建立完整资料快照" }),
  ).toBeVisible();
  await expect(page.getByText(/请先选择本次资料的上传方式/)).toBeVisible();
  const mainText = await page.locator("#main-content").innerText();
  expect(mainText).not.toMatch(/\b(incremental|full|Job|schema|payload)\b/);

  // ---- 补充资料：预览分类 + 冲突门禁 ----
  await page.getByRole("radio", { name: "补充资料" }).click();
  await expect(page.getByText(/在上一有效快照的全部资料基础上/)).toBeVisible();

  await page.setInputFiles("#evidence-file-input", SELECTED_FILES);
  const review = page.getByLabel("确认前复核");
  await expect(review).toBeVisible();
  await expect(review.getByText("检查报告.pdf")).toBeVisible();
  await expect(review.getByText("新增资料").first()).toBeVisible();
  await expect(review.getByText("内容重复")).toBeVisible();
  await expect(review.getByText("名称相同但内容不同")).toBeVisible();
  await expect(review.getByText("格式不支持")).toBeVisible();

  // 有活动预览时锁定上传方式并隐藏再次选文件，不静默丢引用
  await expect(
    page.getByRole("radio", { name: "补充资料" }),
  ).toBeDisabled();
  await expect(
    page.getByRole("radio", { name: "建立完整资料快照" }),
  ).toBeDisabled();
  await expect(page.getByText(/如需更换上传方式，请先点击「取消预览」/)).toBeVisible();
  await expect(page.locator("#evidence-file-input")).toBeHidden();

  // 滚动后顶栏与上下文带都可见且不相交（band 避开 --topbar-height，层级低于顶栏）
  await page.evaluate(() => window.scrollTo(0, 420));
  await page.waitForTimeout(100);
  const rects = await page.evaluate(() => {
    const topbar = document
      .querySelector(".topbar")
      ?.getBoundingClientRect();
    const bandEl = document
      .querySelector(".evidence-band")
      ?.getBoundingClientRect();
    return {
      topbar:
        topbar === undefined
          ? null
          : { top: topbar.top, bottom: topbar.bottom, height: topbar.height },
      band:
        bandEl === undefined
          ? null
          : { top: bandEl.top, bottom: bandEl.bottom, height: bandEl.height },
    };
  });
  expect(rects.topbar).not.toBeNull();
  expect(rects.band).not.toBeNull();
  expect(rects.topbar!.top).toBeGreaterThanOrEqual(0);
  // 上下文带顶边不低于顶栏底边（不相交、不重叠）
  expect(rects.band!.top).toBeGreaterThanOrEqual(rects.topbar!.bottom - 1);

  const confirmButton = page.getByRole("button", { name: "确认上传" });
  await expect(confirmButton).toBeDisabled();
  await expect(
    review.getByText(/还有 1 份同名文件未选择处置方式/),
  ).toBeVisible();

  await page.getByLabel("作为原资料的新版本").check();
  await expect(confirmButton).toBeEnabled();

  // ---- 取消：不建立快照 ----
  await page.getByRole("button", { name: "取消预览" }).click();
  await expect(
    page.getByText("当前有效资料可在下方查看。"),
  ).toBeVisible();
  expect(log.filter((entry) => entry.method === "POST" && /\/commit$/.test(entry.url))).toHaveLength(0);
  // 回到当前资料阅读态：文件选择入口和上传方式都收起
  await expect(page.locator("#evidence-file-input")).toBeHidden();

  // ---- 建立完整资料快照：遗漏核对 ----
  await page.getByRole("button", { name: "补充或重建资料" }).click();
  await page
    .getByRole("radio", { name: "建立完整资料快照" })
    .click();
  await expect(
    page.getByText(/本次选择的文件构成新的完整资料集合/),
  ).toBeVisible();

  await page.setInputFiles("#evidence-file-input", SELECTED_FILES);
  const reviewFull = page.getByLabel("确认前复核");
  await expect(reviewFull).toBeVisible();
  // 完整资料遗漏清单：上一快照有、本次未选择
  await expect(
    reviewFull.getByRole("heading", { name: /上一快照有、本次未选择/ }),
  ).toBeVisible();
  await expect(reviewFull.getByText("既往病历.pdf")).toBeVisible();
  await expect(reviewFull.getByText("需要重新识别").first()).toBeVisible();

  // 解决同名冲突
  await page.getByLabel("作为原资料的新版本").check();
  await expect(
    reviewFull.getByRole("button", { name: "确认上传" }),
  ).toBeEnabled();

  // 滚动到中部后确认，验证不跳顶（上传不得造成页面跳顶）
  await page.evaluate(() => window.scrollTo(0, 300));
  await page.waitForTimeout(80);
  const beforeY = await page.evaluate(() => window.scrollY);

  await reviewFull.getByRole("button", { name: "确认上传" }).click();
  await expect(
    page.getByText(
      "已建立资料快照，正在处理；处理完成并确认启用前，当前有效资料版本不会改变。",
    ),
  ).toBeVisible();

  // 页面未跳顶，URL 未变化（仍保持正确的受试者/节点深链）
  const afterY = await page.evaluate(() => window.scrollY);
  expect(afterY).toBeGreaterThan(0);
  expect(beforeY).toBeGreaterThanOrEqual(0);
  expect(page.url()).toContain(EVIDENCE_HASH);

  // 确认结果仍保留正确的受试者/节点上下文
  const bandAfter = page.getByLabel("当前资料上下文");
  await expect(bandAfter).toContainText("UAT-01");
  await expect(bandAfter).toContainText("筛选期");

  // 服务端收到的确认命令：正确的上传方式 + 正确的审核节点（作用域）
  const commits = log.filter(
    (entry) => entry.method === "POST" && /\/commit$/.test(entry.url),
  );
  expect(commits).toHaveLength(1);
  expect(commits[0].body).toMatchObject({
    upload_mode: "full",
    preview_sha256: expect.stringMatching(/^[0-9a-f]{64}$/),
    resolutions: { "item-e2e-conflict-admission": "new_version" },
  });
  // 预览创建作用域：受试者路径 + 审核节点表单
  const previews = log.filter((entry) =>
    entry.url.endsWith("/evidence-upload-previews"),
  );
  expect(previews.length).toBeGreaterThan(0);
  for (const preview of previews) {
    expect(preview.url).toContain(`/subjects/${SUBJECT_ID}/`);
    expect(preview.form.review_episode_id).toBe(EPISODE_ID);
  }

  await expectNoPageOverflow(page);
  expect(runtimeErrors).toEqual([]);
});

test("移除文件时取消清理失败：不新建预览、原预览仍可见、显示后端中文错误", async ({
  page,
}) => {
  const runtimeErrors = collectRuntimeErrors(page);
  const log = await registerEvidenceRoutes(page, {
    activeReview: true,
    failCancel: true,
  });

  await page.goto(`/${EVIDENCE_HASH}`);
  await expect(
    page.getByRole("heading", { name: "证据工作台", level: 1 }),
  ).toBeVisible();

  await page.getByRole("button", { name: "补充或重建资料" }).click();
  await page.getByRole("radio", { name: "补充资料" }).click();
  await page.setInputFiles("#evidence-file-input", SELECTED_FILES);
  const review = page.getByLabel("确认前复核");
  await expect(review).toBeVisible();
  const createsBefore = log.filter((entry) =>
    entry.url.endsWith("/evidence-upload-previews"),
  ).length;
  expect(createsBefore).toBe(1);

  await review.getByRole("button", { name: "移除" }).first().click();

  // 后端中文错误可见，原预览仍可见，未生成新预览
  await expect(page.getByText(/临时文件清理尚未完成/)).toBeVisible();
  await expect(page.getByLabel("确认前复核")).toBeVisible();
  const createsAfter = log.filter((entry) =>
    entry.url.endsWith("/evidence-upload-previews"),
  ).length;
  expect(createsAfter).toBe(createsBefore);
  await expectNoPageOverflow(page);
  // 注入的 500 会让浏览器记录一条资源加载控制台错误；只要求无页面脚本异常
  expect(runtimeErrors.filter((entry) => entry.startsWith("页面脚本："))).toEqual([]);
});
