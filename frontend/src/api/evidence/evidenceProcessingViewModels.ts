/**
 * 证据处理页、校对风险与被提及资料的运行时解码。
 * 页 ID 只从 ProcessingRevisionDTO.pages 进入领域模型；本模块不生成或猜测页 ID。
 */

import {
  EvidenceDecodeError,
  type EvidenceConflictContext,
  type EvidenceJsonValue,
} from "./evidenceViewModels";
import type {
  CorrectionChangeKindWire,
  ProcessingCandidateStatusWire,
} from "./evidenceProcessingTypes";

export type ProcessingRevisionKind = "base" | "complete";
export type ProcessingRevisionStatus =
  | "staged"
  | "processing"
  | "needs_attention"
  | "retryable_failure"
  | "terminal_failure"
  | "ready"
  | "active"
  | "revision_conflict"
  | "cancelled";
export type ProcessingCandidateStatus = ProcessingCandidateStatusWire;
export type ProcessingPageStatus = "succeeded" | "degraded" | "failed";
export type OcrPageStatus =
  "pending" | "processing" | "succeeded" | "failed" | "cancelled";
export type OcrRiskKind =
  | "negation_polarity"
  | "numeric_value"
  | "decimal_point"
  | "unit"
  | "date"
  | "repeated_text"
  | "output_repetition"
  | "low_confidence";
export type OcrRiskLevel = "blocking" | "informational";
export type OcrRiskReviewDecision =
  "confirmed_as_read" | "corrected" | "not_applicable";
export type CorrectionChangeKind = CorrectionChangeKindWire;
export type LocatorPrecision =
  "bbox" | "text_range" | "page_excerpt" | "page_only";
export type LocatorSourceLayer = "native_text" | "raw_ocr" | "effective_text";
export type LocatorAuthenticity = "authenticated" | "degraded" | "rejected";
export type DisambiguationOutcome =
  "unique_match" | "repeated_text_degraded" | "not_found";
export type ReferencedDocumentOrigin = "manual" | "deterministic_candidate";
export type ReferencedDocumentStatus = "proposed" | "confirmed" | "dismissed";
export type ReferencedDocumentResolutionStatus = "unresolved" | "provided";

export interface ProcessingRevisionPageView {
  entryId: string;
  position: number;
  sourceDocumentVersionId: string;
  pageNumber: number;
  originalFrame: string | null;
  pageArtifactId: string;
  ocrPageId: string | null;
  status: ProcessingPageStatus;
  statusLabel: string;
  failureReason: string | null;
  canOpen: boolean;
  imageAvailable: boolean;
  pageWidth: number | null;
  pageHeight: number | null;
}

export interface GateResultView {
  gate: string;
  gateLabel: string;
  status: string;
  statusLabel: string;
  detail: string;
}

export interface ProcessingRevisionView {
  revisionId: string;
  revisionKind: ProcessingRevisionKind;
  revisionKindLabel: string;
  evidenceSnapshotId: string;
  baseProcessingRevisionId: string | null;
  projectId: string;
  subjectId: string;
  reviewEpisodeId: string;
  status: ProcessingRevisionStatus;
  statusLabel: string;
  isActivatable: boolean;
  isCurrent: boolean;
  manifestSha256: string;
  completionManifestSha256: string | null;
  pages: ProcessingRevisionPageView[];
  riskFlagCount: number;
  pendingRiskFlagCount: number;
  locatorIds: string[];
  riskScanIds: string[];
  riskReviewIds: string[];
  correctionIds: string[];
  metadataRevisionIds: string[];
  referencedDocumentRevisionIds: string[];
  resolutionRevisionIds: string[];
  gates: GateResultView[];
  createdAt: string;
  createdBy: string;
}

export interface OcrRiskFlagView {
  riskId: string;
  riskFlagId: string;
  kind: OcrRiskKind;
  kindLabel: string;
  level: OcrRiskLevel;
  levelLabel: string;
  text: string;
  textStart: number;
  textEnd: number;
  detail: string | null;
  ruleVersion: string;
}

export interface OcrRiskScanView {
  scanId: string;
  ocrPageId: string;
  rawTextSha256: string;
  scannerRuleVersion: string;
  flagsSha256: string;
  coverageStatus: string;
  createdAt: string;
  flags: OcrRiskFlagView[];
}

export interface OcrRiskReviewView {
  reviewId: string;
  riskFlagId: string;
  decision: OcrRiskReviewDecision;
  decisionLabel: string;
  reason: string;
  actor: string;
  baseProcessingRevisionId: string;
  expectedRevision: number;
  createdAt: string;
}

export interface CorrectionView {
  correctionId: string;
  ocrPageId: string;
  rawTextSha256: string;
  textStart: number;
  textEnd: number;
  originalText: string;
  correctedText: string;
  changeKind: CorrectionChangeKind;
  changeKindLabel: string;
  requiresConfirmation: boolean;
  confirmationActor: string | null;
  confirmationAt: string | null;
  reason: string;
  actor: string;
  baseProcessingRevisionId: string;
  supersedesCorrectionId: string | null;
  affectedScope: string[];
  createdAt: string;
}

export interface LocatorView {
  locatorId: string;
  pageArtifactId: string;
  ocrPageId: string | null;
  sourceDocumentVersionId: string;
  pageNumber: number;
  sourceLayer: LocatorSourceLayer;
  sourceLayerLabel: string;
  sourceTextSha256: string;
  targetId: string;
  precision: LocatorPrecision;
  precisionLabel: string;
  degradationReason: string | null;
  textStart: number | null;
  textEnd: number | null;
  excerpt: string | null;
  disambiguation: DisambiguationOutcome;
  locatorAlgorithmVersion: string;
  authenticity: LocatorAuthenticity;
  matchConfidence: number | null;
  bbox: BoundingBoxView | null;
  coordinateFrame: CoordinateFrameView | null;
  coordinateTransformVersion: string | null;
}

export function clinicalLocatorPrecisionLabel(
  precision: LocatorPrecision,
): string {
  switch (precision) {
    case "bbox":
      return "原文位置";
    case "text_range":
      return "识别文字";
    case "page_excerpt":
      return "页内文字";
    case "page_only":
      return "所在页面";
  }
}

export function isReviewableLocator(locator: LocatorView): boolean {
  const excerpt = locator.excerpt?.trim();
  return (
    excerpt === null || excerpt === undefined || /[\p{L}\p{N}]/u.test(excerpt)
  );
}

