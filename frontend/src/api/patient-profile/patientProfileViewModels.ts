/**
 * Patient Profile v2 领域模型与严格运行时解码（Slice 5.5，worker_01）。
 *
 * 只消费 Slice 5.5 HTTP 契约（patientProfileTypes.ts），不读取 fixture/旧审核详情；
 * 服务端中文标签、机器值或必填字段缺失均视为系统异常
 *（PatientProfileDecodeError），绝不在前端猜测或掩盖契约漂移。
 *
 * 硬边界（与后端合同一致）：
 * - 不包含/不推导任何入排结论、行动数量、负责方或通过/不通过语言（Phase 6/7）；
 * - 首屏突出只透出后端 highlights 显式结构化原因，绝不从风险标签关键词推导；
 * - 定位 red box 只在后端提供真实 bbox + 坐标帧时解码，绝不合成坐标。
 */

import type { ReviewStage } from "../../domain/enums";
import type { LocatorWire } from "../evidence/evidenceProcessingTypes";
import {
  decodeEvidenceLocator,
  type LocatorView,
} from "../evidence/evidenceProcessingViewModels";
import type {
  ProfileConflictMemberKindWire,
  ProfileDatePrecisionWire,
  ProfileDurationStatusWire,
  ProfileExpectationStatusWire,
  ProfileFactPolarityWire,
  ProfileGapTypeWire,
  ProfileHighlightReasonWire,
  ProfileItemKindWire,
  ProfileLaneWire,
  ProfileSourceStrengthWire,
  ProfileStatusWire,
} from "./patientProfileTypes";

// ---------------------------------------------------------------------------
// 领域模型（camelCase，wire -> 解码后的唯一消费形态）
// ---------------------------------------------------------------------------

export type ProfileStatus = ProfileStatusWire;

export type ProfileScalarValue = boolean | number | string;

export interface ProfileDateRangeView {
  sourceText: string | null;
  precision: ProfileDatePrecisionWire | null;
  precisionLabel: string | null;
  lowerBound: string | null;
  upperBound: string | null;
}

export interface ProfileEvidenceNavigationView {
  projectId: string;
  subjectId: string;
  reviewEpisodeId: string;
  evidenceSnapshotV2Id: string;
  completeProcessingRevisionId: string;
}

export interface ProfileItemView {
  itemId: string;
  lane: ProfileLaneWire;
  laneLabel: string;
  kind: ProfileItemKindWire;
  kindLabel: string;
  sourceId: string;
  sourceRevision: number;
  title: string;
  subtitle: string | null;

  startRange: ProfileDateRangeView | null;
  endRange: ProfileDateRangeView | null;
  durationStatus: ProfileDurationStatusWire | null;
  durationStatusLabel: string | null;
  recordTime: string | null;

  sourceStrength: ProfileSourceStrengthWire | null;
  sourceStrengthLabel: string | null;
  locatorIds: string[];
  requirementIds: string[];

  polarity: ProfileFactPolarityWire | null;
  polarityLabel: string | null;
  assertedObject: string | null;
  value: ProfileScalarValue | null;
  unit: string | null;

  eventType: string | null;

  medicationName: string | null;
  category: string | null;
  indication: string | null;
  dose: string | null;
  frequency: string | null;
  route: string | null;

  factIds: string[];

  conflictMemberKind: ProfileConflictMemberKindWire | null;
  conflictMemberIds: string[];
  conflictResolutionRevision: number | null;

  templateId: string | null;
  expectationStatus: ProfileExpectationStatusWire | null;
  expectationStatusLabel: string | null;
  gapType: ProfileGapTypeWire | null;
  gapTypeLabel: string | null;
  gapDetail: string | null;
  provenanceFollowup: boolean;
  provenanceReason: string | null;
}

export interface ProfileLaneSectionView {
  lane: ProfileLaneWire;
  laneLabel: string;
  items: ProfileItemView[];
}

export interface ProfileHighlightView {
  itemId: string;
  reasons: ProfileHighlightReasonWire[];
  reasonLabels: string[];
  gapType: ProfileGapTypeWire | null;
  gapTypeLabel: string | null;
  detail: string | null;
}

