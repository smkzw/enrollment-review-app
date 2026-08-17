/**
 * 重新解构差异 wire → ViewModel 映射单元测试（八类类别固定中文标签）。
 */

import { describe, expect, it } from "vitest";
import { mapProtocolDraftDiff } from "./protocolDiffMapper";

const DIFF = {
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
          previous: { kind: "predicate", predicate: { value: 18, unit: "岁" } },
          current: { kind: "logical", operator: "all", children: [] },
        },
      ],
      time_window_changes: [],
      exception_changes: [],
      evidence_changes: [
        {
          stable_ref: "IN-01a#req[1]",
          kind: "requirement",
          previous: null,
          current: { requirement_id: "req-new" },
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
};

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
    expect(evidence.current).toEqual({ requirement_id: "req-new" });
  });

  it("无变化的父规则 hasChanges 为 false", () => {
    const view = mapProtocolDraftDiff(DIFF);
    const ex = view.ruleDiffs.find((rule) => rule.officialCode === "EX-01")!;
    expect(ex.hasChanges).toBe(false);
    expect(ex.changes).toHaveLength(0);
  });

  it("容错缺失或畸形条目，不抛错", () => {
    const view = mapProtocolDraftDiff({
      rule_diffs: [null, { official_code: "" }, { official_code: 42 }],
      added_rule_codes: "not-a-list",
    });
    expect(view.ruleDiffs).toEqual([]);
    expect(view.addedRuleCodes).toEqual([]);
  });

  it("新增/删除整条父规则正常映射", () => {
    const view = mapProtocolDraftDiff({
      added_rule_codes: ["IN-09"],
      removed_rule_codes: ["EX-04"],
      rule_diffs: [
        { official_code: "IN-09", added: true, removed: false, added_component_refs: ["IN-09a"] },
        { official_code: "EX-04", added: false, removed: true, removed_component_refs: ["EX-04a"] },
      ],
    });
    expect(view.addedRuleCodes).toEqual(["IN-09"]);
    expect(view.removedRuleCodes).toEqual(["EX-04"]);
    const added = view.ruleDiffs.find((rule) => rule.officialCode === "IN-09")!;
    expect(added.added).toBe(true);
    expect(added.addedComponentRefs).toEqual(["IN-09a"]);
  });
});
