/**
 * 身份与期别确认面板。
 */

import { useState } from "react";
import type { IdentityReviewView } from "../../api/protocolWorkbenchTypes";
import type { ConfirmIdentityInput } from "../../api/protocolWorkbenchTypes";

interface ProtocolIdentityPanelProps {
  review: IdentityReviewView;
  busy: boolean;
  onConfirm: (input: ConfirmIdentityInput) => void;
  onCancel: () => void;
}

export function ProtocolIdentityPanel({
  review,
  busy,
  onConfirm,
  onCancel,
}: ProtocolIdentityPanelProps) {
  const { identity, phaseCandidates } = review;
  const [studyPhase, setStudyPhase] = useState(
    identity.studyPhase ?? phaseCandidates[0]?.phase ?? "phase_ii",
  );

  const submit = () => {
    if (
      identity.protocolCode === null ||
      identity.projectName === null ||
      identity.officialVersion === null ||
      identity.officialDateValue === null ||
      identity.officialDatePrecision === null
    ) {
      return;
    }
    onConfirm({
      protocolCode: identity.protocolCode,
      projectName: identity.projectName,
      projectCode: identity.projectCode,
      officialVersion: identity.officialVersion,
      officialDateValue: identity.officialDateValue,
      officialDatePrecision: identity.officialDatePrecision,
      studyPhase,
      selectedCandidateIds: identity.selectedCandidateIds,
    });
  };

  return (
    <div className="protocol-identity">
      <header className="page-head">
        <h1 className="page-head__title">确认方案身份与期别</h1>
        <p className="page-head__note">
          请核对从方案原文提取的编号、版本与研究期别。确认后将只解构所选期别及明确共享条款。
        </p>
      </header>

      <section className="protocol-identity__summary" aria-label="提取到的方案身份">
        <dl className="protocol-identity__fields">
          <div>
            <dt>方案编号</dt>
            <dd>{identity.protocolCode ?? "待补充"}</dd>
          </div>
          <div>
            <dt>项目名称</dt>
            <dd>{identity.projectName ?? "待补充"}</dd>
          </div>
          <div>
            <dt>正式版本</dt>
            <dd>{identity.officialVersion ?? "待补充"}</dd>
          </div>
          <div>
            <dt>版本日期</dt>
            <dd>{identity.officialDateValue ?? "待补充"}</dd>
          </div>
        </dl>
      </section>

      <section className="protocol-identity__phase" aria-labelledby="protocol-phase-title">
        <h2 id="protocol-phase-title" className="protocol-section__title">
          研究期别确认
        </h2>
        {phaseCandidates.length === 0 ? (
          <p className="protocol-identity__empty">暂无期别候选，请等待结构提取完成。</p>
        ) : (
          <ul className="protocol-phase-list">
            {phaseCandidates.map((candidate) => (
              <li key={candidate.candidateId}>
                <label className="protocol-phase-option">
                  <input
                    type="radio"
                    name="study-phase"
                    value={candidate.phase}
                    checked={studyPhase === candidate.phase}
                    onChange={() => setStudyPhase(candidate.phase)}
                  />
                  <span className="protocol-phase-option__label">{candidate.phaseLabel}</span>
                  <span className="protocol-phase-option__rationale">{candidate.rationale}</span>
                </label>
              </li>
            ))}
          </ul>
        )}
      </section>

      {review.metadataConflicts.length > 0 && (
        <section className="protocol-identity__conflicts" role="alert">
          <h2 className="protocol-section__title">元信息冲突</h2>
          <ul>
            {review.metadataConflicts.map((conflict) => (
              <li key={conflict.conflictId}>
                <strong>{conflict.fieldLabel}</strong>
                <span>存在多个候选值，请选择正确来源。</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="protocol-identity__actions">
        <button type="button" className="button button--primary" disabled={busy} onClick={submit}>
          确认并继续解构
        </button>
        <button type="button" className="button button--quiet" disabled={busy} onClick={onCancel}>
          返回首页
        </button>
      </div>
    </div>
  );
}
