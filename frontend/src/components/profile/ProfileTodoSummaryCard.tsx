/**
 * Patient Profile 首屏待办汇总：按资料缺口性质聚合当前节点条目。
 *
 * 这里仅做显示层聚合，不改变后端投影，也不把档案头的“待核对”总数
 * 重新解释为四组之和。冲突组按未解决组数计数，解释材料与方案不一致
 * 则按条目另计，和后端缺口投影保持一致。
 */

import type { ProfileGapTypeWire, ProfileItemView } from "../../api/patient-profile";
import type { PatientProfileModel } from "../../features/patient-profile/model";
import {
  AttentionIcon,
  CheckIcon,
  ConflictIcon,
  GapIcon,
  JudgmentIcon,
} from "../shell/icons";

export type ProfileTodoGroup = "missing" | "judgment" | "conflict" | "manual_review";

export interface ProfileTodoCounts {
  missing: number;
  judgment: number;
  conflict: number;
  manual_review: number;
}

export const PROFILE_TODO_GROUPS: readonly ProfileTodoGroup[] = [
  "missing",
  "judgment",
  "conflict",
  "manual_review",
];

const PROFILE_TODO_GAP_TYPES: Readonly<Record<ProfileTodoGroup, readonly ProfileGapTypeWire[]>> = {
  missing: [
    "record_incomplete",
    "referenced_file_missing",
    "required_procedure_not_done",
    "historical_source_unavailable",
  ],
  judgment: ["professional_judgment", "observation_unverified"],
  conflict: ["interpretation_conflict"],
  manual_review: [
    "ocr_or_parse_risk",
    "result_fields_missing",
    "description_insufficient",
    "date_or_anchor_missing",
    "provenance_followup",
  ],
};

const PROFILE_TODO_LABELS: Readonly<Record<ProfileTodoGroup, string>> = {
  missing: "待补资料",
  judgment: "待研究者判断",
  conflict: "资料有矛盾",
  manual_review: "待人工核对",
};

/** 判断条目是否应在指定组的下钻列表中出现。 */
export function isProfileTodoItemInGroup(
  item: ProfileItemView,
  group: ProfileTodoGroup,
): boolean {
  const isUnresolvedConflict =
    group === "conflict" &&
    item.kind === "conflict" &&
    item.conflictResolutionRevision === null;
  const hasGroupGap =
    item.gapType !== null && PROFILE_TODO_GAP_TYPES[group].includes(item.gapType);
  return isUnresolvedConflict || hasGroupGap;
}

/**
 * 返回某组的首条目 ID（以及其余下钻条目），顺序沿用档案泳道顺序。
 * 冲突条目同时满足两种条件时只保留一个 ID，避免重复导航。
 */
export function profileTodoItemIds(
  model: Pick<PatientProfileModel, "items">,
  group: ProfileTodoGroup,
): ReadonlyArray<string> {
  const seen = new Set<string>();
  const ids: string[] = [];
  for (const item of model.items) {
    if (!isProfileTodoItemInGroup(item, group) || seen.has(item.itemId)) continue;
    seen.add(item.itemId);
    ids.push(item.itemId);
  }
  return ids;
}

/** 返回某组下钻目标的首条目 ID。 */
export function firstProfileTodoItemId(
  model: Pick<PatientProfileModel, "items">,
  group: ProfileTodoGroup,
): string | null {
  return profileTodoItemIds(model, group)[0] ?? null;
}

/** 从档案条目计算四组待办数量。 */
export function summarizeProfileTodos(
  model: Pick<PatientProfileModel, "items">,
): ProfileTodoCounts {
  const items = model.items;
  return {
    missing: items.filter((item) => isProfileTodoItemInGroup(item, "missing")).length,
    judgment: items.filter((item) => isProfileTodoItemInGroup(item, "judgment")).length,
    // 规范要求：未解决冲突按组计数，解释材料与方案不一致按条目另计。
    conflict:
      items.filter(
        (item) => item.kind === "conflict" && item.conflictResolutionRevision === null,
      ).length +
      items.filter((item) => item.gapType === "interpretation_conflict").length,
    manual_review: items.filter((item) => isProfileTodoItemInGroup(item, "manual_review")).length,
  };
}

export interface ProfileTodoSummaryCardProps {
  model: PatientProfileModel;
  onNavigate: (gapGroup: ProfileTodoGroup) => void;
}

function groupIcon(group: ProfileTodoGroup) {
  switch (group) {
    case "missing":
      return <GapIcon size={16} />;
    case "judgment":
      return <JudgmentIcon size={16} />;
    case "conflict":
      return <ConflictIcon size={16} />;
    case "manual_review":
      return <AttentionIcon size={16} />;
  }
}

export function ProfileTodoSummaryCard({
  model,
  onNavigate,
}: ProfileTodoSummaryCardProps) {
  const counts = summarizeProfileTodos(model);
  const hasTodos = PROFILE_TODO_GROUPS.some((group) => counts[group] > 0);

  return (
    <section
      className={`profile-section profile-todo-summary${hasTodos ? "" : " profile-todo-summary--clear"}`}
      aria-labelledby="profile-todo-summary-title"
      data-testid="profile-todo-summary"
    >
      <header className="profile-todo-summary__head">
        <h3 id="profile-todo-summary-title" className="profile-section__title">
          本节点资料核对情况
        </h3>
        <p
          className="profile-todo-summary__note"
          title="档案头“待核对 N 项”是需人工过目的条目总数；本卡按资料性质分组，未解决冲突按组计数。"
        >
          按资料性质分组 · 档案头“待核对”统计需人工过目的条目总数
        </p>
      </header>

      {hasTodos ? (
        <div className="profile-todo-summary__items" aria-label="四组待办数量">
          {PROFILE_TODO_GROUPS.map((group) => {
            const count = counts[group];
            const label = PROFILE_TODO_LABELS[group];
            return (
              <button
                key={group}
                type="button"
                className="profile-todo-summary__item count-chip"
                data-testid={`profile-todo-${group}`}
                disabled={count === 0}
                onClick={() => onNavigate(group)}
                title={count === 0 ? `${label}：暂无条目` : `查看${label}条目`}
                aria-label={`${label} ${count} 项`}
              >
                <span className="profile-todo-summary__icon" aria-hidden="true">
                  {groupIcon(group)}
                </span>
                <span className="profile-todo-summary__label">{label}</span>
                <strong className="profile-todo-summary__count" aria-hidden="true">
                  {count}
                </strong>
              </button>
            );
          })}
        </div>
      ) : (
        <div className="profile-todo-summary__clear" role="status">
          <CheckIcon size={17} />
          <span>本次提交资料中，暂无待补资料、待判断、矛盾或待核对事项</span>
        </div>
      )}
    </section>
  );
}
