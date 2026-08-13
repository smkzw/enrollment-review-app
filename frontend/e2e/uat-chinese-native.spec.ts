/**
 * 中文原生与无占位审计（worker_03 / 成功条件 7）。
 * - 所有用户可见文字使用中文临床试验工作语境。
 * - 参与者任务卡不存在“指定受试者/指定行动/指定父规则”等未解析占位；
 *   不得把正确结果写进参与者文字。
 * - 工程内部词（Agent/schema/pipeline/provider/fixture/stub/sessionStorage/
 *   ViewModel 等）不得出现在渲染文本或参与者任务卡。
 * - 允许的专有缩写：ICF、规则编号（EX 系 / IN 系 / REQ 系）、UAT-*、CRC/CRA、V1.0/V2.0、
 *   PDF、Tab/Enter/Escape（帮助页键盘说明）。其含义是面向临床用户的标准记号，
 *   不是程序员内部词。
 */

import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { openRoute } from "./helpers";

const DOC_DIR = path.resolve(
  process.cwd(),
  "..",
  ".trellis",
  "tasks",
  "archive",
  "2026-08",
  "08-13-phase1-5-uat-readiness",
);

/** 内部/工程词；这些词只应出现在代码与开发文档，不应进入用户可见界面或参与者任务卡。 */
const FORBIDDEN_TERMS: ReadonlyArray<RegExp> = [
  /\bAgent\b/i,
  /\bschema\b/i,
  /\bpipeline\b/i,
  /\bprovider\b/i,
  /\blog\b/i,
  /\bfixture\b/i,
  /\bstub\b/i,
  /\bsessionStorage\b/i,
  /\blocalStorage\b/i,
  /\bViewModel\b/i,
  /\bprototypeOnly\b/i,
  /\bplaceholder\b/i,
  /\bundefined\b/i,
  /\bnull\b/i,
  /\byear\b/i,
  /\bxULN\b/i,
  /\bspec\b/i,
  /\bmock\b/i,
  /\brefresh\b/i,
];

/** 未解析占位模式（成功条件 4 / 任务卡无占位） */
const PLACEHOLDER_PATTERNS: ReadonlyArray<RegExp> = [
  /指定受试者/,
  /指定行动/,
  /指定父规则/,
  /指定对象/,
  /待补充/,
  /未解析/,
  /TODO/,
  /FIXME/,
  /XXX/,
  /TBD/,
];

/** 正确结果泄漏模式：把 fixture 结论直接写进参与者文字 */
const ANSWER_LEAK_PATTERNS: ReadonlyArray<RegExp> = [
  /是新增|为新增/,
  /是删除|为删除/,
  /明确障碍(是|为|：|：)UAT-0[1-6]/,
  /资料缺口(是|为|：|：)UAT-0[1-6]/,
];

const ROUTES = [
  "/today",
  "/board?stage=screening",
  "/protocols",
  "/subjects?subject=subject-uat-03-gap_conflict&stage=screening",
  "/workbench?episode=episode-uat-03-screening-gap_conflict&component=component-ex-01",
  "/actions?action=action-uat-03-screening-gap-professional",
  "/tasks",
  "/reports",
  "/help",
];

test.describe("中文原生与无占位审计", () => {
  test("渲染文本不含工程内部词（允许临床专有缩写）", async ({ page }) => {
    test.skip((page.viewportSize()?.width ?? 0) < 1000, "桌面项目执行");
    for (const route of ROUTES) {
      await openRoute(page, route);
      const text = await page.locator("#main-content").innerText();
      for (const pattern of FORBIDDEN_TERMS) {
        const match = text.match(pattern);
        expect(
          match,
          `路由 ${route} 出现内部词「${match?.[0] ?? pattern}」`,
        ).toBeNull();
      }
    }
  });

  test("参与者任务卡无未解析占位，也不泄漏正确结果", () => {
    const runbook = fs.readFileSync(path.join(DOC_DIR, "user-uat-runbook.md"), "utf8");
    for (const pattern of PLACEHOLDER_PATTERNS) {
      expect(
        runbook.match(pattern),
        `任务卡出现占位「${pattern}」`,
      ).toBeNull();
    }
    for (const pattern of ANSWER_LEAK_PATTERNS) {
      expect(
        runbook.match(pattern),
        `任务卡可能泄漏答案「${pattern}」`,
      ).toBeNull();
    }
    for (const pattern of FORBIDDEN_TERMS) {
      expect(
        runbook.match(pattern),
        `任务卡出现内部词「${pattern}」`,
      ).toBeNull();
    }
  });

  test("14 项任务卡均含起始页与目标（无指定对象占位）", () => {
    const runbook = fs.readFileSync(path.join(DOC_DIR, "user-uat-runbook.md"), "utf8");
    // 按标题切分任务卡（m 标志：^ 匹配行首）
    const cards = runbook.split(/^### /m).filter((part) => /^\d+\./.test(part));
    expect(cards, "应恰好存在 14 个任务卡").toHaveLength(14);
    for (let index = 0; index < cards.length; index += 1) {
      const card = cards[index];
      expect(card, `任务卡 ${index + 1} 应写明起始页`).toMatch(/起始页/);
      expect(card, `任务卡 ${index + 1} 应写明目标`).toMatch(/目标/);
    }
  });

  test("帮助页显示稳定中文页面版本，可在任务卡与记录表直接照录", async ({
    page,
  }) => {
    test.skip((page.viewportSize()?.width ?? 0) < 1000, "桌面项目执行");
    await openRoute(page, "/help");
    const version = await page.locator(".page-head__meta").innerText();
    expect(version).toMatch(/^页面版本：界面试用版 \d+\.\d+\.\d+$/);
    // 记录表版本照录说明与帮助页一致
    const recordTemplate = fs.readFileSync(
      path.join(DOC_DIR, "user-uat-record-template.md"),
      "utf8",
    );
    expect(recordTemplate).toMatch(/页面版本（由记录人员填写）/);
    expect(recordTemplate).toMatch(/界面试用版 \d+\.\d+\.\d+/);
  });
});
