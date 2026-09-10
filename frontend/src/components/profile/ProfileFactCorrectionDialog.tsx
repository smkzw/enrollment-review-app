/**
 * Patient Profile 人工事实修订工作区（Slice 5.7）。
 * 预览是只读的；只有填写理由、完成预览并明确确认后才会创建持久任务。
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Check,
  ExternalLink,
  LoaderCircle,
  PencilLine,
  RefreshCw,
  Square,
  X,
  XCircle,
} from "lucide-react";
import { getEvidenceRepository } from "../../api/evidence";
import { getPatientProfileRepository } from "../../api/patient-profile";
import type {
  FactCorrectionDateRangeInput,
  FactCorrectionJsonValue,
  FactCorrectionJobStatusView,
  FactCorrectionPreviewView,
  FactCorrectionRequestInput,
  FactCorrectionTargetKind,
  FactCorrectionUpdates,
} from "../../api/patient-profile";
import {
  PatientProfileApiError,
  PatientProfileDecodeError,
} from "../../api/patient-profile";
import type { ProfileDatePrecisionWire } from "../../api/patient-profile/patientProfileTypes";
import type { ProfileItemView } from "../../api/patient-profile";
import type { PatientProfileModel } from "../../features/patient-profile/model";
import { locatorsForItem } from "../../features/patient-profile/model";
import { useLoad } from "../../app/useLoad";
import { UI_PHRASES } from "../../domain/labels";
import {
  CorrectionImpactSummary,
  CorrectionSnapshotPanel,
} from "./factCorrectionDisplay";

interface DateRangeDraft {
  sourceText: string;
  precision: ProfileDatePrecisionWire | "";
  lowerBound: string;
  upperBound: string;
}

interface CorrectionDraft {
  assertedObject: string;
  valueText: string;
  valueBoolean: "" | "true" | "false";
  valueKind: "string" | "number" | "boolean";
  unit: string;
  polarity: string;
  dateRange: DateRangeDraft;
  eventType: string;
  startRange: DateRangeDraft;
  endRange: DateRangeDraft;
  durationStatus: string;
  medicationName: string;
  category: string;
  indication: string;
  dose: string;
  frequency: string;
  route: string;
}

interface SourceMember {
  fileName: string;
  versionNumber: number;
}

export interface ProfileFactCorrectionCompleted {
  correctionId: string;
  jobId: string;
}

export interface ProfileFactCorrectionDialogProps {
  model: PatientProfileModel;
  item: ProfileItemView;
  targetKind: FactCorrectionTargetKind;
  subjectId: string;
  reviewEpisodeId: string;
  onClose: () => void;
  onOpenEvidence?: (item: ProfileItemView) => void;
  /** 为 true 时隐藏遮罩但保持挂载，以便查看原文后恢复草稿与预览。 */
  evidenceOpen?: boolean;
  onCompleted: (result: ProfileFactCorrectionCompleted) => void;
}

function emptyRange(): DateRangeDraft {
  return { sourceText: "", precision: "", lowerBound: "", upperBound: "" };
}

function toRangeDraft(
  range: ProfileItemView["startRange"],
): DateRangeDraft {
  if (range === null) return emptyRange();
  return {
    sourceText: range.sourceText ?? "",
    precision: range.precision ?? "",
    lowerBound: range.lowerBound ?? "",
    upperBound: range.upperBound ?? "",
  };
}

function initialDraft(item: ProfileItemView, targetKind: FactCorrectionTargetKind): CorrectionDraft {
  const value = item.value;
  return {
    assertedObject: item.assertedObject ?? "",
    valueText: value === null ? "" : String(value),
    valueBoolean: typeof value === "boolean" ? (value ? "true" : "false") : "",
    valueKind: typeof value === "number" ? "number" : typeof value === "boolean" ? "boolean" : "string",
    unit: item.unit ?? "",
    polarity: item.polarity ?? "",
    dateRange: toRangeDraft(item.startRange),
    eventType: targetKind === "event" ? item.eventType ?? "" : "",
    startRange: toRangeDraft(item.startRange),
    endRange: toRangeDraft(item.endRange),
    durationStatus: item.durationStatus ?? "",
    medicationName: item.medicationName ?? "",
    category: item.category ?? "",
    indication: item.indication ?? "",
    dose: item.dose ?? "",
    frequency: item.frequency ?? "",
    route: item.route ?? "",
  };
}

