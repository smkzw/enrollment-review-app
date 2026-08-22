/**
 * 证据处理、页核对与被提及资料的原始 API 结构。
 * 这些类型只描述网络边界；组件消费 evidenceProcessingViewModels.ts 的领域投影。
 */

export type CorrectionChangeKindWire =
  | "polarity"
  | "numeric"
  | "decimal"
  | "unit"
  | "date"
  | "semantic_connector"
  | "other_text";

export type OcrRiskReviewDecisionWire =
  | "confirmed_as_read"
  | "corrected"
  | "not_applicable";

export type ProcessingCandidateStatusWire =
  | "staged"
  | "processing"
  | "needs_attention"
  | "retryable_failure"
  | "terminal_failure"
  | "ready"
  | "active"
  | "revision_conflict"
  | "cancelled";

export type ReferencedDocumentOriginWire =
  | "manual"
  | "deterministic_candidate";

export type ReferencedDocumentResolutionStatusWire = "unresolved" | "provided";

export interface ProcessingRevisionPageWire {
  entry_id: string;
  position: number;
  source_document_version_id: string;
  page_number: number;
  original_frame: string | null;
  page_artifact_id: string;
  ocr_page_id: string | null;
  status: string;
  status_label: string;
  failure_reason: string | null;
  image_available: boolean;
  page_width: number | null;
  page_height: number | null;
}

export interface GateResultWire {
  gate: string;
  gate_label: string;
  status: string;
  status_label: string;
  detail: string;
}

export interface ProcessingRevisionWire {
  evidence_processing_revision_id: string;
  revision_kind: string;
  revision_kind_label: string;
  evidence_snapshot_id: string;
  base_processing_revision_id: string | null;
  project_id: string;
  subject_id: string;
  review_episode_id: string;
  status: string;
  status_label: string;
  is_activatable: boolean;
  is_current: boolean;
  manifest_sha256: string;
  completion_manifest_sha256: string | null;
  pages: ProcessingRevisionPageWire[];
  risk_flag_count: number;
  pending_risk_flag_count: number;
  locator_ids: string[];
  risk_scan_ids: string[];
  risk_review_ids: string[];
  correction_ids: string[];
  metadata_revision_ids: string[];
  referenced_document_revision_ids: string[];
  resolution_revision_ids: string[];
  gates: GateResultWire[];
  created_at: string;
  created_by: string;
}

export interface OcrRiskFlagWire {
  risk_id: string;
  kind: string;
  kind_label: string;
  level: string;
  level_label: string;
  text: string;
  text_start: number;
  text_end: number;
  detail: string | null;
  rule_version: string;
}

export interface OcrRiskScanWire {
  scan_id: string;
  ocr_page_id: string;
  raw_text_sha256: string;
  scanner_rule_version: string;
  flags_sha256: string;
  coverage_status: string;
  created_at: string;
  flags: OcrRiskFlagWire[];
}

export interface OcrRiskReviewWire {
  review_id: string;
  risk_flag_id: string;
  decision: string;
  decision_label: string;
  reason: string;
  actor: string;
  base_processing_revision_id: string;
  expected_revision: number;
  created_at: string;
}

export interface CorrectionWire {
  correction_id: string;
  ocr_page_id: string;
  raw_text_sha256: string;
  text_start: number;
  text_end: number;
  original_text: string;
  corrected_text: string;
  change_kind: string;
  change_kind_label: string;
  requires_confirmation: boolean;
  confirmation_actor: string | null;
  confirmation_at: string | null;
  reason: string;
  actor: string;
  base_processing_revision_id: string;
  supersedes_correction_id: string | null;
  affected_scope: string[];
  created_at: string;
}

export interface LocatorWire {
  locator_id: string;
  page_artifact_id: string;
  ocr_page_id: string | null;
  source_document_version_id: string;
  page_number: number;
  source_layer: string;
  source_layer_label: string;
  source_text_sha256: string;
  target_id: string;
  precision: string;
  precision_label: string;
  degradation_reason: string | null;
  text_start: number | null;
  text_end: number | null;
  excerpt: string | null;
  disambiguation: string;
  locator_algorithm_version: string;
  authenticity: string;
  match_confidence: number | null;
  bbox: {
    x0: number;
    y0: number;
    x1: number;
    y1: number;
  } | null;
  coordinate_frame: {
    space: string;
    page_width: number;
    page_height: number;
    rotation: number;
    transform_version: string;
  } | null;
  coordinate_transform_version: string | null;
}

export interface OcrPageWire {
  ocr_page_id: string;
  page_artifact_id: string;
  source_document_version_id: string;
  page_number: number;
  source_sha256: string;
  raw_text: string;
  raw_text_sha256: string;
  status: string;
  status_label: string;
  processing_revision_id: string | null;
  is_current_revision: boolean;
  effective_text: string | null;
  effective_text_sha256: string | null;
  selected_corrections: CorrectionWire[];
  risk_scans: OcrRiskScanWire[];
  risk_reviews: OcrRiskReviewWire[];
  locators: LocatorWire[];
}

export interface CorrectionConfirmationWire {
  actor: string;
  at: string;
}

export interface CorrectionCreateRequestWire {
  raw_text_sha256: string;
  text_start: number;
  text_end: number;
  original_text: string;
  corrected_text: string;
  change_kind: CorrectionChangeKindWire;
  reason: string;
  base_processing_revision_id: string;
  expected_revision: number;
  idempotency_key: string;
  actor?: string | null;
  supersedes_correction_id?: string | null;
  confirmation?: CorrectionConfirmationWire | null;
  affected_scope?: string[];
  target_candidate_id?: string | null;
  expected_candidate_event_seq?: number | null;
}

