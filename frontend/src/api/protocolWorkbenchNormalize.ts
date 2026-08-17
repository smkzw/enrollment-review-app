/**
 * V2 方案解构 wire → 视图模型校验与归一化（单一解码层，组件不重复解析）。
 */

import { ProtocolWorkbenchApiError } from "./protocolWorkbenchTypes";
import type { DatePrecision, StudyPhase } from "../domain/enums";
import type {
  ConfirmIdentityInput,
  DraftComparisonSideView,
  DraftComparisonView,
  DraftRevisionView,
  FeedbackInput,
  IdentityDecisionView,
  IdentityReviewView,
  IntegrityCheckView,
  IntegrityIssueView,
  IntegrityView,
  MetadataCandidateView,
  MetadataConflictView,
  OfficialProjectView,
  PhaseCandidateView,
  ProjectOfficialVersionView,
  ProjectVersionView,
  ProtocolSessionView,
  PublishResultView,
  SourcesView,
  StartDeconstructionResult,
} from "./protocolWorkbenchTypes";
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

function requireArray<T>(value: unknown, field: string): T[] {
  if (!Array.isArray(value)) {
    throw new ProtocolWorkbenchApiError(
      "INVALID_RESPONSE",
      "服务响应异常",
      `方案解构服务返回的数据不完整（${field} 应为列表）。`,
      "请稍后重试；若问题持续出现，请联系维护人员。",
    );
  }
  return value as T[];
}

function requireRecord(value: unknown, field: string): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new ProtocolWorkbenchApiError(
      "INVALID_RESPONSE",
      "服务响应异常",
      `方案解构服务返回的数据不完整（${field} 应为对象）。`,
      "请稍后重试；若问题持续出现，请联系维护人员。",
    );
  }
  return value as Record<string, unknown>;
}

function requireStudyPhase(value: unknown, field: string): StudyPhase {
  const candidate = requireString(value, field);
  if (
    candidate !== "phase_ii" &&
    candidate !== "phase_iii" &&
    candidate !== "seamless_phase_ii_iii" &&
    candidate !== "other"
  ) {
    throw new ProtocolWorkbenchApiError(
      "INVALID_RESPONSE",
      "服务响应异常",
      `方案解构服务返回的数据不完整（${field} 不是有效研究期别）。`,
      "请稍后重试；若问题持续出现，请联系维护人员。",
    );
  }
  return candidate;
}

function optionalStudyPhase(value: unknown, field: string): StudyPhase | null {
  return value === null || value === undefined ? null : requireStudyPhase(value, field);
}

function optionalDatePrecision(value: unknown, field: string): DatePrecision | null {
  if (value === null || value === undefined) return null;
  const candidate = requireString(value, field);
  if (candidate !== "day" && candidate !== "month" && candidate !== "year" && candidate !== "unknown") {
    throw new ProtocolWorkbenchApiError(
      "INVALID_RESPONSE",
      "服务响应异常",
      `方案解构服务返回的数据不完整（${field} 不是有效日期精度）。`,
      "请稍后重试；若问题持续出现，请联系维护人员。",
    );
  }
  return candidate;
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
    const error = requireRecord(payload.error, "error");
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
  wire: unknown,
): StartDeconstructionResult {
  const row = requireRecord(wire, "start_deconstruction");
  return {
    jobId: requireString(row.job_id, "job_id"),
    state: requireString(row.state, "state"),
    stateLabel: requireString(row.state_label, "state_label"),
    created: row.created === true,
    sourceArtifactId: requireString(row.source_artifact_id, "source_artifact_id"),
    fileName: requireString(row.file_name, "file_name"),
  };
}