export interface BoundingBoxView {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

export interface CoordinateFrameView {
  space: string;
  pageWidth: number;
  pageHeight: number;
  rotation: number;
  transformVersion: string;
}

export interface OcrPageView {
  ocrPageId: string;
  pageArtifactId: string;
  sourceDocumentVersionId: string;
  pageNumber: number;
  sourceSha256: string;
  rawText: string;
  rawTextSha256: string;
  status: OcrPageStatus;
  statusLabel: string;
  processingRevisionId: string | null;
  isCurrentRevision: boolean;
  effectiveText: string | null;
  effectiveTextSha256: string | null;
  selectedCorrections: CorrectionView[];
  riskScans: OcrRiskScanView[];
  riskReviews: OcrRiskReviewView[];
  locators: LocatorView[];
}

export interface ReferencedDocumentResolutionView {
  resolutionRevisionId: string | null;
  status: ReferencedDocumentResolutionStatus | null;
  statusLabel: string | null;
  sourceDocumentVersionId: string | null;
  revision: number | null;
  createdBy: string | null;
  createdAt: string | null;
}

export interface ReferencedDocumentView {
  revisionId: string;
  referencedDocumentId: string;
  projectId: string;
  subjectId: string;
  reviewEpisodeId: string;
  description: string;
  documentType: string | null;
  sourceParty: string | null;
  origin: ReferencedDocumentOrigin;
  originLabel: string;
  patternVersion: string | null;
  status: ReferencedDocumentStatus;
  statusLabel: string;
  userReviewed: boolean;
  reason: string | null;
  revision: number;
  supersedesRevisionId: string | null;
  triggerLocatorId: string | null;
  resolution: ReferencedDocumentResolutionView | null;
  createdAt: string;
  createdBy: string;
}

export interface ReferencedDocumentListView {
  subjectId: string;
  reviewEpisodeId: string;
  items: ReferencedDocumentView[];
}

export interface ProcessingCandidateView {
  candidateId: string;
  jobId: string | null;
  candidateStatus: ProcessingCandidateStatus;
  candidateStatusLabel: string;
  candidateEventSeq: number | null;
  completeRevisionId: string | null;
}

export interface CorrectionCreateResponseView extends ProcessingCandidateView {
  correction: CorrectionView;
  created: boolean;
}

export interface RiskReviewCreateResponseView extends ProcessingCandidateView {
  review: OcrRiskReviewView;
  created: boolean;
}

export interface RiskPageReviewCreateResponseView extends ProcessingCandidateView {
  pageReviewId: string;
  coveredFlagIds: string[];
  reviews: OcrRiskReviewView[];
  created: boolean;
}

export interface BuildRevisionResponseView extends ProcessingCandidateView {
  created: boolean;
  revision: ProcessingRevisionView | null;
}

export interface ActivationEventView {
  eventId: string;
  reviewEpisodeId: string;
  activationSeq: number;
  eventKindLabel: string;
  fromSnapshotId: string | null;
  fromRevisionId: string | null;
  toSnapshotId: string;
  toRevisionId: string;
  reason: string;
  actor: string;
  candidateId: string | null;
  expectedRevision: number;
  resultingEpisodeRevision: number;
  snapshotStatusTransitioned: boolean;
  createdAt: string;
}

const PAGE_STATUS_LABELS: Record<ProcessingPageStatus, string> = {
  succeeded: "原件可查看",
  degraded: "页面可查看，部分内容需核对",
  failed: "页面处理失败",
};
const OCR_STATUS_LABELS: Record<OcrPageStatus, string> = {
  pending: "等待识别",
  processing: "识别中",
  succeeded: "已识别",
  failed: "识别失败",
  cancelled: "已取消",
};
const REVISION_STATUS_LABELS: Record<ProcessingRevisionStatus, string> = {
  staged: "待处理",
  processing: "处理中",
  needs_attention: "需要关注",
  retryable_failure: "失败（可重试）",
  terminal_failure: "处理失败",
  ready: "待发布",
  active: "当前有效",
  revision_conflict: "修订冲突",
  cancelled: "已取消",
};
const CANDIDATE_STATUS_LABELS: Record<ProcessingCandidateStatus, string> = {
  staged: "待处理",
  processing: "处理中",
  needs_attention: "需要关注",
  retryable_failure: "失败（可重试）",
  terminal_failure: "处理失败",
  ready: "待发布",
  active: "当前有效",
  revision_conflict: "修订冲突",
  cancelled: "已取消",
};
const REFERENCED_STATUS_LABELS: Record<ReferencedDocumentStatus, string> = {
  proposed: "待确认",
  confirmed: "已确认",
  dismissed: "已解除",
};
const RESOLUTION_STATUS_LABELS: Record<
  ReferencedDocumentResolutionStatus,
  string
> = {
  unresolved: "未提供",
  provided: "已提供",
};

function record(value: unknown, field: string): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new EvidenceDecodeError(`响应字段 ${field} 应为对象`);
  }
  return value as Record<string, unknown>;
}
function field(
  row: Record<string, unknown>,
  key: string,
  path: string,
): unknown {
  if (!(key in row)) throw new EvidenceDecodeError(`响应缺少字段 ${path}`);
  return row[key];
}
function stringValue(value: unknown, path: string): string {
  if (typeof value !== "string")
    throw new EvidenceDecodeError(`响应字段 ${path} 应为字符串`);
  return value;
}
function nullableString(value: unknown, path: string): string | null {
  if (value === null) return null;
  return stringValue(value, path);
}
function numberValue(value: unknown, path: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new EvidenceDecodeError(`响应字段 ${path} 应为数值`);
  }
  return value;
}
function nullableNumber(value: unknown, path: string): number | null {
  if (value === null) return null;
  return numberValue(value, path);
}
function booleanValue(value: unknown, path: string): boolean {
  if (typeof value !== "boolean")
    throw new EvidenceDecodeError(`响应字段 ${path} 应为布尔值`);
  return value;
}
function arrayValue(value: unknown, path: string): unknown[] {
  if (!Array.isArray(value))
    throw new EvidenceDecodeError(`响应字段 ${path} 应为数组`);
  return value;
}
function nonEmptyLabel(value: unknown, path: string, fallback: string): string {
  const result = stringValue(value, path);
  return result.length > 0 ? result : fallback;
}
function enumValue<T extends string>(
  value: unknown,
  values: readonly T[],
  path: string,
  label: string,
): T {
  const result = stringValue(value, path);
  if (!values.includes(result as T)) {
    throw new EvidenceDecodeError(`未知的${label} ${result}`);
  }
  return result as T;
}
function requiredStringArray(value: unknown, path: string): string[] {
  return arrayValue(value, path).map((item, index) =>
    stringValue(item, `${path}[${index}]`),
  );
}
function requiredString(value: unknown, path: string): string {
  return stringValue(value, path);
}
function requiredNullableString(
  row: Record<string, unknown>,
  key: string,
  path: string,
): string | null {
  return nullableString(field(row, key, path), path);
}

