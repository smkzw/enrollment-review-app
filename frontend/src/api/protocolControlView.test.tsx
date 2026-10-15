// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { normalizeProtocolControlRequirements } from "./protocolControlView";
import { ProtocolControlPanel } from "../components/protocols/ProtocolControlPanel";
import { ProtocolWorkbenchApiError } from "./protocolWorkbenchTypes";

function payload(scopeCitation?: unknown) {
  return {
    job_id: "control-job", source_job_id: "source-job", checkpoint_id: "checkpoint",
    workflow_stages: [{ workflow_stage_id: "screening", display_name: "筛选期" }],
    relation_target_labels: {}, calculation_gaps: [], restricted_statements: [],
    candidates: [{
      control_candidate_id: "control-1", title: "核对检查完成记录", applicable_population: "本次筛选的受试者",
      semantics: {
        control_candidate_id: "control-1", title: "核对检查完成记录", applicable_population: "本次筛选的受试者",
        applicability_expression: null, trigger_expression: null, exception_expression: null,
        obligation_expression: { groups: [{
          obligation_group_id: "obligation-1", applies_to_trigger_branch_ids: [], activated_by_exception_group_ids: [],
          atoms: [{
            statement: "完成检查记录。", source_excerpts: ["完成检查记录。"], requires_professional_judgment: false,
            time_constraint: null, modality: "mandatory", temporal_scope: null,
            prospective_period: null, continuing_obligation: null,
          }],
        }] },
        review_node_bindings: [{
          workflow_stage_id: "screening", role: "decide_at_node", guidance: null,
          ...(scopeCitation === undefined ? {} : { scope_citation: scopeCitation }),
        }], minimum_evidence: [], cross_source_relations: [],
      },
    }],
  };
}

const scopeCitation = {
  structure_unit_id: "body.p10", source_span_ids: ["span.p10"],
  source_excerpt: "筛选期", source_unit_sha256: "a".repeat(64),
};

const restricted = {
  restricted_statement_id: "restricted:1", source_structure_unit_id: "body.p20",
  source_statement_index: 0, source_span_ids: ["span.p20"],
  source_quote: "先前阶段治疗者不得入组", limitation_kind: "interpretation_unresolved",
  unresolved_dimensions: ["“先前阶段”具体范围尚未核清"], dependency_refs: [],
  scope_quote: "本次筛选", time_words: ["给药前"], exception_words: "已完成规定洗脱者除外",
  affected_stage: "筛选期", source_force: "prohibited", decision_functions: ["exception"],
};

afterEach(cleanup);

describe("补充要求审核时期的独立原文依据", () => {
  it("混合已核要求与未决来源均可查看，不把限制改成满足或病例缺件", () => {
    const data = normalizeProtocolControlRequirements({ ...payload(), restricted_statements: [restricted] });
    expect(data.requirements).toHaveLength(1);
    expect(data.restrictedStatements[0].sourceSpanIds).toEqual(["span.p20"]);
    render(<ProtocolControlPanel controls={{
      state: { sourceJobId: "source-job", draftRevisionId: "draft", status: "ready", data },
      retry: vi.fn(), retryFailed: vi.fn(async () => {}), retrying: false,
    }} />);
    expect(screen.getByText(/另有1段方案原文尚不能自动核对/)).toBeVisible();
    expect(screen.getByText("核对检查完成记录")).toBeVisible();
    expect(screen.getByText(restricted.source_quote)).toBeVisible();
    expect(screen.getByText(restricted.scope_quote)).toBeVisible();
    expect(screen.getByText(restricted.exception_words)).toBeVisible();
    expect(screen.getByText(/不代表受试者缺少资料/)).toBeVisible();
    expect(screen.queryByText("body.p20")).toBeNull();
    expect(screen.queryByText("prohibited")).toBeNull();
  });

  it("只有受限原文时不显示为没有额外要求", () => {
    const data = normalizeProtocolControlRequirements({
      ...payload(), candidates: [], restricted_statements: [{ ...restricted, limitation_kind: "consumer_unavailable" }],
    });
    render(<ProtocolControlPanel controls={{
      state: { sourceJobId: "source-job", draftRevisionId: "draft", status: "ready", data },
      retry: vi.fn(), retryFailed: vi.fn(async () => {}), retrying: false,
    }} />);
    expect(screen.getByText(/核对方法尚未接通/)).toBeVisible();
    expect(screen.queryByText("本次整理未列出额外审核要求。")).toBeNull();
  });

  it.each([
    undefined, [{ ...restricted, source_span_ids: [] }],
    [{ ...restricted, unresolved_dimensions: [] }],
    [{ ...restricted, source_statement_index: -1 }],
    [{ ...restricted, dependency_refs: ["missing"] }],
    [{ ...restricted, limitation_kind: "satisfied" }], [restricted, restricted],
  ])("漏字段或损坏受限来源不能被隐藏为正常要求", (rows) => {
    expect(() => normalizeProtocolControlRequirements({ ...payload(), restricted_statements: rows }))
      .toThrow(ProtocolWorkbenchApiError);
  });

  it("依赖指向同一份受限包的具体条目而非内部编号", () => {
    const data = normalizeProtocolControlRequirements({ ...payload(), restricted_statements: [restricted, {
      ...restricted, restricted_statement_id: "restricted:2", source_statement_index: 1,
      dependency_refs: [restricted.restricted_statement_id],
    }] });
    expect(data.restrictedStatements[1].dependencyLabels).toEqual(["待核原文1"]);
  });
  it("保留标题的实际来源，不把标题拼进操作原文", () => {
    const requirement = normalizeProtocolControlRequirements(payload(scopeCitation)).requirements[0];
    expect(requirement.nodes[0].scopeSource).toEqual({
      structureUnitId: "body.p10", sourceSpanIds: ["span.p10"], excerpt: "筛选期", sourceHash: "a".repeat(64),
    });
    expect(requirement.obligations[0].atoms[0].excerpts).toEqual(["完成检查记录。"]);
  });

  it.each([undefined, null])("兼容未另列标题引用的既有记录：%s", (citation) => {
    expect(normalizeProtocolControlRequirements(payload(citation)).requirements[0].nodes[0].scopeSource).toBeNull();
  });

  it.each([
    { ...scopeCitation, source_span_ids: [] },
    { ...scopeCitation, source_span_ids: ["span.p10", "span.p10"] },
    { ...scopeCitation, source_excerpt: "" },
    { ...scopeCitation, structure_unit_id: "" },
    { ...scopeCitation, source_unit_sha256: "unknown" },
  ])("存在但损坏的时期引用不能被静默隐藏", (citation) => {
    expect(() => normalizeProtocolControlRequirements(payload(citation))).toThrow(ProtocolWorkbenchApiError);
  });

  it("补充要求展开后可单独查阅审核时期原文，不展示内部标识", () => {
    const data = normalizeProtocolControlRequirements(payload(scopeCitation));
    render(<ProtocolControlPanel controls={{
      state: { sourceJobId: "source-job", draftRevisionId: "draft-1", status: "ready", data },
      retry: vi.fn(), retryFailed: vi.fn(async () => {}), retrying: false,
    }} />);
    fireEvent.click(screen.getByText("核对检查完成记录"));
    const summary = screen.getByText("审核时期原文");
    fireEvent.click(summary);
    expect(summary.closest("details")).toHaveAttribute("open");
    expect(summary.parentElement?.querySelector("blockquote")?.textContent).toBe("筛选期");
    expect(screen.queryByText("body.p10")).toBeNull();
    expect(screen.queryByText("span.p10")).toBeNull();
  });
});
