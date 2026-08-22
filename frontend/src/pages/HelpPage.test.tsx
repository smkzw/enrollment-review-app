// @vitest-environment jsdom
/**
 * 系统帮助组件测试：步骤化说明覆盖全部主题，且不出现内部实现词。
 * 另覆盖：页面版本显示、两步复位（取消不变 / 确认只删登记键并回到今日工作）。
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, beforeEach } from "vitest";
import {
  resetUatTrialState,
  UAT_KEY_CREATED_PROJECT,
  UAT_KEY_MANUAL_ACTIONS,
  UAT_KEY_PROTOCOL_DRAFT_SAVED,
  UAT_KEY_TASK_PROGRESS,
  UAT_PAGE_VERSION,
} from "../app/uatTrialState";
import { helpSectionsForMode, HelpPage } from "./HelpPage";

describe("系统帮助", () => {
  beforeEach(() => {
    window.location.hash = "";
    window.sessionStorage.clear();
  });

  it("提供分步骤帮助并覆盖核心主题", async () => {
    render(<HelpPage />);
    expect(await screen.findByRole("heading", { name: "系统帮助" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /从这里开始：认识界面/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /今日工作：今天先做什么/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /项目看板：查看全部受试者/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /查看受试者资料与风险/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /上传资料与核对原件/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /入排工作台：规则、判断与证据/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /行动中心：谁负责、补什么、何时完成/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /任务与系统：资料整理进度/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /方案工作台：首次解构与重新解构/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /常见问题：重新解构与发布/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /键盘操作/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /遇到问题怎么办/ })).toBeInTheDocument();
    expect(screen.getByText(/建立完整资料快照/)).toBeInTheDocument();
    expect(screen.getByText(/红框只表示系统掌握了可映射到原件页图的真实区域坐标/)).toBeInTheDocument();
    expect(screen.getByText(/失败时只重新处理失败部分/)).toBeInTheDocument();
    expect(screen.getAllByText(/补入漏识别文字/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/页首、页末或原文中已选位置/).length).toBeGreaterThan(0);
  });

  it("说明中没有内部实现词", async () => {
    render(<HelpPage />);
    await screen.findByRole("heading", { name: "系统帮助" });
    const body = document.body.textContent ?? "";
    for (const forbidden of ["Gate", "Agent", "schema", "hash", "log", "stub", "pipeline", "API", "key", "sessionStorage", "fixture", "reset"]) {
      expect(body).not.toContain(forbidden);
    }
  });

  it("正式模式帮助只介绍当前可用流程", () => {
    const formalText = helpSectionsForMode(false)
      .flatMap((section) => [section.title, ...section.steps, section.tip ?? ""])
      .join("\n");
    expect(formalText).toContain("打开系统后直接进入「方案工作台」");
    expect(formalText).toContain("还没有当前有效资料");
    expect(formalText).not.toMatch(/界面试用|演示|今日工作|项目看板|行动中心|任务与系统/);
  });

  it("显示稳定中文页面版本，可直接照录", async () => {
    render(<HelpPage />);
    await screen.findByRole("heading", { name: "系统帮助" });
    expect(screen.getByText(new RegExp(`界面版本：${UAT_PAGE_VERSION}`))).toBeInTheDocument();
    expect(UAT_PAGE_VERSION).toMatch(/^界面试用版 \d+\.\d+\.\d+$/);
  });

  it("首次点击只打开确认界面，不改变任何状态", async () => {
    window.sessionStorage.setItem(UAT_KEY_MANUAL_ACTIONS, "x");
    window.sessionStorage.setItem("unrelated:preference", "keep");
    const user = userEvent.setup();
    render(<HelpPage />);
    await screen.findByRole("heading", { name: "系统帮助" });

    await user.click(screen.getByRole("button", { name: "开始新的界面试用" }));

    expect(screen.getByRole("dialog", { name: "开始新的界面试用" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "确认并回到今日工作" })).toBeInTheDocument();
    expect(window.sessionStorage.getItem(UAT_KEY_MANUAL_ACTIONS)).toBe("x");
    expect(window.sessionStorage.getItem("unrelated:preference")).toBe("keep");
  });

  it("取消复位不改变任何状态，也不离开页面", async () => {
    window.sessionStorage.setItem(UAT_KEY_MANUAL_ACTIONS, "x");
    window.sessionStorage.setItem(UAT_KEY_TASK_PROGRESS, "y");
    window.sessionStorage.setItem("unrelated:preference", "keep");
    const user = userEvent.setup();
    render(<HelpPage />);
    await screen.findByRole("heading", { name: "系统帮助" });

    await user.click(screen.getByRole("button", { name: "开始新的界面试用" }));
    await user.click(screen.getByRole("button", { name: "先不要" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(window.sessionStorage.getItem(UAT_KEY_MANUAL_ACTIONS)).toBe("x");
    expect(window.sessionStorage.getItem(UAT_KEY_TASK_PROGRESS)).toBe("y");
    expect(window.sessionStorage.getItem("unrelated:preference")).toBe("keep");
    expect(window.location.hash).toBe("");
  });

  it("确认复位只删除登记键，保留无关键，并回到今日工作", async () => {
    window.sessionStorage.setItem(UAT_KEY_MANUAL_ACTIONS, "x");
    window.sessionStorage.setItem(UAT_KEY_CREATED_PROJECT, "y");
    window.sessionStorage.setItem(UAT_KEY_PROTOCOL_DRAFT_SAVED, "true");
    window.sessionStorage.setItem(UAT_KEY_TASK_PROGRESS, "z");
    window.sessionStorage.setItem("unrelated:preference", "keep");
    const user = userEvent.setup();
    render(<HelpPage />);
    await screen.findByRole("heading", { name: "系统帮助" });

    await user.click(screen.getByRole("button", { name: "开始新的界面试用" }));
    await user.click(screen.getByRole("button", { name: "确认并回到今日工作" }));

    expect(window.sessionStorage.getItem(UAT_KEY_MANUAL_ACTIONS)).toBeNull();
    expect(window.sessionStorage.getItem(UAT_KEY_CREATED_PROJECT)).toBeNull();
    expect(window.sessionStorage.getItem(UAT_KEY_PROTOCOL_DRAFT_SAVED)).toBeNull();
    expect(window.sessionStorage.getItem(UAT_KEY_TASK_PROGRESS)).toBeNull();
    expect(window.sessionStorage.getItem("unrelated:preference")).toBe("keep");
    expect(window.location.hash).toBe("#/today");
  });

  it("复位函数自身保证空会话不报错", () => {
    expect(() => resetUatTrialState()).not.toThrow();
  });
});
