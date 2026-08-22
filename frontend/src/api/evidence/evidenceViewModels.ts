/**
 * 证据工作台领域模型与运行时解码（Slice 4.2）。
 * - 组件只消费 EvidenceUploadPreviewView / EvidenceSnapshotView / EvidenceCommitView。
 * - 解码在运行时校验网络载荷形状与枚举取值：未知分类、缺失必填字段立即抛出
 *   EvidenceDecodeError，绝不把 undefined 或机器值渲染进界面。
 * - 服务端已投影中文标签（status_label / reason / next_action 等）；本模块只提供
 *   兜底中文映射，确保缺失标签时界面仍保持自然中文，不暴露内部枚举词。
 */

import type { EvidenceUploadErrorBody } from "./evidenceTypes";
import type { ProcessingCandidateStatusWire } from "./evidenceProcessingTypes";

// ---------------------------------------------------------------------------
// 领域模型
// ---------------------------------------------------------------------------

export type EvidenceUploadMode = "incremental" | "full";

export type EvidenceItemStatus =
  | "added"
  | "duplicate"
  | "conflict"
  | "unsupported"
  | "unreadable"
  | "full_snapshot_omission"
  | "expected_reprocessing";

export type EvidencePreviewStatus =
  "staged" | "committed" | "cancelled" | "cancel_pending";

export type EvidenceConflictResolution = "new_version" | "keep_parallel";

export type EvidenceSnapshotStatus =
  | "staged"
  | "processing"
  | "needs_attention"
  | "retryable_failure"
  | "terminal_failure"
  | "ready"
  | "active"
  | "revision_conflict"
  | "cancelled";

export interface EvidenceItemView {
  itemId: string;
  fileName: string;
  byteSize: number;
  mediaType: string;
  status: EvidenceItemStatus;
  statusLabel: string;
  processingHintLabel: string;
  reason: string;
  nextAction: string;
  logicalDocumentId: string | null;
  existingVersionId: string | null;
}

export interface EvidenceUploadPreviewView {
  previewId: string;
  projectId: string;
  subjectId: string;
  reviewEpisodeId: string;
  uploadMode: EvidenceUploadMode;
  uploadModeLabel: string;
  baseRevision: number;
  baseSnapshotId: string | null;
  status: EvidencePreviewStatus;
  statusLabel: string;
  items: EvidenceItemView[];
  matchingSnapshotId: string | null;
  matchingSnapshotStatus: EvidenceSnapshotStatus | null;
  matchingSnapshotStatusLabel: string | null;
  previewSha256: string;
  createdAt: string;
}

export interface EvidenceMetadataRevisionView {
  metadataRevisionId: string;
  sourceDocumentVersionId: string;
  documentType: string;
  sourceParty: string;
  reason: string;
  isAutoSuggestion: boolean;
  supersedesMetadataRevisionId: string | null;
  revision: number;
  createdAt: string;
  createdBy: string;
}

export interface EvidenceMetadataRevisionResponseView {
  metadata: EvidenceMetadataRevisionView;
  /** true 表示追加了新修订；false 表示同一幂等请求的安全回放。 */
  created: boolean;
}

export interface EvidenceSnapshotMemberView {
  memberId: string;
  snapshotId: string;
  logicalDocumentId: string;
  sourceDocumentVersionId: string;
  fileName: string;
  mediaType: string;
  versionNumber: number;
  origin: string;
  originLabel: string;
  metadataHead: EvidenceMetadataRevisionView;
}

export interface EvidenceSnapshotCandidateView {
  candidateId: string;
  jobId: string | null;
  candidateStatus: ProcessingCandidateStatusWire;
  candidateStatusLabel: string;
  candidateEventSeq: number;
  completeRevisionId: string | null;
}

export interface EvidenceSnapshotView {
  evidenceSnapshotId: string;
  projectId: string;
  subjectId: string;
  reviewEpisodeId: string;
  uploadMode: EvidenceUploadMode;
  uploadModeLabel: string;
  priorSnapshotId: string | null;
  comparisonSnapshotId: string | null;
  status: EvidenceSnapshotStatus;
  statusLabel: string;
  /** 服务端依据审核节点成对活动指针投影；前端不得按状态/时间推导。 */
  isCurrent: boolean;
  baseProcessingRevisionId: string | null;
  /** 本次上传的持久处理任务；处理候选尚未生成时仍可恢复任务详情。 */
  uploadJobId: string | null;
  latestProcessingCandidate: EvidenceSnapshotCandidateView | null;
  members: EvidenceSnapshotMemberView[];
  collectionSha256: string;
  createdAt: string;
}