export interface PatientProfileRevisionView {
  revisionId: string;
  schemaVersion: "phase5/v1";
  status: ProfileStatusWire;
  statusLabel: string;
  revision: number;
  reviewStage: ReviewStage;
  reviewStageLabel: string;
  generatedAt: string | null;
  createdAt: string;
  pendingReviewCount: number;
  lanes: ProfileLaneSectionView[];
  highlights: ProfileHighlightView[];
  evidenceLocators: LocatorView[];
  evidenceNavigation: ProfileEvidenceNavigationView;
}

export interface PatientProfileHistoryView {
  subjectId: string;
  reviewEpisodeId: string;
  items: PatientProfileRevisionView[];
}

// ---------------------------------------------------------------------------
// 错误类型
// ---------------------------------------------------------------------------

/** 服务端错误信封（errors.py）：code/title/detail/recovery_action/correlation_id。 */
export class PatientProfileApiError extends Error {
  readonly code: string;
  readonly title: string;
  readonly recoveryAction: string;
  readonly statusCode: number;

  constructor(
    code: string,
    title: string,
    message: string,
    recoveryAction: string,
    statusCode = 0,
  ) {
    super(message);
    this.name = "PatientProfileApiError";
    this.code = code;
    this.title = title;
    this.recoveryAction = recoveryAction;
    this.statusCode = statusCode;
  }
}

/** 服务端返回了无法识别的载荷（未知分类/缺字段/违反契约不变量）：视为系统异常。 */
export class PatientProfileDecodeError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "PatientProfileDecodeError";
  }
}

// ---------------------------------------------------------------------------
// 运行时校验工具
// ---------------------------------------------------------------------------

function record(value: unknown, fieldName: string): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new PatientProfileDecodeError(`响应字段 ${fieldName} 应为对象`);
  }
  return value as Record<string, unknown>;
}

function field(
  row: Record<string, unknown>,
  key: string,
  fieldName: string,
): unknown {
  if (!(key in row)) {
    throw new PatientProfileDecodeError(`响应缺少字段 ${fieldName}`);
  }
  return row[key];
}

function stringValue(value: unknown, fieldName: string): string {
  if (typeof value !== "string") {
    throw new PatientProfileDecodeError(`响应字段 ${fieldName} 应为字符串`);
  }
  return value;
}

function nonEmptyString(value: unknown, fieldName: string): string {
  const decoded = stringValue(value, fieldName);
  if (decoded.trim().length === 0) {
    throw new PatientProfileDecodeError(`响应字段 ${fieldName} 不能为空`);
  }
  return decoded;
}

function numberValue(value: unknown, fieldName: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new PatientProfileDecodeError(`响应字段 ${fieldName} 应为数值`);
  }
  return value;
}

function integerValue(value: unknown, fieldName: string): number {
  const decoded = numberValue(value, fieldName);
  if (!Number.isSafeInteger(decoded)) {
    throw new PatientProfileDecodeError(`响应字段 ${fieldName} 应为整数`);
  }
  return decoded;
}

function positiveIntegerValue(value: unknown, fieldName: string): number {
  const decoded = integerValue(value, fieldName);
  if (decoded < 1) {
    throw new PatientProfileDecodeError(`响应字段 ${fieldName} 应为正整数`);
  }
  return decoded;
}

function booleanValue(value: unknown, fieldName: string): boolean {
  if (typeof value !== "boolean") {
    throw new PatientProfileDecodeError(`响应字段 ${fieldName} 应为布尔值`);
  }
  return value;
}

function arrayValue(value: unknown, fieldName: string): unknown[] {
  if (!Array.isArray(value)) {
    throw new PatientProfileDecodeError(`响应字段 ${fieldName} 应为数组`);
  }
  return value;
}

function optionalString(value: unknown, fieldName: string): string | null {
  if (value === null || value === undefined) return null;
  return stringValue(value, fieldName);
}

function requiredNullableString(
  row: Record<string, unknown>,
  key: string,
  fieldName: string,
): string | null {
  return optionalString(field(row, key, fieldName), fieldName);
}

function requiredUtcDateTime(value: unknown, fieldName: string): string {
  const decoded = nonEmptyString(value, fieldName);
  const hasUtcOffset = decoded.endsWith("Z") || decoded.endsWith("+00:00");
  if (!hasUtcOffset || Number.isNaN(Date.parse(decoded))) {
    throw new PatientProfileDecodeError(
      `响应字段 ${fieldName} 应为有效的 UTC 时间`,
    );
  }
  return decoded;
}

function optionalUtcDateTime(
  value: unknown,
  fieldName: string,
): string | null {
  if (value === null || value === undefined) return null;
  return requiredUtcDateTime(value, fieldName);
}