function decodeGate(value: unknown, index: number): GateResultView {
  const row = record(value, `revision.gates[${index}]`);
  return {
    gate: requiredString(
      field(row, "gate", `revision.gates[${index}].gate`),
      `revision.gates[${index}].gate`,
    ),
    gateLabel: nonEmptyLabel(
      field(row, "gate_label", `revision.gates[${index}].gate_label`),
      `revision.gates[${index}].gate_label`,
      "处理条件",
    ),
    status: requiredString(
      field(row, "status", `revision.gates[${index}].status`),
      `revision.gates[${index}].status`,
    ),
    statusLabel: nonEmptyLabel(
      field(row, "status_label", `revision.gates[${index}].status_label`),
      `revision.gates[${index}].status_label`,
      "待核对",
    ),
    detail: requiredString(
      field(row, "detail", `revision.gates[${index}].detail`),
      `revision.gates[${index}].detail`,
    ),
  };
}

export function decodeProcessingRevision(
  wire: unknown,
): ProcessingRevisionView {
  const row = record(wire, "processing_revision");
  const revisionKind = enumValue(
    field(row, "revision_kind", "revision.revision_kind"),
    ["base", "complete"],
    "revision.revision_kind",
    "处理修订类型",
  );
  const status = enumValue(
    field(row, "status", "revision.status"),
    Object.keys(REVISION_STATUS_LABELS) as ProcessingRevisionStatus[],
    "revision.status",
    "处理修订状态",
  );
  const pages = arrayValue(
    field(row, "pages", "revision.pages"),
    "revision.pages",
  ).map((item, index) => decodeProcessingRevisionPage(item, index));
  const positions = new Set(pages.map((page) => page.position));
  if (positions.size !== pages.length) {
    throw new EvidenceDecodeError("处理修订页清单存在重复页序");
  }
  const gates = arrayValue(
    field(row, "gates", "revision.gates"),
    "revision.gates",
  ).map(decodeGate);
  return {
    revisionId: requiredString(
      field(
        row,
        "evidence_processing_revision_id",
        "revision.evidence_processing_revision_id",
      ),
      "revision.evidence_processing_revision_id",
    ),
    revisionKind,
    revisionKindLabel: nonEmptyLabel(
      field(row, "revision_kind_label", "revision.revision_kind_label"),
      "revision.revision_kind_label",
      revisionKind === "complete" ? "完整处理修订" : "基础处理修订",
    ),
    evidenceSnapshotId: requiredString(
      field(row, "evidence_snapshot_id", "revision.evidence_snapshot_id"),
      "revision.evidence_snapshot_id",
    ),
    baseProcessingRevisionId: requiredNullableString(
      row,
      "base_processing_revision_id",
      "revision.base_processing_revision_id",
    ),
    projectId: requiredString(
      field(row, "project_id", "revision.project_id"),
      "revision.project_id",
    ),
    subjectId: requiredString(
      field(row, "subject_id", "revision.subject_id"),
      "revision.subject_id",
    ),
    reviewEpisodeId: requiredString(
      field(row, "review_episode_id", "revision.review_episode_id"),
      "revision.review_episode_id",
    ),
    status,
    statusLabel: nonEmptyLabel(
      field(row, "status_label", "revision.status_label"),
      "revision.status_label",
      REVISION_STATUS_LABELS[status],
    ),
    isActivatable: booleanValue(
      field(row, "is_activatable", "revision.is_activatable"),
      "revision.is_activatable",
    ),
    isCurrent: booleanValue(
      field(row, "is_current", "revision.is_current"),
      "revision.is_current",
    ),
    manifestSha256: requiredString(
      field(row, "manifest_sha256", "revision.manifest_sha256"),
      "revision.manifest_sha256",
    ),
    completionManifestSha256: requiredNullableString(
      row,
      "completion_manifest_sha256",
      "revision.completion_manifest_sha256",
    ),
    pages,
    riskFlagCount: numberValue(
      field(row, "risk_flag_count", "revision.risk_flag_count"),
      "revision.risk_flag_count",
    ),
    pendingRiskFlagCount: numberValue(
      field(
        row,
        "pending_risk_flag_count",
        "revision.pending_risk_flag_count",
      ),
      "revision.pending_risk_flag_count",
    ),
    locatorIds: requiredStringArray(
      field(row, "locator_ids", "revision.locator_ids"),
      "revision.locator_ids",
    ),
    riskScanIds: requiredStringArray(
      field(row, "risk_scan_ids", "revision.risk_scan_ids"),
      "revision.risk_scan_ids",
    ),
    riskReviewIds: requiredStringArray(
      field(row, "risk_review_ids", "revision.risk_review_ids"),
      "revision.risk_review_ids",
    ),
    correctionIds: requiredStringArray(
      field(row, "correction_ids", "revision.correction_ids"),
      "revision.correction_ids",
    ),
    metadataRevisionIds: requiredStringArray(
      field(row, "metadata_revision_ids", "revision.metadata_revision_ids"),
      "revision.metadata_revision_ids",
    ),
    referencedDocumentRevisionIds: requiredStringArray(
      field(
        row,
        "referenced_document_revision_ids",
        "revision.referenced_document_revision_ids",
      ),
      "revision.referenced_document_revision_ids",
    ),
    resolutionRevisionIds: requiredStringArray(
      field(row, "resolution_revision_ids", "revision.resolution_revision_ids"),
      "revision.resolution_revision_ids",
    ),
    gates,
    createdAt: requiredString(
      field(row, "created_at", "revision.created_at"),
      "revision.created_at",
    ),
    createdBy: requiredString(
      field(row, "created_by", "revision.created_by"),
      "revision.created_by",
    ),
  };
}

export function decodeActivationEvent(wire: unknown): ActivationEventView {
  const row = record(wire, "activation_event");
  return {
    eventId: requiredString(
      field(row, "event_id", "activation_event.event_id"),
      "activation_event.event_id",
    ),
    reviewEpisodeId: requiredString(
      field(row, "review_episode_id", "activation_event.review_episode_id"),
      "activation_event.review_episode_id",
    ),
    activationSeq: numberValue(
      field(row, "activation_seq", "activation_event.activation_seq"),
      "activation_event.activation_seq",
    ),
    eventKindLabel: nonEmptyLabel(
      field(row, "event_kind_label", "activation_event.event_kind_label"),
      "activation_event.event_kind_label",
      "启用资料版本",
    ),
    fromSnapshotId: requiredNullableString(
      row,
      "from_snapshot_id",
      "activation_event.from_snapshot_id",
    ),
    fromRevisionId: requiredNullableString(
      row,
      "from_revision_id",
      "activation_event.from_revision_id",
    ),
    toSnapshotId: requiredString(
      field(row, "to_snapshot_id", "activation_event.to_snapshot_id"),
      "activation_event.to_snapshot_id",
    ),
    toRevisionId: requiredString(
      field(row, "to_revision_id", "activation_event.to_revision_id"),
      "activation_event.to_revision_id",
    ),
    reason: requiredString(
      field(row, "reason", "activation_event.reason"),
      "activation_event.reason",
    ),
    actor: requiredString(
      field(row, "actor", "activation_event.actor"),
      "activation_event.actor",
    ),
    candidateId: requiredNullableString(
      row,
      "candidate_id",
      "activation_event.candidate_id",
    ),
    expectedRevision: numberValue(
      field(row, "expected_revision", "activation_event.expected_revision"),
      "activation_event.expected_revision",
    ),
    resultingEpisodeRevision: numberValue(
      field(
        row,
        "resulting_episode_revision",
        "activation_event.resulting_episode_revision",
      ),
      "activation_event.resulting_episode_revision",
    ),
    snapshotStatusTransitioned: booleanValue(
      field(
        row,
        "snapshot_status_transitioned",
        "activation_event.snapshot_status_transitioned",
      ),
      "activation_event.snapshot_status_transitioned",
    ),
    createdAt: requiredString(
      field(row, "created_at", "activation_event.created_at"),
      "activation_event.created_at",
    ),
  };
}

