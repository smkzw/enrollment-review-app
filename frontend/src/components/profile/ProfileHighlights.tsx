/**
 * Patient Profile 首屏重点（Slice 5.6）：只展示后端 highlights 显式结构化集合。
 * 前端绝不从风险标签关键词推导首屏；无突出条目时给中性空提示。
 * 提供 onOpenEvidence 时，有定位的重点条目显示“查看原文”打开证据面板。
 */

import type { PatientProfileModel } from "../../features/patient-profile/model";
import type { ProfileItemView } from "../../api/patient-profile";
import { locatorsForItem } from "../../features/patient-profile/model";

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
  if (model.highlights.length === 0) {
    return (
      <p className="profile-lane__muted">
        当前没有需要重点提示的条目。
      </p>
    );
  }

  return (
    <ul className="profile-highlight-list">
      {model.highlights.map((highlight) => {
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
  );
}