export function normalizeSession(wire: unknown): ProtocolSessionView {
  const row = requireRecord(wire, "session");
  return {
    jobId: requireString(row.job_id, "job_id"),
    jobType: requireString(row.job_type, "job_type"),
    state: requireString(row.state, "state"),
    stateLabel: requireString(row.state_label, "state_label"),
    progressCompleted: requireNumber(row.progress_completed, "progress_completed"),
    progressTotal: requireNumber(row.progress_total, "progress_total"),
    sessionKind: requireString(row.session_kind, "session_kind"),
    awaitingUser: optionalString(row.awaiting_user),
    awaitingUserLabel: optionalString(row.awaiting_user_label),
    sourceArtifactId: optionalString(row.source_artifact_id),
    fileName: optionalString(row.file_name),
    snapshotId: optionalString(row.snapshot_id),
    draftId: optionalString(row.draft_id),
    draftRevisionId: optionalString(row.draft_revision_id),
    draftRevisionNumber: optionalNumber(row.draft_revision_number),
    draftStatus: optionalString(row.draft_status),
    draftStatusLabel: optionalString(row.draft_status_label),
    selectedPhase: optionalStudyPhase(row.selected_phase, "selected_phase"),
    selectedPhaseLabel: optionalString(row.selected_phase_label),
    protocolCode: optionalString(row.protocol_code),
    officialVersion: optionalString(row.official_version),
    recoveryCheckpointId: optionalString(row.recovery_checkpoint_id),
    recoveryStepId: optionalString(row.recovery_step_id),
    nextAction: requireString(row.next_action, "next_action"),
    publishable: optionalBoolean(row.publishable),
    targetProjectId: optionalString(row.target_project_id),
    targetProjectName: optionalString(row.target_project_name),
    targetProjectCode: optionalString(row.target_project_code),
    targetProtocolCode: optionalString(row.target_protocol_code),
    targetStudyPhase: optionalStudyPhase(row.target_study_phase, "target_study_phase"),
    targetStudyPhaseLabel: optionalString(row.target_study_phase_label),
    targetOfficialVersion: optionalString(row.target_official_version),
    targetRuleSetRevision: optionalNumber(row.target_rule_set_revision),
  };
}

function normalizePhaseCandidate(
  raw: unknown,
): PhaseCandidateView {
  const row = requireRecord(raw, "phase_candidates[]");
  return {
    candidateId: requireString(row.candidate_id, "candidate_id"),
    phase: requireStudyPhase(row.phase, "phase"),
    phaseLabel: requireString(row.phase_label, "phase_label"),
    rationale: requireString(row.rationale, "rationale"),
    sourceExcerpt: requireString(row.source_excerpt, "source_excerpt"),
  };
}

function normalizeMetadataCandidate(
  raw: unknown,
): MetadataCandidateView {
  const row = requireRecord(raw, "metadata_candidates[]");
  return {
    candidateId: requireString(row.candidate_id, "candidate_id"),
    field: requireString(row.field, "field"),
    fieldLabel: requireString(row.field_label, "field_label"),
    value: requireString(row.value, "value"),
    sourceLabel: requireString(row.source_label, "source_label"),
    sourceExcerpt: requireString(row.source_excerpt, "source_excerpt"),
    isFallback: row.is_fallback === true,
  };
}

function normalizeMetadataConflict(
  raw: unknown,
): MetadataConflictView {
  const row = requireRecord(raw, "metadata_conflicts[]");
  const candidates = requireArray<unknown>(
    row.candidates,
    "metadata_conflicts[].candidates",
  ).map((item) => {
    const candidate = requireRecord(item, "metadata_conflicts[].candidates[]");
    return {
      candidateId: requireString(candidate.candidate_id, "candidate_id"),
      value: requireString(candidate.value, "value"),
      sourceLabel: requireString(candidate.source_label, "source_label"),
    };
  });
  return {
    conflictId: requireString(row.conflict_id, "conflict_id"),
    field: requireString(row.field, "field"),
    fieldLabel: requireString(row.field_label, "field_label"),
    reason: requireString(row.reason, "reason"),
    candidates,
  };
}

function normalizeIdentityDecision(wire: unknown): IdentityDecisionView {
  const row = requireRecord(wire, "identity");
  return {
    identityDecisionId: requireString(row.identity_decision_id, "identity_decision_id"),
    snapshotId: requireString(row.snapshot_id, "snapshot_id"),
    status: requireString(row.status, "status"),
    statusLabel: requireString(row.status_label, "status_label"),
    projectName: optionalString(row.project_name),
    projectCode: optionalString(row.project_code),
    protocolCode: optionalString(row.protocol_code),
    officialVersion: optionalString(row.official_version),
    officialDateValue: optionalString(row.official_date_value),
    officialDatePrecision: optionalDatePrecision(
      row.official_date_precision,
      "official_date_precision",
    ),
    studyPhase: optionalStudyPhase(row.study_phase, "study_phase"),
    studyPhaseLabel: optionalString(row.study_phase_label),
    confirmationRequired: row.confirmation_required === true,
    conflictIds: requireArray<unknown>(row.conflict_ids, "conflict_ids").map((value) =>
      requireString(value, "conflict_ids[]"),
    ),
    selectedCandidateIds: requireArray<unknown>(
      row.selected_candidate_ids,
      "selected_candidate_ids",
    ).map((value) => requireString(value, "selected_candidate_ids[]")),
  };
}