function scalarValue(
  value: unknown,
  fieldName: string,
): ProfileScalarValue | null {
  if (value === null || value === undefined) return null;
  if (typeof value === "boolean" || typeof value === "string") return value;
  if (typeof value === "number") {
    if (!Number.isFinite(value)) {
      throw new PatientProfileDecodeError(`响应字段 ${fieldName} 应为有限数值`);
    }
    return value;
  }
  throw new PatientProfileDecodeError(`响应字段 ${fieldName} 应为事实值`);
}

function stringArray(
  row: Record<string, unknown>,
  key: string,
  fieldName: string,
): string[] {
  return arrayValue(field(row, key, fieldName), fieldName).map((item, index) =>
    nonEmptyString(item, `${fieldName}[${index}]`),
  );
}

/** 中文标签属于 HTTP 契约；缺失或空白必须显式失败，不能由前端猜测。 */
function nonEmptyLabel(value: unknown, fieldName: string): string {
  return nonEmptyString(value, fieldName);
}

function enumValue<T extends string>(
  value: unknown,
  allowed: readonly T[],
  fieldName: string,
  label: string,
): T {
  const raw = stringValue(value, fieldName);
  if (!(allowed as readonly string[]).includes(raw)) {
    throw new PatientProfileDecodeError(`未知的${label} ${raw}`);
  }
  return raw as T;
}

function nullableEnum<T extends string>(
  value: unknown,
  allowed: readonly T[],
  fieldName: string,
  label: string,
): T | null {
  if (value === null || value === undefined) return null;
  return enumValue(value, allowed, fieldName, label);
}

function nullablePositiveInteger(
  value: unknown,
  fieldName: string,
): number | null {
  if (value === null || value === undefined) return null;
  return positiveIntegerValue(value, fieldName);
}

// ---------------------------------------------------------------------------
// 稳定机器值允许集（与后端 StableEnum/DTO 一致；未知值绝不猜测）
// ---------------------------------------------------------------------------

const PROFILE_STATUSES: readonly ProfileStatusWire[] = [
  "succeeded",
  "generating",
  "failed",
  "stale",
];

const PROFILE_LANES: readonly ProfileLaneWire[] = [
  "study_milestone",
  "demographics",
  "target_disease",
  "symptoms_signs",
  "medical_history",
  "medication",
  "non_drug_treatment",
  "test_exam_score",
  "allergy_infection_immune",
  "reproductive",
  "social_environmental",
  "special_history",
  "evidence_quality",
];

const PROFILE_ITEM_KINDS: readonly ProfileItemKindWire[] = [
  "fact",
  "event",
  "exposure",
  "conflict",
  "expectation",
];

const PROFILE_HIGHLIGHT_REASONS: readonly ProfileHighlightReasonWire[] = [
  "unresolved_conflict",
  "current_due_expectation_gap",
  "weak_source_positive_long_term_history",
  "structured_ocr_or_parse_risk",
  "source_report_abnormal",
  "source_report_critical",
  "source_report_trend",
];

const GAP_TYPES: readonly ProfileGapTypeWire[] = [
  "record_incomplete",
  "description_insufficient",
  "historical_source_unavailable",
  "referenced_file_missing",
  "required_procedure_not_done",
  "result_fields_missing",
  "date_or_anchor_missing",
  "observation_unverified",
  "professional_judgment",
  "source_conflict",
  "ocr_or_parse_risk",
  "interpretation_conflict",
  "future_stage_not_due",
  "provenance_followup",
  "control_applicability_pending",
];

const EXPECTATION_STATUSES: readonly ProfileExpectationStatusWire[] = [
  "observed",
  "observed_weak",
  "referenced_missing",
  "absent",
  "not_due",
  "pending_control_applicability",
];

const SOURCE_STRENGTHS: readonly ProfileSourceStrengthWire[] = [
  "contemporaneous_objective_result",
  "historical_primary_document",
  "current_study_chart_direct_record",
  "screening_record_transcription",
  "unverifiable_source",
];

const DURATION_STATUSES: readonly ProfileDurationStatusWire[] = [
  "ongoing",
  "ended",
  "intermittent",
  "single",
  "unknown",
];

const FACT_POLARITIES: readonly ProfileFactPolarityWire[] = [
  "affirmed",
  "negated",
  "unknown",
];

