/**
 * Slice 5.7 人工事实修订响应的严格运行时解码。
 * 修订预览、任务状态和历史都来自真实 V2 API；未知状态或缺字段直接失败，
 * 不把后端机器值静默显示到医学界面。
 */

import {
  PatientProfileApiError,
  PatientProfileDecodeError,
} from "./patientProfileViewModels";
import type {
  FactCorrectionJsonValue,
  FactCorrectionTargetKind,
} from "./factCorrectionTypes";

export type FactCorrectionJsonPrimitive = null | boolean | number | string;
export type FactCorrectionJsonRecord = {
  [key: string]: FactCorrectionJsonValue;
};

export type FactCorrectionScopeKind = "local" | "node";
export type FactCorrectionJobState =
  | "queued"
  | "running"
  | "completed"
  | "failed_retryable"
  | "failed_final"
  | "cancel_requested"
  | "cancelled"
  | "recovering"
  | "waiting_user";

export interface FactCorrectionImpactView {
  scopeKind: FactCorrectionScopeKind;
  scopeKindLabel: string;
  fallbackReason: string | null;
  affectedLocatorIds: string[];
  affectedDocumentIds: string[];
  affectedFactIds: string[];
  affectedEventIds: string[];
  affectedExposureIds: string[];
  affectedConflictGroupIds: string[];
  affectedRuleLinkIds: string[];
  affectedExpectationIds: string[];
  affectedProfileRevisionIds: string[];
}

export interface FactCorrectionPreviewView {
  targetKind: FactCorrectionTargetKind;
  targetKindLabel: string;
  targetId: string;
  locatorIds: string[];
  oldSnapshot: FactCorrectionJsonRecord;
  newSnapshot: FactCorrectionJsonRecord;
  impact: FactCorrectionImpactView;
}

export interface FactCorrectionSubmitView {
  jobId: string;
  correctionId: string;
  created: boolean;
  state: FactCorrectionJobState;
  stateLabel: string;
  recoveryAction: string;
}

export interface FactCorrectionRecordView {
  correctionId: string;
  targetKind: FactCorrectionTargetKind;
  targetKindLabel: string;
  targetId: string;
  newEntityId: string;
  reason: string;
  operatorId: string;
  locatorIds: string[];
  correctedAt: string;
  oldSnapshot: FactCorrectionJsonRecord;
  newSnapshot: FactCorrectionJsonRecord;
  impact: FactCorrectionImpactView;
  profileRevisionId: string;
  profileRevision: number;
}

export interface FactCorrectionHistoryView {
  subjectId: string;
  reviewEpisodeId: string;
  items: FactCorrectionRecordView[];
}

export interface FactCorrectionJobStatusView {
  jobId: string;
  state: FactCorrectionJobState;
  stateLabel: string;
  cancelRequested: boolean;
  progressCompleted: number;
  progressTotal: number;
  errorCode: string | null;
  errorClassification: string | null;
  retryableScope: string[];
  recoveryAction: string;
  createdAt: string;
  updatedAt: string;
  lastEventSeq: number;
}

export interface FactCorrectionJobActionView {
  jobId: string;
  state: FactCorrectionJobState;
  stateLabel: string;
  changed: boolean;
}

function record(value: unknown, path: string): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new PatientProfileDecodeError(`${path} 应为对象。`);
  }
  return value as Record<string, unknown>;
}

function requiredField(row: Record<string, unknown>, key: string, path: string): unknown {
  if (!(key in row)) throw new PatientProfileDecodeError(`${path}.${key} 缺少字段。`);
  return row[key];
}

function requiredString(value: unknown, path: string): string {
  if (typeof value !== "string" || value.trim().length === 0) {
    throw new PatientProfileDecodeError(`${path} 应为非空文字。`);
  }
  return value;
}

function nullableString(value: unknown, path: string): string | null {
  if (value === null) return null;
  return requiredString(value, path);
}

