/**
 * 重新解构差异 wire → ViewModel 映射单元测试（八类类别固定中文标签）。
 */

import { describe, expect, it } from "vitest";
import { normalizeProtocolDraftDiff } from "../api/protocolWorkbenchNormalize";
import type { ProtocolDraftDiffWire } from "../api/protocolWorkbenchTypes";
import { mapProtocolDraftDiff } from "./protocolDiffMapper";

function completeDiff(
  overrides: Partial<ProtocolDraftDiffWire> = {},
): ProtocolDraftDiffWire {
  return {
    added_rule_codes: [],
    removed_rule_codes: [],
    modified_rule_codes: [],
    added_workflow_stage_ids: [],
    removed_workflow_stage_ids: [],
    modified_workflow_stage_ids: [],
    changed_component_ids: [],
    changed_requirement_ids: [],
    changed_procedure_mapping_ids: [],
    source_scope_changed: false,
    workflow_visit_rewritten: false,
    clarification_semantics_changed: false,
    rule_diffs: [],
    ...overrides,
  };
}

const DIFF = completeDiff({
  added_rule_codes: [],
  removed_rule_codes: [],
  modified_rule_codes: ["IN-01"],
  rule_diffs: [
    {
      official_code: "IN-01",
      added: false,
      removed: false,
      added_component_refs: [],
      removed_component_refs: [],
      original_text_changes: [
        {
          stable_ref: "IN-01",
          kind: "rule",
          previous: { source_text: "年龄≥18岁" },
          current: { source_text: "年龄≥18周岁且≤65周岁" },
        },
      ],
      logic_changes: [
        {
          stable_ref: "IN-01a",
          kind: "component",
          previous: {
            kind: "predicate",
            predicate: {
              subject: "受试者",
              attribute: "年龄",
              comparator: "gte",
              value: 18,
              unit: "岁",
            },
          },
          current: {
            kind: "logical",
            operator: "all",
            children: [
              {
                kind: "predicate",
                predicate: {
                  subject: "受试者",
                  attribute: "年龄",
                  comparator: "gte",
                  value: 18,
                  unit: "岁",
                },
              },
              {
                kind: "predicate",
                predicate: {
                  subject: "受试者",
                  attribute: "年龄",
                  comparator: "lte",
                  value: 65,
                  unit: "岁",
                },
              },
            ],
          },
        },
      ],
      time_window_changes: [],
      exception_changes: [],
      evidence_changes: [
        {
          stable_ref: "IN-01a#req[1]",
          kind: "requirement",
          previous: null,
          current: {
            evidence: {
              fact_type: "年龄",
              required_source_types: ["病历"],
              allows_screening_record_transcription: true,
              requires_contemporaneous_objective_source: false,
              description: "核对年龄记录",
            },
          },
        },
      ],
      due_stage_changes: [],
    },
    {
      official_code: "EX-01",
      added: false,
      removed: false,
      added_component_refs: [],
      removed_component_refs: [],
      original_text_changes: [],
      logic_changes: [],
      time_window_changes: [],
      exception_changes: [],
      evidence_changes: [],
      due_stage_changes: [],
    },
  ],
});

