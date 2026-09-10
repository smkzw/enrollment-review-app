/**
 * Patient Profile 条目卡片（Slice 5.6）：呈现单条事实/事件/用药暴露/证据冲突/资料期望。
 * - 事件时间（start/end 区间）与记录时间（recordTime）分开展示；
 * - 只展示后端已提供的中文标签（来源强度、极性、持续状态等），前端不发明措辞；
 * - 定位只呈现真实定位数量与精度词，不做合成坐标、不画红框（红框由证据查看器负责）；
 * - 提供 onOpenEvidence 时，有定位的条目显示“查看原文”，打开证据面板联动原件。
 */

import type { ProfileDateRangeView, ProfileItemView } from "../../api/patient-profile";
import type { PatientProfileModel } from "../../features/patient-profile/model";
import {
  formatProfileDateTime,
  locatorsForItem,
} from "../../features/patient-profile/model";

export interface ProfileItemCardProps {
  model: PatientProfileModel;
  item: ProfileItemView;
  /** 提供时，有定位的条目显示“查看原文”，打开证据面板联动原件。 */
  onOpenEvidence?: (item: ProfileItemView) => void;
  /** 提供时，仅事实/事件/用药暴露显示结构化修订入口。 */
  onRequestCorrection?: (item: ProfileItemView) => void;
}

function rangeText(range: ProfileDateRangeView | null): string | null {
  if (range === null) return null;
  const source = formatSourceDate(range.sourceText);
  const precision = range.precisionLabel !== null ? `（精度：${range.precisionLabel}）` : "";
  if (range.lowerBound === null && range.upperBound === null) {
    return `${source}${precision}`;
  }
  const lower = range.lowerBound ?? "未知";
  const upper = range.upperBound ?? "未知";
  return `${source}${precision} · ${lower} 至 ${upper}`;
}

function formatSourceDate(sourceText: string | null): string {
  if (sourceText === null) return "日期未记录";
  const parts = sourceText.split(/[./-]/);
  if (parts.length === 3 && /^\d{4}$/.test(parts[0])) {
    const month = /^\d{1,2}$/.test(parts[1]) ? `${Number(parts[1])}月` : "月不详";
    const day = /^\d{1,2}$/.test(parts[2]) ? `${Number(parts[2])}日` : "日不详";
    if (/^UK$/i.test(parts[1]) || /^UK$/i.test(parts[2])) {
      return `${parts[0]}年${month}${day}`;
    }
  }
  return sourceText;
}

