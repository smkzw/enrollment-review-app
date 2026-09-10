/** 持久资料整理任务的前端投影。组件只消费中文业务字段，不展示内部分类。 */

import { EvidenceDecodeError } from "./evidenceViewModels";

export interface EvidenceJobStepView {
  stepId: string;
  name: string;
  state: string;
  stateLabel: string;
  attempt: number;
  maxAttempts: number;
  retryable: boolean;
}

export interface EvidenceJobEventView {
  eventId: string;
  eventType: string;
  eventTypeLabel: string;
  occurredAt: string;
  attempt: number;
  retryable: boolean;
  progressCompleted: number;
  progressTotal: number;
}

export interface EvidenceJobStatusView {
  jobId: string;
  isTargetedReview?: boolean;
  isPageReview?: boolean;
  state: string;
  stateLabel: string;
  cancelRequested: boolean;
  progressCompleted: number;
  progressTotal: number;
  recoveryAction: string;
  createdAt: string;
  updatedAt: string;
  steps: EvidenceJobStepView[];
  events: EvidenceJobEventView[];
}

export interface EvidenceFileProgressView {
  sourceDocumentVersionId: string;
  fileName: string;
  pageTotal: number;
  pageSucceeded: number;
  pageFailed: number;
  status: string;
  statusLabel: string;
}

export interface EvidenceJobProgressView {
  jobId: string;
  jobState: string;
  jobStateLabel: string;
  totalPages: number;
  completedPages: number;
  failedPages: number;
  pendingPages: number;
  scopeNote: string;
  files: EvidenceFileProgressView[];
}

export interface EvidenceJobDetailView {
  status: EvidenceJobStatusView;
  progress: EvidenceJobProgressView | null;
}

/** 页面视觉核验任务（修订级投影）：组件只消费中文业务字段与稳定机器状态。 */
export interface SelectiveVisionTaskView {
  evidenceProcessingRevisionId: string;
  found: boolean;
  jobId: string | null;
  state: string | null;
  stateLabel: string;
  cancelRequested: boolean;
  progressCompleted: number;
  progressTotal: number;
  recoveryAction: string;
  canRetry: boolean;
  canCancel: boolean;
  eligiblePageCount: number | null;
  skippedPageCount: number | null;
  observationPageCount: number | null;
  closedPageCount: number | null;
  closedReasonLabel: string | null;
  failedScopeLabel: string | null;
  createdAt: string | null;
  updatedAt: string | null;
}

export interface SelectiveVisionTaskActionView {
  jobId: string;
  state: string;
  stateLabel: string;
  changed: boolean;
}

function record(value: unknown, path: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new EvidenceDecodeError(`${path} 不是可识别的记录。`);
  }
  return value as Record<string, unknown>;
}

function stringValue(row: Record<string, unknown>, key: string, path: string): string {
  const value = row[key];
  if (typeof value !== "string" || value.length === 0) {
    throw new EvidenceDecodeError(`${path}.${key} 缺少文字内容。`);
  }
  return value;
}

function numberValue(row: Record<string, unknown>, key: string, path: string): number {
  const value = row[key];
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0) {
    throw new EvidenceDecodeError(`${path}.${key} 不是有效数量。`);
  }
  return value;
}

function booleanValue(row: Record<string, unknown>, key: string, path: string): boolean {
  const value = row[key];
  if (typeof value !== "boolean") {
    throw new EvidenceDecodeError(`${path}.${key} 不是有效的是非值。`);
  }
  return value;
}

function arrayValue(row: Record<string, unknown>, key: string, path: string): unknown[] {
  const value = row[key];
  if (!Array.isArray(value)) {
    throw new EvidenceDecodeError(`${path}.${key} 不是有效清单。`);
  }
  return value;
}

export function decodeEvidenceJobStatus(payload: unknown): EvidenceJobStatusView {
  const row = record(payload, "task");
  return {
    jobId: stringValue(row, "job_id", "task"),
    isTargetedReview: optionalStringValue(row, "job_type", "task") === "r3_targeted_page_review",
    isPageReview: optionalStringValue(row, "job_type", "task") === "r3_page_review",
    state: stringValue(row, "state", "task"),
    stateLabel: stringValue(row, "state_label", "task"),
    cancelRequested: booleanValue(row, "cancel_requested", "task"),
    progressCompleted: numberValue(row, "progress_completed", "task"),
    progressTotal: numberValue(row, "progress_total", "task"),
    recoveryAction: stringValue(row, "recovery_action", "task"),
    createdAt: stringValue(row, "created_at", "task"),
    updatedAt: stringValue(row, "updated_at", "task"),
    steps: arrayValue(row, "steps", "task").map((item, index) => {
      const step = record(item, `task.steps[${index}]`);
      return {
        stepId: stringValue(step, "step_id", `task.steps[${index}]`),
        name: stringValue(step, "name", `task.steps[${index}]`),
        state: stringValue(step, "state", `task.steps[${index}]`),
        stateLabel: stringValue(step, "state_label", `task.steps[${index}]`),
        attempt: numberValue(step, "attempt", `task.steps[${index}]`),
        maxAttempts: numberValue(step, "max_attempts", `task.steps[${index}]`),
        retryable: booleanValue(step, "retryable", `task.steps[${index}]`),
      };
    }),
    events: arrayValue(row, "events", "task").map((item, index) => {
      const event = record(item, `task.events[${index}]`);
      return {
        eventId: stringValue(event, "job_event_id", `task.events[${index}]`),
        eventType: stringValue(event, "event_type", `task.events[${index}]`),
        eventTypeLabel: stringValue(event, "event_type_label", `task.events[${index}]`),
        occurredAt: stringValue(event, "occurred_at", `task.events[${index}]`),
        attempt: numberValue(event, "attempt", `task.events[${index}]`),
        retryable: booleanValue(event, "retryable", `task.events[${index}]`),
        progressCompleted: numberValue(event, "progress_completed", `task.events[${index}]`),
        progressTotal: numberValue(event, "progress_total", `task.events[${index}]`),
      };
    }),
  };
}

