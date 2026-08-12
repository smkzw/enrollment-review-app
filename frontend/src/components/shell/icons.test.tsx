// @vitest-environment jsdom
/**
 * 图标可访问性测试（合同 §7.1）：图标按钮必须有中文可访问名称与工具提示；
 * 图标本身为装饰性（aria-hidden），状态同时以文字呈现（§2.1 不只靠颜色）。
 * 图标统一来自 lucide-react（见 icons.tsx）。
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SideNav } from "./SideNav";
import {
  BlockingBadge,
  MainStatusBadge,
  TaskStateBadge,
} from "./StatusBadge";
import { ProjectBoardPage } from "../../pages/ProjectBoardPage";

const CHINESE = /[\u4e00-\u9fff]/;

describe("图标可访问性（合同 §7.1）", () => {
  it("侧栏图标按钮都有中文可访问名称与工具提示", () => {
    render(<SideNav currentPath="/today" />);
    const iconButtons = document.querySelectorAll(".icon-button");
    expect(iconButtons.length).toBeGreaterThan(0);
    iconButtons.forEach((button) => {
      expect(button.getAttribute("aria-label")).toMatch(CHINESE);
      expect(button.getAttribute("title")).toMatch(CHINESE);
    });
  });

  it("看板阶段单元格直达按钮都有中文可访问名称与工具提示", async () => {
    render(<ProjectBoardPage />);
    await screen.findByRole("table");
    const openLinks = document.querySelectorAll(".episode-cell__open");
    expect(openLinks.length).toBeGreaterThan(0);
    openLinks.forEach((link) => {
      expect(link.getAttribute("aria-label")).toMatch(/打开 .*审核/);
      expect(link.getAttribute("title")).toMatch(/打开 .*审核/);
    });
  });

  it("状态徽标：文字与图标同时呈现，图标为装饰性 aria-hidden", () => {
    render(
      <>
        <MainStatusBadge status="clear_barrier" />
        <BlockingBadge level="blocking" />
        <TaskStateBadge state="resumable" />
      </>,
    );
    const badges = document.querySelectorAll(".status-badge");
    expect(badges.length).toBe(3);
    badges.forEach((badge) => {
      expect(badge.textContent).toMatch(CHINESE);
      const svg = badge.querySelector("svg");
      expect(svg).not.toBeNull();
      expect(svg).toHaveAttribute("aria-hidden", "true");
    });
  });

  it("图标为 lucide 风格 svg（stroke 属性，非文本填充伪图标）", () => {
    render(<SideNav currentPath="/today" />);
    const svg = document.querySelector(".side-nav__menu-button svg");
    expect(svg).not.toBeNull();
    expect(svg).toHaveAttribute("stroke");
    expect(svg?.textContent ?? "").not.toMatch(/[\u4e00-\u9fff]/);
  });
});