export interface EvidenceSnapshotListView {
  subjectId: string;
  reviewEpisodeId: string;
  activeEvidenceSnapshotId: string | null;
  activeEvidenceProcessingRevisionId: string | null;
  items: EvidenceSnapshotView[];
}

export interface EvidenceResolutionDecisionView {
  itemId: string;
  logicalDocumentId: string;
  resolution: EvidenceConflictResolution;
  resolutionLabel: string;
  sourceDocumentVersionId: string;
  supersedesVersionId: string | null;
}

export interface EvidenceCommitView {
  commitId: string;
  previewId: string;
  evidenceSnapshotId: string;
  projectId: string;
  subjectId: string;
  reviewEpisodeId: string;
  uploadMode: EvidenceUploadMode;
  uploadModeLabel: string;
  idempotencyKey: string;
  jobId: string | null;
  /** 三标志互斥：新建候选 / 同键回放 / 跨预览同集合 no-op。 */
  created: boolean;
  replayed: boolean;
  duplicate: boolean;
  resolutions: EvidenceResolutionDecisionView[];
  snapshot: EvidenceSnapshotView;
  createdAt: string;
}

// ---------------------------------------------------------------------------
// 错误类型
// ---------------------------------------------------------------------------

export type EvidenceJsonPrimitive = null | boolean | number | string;
export type EvidenceJsonValue =
  | EvidenceJsonPrimitive
  | EvidenceJsonValue[]
  | { [key: string]: EvidenceJsonValue };

export interface EvidenceConflictContext {
  submitted: Record<string, EvidenceJsonValue>;
  currentRecord: Record<string, EvidenceJsonValue>;
  fieldDiff: Record<string, EvidenceJsonValue>;
}

export class EvidenceApiError extends Error {
  readonly code: string;
  readonly title: string;
  readonly recoveryAction: string;
  readonly statusCode: number;
  readonly conflictContext: EvidenceConflictContext | null;

  constructor(
    code: string,
    title: string,
    message: string,
    recoveryAction: string,
    statusCode = 0,
    conflictContext: EvidenceConflictContext | null = null,
  ) {
    super(message);
    this.name = "EvidenceApiError";
    this.code = code;
    this.title = title;
    this.recoveryAction = recoveryAction;
    this.statusCode = statusCode;
    this.conflictContext = conflictContext;
  }
}

/** 服务端返回了无法识别的载荷（未知分类/缺字段）：视为系统异常，不猜测渲染。 */
export class EvidenceDecodeError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "EvidenceDecodeError";
  }
}

// ---------------------------------------------------------------------------
// 兜底中文映射（服务端标签缺失时使用；用户可见，永不输出机器值）
// ---------------------------------------------------------------------------

const UPLOAD_MODE_FALLBACK_LABELS: Record<EvidenceUploadMode, string> = {
  incremental: "补充资料",
  full: "建立完整资料快照",
};

const ITEM_STATUS_FALLBACK_LABELS: Record<EvidenceItemStatus, string> = {
  added: "新增资料",
  duplicate: "内容重复",
  conflict: "名称相同但内容不同",
  unsupported: "格式不支持",
  unreadable: "无法读取",
  full_snapshot_omission: "完整资料中未选择",
  expected_reprocessing: "需要重新识别",
};

const PREVIEW_STATUS_FALLBACK_LABELS: Record<EvidencePreviewStatus, string> = {
  staged: "等待确认",
  committed: "已确认",
  cancelled: "已取消",
  cancel_pending: "正在取消",
};