const DATE_PRECISIONS: readonly ProfileDatePrecisionWire[] = [
  "day",
  "month",
  "year",
  "unknown",
];

const REVIEW_STAGES: readonly ReviewStage[] = [
  "pre_screening",
  "screening",
  "run_in",
  "baseline",
];

const CONFLICT_MEMBER_KINDS: readonly ProfileConflictMemberKindWire[] = [
  "fact",
  "event",
  "exposure",
];

// ---------------------------------------------------------------------------
// 解码器
// ---------------------------------------------------------------------------

export function decodePatientProfileError(
  payload: unknown,
  statusCode = 0,
): PatientProfileApiError {
  if (payload !== null && typeof payload === "object" && "error" in payload) {
    try {
      const error = record(payload.error, "error");
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
      return new PatientProfileApiError(
        code,
        title,
        detail,
        recovery,
        statusCode,
      );
    } catch {
      // 信封结构损坏：按不可识别错误处理
    }
  }
  return new PatientProfileApiError(
    "INVALID_RESPONSE",
    "服务响应异常",
    "病历档案服务返回了无法识别的错误格式。",
    "请稍后重试；若问题持续出现，请联系维护人员。",
    statusCode,
  );
}

function decodeDateRange(value: unknown, path: string): ProfileDateRangeView | null {
  if (value === null || value === undefined) return null;
  const row = record(value, path);
  const precision = nullableEnum(
    field(row, "precision", `${path}.precision`),
    DATE_PRECISIONS,
    `${path}.precision`,
    "日期精度",
  );
  return {
    sourceText: requiredNullableString(row, "source_text", `${path}.source_text`),
    precision,
    precisionLabel:
      precision === null
        ? requiredNullableString(
            row,
            "precision_label",
            `${path}.precision_label`,
          )
        : nonEmptyLabel(
            field(row, "precision_label", `${path}.precision_label`),
            `${path}.precision_label`,
          ),
    lowerBound: requiredNullableString(
      row,
      "lower_bound",
      `${path}.lower_bound`,
    ),
    upperBound: requiredNullableString(
      row,
      "upper_bound",
      `${path}.upper_bound`,
    ),
  };
}