function decodeProcessingRevisionPage(
  value: unknown,
  index: number,
): ProcessingRevisionPageView {
  const row = record(value, `revision.pages[${index}]`);
  const path = `revision.pages[${index}]`;
  const status = enumValue(
    field(row, "status", `${path}.status`),
    ["succeeded", "degraded", "failed"],
    `${path}.status`,
    "页处理状态",
  );
  const ocrPageId = requiredNullableString(
    row,
    "ocr_page_id",
    `${path}.ocr_page_id`,
  );
  const failureReason = requiredNullableString(
    row,
    "failure_reason",
    `${path}.failure_reason`,
  );
  const imageAvailable = booleanValue(
    field(row, "image_available", `${path}.image_available`),
    `${path}.image_available`,
  );
  const pageWidth = nullableNumber(
    field(row, "page_width", `${path}.page_width`),
    `${path}.page_width`,
  );
  const pageHeight = nullableNumber(
    field(row, "page_height", `${path}.page_height`),
    `${path}.page_height`,
  );
  if (status === "failed" && ocrPageId !== null) {
    throw new EvidenceDecodeError("失败页不得携带可打开的识别页编号");
  }
  if (
    (status === "failed" || status === "degraded") &&
    (failureReason === null || failureReason.trim() === "")
  ) {
    throw new EvidenceDecodeError("失败或降级页必须说明处理原因");
  }
  if (imageAvailable !== (pageWidth !== null && pageHeight !== null)) {
    throw new EvidenceDecodeError("原始页图状态与页尺寸不一致");
  }
  if (
    (pageWidth !== null && pageWidth <= 0) ||
    (pageHeight !== null && pageHeight <= 0)
  ) {
    throw new EvidenceDecodeError("原始资料页尺寸必须为正数");
  }
  return {
    entryId: requiredString(
      field(row, "entry_id", `${path}.entry_id`),
      `${path}.entry_id`,
    ),
    position: numberValue(
      field(row, "position", `${path}.position`),
      `${path}.position`,
    ),
    sourceDocumentVersionId: requiredString(
      field(
        row,
        "source_document_version_id",
        `${path}.source_document_version_id`,
      ),
      `${path}.source_document_version_id`,
    ),
    pageNumber: numberValue(
      field(row, "page_number", `${path}.page_number`),
      `${path}.page_number`,
    ),
    originalFrame: requiredNullableString(
      row,
      "original_frame",
      `${path}.original_frame`,
    ),
    pageArtifactId: requiredString(
      field(row, "page_artifact_id", `${path}.page_artifact_id`),
      `${path}.page_artifact_id`,
    ),
    ocrPageId,
    status,
    statusLabel: nonEmptyLabel(
      field(row, "status_label", `${path}.status_label`),
      `${path}.status_label`,
      PAGE_STATUS_LABELS[status],
    ),
    failureReason,
    canOpen: ocrPageId !== null,
    imageAvailable,
    pageWidth,
    pageHeight,
  };
}

function decodeRiskFlag(
  value: unknown,
  scanId: string,
  index: number,
): OcrRiskFlagView {
  const row = record(value, `risk_scan.flags[${index}]`);
  const path = `risk_scan.flags[${index}]`;
  const kind = enumValue(
    field(row, "kind", `${path}.kind`),
    [
      "negation_polarity",
      "numeric_value",
      "decimal_point",
      "unit",
      "date",
      "repeated_text",
      "output_repetition",
      "low_confidence",
    ],
    `${path}.kind`,
    "风险类型",
  );
  const level = enumValue(
    field(row, "level", `${path}.level`),
    ["blocking", "informational"],
    `${path}.level`,
    "风险级别",
  );
  const textStart = numberValue(
    field(row, "text_start", `${path}.text_start`),
    `${path}.text_start`,
  );
  const textEnd = numberValue(
    field(row, "text_end", `${path}.text_end`),
    `${path}.text_end`,
  );
  if (textStart < 0 || textEnd <= textStart)
    throw new EvidenceDecodeError(`风险 ${path} 的原文范围无效`);
  return {
    riskId: requiredString(
      field(row, "risk_id", `${path}.risk_id`),
      `${path}.risk_id`,
    ),
    riskFlagId: `${scanId}:${requiredString(field(row, "risk_id", `${path}.risk_id`), `${path}.risk_id`)}`,
    kind,
    kindLabel: nonEmptyLabel(
      field(row, "kind_label", `${path}.kind_label`),
      `${path}.kind_label`,
      "识别风险",
    ),
    level,
    levelLabel: nonEmptyLabel(
      field(row, "level_label", `${path}.level_label`),
      `${path}.level_label`,
      level === "blocking" ? "需核对" : "提示性",
    ),
    text: requiredString(field(row, "text", `${path}.text`), `${path}.text`),
    textStart,
    textEnd,
    detail: requiredNullableString(row, "detail", `${path}.detail`),
    ruleVersion: requiredString(
      field(row, "rule_version", `${path}.rule_version`),
      `${path}.rule_version`,
    ),
  };
}

function decodeRiskScan(value: unknown, index: number): OcrRiskScanView {
  const row = record(value, `page.risk_scans[${index}]`);
  const path = `page.risk_scans[${index}]`;
  const scanId = requiredString(
    field(row, "scan_id", `${path}.scan_id`),
    `${path}.scan_id`,
  );
  return {
    scanId,
    ocrPageId: requiredString(
      field(row, "ocr_page_id", `${path}.ocr_page_id`),
      `${path}.ocr_page_id`,
    ),
    rawTextSha256: requiredString(
      field(row, "raw_text_sha256", `${path}.raw_text_sha256`),
      `${path}.raw_text_sha256`,
    ),
    scannerRuleVersion: requiredString(
      field(row, "scanner_rule_version", `${path}.scanner_rule_version`),
      `${path}.scanner_rule_version`,
    ),
    flagsSha256: requiredString(
      field(row, "flags_sha256", `${path}.flags_sha256`),
      `${path}.flags_sha256`,
    ),
    coverageStatus: requiredString(
      field(row, "coverage_status", `${path}.coverage_status`),
      `${path}.coverage_status`,
    ),
    createdAt: requiredString(
      field(row, "created_at", `${path}.created_at`),
      `${path}.created_at`,
    ),
    flags: arrayValue(
      field(row, "flags", `${path}.flags`),
      `${path}.flags`,
    ).map((item, flagIndex) => decodeRiskFlag(item, scanId, flagIndex)),
  };
}

