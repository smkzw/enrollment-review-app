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
              source_validity_window: { value: 1, unit: "month" },
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

function periodDiff(period: unknown) {
  return {
    ...completeDiff(),
    rule_diffs: [{
      official_code: "EX-01", added: false, removed: false,
      added_component_refs: [], removed_component_refs: [],
      original_text_changes: [], logic_changes: [], exception_changes: [],
      evidence_changes: [], due_stage_changes: [],
      time_window_changes: [{ stable_ref: "EX-01a", kind: "component",
        previous: [{ scope: "main", time_constraint: null, occurrence_window: null,
          prospective_window: null, prospective_period: null }],
        current: [{ scope: "main", time_constraint: null, occurrence_window: null,
          prospective_window: null, prospective_period: period }] }],
    }],
  };
}

const sourceComputation = {
  operator: "mean", operator_ref: { statement_index: 0, quote: "均值" },
  input_refs: [{ statement_index: 0, quote: "最近三次记录" }], missing_policy: "not_specified",
  missing_ref: null, declared_input_count: null, max_missing_count: null,
};

function computationDiff(calculation: unknown) {
  const diff = structuredClone(DIFF);
  diff.rule_diffs[0].logic_changes[0].current = {
    kind: "predicate", predicate: { subject: "受试者", attribute: "审核值", comparator: "gte", value: 7,
      unit: "分", source_computation: calculation },
  } as ProtocolDraftDiffWire["rule_diffs"][number]["logic_changes"][number]["current"];
  return diff;
}

describe("计算方法差异", () => {
  const selection = { mode: "latest_n", source: { statement_index: 0, quote: "最近三次记录" },
    ordering_basis: "unresolved", ordering_ref: null, window_refs: [] };
  const selectedComputation = { ...sourceComputation,
    declared_input_count: { value: 3, number_text: "三", source: { statement_index: 0, quote: "最近三次记录" } },
    input_selection: selection };
  it("原文排序日期未明确时保留未核清，不默认报告日期", () => {
    const normalized = normalizeProtocolDraftDiff(computationDiff(selectedComputation));
    expect(normalized.rule_diffs[0].logic_changes[0].current).toMatchObject({ predicate: { source_computation: selectedComputation } });
    expect(JSON.stringify(mapProtocolDraftDiff(normalized))).toContain('"ordering_basis":"unresolved"');
    const legacy = normalizeProtocolDraftDiff(computationDiff({ ...sourceComputation, input_selection: null }));
    expect(legacy.rule_diffs[0].logic_changes[0].current).toMatchObject({ predicate: { source_computation: sourceComputation } });
  });
  it.each([
    { ...selectedComputation, declared_input_count: null },
    { ...selectedComputation, input_selection: { ...selection, ordering_basis: "report_time" } },
    { ...selectedComputation, input_selection: { ...selection, mode: "single", ordering_basis: null } },
    { ...selectedComputation, input_selection: { ...selection, ordering_basis: null } },
    { ...selectedComputation, input_selection: { ...selection, verified: true } },
    { ...selectedComputation, input_selection: { ...selection, window_refs: [{ statement_index: 1, quote: "其他范围" }] } },
    { ...selectedComputation, declared_input_count: { value: 7, number_text: "7", source: { statement_index: 0, quote: "至少为7分" } } },
    { ...selectedComputation, missing_policy: "exclude", missing_ref: { statement_index: 1, quote: "缺失不填补" },
      max_missing_count: { value: 1, number_text: "一", source: { statement_index: 1, quote: "最多允许缺失一次" } } },
  ])("拒绝缺数量、无源排序与借窗 %j", (calculation) => {
    expect(() => normalizeProtocolDraftDiff(computationDiff(calculation))).toThrow();
  });
  it("解码与界面映射都保留原文计算方法，不伪造已完成计算", () => {
    const normalized = normalizeProtocolDraftDiff(computationDiff(sourceComputation));
    expect(normalized.rule_diffs[0].logic_changes[0].current).toMatchObject({
      predicate: { source_computation: sourceComputation },
    });
    expect(JSON.stringify(mapProtocolDraftDiff(normalized))).toContain("最近三次记录");
  });
  it.each([
    { ...sourceComputation, operator: "vote" },
    { ...sourceComputation, operator_ref: { statement_index: -1, quote: "均值" } },
    { ...sourceComputation, operator_ref: { statement_index: 0, quote: " " } },
    { ...sourceComputation, input_refs: [] },
    { ...sourceComputation, missing_policy: "impute" },
    { ...sourceComputation, verified: true },
  ])("拒绝错误或自称已核实的计算方法 %j", (calculation) => {
    expect(() => normalizeProtocolDraftDiff(computationDiff(calculation))).toThrow();
  });
});

