/**
 * Patient Profile 事件行（合同 §4.2 关键事件摘要）：
 * 状态词、日期精度、关联规则与可打开的证据同卡可见。
 */

import { RouteLink } from "../../app/router";
import type { ProfileEventView } from "../../domain/viewModels";
import type { ReviewEpisodeId, RuleComponentId } from "../../domain/ids";
import { OpenIcon } from "../shell/icons";

export interface ProfileEventRowProps {
  event: ProfileEventView;
  /** 事件所属审核节点（直达工作台的 URL 契约） */
  episodeId: ReviewEpisodeId;
  /** 组件 ID → 显示编号（如 EX-01a） */
  componentCodeOf: (componentId: RuleComponentId) => string;
}

function dateText(event: ProfileEventView): string {
  const { startDate, endDate } = event;
  const start =
    startDate === null
      ? null
      : `${startDate.value}（精度：${startDate.precisionLabel}）`;
  if (endDate === null) return start === null ? "" : `时间：${start}`;
  const end = `${endDate.value}（精度：${endDate.precisionLabel}）`;
  return start === null ? `时间：${end}` : `时间：${start} 至 ${end}`;
}

export function ProfileEventRow({
  event,
  episodeId,
  componentCodeOf,
}: ProfileEventRowProps) {
  const codes = event.relatedRuleComponentIds.map(componentCodeOf);
  const time = dateText(event);
  const firstComponent =
    event.relatedRuleComponentIds.length > 0
      ? event.relatedRuleComponentIds[0]
      : undefined;
  const firstSpan = event.evidence.length > 0 ? event.evidence[0].spanId : undefined;

  return (
    <article className="profile-event">
      <header className="profile-event__head">
        <h4 className="profile-event__title">{event.title}</h4>
        <span className="profile-event__lane">{event.laneLabel}</span>
      </header>
      {event.riskLabels.length > 0 && (
        <div className="chip-group profile-event__risks">
          {event.riskLabels.map((label) => (
            <span key={label} className="count-chip profile-event__risk-chip">
              {label}
            </span>
          ))}
        </div>
      )}
      {time !== "" && <p className="profile-event__meta">{time}</p>}
      <div className="profile-event__foot">
        {codes.length > 0 && (
          <span className="profile-event__rules">
            关联规则：{codes.join("、")}
          </span>
        )}
        {firstSpan !== undefined && (
          <RouteLink
            to="/workbench"
            params={{
              episode: episodeId,
              component: firstComponent,
              evidence: firstSpan,
            }}
            className="button button--quiet profile-event__evidence"
            ariaLabel={`打开证据：${event.title}`}
            title={`打开证据：${event.evidence.length} 处定位`}
          >
            <OpenIcon size={13} />
            打开证据
          </RouteLink>
        )}
      </div>
    </article>
  );
}
