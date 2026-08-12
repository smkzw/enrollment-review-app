/// <reference types="node" />
/**
 * 页面宽度合同测试（合同 §3.2/§3.3）：页面消费 AppShell 全宽，
 * 1920 宽与 200% 缩放下不因固定 max-width 产生空白或页面级横向滚动；
 * 密集矩阵只在表格容器内横向滚动。
 * jsdom 无法测量布局，本测试直接校验样式契约（布局行为的唯一单元级证据）。
 * 注意：@media/@container 断点中的 max-width 是响应式断点，不是页面宽度上限。
 */

import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const read = (file: string): string =>
  readFileSync(new URL(file, import.meta.url), "utf8");

/** 提取 CSS 声明中的 max-width（跳过 @media/@container 断点写法） */
const maxWidthDeclarations = (css: string): string[] =>
  css.match(/(?:^|[;{}])\s*max-width\s*:\s*([^;}]+);/g) ?? [];

describe("页面宽度合同：无页面级宽度上限", () => {
  it("今日工作页样式无 max-width 声明（页面全宽）", () => {
    const css = read("./today.css");
    expect(maxWidthDeclarations(css)).toEqual([]);
  });

  it("项目看板页无页面级宽度上限；仅受试者检索输入保留 max-width:100%", () => {
    const css = read("./board.css");
    const caps = maxWidthDeclarations(css);
    const pageCaps = caps.filter((declaration) => !declaration.includes("100%"));
    expect(pageCaps).toEqual([]);
  });

  it("密集矩阵保留组件内横向滚动（.board-table-wrap overflow-x: auto）", () => {
    const css = read("./board.css");
    const wrapRule = css.match(/\.board-table-wrap\s*\{[^}]*\}/)?.[0] ?? "";
    expect(wrapRule).toMatch(/overflow-x:\s*auto/);
    expect(wrapRule).not.toMatch(/overflow:\s*hidden/);
  });

  it("全局壳主工作区为容器查询全宽，无 max-width 声明", () => {
    const css = read("./shell.css");
    expect(maxWidthDeclarations(css)).toEqual([]);
    const contentRule =
      css.match(/\.app-shell__content\s*\{[^}]*\}/)?.[0] ?? "";
    expect(contentRule).toMatch(/container-type:\s*inline-size/);
    expect(contentRule).toMatch(/width:\s*100%/);
  });
});