const SNAPSHOT_STATUS_FALLBACK_LABELS: Record<EvidenceSnapshotStatus, string> =
  {
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

const RESOLUTION_FALLBACK_LABELS: Record<EvidenceConflictResolution, string> = {
  new_version: "作为原资料的新版本",
  keep_parallel: "作为另一份资料并列保留",
};

const ITEM_NEXT_ACTION_FALLBACK: Record<EvidenceItemStatus, string> = {
  added: "将首次处理该文件，请确认后提交。",
  duplicate: "系统将复用已有处理结果，不会重复保存或重复识别。",
  conflict: "请选择“作为原资料的新版本”或“作为另一份资料并列保留”。",
  unsupported: "该文件格式当前不受支持。",
  unreadable: "该文件无法读取，请检查后重新选择。",
  full_snapshot_omission:
    "如确认遗漏，请重新选择该文件；完整资料快照只包含本次选择。",
  expected_reprocessing: "系统将按本次快照重新处理该文件。",
};

// ---------------------------------------------------------------------------
// 运行时校验工具
// ---------------------------------------------------------------------------

function requireRecord(value: unknown, field: string): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new EvidenceDecodeError(`响应字段 ${field} 应为对象`);
  }
  return value as Record<string, unknown>;
}

function requireString(value: unknown, field: string): string {
  if (typeof value !== "string") {
    throw new EvidenceDecodeError(`响应字段 ${field} 应为字符串`);
  }
  return value;
}

function requireNumber(value: unknown, field: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new EvidenceDecodeError(`响应字段 ${field} 应为数值`);
  }
  return value;
}

function requirePositiveInteger(value: unknown, field: string): number {
  const decoded = requireNumber(value, field);
  if (!Number.isSafeInteger(decoded) || decoded < 1) {
    throw new EvidenceDecodeError(`响应字段 ${field} 应为正整数`);
  }
  return decoded;
}

function requireNonEmptyString(value: unknown, field: string): string {
  const decoded = requireString(value, field);
  if (decoded.trim().length === 0) {
    throw new EvidenceDecodeError(`响应字段 ${field} 不能为空`);
  }
  return decoded;
}

function requireUtcDateTimeString(value: unknown, field: string): string {
  const decoded = requireNonEmptyString(value, field);
  const hasUtcOffset = decoded.endsWith("Z") || decoded.endsWith("+00:00");
  if (!hasUtcOffset || Number.isNaN(Date.parse(decoded))) {
    throw new EvidenceDecodeError(`响应字段 ${field} 应为有效的 UTC 时间`);
  }
  return decoded;
}

function requireBoolean(value: unknown, field: string): boolean {
  if (typeof value !== "boolean") {
    throw new EvidenceDecodeError(`响应字段 ${field} 应为布尔值`);
  }
  return value;
}

function requireArray(value: unknown, field: string): unknown[] {
  if (!Array.isArray(value)) {
    throw new EvidenceDecodeError(`响应字段 ${field} 应为数组`);
  }
  return value;
}

function optionalString(value: unknown, field: string): string | null {
  if (value === null || value === undefined) return null;
  return requireString(value, field);
}

function requiredNullableString(
  row: Record<string, unknown>,
  key: string,
  field: string,
): string | null {
  if (!(key in row)) {
    throw new EvidenceDecodeError(`响应缺少字段 ${field}`);
  }
  return optionalString(row[key], field);
}

export function decodeJsonValue(
  value: unknown,
  field: string,
): EvidenceJsonValue {
  if (
    value === null ||
    typeof value === "string" ||
    typeof value === "boolean"
  ) {
    return value;
  }
  if (typeof value === "number") {
    if (!Number.isFinite(value)) {
      throw new EvidenceDecodeError(`响应字段 ${field} 应为有限数值`);
    }
    return value;
  }
  if (Array.isArray(value)) {
    return value.map((item, index) =>
      decodeJsonValue(item, `${field}[${index}]`),
    );
  }
  if (value !== null && typeof value === "object") {
    const record: Record<string, EvidenceJsonValue> = {};
    for (const [key, item] of Object.entries(value)) {
      record[key] = decodeJsonValue(item, `${field}.${key}`);
    }
    return record;
  }
  throw new EvidenceDecodeError(`响应字段 ${field} 不是有效的结构化值`);
}

function decodeJsonRecord(
  value: unknown,
  field: string,
): Record<string, EvidenceJsonValue> {
  const decoded = decodeJsonValue(value, field);
  if (
    decoded === null ||
    Array.isArray(decoded) ||
    typeof decoded !== "object"
  ) {
    throw new EvidenceDecodeError(`响应字段 ${field} 应为结构化对象`);
  }
  return decoded;
}