export interface ProcessingCandidateResultWire {
  candidate_id: string;
  job_id: string;
  candidate_status: ProcessingCandidateStatusWire;
  candidate_status_label: string;
  candidate_event_seq: number;
  complete_revision_id: string | null;
}

export interface ProcessingCandidateStatusResponseWire extends ProcessingCandidateResultWire {}

export interface CorrectionCreateResponseWire extends ProcessingCandidateResultWire {
  correction: CorrectionWire;
  created: boolean;
}

export interface RiskReviewCreateRequestWire {
  risk_flag_id: string;
  decision: OcrRiskReviewDecisionWire;
  reason: string;
  base_processing_revision_id: string;
  expected_revision: number;
  idempotency_key: string;
  actor?: string | null;
  target_candidate_id?: string | null;
  expected_candidate_event_seq?: number | null;
}

export interface RiskReviewCreateResponseWire extends ProcessingCandidateResultWire {
  review: OcrRiskReviewWire;
  created: boolean;
}

export interface RiskPageReviewCreateRequestWire {
  scan_id: string;
  decision: "confirmed_as_read";
  reason: string;
  base_processing_revision_id: string;
  expected_revision: number;
  idempotency_key: string;
  actor?: string | null;
  target_candidate_id?: string | null;
  expected_candidate_event_seq?: number | null;
}

export interface OcrRiskPageReviewWire {
  page_review_id: string;
  ocr_page_id: string;
  scan_id: string;
  raw_text_sha256: string;
  scanner_rule_version: string;
  decision: "confirmed_as_read";
  decision_label: string;
  reason: string;
  actor: string;
  base_processing_revision_id: string;
  expected_revision: number;
  covered_flag_ids: string[];
  created_review_ids: string[];
  covered_flag_sha256: string;
  created_at: string;
}

export interface RiskPageReviewCreateResponseWire extends ProcessingCandidateResultWire {
  page_review: OcrRiskPageReviewWire;
  reviews: OcrRiskReviewWire[];
  created: boolean;
}

export interface BuildRevisionRequestWire {
  evidence_snapshot_id: string;
  base_processing_revision_id: string;
  expected_revision: number;
  idempotency_key: string;
  actor?: string | null;
  scanner_rule_version?: string | null;
  selected_locator_ids?: string[];
}

export interface BuildRevisionResponseWire extends ProcessingCandidateResultWire {
  created: boolean;
  revision: ProcessingRevisionWire | null;
}

export interface ActivateRevisionRequestWire {
  expected_revision: number;
  idempotency_key: string;
  actor?: string | null;
  reason: string;
  candidate_id?: string | null;
  job_id?: string | null;
}

export interface ActivationEventWire {
  event_id: string;
  review_episode_id: string;
  activation_seq: number;
  event_kind: string;
  event_kind_label: string;
  from_snapshot_id: string | null;
  from_revision_id: string | null;
  to_snapshot_id: string;
  to_revision_id: string;
  reason: string;
  actor: string;
  candidate_id: string | null;
  expected_revision: number;
  resulting_episode_revision: number;
  snapshot_status_transitioned: boolean;
  created_at: string;
}

export interface ReferencedDocumentResolutionWire {
  resolution_revision_id: string | null;
  status: string | null;
  status_label: string | null;
  source_document_version_id: string | null;
  revision: number | null;
  created_by: string | null;
  created_at: string | null;
}

export interface ReferencedDocumentWire {
  revision_id: string;
  referenced_document_id: string;
  project_id: string;
  subject_id: string;
  review_episode_id: string;
  description: string;
  document_type: string | null;
  source_party: string | null;
  origin: string;
  origin_label: string;
  pattern_version: string | null;
  status: string;
  status_label: string;
  user_reviewed: boolean;
  reason: string | null;
  revision: number;
  supersedes_revision_id: string | null;
  trigger_locator_id: string | null;
  resolution: ReferencedDocumentResolutionWire | null;
  created_at: string;
  created_by: string;
}

export interface ReferencedDocumentListWire {
  subject_id: string;
  review_episode_id: string;
  items: ReferencedDocumentWire[];
}

export interface ReferencedDocumentCreateRequestWire {
  review_episode_id: string;
  expected_revision: number;
  idempotency_key: string;
  description: string;
  document_type?: string | null;
  source_party?: string | null;
  origin?: ReferencedDocumentOriginWire;
  pattern_version?: string | null;
  trigger_locator_id?: string | null;
  actor?: string | null;
}

export interface ReferencedDocumentReviseRequestWire {
  expected_revision: number;
  idempotency_key: string;
  description: string;
  document_type?: string | null;
  source_party?: string | null;
  reason: string;
  actor?: string | null;
}

export interface ReferencedDocumentConfirmRequestWire {
  expected_revision: number;
  idempotency_key: string;
  trigger_locator_id: string;
  reason: string;
  actor?: string | null;
}

export interface ReferencedDocumentDismissRequestWire {
  expected_revision: number;
  idempotency_key: string;
  reason: string;
  actor?: string | null;
}

export interface ReferencedDocumentResolveRequestWire {
  expected_revision: number;
  idempotency_key: string;
  status?: ReferencedDocumentResolutionStatusWire;
  source_document_version_id?: string | null;
  actor?: string | null;
}
