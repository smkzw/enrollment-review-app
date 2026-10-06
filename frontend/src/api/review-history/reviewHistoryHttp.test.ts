import { describe, expect, it } from "vitest";
import { decodeReviewHistoryRunDetail } from "./reviewHistoryHttp";

function wire() {
  const identity = { context_id: "context", review_run_id: "run", stage: "screening",
    workflow_stage_id: null, episode_revision: 1, protocol_version_id: "protocol",
    rule_set_id: "rules", rule_set_revision: 1, evidence_snapshot_v2_id: "snapshot",
    complete_processing_revision_id: "processing" };
  const at = "2026-10-03T00:00:00Z";
  return {
    run: { ...identity, status: "completed", started_at: at, completed_at: at, supersedes_review_run_id: null },
    context: { ...identity, created_at: at, evaluator_version: "synthetic/v1", project_id: "project",
      subject_id: "subject", review_episode_id: "episode", rule_set_sha256: "a".repeat(64),
      clause_pack_sha256: "b".repeat(64), protocol_integrity_gate_result_id: "gate",
      fact_count: 0, expectation_count: 0, conflict_group_count: 0, judgment_search_count: 0,
      subject_code: "合成个例", project_name: "合成项目", center_code: null, center_name: null,
      official_protocol_version: "1", workflow_stage_label: "筛选期" },
    assessments: [], actions: [], missing_rule_component_ids: [], evidence_locators: [], controls: [],
    missing_protocol_control_ids: [], control_selection_records: [],
    restricted_requirements: [{ origin: "control", requirement_id: "limited", display_label: "方案补充要求",
      title: "持续期间", source_text: "核对持续期间。", source_span_ids: ["span"],
      source_excerpts: ["核对持续期间。"], scope_quote: "符合相应定义时", time_words: ["筛选时"],
      exception_words: "特殊情况除外", affected_stage: "筛选期至治疗结束",
      decision_functions: ["time_validity"], source_force: "prohibited",
      limitation_kind: "consumer_unavailable", unresolved_dimensions: ["期间计算尚未支持"], dependency_refs: [] as string[] }],
  };
}

describe("冻结报告中的方案限制", () => {
  it("保留来源及能力限制，不制造判定或医学补证", () => {
    const input = wire();
    const before = JSON.stringify(input);
    const report = decodeReviewHistoryRunDetail(input);
    expect(report.restrictedRequirements[0]).toMatchObject({
      origin: "control", sourceSpanIds: ["span"], exceptionWords: "特殊情况除外",
      affectedStage: "筛选期至治疗结束", sourceForce: "prohibited", decisionFunctions: ["time_validity"],
      limitationKind: "consumer_unavailable",
    });
    expect(report.assessments).toEqual([]);
    expect(report.actions).toEqual([]);
    expect(JSON.stringify(input)).toBe(before);
  });
  it.each(["limitation_kind", "source_span_ids", "source_excerpts", "unresolved_dimensions"])("拒绝损坏字段 %s", (field) => {
    const input = wire();
    Object.assign(input.restricted_requirements[0]!, { [field]: field === "limitation_kind" ? "satisfied" : [] });
    expect(() => decodeReviewHistoryRunDetail(input)).toThrow();
  });
  it("拒绝重复身份和未列明的依赖", () => {
    const input = wire();
    input.restricted_requirements.push({ ...input.restricted_requirements[0]! });
    expect(() => decodeReviewHistoryRunDetail(input)).toThrow("身份不一致");
    input.restricted_requirements.pop();
    input.restricted_requirements[0]!.dependency_refs = ["missing"];
    expect(() => decodeReviewHistoryRunDetail(input)).toThrow("身份不一致");
  });
  it("旧冻结记录没有限制时由现行接口返回明确空列表", () => {
    const input = wire();
    input.restricted_requirements = [];
    expect(decodeReviewHistoryRunDetail(input).restrictedRequirements).toEqual([]);
    delete (input as Record<string, unknown>).restricted_requirements;
    expect(() => decodeReviewHistoryRunDetail(input)).toThrow();
  });
});