function decodeConflictContext(value: unknown): EvidenceConflictContext | null {
  if (value === undefined || value === null) return null;
  const row = requireRecord(value, "error.context");
  return {
    submitted: decodeJsonRecord(row.submitted ?? {}, "error.context.submitted"),
    currentRecord: decodeJsonRecord(
      row.current_record ?? {},
      "error.context.current_record",
    ),
    fieldDiff: decodeJsonRecord(
      row.field_diff ?? {},
      "error.context.field_diff",
    ),
  };
}

function asMode(value: unknown, field: string): EvidenceUploadMode {
  const raw = requireString(value, field);
  if (raw !== "incremental" && raw !== "full") {
    throw new EvidenceDecodeError(`未知的上传方式 ${raw}`);
  }
  return raw;
}

function asItemStatus(value: unknown, field: string): EvidenceItemStatus {
  const raw = requireString(value, field);
  const statuses: readonly EvidenceItemStatus[] = [
    "added",
    "duplicate",
    "conflict",
    "unsupported",
    "unreadable",
    "full_snapshot_omission",
    "expected_reprocessing",
  ];
  if (!statuses.includes(raw as EvidenceItemStatus)) {
    throw new EvidenceDecodeError(`未知的资料分类 ${raw}`);
  }
  return raw as EvidenceItemStatus;
}

function asPreviewStatus(value: unknown, field: string): EvidencePreviewStatus {
  const raw = requireString(value, field);
  const statuses: readonly EvidencePreviewStatus[] = [
    "staged",
    "committed",
    "cancelled",
    "cancel_pending",
  ];
  if (!statuses.includes(raw as EvidencePreviewStatus)) {
    throw new EvidenceDecodeError(`未知的预览状态 ${raw}`);
  }
  return raw as EvidencePreviewStatus;
}

function asSnapshotStatus(
  value: unknown,
  field: string,
): EvidenceSnapshotStatus {
  const raw = requireString(value, field);
  const statuses: readonly EvidenceSnapshotStatus[] = [
    "staged",
    "processing",
    "needs_attention",
    "retryable_failure",
    "terminal_failure",
    "ready",
    "active",
    "revision_conflict",
    "cancelled",
  ];
  if (!statuses.includes(raw as EvidenceSnapshotStatus)) {
    throw new EvidenceDecodeError(`未知的快照状态 ${raw}`);
  }
  return raw as EvidenceSnapshotStatus;
}

function asResolution(
  value: unknown,
  field: string,
): EvidenceConflictResolution {
  const raw = requireString(value, field);
  if (raw !== "new_version" && raw !== "keep_parallel") {
    throw new EvidenceDecodeError(`未知的处置方式 ${raw}`);
  }
  return raw;
}

function textOr(value: unknown, field: string, fallback: string): string {
  const raw = requireString(value, field);
  return raw.length > 0 ? raw : fallback;
}

// ---------------------------------------------------------------------------
// 解码器
// ---------------------------------------------------------------------------

export function decodeUploadPreviewError(
  payload: unknown,
  statusCode = 0,
): EvidenceApiError {
  if (payload !== null && typeof payload === "object" && "error" in payload) {
    try {
      const error = requireRecord(payload.error, "error");
      const detail =
        typeof error.detail === "string" && error.detail.length > 0
          ? error.detail
          : "请求未能完成。";
      const title = typeof error.title === "string" ? error.title : "操作失败";
      const code = typeof error.code === "string" ? error.code : "UNKNOWN";
      const recovery =
        typeof error.recovery_action === "string" &&
        error.recovery_action.length > 0
          ? error.recovery_action
          : "请稍后重试。";
      return new EvidenceApiError(
        code,
        title,
        detail,
        recovery,
        statusCode,
        decodeConflictContext(error.context),
      );
    } catch {
      // 信封结构损坏：按不可识别错误处理
    }
  }
  return new EvidenceApiError(
    "INVALID_RESPONSE",
    "服务响应异常",
    "证据服务返回了无法识别的错误格式。",
    "请稍后重试；若问题持续出现，请联系维护人员。",
    statusCode,
  );
}

