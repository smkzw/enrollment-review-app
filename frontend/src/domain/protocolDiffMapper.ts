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
import type {
  ProtocolCategoryChangeWire,
  ProtocolDraftDiffWire,
  ProtocolRuleDiffWire,
} from "../api/protocolWorkbenchTypes";

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
const CHANGE_FIELD_TO_CATEGORY = [
  ["original_text_changes", "original_text"],
  ["logic_changes", "logic"],
  ["time_window_changes", "time_window"],
  ["exception_changes", "exception"],
  ["evidence_changes", "evidence"],
  ["due_stage_changes", "due_stage"],
] as const satisfies ReadonlyArray<[
  | "original_text_changes"
  | "logic_changes"
  | "time_window_changes"
  | "exception_changes"
  | "evidence_changes"
  | "due_stage_changes",
  DiffCategoryKey,
]>;

function toCategoryChange(
  category: DiffCategoryKey,
  row: ProtocolCategoryChangeWire,
): ProtocolCategoryChangeView {
  return {
    category,
    categoryLabel: DIFF_CATEGORY_LABELS[category],
    stableRef: row.stable_ref,
    kind: row.kind,
    previous: row.previous,
    current: row.current,
  };
}

function toRuleDiff(row: ProtocolRuleDiffWire): ProtocolRuleDiffView {
  const changes: ProtocolCategoryChangeView[] = [];
  for (const [field, category] of CHANGE_FIELD_TO_CATEGORY) {
    const list = row[field];
    for (const entry of list) {
      changes.push(toCategoryChange(category, entry));
    }
  }
  const hasChanges =
    row.added || row.removed || row.added_component_refs.length > 0 || row.removed_component_refs.length > 0 || changes.length > 0;
  return {
    officialCode: row.official_code,
    added: row.added,
    removed: row.removed,
    addedComponentRefs: row.added_component_refs,
    removedComponentRefs: row.removed_component_refs,
    changes,
    hasChanges,
  };
}

/** 从 DraftComparisonView.diff（backend 确定性输出）映射为展示模型。 */
export function mapProtocolDraftDiff(
  diff: ProtocolDraftDiffWire,
): ProtocolDraftDiffView {
  const ruleDiffs = diff.rule_diffs.map(toRuleDiff);
  return {
    addedRuleCodes: diff.added_rule_codes,
    removedRuleCodes: diff.removed_rule_codes,
    modifiedRuleCodes: diff.modified_rule_codes,
    ruleDiffs,
  };
}
