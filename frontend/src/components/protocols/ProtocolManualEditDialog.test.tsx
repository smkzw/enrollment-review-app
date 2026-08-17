// @vitest-environment jsdom
/**
 * 手工修订弹层组件测试（Slice 6）。
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ProtocolManualEditDialog } from "./ProtocolRedoDialogs";
import { draftComparisonFixture } from "../../fixtures/protocol-deconstruction-workbench";

describe("ProtocolManualEditDialog", () => {
  it("列出候选子项并提交修订值", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(
      <ProtocolManualEditDialog
        open
        busy={false}
        candidateContent={draftComparisonFixture.candidate.content}
        onClose={() => undefined}
        onSubmit={onSubmit}
      />,
    );
    expect(screen.getByRole("heading", { name: "手工修订草稿" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "修订子项" })).toBeInTheDocument();
    const titleInput = screen.getByRole("textbox", { name: "子项标题" });
    await user.clear(titleInput);
    await user.type(titleInput, "年龄要求（修订）");
    await user.click(screen.getByRole("button", { name: "提交手工修订" }));
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        componentId: "component-in",
        patch: expect.objectContaining({
          title: "年龄要求（修订）",
          predicate: expect.objectContaining({ attribute: "年龄" }),
          requirements: expect.arrayContaining([
            expect.objectContaining({ dueStage: "screening" }),
          ]),
        }),
      }),
    );
    expect(screen.getByText("方案原文（只读）")).toBeInTheDocument();
  });

  it("关闭按钮触发 onClose 且不提交", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    const onClose = vi.fn();
    render(
      <ProtocolManualEditDialog
        open
        busy={false}
        candidateContent={draftComparisonFixture.candidate.content}
        onClose={onClose}
        onSubmit={onSubmit}
      />,
    );
    await user.click(screen.getByRole("button", { name: "先不要" }));
    expect(onClose).toHaveBeenCalled();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("Escape 键关闭弹层", async () => {
    const onClose = vi.fn();
    render(
      <ProtocolManualEditDialog
        open
        busy={false}
        candidateContent={draftComparisonFixture.candidate.content}
        onClose={onClose}
        onSubmit={() => undefined}
      />,
    );
    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalled();
  });

  it("关闭状态不渲染弹层", () => {
    render(
      <ProtocolManualEditDialog
        open={false}
        busy={false}
        candidateContent={draftComparisonFixture.candidate.content}
        onClose={() => undefined}
        onSubmit={() => undefined}
      />,
    );
    expect(screen.queryByRole("heading", { name: "手工修订草稿" })).not.toBeInTheDocument();
  });
});