/** 供错误类型推断使用：服务端错误信封结构。 */
export function isEvidenceUploadErrorBody(
  value: unknown,
): value is EvidenceUploadErrorBody {
  return (
    value !== null &&
    typeof value === "object" &&
    "code" in value &&
    "title" in value
  );
}

export function decodeUploadPreviewItem(wire: unknown): EvidenceItemView {
  const row = requireRecord(wire, "item");
  const status = asItemStatus(row.status, "item.status");
  const fileName = requireString(row.file_name, "item.file_name");
  const byteSize = requireNumber(row.byte_size, "item.byte_size");
  const statusLabel = textOr(
    row.status_label,
    "item.status_label",
    ITEM_STATUS_FALLBACK_LABELS[status],
  );
  const nextAction = textOr(
    row.next_action,
    "item.next_action",
    ITEM_NEXT_ACTION_FALLBACK[status],
  );
  return {
    itemId: requireString(row.item_id, "item.item_id"),
    fileName,
    byteSize,
    mediaType: textOr(row.media_type, "item.media_type", "未知格式"),
    status,
    statusLabel,
    processingHintLabel: textOr(
      row.processing_hint_label,
      "item.processing_hint_label",
      "需要处理",
    ),
    reason: textOr(row.reason, "item.reason", ""),
    nextAction,
    logicalDocumentId: optionalString(
      row.logical_document_id,
      "item.logical_document_id",
    ),
    existingVersionId: optionalString(
      row.existing_version_id,
      "item.existing_version_id",
    ),
  };
}

export function decodeUploadPreview(wire: unknown): EvidenceUploadPreviewView {
  const row = requireRecord(wire, "preview");
  const uploadMode = asMode(row.upload_mode, "preview.upload_mode");
  const status = asPreviewStatus(row.status, "preview.status");
  const items = requireArray(row.items, "preview.items").map((item) =>
    decodeUploadPreviewItem(item),
  );
  const matchingSnapshotId = requiredNullableString(
    row,
    "matching_snapshot_id",
    "preview.matching_snapshot_id",
  );
  const matchingSnapshotStatusValue = requiredNullableString(
    row,
    "matching_snapshot_status",
    "preview.matching_snapshot_status",
  );
  const matchingSnapshotStatusLabelValue = requiredNullableString(
    row,
    "matching_snapshot_status_label",
    "preview.matching_snapshot_status_label",
  );
  if (
    (matchingSnapshotId === null) !== (matchingSnapshotStatusValue === null) ||
    (matchingSnapshotId === null) !==
      (matchingSnapshotStatusLabelValue === null)
  ) {
    throw new EvidenceDecodeError(
      "响应中的重复资料版本标识、状态和状态说明必须同时存在或同时为空",
    );
  }
  const matchingSnapshotStatus =
    matchingSnapshotStatusValue === null
      ? null
      : asSnapshotStatus(
          matchingSnapshotStatusValue,
          "preview.matching_snapshot_status",
        );
  return {
    previewId: requireString(row.preview_id, "preview.preview_id"),
    projectId: requireString(row.project_id, "preview.project_id"),
    subjectId: requireString(row.subject_id, "preview.subject_id"),
    reviewEpisodeId: requireString(
      row.review_episode_id,
      "preview.review_episode_id",
    ),
    uploadMode,
    uploadModeLabel: textOr(
      row.upload_mode_label,
      "preview.upload_mode_label",
      UPLOAD_MODE_FALLBACK_LABELS[uploadMode],
    ),
    baseRevision: requireNumber(row.base_revision, "preview.base_revision"),
    baseSnapshotId: optionalString(
      row.base_snapshot_id,
      "preview.base_snapshot_id",
    ),
    status,
    statusLabel: textOr(
      row.status_label,
      "preview.status_label",
      PREVIEW_STATUS_FALLBACK_LABELS[status],
    ),
    items,
    matchingSnapshotId,
    matchingSnapshotStatus,
    matchingSnapshotStatusLabel:
      matchingSnapshotStatus === null
        ? null
        : textOr(
            matchingSnapshotStatusLabelValue,
            "preview.matching_snapshot_status_label",
            SNAPSHOT_STATUS_FALLBACK_LABELS[matchingSnapshotStatus],
          ),
    previewSha256: requireString(row.preview_sha256, "preview.preview_sha256"),
    createdAt: requireUtcDateTimeString(row.created_at, "preview.created_at"),
  };
}

