/**
 * V2 方案解构 wire → 视图模型校验与归一化（单一解码层，组件不重复解析）。
 */

import { ProtocolWorkbenchApiError } from "./protocolWorkbenchTypes";
import type {
  ConfirmIdentityInput,
  DraftRevisionView,
  IdentityDecisionView,
  IdentityReviewView,
  IntegrityCheckView,
  IntegrityIssueView,
  IntegrityView,
  MetadataConflictView,
  PhaseCandidateView,
  ProtocolSessionView,
  PublishResultView,
  SourcesView,
  StartDeconstructionResult,
} from "./protocolWorkbenchTypes";
import type {
  WireDraftRevisionResponse,
  WireErrorEnvelope,
  WireIdentityReviewResponse,
  WireIntegrityResponse,
  WireProtocolSessionResponse,
  WirePublishResponse,
  WireSourcesResponse,
  WireStartDeconstructionResponse,
} from "./protocolWorkbenchWire";

function requireString(value: unknown, field: string): string {
  if (typeof value !== "string" || value.length === 0) {
    throw new ProtocolWorkbenchApiError(
      "INVALID_RESPONSE",
      "服务响应异常",
      `方案解构服务返回的数据不完整（缺少 ${field}）。`,
      "请稍后重试；若问题持续出现，请联系维护人员。",
    );
  }
  return value;
}

function requireNumber(value: unknown, field: string): number {
  if (typeof value !== "number" || Number.isNaN(value)) {
    throw new ProtocolWorkbenchApiError(
      "INVALID_RESPONSE",
      "服务响应异常",
      `方案解构服务返回的数据不完整（${field} 应为数字）。`,
      "请稍后重试；若问题持续出现，请联系维护人员。",
    );
  }
  return value;
}

function optionalString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function optionalNumber(value: unknown): number | null {
  return typeof value === "number" && !Number.isNaN(value) ? value : null;
}

function optionalBoolean(value: unknown): boolean | null {
  return typeof value === "boolean" ? value : null;
}

export function decodeProtocolWorkbenchError(payload: unknown): ProtocolWorkbenchApiError {
  if (
    payload !== null &&
    typeof payload === "object" &&
    "error" in payload &&
    payload.error !== null &&
    typeof payload.error === "object"
  ) {
    const envelope = payload as WireErrorEnvelope;
    const error = envelope.error;
    const detail =
      typeof error.detail === "string" && error.detail.length > 0
        ? error.detail
        : "请求未能完成。";
    const title = typeof error.title === "string" ? error.title : "操作失败";
    const code = typeof error.code === "string" ? error.code : "UNKNOWN";
    const recovery =
      typeof error.recovery_action === "string" && error.recovery_action.length > 0
        ? error.recovery_action
        : "请稍后重试。";
    return new ProtocolWorkbenchApiError(code, title, detail, recovery);
  }
  return new ProtocolWorkbenchApiError(
    "INVALID_RESPONSE",
    "服务响应异常",
    "方案解构服务返回了无法识别的错误格式。",
    "请稍后重试；若问题持续出现，请联系维护人员。",
  );
}

export function normalizeStartDeconstruction(
  wire: WireStartDeconstructionResponse,
): StartDeconstructionResult {
  return {
    jobId: requireString(wire.job_id, "job_id"),
    state: requireString(wire.state, "state"),
    stateLabel: requireString(wire.state_label, "state_label"),
    created: wire.created === true,
    sourceArtifactId: requireString(wire.source_artifact_id, "source_artifact_id"),
    fileName: requireString(wire.file_name, "file_name"),
  };
}