function decodeItem(value: unknown, index: number): ProfileItemView {
  const path = `lanes.items[${index}]`;
  const row = record(value, path);
  const lane = enumValue(
    field(row, "lane", `${path}.lane`),
    PROFILE_LANES,
    `${path}.lane`,
    "泳道",
  );
  const kind = enumValue(
    field(row, "kind", `${path}.kind`),
    PROFILE_ITEM_KINDS,
    `${path}.kind`,
    "条目类型",
  );
  const durationStatus = nullableEnum(
    field(row, "duration_status", `${path}.duration_status`),
    DURATION_STATUSES,
    `${path}.duration_status`,
    "持续状态",
  );
  const sourceStrength = nullableEnum(
    field(row, "source_strength", `${path}.source_strength`),
    SOURCE_STRENGTHS,
    `${path}.source_strength`,
    "来源强度",
  );
  const polarity = nullableEnum(
    field(row, "polarity", `${path}.polarity`),
    FACT_POLARITIES,
    `${path}.polarity`,
    "事实极性",
  );
  const conflictMemberKind = nullableEnum(
    field(row, "conflict_member_kind", `${path}.conflict_member_kind`),
    CONFLICT_MEMBER_KINDS,
    `${path}.conflict_member_kind`,
    "冲突成员类型",
  );
  const expectationStatus = nullableEnum(
    field(row, "expectation_status", `${path}.expectation_status`),
    EXPECTATION_STATUSES,
    `${path}.expectation_status`,
    "资料期望状态",
  );
  const gapType = nullableEnum(
    field(row, "gap_type", `${path}.gap_type`),
    GAP_TYPES,
    `${path}.gap_type`,
    "资料缺口类型",
  );
  return {
    itemId: nonEmptyString(
      field(row, "item_id", `${path}.item_id`),
      `${path}.item_id`,
    ),
    lane,
    laneLabel: nonEmptyLabel(
      field(row, "lane_label", `${path}.lane_label`),
      `${path}.lane_label`,
    ),
    kind,
    kindLabel: nonEmptyLabel(
      field(row, "kind_label", `${path}.kind_label`),
      `${path}.kind_label`,
    ),
    sourceId: nonEmptyString(
      field(row, "source_id", `${path}.source_id`),
      `${path}.source_id`,
    ),
    sourceRevision: positiveIntegerValue(
      field(row, "source_revision", `${path}.source_revision`),
      `${path}.source_revision`,
    ),
    title: nonEmptyString(
      field(row, "title", `${path}.title`),
      `${path}.title`,
    ),
    subtitle: requiredNullableString(row, "subtitle", `${path}.subtitle`),
    startRange: decodeDateRange(
      field(row, "start_range", `${path}.start_range`),
      `${path}.start_range`,
    ),
    endRange: decodeDateRange(
      field(row, "end_range", `${path}.end_range`),
      `${path}.end_range`,
    ),
    durationStatus,
    durationStatusLabel:
      durationStatus === null
        ? requiredNullableString(
            row,
            "duration_status_label",
            `${path}.duration_status_label`,
          )
        : nonEmptyLabel(
            field(row, "duration_status_label", `${path}.duration_status_label`),
            `${path}.duration_status_label`,
          ),
    recordTime: optionalUtcDateTime(
      field(row, "record_time", `${path}.record_time`),
      `${path}.record_time`,
    ),
    sourceStrength,
    sourceStrengthLabel:
      sourceStrength === null
        ? requiredNullableString(
            row,
            "source_strength_label",
            `${path}.source_strength_label`,
          )
        : nonEmptyLabel(
            field(row, "source_strength_label", `${path}.source_strength_label`),
            `${path}.source_strength_label`,
          ),
    locatorIds: stringArray(row, "locator_ids", `${path}.locator_ids`),
    requirementIds: stringArray(
      row,
      "requirement_ids",
      `${path}.requirement_ids`,
    ),
    polarity,
    polarityLabel:
      polarity === null
        ? requiredNullableString(row, "polarity_label", `${path}.polarity_label`)
        : nonEmptyLabel(
            field(row, "polarity_label", `${path}.polarity_label`),
            `${path}.polarity_label`,
          ),
    assertedObject: requiredNullableString(
      row,
      "asserted_object",
      `${path}.asserted_object`,
    ),
    value: scalarValue(field(row, "value", `${path}.value`), `${path}.value`),
    unit: requiredNullableString(row, "unit", `${path}.unit`),
    eventType: requiredNullableString(row, "event_type", `${path}.event_type`),
    medicationName: requiredNullableString(
      row,
      "medication_name",
      `${path}.medication_name`,
    ),
    category: requiredNullableString(row, "category", `${path}.category`),
    indication: requiredNullableString(
      row,
      "indication",
      `${path}.indication`,
    ),
    dose: requiredNullableString(row, "dose", `${path}.dose`),
    frequency: requiredNullableString(row, "frequency", `${path}.frequency`),
    route: requiredNullableString(row, "route", `${path}.route`),
    factIds: stringArray(row, "fact_ids", `${path}.fact_ids`),
    conflictMemberKind,
    conflictMemberIds: stringArray(
      row,
      "conflict_member_ids",
      `${path}.conflict_member_ids`,
    ),
    conflictResolutionRevision: nullablePositiveInteger(
      field(row, "conflict_resolution_revision", `${path}.conflict_resolution_revision`),
      `${path}.conflict_resolution_revision`,
    ),
    templateId: requiredNullableString(row, "template_id", `${path}.template_id`),
    expectationStatus,
    expectationStatusLabel:
      expectationStatus === null
        ? requiredNullableString(
            row,
            "expectation_status_label",
            `${path}.expectation_status_label`,
          )
        : nonEmptyLabel(
            field(
              row,
              "expectation_status_label",
              `${path}.expectation_status_label`,
            ),
            `${path}.expectation_status_label`,
          ),
    gapType,
    gapTypeLabel:
      gapType === null
        ? requiredNullableString(row, "gap_type_label", `${path}.gap_type_label`)
        : nonEmptyLabel(
            field(row, "gap_type_label", `${path}.gap_type_label`),
            `${path}.gap_type_label`,
          ),
    gapDetail: requiredNullableString(row, "gap_detail", `${path}.gap_detail`),
    provenanceFollowup: booleanValue(
      field(row, "provenance_followup", `${path}.provenance_followup`),
      `${path}.provenance_followup`,
    ),
    provenanceReason: requiredNullableString(
      row,
      "provenance_reason",
      `${path}.provenance_reason`,
    ),
  };
}

