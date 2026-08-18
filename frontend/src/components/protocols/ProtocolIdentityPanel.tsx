/**
 * 身份与期别确认面板。
 */

import { useState } from "react";
import type {
  ConfirmIdentityInput,
  ConfirmableDatePrecision,
  IdentityReviewView,
  MetadataCandidateView,
} from "../../api/protocolWorkbenchTypes";

interface ProtocolIdentityPanelProps {
  review: IdentityReviewView;
  busy: boolean;
  onConfirm: (input: ConfirmIdentityInput) => void;
  onCancel: () => void;
  errorMessage?: string;
}

function datePrecision(value: string): ConfirmableDatePrecision | null {
  if (/^\d{4}$/.test(value)) {
    return Number(value) >= 1 ? "year" : null;
  }
  const month = /^(\d{4})-(\d{2})$/.exec(value);
  if (month !== null) {
    const yearNumber = Number(month[1]);
    const monthNumber = Number(month[2]);
    return yearNumber >= 1 && monthNumber >= 1 && monthNumber <= 12 ? "month" : null;
  }
  const day = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (day === null) return null;
  const [yearNumber, monthNumber, dayNumber] = day.slice(1).map(Number);
  if (yearNumber < 1) return null;
  const parsed = new Date(Date.UTC(yearNumber, monthNumber - 1, dayNumber));
  return parsed.getUTCFullYear() === yearNumber &&
    parsed.getUTCMonth() === monthNumber - 1 &&
    parsed.getUTCDate() === dayNumber
    ? "day"
    : null;
}

interface MetadataCandidateGroup {
  candidate: MetadataCandidateView;
  count: number;
}

function groupRepeatedMetadataCandidates(
  candidates: MetadataCandidateView[],
): MetadataCandidateGroup[] {
  const groups = new Map<string, MetadataCandidateGroup>();
  candidates.forEach((candidate) => {
    const key = [
      candidate.field,
      candidate.value,
      candidate.sourceLabel,
      candidate.sourceExcerpt,
    ].join("\u0000");
    const current = groups.get(key);
    groups.set(
      key,
      current === undefined
        ? { candidate, count: 1 }
        : { candidate: current.candidate, count: current.count + 1 },
    );
  });
  return [...groups.values()];
}