export function ProfileItemCard({
  model,
  item,
  onOpenEvidence,
  onRequestCorrection,
}: ProfileItemCardProps) {
  const locators = locatorsForItem(model, item);
  const canRequestCorrection =
    onRequestCorrection !== undefined &&
    locators.length > 0 &&
    (item.kind === "fact" || item.kind === "event" || item.kind === "exposure");
  const eventStart = rangeText(item.startRange);
  const eventEnd = rangeText(item.endRange);
  const recordedAt = formatProfileDateTime(item.recordTime);

  const valueText =
    item.value !== null
      ? `${String(item.value)}${item.unit !== null ? ` ${item.unit}` : ""}`
      : null;

  const medicationParts = [
    item.medicationName,
    item.category !== null ? `类别：${item.category}` : null,
    item.indication !== null ? `适应证：${item.indication}` : null,
    item.dose !== null ? `剂量：${item.dose}` : null,
    item.frequency !== null ? `频次：${item.frequency}` : null,
    item.route !== null ? `途径：${item.route}` : null,
  ].filter((part): part is string => part !== null);

  return (
    <article className="profile-item">
      <header className="profile-item__head">
        <h4 className="profile-item__title">{item.title}</h4>
        <div className="chip-group profile-item__tags">
          <span className="count-chip profile-item__kind">{item.kindLabel}</span>
          <span className="count-chip profile-item__lane">{item.laneLabel}</span>
          {item.sourceStrengthLabel !== null && (
            <span className="count-chip profile-item__strength">
              来源：{item.sourceStrengthLabel}
            </span>
          )}
        </div>
      </header>

      {item.subtitle !== null && (
        <p className="profile-item__subtitle">{item.subtitle}</p>
      )}

      <dl className="profile-item__meta">
        {(eventStart !== null || eventEnd !== null) && (
          <div className="profile-item__row">
            <dt>事件时间</dt>
            <dd>
              {eventStart ?? "起止未记录"}
              {eventEnd !== null && eventEnd !== eventStart ? ` 至 ${eventEnd}` : ""}
            </dd>
          </div>
        )}
        {item.durationStatusLabel !== null && (
          <div className="profile-item__row">
            <dt>持续状态</dt>
            <dd>{item.durationStatusLabel}</dd>
          </div>
        )}
        {recordedAt !== null && (
          <div className="profile-item__row">
            <dt>记录时间</dt>
            <dd>{recordedAt}</dd>
          </div>
        )}
        {item.polarityLabel !== null && (
          <div className="profile-item__row">
            <dt>记录性质</dt>
            <dd>{item.polarityLabel}</dd>
          </div>
        )}
        {item.assertedObject !== null && (
          <div className="profile-item__row">
            <dt>记录项目</dt>
            <dd>{item.assertedObject}</dd>
          </div>
        )}
        {valueText !== null && (
          <div className="profile-item__row">
            <dt>记录结果</dt>
            <dd>{valueText}</dd>
          </div>
        )}
        {medicationParts.length > 0 && (
          <div className="profile-item__row profile-item__row--wide">
            <dt>用药信息</dt>
            <dd>{medicationParts.join(" · ")}</dd>
          </div>
        )}
        {item.kind === "conflict" && (
          <div className="profile-item__row profile-item__row--wide">
            <dt>冲突并列</dt>
            <dd>
              相互矛盾的记录 {item.conflictMemberIds.length} 条
              {item.conflictResolutionRevision !== null
                ? ` · 已在档案第 ${item.conflictResolutionRevision} 版解决`
                : " · 尚未解决"}
            </dd>
          </div>
        )}
        {item.kind === "expectation" && item.expectationStatusLabel !== null && (
          <div className="profile-item__row profile-item__row--wide">
            <dt>资料核对</dt>
            <dd>
              <span className={`status-badge status-badge--expectation status-badge--expectation-${item.expectationStatus ?? "absent"}`}>
                {item.expectationStatusLabel}
              </span>
              {item.gapTypeLabel !== null && ` · 缺口：${item.gapTypeLabel}`}
              {item.gapDetail !== null && ` · ${item.gapDetail}`}
            </dd>
          </div>
        )}
        {item.provenanceFollowup && item.provenanceReason !== null && (
          <div className="profile-item__row profile-item__row--wide">
            <dt>溯源提醒</dt>
            <dd>{item.provenanceReason}</dd>
          </div>
        )}
        {locators.length > 0 && (
          <div className="profile-item__row profile-item__row--wide">
            <dt>原文定位</dt>
            <dd className="profile-item__locator-cell">
              <span>
                {locators.length} 处 ·{" "}
                {locators.map((locator) => locator.precisionLabel).join("、")}
              </span>
              {onOpenEvidence !== undefined && (
                <button
                  type="button"
                  className="chip profile-item__open-evidence"
                  onClick={() => onOpenEvidence(item)}
                  aria-label={`查看“${item.title}”的原文证据`}
                >
                  查看原文
                </button>
              )}
              {canRequestCorrection && (
                <button
                  type="button"
                  className="chip profile-item__request-correction"
                  onClick={() => onRequestCorrection(item)}
                  aria-label={`核对并修订“${item.title}”`}
                >
                  核对并修订
                </button>
              )}
            </dd>
          </div>
        )}
      </dl>
    </article>
  );
}