export function normalizeIdentityReview(wire: unknown): IdentityReviewView {
  const row = requireRecord(wire, "identity_review");
  return {
    jobId: requireString(row.job_id, "job_id"),
    snapshotId: requireString(row.snapshot_id, "snapshot_id"),
    confirmationRequired: row.confirmation_required === true,
    identity: normalizeIdentityDecision(row.identity),
    phaseCandidates: requireArray<unknown>(
      row.phase_candidates,
      "phase_candidates",
    ).map(normalizePhaseCandidate),
    metadataCandidates: requireArray<unknown>(
      row.metadata_candidates,
      "metadata_candidates",
    ).map(normalizeMetadataCandidate),
    metadataConflicts: requireArray<unknown>(
      row.metadata_conflicts,
      "metadata_conflicts",
    ).map(normalizeMetadataConflict),
  };
}

export function normalizeDraftRevision(wire: unknown): DraftRevisionView {
  const row = requireRecord(wire, "draft");
  return {
    jobId: requireString(row.job_id, "job_id"),
    revisionId: requireString(row.revision_id, "revision_id"),
    draftId: requireString(row.draft_id, "draft_id"),
    revisionNumber: requireNumber(row.revision_number, "revision_number"),
    status: requireString(row.status, "status"),
    statusLabel: requireString(row.status_label, "status_label"),
    reason: requireString(row.reason, "reason"),
    reasonLabel: requireString(row.reason_label, "reason_label"),
    actor: requireString(row.actor, "actor"),
    createdAt: requireString(row.created_at, "created_at"),
    studyPhase: requireStudyPhase(row.study_phase, "study_phase"),
    studyPhaseLabel: requireString(row.study_phase_label, "study_phase_label"),
    protocolCode: optionalString(row.protocol_code),
    officialVersion: optionalString(row.official_version),
    ruleCount: requireNumber(row.rule_count, "rule_count"),
    workflowStageCount: requireNumber(row.workflow_stage_count, "workflow_stage_count"),
    content: requireRecord(row.content, "content"),
    diff:
      row.diff === null || row.diff === undefined
        ? null
        : requireRecord(row.diff, "diff"),
  };
}

function normalizeIntegrityIssue(wire: unknown): IntegrityIssueView {
  const row = requireRecord(wire, "issues[]");
  return {
    issueCode: requireString(row.issue_code, "issue_code"),
    checkName: requireString(row.check_name, "check_name"),
    level: requireString(row.level, "level"),
    problem: requireString(row.problem, "problem"),
    impact: requireString(row.impact, "impact"),
    nextAction: requireString(row.next_action, "next_action"),
    affectedRefs: requireArray<unknown>(row.affected_refs, "affected_refs").map((value) =>
      requireString(value, "affected_refs[]"),
    ),
    repairScope: requireArray<unknown>(row.repair_scope, "repair_scope").map((value) =>
      requireString(value, "repair_scope[]"),
    ),
  };
}

function normalizeIntegrityCheck(wire: unknown): IntegrityCheckView {
  const row = requireRecord(wire, "checks[]");
  return {
    checkName: requireString(row.check_name, "check_name"),
    passed: row.passed === true,
    issueCount: requireNumber(row.issue_count, "issue_count"),
  };
}

export function normalizeIntegrity(wire: unknown): IntegrityView {
  const row = requireRecord(wire, "integrity");
  return {
    jobId: requireString(row.job_id, "job_id"),
    publishable: row.publishable === true,
    blockingCount: requireNumber(row.blocking_count, "blocking_count"),
    reviewCount: requireNumber(row.review_count, "review_count"),
    reminderCount: requireNumber(row.reminder_count, "reminder_count"),
    summary: requireString(row.summary, "summary"),
    checks: requireArray<unknown>(row.checks, "checks").map(normalizeIntegrityCheck),
    issues: requireArray<unknown>(row.issues, "issues").map(normalizeIntegrityIssue),
  };
}

export function normalizeSources(wire: unknown): SourcesView {
  const row = requireRecord(wire, "sources");
  return {
    jobId: requireString(row.job_id, "job_id"),
    snapshotId: requireString(row.snapshot_id, "snapshot_id"),
    selectedPhase: requireStudyPhase(row.selected_phase, "selected_phase"),
    selectedPhaseLabel: requireString(row.selected_phase_label, "selected_phase_label"),
    sourceSpans: requireRecord(row.source_spans, "source_spans"),
    sourceMaterials: requireRecord(row.source_materials, "source_materials"),
  };
}

