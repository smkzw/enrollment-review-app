// @vitest-environment jsdom
/**
 * 顶栏组件测试：中文项目展示名派生（视觉缺陷 1 的显示层回归）。
 * 不得暴露原始项目代号 SYNTHETIC-001-III；帮助入口保持可达。
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it, beforeEach } from "vitest";
import { TopBar } from "./TopBar";

describe("顶栏", () => {
  beforeEach(() => {
    window.location.hash = "";
  });

  it("显示中文项目展示名与方案版本，不暴露原始项目代号", async () => {
    render(<TopBar positionLabel="今日工作" />);
    expect(
      await screen.findByText("界面试用项目 · III期"),
    ).toBeInTheDocument();
    expect(screen.getByText("方案 V1.0")).toBeInTheDocument();
    expect(screen.queryByText(/SYNTHETIC/)).not.toBeInTheDocument();
    expect(screen.queryByText(/SYNTHETIC-001-III/)).not.toBeInTheDocument();
  });

  it("显示当前位置与帮助入口", async () => {
    render(<TopBar positionLabel="入排工作台" />);
    expect(await screen.findByText("入排工作台")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "打开系统帮助" })).toHaveAttribute(
      "href",
      "#/help",
    );
  });
});