function dateRangeInput(
  draft: DateRangeDraft,
  original: ProfileItemView["startRange"],
): FactCorrectionDateRangeInput | null | undefined {
  const hasValue = Object.values(draft).some((value) => value.length > 0);
  if (!hasValue && original === null) return undefined;
  if (!hasValue) return null;
  return {
    sourceText: draft.sourceText.trim() || null,
    precision: draft.precision === "" ? null : draft.precision,
    lowerBound: draft.lowerBound.trim() || null,
    upperBound: draft.upperBound.trim() || null,
  };
}

function valueInput(draft: CorrectionDraft): { value: FactCorrectionJsonValue; error: string | null } {
  if (draft.valueKind === "number") {
    if (draft.valueText.trim() === "") return { value: null, error: null };
    const parsed = Number(draft.valueText);
    return Number.isFinite(parsed)
      ? { value: parsed, error: null }
      : { value: null, error: "请输入有效数值。" };
  }
  if (draft.valueKind === "boolean") {
    if (draft.valueBoolean === "true") return { value: true, error: null };
    if (draft.valueBoolean === "false") return { value: false, error: null };
    return { value: null, error: null };
  }
  return { value: draft.valueText.trim() || null, error: null };
}

function updatesForDraft(
  draft: CorrectionDraft,
  item: ProfileItemView,
  targetKind: FactCorrectionTargetKind,
): { updates: FactCorrectionUpdates; error: string | null } {
  if (targetKind === "fact") {
    const value = valueInput(draft);
    return {
      error: value.error,
      updates: {
        assertedObject: draft.assertedObject.trim() || null,
        value: value.value,
        unit: draft.unit.trim() || null,
        polarity: draft.polarity || null,
        dateRange: dateRangeInput(draft.dateRange, item.startRange),
      },
    };
  }

  if (targetKind === "event") {
    return {
      error: null,
      updates: {
        eventType: draft.eventType.trim() || undefined,
        startRange: dateRangeInput(draft.startRange, item.startRange),
        endRange: dateRangeInput(draft.endRange, item.endRange),
        durationStatus: draft.durationStatus || null,
        factIds: [...item.factIds],
      },
    };
  }

  return {
    error: null,
    updates: {
      medicationName: draft.medicationName.trim() || null,
      category: draft.category.trim() || null,
      indication: draft.indication.trim() || null,
      dose: draft.dose.trim() || null,
      unit: draft.unit?.trim() || null,
      frequency: draft.frequency.trim() || null,
      route: draft.route.trim() || null,
      startRange: dateRangeInput(draft.startRange, item.startRange),
      endRange: dateRangeInput(draft.endRange, item.endRange),
      durationStatus: draft.durationStatus || null,
      factIds: [...item.factIds],
    },
  };
}

function correctionRequest(
  draft: CorrectionDraft,
  item: ProfileItemView,
  targetKind: FactCorrectionTargetKind,
  reason: string,
): { request: FactCorrectionRequestInput; error: string | null } {
  const built = updatesForDraft(draft, item, targetKind);
  return {
    error: built.error,
    request: {
      targetKind,
      targetId: item.sourceId,
      locatorIds: [...item.locatorIds].sort(),
      reason: reason.trim(),
      updates: built.updates,
    },
  };
}

function errorMessage(error: unknown): string {
  if (error instanceof PatientProfileApiError) {
    return error.recoveryAction.length > 0
      ? `${error.message} ${error.recoveryAction}`
      : error.message;
  }
  if (error instanceof PatientProfileDecodeError) return "修订服务返回的内容无法识别，请重新读取。";
  return UI_PHRASES.temporarilyUnavailable;
}

function isTerminal(state: FactCorrectionJobStatusView["state"]): boolean {
  return state === "completed" || state === "failed_final" || state === "cancelled";
}

function isFailure(state: FactCorrectionJobStatusView["state"]): boolean {
  return state === "failed_retryable" || state === "failed_final";
}

