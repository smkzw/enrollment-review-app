/**
 * Patient Profile 风险过滤（合同 §4.2）：首屏只突出入排相关、异常、临界、
 * 趋势、冲突与资料缺口，完整资料按需展开；隐藏不等于删除。
 * 分类由事件字段与风险标签推导，不做临床判定。
 */

import type { ProfileEventView } from "../../domain/viewModels";
import type { ProfileLane } from "../../domain/enums";

/** 完整明细的主题顺序（合同 §4.2 完整资料清单），空主题也渲染并说明未记录 */
export const PROFILE_LANE_ORDER: readonly ProfileLane[] = [
  "study_milestone",
  "demographics",
  "target_disease",
  "symptoms_signs",
  "medical_history",
  "medication",
  "non_drug_treatment",
  "test_exam_score",
  "allergy_infection_immune",
  "reproductive",
  "social_environmental",
  "special_history",
  "evidence_quality",
];

export type ProfileFilterKey =
  | "enrollment"
  | "abnormal"
  | "critical"
  | "trend"
  | "conflict"
  | "gap"
  | "future";

export interface ProfileFilterOption {
  key: ProfileFilterKey;
  label: string;
  describe: string;
}

/** 固定顺序的过滤项（合同 §4.2 风险过滤清单） */
export const PROFILE_FILTERS: readonly ProfileFilterOption[] = [
  { key: "enrollment", label: "入排相关", describe: "与入选/排除条件相关的资料" },
  { key: "abnormal", label: "异常", describe: "标记为异常的资料或检查" },
  { key: "critical", label: "临界", describe: "标记为临界或需要警惕的资料" },
  { key: "trend", label: "趋势变化", describe: "随时间发生变化、需要留意的资料" },
  { key: "conflict", label: "存在冲突", describe: "同一事项来源不一致" },
  { key: "gap", label: "资料缺口", describe: "应备资料尚未见到或来源缺失" },
  { key: "future", label: "后续节点关注", describe: "属于后续审核节点的事项" },
];

const GAP_RISK_LABELS = new Set(["记录不完整", "来源缺失", "日期锚点", "当前节点缺口"]);
const FUTURE_RISK_LABELS = new Set(["阶段隔离"]);

/** 事件归属的风险分类（首屏风险视图的展示依据） */
export function eventFilterKeys(event: ProfileEventView): ReadonlyArray<ProfileFilterKey> {
  const keys = new Set<ProfileFilterKey>();
  if (
    event.relatedRuleComponentIds.length > 0 ||
    event.riskLabels.includes("入排相关")
  ) {
    keys.add("enrollment");
  }
  if (event.isAbnormal) keys.add("abnormal");
  if (event.isCritical) keys.add("critical");
  if (event.hasTrendChange) keys.add("trend");
  if (event.riskLabels.includes("来源冲突")) keys.add("conflict");
  if (event.riskLabels.some((label) => GAP_RISK_LABELS.has(label))) {
    keys.add("gap");
  }
  if (event.riskLabels.some((label) => FUTURE_RISK_LABELS.has(label))) {
    keys.add("future");
  }
  return [...keys];
}

/** 事件是否属于“风险视图”默认集合（有任一分类即突出显示） */
export function isRiskEvent(event: ProfileEventView): boolean {
  return eventFilterKeys(event).length > 0;
}
