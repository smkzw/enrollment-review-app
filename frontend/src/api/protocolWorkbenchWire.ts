/**
 * V2 方案解构 API 线格式（snake_case，与 protocol_schemas.py 对齐）。
 * 组件不得直接使用；经 normalize 转为 protocolWorkbenchTypes 视图。
 */

import type { DatePrecision, StudyPhase } from "../domain/enums";

export interface WireErrorEnvelope {
  error: {
    code: string;
    title: string;
    detail: string;
    recovery_action: string;
    correlation_id?: string;
    context?: unknown;
  };
}

export interface WireStartDeconstructionResponse {
  job_id: string;
  state: string;
  state_label: string;
  created: boolean;
  source_artifact_id: string;
  file_name: string;
}

export interface WireProtocolSessionResponse {
  job_id: string;
  job_type: string;
  state: string;
  state_label: string;
  progress_completed: number;
  progress_total: number;
  session_kind: string;
  awaiting_user: string | null;
  awaiting_user_label: string | null;
  source_artifact_id: string | null;
  file_name: string | null;
  snapshot_id: string | null;
  draft_id: string | null;
  draft_revision_id: string | null;
  draft_revision_number: number | null;
  draft_status: string | null;
  draft_status_label: string | null;
  selected_phase: StudyPhase | null;
  selected_phase_label: string | null;
  protocol_code: string | null;
  official_version: string | null;
  recovery_checkpoint_id: string | null;
  recovery_step_id: string | null;
  next_action: string;
  publishable: boolean | null;
}

export interface WireIdentityDecision {
  identity_decision_id: string;
  snapshot_id: string;
  status: string;
  status_label: string;
  project_name: string | null;
  project_code: string | null;
  protocol_code: string | null;
  official_version: string | null;
  official_date_value: string | null;
  official_date_precision: DatePrecision | null;
  study_phase: StudyPhase | null;
  study_phase_label: string | null;
  confirmation_required: boolean;
  conflict_ids: string[];
  selected_candidate_ids: string[];
}

export interface WirePhaseCandidate {
  candidate_id: string;
  phase: StudyPhase;
  phase_label: string;
  rationale: string;
  source_excerpt: string;
}

export interface WireMetadataCandidate {
  candidate_id: string;
  field: string;
  field_label: string;
  value: string;
  source_label: string;
  source_excerpt: string;
  is_fallback: boolean;
}

export interface WireMetadataConflict {
  conflict_id: string;
  field: string;
  field_label: string;
  reason: string;
  candidates: ReadonlyArray<{
    candidate_id: string;
    value: string;
    source_label: string;
  }>;
}

export interface WireIdentityReviewResponse {
  job_id: string;
  snapshot_id: string;
  confirmation_required: boolean;
  identity: WireIdentityDecision;
  phase_candidates: ReadonlyArray<WirePhaseCandidate>;
  metadata_candidates: ReadonlyArray<WireMetadataCandidate>;
  metadata_conflicts: ReadonlyArray<WireMetadataConflict>;
}

export interface WireDraftRevisionResponse {
  job_id: string;
  revision_id: string;
  draft_id: string;
  revision_number: number;
  status: string;
  status_label: string;
  reason: string;
  reason_label: string;
  actor: string;
  created_at: string;
  study_phase: StudyPhase;
  study_phase_label: string;
  protocol_code: string | null;
  official_version: string | null;
  rule_count: number;
  workflow_stage_count: number;
  content: Record<string, unknown>;
  diff: Record<string, unknown> | null;
}

export interface WireIntegrityIssue {
  issue_code: string;
  check_name: string;
  level: string;
  problem: string;
  impact: string;
  next_action: string;
  affected_refs: string[];
  repair_scope: string[];
}

export interface WireIntegrityCheck {
  check_name: string;
  passed: boolean;
  issue_count: number;
}

export interface WireIntegrityResponse {
  job_id: string;
  publishable: boolean;
  blocking_count: number;
  review_count: number;
  reminder_count: number;
  summary: string;
  checks: WireIntegrityCheck[];
  issues: WireIntegrityIssue[];
}

export interface WireSourcesResponse {
  job_id: string;
  snapshot_id: string;
  selected_phase: StudyPhase;
  selected_phase_label: string;
  source_spans: Record<string, unknown>;
  source_materials: Record<string, unknown>;
}

export interface WirePublishResponse {
  job_id: string;
  project_id: string;
  protocol_version_id: string;
  rule_set_id: string;
  rule_set_revision: number;
  replay: boolean;
}
