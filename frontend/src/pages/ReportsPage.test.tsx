// @vitest-environment jsdom
/**
 * 报告组件测试：三个报告入口与界面试用说明（不生成真实文件）。
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, beforeEach } from "vitest";
import { ReportsPage } from "./ReportsPage";

describe("报告", () => {
  beforeEach(() => {
    window.location.hash = "";
  });

  it("提供个例、中心与项目三个报告入口", async () => {
    render(<ReportsPage />);
    expect(await screen.findByRole("heading", { name: "报告" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "个例报告" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "中心报告" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "项目报告" })).toBeInTheDocument();
  });

  it("点击生成报告显示界面试用说明，不生成真实文件", async () => {
    const user = userEvent.setup();
    render(<ReportsPage />);
    await screen.findByRole("heading", { name: "报告" });
    await user.click(screen.getAllByRole("button", { name: "生成报告" })[0]);
    expect(
      screen.getByText(/“个例报告”将在后续阶段提供生成与导出功能，当前不会生成文件。/),
    ).toBeInTheDocument();
  });
});