export function decodeMetadataRevision(
  wire: unknown,
): EvidenceMetadataRevisionView {
  const row = requireRecord(wire, "metadata");
  const revision = requirePositiveInteger(row.revision, "metadata.revision");
  const supersedesMetadataRevisionId = requiredNullableString(
    row,
    "supersedes_metadata_revision_id",
    "metadata.supersedes_metadata_revision_id",
  );
  if (revision === 1 && supersedesMetadataRevisionId !== null) {
    throw new EvidenceDecodeError("初始资料信息修订不能引用前序修订");
  }
  if (revision > 1 && supersedesMetadataRevisionId === null) {
    throw new EvidenceDecodeError("非初始资料信息修订必须引用前序修订");
  }
  return {
    metadataRevisionId: requireNonEmptyString(
      row.metadata_revision_id,
      "metadata.metadata_revision_id",
    ),
    sourceDocumentVersionId: requireNonEmptyString(
      row.source_document_version_id,
      "metadata.source_document_version_id",
    ),
    documentType: requireNonEmptyString(
      row.document_type,
      "metadata.document_type",
    ),
    sourceParty: requireNonEmptyString(
      row.source_party,
      "metadata.source_party",
    ),
    reason: requireNonEmptyString(row.reason, "metadata.reason"),
    isAutoSuggestion: requireBoolean(
      row.is_auto_suggestion,
      "metadata.is_auto_suggestion",
    ),
    supersedesMetadataRevisionId,
    revision,
    createdAt: requireUtcDateTimeString(row.created_at, "metadata.created_at"),
    createdBy: requireNonEmptyString(row.created_by, "metadata.created_by"),
  };
}

export function decodeMetadataRevisionResponse(
  wire: unknown,
): EvidenceMetadataRevisionResponseView {
  const row = requireRecord(wire, "metadata_response");
  return {
    metadata: decodeMetadataRevision(row.metadata),
    created: requireBoolean(row.created, "metadata_response.created"),
  };
}

function decodeSnapshotMember(wire: unknown): EvidenceSnapshotMemberView {
  const row = requireRecord(wire, "member");
  const sourceDocumentVersionId = requireString(
    row.source_document_version_id,
    "member.source_document_version_id",
  );
  const metadataHead = decodeMetadataRevision(row.metadata_head);
  if (metadataHead.sourceDocumentVersionId !== sourceDocumentVersionId) {
    throw new EvidenceDecodeError("资料分类信息与快照成员不属于同一份资料");
  }
  return {
    memberId: requireString(row.member_id, "member.member_id"),
    snapshotId: requireString(row.snapshot_id, "member.snapshot_id"),
    logicalDocumentId: requireString(
      row.logical_document_id,
      "member.logical_document_id",
    ),
    sourceDocumentVersionId,
    fileName: requireString(row.file_name, "member.file_name"),
    mediaType: textOr(row.media_type, "member.media_type", "未知格式"),
    versionNumber: requireNumber(row.version_number, "member.version_number"),
    origin: requireString(row.origin, "member.origin"),
    originLabel: textOr(row.origin_label, "member.origin_label", ""),
    metadataHead,
  };
}

