/**
 * 记录工作台：真实浏览器端到端验收（worker_03 交付）。
 *
 * 覆盖清单（与执行上下文要求一一对应）：
 * - 首次建立批次、14 项任务存在
 * - 计时与手工用时
 * - 自动保存与刷新恢复
 * - 参与者界面复位不清记录
 * - 错误结论停止提示（含 E0/E4 互斥、修正后消失）
 * - 总体/逐任务统计（全部由逐项原始记录派生）
 * - Markdown/CSV/逐任务 CSV/本机备份四类下载
 * - 损坏备份拒绝、有效备份预览确认恢复
 * - 1080P 与 4K 桌面无横向溢出
 * - 最终证据截图（仅 4 张：桌面总览、桌面记录、4K 记录、错误结论停止提示）
 *
 * 项目门槛：桌面用例仅在 desktop-1080p 项目执行，4K 用例仅在 desktop-4k 项目执行，
 * 其余项目跳过，避免重复执行与截图互相覆盖。每个用例都在独立浏览器上下文中运行，
 * 记录数据写入独立本机存储键，互不污染。
 */

import { test, expect, type Page } from "@playwright/test";
import fs from "node:fs";
import { expectNoPageOverflow, openRoute } from "./helpers";
import {
  UAT_KEY_CREATED_PROJECT,
  UAT_KEY_MANUAL_ACTIONS,
  UAT_KEY_PROTOCOL_DRAFT_SAVED,
  UAT_KEY_TASK_PROGRESS,
} from "../src/app/uatTrialState";

const DESKTOP_PROJECT = "desktop-1080p";
const WIDE_PROJECT = "desktop-4k";

const TASK_IDS = Array.from(
  { length: 14 },
  (_, index) => `UAT-P1-${String(index + 1).padStart(2, "0")}`,
);

const SCREENSHOTS = {
  desktopOverview: "e2e/screenshots/uat-recorder-desktop-overview.png",
  desktopRecord: "e2e/screenshots/uat-recorder-desktop-record.png",
  wideRecord: "e2e/screenshots/uat-recorder-4k-record.png",
  stopBanner: "e2e/screenshots/uat-recorder-e4-stop-banner.png",
};

/** 本用例只在指定 Playwright 项目执行，其余项目跳过。 */
function onlyIn(projectName: string): void {
  test.skip(
    test.info().project.name !== projectName,
    `本用例仅在 ${projectName} 项目执行`,
  );
}

/** 收集页面脚本错误与控制台错误（排除浏览器 favicon 404 噪声）。 */
function watchErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(`页面脚本：${error.message}`));
  page.on("console", (message) => {
    if (message.type() === "error" && !message.text().includes("favicon")) {
      errors.push(`控制台：${message.text()}`);
    }
  });
  return errors;
}

/** 打开记录工作台并等待完全就绪：标题、14 张任务卡、自动读取页面版本。 */
async function openRecorder(page: Page): Promise<void> {
  await page.goto("/uat-recorder.html");
  await expect(
    page.getByRole("heading", { name: "入排审核界面试用记录", level: 1 }),
  ).toBeVisible();
  await expect(page.locator(".rec-task-card")).toHaveCount(14);
  await expect(page.locator("#rec-page-version")).toHaveText("界面试用版 1.5.2");
}

/** 增加参与者（自动编号 P01、P02……），可选覆盖代号。 */
async function addParticipant(page: Page, code?: string): Promise<void> {
  await page.getByRole("button", { name: "增加参与者" }).click();
  await expect(page.locator("#rec-participant-code")).toBeVisible();
  if (code) await page.locator("#rec-participant-code").fill(code);
}

const durationInput = (page: Page) => page.locator("#rec-f-duration");

const radioOf = (page: Page, name: string, value: "true" | "false" | "") =>
  page.locator(`#rec-record-form input[name="${name}"][value="${value}"]`);

const errorCheckbox = (page: Page, errorId: string) =>
  page.locator(`#rec-record-form .rec-error-item[data-error-id="${errorId}"] input`);

/** 自动汇总门槛表指定行（第一张表）。 */
const gateRow = (page: Page, label: string) =>
  page
    .locator("#rec-summary .rec-table")
    .first()
    .locator("tbody tr")
    .filter({ hasText: label })
    .first();