export function normalizePublishResult(wire: unknown): PublishResultView {
  const row = requireRecord(wire, "publish");
  return {
    jobId: requireString(row.job_id, "job_id"),
    projectId: requireString(row.project_id, "project_id"),
    protocolVersionId: requireString(row.protocol_version_id, "protocol_version_id"),
    ruleSetId: requireString(row.rule_set_id, "rule_set_id"),
    ruleSetRevision: requireNumber(row.rule_set_revision, "rule_set_revision"),
    replay: row.replay === true,
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

function normalizeOfficialProject(raw: unknown): OfficialProjectView {
  const row = requireRecord(raw, "projects[]");
  return {
    projectId: requireString(row.project_id, "project_id"),
    projectCode: requireString(row.project_code, "project_code"),
    projectName: requireString(row.project_name, "project_name"),
    studyPhase: requireStudyPhase(row.study_phase, "study_phase"),
    studyPhaseLabel: requireString(row.study_phase_label, "study_phase_label"),
    protocolCode: requireString(row.protocol_code, "protocol_code"),
    officialVersion: requireString(row.official_version, "official_version"),
    officialDateValue: optionalString(row.official_date_value),
    officialDatePrecision: optionalDatePrecision(
      row.official_date_precision,
      "official_date_precision",
    ),
    ruleSetId: requireString(row.rule_set_id, "rule_set_id"),
    ruleSetRevision: requireNumber(row.rule_set_revision, "rule_set_revision"),
  };
}

export function normalizeOfficialProjectList(wire: unknown): OfficialProjectView[] {
  const row = requireRecord(wire, "official_project_list");
  return requireArray<unknown>(row.projects, "projects").map(normalizeOfficialProject);
}

export function normalizeProjectOfficialVersion(
  wire: unknown,
): ProjectOfficialVersionView {
  const row = requireRecord(wire, "project_official_version");
  const versions = requireArray<unknown>(row.versions, "versions").map((item) => {
    const version = requireRecord(item, "versions[]");
    return {
      ruleSetRevision: requireNumber(version.rule_set_revision, "rule_set_revision"),
      protocolVersionId: requireString(
        version.protocol_version_id,
        "protocol_version_id",
      ),
      officialVersion: requireString(version.official_version, "official_version"),
      officialDateValue: optionalString(version.official_date_value),
      officialDatePrecision: optionalDatePrecision(
        version.official_date_precision,
        "official_date_precision",
      ),
      sha256: requireString(version.sha256, "sha256"),
      ruleCount: requireNumber(version.rule_count, "rule_count"),
      publishedAt: requireString(version.published_at, "published_at"),
    } as ProjectVersionView;
  });
  return {
    project: normalizeOfficialProject(row.project),
    versions,
    publicationCount: requireNumber(row.publication_count, "publication_count"),
  };
}

function normalizeDraftComparisonSide(raw: unknown): DraftComparisonSideView {
  const row = requireRecord(raw, "draft_comparison_side");
  return {
    revisionId: requireString(row.revision_id, "revision_id"),
    draftId: requireString(row.draft_id, "draft_id"),
    protocolVersionId: requireString(
      row.protocol_version_id,
      "protocol_version_id",
    ),
    officialVersion: optionalString(row.official_version),
    revisionNumber: optionalNumber(row.revision_number),
    status: optionalString(row.status),
    ruleCount: requireNumber(row.rule_count, "rule_count"),
    workflowStageCount: requireNumber(row.workflow_stage_count, "workflow_stage_count"),
    isFormalBaseline: row.is_formal_baseline === true,
    content: requireRecord(row.content, "content"),
    sourceRefs: requireArray<unknown>(row.source_refs, "source_refs").map((value) =>
      requireString(value, "source_refs[]"),
    ),
  };
}

export function normalizeDraftComparison(wire: unknown): DraftComparisonView {
  const row = requireRecord(wire, "draft_comparison");
  return {
    jobId: requireString(row.job_id, "job_id"),
    baseline: normalizeDraftComparisonSide(row.baseline),
    candidate: normalizeDraftComparisonSide(row.candidate),
    diff: requireRecord(row.diff, "diff"),
    sourceBound: row.source_bound === true,
  };
}

/** 反馈修订请求：视图 → wire snake_case（原文理解纠错 / 补充解释）。 */
export function encodeFeedback(input: FeedbackInput): Record<string, unknown> {
  return {
    expected_revision_id: input.expectedRevisionId,
    draft: input.draft,
    feedback_kind: input.feedbackKind,
    feedback_note: input.feedbackNote,
    actor: input.actor ?? "用户",
  };
}