function optionalStringValue(
  row: Record<string, unknown>,
  key: string,
  path: string,
): string | null {
  const value = row[key];
  if (value === null || value === undefined) return null;
  if (typeof value !== "string") {
    throw new EvidenceDecodeError(`${path}.${key} 不是有效的文字内容。`);
  }
  return value;
}

function optionalNumberValue(
  row: Record<string, unknown>,
  key: string,
  path: string,
): number | null {
  const value = row[key];
  if (value === null || value === undefined) return null;
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0) {
    throw new EvidenceDecodeError(`${path}.${key} 不是有效数量。`);
  }
  return value;
}

export function decodeSelectiveVisionTask(
  payload: unknown,
): SelectiveVisionTaskView {
  const row = record(payload, "visionTask");
  return {
    evidenceProcessingRevisionId: stringValue(
      row,
      "evidence_processing_revision_id",
      "visionTask",
    ),
    found: booleanValue(row, "found", "visionTask"),
    jobId: optionalStringValue(row, "job_id", "visionTask"),
    state: optionalStringValue(row, "state", "visionTask"),
    stateLabel: stringValue(row, "state_label", "visionTask"),
    cancelRequested: booleanValue(row, "cancel_requested", "visionTask"),
    progressCompleted: numberValue(row, "progress_completed", "visionTask"),
    progressTotal: numberValue(row, "progress_total", "visionTask"),
    recoveryAction: stringValue(row, "recovery_action", "visionTask"),
    canRetry: booleanValue(row, "can_retry", "visionTask"),
    canCancel: booleanValue(row, "can_cancel", "visionTask"),
    eligiblePageCount: optionalNumberValue(
      row,
      "eligible_page_count",
      "visionTask",
    ),
    skippedPageCount: optionalNumberValue(
      row,
      "skipped_page_count",
      "visionTask",
    ),
    observationPageCount: optionalNumberValue(
      row,
      "observation_page_count",
      "visionTask",
    ),
    closedPageCount: optionalNumberValue(row, "closed_page_count", "visionTask"),
    closedReasonLabel: optionalStringValue(
      row,
      "closed_reason_label",
      "visionTask",
    ),
    failedScopeLabel: optionalStringValue(
      row,
      "failed_scope_label",
      "visionTask",
    ),
    createdAt: optionalStringValue(row, "created_at", "visionTask"),
    updatedAt: optionalStringValue(row, "updated_at", "visionTask"),
  };
}

export function decodeSelectiveVisionTaskAction(
  payload: unknown,
): SelectiveVisionTaskActionView {
  const row = record(payload, "visionTaskAction");
  return {
    jobId: stringValue(row, "job_id", "visionTaskAction"),
    state: stringValue(row, "state", "visionTaskAction"),
    stateLabel: stringValue(row, "state_label", "visionTaskAction"),
    changed: booleanValue(row, "changed", "visionTaskAction"),
  };
}

export function decodeEvidenceJobProgress(payload: unknown): EvidenceJobProgressView {
  const row = record(payload, "progress");
  return {
    jobId: stringValue(row, "job_id", "progress"),
    jobState: stringValue(row, "job_state", "progress"),
    jobStateLabel: stringValue(row, "job_state_label", "progress"),
    totalPages: numberValue(row, "total_pages", "progress"),
    completedPages: numberValue(row, "completed_pages", "progress"),
    failedPages: numberValue(row, "failed_pages", "progress"),
    pendingPages: numberValue(row, "pending_pages", "progress"),
    scopeNote: stringValue(row, "scope_note", "progress"),
    files: arrayValue(row, "files", "progress").map((item, index) => {
      const file = record(item, `progress.files[${index}]`);
      return {
        sourceDocumentVersionId: stringValue(file, "source_document_version_id", `progress.files[${index}]`),
        fileName: stringValue(file, "file_name", `progress.files[${index}]`),
        pageTotal: numberValue(file, "page_total", `progress.files[${index}]`),
        pageSucceeded: numberValue(file, "page_succeeded", `progress.files[${index}]`),
        pageFailed: numberValue(file, "page_failed", `progress.files[${index}]`),
        status: stringValue(file, "status", `progress.files[${index}]`),
        statusLabel: stringValue(file, "status_label", `progress.files[${index}]`),
      };
    }),
  };
}