function statusText(status: FactCorrectionJobStatusView | null, initial: string | null): string {
  if (status?.errorCode === "STALE_AUTHORITY") return "原资料已变化，本次修订未提交";
  return status?.stateLabel ?? initial ?? "等待处理";
}

function sourceMemberMap(
  snapshot: { members: Array<{ sourceDocumentVersionId: string; fileName: string; versionNumber: number }> } | null,
): Map<string, SourceMember> {
  if (snapshot === null) return new Map();
  return new Map(
    snapshot.members.map((member) => [
      member.sourceDocumentVersionId,
      { fileName: member.fileName, versionNumber: member.versionNumber },
    ]),
  );
}

function SourceLocatorList({
  model,
  item,
  onOpenEvidence,
}: {
  model: PatientProfileModel;
  item: ProfileItemView;
  onOpenEvidence?: (item: ProfileItemView) => void;
}) {
  const evidence = useLoad(
    (signal) =>
      getEvidenceRepository().getEvidenceSnapshot(
        model.evidenceNavigation.evidenceSnapshotV2Id,
        { signal },
      ),
    [model.evidenceNavigation.evidenceSnapshotV2Id],
  );
  const snapshot = evidence.state.status === "success" ? evidence.state.data : null;
  const members = useMemo(() => sourceMemberMap(snapshot), [snapshot]);
  const locators = locatorsForItem(model, item);

  return (
    <section className="profile-correction-sources" aria-labelledby="correction-sources-title">
      <div className="profile-correction-section-head">
        <div>
          <h3 id="correction-sources-title">来源原文</h3>
          <p>本次修订必须引用当前冻结资料中的原文定位。</p>
        </div>
        {evidence.state.status === "loading" && (
          <span className="profile-correction-inline-status">正在读取资料信息</span>
        )}
      </div>
      {locators.length === 0 ? (
        <p className="profile-correction-warning">当前条目没有可用原文定位，不能提交修订。</p>
      ) : (
        <ul className="profile-correction-source-list">
          {locators.map((locator, index) => {
            const member = members.get(locator.sourceDocumentVersionId);
            const fileText = member?.fileName ?? "资料文件";
            const versionText = member === undefined
              ? "资料版本信息待补全"
              : `资料版本第 ${member.versionNumber} 版`;
            return (
              <li key={locator.locatorId} className="profile-correction-source">
                <div className="profile-correction-source__main">
                  <strong>{fileText}</strong>
                  <span>{versionText} · 第 {locator.pageNumber} 页 · {locator.precisionLabel}</span>
                  {locator.excerpt !== null && <q>{locator.excerpt}</q>}
                  {locator.degradationReason !== null && (
                    <small>{locator.degradationReason}</small>
                  )}
                </div>
                {onOpenEvidence !== undefined && (
                  <button
                    type="button"
                    className="button button--quiet profile-correction-source__open"
                    onClick={() => onOpenEvidence(item)}
                    aria-label={`查看第 ${locator.pageNumber} 页原文定位 ${index + 1}`}
                  >
                    <ExternalLink size={15} aria-hidden="true" />
                    查看原文
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      )}
      {evidence.state.status === "error" && (
        <p className="profile-correction-inline-status">
          资料文件名暂时无法读取，仍保留页码、版本和摘录供核对。
        </p>
      )}
    </section>
  );
}

function DateRangeEditor({
  label,
  value,
  onChange,
  disabled,
}: {
  label: string;
  value: DateRangeDraft;
  onChange: (next: DateRangeDraft) => void;
  disabled: boolean;
}) {
  return (
    <fieldset className="profile-correction-date-range">
      <legend>{label}</legend>
      <div className="profile-correction-date-range__grid">
        <label>
          <span>原文日期</span>
          <input
            type="text"
            value={value.sourceText}
            disabled={disabled}
            onChange={(event) => onChange({ ...value, sourceText: event.target.value })}
            placeholder="如：2026年3月"
          />
        </label>
        <label>
          <span>精度</span>
          <select
            value={value.precision}
            disabled={disabled}
            onChange={(event) => {
              const next = event.target.value;
              if (next === "" || next === "day" || next === "month" || next === "year" || next === "unknown") {
                onChange({ ...value, precision: next });
              }
            }}
          >
            <option value="">未填写</option>
            <option value="day">日</option>
            <option value="month">月</option>
            <option value="year">年</option>
            <option value="unknown">未明确精度</option>
          </select>
        </label>
        <label>
          <span>确定下界</span>
          <input
            type="text"
            value={value.lowerBound}
            disabled={disabled}
            onChange={(event) => onChange({ ...value, lowerBound: event.target.value })}
            placeholder="可留空"
          />
        </label>
        <label>
          <span>确定上界</span>
          <input
            type="text"
            value={value.upperBound}
            disabled={disabled}
            onChange={(event) => onChange({ ...value, upperBound: event.target.value })}
            placeholder="可留空"
          />
        </label>
      </div>
    </fieldset>
  );
}

function TextField({
  label,
  value,
  onChange,
  disabled,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  disabled: boolean;
  placeholder?: string;
}) {
  return (
    <label className="profile-correction-field">
      <span>{label}</span>
      <input
        type="text"
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
      />
    </label>
  );
}

function CorrectionFields({
  targetKind,
  item,
  draft,
  onChange,
  disabled,
}: {
  targetKind: FactCorrectionTargetKind;
  item: ProfileItemView;
  draft: CorrectionDraft;
  onChange: (patch: Partial<CorrectionDraft>) => void;
  disabled: boolean;
}) {
  if (targetKind === "fact") {
    return (
      <div className="profile-correction-fields">
        <div className="profile-correction-fields__grid">
          <TextField
            label="记录项目"
            value={draft.assertedObject}
            disabled={disabled}
            onChange={(value) => onChange({ assertedObject: value })}
          />
          <label className="profile-correction-field">
            <span>记录性质</span>
            <select
              value={draft.polarity}
              disabled={disabled}
              onChange={(event) => onChange({ polarity: event.target.value })}
            >
              <option value="">未填写</option>
              <option value="affirmed">肯定</option>
              <option value="negated">否定</option>
              <option value="unknown">未明确</option>
            </select>
          </label>
          <label className="profile-correction-field">
            <span>记录结果</span>
            {draft.valueKind === "boolean" ? (
              <select
                value={draft.valueBoolean}
                disabled={disabled}
                onChange={(event) => {
                  const next = event.target.value;
                  if (next === "" || next === "true" || next === "false") {
                    onChange({ valueBoolean: next });
                  }
                }}
              >
                <option value="">未填写</option>
                <option value="true">是</option>
                <option value="false">否</option>
              </select>
            ) : (
              <input
                type={draft.valueKind === "number" ? "number" : "text"}
                value={draft.valueText}
                disabled={disabled}
                onChange={(event) => onChange({ valueText: event.target.value })}
              />
            )}
          </label>
          <TextField
            label="单位"
            value={draft.unit}
            disabled={disabled}
            onChange={(value) => onChange({ unit: value })}
            placeholder="如：mmHg"
          />
        </div>
        <DateRangeEditor
          label="事件时间"
          value={draft.dateRange}
          disabled={disabled}
          onChange={(dateRange) => onChange({ dateRange })}
        />
      </div>
    );
  }

  if (targetKind === "event") {
    return (
      <div className="profile-correction-fields">
        <div className="profile-correction-fields__grid">
          <TextField
            label="事件名称"
            value={draft.eventType}
            disabled={disabled}
            onChange={(value) => onChange({ eventType: value })}
            placeholder={item.title}
          />
          <label className="profile-correction-field">
            <span>持续状态</span>
            <select
              value={draft.durationStatus}
              disabled={disabled}
              onChange={(event) => onChange({ durationStatus: event.target.value })}
            >
              <option value="">未填写</option>
              <option value="ongoing">持续</option>
              <option value="ended">已结束</option>
              <option value="intermittent">间歇</option>
              <option value="single">单次</option>
              <option value="unknown">未明确</option>
            </select>
          </label>
        </div>
        <DateRangeEditor
          label="发生时间"
          value={draft.startRange}
          disabled={disabled}
          onChange={(startRange) => onChange({ startRange })}
        />
        <DateRangeEditor
          label="结束时间"
          value={draft.endRange}
          disabled={disabled}
          onChange={(endRange) => onChange({ endRange })}
        />
      </div>
    );
  }

  return (
    <div className="profile-correction-fields">
      <div className="profile-correction-fields__grid">
        <TextField label="药物或治疗" value={draft.medicationName} disabled={disabled} onChange={(value) => onChange({ medicationName: value })} />
        <TextField label="类别" value={draft.category} disabled={disabled} onChange={(value) => onChange({ category: value })} />
        <TextField label="适应证" value={draft.indication} disabled={disabled} onChange={(value) => onChange({ indication: value })} />
        <TextField label="剂量" value={draft.dose} disabled={disabled} onChange={(value) => onChange({ dose: value })} />
        <TextField label="剂量单位" value={draft.unit} disabled={disabled} onChange={(value) => onChange({ unit: value })} placeholder="如：mg" />
        <TextField label="频次" value={draft.frequency} disabled={disabled} onChange={(value) => onChange({ frequency: value })} />
        <TextField label="途径" value={draft.route} disabled={disabled} onChange={(value) => onChange({ route: value })} />
      </div>
      <DateRangeEditor
        label="开始时间"
        value={draft.startRange}
        disabled={disabled}
        onChange={(startRange) => onChange({ startRange })}
      />
      <DateRangeEditor
        label="结束时间"
        value={draft.endRange}
        disabled={disabled}
        onChange={(endRange) => onChange({ endRange })}
      />
      <label className="profile-correction-field">
        <span>持续状态</span>
        <select
          value={draft.durationStatus}
          disabled={disabled}
          onChange={(event) => onChange({ durationStatus: event.target.value })}
        >
          <option value="">未填写</option>
          <option value="ongoing">持续</option>
          <option value="ended">已结束</option>
          <option value="intermittent">间歇</option>
          <option value="single">单次</option>
          <option value="unknown">未明确</option>
        </select>
      </label>
    </div>
  );
}

export function ProfileFactCorrectionDialog({
  model,
  item,
  targetKind,
  subjectId,
  reviewEpisodeId,
  onClose,
  onOpenEvidence,
  evidenceOpen = false,
  onCompleted,
}: ProfileFactCorrectionDialogProps) {
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const [draft, setDraft] = useState<CorrectionDraft>(() => initialDraft(item, targetKind));
  const [reason, setReason] = useState("");
  const [preview, setPreview] = useState<FactCorrectionPreviewView | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState<{
    jobId: string;
    correctionId: string;
    stateLabel: string;
  } | null>(null);
  const [jobStatus, setJobStatus] = useState<FactCorrectionJobStatusView | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const completionReported = useRef<string | null>(null);
  const closeBlocked =
    submitted !== null &&
    (jobStatus === null || !isTerminal(jobStatus.state));

  const updateDraft = useCallback(
    (patch: Partial<CorrectionDraft>) => {
      const canEditAgain = jobStatus !== null && isFailure(jobStatus.state);
      if (canEditAgain) {
        setSubmitted(null);
        setJobStatus(null);
        setStatusError(null);
      }
      setDraft((current) => ({ ...current, ...patch }));
      setPreview(null);
      setConfirmed(false);
      setFormError(null);
    },
    [jobStatus],
  );

  useEffect(() => {
    if (evidenceOpen) return;
    dialogRef.current?.focus();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        if (!closeBlocked) onClose();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [closeBlocked, evidenceOpen, onClose]);

  const buildRequest = useCallback(
    () => correctionRequest(draft, item, targetKind, reason),
    [draft, item, reason, targetKind],
  );

  const previewImpact = useCallback(async () => {
    if (reason.trim().length === 0) {
      setFormError("请先填写本次修订理由，再预览影响范围。");
      return;
    }
    const built = buildRequest();
    if (built.error !== null) {
      setFormError(built.error);
      return;
    }
    setPreviewing(true);
    setFormError(null);
    try {
      const next = await getPatientProfileRepository().previewFactCorrection(
        subjectId,
        reviewEpisodeId,
        built.request,
      );
      setPreview(next);
      setConfirmed(false);
    } catch (error) {
      setFormError(errorMessage(error));
    } finally {
      setPreviewing(false);
    }
  }, [buildRequest, reason, reviewEpisodeId, subjectId]);

  const submit = useCallback(async () => {
    if (preview === null) {
      setFormError("请先预览影响范围。");
      return;
    }
    if (!confirmed) {
      setFormError("请确认已核对修改前后内容和影响范围。");
      return;
    }
    const built = buildRequest();
    if (built.error !== null) {
      setFormError(built.error);
      return;
    }
    setSubmitting(true);
    setFormError(null);
    try {
      const next = await getPatientProfileRepository().submitFactCorrection(
        subjectId,
        reviewEpisodeId,
        built.request,
      );
      setSubmitted({
        jobId: next.jobId,
        correctionId: next.correctionId,
        stateLabel: next.stateLabel,
      });
      setJobStatus(null);
      setStatusError(null);
    } catch (error) {
      setFormError(errorMessage(error));
    } finally {
      setSubmitting(false);
    }
  }, [buildRequest, confirmed, preview, reviewEpisodeId, subjectId]);

  useEffect(() => {
    const job = submitted;
    if (job === null) return;
    let cancelled = false;
    let timer: number | null = null;

    const readStatus = async () => {
      try {
        const next = await getPatientProfileRepository().getFactCorrectionJobStatus(job.jobId);
        if (cancelled) return;
        setJobStatus(next);
        setStatusError(null);
        if (next.errorCode === "STALE_AUTHORITY") {
          setPreview(null);
          setConfirmed(false);
        }
        if (next.state === "completed") {
          if (completionReported.current === job.jobId) return;
          completionReported.current = job.jobId;
          if (!cancelled) {
            onCompleted({
              correctionId: job.correctionId,
              jobId: job.jobId,
            });
          }
          return;
        }
        if (!isTerminal(next.state)) timer = window.setTimeout(readStatus, 900);
      } catch (error) {
        if (cancelled) return;
        setStatusError(errorMessage(error));
        timer = window.setTimeout(readStatus, 1500);
      }
    };

    void readStatus();
    return () => {
      cancelled = true;
      if (timer !== null) window.clearTimeout(timer);
    };
  }, [onCompleted, reviewEpisodeId, subjectId, submitted]);

  const retry = useCallback(async () => {
    if (submitted === null) return;
    setStatusError(null);
    try {
      const next = await getPatientProfileRepository().retryFactCorrectionJob(submitted.jobId);
      setJobStatus((current) =>
        current === null
          ? null
          : { ...current, state: next.state, stateLabel: next.stateLabel, errorCode: null, errorClassification: null },
      );
    } catch (error) {
      setStatusError(errorMessage(error));
    }
  }, [submitted]);

  const cancel = useCallback(async () => {
    if (submitted === null) return;
    setStatusError(null);
    try {
      const next = await getPatientProfileRepository().cancelFactCorrectionJob(submitted.jobId);
      setJobStatus((current) =>
        current === null
          ? null
          : { ...current, state: next.state, stateLabel: next.stateLabel, cancelRequested: next.state === "cancel_requested" },
      );
    } catch (error) {
      setStatusError(errorMessage(error));
    }
  }, [submitted]);

  const activeStatus = jobStatus;
  const statusLabel = statusText(activeStatus, submitted?.stateLabel ?? null);
  const locked = submitted !== null && (activeStatus === null || !isFailure(activeStatus.state));
  const canRetry =
    submitted !== null &&
    activeStatus !== null &&
    isFailure(activeStatus.state) &&
    activeStatus.errorCode !== "STALE_AUTHORITY";
  const canCancel =
    submitted !== null &&
    activeStatus !== null &&
    !isTerminal(activeStatus.state) &&
    activeStatus.state !== "cancel_requested";
  const showCompleted = activeStatus?.state === "completed";

  return (
    <div
      className="profile-correction-overlay"
      role="presentation"
      aria-hidden={evidenceOpen ? true : undefined}
      style={
        evidenceOpen
          ? { visibility: "hidden", pointerEvents: "none" }
          : undefined
      }
    >
      <div
        ref={dialogRef}
        className="profile-correction-dialog"
        role="dialog"
        aria-modal={evidenceOpen ? false : true}
        aria-labelledby="profile-correction-title"
        tabIndex={-1}
      >
        <header className="profile-correction-dialog__head">
          <div>
            <p className="profile-correction-dialog__eyebrow">核对资料后追加一条修订记录</p>
            <h2 id="profile-correction-title">核对并修订：{item.title}</h2>
            <p>{item.kindLabel} · {item.laneLabel}</p>
          </div>
          <button
            type="button"
            className="icon-button"
            onClick={onClose}
            disabled={closeBlocked}
            aria-label="关闭事实修订"
            title={closeBlocked ? "处理结束前请保持窗口打开" : "关闭"}
          >
            <X size={19} aria-hidden="true" />
          </button>
        </header>

        <div className="profile-correction-dialog__body">
          <div className="profile-correction-dialog__main">
            <section className="profile-correction-current" aria-labelledby="correction-current-title">
              <div className="profile-correction-section-head">
                <div>
                  <h3 id="correction-current-title">当前记录</h3>
                  <p>只修改结构化事实、事件或用药/治疗暴露；原始资料和既有记录不会被覆盖。</p>
                </div>
                <span className="count-chip"><PencilLine size={14} aria-hidden="true" />{item.kindLabel}</span>
              </div>
              <CorrectionFields
                targetKind={targetKind}
                item={item}
                draft={draft}
                onChange={updateDraft}
                disabled={locked}
              />
            </section>

            <SourceLocatorList model={model} item={item} onOpenEvidence={onOpenEvidence} />

            <section className="profile-correction-reason" aria-labelledby="correction-reason-title">
              <label htmlFor="correction-reason">
                <span id="correction-reason-title">修订理由（必填）</span>
                <textarea
                  id="correction-reason"
                  value={reason}
                  disabled={locked}
                  onChange={(event) => {
                    setReason(event.target.value);
                    setPreview(null);
                    setConfirmed(false);
                    setFormError(null);
                  }}
                  rows={3}
                  placeholder="请说明原文与当前记录的差异，以及本次修订依据。"
                />
              </label>
            </section>

            {formError !== null && <p className="profile-correction-error" role="alert">{formError}</p>}

            <div className="profile-correction-dialog__actions">
              <button
                type="button"
                className="button"
                onClick={() => void previewImpact()}
                disabled={previewing || locked}
              >
                {previewing ? <LoaderCircle className="profile-correction-spin" size={16} aria-hidden="true" /> : <Square size={15} aria-hidden="true" />}
                预览影响范围
              </button>
              <button
                type="button"
                className="button button--primary"
                onClick={() => void submit()}
                disabled={submitting || locked || preview === null || !confirmed}
              >
                {submitting ? <LoaderCircle className="profile-correction-spin" size={16} aria-hidden="true" /> : <Check size={16} aria-hidden="true" />}
                提交修订
              </button>
              <button
                type="button"
                className="button button--quiet"
                onClick={onClose}
                disabled={closeBlocked}
                title={closeBlocked ? "处理结束前请保持窗口打开" : undefined}
              >
                {closeBlocked ? "处理中请保持窗口打开" : "先关闭"}
              </button>
            </div>
          </div>

          <aside className="profile-correction-dialog__side" aria-label="修订预览与任务状态">
            <section className="profile-correction-preview" aria-labelledby="correction-preview-title">
              <div className="profile-correction-section-head">
                <div>
                  <h3 id="correction-preview-title">影响范围预览</h3>
                  <p>只读预览，不会写入任何新记录。</p>
                </div>
                {preview !== null && <span className="status-badge status-badge--info">已生成预览</span>}
              </div>
              {preview === null ? (
                <p className="profile-correction-placeholder">填写理由并预览后，这里会显示修改前后内容和确定性影响范围。</p>
              ) : (
                <div className="profile-correction-preview__content">
                  <div className="profile-correction-comparison">
                    <CorrectionSnapshotPanel
                      label="修改前"
                      snapshot={preview.oldSnapshot}
                      targetKind={targetKind}
                      item={item}
                    />
                    <CorrectionSnapshotPanel
                      label="拟修改"
                      snapshot={preview.newSnapshot}
                      targetKind={targetKind}
                      item={item}
                    />
                  </div>
                  <section className={`profile-correction-impact${preview.impact.scopeKind === "node" ? " profile-correction-impact--node" : ""}`}>
                    <div className="profile-correction-section-head">
                      <div>
                        <h4>影响范围</h4>
                        <p>{preview.impact.scopeKindLabel}</p>
                      </div>
                    </div>
                    {preview.impact.scopeKind === "node" && (
                      <p className="profile-correction-impact__notice">
                        将重新整理本审核节点全部事实。既有档案版本保持不变，完成后只会生成新的当前档案版本。
                      </p>
                    )}
                    {preview.impact.fallbackReason !== null &&
                      preview.impact.fallbackReason !== "将重新整理本审核节点全部事实" && (
                      <p className="profile-correction-impact__reason">{preview.impact.fallbackReason}</p>
                    )}
                    <CorrectionImpactSummary impact={preview.impact} />
                  </section>
                  <label className="profile-correction-confirm">
                    <input
                      type="checkbox"
                      checked={confirmed}
                      disabled={locked}
                      onChange={(event) => setConfirmed(event.target.checked)}
                    />
                    <span>我已核对修改前后内容、来源原文和影响范围，确认提交。</span>
                  </label>
                </div>
              )}
            </section>

            {submitted !== null && (
              <section className="profile-correction-job" aria-live="polite">
                <div className="profile-correction-section-head">
                  <div>
                    <h3>修订处理状态</h3>
                    <p>{statusLabel}</p>
                  </div>
                  {showCompleted ? <Check size={20} className="profile-correction-job__done" aria-label="修订已完成" /> : <LoaderCircle size={20} className="profile-correction-spin" aria-label="正在读取状态" />}
                </div>
                {activeStatus !== null && activeStatus.progressTotal > 0 && (
                  <p className="profile-correction-job__progress">已完成 {activeStatus.progressCompleted} / {activeStatus.progressTotal} 项整理</p>
                )}
                {closeBlocked && (
                  <p className="profile-correction-job__notice">
                    请保持当前窗口打开。处理结束后系统会自动刷新病历档案和修订记录。
                  </p>
                )}
                {activeStatus?.errorCode === "STALE_AUTHORITY" && (
                  <p className="profile-correction-job__warning">审核节点的活动资料已变化，本次没有写入。请返回档案重新核对。</p>
                )}
                {activeStatus !== null && isFailure(activeStatus.state) && activeStatus.errorCode !== "STALE_AUTHORITY" && (
                  <div className="profile-correction-job__recovery">
                    <p>修改内容仍保留在当前窗口，可以重新处理失败部分。</p>
                    {canRetry && (
                      <button type="button" className="button" onClick={() => void retry()}>
                        <RefreshCw size={15} aria-hidden="true" />
                        重新处理失败部分
                      </button>
                    )}
                  </div>
                )}
                {canCancel && (
                  <button type="button" className="button button--quiet" onClick={() => void cancel()}>
                    <XCircle size={15} aria-hidden="true" />
                    请求停止处理
                  </button>
                )}
                {activeStatus?.state === "cancel_requested" && (
                  <p className="profile-correction-job__warning">停止请求已受理，将在当前安全边界完成后停止。</p>
                )}
                {activeStatus?.state === "cancelled" && (
                  <p className="profile-correction-job__warning">本次修订已停止，没有显示为完成。</p>
                )}
                {showCompleted && (
                  <p className="profile-correction-job__success">修订已完成，档案和修订记录正在刷新。</p>
                )}
                {statusError !== null && (
                  <div className="profile-correction-job__error">
                    <p>{statusError}</p>
                    <button
                      type="button"
                      className="button button--quiet"
                      onClick={() => {
                        setSubmitted((current) => current === null ? null : { ...current });
                        setStatusError(null);
                      }}
                    >
                      重新读取状态
                    </button>
                  </div>
                )}
                {showCompleted && (
                  <button type="button" className="button button--quiet" onClick={onClose}>
                    关闭并回到档案
                  </button>
                )}
              </section>
            )}
          </aside>
        </div>
      </div>
    </div>
  );
}