describe("方案记录用途", () => {
  const purpose = { target_kind: "event_history", record_obligation: "required",
    proposition_direction: "event_present", source_excerpts: ["既往事件须以规定记录核对"] };
  function purposeDiff(recordSemantics: unknown) {
    const diff = structuredClone(DIFF);
    diff.rule_diffs[0].logic_changes[0].current = { kind: "predicate", predicate: {
      subject: "受试者", attribute: "既往事件", comparator: "exists", record_semantics: recordSemantics,
    } } as ProtocolDraftDiffWire["rule_diffs"][number]["logic_changes"][number]["current"];
    return diff;
  }
  it("既往事件也可要求指定记录，解码和映射不丢用途", () => {
    const normalized = normalizeProtocolDraftDiff(purposeDiff(purpose));
    expect(normalized.rule_diffs[0].logic_changes[0].current).toMatchObject({ predicate: { record_semantics: purpose } });
    expect(JSON.stringify(mapProtocolDraftDiff(normalized))).toContain("既往事件须以规定记录核对");
  });
  it.each([
    { ...purpose, verified: true }, { ...purpose, accepted: true },
    { ...purpose, source_excerpts: [] }, { ...purpose, source_excerpts: [" "] },
    { ...purpose, source_excerpts: ["重复", "重复"] }, { ...purpose, target_kind: "other" },
  ])("拒绝空依据、方向错误和自称核实 %j", (changed) => {
    expect(() => normalizeProtocolDraftDiff(purposeDiff(changed))).toThrow();
  });
});

describe("有源期间的差异读取", () => {
  it("正常读取并映射完整原文，不改写期间边界", () => {
    const period = { kind: "source_defined", source_excerpts: [" 准备阶段及干预阶段（第六次访视之前） "] };
    const normalized = normalizeProtocolDraftDiff(periodDiff(period));
    const changes = mapProtocolDraftDiff(normalized).ruleDiffs[0].changes;
    expect(changes[0].category).toBe("time_window");
    expect(changes[0].current).toEqual([{ scope: "main", time_constraint: null,
      occurrence_window: null, prospective_window: null, prospective_period: period }]);
  });

  it.each([
    { kind: "source_defined", source_excerpts: [] },
    { kind: "source_defined", source_excerpts: [" "] },
    { kind: "source_defined", source_excerpts: ["期间", "期间"] },
    { kind: "source_defined", source_excerpts: [42] },
    { kind: "source_defined", source_excerpts: ["期间"], period: "study_period" },
    { kind: "unknown", period: "study_period" },
  ])("拒绝不完整、混合或未知的期间表达：%j", (period) => {
    expect(() => normalizeProtocolDraftDiff(periodDiff(period))).toThrow(/期间|source_excerpts/);
  });

  it.each(["study_period", "treatment_period"])("保留原有期间：%s", (period) => {
    const normalized = normalizeProtocolDraftDiff(periodDiff({ period }));
    expect(normalized.rule_diffs[0].time_window_changes[0].current).toEqual([
      { scope: "main", time_constraint: null, occurrence_window: null,
        prospective_window: null, prospective_period: { period } },
    ]);
  });
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
        source_validity_window: { value: 1, unit: "month" },
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