export function ProtocolIdentityPanel({
  review,
  busy,
  onConfirm,
  onCancel,
  errorMessage,
}: ProtocolIdentityPanelProps) {
  const { identity, phaseCandidates, metadataCandidates, metadataConflicts } = review;
  const [protocolCode, setProtocolCode] = useState(identity.protocolCode ?? "");
  const [projectName, setProjectName] = useState(identity.projectName ?? "");
  const [projectCode, setProjectCode] = useState(identity.projectCode ?? "");
  const [officialVersion, setOfficialVersion] = useState(identity.officialVersion ?? "");
  const [officialDateValue, setOfficialDateValue] = useState(identity.officialDateValue ?? "");
  const [selectedCandidateIds, setSelectedCandidateIds] = useState(
    identity.selectedCandidateIds,
  );
  const [studyPhase, setStudyPhase] = useState(
    identity.studyPhase ?? (phaseCandidates.length === 1 ? phaseCandidates[0].phase : null),
  );
  const officialDatePrecision = datePrecision(officialDateValue);
  const canSubmit =
    protocolCode.trim().length > 0 &&
    projectName.trim().length > 0 &&
    officialVersion.trim().length > 0 &&
    officialDatePrecision !== null &&
    studyPhase !== null &&
    phaseCandidates.some((candidate) => candidate.phase === studyPhase);

  const submit = () => {
    if (!canSubmit || officialDatePrecision === null || studyPhase === null) return;
    onConfirm({
      protocolCode: protocolCode.trim(),
      projectName: projectName.trim(),
      projectCode: projectCode.trim() || null,
      officialVersion: officialVersion.trim(),
      officialDateValue,
      officialDatePrecision,
      studyPhase,
      selectedCandidateIds,
    });
  };

  const chooseMetadataCandidate = (
    field: string,
    candidateId: string,
    value: string,
  ) => {
    const fieldCandidateIds = new Set(
      metadataCandidates
        .filter((candidate) => candidate.field === field)
        .map((candidate) => candidate.candidateId),
    );
    setSelectedCandidateIds((current) => [
      ...current.filter((id) => !fieldCandidateIds.has(id)),
      candidateId,
    ]);
    switch (field) {
      case "protocol_code":
        setProtocolCode(value);
        break;
      case "project_name":
        setProjectName(value);
        break;
      case "project_code":
        setProjectCode(value);
        break;
      case "protocol_version":
        setOfficialVersion(value);
        break;
      case "protocol_date":
        setOfficialDateValue(value);
        break;
    }
  };

  const metadataById = new Map(
    metadataCandidates.map((candidate) => [candidate.candidateId, candidate]),
  );
  const metadataCandidateGroups = groupRepeatedMetadataCandidates(metadataCandidates);

  return (
    <div className="protocol-identity">
      <header className="page-head">
        <h1 className="page-head__title">核对方案信息与研究期别</h1>
        <p className="page-head__note">
          请核对从方案原文提取的编号、版本与研究期别。确认后将只解构所选期别及明确共享条款。
        </p>
      </header>

      <section className="protocol-identity__summary" aria-label="提取到的方案信息">
        <div className="protocol-identity__fields">
          <label>
            <span>方案编号</span>
            <input value={protocolCode} onChange={(event) => setProtocolCode(event.target.value)} />
          </label>
          <label>
            <span>项目名称</span>
            <input value={projectName} onChange={(event) => setProjectName(event.target.value)} />
          </label>
          <label>
            <span>项目代号（可不填）</span>
            <input value={projectCode} onChange={(event) => setProjectCode(event.target.value)} />
          </label>
          <label>
            <span>正式版本</span>
            <input value={officialVersion} onChange={(event) => setOfficialVersion(event.target.value)} />
          </label>
          <label>
            <span>版本日期</span>
            <input
              value={officialDateValue}
              inputMode="numeric"
              placeholder="例如：2026-08-17"
              aria-invalid={officialDateValue.length > 0 && officialDatePrecision === null}
              aria-describedby="protocol-date-hint"
              onChange={(event) => setOfficialDateValue(event.target.value.trim())}
            />
            <small id="protocol-date-hint">可填写年、年月或完整日期</small>
          </label>
        </div>
      </section>

      {metadataCandidates.length > 0 && (
        <section className="protocol-identity__candidates" aria-labelledby="protocol-candidates-title">
          <h2 id="protocol-candidates-title" className="protocol-section__title">
            方案信息提取依据
          </h2>
          <ul className="protocol-metadata-candidate-list">
            {metadataCandidateGroups.map(({ candidate, count }) => (
              <li key={candidate.candidateId} className="protocol-metadata-candidate">
                <div className="protocol-metadata-candidate__head">
                  <strong>{candidate.fieldLabel}</strong>
                  <span>{candidate.value}</span>
                  <small>
                    {candidate.sourceLabel}
                    {count > 1 ? ` · 共 ${count} 处相同记录` : ""}
                  </small>
                </div>
                <p>{candidate.sourceExcerpt}</p>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="protocol-identity__phase" aria-labelledby="protocol-phase-title">
        <h2 id="protocol-phase-title" className="protocol-section__title">
          研究期别确认
        </h2>
        {phaseCandidates.length === 0 ? (
          <p className="protocol-identity__empty">暂无期别候选，请等待结构提取完成。</p>
        ) : (
          <>
          {phaseCandidates.length > 1 && studyPhase === null && (
            <p className="protocol-identity__phase-required" role="status">
              本方案包含多个研究期别，请先选择本次要建立的独立项目期别。
            </p>
          )}
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
                  <span className="protocol-phase-option__source">
                    来源摘录：{candidate.sourceExcerpt}
                  </span>
                </label>
              </li>
            ))}
          </ul>
          </>
        )}
      </section>

      {metadataConflicts.length > 0 && (
        <section className="protocol-identity__conflicts" role="alert">
          <h2 className="protocol-section__title">方案信息存在冲突</h2>
          <ul>
            {metadataConflicts.map((conflict) => (
              <li key={conflict.conflictId} className="protocol-metadata-conflict">
                <fieldset>
                  <legend>{conflict.fieldLabel}</legend>
                  <p>{conflict.reason}</p>
                  {conflict.candidates.map((candidate) => {
                    const sourceCandidate = metadataById.get(candidate.candidateId);
                    return (
                      <label key={candidate.candidateId} className="protocol-metadata-option">
                        <input
                          type="radio"
                          name={`identity-conflict-${conflict.conflictId}`}
                          checked={selectedCandidateIds.includes(candidate.candidateId)}
                          onChange={() =>
                            chooseMetadataCandidate(
                              conflict.field,
                              candidate.candidateId,
                              candidate.value,
                            )
                          }
                        />
                        <span>
                          <strong>{candidate.value}</strong>
                          <small>{candidate.sourceLabel}</small>
                          {sourceCandidate?.sourceExcerpt && (
                            <small>{sourceCandidate.sourceExcerpt}</small>
                          )}
                        </span>
                      </label>
                    );
                  })}
                </fieldset>
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="protocol-identity__actions">
        {errorMessage !== undefined && errorMessage.length > 0 && (
          <p className="protocol-identity__error" role="alert">
            {errorMessage}
          </p>
        )}
        {!canSubmit && (
          <p className="protocol-identity__required" role="status">
            请补全方案编号、项目名称、正式版本和版本日期，并确认研究期别。
          </p>
        )}
        <button
          type="button"
          className="button button--primary"
          disabled={busy || !canSubmit}
          onClick={submit}
        >
          确认并继续解构
        </button>
        <button type="button" className="button button--quiet" disabled={busy} onClick={onCancel}>
          返回首页
        </button>
      </div>
    </div>
  );
}