function requiredBoolean(value: unknown, path: string): boolean {
  if (typeof value !== "boolean") throw new PatientProfileDecodeError(`${path} 应为布尔值。`);
  return value;
}

function nonNegativeInteger(value: unknown, path: string): number {
  if (typeof value !== "number" || !Number.isInteger(value) || value < 0) {
    throw new PatientProfileDecodeError(`${path} 应为非负整数。`);
  }
  return value;
}

function positiveInteger(value: unknown, path: string): number {
  const decoded = nonNegativeInteger(value, path);
  if (decoded === 0) {
    throw new PatientProfileDecodeError(`${path} 应为正整数。`);
  }
  return decoded;
}

function stringArray(value: unknown, path: string): string[] {
  if (!Array.isArray(value)) throw new PatientProfileDecodeError(`${path} 应为文字清单。`);
  return value.map((entry, index) => requiredString(entry, `${path}[${index}]`));
}

function jsonValue(value: unknown, path: string): FactCorrectionJsonValue {
  if (value === null || typeof value === "string" || typeof value === "boolean") {
    return value;
  }
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new PatientProfileDecodeError(`${path} 含无效数值。`);
    return value;
  }
  if (Array.isArray(value)) {
    return value.map((entry, index) => jsonValue(entry, `${path}[${index}]`));
  }
  const row = record(value, path);
  const result: FactCorrectionJsonRecord = {};
  for (const [key, entry] of Object.entries(row)) {
    result[key] = jsonValue(entry, `${path}.${key}`);
  }
  return result;
}

function jsonRecord(value: unknown, path: string): FactCorrectionJsonRecord {
  const decoded = jsonValue(value, path);
  if (decoded === null || Array.isArray(decoded) || typeof decoded !== "object") {
    throw new PatientProfileDecodeError(`${path} 应为 JSON 对象。`);
  }
  return decoded;
}

function targetKind(value: unknown, path: string): FactCorrectionTargetKind {
  if (value === "fact" || value === "event" || value === "exposure") return value;
  throw new PatientProfileDecodeError(`${path} 不是可识别的修订对象。`);
}

function scopeKind(value: unknown, path: string): FactCorrectionScopeKind {
  if (value === "local" || value === "node") return value;
  throw new PatientProfileDecodeError(`${path} 不是可识别的影响范围。`);
}

function jobState(value: unknown, path: string): FactCorrectionJobState {
  const states: FactCorrectionJobState[] = [
    "queued",
    "running",
    "completed",
    "failed_retryable",
    "failed_final",
    "cancel_requested",
    "cancelled",
    "recovering",
    "waiting_user",
  ];
  if (typeof value === "string" && states.includes(value as FactCorrectionJobState)) {
    return value as FactCorrectionJobState;
  }
  throw new PatientProfileDecodeError(`${path} 不是可识别的处理状态。`);
}

function impact(value: unknown, path: string): FactCorrectionImpactView {
  const row = record(value, path);
  return {
    scopeKind: scopeKind(requiredField(row, "scope_kind", path), `${path}.scope_kind`),
    scopeKindLabel: requiredString(
      requiredField(row, "scope_kind_label", path),
      `${path}.scope_kind_label`,
    ),
    fallbackReason: nullableString(
      requiredField(row, "fallback_reason", path),
      `${path}.fallback_reason`,
    ),
    affectedLocatorIds: stringArray(
      requiredField(row, "affected_locator_ids", path),
      `${path}.affected_locator_ids`,
    ),
    affectedDocumentIds: stringArray(
      requiredField(row, "affected_document_ids", path),
      `${path}.affected_document_ids`,
    ),
    affectedFactIds: stringArray(
      requiredField(row, "affected_fact_ids", path),
      `${path}.affected_fact_ids`,
    ),
    affectedEventIds: stringArray(
      requiredField(row, "affected_event_ids", path),
      `${path}.affected_event_ids`,
    ),
    affectedExposureIds: stringArray(
      requiredField(row, "affected_exposure_ids", path),
      `${path}.affected_exposure_ids`,
    ),
    affectedConflictGroupIds: stringArray(
      requiredField(row, "affected_conflict_group_ids", path),
      `${path}.affected_conflict_group_ids`,
    ),
    affectedRuleLinkIds: stringArray(
      requiredField(row, "affected_rule_link_ids", path),
      `${path}.affected_rule_link_ids`,
    ),
    affectedExpectationIds: stringArray(
      requiredField(row, "affected_expectation_ids", path),
      `${path}.affected_expectation_ids`,
    ),
    affectedProfileRevisionIds: stringArray(
      requiredField(row, "affected_profile_revision_ids", path),
      `${path}.affected_profile_revision_ids`,
    ),
  };
}