export function normalizeSession(wire: WireProtocolSessionResponse): ProtocolSessionView {
  return {
    jobId: requireString(wire.job_id, "job_id"),
    jobType: requireString(wire.job_type, "job_type"),
    state: requireString(wire.state, "state"),
    stateLabel: requireString(wire.state_label, "state_label"),
    progressCompleted: requireNumber(wire.progress_completed, "progress_completed"),
    progressTotal: requireNumber(wire.progress_total, "progress_total"),
    sessionKind: requireString(wire.session_kind, "session_kind"),
    awaitingUser: optionalString(wire.awaiting_user),
    awaitingUserLabel: optionalString(wire.awaiting_user_label),
    sourceArtifactId: optionalString(wire.source_artifact_id),
    fileName: optionalString(wire.file_name),
    snapshotId: optionalString(wire.snapshot_id),
    draftId: optionalString(wire.draft_id),
    draftRevisionId: optionalString(wire.draft_revision_id),
    draftRevisionNumber: optionalNumber(wire.draft_revision_number),
    draftStatus: optionalString(wire.draft_status),
    draftStatusLabel: optionalString(wire.draft_status_label),
    selectedPhase: optionalString(wire.selected_phase),
    selectedPhaseLabel: optionalString(wire.selected_phase_label),
    protocolCode: optionalString(wire.protocol_code),
    officialVersion: optionalString(wire.official_version),
    recoveryCheckpointId: optionalString(wire.recovery_checkpoint_id),
    recoveryStepId: optionalString(wire.recovery_step_id),
    nextAction: requireString(wire.next_action, "next_action"),
    publishable: optionalBoolean(wire.publishable),
  };
}

function normalizePhaseCandidate(raw: Record<string, unknown>): PhaseCandidateView {
  return {
    candidateId: requireString(raw.candidate_id ?? raw.candidateId, "candidate_id"),
    phase: requireString(raw.phase, "phase"),
    phaseLabel: requireString(raw.phase_label ?? raw.phaseLabel, "phase_label"),
    rationale: requireString(raw.rationale, "rationale"),
  };
}

function normalizeMetadataConflict(raw: Record<string, unknown>): MetadataConflictView {
  const candidatesRaw = raw.candidates;
  const candidates = Array.isArray(candidatesRaw)
    ? candidatesRaw.map((item) => {
        const row = item as Record<string, unknown>;
        return {
          candidateId: requireString(row.candidate_id ?? row.candidateId, "candidate_id"),
          value: requireString(row.value, "value"),
          sourceLabel: requireString(row.source_label ?? row.sourceLabel, "source_label"),
        };
      })
    : [];
  return {
    conflictId: requireString(raw.conflict_id ?? raw.conflictId, "conflict_id"),
    field: requireString(raw.field, "field"),
    fieldLabel: requireString(raw.field_label ?? raw.fieldLabel, "field_label"),
    candidates,
  };
}

function normalizeIdentityDecision(wire: WireIdentityReviewResponse["identity"]): IdentityDecisionView {
  return {
    identityDecisionId: requireString(wire.identity_decision_id, "identity_decision_id"),
    snapshotId: requireString(wire.snapshot_id, "snapshot_id"),
    status: requireString(wire.status, "status"),
    statusLabel: requireString(wire.status_label, "status_label"),
    projectName: optionalString(wire.project_name),
    projectCode: optionalString(wire.project_code),
    protocolCode: optionalString(wire.protocol_code),
    officialVersion: optionalString(wire.official_version),
    officialDateValue: optionalString(wire.official_date_value),
    officialDatePrecision: optionalString(wire.official_date_precision),
    studyPhase: optionalString(wire.study_phase),
    studyPhaseLabel: optionalString(wire.study_phase_label),
    confirmationRequired: wire.confirmation_required === true,
    conflictIds: Array.isArray(wire.conflict_ids) ? [...wire.conflict_ids.map(String)] : [],
    selectedCandidateIds: Array.isArray(wire.selected_candidate_ids)
      ? [...wire.selected_candidate_ids.map(String)]
      : [],
  };
}

export function normalizeIdentityReview(wire: WireIdentityReviewResponse): IdentityReviewView {
  return {
    jobId: requireString(wire.job_id, "job_id"),
    snapshotId: requireString(wire.snapshot_id, "snapshot_id"),
    confirmationRequired: wire.confirmation_required === true,
    identity: normalizeIdentityDecision(wire.identity),
    phaseCandidates: wire.phase_candidates.map((item) =>
      normalizePhaseCandidate(item as Record<string, unknown>),
    ),
    metadataCandidates: wire.metadata_candidates,
    metadataConflicts: wire.metadata_conflicts.map((item) =>
      normalizeMetadataConflict(item as Record<string, unknown>),
    ),
  };
}

