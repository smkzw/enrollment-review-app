/**
 * 应备证据覆盖（合同 §4.2 第 4 项）：已找到 / 证据较弱 / 已引用但资料未提供 /
 * 尚未见到 / 后续节点尚未到期 五类状态显式区分。
 * “尚未见到”与“明确否认”绝不混为一谈：本组件只展示状态词与缺口词。
 */

import type { EvidenceExpectationView } from "../../domain/viewModels";
import { CheckIcon, GapIcon, AttentionIcon, RunningIcon } from "../shell/icons";
import { UI_PHRASES } from "../../domain/labels";

const STATUS_ORDER = ["observed", "observed_weak", "referenced_missing", "absent", "not_due"] as const;

function statusIcon(status: EvidenceExpectationView["status"]) {
  switch (status) {
    case "observed":
      return <CheckIcon size={13} />;
    case "observed_weak":
      return <AttentionIcon size={13} />;
    case "referenced_missing":
      return <GapIcon size={13} />;
    case "absent":
      return <GapIcon size={13} />;
    case "not_due":
      return <RunningIcon size={13} />;
  }
}

export function ExpectationCoverage({
  expectations,
}: {
  expectations: ReadonlyArray<EvidenceExpectationView>;
}) {
  if (expectations.length === 0) {
    return <p className="expectation-cover__muted">当前节点没有应备证据要求。</p>;
  }

  const sorted = [...expectations].sort(
    (a, b) =>
      STATUS_ORDER.indexOf(a.status as (typeof STATUS_ORDER)[number]) -
      STATUS_ORDER.indexOf(b.status as (typeof STATUS_ORDER)[number]),
  );
  const missingCount = sorted.filter(
    (expectation) =>
      expectation.status === "absent" ||
      expectation.status === "referenced_missing",
  ).length;

  return (
    <div className="expectation-cover">
      <p className="expectation-cover__summary">
        应备证据共 {expectations.length} 项，尚未见到或资料未提供 {missingCount} 项。
      </p>
      <ul className="expectation-cover__list">
        {sorted.map((expectation) => (
          <li key={expectation.expectationId} className="expectation-cover__row">
            <span
              className={`status-badge status-badge--expectation status-badge--expectation-${expectation.status}`}
            >
              {statusIcon(expectation.status)}
              <span>{expectation.statusLabel}</span>
            </span>
            <span className="expectation-cover__gap">{expectation.gapLabel}</span>
            {expectation.status === "absent" && (
              <span className="expectation-cover__note">
                资料中未见这项记录，需要核对是否实际询问或产生过
              </span>
            )}
            {expectation.status === "referenced_missing" && (
              <span className="expectation-cover__note">
                {UI_PHRASES.evidenceMissing}
              </span>
            )}
            {expectation.status === "not_due" && (
              <span className="expectation-cover__note">
                该资料属于后续节点，当前不作为缺口处理
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
