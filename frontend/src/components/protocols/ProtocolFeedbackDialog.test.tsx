// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { draftComparisonFixture } from "../../fixtures/protocol-deconstruction-workbench";
import { ProtocolFeedbackDialog } from "./ProtocolRedoDialogs";

describe("方案草稿局部纠错", () => {
  it("同条标准有多项要求时必须选定具体子项", async () => {
    const user = userEvent.setup();
    const content = structuredClone(draftComparisonFixture.candidate.content) as Record<string, unknown>;
    const rule = (content.proposed_rules as Array<Record<string, unknown>>)[0]!;
    const first = (rule.components as Array<Record<string, unknown>>)[0]!;
    rule.components = [first, {
      ...first,
      rule_component_id: "component-in-second",
      display_code: "IN-01b",
      title: "第二项独立要求",
    }];
    const onSubmit = vi.fn();
    render(<ProtocolFeedbackDialog open busy={false} candidateContent={content}
      onClose={() => undefined} onSubmit={onSubmit} />);

    await user.click(screen.getByRole("radio", { name: /原文理解纠错/ }));
    await user.type(screen.getByRole("textbox", { name: "具体意见（必填）" }), "第二项适用范围需要核对");
    const submit = screen.getByRole("button", { name: "提交反馈修订" });
    expect(submit).toBeDisabled();
    await user.selectOptions(screen.getByRole("combobox", { name: "需要纠正的具体要求" }), "component-in-second");
    await user.click(submit);
    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
      kind: "source_error",
      targetRuleCode: "IN-01",
      targetComponentId: "component-in-second",
    }));
  });
});