function decodeRiskReview(value: unknown, index: number): OcrRiskReviewView {
  const row = record(value, `page.risk_reviews[${index}]`);
  const path = `page.risk_reviews[${index}]`;
  const decision = enumValue(
    field(row, "decision", `${path}.decision`),
    ["confirmed_as_read", "corrected", "not_applicable"],
    `${path}.decision`,
    "风险核对决定",
  );
  return {
    reviewId: requiredString(
      field(row, "review_id", `${path}.review_id`),
      `${path}.review_id`,
    ),
    riskFlagId: requiredString(
      field(row, "risk_flag_id", `${path}.risk_flag_id`),
      `${path}.risk_flag_id`,
    ),
    decision,
    decisionLabel: nonEmptyLabel(
      field(row, "decision_label", `${path}.decision_label`),
      `${path}.decision_label`,
      "已核对",
    ),
    reason: requiredString(
      field(row, "reason", `${path}.reason`),
      `${path}.reason`,
    ),
    actor: requiredString(
      field(row, "actor", `${path}.actor`),
      `${path}.actor`,
    ),
    baseProcessingRevisionId: requiredString(
      field(
        row,
        "base_processing_revision_id",
        `${path}.base_processing_revision_id`,
      ),
      `${path}.base_processing_revision_id`,
    ),
    expectedRevision: numberValue(
      field(row, "expected_revision", `${path}.expected_revision`),
      `${path}.expected_revision`,
    ),
    createdAt: requiredString(
      field(row, "created_at", `${path}.created_at`),
      `${path}.created_at`,
    ),
  };
}

function decodeCorrection(
  value: unknown,
  index: number,
  prefix = "page.selected_corrections",
): CorrectionView {
  const row = record(value, `${prefix}[${index}]`);
  const path = `${prefix}[${index}]`;
  const changeKind = enumValue(
    field(row, "change_kind", `${path}.change_kind`),
    [
      "polarity",
      "numeric",
      "decimal",
      "unit",
      "date",
      "semantic_connector",
      "other_text",
    ],
    `${path}.change_kind`,
    "校对变化类型",
  );
  const textStart = numberValue(
    field(row, "text_start", `${path}.text_start`),
    `${path}.text_start`,
  );
  const textEnd = numberValue(
    field(row, "text_end", `${path}.text_end`),
    `${path}.text_end`,
  );
  const originalText = stringValue(
    field(row, "original_text", `${path}.original_text`),
    `${path}.original_text`,
  );
  if (
    !Number.isInteger(textStart) ||
    !Number.isInteger(textEnd) ||
    textStart < 0 ||
    textEnd < textStart
  ) {
    throw new EvidenceDecodeError(`校对 ${path} 的来源位置无效`);
  }
  if (textStart === textEnd ? originalText !== "" : originalText.length === 0) {
    throw new EvidenceDecodeError(`校对 ${path} 的原文与来源位置不一致`);
  }
  return {
    correctionId: requiredString(
      field(row, "correction_id", `${path}.correction_id`),
      `${path}.correction_id`,
    ),
    ocrPageId: requiredString(
      field(row, "ocr_page_id", `${path}.ocr_page_id`),
      `${path}.ocr_page_id`,
    ),
    rawTextSha256: requiredString(
      field(row, "raw_text_sha256", `${path}.raw_text_sha256`),
      `${path}.raw_text_sha256`,
    ),
    textStart,
    textEnd,
    originalText,
    correctedText: requiredString(
      field(row, "corrected_text", `${path}.corrected_text`),
      `${path}.corrected_text`,
    ),
    changeKind,
    changeKindLabel: nonEmptyLabel(
      field(row, "change_kind_label", `${path}.change_kind_label`),
      `${path}.change_kind_label`,
      "文字校对",
    ),
    requiresConfirmation: booleanValue(
      field(row, "requires_confirmation", `${path}.requires_confirmation`),
      `${path}.requires_confirmation`,
    ),
    confirmationActor: requiredNullableString(
      row,
      "confirmation_actor",
      `${path}.confirmation_actor`,
    ),
    confirmationAt: requiredNullableString(
      row,
      "confirmation_at",
      `${path}.confirmation_at`,
    ),
    reason: requiredString(
      field(row, "reason", `${path}.reason`),
      `${path}.reason`,
    ),
    actor: requiredString(
      field(row, "actor", `${path}.actor`),
      `${path}.actor`,
    ),
    baseProcessingRevisionId: requiredString(
      field(
        row,
        "base_processing_revision_id",
        `${path}.base_processing_revision_id`,
      ),
      `${path}.base_processing_revision_id`,
    ),
    supersedesCorrectionId: requiredNullableString(
      row,
      "supersedes_correction_id",
      `${path}.supersedes_correction_id`,
    ),
    affectedScope: requiredStringArray(
      field(row, "affected_scope", `${path}.affected_scope`),
      `${path}.affected_scope`,
    ),
    createdAt: requiredString(
      field(row, "created_at", `${path}.created_at`),
      `${path}.created_at`,
    ),
  };
}

