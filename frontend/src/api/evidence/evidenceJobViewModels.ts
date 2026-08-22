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
  progress: EvidenceJobProgressView;
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