/** 逐任务汇总表指定行（第二张表，用「第 NN 项」定位）。 */
const taskRow = (page: Page, ordinal: string) =>
  page
    .locator("#rec-summary .rec-table")
    .nth(1)
    .locator("tbody tr")
    .filter({ hasText: ordinal })
    .first();

/** 点击导出按钮并读取下载文件内容。 */
async function exportText(
  page: Page,
  label: string,
): Promise<{ filename: string; text: string }> {
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: label }).click(),
  ]);
  const path = await download.path();
  const text = await fs.promises.readFile(path, "utf8");
  return { filename: download.suggestedFilename(), text };
}

/** 读取记录工作台的本机存储键（键名含 uat-recorder 的 localStorage 键）。 */
async function recorderStorage(page: Page): Promise<{
  count: number;
  value: string | null;
}> {
  return page.evaluate(() => {
    const keys = Object.keys(window.localStorage).filter((key) =>
      key.includes("uat-recorder"),
    );
    return {
      count: keys.length,
      value: keys.length === 1 ? window.localStorage.getItem(keys[0]) : null,
    };
  });
}

test.describe("记录工作台端到端（桌面）", () => {
  test("首次建立批次并自动读取页面版本", async ({ page }) => {
    onlyIn(DESKTOP_PROJECT);
    const errors = watchErrors(page);
    await openRecorder(page);
    await expect(page.locator("#rec-batch-code")).toHaveValue("");
    const today = await page.evaluate(() => {
      const d = new Date();
      const pad = (n: number) => String(n).padStart(2, "0");
      return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
    });
    await expect(page.locator("#rec-batch-start")).toHaveValue(today);
    await expect(page.getByText("还没有参与者，请先「增加参与者」。")).toBeVisible();
    await expect(page.locator("#rec-save-status")).toHaveText(
      /未找到本机记录，已建立空白批次|已自动读取当前界面版本并保存到本机/,
    );
    await page.locator("#rec-batch-code").fill("2026-08-13-A");
    await expect(page.locator("#rec-save-status")).toHaveText(
      /已保存到本机（\d{2}:\d{2}:\d{2}）/,
    );
    expect(errors).toEqual([]);
  });

  test("14 项任务按合同顺序存在", async ({ page }) => {
    onlyIn(DESKTOP_PROJECT);
    const errors = watchErrors(page);
    await openRecorder(page);
    const ids = await page.locator(".rec-task-card").evaluateAll((cards) =>
      cards.map((card) => (card as HTMLElement).dataset.taskId),
    );
    expect(ids).toEqual(TASK_IDS);
    await expect(page.locator(".rec-task-card").first()).toContainText("今日工作");
    await expect(page.locator(".rec-task-card").nth(13)).toContainText("三档缩放");
    expect(errors).toEqual([]);
  });

  test("计时与手工用时：计时续累并可从修正值继续", async ({ page }) => {
    onlyIn(DESKTOP_PROJECT);
    const errors = watchErrors(page);
    await openRecorder(page);
    await addParticipant(page);
    await page.getByRole("button", { name: "开始计时" }).click();
    await expect(page.locator(".rec-timer-value")).toHaveAttribute(
      "data-running",
      "true",
    );
    await page.waitForTimeout(2100);
    await page.getByRole("button", { name: "暂停计时" }).click();
    await expect(page.locator("#rec-save-status")).toHaveText(
      /计时已暂停并保存到本机/,
    );
    expect(Number(await durationInput(page).inputValue())).toBeGreaterThanOrEqual(2);
    // 手工修正用时：输入框与计时读数立即同步
    await durationInput(page).fill("100");
    await expect(durationInput(page)).toHaveValue("100");
    await expect(page.locator(".rec-timer-value")).toHaveText("100");
    // 再次开始计时：从修正值续累
    await page.getByRole("button", { name: "开始计时" }).click();
    await expect(page.locator(".rec-timer-value")).toHaveText("100");
    await page.waitForTimeout(1100);
    await page.getByRole("button", { name: "暂停计时" }).click();
    const resumed = Number(await durationInput(page).inputValue());
    expect(resumed).toBeGreaterThanOrEqual(101);
    expect(resumed).toBeLessThanOrEqual(103);
    expect(errors).toEqual([]);
  });

  test("自动保存与刷新恢复", async ({ page }) => {
    onlyIn(DESKTOP_PROJECT);
    const errors = watchErrors(page);
    await openRecorder(page);
    await page.locator("#rec-batch-code").fill("2026-08-13-B");
    await addParticipant(page);
    await durationInput(page).fill("42");
    await radioOf(page, "rec-radio-completed", "true").check();
    await page.locator("#rec-f-notes").fill("自动保存验证");
    await expect(page.locator("#rec-save-status")).toHaveText(
      /已保存到本机（\d{2}:\d{2}:\d{2}）/,
    );
    await page.reload();
    await expect(
      page.getByRole("heading", { name: "入排审核界面试用记录", level: 1 }),
    ).toBeVisible();
    await expect(page.locator(".rec-task-card")).toHaveCount(14);
    await expect(page.locator("#rec-batch-code")).toHaveValue("2026-08-13-B");
    await expect(page.locator(".rec-participant-card").first()).toContainText("P01");
    await expect(durationInput(page)).toHaveValue("42");
    await expect(page.locator("#rec-f-notes")).toHaveValue("自动保存验证");
    await expect(
      page.locator('.rec-task-card[data-task-id="UAT-P1-01"] .rec-task-badge'),
    ).toHaveText("完成");
    await expect(page.locator("#rec-save-status")).toHaveText("记录已从本机恢复");
    expect(errors).toEqual([]);
  });

  test("参与者界面复位不清记录工作台数据", async ({ page }) => {
    onlyIn(DESKTOP_PROJECT);
    const errors = watchErrors(page);
    const registeredKeys = [
      UAT_KEY_MANUAL_ACTIONS,
      UAT_KEY_CREATED_PROJECT,
      UAT_KEY_PROTOCOL_DRAFT_SAVED,
      UAT_KEY_TASK_PROGRESS,
    ];
    await openRecorder(page);
    await page.locator("#rec-batch-code").fill("2026-08-13-B");
    await addParticipant(page);
    await durationInput(page).fill("42");
    await radioOf(page, "rec-radio-completed", "false").check();
    // 先制造登记键“已使用”状态，用于证明复位真实执行
    await page.evaluate((keys) => {
      for (const key of keys) window.sessionStorage.setItem(key, "x");
    }, registeredKeys);
    const before = await recorderStorage(page);
    expect(before.count).toBe(1);
    expect(before.value).not.toBeNull();
    // 参与者界面：帮助页执行“开始新的界面试用”
    await openRoute(page, "/help");
    await page.getByRole("button", { name: "开始新的界面试用" }).click();
    await page.getByRole("button", { name: "确认并回到今日工作" }).click();
    await expect(page).toHaveURL(/\/today$/);
    await expect(page.getByRole("heading", { name: "今日工作", level: 1 })).toBeVisible();
    // 复位只清除登记键；记录工作台本机键原样保留
    const after = await page.evaluate((keys) => {
      const recorderKeys = Object.keys(window.localStorage).filter((key) =>
        key.includes("uat-recorder"),
      );
      return {
        session: keys.map((key) => window.sessionStorage.getItem(key)),
        recorderCount: recorderKeys.length,
        recorderValue:
          recorderKeys.length === 1
            ? window.localStorage.getItem(recorderKeys[0])
            : null,
      };
    }, registeredKeys);
    expect(after.session.every((value) => value === null)).toBe(true);
    expect(after.recorderCount).toBe(1);
    expect(after.recorderValue).toBe(before.value);
    // 回到记录工作台，记录完好
    await openRecorder(page);
    await expect(page.locator("#rec-batch-code")).toHaveValue("2026-08-13-B");
    await expect(durationInput(page)).toHaveValue("42");
    expect(errors).toEqual([]);
  });

  test("错误结论触发持续停止提示，修正后消失", async ({ page }) => {
    onlyIn(DESKTOP_PROJECT);
    const errors = watchErrors(page);
    await openRecorder(page);
    await addParticipant(page);
    await durationInput(page).fill("12");
    await errorCheckbox(page, "E4").check();
    const banner = page.locator("#rec-stop-banner");
    await expect(banner).toBeVisible();
    await expect(page.locator("#rec-stop-banner-list")).toContainText(
      "错误结论：参与者 P01 在第 01 项中出现错误结论",
    );
    await expect(page.locator("#rec-exceptions")).toContainText("错误结论");
    await expect(
      gateRow(page, "错误结论计数").locator("td.rec-gate-fail"),
    ).toHaveText("未通过");
    await expect(
      page.locator('.rec-task-card[data-task-id="UAT-P1-01"] .rec-task-badge'),
    ).toHaveText("错误结论");
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: SCREENSHOTS.stopBanner });
    // E0 与 E4 互斥：选择“无错误”立即解除停止提示
    await errorCheckbox(page, "E0").check();
    await expect(errorCheckbox(page, "E4")).not.toBeChecked();
    await expect(banner).toBeHidden();
    // 重新选择 E4，停止提示立即恢复，E0 被清除
    await errorCheckbox(page, "E4").check();
    await expect(banner).toBeVisible();
    await expect(errorCheckbox(page, "E0")).not.toBeChecked();
    // 修正后停止提示消失，门槛回到通过
    await errorCheckbox(page, "E4").uncheck();
    await expect(banner).toBeHidden();
    await expect(
      gateRow(page, "错误结论计数").locator("td.rec-gate-pass"),
    ).toHaveText("通过");
    expect(errors).toEqual([]);
  });

  test("总体与逐任务统计全部由原始记录派生", async ({ page }) => {
    onlyIn(DESKTOP_PROJECT);
    const errors = watchErrors(page);
    await openRecorder(page);
    await addParticipant(page);
    await durationInput(page).fill("30");
    await radioOf(page, "rec-radio-completed", "true").check();
    await radioOf(page, "rec-radio-layout", "false").check();
    // 门槛表：样本量类未通过，完成率类通过，其余按零分母/未测试口径
    await expect(gateRow(page, "有效参与者人数").locator("td").nth(2)).toHaveText("1");
    await expect(
      gateRow(page, "有效参与者人数").locator("td.rec-gate-fail"),
    ).toHaveText("未通过");
    await expect(gateRow(page, "有效任务运行总数").locator("td").nth(2)).toHaveText("1");
    await expect(
      gateRow(page, "总体无辅助完成率").locator("td.rec-gate-pass"),
    ).toHaveText("通过");
    await expect(
      gateRow(page, "单项无辅助完成率").locator("td.rec-gate-fail"),
    ).toHaveText("未通过");
    await expect(gateRow(page, "总体无辅助完成率").locator("td").nth(2)).toContainText(
      "100.0%",
    );
    await expect(
      gateRow(page, "错误结论计数").locator("td.rec-gate-pass"),
    ).toHaveText("通过");
    await expect(
      gateRow(page, "关键证据操作数").locator("td.rec-gate-fail"),
    ).toHaveText("未通过");
    await expect(
      gateRow(page, "布局与键盘").locator("td.rec-gate-pass"),
    ).toHaveText("通过");
    await expect(
      gateRow(page, "主观评价").locator("td.rec-gate-fail"),
    ).toHaveText("未通过");
    // 逐任务表：第 01 项有记录，第 02 项未填写且比例无法计算
    const row01 = taskRow(page, "第 01 项");
    await expect(row01.locator("td").nth(1)).toHaveText("1");
    await expect(row01.locator("td").nth(3)).toHaveText("100.0%");
    await expect(row01.locator("td").nth(2)).toHaveText("1");
    await expect(row01.locator("td").nth(4)).toHaveText("0");
    await expect(row01.locator("td").nth(6)).toHaveText("0");
    const row02 = taskRow(page, "第 02 项");
    await expect(row02.locator("td").nth(1)).toHaveText("0");
    await expect(row02.locator("td").nth(3)).toHaveText("无法计算");
    await expect(row02.locator("td").nth(6)).toHaveText("1");
    expect(errors).toEqual([]);
  });

  test("四类导出内容均来自同一份原始记录", async ({ page }) => {
    onlyIn(DESKTOP_PROJECT);
    const errors = watchErrors(page);
    await openRecorder(page);
    await page.locator("#rec-batch-code").fill("2026-08-13-B");
    await addParticipant(page);
    await durationInput(page).fill("12");
    await radioOf(page, "rec-radio-completed", "false").check();
    const markdown = await exportText(page, "导出审阅用 Markdown 文件");
    expect(markdown.filename).toMatch(/^界面试用记录-2026-08-13-B-\d{8}-\d{4}\.md$/);
    expect(markdown.text).toContain("## 0. 批次基本信息");
    expect(markdown.text).toContain("## 1. 逐人原始记录");
    expect(markdown.text).toContain("## 6. 正式门槛结论");
    expect(markdown.text).toContain("2026-08-13-B");
    expect(markdown.text).toContain("UAT-P1-01");
    expect(markdown.text).toContain("达到临时门槛不等于方案冻结");
    const csv = await exportText(page, "导出逐行原始记录 CSV");
    expect(csv.filename).toMatch(/^界面试用原始记录-2026-08-13-B-\d{8}-\d{4}\.csv$/);
    expect(csv.text).toContain("参与者代号");
    expect(csv.text).toContain("P01");
    expect(csv.text).toContain("\r\n");
    expect(csv.text).toContain("UAT-P1-01");
    const summaryCsv = await exportText(page, "导出逐任务统计 CSV");
    expect(summaryCsv.filename).toMatch(/^界面试用逐任务统计-2026-08-13-B-\d{8}-\d{4}\.csv$/);
    expect(summaryCsv.text).toContain("任务编号");
    expect(summaryCsv.text).toContain("UAT-P1-01");
    const backup = await exportText(page, "导出本机备份文件");
    expect(backup.filename).toMatch(/^本机备份-2026-08-13-B-\d{8}-\d{4}\.json$/);
    const parsed = JSON.parse(backup.text);
    expect(parsed.schema).toBe("enrollment-review/uat-recorder-backup");
    expect(parsed.version).toBe(1);
    expect(parsed.batch.batchCode).toBe("2026-08-13-B");
    expect(parsed.batch.participants).toHaveLength(1);
    expect(parsed.batch.participants[0].code).toBe("P01");
    expect(Object.keys(parsed.batch.participants[0].taskRecords)).toHaveLength(14);
    expect(errors).toEqual([]);
  });

  test("损坏备份被拒绝且不改变当前记录", async ({ page }) => {
    onlyIn(DESKTOP_PROJECT);
    const errors = watchErrors(page);
    await openRecorder(page);
    const importInput = page.locator(
      'label.rec-btn:has-text("导入本机备份文件") input[type="file"]',
    );
    // 向量 1：不是本工作台备份
    await importInput.setInputFiles({
      name: "bad.json",
      mimeType: "application/json",
      buffer: Buffer.from('{"foo":"bar"}'),
    });
    await expect(page.locator("#rec-dialog-title")).toHaveText(
      "导入预览：文件校验未通过",
    );
    await expect(page.locator("#rec-dialog-body")).toContainText(
      "该文件不能用作本机备份",
    );
    await expect(page.locator("#rec-dialog-confirm")).toBeDisabled();
    await page.locator("#rec-dialog-cancel").click();
    await expect(page.locator("#rec-dialog")).not.toBeVisible();
    // 向量 2：封套正确但版本不识别
    await importInput.setInputFiles({
      name: "wrong-version.json",
      mimeType: "application/json",
      buffer: Buffer.from(
        JSON.stringify({
          schema: "enrollment-review/uat-recorder-backup",
          version: 99,
          batch: {},
        }),
      ),
    });
    await expect(page.locator("#rec-dialog-title")).toHaveText(
      "导入预览：文件校验未通过",
    );
    await expect(page.locator("#rec-dialog-confirm")).toBeDisabled();
    await page.locator("#rec-dialog-cancel").click();
    await expect(page.locator("#rec-batch-code")).toHaveValue("");
    expect(errors).toEqual([]);
  });

  test("有效备份先预览再确认恢复", async ({ page }) => {
    onlyIn(DESKTOP_PROJECT);
    const errors = watchErrors(page);
    await openRecorder(page);
    // 状态 A：1 名参与者、1 条任务记录
    await page.locator("#rec-batch-code").fill("2026-08-13-B");
    await addParticipant(page);
    await durationInput(page).fill("12");
    await radioOf(page, "rec-radio-completed", "false").check();
    const backup = await exportText(page, "导出本机备份文件");
    // 修改当前状态：增加 P02 并填写记录
    await addParticipant(page);
    await expect(page.locator("#rec-participant-code")).toHaveValue("P02");
    await durationInput(page).fill("7");
    // 导入备份：预览后确认替换
    const importInput = page.locator(
      'label.rec-btn:has-text("导入本机备份文件") input[type="file"]',
    );
    await importInput.setInputFiles({
      name: "restore.json",
      mimeType: "application/json",
      buffer: Buffer.from(backup.text, "utf8"),
    });
    await expect(page.locator("#rec-dialog-title")).toHaveText("导入本机备份（预览）");
    const body = page.locator("#rec-dialog-body");
    await expect(body).toContainText("2026-08-13-B");
    await expect(body).toContainText("界面试用版 1.5.2");
    await expect(body).toContainText("参与者数");
    await expect(body).toContainText("1 人");
    await expect(body).toContainText("任务记录数");
    await expect(body).toContainText("1 条");
    await page
      .locator("#rec-dialog-confirm", { hasText: "确认替换当前批次" })
      .click();
    await expect(page.locator("#rec-dialog")).not.toBeVisible();
    await expect(page.locator(".rec-participant-card")).toHaveCount(1);
    await expect(page.locator(".rec-participant-card").first()).toContainText("P01");
    await expect(page.locator("#rec-batch-code")).toHaveValue("2026-08-13-B");
    await expect(durationInput(page)).toHaveValue("12");
    await expect(page.locator("#rec-save-status")).toHaveText(
      /已导入本机备份并替换当前批次/,
    );
    // 刷新后恢复结果仍在
    await page.reload();
    await expect(page.locator(".rec-participant-card")).toHaveCount(1);
    await expect(page.locator("#rec-batch-code")).toHaveValue("2026-08-13-B");
    await expect(durationInput(page)).toHaveValue("12");
    expect(errors).toEqual([]);
  });

  test("桌面无页面级横向溢出", async ({ page }) => {
    onlyIn(DESKTOP_PROJECT);
    const errors = watchErrors(page);
    await openRecorder(page);
    await expectNoPageOverflow(page);
    await addParticipant(page);
    await durationInput(page).fill("30");
    await radioOf(page, "rec-radio-completed", "true").check();
    await expectNoPageOverflow(page);
    await errorCheckbox(page, "E4").check();
    await expect(page.locator("#rec-stop-banner")).toBeVisible();
    await expectNoPageOverflow(page);
    await errorCheckbox(page, "E4").uncheck();
    expect(errors).toEqual([]);
  });

  test("最终证据截图：桌面总览与桌面记录", async ({ page }) => {
    onlyIn(DESKTOP_PROJECT);
    const errors = watchErrors(page);
    await openRecorder(page);
    await page.locator("#rec-batch-code").fill("2026-08-13-B");
    await addParticipant(page);
    await durationInput(page).fill("45");
    await radioOf(page, "rec-radio-completed", "true").check();
    await page.locator("#rec-f-notes").fill("参与者按任务卡独立完成，未请求提示。");
    // 桌面记录：滚动到当前任务记录区截取视口
    await page.locator("#rec-record-form").scrollIntoViewIfNeeded();
    await page.screenshot({ path: SCREENSHOTS.desktopRecord });
    // 桌面总览：整页截图
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: SCREENSHOTS.desktopOverview, fullPage: true });
    expect(errors).toEqual([]);
  });
});

test.describe("记录工作台端到端（4K）", () => {
  test("4K 无页面级横向溢出且记录可用", async ({ page }) => {
    onlyIn(WIDE_PROJECT);
    const errors = watchErrors(page);
    await openRecorder(page);
    await expectNoPageOverflow(page);
    await addParticipant(page);
    await durationInput(page).fill("18");
    await radioOf(page, "rec-radio-completed", "false").check();
    await expectNoPageOverflow(page);
    await expect(page.locator("#rec-stop-banner")).toBeHidden();
    await page.locator("#rec-record-form").scrollIntoViewIfNeeded();
    await page.screenshot({ path: SCREENSHOTS.wideRecord });
    expect(errors).toEqual([]);
  });
});
