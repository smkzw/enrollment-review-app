/**
 * 重新解构差异 wire → ViewModel 映射：只消费 backend 确定性输出的八类结构。
 * 类别键与中文标签固定；previous/current 透传快照，展示层按类别渲染。
 */

import type {
  DiffCategoryKey,
  ProtocolCategoryChangeView,
  ProtocolDraftDiffView,
  ProtocolRuleDiffView,
} from "./protocolDiffViewModels";

export const DIFF_CATEGORY_LABELS: Record<DiffCategoryKey, string> = {
  added: "新增",
  removed: "删除",
  original_text: "原文",
  logic: "逻辑",
  time_window: "时间窗",
  exception: "例外",
  evidence: "证据要求",
  due_stage: "应完成阶段",
};

/** 后端 rule_diffs[] 中六类子组件级变化的字段名 → 类别键。 */
const CHANGE_FIELD_TO_CATEGORY: ReadonlyArray<[string, DiffCategoryKey]> = [
  ["original_text_changes", "original_text"],
  ["logic_changes", "logic"],
  ["time_window_changes", "time_window"],
  ["exception_changes", "exception"],
  ["evidence_changes", "evidence"],
  ["due_stage_changes", "due_stage"],
];

interface WireCategoryChange {
  stable_ref?: unknown;
  kind?: unknown;
  previous?: unknown;
  current?: unknown;
}

interface WireRuleDiff {
  official_code?: unknown;
  added?: unknown;
  removed?: unknown;
  added_component_refs?: unknown;
  removed_component_refs?: unknown;
  [field: string]: unknown;
}

function stringList(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
}

function toCategoryChange(
  category: DiffCategoryKey,
  raw: unknown,
): ProtocolCategoryChangeView | null {
  if (raw === null || typeof raw !== "object" || Array.isArray(raw)) return null;
  const row = raw as WireCategoryChange;
  const stableRef =
    typeof row.stable_ref === "string" && row.stable_ref.length > 0
      ? row.stable_ref
      : "—";
  const kind = row.kind === "rule" || row.kind === "requirement" ? row.kind : "component";
  return {
    category,
    categoryLabel: DIFF_CATEGORY_LABELS[category],
    stableRef,
    kind,
    previous: row.previous ?? null,
    current: row.current ?? null,
  };
}

function toRuleDiff(raw: unknown): ProtocolRuleDiffView | null {
  if (raw === null || typeof raw !== "object" || Array.isArray(raw)) return null;
  const row = raw as WireRuleDiff;
  const officialCode =
    typeof row.official_code === "string" && row.official_code.length > 0
      ? row.official_code
      : "";
  if (officialCode.length === 0) return null;
  const added = row.added === true;
  const removed = row.removed === true;
  const addedComponentRefs = stringList(row.added_component_refs);
  const removedComponentRefs = stringList(row.removed_component_refs);
  const changes: ProtocolCategoryChangeView[] = [];
  for (const [field, category] of CHANGE_FIELD_TO_CATEGORY) {
    const list = row[field];
    if (!Array.isArray(list)) continue;
    for (const entry of list) {
      const change = toCategoryChange(category, entry);
      if (change !== null) changes.push(change);
    }
  }
  const hasChanges =
    added || removed || addedComponentRefs.length > 0 || removedComponentRefs.length > 0 || changes.length > 0;
  return {
    officialCode,
    added,
    removed,
    addedComponentRefs,
    removedComponentRefs,
    changes,
    hasChanges,
  };
}

/** 从 DraftComparisonView.diff（backend 确定性输出）映射为展示模型。 */
export function mapProtocolDraftDiff(
  diff: Record<string, unknown>,
): ProtocolDraftDiffView {
  const ruleDiffs: ProtocolRuleDiffView[] = [];
  const rawRuleDiffs = diff.rule_diffs;
  if (Array.isArray(rawRuleDiffs)) {
    for (const raw of rawRuleDiffs) {
      const rule = toRuleDiff(raw);
      if (rule !== null) ruleDiffs.push(rule);
    }
  }
  return {
    addedRuleCodes: stringList(diff.added_rule_codes),
    removedRuleCodes: stringList(diff.removed_rule_codes),
    modifiedRuleCodes: stringList(diff.modified_rule_codes),
    ruleDiffs,
  };
}