export function decodeFactCorrectionError(
  payload: unknown,
  statusCode: number,
): PatientProfileApiError {
  try {
    const envelope = record(payload, "error");
    const error = record(requiredField(envelope, "error", "response"), "response.error");
    return new PatientProfileApiError(
      requiredString(requiredField(error, "code", "response.error"), "response.error.code"),
      requiredString(requiredField(error, "title", "response.error"), "response.error.title"),
      requiredString(requiredField(error, "detail", "response.error"), "response.error.detail"),
      requiredString(
        requiredField(error, "recovery_action", "response.error"),
        "response.error.recovery_action",
      ),
      statusCode,
    );
  } catch (error) {
    if (error instanceof PatientProfileDecodeError) {
      return new PatientProfileApiError(
        "INVALID_RESPONSE",
        "服务响应异常",
        "修订服务返回了无法识别的错误说明。",
        "请稍后重新读取；若问题持续出现，请联系维护人员。",
        statusCode,
      );
    }
    throw error;
  }
}

export function decodeFactCorrectionPreview(payload: unknown): FactCorrectionPreviewView {
  const row = record(payload, "preview");
  return {
    targetKind: targetKind(requiredField(row, "target_kind", "preview"), "preview.target_kind"),
    targetKindLabel: requiredString(
      requiredField(row, "target_kind_label", "preview"),
      "preview.target_kind_label",
    ),
    targetId: requiredString(requiredField(row, "target_id", "preview"), "preview.target_id"),
    locatorIds: stringArray(
      requiredField(row, "locator_ids", "preview"),
      "preview.locator_ids",
    ),
    oldSnapshot: jsonRecord(
      requiredField(row, "old_snapshot", "preview"),
      "preview.old_snapshot",
    ),
    newSnapshot: jsonRecord(
      requiredField(row, "new_snapshot", "preview"),
      "preview.new_snapshot",
    ),
    impact: impact(requiredField(row, "impact", "preview"), "preview.impact"),
  };
}

export function decodeFactCorrectionSubmit(payload: unknown): FactCorrectionSubmitView {
  const row = record(payload, "submit");
  return {
    jobId: requiredString(requiredField(row, "job_id", "submit"), "submit.job_id"),
    correctionId: requiredString(
      requiredField(row, "correction_id", "submit"),
      "submit.correction_id",
    ),
    created: requiredBoolean(requiredField(row, "created", "submit"), "submit.created"),
    state: jobState(requiredField(row, "state", "submit"), "submit.state"),
    stateLabel: requiredString(
      requiredField(row, "state_label", "submit"),
      "submit.state_label",
    ),
    recoveryAction: requiredString(
      requiredField(row, "recovery_action", "submit"),
      "submit.recovery_action",
    ),
  };
}