function decodeSnapshotCandidate(wire: unknown): EvidenceSnapshotCandidateView {
  const row = requireRecord(wire, "snapshot.latest_processing_candidate");
  const candidateStatus = requireString(
    row.candidate_status,
    "snapshot.latest_processing_candidate.candidate_status",
  );
  const statuses: readonly ProcessingCandidateStatusWire[] = [
    "staged",
    "processing",
    "needs_attention",
    "retryable_failure",
    "terminal_failure",
    "ready",
    "revision_conflict",
    "cancelled",
    "active",
  ];
  if (!statuses.includes(candidateStatus as ProcessingCandidateStatusWire)) {
    throw new EvidenceDecodeError(`未知的资料版本生成状态 ${candidateStatus}`);
  }
  const candidateEventSeq = requireNumber(
    row.candidate_event_seq,
    "snapshot.latest_processing_candidate.candidate_event_seq",
  );
  if (!Number.isSafeInteger(candidateEventSeq) || candidateEventSeq < 0) {
    throw new EvidenceDecodeError("资料版本生成状态序号应为非负整数");
  }
  return {
    candidateId: requireNonEmptyString(
      row.candidate_id,
      "snapshot.latest_processing_candidate.candidate_id",
    ),
    jobId: requiredNullableString(
      row,
      "job_id",
      "snapshot.latest_processing_candidate.job_id",
    ),
    candidateStatus: candidateStatus as ProcessingCandidateStatusWire,
    candidateStatusLabel: requireNonEmptyString(
      row.candidate_status_label,
      "snapshot.latest_processing_candidate.candidate_status_label",
    ),
    candidateEventSeq,
    completeRevisionId: requiredNullableString(
      row,
      "complete_revision_id",
      "snapshot.latest_processing_candidate.complete_revision_id",
    ),
  };
}

export function decodeSnapshot(wire: unknown): EvidenceSnapshotView {
  const row = requireRecord(wire, "snapshot");
  const uploadMode = asMode(row.upload_mode, "snapshot.upload_mode");
  const status = asSnapshotStatus(row.status, "snapshot.status");
  const members = requireArray(row.members, "snapshot.members").map(
    decodeSnapshotMember,
  );
  return {
    evidenceSnapshotId: requireString(
      row.evidence_snapshot_id,
      "snapshot.evidence_snapshot_id",
    ),
    projectId: requireString(row.project_id, "snapshot.project_id"),
    subjectId: requireString(row.subject_id, "snapshot.subject_id"),
    reviewEpisodeId: requireString(
      row.review_episode_id,
      "snapshot.review_episode_id",
    ),
    uploadMode,
    uploadModeLabel: textOr(
      row.upload_mode_label,
      "snapshot.upload_mode_label",
      UPLOAD_MODE_FALLBACK_LABELS[uploadMode],
    ),
    priorSnapshotId: optionalString(
      row.prior_snapshot_id,
      "snapshot.prior_snapshot_id",
    ),
    comparisonSnapshotId: optionalString(
      row.comparison_snapshot_id,
      "snapshot.comparison_snapshot_id",
    ),
    status,
    statusLabel: textOr(
      row.status_label,
      "snapshot.status_label",
      SNAPSHOT_STATUS_FALLBACK_LABELS[status],
    ),
    isCurrent: requireBoolean(row.is_current, "snapshot.is_current"),
    baseProcessingRevisionId: requiredNullableString(
      row,
      "base_processing_revision_id",
      "snapshot.base_processing_revision_id",
    ),
    uploadJobId: requiredNullableString(
      row,
      "upload_job_id",
      "snapshot.upload_job_id",
    ),
    latestProcessingCandidate:
      row.latest_processing_candidate === null ||
      row.latest_processing_candidate === undefined
        ? null
        : decodeSnapshotCandidate(row.latest_processing_candidate),
    members,
    collectionSha256: requireString(
      row.collection_sha256,
      "snapshot.collection_sha256",
    ),
    createdAt: requireString(row.created_at, "snapshot.created_at"),
  };
}

export function decodeSnapshotList(wire: unknown): EvidenceSnapshotListView {
  const row = requireRecord(wire, "snapshot_list");
  const items = requireArray(row.items, "snapshot_list.items").map((item) =>
    decodeSnapshot(item),
  );
  const activeEvidenceSnapshotId = requiredNullableString(
    row,
    "active_evidence_snapshot_id",
    "snapshot_list.active_evidence_snapshot_id",
  );
  const activeEvidenceProcessingRevisionId = requiredNullableString(
    row,
    "active_evidence_processing_revision_id",
    "snapshot_list.active_evidence_processing_revision_id",
  );
  for (const item of items) {
    const expectedCurrent =
      item.evidenceSnapshotId === activeEvidenceSnapshotId;
    if (item.isCurrent !== expectedCurrent) {
      throw new EvidenceDecodeError(
        "资料快照的当前标记与审核节点活动指针不一致",
      );
    }
  }
  return {
    subjectId: requireString(row.subject_id, "snapshot_list.subject_id"),
    reviewEpisodeId: requireString(
      row.review_episode_id,
      "snapshot_list.review_episode_id",
    ),
    activeEvidenceSnapshotId,
    activeEvidenceProcessingRevisionId,
    items,
  };
}