describe("mapProtocolDraftDiff", () => {
  it("按官方编号逐条映射并保留八类中文标签", () => {
    const view = mapProtocolDraftDiff(DIFF);
    expect(view.modifiedRuleCodes).toEqual(["IN-01"]);
    expect(view.ruleDiffs).toHaveLength(2);
    const rule = view.ruleDiffs[0]!;
    expect(rule.officialCode).toBe("IN-01");
    expect(rule.hasChanges).toBe(true);
    expect(rule.changes).toHaveLength(3);
    const labels = rule.changes.map((change) => change.categoryLabel);
    expect(labels).toContain("原文");
    expect(labels).toContain("逻辑");
    expect(labels).toContain("证据要求");
    const evidence = rule.changes.find((change) => change.category === "evidence")!;
    expect(evidence.kind).toBe("requirement");
    expect(evidence.current).toEqual({
      evidence: {
        fact_type: "年龄",
        required_source_types: ["病历"],
        allows_screening_record_transcription: true,
        requires_contemporaneous_objective_source: false,
        description: "核对年龄记录",
      },
    });
  });

  it("无变化的父规则 hasChanges 为 false", () => {
    const view = mapProtocolDraftDiff(DIFF);
    const ex = view.ruleDiffs.find((rule) => rule.officialCode === "EX-01")!;
    expect(ex.hasChanges).toBe(false);
    expect(ex.changes).toHaveLength(0);
  });

  it("差异合同缺失或畸形时明确拒绝，不伪装成无差异", () => {
    expect(() => normalizeProtocolDraftDiff({
      rule_diffs: [null, { official_code: "" }, { official_code: 42 }],
      added_rule_codes: "not-a-list",
    })).toThrow(/数据不完整/);
  });

  it.each([
    [
      "空的并列逻辑",
      "logic_changes",
      { kind: "logical", operator: "all", children: [] },
    ],
    [
      "否定逻辑包含两个条件",
      "logic_changes",
      {
        kind: "logical",
        operator: "not",
        children: [
          { kind: "predicate", predicate: { subject: "受试者", attribute: "妊娠", comparator: "eq", value: true } },
          { kind: "predicate", predicate: { subject: "受试者", attribute: "哺乳", comparator: "eq", value: true } },
        ],
      },
    ],
    [
      "非法时间方向",
      "time_window_changes",
      [{
        scope: "main",
        time_constraint: { anchor_type: "randomization_date", direction: "around" },
        occurrence_window: null,
        prospective_window: null,
        prospective_period: null,
      }],
    ],
    [
      "非法时间单位",
      "time_window_changes",
      [{
        scope: "main",
        time_constraint: null,
        occurrence_window: { duration: { value: 3, unit: "quarter" }, minimum_count: 1 },
        prospective_window: null,
        prospective_period: null,
      }],
    ],
  ])("拒绝%s，不让页面猜测临床语义", (_label, category, payload) => {
    const rule = {
      official_code: "EX-01",
      added: false,
      removed: false,
      added_component_refs: [],
      removed_component_refs: [],
      original_text_changes: [],
      logic_changes: [],
      time_window_changes: [],
      exception_changes: [],
      evidence_changes: [],
      due_stage_changes: [],
      [category]: [{
        stable_ref: "EX-01a",
        kind: "component",
        previous: payload,
        current: payload,
      }],
    };
    expect(() => normalizeProtocolDraftDiff({ ...completeDiff(), rule_diffs: [rule] })).toThrow(/无法核对/);
  });

  it.each([
    ["父规则级证据变化", "rule", null, { evidence: {
      fact_type: "病史", required_source_types: ["既往病历"],
      allows_screening_record_transcription: true,
      requires_contemporaneous_objective_source: false,
      description: "核对既往病史",
    } }],
    ["双边同时存在的单条资料要求变化", "requirement", { evidence: {
      fact_type: "病史", required_source_types: ["既往病历"],
      allows_screening_record_transcription: true,
      requires_contemporaneous_objective_source: false,
      description: "原资料要求",
    } }, { evidence: {
      fact_type: "病史", required_source_types: ["既往病历"],
      allows_screening_record_transcription: true,
      requires_contemporaneous_objective_source: true,
      description: "新资料要求",
    } }],
  ])("拒绝%s", (_label, kind, previous, current) => {
    const rule = {
      official_code: "EX-01", added: false, removed: false,
      added_component_refs: [], removed_component_refs: [],
      original_text_changes: [], logic_changes: [], time_window_changes: [],
      exception_changes: [], due_stage_changes: [],
      evidence_changes: [{
        stable_ref: "EX-01a#req[1]", kind, previous, current,
      }],
    };
    expect(() => normalizeProtocolDraftDiff({ ...completeDiff(), rule_diffs: [rule] })).toThrow(/无法核对/);
  });

  it("新增/删除整条父规则正常映射", () => {
    const view = mapProtocolDraftDiff(completeDiff({
      added_rule_codes: ["IN-09"],
      removed_rule_codes: ["EX-04"],
      rule_diffs: [
        {
          official_code: "IN-09",
          added: true,
          removed: false,
          added_component_refs: ["IN-09a"],
          removed_component_refs: [],
          original_text_changes: [], logic_changes: [], time_window_changes: [],
          exception_changes: [], evidence_changes: [], due_stage_changes: [],
        },
        {
          official_code: "EX-04",
          added: false,
          removed: true,
          added_component_refs: [],
          removed_component_refs: ["EX-04a"],
          original_text_changes: [], logic_changes: [], time_window_changes: [],
          exception_changes: [], evidence_changes: [], due_stage_changes: [],
        },
      ],
    }));
    expect(view.addedRuleCodes).toEqual(["IN-09"]);
    expect(view.removedRuleCodes).toEqual(["EX-04"]);
    const added = view.ruleDiffs.find((rule) => rule.officialCode === "IN-09")!;
    expect(added.added).toBe(true);
    expect(added.addedComponentRefs).toEqual(["IN-09a"]);
  });
});