export function decodeEvidenceLocator(
  value: unknown,
  index: number,
  pathRoot = "page.locators",
): LocatorView {
  const path = `${pathRoot}[${index}]`;
  const row = record(value, path);
  const precision = enumValue(
    field(row, "precision", `${path}.precision`),
    ["bbox", "text_range", "page_excerpt", "page_only"],
    `${path}.precision`,
    "定位精度",
  );
  const sourceLayer = enumValue(
    field(row, "source_layer", `${path}.source_layer`),
    ["native_text", "raw_ocr", "effective_text"],
    `${path}.source_layer`,
    "定位文本层",
  );
  const authenticity = enumValue(
    field(row, "authenticity", `${path}.authenticity`),
    ["authenticated", "degraded", "rejected"],
    `${path}.authenticity`,
    "定位真实性",
  );
  const disambiguation = enumValue(
    field(row, "disambiguation", `${path}.disambiguation`),
    ["unique_match", "repeated_text_degraded", "not_found"],
    `${path}.disambiguation`,
    "定位消歧结果",
  );
  const bboxWire = field(row, "bbox", `${path}.bbox`);
  const frameWire = field(row, "coordinate_frame", `${path}.coordinate_frame`);
  const bbox =
    bboxWire === null
      ? null
      : (() => {
          const item = record(bboxWire, `${path}.bbox`);
          return {
            x0: numberValue(
              field(item, "x0", `${path}.bbox.x0`),
              `${path}.bbox.x0`,
            ),
            y0: numberValue(
              field(item, "y0", `${path}.bbox.y0`),
              `${path}.bbox.y0`,
            ),
            x1: numberValue(
              field(item, "x1", `${path}.bbox.x1`),
              `${path}.bbox.x1`,
            ),
            y1: numberValue(
              field(item, "y1", `${path}.bbox.y1`),
              `${path}.bbox.y1`,
            ),
          };
        })();
  const coordinateFrame =
    frameWire === null
      ? null
      : (() => {
          const item = record(frameWire, `${path}.coordinate_frame`);
          return {
            space: requiredString(
              field(item, "space", `${path}.coordinate_frame.space`),
              `${path}.coordinate_frame.space`,
            ),
            pageWidth: numberValue(
              field(item, "page_width", `${path}.coordinate_frame.page_width`),
              `${path}.coordinate_frame.page_width`,
            ),
            pageHeight: numberValue(
              field(
                item,
                "page_height",
                `${path}.coordinate_frame.page_height`,
              ),
              `${path}.coordinate_frame.page_height`,
            ),
            rotation: numberValue(
              field(item, "rotation", `${path}.coordinate_frame.rotation`),
              `${path}.coordinate_frame.rotation`,
            ),
            transformVersion: requiredString(
              field(
                item,
                "transform_version",
                `${path}.coordinate_frame.transform_version`,
              ),
              `${path}.coordinate_frame.transform_version`,
            ),
          };
        })();
  if (precision === "bbox") {
    if (
      authenticity !== "authenticated" ||
      bbox === null ||
      coordinateFrame === null
    ) {
      throw new EvidenceDecodeError("区域定位缺少真实性证明或原始页坐标系");
    }
    if (
      coordinateFrame.pageWidth <= 0 ||
      coordinateFrame.pageHeight <= 0 ||
      bbox.x0 < 0 ||
      bbox.y0 < 0 ||
      bbox.x1 <= bbox.x0 ||
      bbox.y1 <= bbox.y0 ||
      bbox.x1 > coordinateFrame.pageWidth ||
      bbox.y1 > coordinateFrame.pageHeight
    ) {
      throw new EvidenceDecodeError("区域定位超出原始资料页范围");
    }
  } else if (bbox !== null || coordinateFrame !== null) {
    throw new EvidenceDecodeError("降级定位不得携带区域坐标");
  }
  return {
    locatorId: requiredString(
      field(row, "locator_id", `${path}.locator_id`),
      `${path}.locator_id`,
    ),
    pageArtifactId: requiredString(
      field(row, "page_artifact_id", `${path}.page_artifact_id`),
      `${path}.page_artifact_id`,
    ),
    ocrPageId: requiredNullableString(
      row,
      "ocr_page_id",
      `${path}.ocr_page_id`,
    ),
    sourceDocumentVersionId: requiredString(
      field(
        row,
        "source_document_version_id",
        `${path}.source_document_version_id`,
      ),
      `${path}.source_document_version_id`,
    ),
    pageNumber: numberValue(
      field(row, "page_number", `${path}.page_number`),
      `${path}.page_number`,
    ),
    sourceLayer,
    sourceLayerLabel: nonEmptyLabel(
      field(row, "source_layer_label", `${path}.source_layer_label`),
      `${path}.source_layer_label`,
      "证据文本",
    ),
    sourceTextSha256: requiredString(
      field(row, "source_text_sha256", `${path}.source_text_sha256`),
      `${path}.source_text_sha256`,
    ),
    targetId: requiredString(
      field(row, "target_id", `${path}.target_id`),
      `${path}.target_id`,
    ),
    precision,
    precisionLabel: nonEmptyLabel(
      field(row, "precision_label", `${path}.precision_label`),
      `${path}.precision_label`,
      "页内定位",
    ),
    degradationReason: requiredNullableString(
      row,
      "degradation_reason",
      `${path}.degradation_reason`,
    ),
    textStart: nullableNumber(
      field(row, "text_start", `${path}.text_start`),
      `${path}.text_start`,
    ),
    textEnd: nullableNumber(
      field(row, "text_end", `${path}.text_end`),
      `${path}.text_end`,
    ),
    excerpt: requiredNullableString(row, "excerpt", `${path}.excerpt`),
    disambiguation,
    locatorAlgorithmVersion: requiredString(
      field(
        row,
        "locator_algorithm_version",
        `${path}.locator_algorithm_version`,
      ),
      `${path}.locator_algorithm_version`,
    ),
    authenticity,
    matchConfidence: nullableNumber(
      field(row, "match_confidence", `${path}.match_confidence`),
      `${path}.match_confidence`,
    ),
    bbox,
    coordinateFrame,
    coordinateTransformVersion: requiredNullableString(
      row,
      "coordinate_transform_version",
      `${path}.coordinate_transform_version`,
    ),
  };
}

export function decodeOcrPage(wire: unknown): OcrPageView {
  const row = record(wire, "ocr_page");
  const status = enumValue(
    field(row, "status", "page.status"),
    ["pending", "processing", "succeeded", "failed", "cancelled"],
    "page.status",
    "识别页状态",
  );
  const rawText = requiredString(
    field(row, "raw_text", "page.raw_text"),
    "page.raw_text",
  );
  const selectedCorrections = arrayValue(
    field(row, "selected_corrections", "page.selected_corrections"),
    "page.selected_corrections",
  ).map((item, index) => decodeCorrection(item, index));
  for (const correction of selectedCorrections) {
    if (
      correction.textStart < 0 ||
      correction.textEnd < correction.textStart ||
      correction.textEnd > rawText.length
    ) {
      throw new EvidenceDecodeError("校对范围超出原始识别文本");
    }
    if (
      rawText.slice(correction.textStart, correction.textEnd) !==
      correction.originalText
    ) {
      throw new EvidenceDecodeError("校对原文与原始识别文本不一致");
    }
  }
  return {
    ocrPageId: requiredString(
      field(row, "ocr_page_id", "page.ocr_page_id"),
      "page.ocr_page_id",
    ),
    pageArtifactId: requiredString(
      field(row, "page_artifact_id", "page.page_artifact_id"),
      "page.page_artifact_id",
    ),
    sourceDocumentVersionId: requiredString(
      field(
        row,
        "source_document_version_id",
        "page.source_document_version_id",
      ),
      "page.source_document_version_id",
    ),
    pageNumber: numberValue(
      field(row, "page_number", "page.page_number"),
      "page.page_number",
    ),
    sourceSha256: requiredString(
      field(row, "source_sha256", "page.source_sha256"),
      "page.source_sha256",
    ),
    rawText,
    rawTextSha256: requiredString(
      field(row, "raw_text_sha256", "page.raw_text_sha256"),
      "page.raw_text_sha256",
    ),
    status,
    statusLabel: nonEmptyLabel(
      field(row, "status_label", "page.status_label"),
      "page.status_label",
      OCR_STATUS_LABELS[status],
    ),
    processingRevisionId: requiredNullableString(
      row,
      "processing_revision_id",
      "page.processing_revision_id",
    ),
    isCurrentRevision: booleanValue(
      field(row, "is_current_revision", "page.is_current_revision"),
      "page.is_current_revision",
    ),
    effectiveText: requiredNullableString(
      row,
      "effective_text",
      "page.effective_text",
    ),
    effectiveTextSha256: requiredNullableString(
      row,
      "effective_text_sha256",
      "page.effective_text_sha256",
    ),
    selectedCorrections,
    riskScans: arrayValue(
      field(row, "risk_scans", "page.risk_scans"),
      "page.risk_scans",
    ).map(decodeRiskScan),
    riskReviews: arrayValue(
      field(row, "risk_reviews", "page.risk_reviews"),
      "page.risk_reviews",
    ).map(decodeRiskReview),
    locators: arrayValue(
      field(row, "locators", "page.locators"),
      "page.locators",
    ).map((locator, index) => decodeEvidenceLocator(locator, index)),
  };
}

