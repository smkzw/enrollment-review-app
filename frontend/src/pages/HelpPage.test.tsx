// @vitest-environment jsdom
/**
 * 系统帮助组件测试：步骤化说明覆盖全部主题，且不出现内部实现词。
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it, beforeEach } from "vitest";
import { HelpPage } from "./HelpPage";

describe("系统帮助", () => {
  beforeEach(() => {
    window.location.hash = "";
  });

  it("提供分步骤帮助并覆盖核心主题", async () => {
    render(<HelpPage />);
    expect(await screen.findByRole("heading", { name: "系统帮助" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /从这里开始：认识界面/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /今日工作：今天先做什么/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /项目看板：查看全部受试者/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /查看受试者资料与风险/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /入排工作台：规则、判断与证据/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /行动中心：谁负责、补什么、何时完成/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /任务与系统：资料整理进度/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /报告与方案/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /键盘操作/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /遇到问题怎么办/ })).toBeInTheDocument();
  });

  it("说明中没有内部实现词", async () => {
    render(<HelpPage />);
    await screen.findByRole("heading", { name: "系统帮助" });
    const body = document.body.textContent ?? "";
    for (const forbidden of ["Gate", "Agent", "schema", "hash", "log", "stub", "pipeline", "API"]) {
      expect(body).not.toContain(forbidden);
    }
  });
});
