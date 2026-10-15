// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { draftComparisonFixture } from "../../fixtures/protocol-deconstruction-workbench";
import { ProtocolFeedbackDialog } from "./ProtocolRedoDialogs";

describe("方案草稿局部纠错", () => {
  it("撤下重复待核来源必须显式选择，改选要求后不沿用该请求", async () => {
    const user = userEvent.setup();
    const content = structuredClone(draftComparisonFixture.candidate.content) as Record<string, unknown>;
    const rule = (content.proposed_rules as Array<Record<string, unknown>>)[0]!;
    rule.restricted_components = [{ rule_component_id: "duplicate-holder", display_code: "IN-01待核",
      title: "重复来源", source_span_ids: ["source-1"], source_excerpts: ["原文"],
      limitation_kind: "consumer_unavailable", unresolved_dimensions: ["未装配"] }];
    const onSubmit = vi.fn();
    render(<ProtocolFeedbackDialog open busy={false} candidateContent={content}
      onClose={() => undefined} onSubmit={onSubmit} />);
    await user.click(screen.getByRole("radio", { name: /原文理解纠错/ }));
    await user.selectOptions(screen.getByRole("combobox", { name: "需要纠正的具体要求" }), "duplicate-holder");
    await user.click(screen.getByRole("checkbox", { name: "撤下已由其他要求完整承担的重复待核项" }));
    await user.type(screen.getByRole("textbox", { name: "具体意见（必填）" }), "来源已由独立要求承担，条件不变");
    await user.click(screen.getByRole("button", { name: "提交反馈修订" }));
    expect(onSubmit).toHaveBeenLastCalledWith(expect.objectContaining({
      retireRedundantSource: true, targetComponentId: "duplicate-holder",
    }));
    await user.selectOptions(screen.getByRole("combobox", { name: "需要纠正的具体要求" }), "");
    expect(screen.queryByRole("checkbox", { name: "撤下已由其他要求完整承担的重复待核项" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("checkbox", { name: "仅核对总标题与各子项适用节点，不修改条件" }));
    await user.click(screen.getByRole("button", { name: "提交反馈修订" }));
    expect(onSubmit).toHaveBeenLastCalledWith(expect.objectContaining({ reviewParentScope: true }));
    expect(onSubmit.mock.lastCall?.[0]).not.toHaveProperty("retireRedundantSource");
  });
  it("总标题核对使用独立请求，不冒充单个子项的修改权限", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<ProtocolFeedbackDialog open busy={false}
      candidateContent={draftComparisonFixture.candidate.content}
      onClose={() => undefined} onSubmit={onSubmit} />);
    await user.click(screen.getByRole("radio", { name: /原文理解纠错/ }));
    await user.click(screen.getByRole("checkbox", { name: "仅核对总标题与各子项适用节点，不修改条件" }));
    expect(screen.queryByRole("combobox", { name: "需要纠正的具体要求" })).not.toBeInTheDocument();
    await user.type(screen.getByRole("textbox", { name: "具体意见（必填）" }), "核对总标题是否分别说明节点");
    await user.click(screen.getByRole("button", { name: "提交反馈修订" }));
    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ kind: "source_error", reviewParentScope: true, targetComponentId: null }));
  });
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