function decodeResolution(
  value: unknown,
  path: string,
): ReferencedDocumentResolutionView {
  const row = record(value, path);
  const statusValue = requiredNullableString(row, "status", `${path}.status`);
  const status =
    statusValue === null
      ? null
      : enumValue(
          statusValue,
          ["unresolved", "provided"],
          `${path}.status`,
          "资料满足状态",
        );
  return {
    resolutionRevisionId: requiredNullableString(
      row,
      "resolution_revision_id",
      `${path}.resolution_revision_id`,
    ),
    status,
    statusLabel:
      requiredNullableString(row, "status_label", `${path}.status_label`) ??
      (status === null ? null : RESOLUTION_STATUS_LABELS[status]),
    sourceDocumentVersionId: requiredNullableString(
      row,
      "source_document_version_id",
      `${path}.source_document_version_id`,
    ),
    revision: nullableNumber(
      field(row, "revision", `${path}.revision`),
      `${path}.revision`,
    ),
    createdBy: requiredNullableString(row, "created_by", `${path}.created_by`),
    createdAt: requiredNullableString(row, "created_at", `${path}.created_at`),
  };
}

export function decodeReferencedDocument(
  wire: unknown,
): ReferencedDocumentView {
  const row = record(wire, "referenced_document");
  const origin = enumValue(
    field(row, "origin", "referenced.origin"),
    ["manual", "deterministic_candidate"],
    "referenced.origin",
    "资料来源",
  );
  const status = enumValue(
    field(row, "status", "referenced.status"),
    ["proposed", "confirmed", "dismissed"],
    "referenced.status",
    "被提及资料状态",
  );
  const resolutionWire = field(row, "resolution", "referenced.resolution");
  return {
    revisionId: requiredString(
      field(row, "revision_id", "referenced.revision_id"),
      "referenced.revision_id",
    ),
    referencedDocumentId: requiredString(
      field(row, "referenced_document_id", "referenced.referenced_document_id"),
      "referenced.referenced_document_id",
    ),
    projectId: requiredString(
      field(row, "project_id", "referenced.project_id"),
      "referenced.project_id",
    ),
    subjectId: requiredString(
      field(row, "subject_id", "referenced.subject_id"),
      "referenced.subject_id",
    ),
    reviewEpisodeId: requiredString(
      field(row, "review_episode_id", "referenced.review_episode_id"),
      "referenced.review_episode_id",
    ),
    description: requiredString(
      field(row, "description", "referenced.description"),
      "referenced.description",
    ),
    documentType: requiredNullableString(
      row,
      "document_type",
      "referenced.document_type",
    ),
    sourceParty: requiredNullableString(
      row,
      "source_party",
      "referenced.source_party",
    ),
    origin,
    originLabel: nonEmptyLabel(
      field(row, "origin_label", "referenced.origin_label"),
      "referenced.origin_label",
      origin === "manual" ? "手工登记" : "系统候选",
    ),
    patternVersion: requiredNullableString(
      row,
      "pattern_version",
      "referenced.pattern_version",
    ),
    status,
    statusLabel: nonEmptyLabel(
      field(row, "status_label", "referenced.status_label"),
      "referenced.status_label",
      REFERENCED_STATUS_LABELS[status],
    ),
    userReviewed: booleanValue(
      field(row, "user_reviewed", "referenced.user_reviewed"),
      "referenced.user_reviewed",
    ),
    reason: requiredNullableString(row, "reason", "referenced.reason"),
    revision: numberValue(
      field(row, "revision", "referenced.revision"),
      "referenced.revision",
    ),
    supersedesRevisionId: requiredNullableString(
      row,
      "supersedes_revision_id",
      "referenced.supersedes_revision_id",
    ),
    triggerLocatorId: requiredNullableString(
      row,
      "trigger_locator_id",
      "referenced.trigger_locator_id",
    ),
    resolution:
      resolutionWire === null
        ? null
        : decodeResolution(resolutionWire, "referenced.resolution"),
    createdAt: requiredString(
      field(row, "created_at", "referenced.created_at"),
      "referenced.created_at",
    ),
    createdBy: requiredString(
      field(row, "created_by", "referenced.created_by"),
      "referenced.created_by",
    ),
  };
}

export function decodeReferencedDocumentList(
  wire: unknown,
): ReferencedDocumentListView {
  const row = record(wire, "referenced_document_list");
  return {
    subjectId: requiredString(
      field(row, "subject_id", "referenced_list.subject_id"),
      "referenced_list.subject_id",
    ),
    reviewEpisodeId: requiredString(
      field(row, "review_episode_id", "referenced_list.review_episode_id"),
      "referenced_list.review_episode_id",
    ),
    items: arrayValue(
      field(row, "items", "referenced_list.items"),
      "referenced_list.items",
    ).map(decodeReferencedDocument),
  };
}

export function decodeReferencedDocumentResolution(
  wire: unknown,
): ReferencedDocumentResolutionView {
  return decodeResolution(wire, "resolution");
}

function decodeProcessingCandidate(
  value: unknown,
  path: string,
): ProcessingCandidateView {
  const row = record(value, path);
  const candidateStatus = enumValue(
    field(row, "candidate_status", `${path}.candidate_status`),
    Object.keys(CANDIDATE_STATUS_LABELS) as ProcessingCandidateStatus[],
    `${path}.candidate_status`,
    "处理候选状态",
  );
  return {
    candidateId: requiredString(
      field(row, "candidate_id", `${path}.candidate_id`),
      `${path}.candidate_id`,
    ),
    jobId: requiredNullableString(row, "job_id", `${path}.job_id`),
    candidateStatus,
    candidateStatusLabel: nonEmptyLabel(
      field(row, "candidate_status_label", `${path}.candidate_status_label`),
      `${path}.candidate_status_label`,
      CANDIDATE_STATUS_LABELS[candidateStatus],
    ),
    candidateEventSeq: numberValue(
      field(row, "candidate_event_seq", `${path}.candidate_event_seq`),
      `${path}.candidate_event_seq`,
    ),
    completeRevisionId: requiredNullableString(
      row,
      "complete_revision_id",
      `${path}.complete_revision_id`,
    ),
  };
}