function correctionRecord(value: unknown, path: string): FactCorrectionRecordView {
  const row = record(value, path);
  return {
    correctionId: requiredString(requiredField(row, "correction_id", path), `${path}.correction_id`),
    targetKind: targetKind(requiredField(row, "target_kind", path), `${path}.target_kind`),
    targetKindLabel: requiredString(
      requiredField(row, "target_kind_label", path),
      `${path}.target_kind_label`,
    ),
    targetId: requiredString(requiredField(row, "target_id", path), `${path}.target_id`),
    newEntityId: requiredString(
      requiredField(row, "new_entity_id", path),
      `${path}.new_entity_id`,
    ),
    reason: requiredString(requiredField(row, "reason", path), `${path}.reason`),
    operatorId: requiredString(requiredField(row, "operator_id", path), `${path}.operator_id`),
    locatorIds: stringArray(requiredField(row, "locator_ids", path), `${path}.locator_ids`),
    correctedAt: requiredString(
      requiredField(row, "corrected_at", path),
      `${path}.corrected_at`,
    ),
    oldSnapshot: jsonRecord(
      requiredField(row, "old_snapshot", path),
      `${path}.old_snapshot`,
    ),
    newSnapshot: jsonRecord(
      requiredField(row, "new_snapshot", path),
      `${path}.new_snapshot`,
    ),
    impact: impact(requiredField(row, "impact", path), `${path}.impact`),
    profileRevisionId: requiredString(
      requiredField(row, "patient_profile_revision_id", path),
      `${path}.patient_profile_revision_id`,
    ),
    profileRevision: positiveInteger(
      requiredField(row, "patient_profile_revision", path),
      `${path}.patient_profile_revision`,
    ),
  };
}

export function decodeFactCorrectionHistory(payload: unknown): FactCorrectionHistoryView {
  const row = record(payload, "history");
  const rawItems = requiredField(row, "items", "history");
  if (!Array.isArray(rawItems)) throw new PatientProfileDecodeError("history.items 应为数组。");
  return {
    subjectId: requiredString(requiredField(row, "subject_id", "history"), "history.subject_id"),
    reviewEpisodeId: requiredString(
      requiredField(row, "review_episode_id", "history"),
      "history.review_episode_id",
    ),
    items: rawItems.map((entry, index) => correctionRecord(entry, `history.items[${index}]`)),
  };
}

export function decodeFactCorrectionJobStatus(payload: unknown): FactCorrectionJobStatusView {
  const row = record(payload, "task");
  return {
    jobId: requiredString(requiredField(row, "job_id", "task"), "task.job_id"),
    state: jobState(requiredField(row, "state", "task"), "task.state"),
    stateLabel: requiredString(requiredField(row, "state_label", "task"), "task.state_label"),
    cancelRequested: requiredBoolean(
      requiredField(row, "cancel_requested", "task"),
      "task.cancel_requested",
    ),
    progressCompleted: nonNegativeInteger(
      requiredField(row, "progress_completed", "task"),
      "task.progress_completed",
    ),
    progressTotal: nonNegativeInteger(
      requiredField(row, "progress_total", "task"),
      "task.progress_total",
    ),
    errorCode: nullableString(requiredField(row, "error_code", "task"), "task.error_code"),
    errorClassification: nullableString(
      requiredField(row, "error_classification", "task"),
      "task.error_classification",
    ),
    retryableScope: stringArray(
      requiredField(row, "retryable_scope", "task"),
      "task.retryable_scope",
    ),
    recoveryAction: requiredString(
      requiredField(row, "recovery_action", "task"),
      "task.recovery_action",
    ),
    createdAt: requiredString(requiredField(row, "created_at", "task"), "task.created_at"),
    updatedAt: requiredString(requiredField(row, "updated_at", "task"), "task.updated_at"),
    lastEventSeq: nonNegativeInteger(
      requiredField(row, "last_event_seq", "task"),
      "task.last_event_seq",
    ),
  };
}

export function decodeFactCorrectionJobAction(payload: unknown): FactCorrectionJobActionView {
  const row = record(payload, "action");
  return {
    jobId: requiredString(requiredField(row, "job_id", "action"), "action.job_id"),
    state: jobState(requiredField(row, "state", "action"), "action.state"),
    stateLabel: requiredString(requiredField(row, "state_label", "action"), "action.state_label"),
    changed: requiredBoolean(requiredField(row, "changed", "action"), "action.changed"),
  };
}