function decodeLaneSection(value: unknown, index: number): ProfileLaneSectionView {
  const path = `lanes[${index}]`;
  const row = record(value, path);
  const lane = enumValue(
    field(row, "lane", `${path}.lane`),
    PROFILE_LANES,
    `${path}.lane`,
    "泳道",
  );
  return {
    lane,
    laneLabel: nonEmptyLabel(
      field(row, "lane_label", `${path}.lane_label`),
      `${path}.lane_label`,
    ),
    items: arrayValue(field(row, "items", `${path}.items`), `${path}.items`).map(
      (item, itemIndex) => decodeItem(item, itemIndex),
    ),
  };
}

function decodeHighlight(value: unknown, index: number): ProfileHighlightView {
  const path = `highlights[${index}]`;
  const row = record(value, path);
  const reasons = arrayValue(
    field(row, "reasons", `${path}.reasons`),
    `${path}.reasons`,
  ).map((reason, reasonIndex) =>
    enumValue(
      reason,
      PROFILE_HIGHLIGHT_REASONS,
      `${path}.reasons[${reasonIndex}]`,
      "首屏突出原因",
    ),
  );
  const rawReasonLabels = arrayValue(
    field(row, "reason_labels", `${path}.reason_labels`),
    `${path}.reason_labels`,
  ).map((label, labelIndex) =>
    stringValue(label, `${path}.reason_labels[${labelIndex}]`),
  );
  if (rawReasonLabels.length !== reasons.length) {
    throw new PatientProfileDecodeError(
      `${path}.reason_labels 必须与突出原因逐项对应`,
    );
  }
  const reasonLabels = rawReasonLabels.map((label, reasonIndex) =>
    nonEmptyLabel(label, `${path}.reason_labels[${reasonIndex}]`),
  );
  const gapType = nullableEnum(
    field(row, "gap_type", `${path}.gap_type`),
    GAP_TYPES,
    `${path}.gap_type`,
    "资料缺口类型",
  );
  return {
    itemId: nonEmptyString(
      field(row, "item_id", `${path}.item_id`),
      `${path}.item_id`,
    ),
    reasons,
    reasonLabels,
    gapType,
    gapTypeLabel:
      gapType === null
        ? requiredNullableString(row, "gap_type_label", `${path}.gap_type_label`)
        : nonEmptyLabel(
            field(row, "gap_type_label", `${path}.gap_type_label`),
            `${path}.gap_type_label`,
          ),
    detail: requiredNullableString(row, "detail", `${path}.detail`),
  };
}

function decodeEvidenceNavigation(
  value: unknown,
): ProfileEvidenceNavigationView {
  const path = "evidence_navigation";
  const row = record(value, path);
  return {
    projectId: nonEmptyString(
      field(row, "project_id", `${path}.project_id`),
      `${path}.project_id`,
    ),
    subjectId: nonEmptyString(
      field(row, "subject_id", `${path}.subject_id`),
      `${path}.subject_id`,
    ),
    reviewEpisodeId: nonEmptyString(
      field(row, "review_episode_id", `${path}.review_episode_id`),
      `${path}.review_episode_id`,
    ),
    evidenceSnapshotV2Id: nonEmptyString(
      field(row, "evidence_snapshot_v2_id", `${path}.evidence_snapshot_v2_id`),
      `${path}.evidence_snapshot_v2_id`,
    ),
    completeProcessingRevisionId: nonEmptyString(
      field(
        row,
        "complete_processing_revision_id",
        `${path}.complete_processing_revision_id`,
      ),
      `${path}.complete_processing_revision_id`,
    ),
  };
}

function profileItemIds(revision: {
  lanes: ProfileLaneSectionView[];
}): Set<string> {
  return new Set(
    revision.lanes.flatMap((section) => section.items.map((item) => item.itemId)),
  );
}

