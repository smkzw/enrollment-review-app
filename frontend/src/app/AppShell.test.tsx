// @vitest-environment jsdom
/**
 * 全局壳组件测试：无登录导航、默认首屏、页面切换、移动抽屉键盘路径。
 * 使用真实 stub 仓储（fixture/v1），覆盖工作项验收“navigation”行为。
 */

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, beforeEach } from "vitest";
import { App } from "../App";

async function renderApp() {
  const user = userEvent.setup();
  render(<App />);
  // 默认首屏：今日工作加载完成
  await screen.findByRole("heading", { name: "今日工作" });
  return user;
}

describe("全局壳与导航", () => {
  beforeEach(() => {
    window.location.hash = "";
  });

  it("无登录直达今日工作，不出现登录入口", async () => {
    await renderApp();
    expect(
      screen.queryByText(/登录|账号|密码/i),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "今日工作" })).toBeInTheDocument();
  });

  it("侧栏显示已实现的一级入口并标出当前位置", async () => {
    await renderApp();
    const nav = screen.getByRole("navigation", { name: "主要功能" });
    expect(within(nav).getByRole("link", { name: "今日工作" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(
      within(nav).getByRole("link", { name: "项目看板" }),
    ).toBeInTheDocument();
  });

  it("点击项目看板切换到看板页并更新当前位置", async () => {
    const user = await renderApp();
    await user.click(screen.getByRole("link", { name: "项目看板" }));
    await screen.findByRole("heading", { name: "项目看板" });
    expect(window.location.hash).toMatch(/^#\/board/);
    const nav = screen.getByRole("navigation", { name: "主要功能" });
    expect(within(nav).getByRole("link", { name: "项目看板" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(
      screen.getByText(/当前位置/).parentElement,
    ).toHaveTextContent("项目看板");
  });

  it("移动抽屉：菜单按钮打开，Escape 关闭并返回焦点", async () => {
    const user = await renderApp();
    const menuButton = screen.getByRole("button", { name: "打开菜单" });
    expect(menuButton).toHaveAttribute("aria-expanded", "false");
    await user.click(menuButton);
    expect(menuButton).toHaveAttribute("aria-expanded", "true");
    expect(document.querySelector(".side-nav__scrim")).toBeInTheDocument();
    await user.keyboard("{Escape}");
    await waitFor(() => {
      expect(menuButton).toHaveAttribute("aria-expanded", "false");
      expect(document.querySelector(".side-nav__scrim")).not.toBeInTheDocument();
    });
    expect(menuButton).toHaveFocus();
  });

  it("帮助入口存在且指向 /help（由后续工作项接入）", async () => {
    await renderApp();
    const help = screen.getByRole("link", { name: "打开系统帮助" });
    expect(help).toHaveAttribute("href", "#/help");
  });

  it("首次方案解构不显示无关的示例项目上下文", async () => {
    window.location.hash = "#/protocols";
    render(<App />);
    await screen.findByRole("heading", { name: "方案工作台" });
    expect(screen.queryByText(/界面试用项目/)).not.toBeInTheDocument();
    expect(screen.queryByText("方案 V1.0")).not.toBeInTheDocument();
  });
});