export function decodeResolutionDecision(
  wire: unknown,
): EvidenceResolutionDecisionView {
  const row = requireRecord(wire, "resolution");
  const resolution = asResolution(row.resolution, "resolution.resolution");
  return {
    itemId: requireString(row.item_id, "resolution.item_id"),
    logicalDocumentId: requireString(
      row.logical_document_id,
      "resolution.logical_document_id",
    ),
    resolution,
    resolutionLabel: textOr(
      row.resolution_label,
      "resolution.resolution_label",
      RESOLUTION_FALLBACK_LABELS[resolution],
    ),
    sourceDocumentVersionId: requireString(
      row.source_document_version_id,
      "resolution.source_document_version_id",
    ),
    supersedesVersionId: optionalString(
      row.supersedes_version_id,
      "resolution.supersedes_version_id",
    ),
  };
}

export function decodeCommitResponse(wire: unknown): EvidenceCommitView {
  const row = requireRecord(wire, "commit");
  const uploadMode = asMode(row.upload_mode, "commit.upload_mode");
  const created = requireBoolean(row.created, "commit.created");
  const replayed = requireBoolean(row.replayed, "commit.replayed");
  const duplicate = requireBoolean(row.duplicate, "commit.duplicate");
  // 与后端 EvidenceUploadConfirmResult 验证器完全对齐：
  // - created 为真时不得同时标记回放或重复集合 no-op；
  // - 非新建时 must 至少标记回放或重复集合之一（回放保留原确认的 duplicate 事实，
  //   因此 replayed=true, duplicate=true 是合法组合）。
  if (created && (replayed || duplicate)) {
    throw new EvidenceDecodeError("新建候选不能同时标记为回放或重复集合 no-op");
  }
  if (!created && !replayed && !duplicate) {
    throw new EvidenceDecodeError(
      "确认结果必须标记为新建、回放或重复集合 no-op 之一",
    );
  }
  const resolutions = requireArray(row.resolutions, "commit.resolutions").map(
    decodeResolutionDecision,
  );
  const snapshot = decodeSnapshot(
    requireRecord(row.snapshot, "commit.snapshot"),
  );
  return {
    commitId: requireString(row.commit_id, "commit.commit_id"),
    previewId: requireString(row.preview_id, "commit.preview_id"),
    evidenceSnapshotId: requireString(
      row.evidence_snapshot_id,
      "commit.evidence_snapshot_id",
    ),
    projectId: requireString(row.project_id, "commit.project_id"),
    subjectId: requireString(row.subject_id, "commit.subject_id"),
    reviewEpisodeId: requireString(
      row.review_episode_id,
      "commit.review_episode_id",
    ),
    uploadMode,
    uploadModeLabel: textOr(
      row.upload_mode_label,
      "commit.upload_mode_label",
      UPLOAD_MODE_FALLBACK_LABELS[uploadMode],
    ),
    idempotencyKey: requireString(
      row.idempotency_key,
      "commit.idempotency_key",
    ),
    jobId: optionalString(row.job_id, "commit.job_id"),
    created,
    replayed,
    duplicate,
    resolutions,
    snapshot,
    createdAt: requireString(row.created_at, "commit.created_at"),
  };
}

// ---------------------------------------------------------------------------
// 展示派生
// ---------------------------------------------------------------------------

/** 文件大小中文展示（B/KB/MB），避免英文单位直接裸露。 */
export function formatByteSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** 确认结果的中文说明：同时诚实表达“请求已处理”与“命中已有资料集合”两种事实。 */
export function commitResultMessage(commit: EvidenceCommitView): string {
  if (commit.created) {
    return "已建立资料快照，正在处理；处理完成并确认启用前，当前有效资料版本不会改变。";
  }
  if (commit.replayed && commit.duplicate) {
    return "该请求已处理过，未重复建立快照；原确认命中的资料集合与已有快照相同。";
  }
  if (commit.replayed) {
    return "该请求与之前提交的内容相同，未重复建立快照。";
  }
  return "所选资料集合与已存在的快照相同，未重复建立快照。";
}