export function decodePatientProfileRevision(
  wire: unknown,
): PatientProfileRevisionView {
  const path = "revision";
  const row = record(wire, path);
  const schemaVersion = nonEmptyString(
    field(row, "schema_version", `${path}.schema_version`),
    `${path}.schema_version`,
  );
  if (schemaVersion !== "phase5/v1") {
    throw new PatientProfileDecodeError(`未知的档案契约版本 ${schemaVersion}`);
  }
  const status = enumValue(
    field(row, "status", `${path}.status`),
    PROFILE_STATUSES,
    `${path}.status`,
    "档案状态",
  );
  const reviewStage = enumValue(
    field(row, "review_stage", `${path}.review_stage`),
    REVIEW_STAGES,
    `${path}.review_stage`,
    "审核阶段",
  );
  const lanes = arrayValue(
    field(row, "lanes", `${path}.lanes`),
    `${path}.lanes`,
  ).map((lane, index) => decodeLaneSection(lane, index));
  const laneSet = new Set(lanes.map((section) => section.lane));
  if (
    laneSet.size !== PROFILE_LANES.length ||
    !PROFILE_LANES.every((lane) => laneSet.has(lane))
  ) {
    throw new PatientProfileDecodeError("病历档案泳道不完整：必须恰好包含 13 条泳道");
  }
  const highlights = arrayValue(
    field(row, "highlights", `${path}.highlights`),
    `${path}.highlights`,
  ).map((highlight, index) => decodeHighlight(highlight, index));
  const evidenceLocators = arrayValue(
    field(row, "evidence_locators", `${path}.evidence_locators`),
    `${path}.evidence_locators`,
  ).map((locator, index) => {
    try {
      return decodeEvidenceLocator(locator, index, "evidence_locators");
    } catch (error: unknown) {
      if (error instanceof Error) {
        throw new PatientProfileDecodeError(error.message);
      }
      throw error;
    }
  });

  // 契约不变量：首屏突出只引用档案内条目；条目定位全部能在深链定位中解析。
  const allItemIds = profileItemIds({ lanes });
  for (const highlight of highlights) {
    if (!allItemIds.has(highlight.itemId)) {
      throw new PatientProfileDecodeError(
        `首屏突出引用了不存在的档案条目 ${highlight.itemId}`,
      );
    }
  }
  const locatorIds = new Set(evidenceLocators.map((locator) => locator.locatorId));
  const requiredLocatorIds = new Set<string>();
  for (const section of lanes) {
    for (const item of section.items) {
      for (const locatorId of item.locatorIds) {
        requiredLocatorIds.add(locatorId);
      }
    }
  }
  for (const locatorId of requiredLocatorIds) {
    if (!locatorIds.has(locatorId)) {
      throw new PatientProfileDecodeError(
        `档案条目引用的原文定位没有完整解析：${locatorId}`,
      );
    }
  }

  return {
    revisionId: nonEmptyString(
      field(row, "patient_profile_revision_id", `${path}.patient_profile_revision_id`),
      `${path}.patient_profile_revision_id`,
    ),
    schemaVersion,
    status,
    statusLabel: nonEmptyLabel(
      field(row, "status_label", `${path}.status_label`),
      `${path}.status_label`,
    ),
    revision: positiveIntegerValue(
      field(row, "revision", `${path}.revision`),
      `${path}.revision`,
    ),
    reviewStage,
    reviewStageLabel: nonEmptyLabel(
      field(row, "review_stage_label", `${path}.review_stage_label`),
      `${path}.review_stage_label`,
    ),
    generatedAt: optionalUtcDateTime(
      field(row, "generated_at", `${path}.generated_at`),
      `${path}.generated_at`,
    ),
    createdAt: requiredUtcDateTime(
      field(row, "created_at", `${path}.created_at`),
      `${path}.created_at`,
    ),
    pendingReviewCount: integerValue(
      field(row, "pending_review_count", `${path}.pending_review_count`),
      `${path}.pending_review_count`,
    ),
    lanes,
    highlights,
    evidenceLocators,
    evidenceNavigation: decodeEvidenceNavigation(
      field(row, "evidence_navigation", `${path}.evidence_navigation`),
    ),
  };
}

export function decodePatientProfileHistory(
  wire: unknown,
): PatientProfileHistoryView {
  const path = "history";
  const row = record(wire, path);
  return {
    subjectId: nonEmptyString(
      field(row, "subject_id", `${path}.subject_id`),
      `${path}.subject_id`,
    ),
    reviewEpisodeId: nonEmptyString(
      field(row, "review_episode_id", `${path}.review_episode_id`),
      `${path}.review_episode_id`,
    ),
    items: arrayValue(
      field(row, "items", `${path}.items`),
      `${path}.items`,
    ).map((revision) =>
      decodePatientProfileRevision(revision),
    ),
  };
}

// ---------------------------------------------------------------------------
// wire 类型再导出（契约测试与类型消费用；运行时解码是唯一数据入口）
// ---------------------------------------------------------------------------

export type { LocatorWire };