export function normalizeDraftRevision(wire: WireDraftRevisionResponse): DraftRevisionView {
  return {
    jobId: requireString(wire.job_id, "job_id"),
    revisionId: requireString(wire.revision_id, "revision_id"),
    draftId: requireString(wire.draft_id, "draft_id"),
    revisionNumber: requireNumber(wire.revision_number, "revision_number"),
    status: requireString(wire.status, "status"),
    statusLabel: requireString(wire.status_label, "status_label"),
    reason: requireString(wire.reason, "reason"),
    reasonLabel: requireString(wire.reason_label, "reason_label"),
    actor: requireString(wire.actor, "actor"),
    createdAt: requireString(wire.created_at, "created_at"),
    studyPhase: requireString(wire.study_phase, "study_phase"),
    studyPhaseLabel: requireString(wire.study_phase_label, "study_phase_label"),
    protocolCode: optionalString(wire.protocol_code),
    officialVersion: optionalString(wire.official_version),
    ruleCount: requireNumber(wire.rule_count, "rule_count"),
    workflowStageCount: requireNumber(wire.workflow_stage_count, "workflow_stage_count"),
    content: wire.content,
    diff: wire.diff,
  };
}

function normalizeIntegrityIssue(wire: WireIntegrityResponse["issues"][number]): IntegrityIssueView {
  return {
    issueCode: requireString(wire.issue_code, "issue_code"),
    checkName: requireString(wire.check_name, "check_name"),
    level: requireString(wire.level, "level"),
    problem: requireString(wire.problem, "problem"),
    impact: requireString(wire.impact, "impact"),
    nextAction: requireString(wire.next_action, "next_action"),
    affectedRefs: Array.isArray(wire.affected_refs) ? [...wire.affected_refs.map(String)] : [],
    repairScope: Array.isArray(wire.repair_scope) ? [...wire.repair_scope.map(String)] : [],
  };
}

function normalizeIntegrityCheck(
  wire: WireIntegrityResponse["checks"][number],
): IntegrityCheckView {
  return {
    checkName: requireString(wire.check_name, "check_name"),
    passed: wire.passed === true,
    issueCount: requireNumber(wire.issue_count, "issue_count"),
  };
}

export function normalizeIntegrity(wire: WireIntegrityResponse): IntegrityView {
  return {
    jobId: requireString(wire.job_id, "job_id"),
    publishable: wire.publishable === true,
    blockingCount: requireNumber(wire.blocking_count, "blocking_count"),
    reviewCount: requireNumber(wire.review_count, "review_count"),
    reminderCount: requireNumber(wire.reminder_count, "reminder_count"),
    summary: requireString(wire.summary, "summary"),
    checks: wire.checks.map(normalizeIntegrityCheck),
    issues: wire.issues.map(normalizeIntegrityIssue),
  };
}

export function normalizeSources(wire: WireSourcesResponse): SourcesView {
  return {
    jobId: requireString(wire.job_id, "job_id"),
    snapshotId: requireString(wire.snapshot_id, "snapshot_id"),
    selectedPhase: requireString(wire.selected_phase, "selected_phase"),
    selectedPhaseLabel: requireString(wire.selected_phase_label, "selected_phase_label"),
    sourceSpans: wire.source_spans,
    sourceMaterials: wire.source_materials,
  };
}

export function normalizePublishResult(wire: WirePublishResponse): PublishResultView {
  return {
    jobId: requireString(wire.job_id, "job_id"),
    projectId: requireString(wire.project_id, "project_id"),
    protocolVersionId: requireString(wire.protocol_version_id, "protocol_version_id"),
    ruleSetId: requireString(wire.rule_set_id, "rule_set_id"),
    ruleSetRevision: requireNumber(wire.rule_set_revision, "rule_set_revision"),
    replay: wire.replay === true,
  };
}

/** 确认身份请求：视图 camelCase → wire snake_case。 */
export function encodeConfirmIdentity(input: ConfirmIdentityInput): Record<string, unknown> {
  return {
    protocol_code: input.protocolCode,
    project_name: input.projectName,
    project_code: input.projectCode ?? null,
    official_version: input.officialVersion,
    official_date_value: input.officialDateValue,
    official_date_precision: input.officialDatePrecision,
    study_phase: input.studyPhase,
    selected_candidate_ids: input.selectedCandidateIds ?? [],
    actor: input.actor ?? "用户",
  };
}
