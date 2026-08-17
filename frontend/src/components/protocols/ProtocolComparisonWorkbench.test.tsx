// @vitest-environment jsdom
/**
 * 重新解构并列差异工作台组件测试（Slice 6）。
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ProtocolComparisonWorkbench } from "./ProtocolComparisonWorkbench";
import { draftComparisonFixture, protocolRedoSessionFixture } from "../../fixtures/protocol-deconstruction-workbench";

function renderWorkbench() {
  return render(
    <ProtocolComparisonWorkbench
      session={protocolRedoSessionFixture}
      comparison={draftComparisonFixture}
      saving={false}
      feedbackBusy={false}
      onSaveDraft={() => undefined}
      onOpenFeedback={() => undefined}
      onOpenManualEdit={() => undefined}
      onCancel={() => undefined}
      onPublish={() => undefined}
    />,
  );
}

describe("重新解构并列差异工作台", () => {
  it("展示目标项目与正式版本摘要", () => {
    renderWorkbench();
    expect(screen.getByRole("heading", { name: /并列比较差异/ })).toBeInTheDocument();
    expect(screen.getAllByText(/测试研究/).length).toBeGreaterThan(0);
    expect(screen.getAllByText("当前正式版本", { exact: true }).length).toBeGreaterThan(0);
    expect(screen.getAllByText("新草稿", { exact: true }).length).toBeGreaterThan(0);
  });

  it("逐条展示八类差异：IN-01 原文与逻辑变化", () => {
    renderWorkbench();
    expect(screen.getAllByText("IN-01").length).toBeGreaterThan(0);
    expect(screen.getAllByText("原文").length).toBeGreaterThan(0);
    expect(screen.getAllByText("逻辑").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/年龄≥18岁/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/年龄≥18周岁且≤65周岁/).length).toBeGreaterThan(0);
  });

  it("提供保存、反馈修订、手工修订、取消与发布操作", () => {
    renderWorkbench();
    expect(screen.getByRole("button", { name: "保存草稿" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "基于反馈修订" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "手工修订" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "取消" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "发布" })).toBeInTheDocument();
  });

  it("筛选项默认只显示有变化的规则", () => {
    renderWorkbench();
    const changedButton = screen.getByRole("button", { name: /仅显示有变化的规则/ });
    expect(changedButton).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: /全部规则/ })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });
});
