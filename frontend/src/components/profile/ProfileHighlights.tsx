/**
 * Patient Profile 首屏重点（Slice 5.6）：只展示后端 highlights 显式结构化集合。
 * 前端绝不从风险标签关键词推导首屏；无突出条目时给中性空提示。
 * 提供 onOpenEvidence 时，有定位的重点条目显示“查看原文”打开证据面板。
 */

import { useState } from "react";
import type { PatientProfileModel } from "../../features/patient-profile/model";
import type { ProfileItemView } from "../../api/patient-profile";
import { locatorsForItem } from "../../features/patient-profile/model";
import { isProfileTodoItemInGroup, type ProfileTodoGroup } from "./ProfileTodoSummaryCard";

const INITIAL_VISIBLE_COUNT = 8;
const GROUP_SAMPLE_COUNT = 2;
const DISPLAY_GROUPS: readonly ProfileTodoGroup[] = [
  "conflict", "judgment", "manual_review", "missing",
];

function initialHighlights(model: PatientProfileModel) {
  const selected = new Set<string>();
  for (const group of DISPLAY_GROUPS) {
    let inGroup = 0;
    for (const highlight of model.highlights) {
      const item = model.itemById.get(highlight.itemId);
      if (item === undefined) throw new Error("首屏重点引用了不存在的档案条目");
      if (!selected.has(highlight.itemId) && isProfileTodoItemInGroup(item, group)) {
        selected.add(highlight.itemId);
        if (++inGroup === GROUP_SAMPLE_COUNT) break;
      }
    }
  }
  for (const highlight of model.highlights) {
    if (selected.size >= INITIAL_VISIBLE_COUNT) break;
    selected.add(highlight.itemId);
  }
  return model.highlights.filter((highlight) => selected.has(highlight.itemId));
}

export interface ProfileHighlightsProps {
  model: PatientProfileModel;
  onOpenEvidence?: (item: ProfileItemView) => void;
  onRequestCorrection?: (item: ProfileItemView) => void;
}

export function ProfileHighlights({
  model,
  onOpenEvidence,
  onRequestCorrection,
}: ProfileHighlightsProps) {
  const [expanded, setExpanded] = useState(false);
  if (model.highlights.length === 0) {
    return (
      <p className="profile-lane__muted">
        当前没有需要重点提示的条目。
      </p>
    );
  }

  const firstHighlights = initialHighlights(model);
  const hasMore = model.highlights.length > firstHighlights.length;
  const visibleHighlights = expanded ? model.highlights : firstHighlights;

  return (
    <>
    {hasMore && (
      <p className="profile-highlight-list__scope">
        各类待核事项先显示部分条目；上方分类可直达相应条目，全部内容均可展开。
      </p>
    )}
    <ul className="profile-highlight-list">
      {visibleHighlights.map((highlight) => {
        const item = model.itemById.get(highlight.itemId);
        if (item === undefined) {
          throw new Error("首屏重点引用了不存在的档案条目");
        }
        const canRequestCorrection =
          onRequestCorrection !== undefined &&
          locatorsForItem(model, item).length > 0 &&
          (item.kind === "fact" || item.kind === "event" || item.kind === "exposure");
        return (
          <li key={highlight.itemId} className="profile-highlight">
            <header className="profile-highlight__head">
              <h4 className="profile-highlight__title">{item.title}</h4>
              <span className="profile-highlight__kind">
                {item.kindLabel} · {item.laneLabel}
              </span>
            </header>
            <div className="chip-group profile-highlight__reasons">
              {highlight.reasonLabels.map((label, index) => (
                <span key={`${highlight.itemId}-${index}`} className="count-chip profile-highlight__reason">
                  {label}
                </span>
              ))}
            </div>
            {highlight.gapTypeLabel !== null && (
              <p className="profile-highlight__meta">资料缺口：{highlight.gapTypeLabel}</p>
            )}
            {highlight.detail !== null && (
              <p className="profile-highlight__detail">{highlight.detail}</p>
            )}
            {onOpenEvidence !== undefined &&
              locatorsForItem(model, item).length > 0 && (
                <button
                  type="button"
                  className="chip profile-highlight__open-evidence"
                  onClick={() => onOpenEvidence(item)}
                  aria-label={`查看“${item.title}”的原文证据`}
                >
                  查看原文
                </button>
              )}
            {canRequestCorrection && (
              <button
                type="button"
                className="chip profile-highlight__request-correction"
                onClick={() => onRequestCorrection(item)}
                aria-label={`核对并修订“${item.title}”`}
              >
                核对并修订
              </button>
            )}
          </li>
        );
      })}
    </ul>
    {hasMore && (
      <button
        type="button"
        className="chip profile-highlight-list__toggle"
        aria-expanded={expanded}
        onClick={() => setExpanded((value) => !value)}
      >
        {expanded ? "收起重点明细" : `展开其余 ${model.highlights.length - firstHighlights.length} 项`}
      </button>
    )}
    </>
  );
}