export function decodeProcessingCandidateStatus(
  wire: unknown,
): ProcessingCandidateView {
  return decodeProcessingCandidate(wire, "processing_candidate");
}

export function decodeCorrectionResponse(
  wire: unknown,
): CorrectionCreateResponseView {
  const row = record(wire, "correction_response");
  return {
    ...decodeProcessingCandidate(row, "correction_response"),
    correction: decodeCorrection(
      field(row, "correction", "correction_response.correction"),
      0,
      "correction_response.correction",
    ),
    created: booleanValue(
      field(row, "created", "correction_response.created"),
      "correction_response.created",
    ),
  };
}

export function decodeRiskReviewResponse(
  wire: unknown,
): RiskReviewCreateResponseView {
  const row = record(wire, "risk_review_response");
  return {
    ...decodeProcessingCandidate(row, "risk_review_response"),
    review: decodeRiskReview(
      field(row, "review", "risk_review_response.review"),
      0,
    ),
    created: booleanValue(
      field(row, "created", "risk_review_response.created"),
      "risk_review_response.created",
    ),
  };
}

export function decodeRiskPageReviewResponse(
  wire: unknown,
): RiskPageReviewCreateResponseView {
  const row = record(wire, "risk_page_review_response");
  const pageReview = record(
    field(row, "page_review", "risk_page_review_response.page_review"),
    "risk_page_review_response.page_review",
  );
  return {
    ...decodeProcessingCandidate(row, "risk_page_review_response"),
    pageReviewId: requiredString(
      field(
        pageReview,
        "page_review_id",
        "risk_page_review_response.page_review.page_review_id",
      ),
      "risk_page_review_response.page_review.page_review_id",
    ),
    coveredFlagIds: arrayValue(
      field(
        pageReview,
        "covered_flag_ids",
        "risk_page_review_response.page_review.covered_flag_ids",
      ),
      "risk_page_review_response.page_review.covered_flag_ids",
    ).map((value, index) =>
      requiredString(
        value,
        `risk_page_review_response.page_review.covered_flag_ids[${index}]`,
      ),
    ),
    reviews: arrayValue(
      field(row, "reviews", "risk_page_review_response.reviews"),
      "risk_page_review_response.reviews",
    ).map((value, index) => decodeRiskReview(value, index)),
    created: booleanValue(
      field(row, "created", "risk_page_review_response.created"),
      "risk_page_review_response.created",
    ),
  };
}

export function decodeBuildRevisionResponse(
  wire: unknown,
): BuildRevisionResponseView {
  const row = record(wire, "build_revision_response");
  const revision = field(row, "revision", "build_revision_response.revision");
  return {
    ...decodeProcessingCandidate(row, "build_revision_response"),
    created: booleanValue(
      field(row, "created", "build_revision_response.created"),
      "build_revision_response.created",
    ),
    revision: revision === null ? null : decodeProcessingRevision(revision),
  };
}

export function isProcessingCandidatePending(
  status: ProcessingCandidateStatus,
): boolean {
  switch (status) {
    case "staged":
    case "processing":
      return true;
    case "needs_attention":
    case "retryable_failure":
    case "terminal_failure":
    case "ready":
    case "active":
    case "revision_conflict":
    case "cancelled":
      return false;
  }
}

export interface ConflictDifferenceRow {
  field: string;
  submitted: string;
  current: string;
}

const FIELD_LABELS: Record<string, string> = {
  description: "资料说明",
  document_type: "资料类型",
  source_party: "资料来源方",
  trigger_locator_id: "触发定位",
  text_start: "原文起点",
  text_end: "原文终点",
  corrected_text: "校对后文本",
  original_text: "原始文本",
  reason: "本次说明",
  expected_revision: "当前修订",
  status: "当前状态",
};

function displayValue(value: EvidenceJsonValue | undefined): string {
  if (value === undefined) return "未提交";
  if (value === null) return "未填写";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean")
    return String(value);
  if (Array.isArray(value)) return value.map(displayValue).join("、");
  const entries = Object.entries(value).filter(
    ([key]) => !key.endsWith("_id") && key !== "idempotency_key",
  );
  if (entries.length === 0) return "系统中的另一版本";
  return entries
    .map(
      ([key, item]) =>
        `${FIELD_LABELS[key] ?? "相关内容"}：${displayValue(item)}`,
    )
    .join("；");
}

export function conflictDifferenceRows(
  context: EvidenceConflictContext | null,
): ConflictDifferenceRow[] {
  if (context === null) return [];
  return Object.entries(context.fieldDiff).map(([key, diff]) => {
    const diffRecord =
      diff !== null && typeof diff === "object" && !Array.isArray(diff)
        ? diff
        : null;
    const submitted = diffRecord?.submitted ?? context.submitted[key];
    const current = diffRecord?.current ?? context.currentRecord[key];
    return {
      field: FIELD_LABELS[key] ?? "相关内容",
      submitted: displayValue(submitted),
      current: displayValue(current),
    };
  });
}

export function criticalCorrectionKind(kind: CorrectionChangeKind): boolean {
  return [
    "polarity",
    "numeric",
    "decimal",
    "unit",
    "date",
    "semantic_connector",
  ].includes(kind);
}

const CRITICAL_CORRECTION_TOKEN =
  /未见(?:异常)?|否认|确认|可见|阴性|阳性|正常|异常|未使用|已使用|未接受|已接受|未接种|已接种|\d+(?:\.\d+)?|mg\/dL|mg\/dl|ug\/L|μg\/L|µg\/L|U\/L|u\/L|IU\/L|mmol\/L|umol\/L|μmol\/L|µmol\/L|ng\/mL|pg\/mL|g\/L|mmHg|cmH2O|%|并且|以及|同时|任一|任意|全部|所有|至少|至多|且|或|和/g;

export function criticalCorrectionTextChanged(
  originalText: string,
  correctedText: string,
): boolean {
  const signature = (text: string) =>
    JSON.stringify((text.match(CRITICAL_CORRECTION_TOKEN) ?? []).sort());
  return signature(originalText) !== signature(correctedText);
}

export function correctionKindLabel(kind: CorrectionChangeKind): string {
  const labels: Record<CorrectionChangeKind, string> = {
    polarity: "肯定/否定",
    numeric: "关键数值",
    decimal: "小数点",
    unit: "单位",
    date: "日期",
    semantic_connector: "语义连接词",
    other_text: "其他文字",
  };
  return labels[kind];
}
