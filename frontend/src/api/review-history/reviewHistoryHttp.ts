/**
 * 正式审核历史只读 HTTP 适配器（严格解码）。
 *
 * 只调用只读端点（app/api/v2/review_history.py 是固定线上合同）：
 * - GET /api/v2/subjects/{subject_id}/review-episodes/{review_episode_id}/review-runs
 * - GET /api/v2/subjects/{subject_id}/review-episodes/{review_episode_id}/review-runs/{review_run_id}
 *
 * 解码按“不可信输入”处理：未知字段（对齐后端 DTO 的 ``extra="forbid"``）、未知枚举值、
 * 缺失字段一律拒绝；并复现冻结记录自身的不变量——
 * - 路径归属：列表的 subject/episode 与请求一致；详情的 run/context 与请求身份一致；
 * - run 与冻结输入绑定：context_id / review_run_id / 阶段 / 规则修订 / 资料版本必须逐项一致；
 * - 重复身份：结论（含审核要点）、待办、状态转换不得重复，列表条目身份不得重复；
 * - 待办引用结论：assessment_id 必须属于本次审核，且与待办声明的审核要点一致；
 * - 状态与时间一致：状态只由完成时间推导、完成不早于开始、待办当前状态与最后一次转换一致，
 *   系统自动关闭必须保留转换记录；已完成审核不得缺少冻结结论。
 *
 * 本模块不重算判定、不推导阻断级别、不读取实时投影、不把待办关闭当成规则通过。
 * 失败错误复用 ``EligibilityReviewApiError``（经 ``decodeEligibilityReviewError``），
 * 现有 ``useLoad`` 无需改动即可显示中文信封；结构不可信时抛 ``ReviewHistoryDecodeError``。
 */
import { decodeEligibilityReviewError } from "../eligibility-review";
import { decodeEvidenceLocator } from "../evidence/evidenceProcessingViewModels";
import { getProtocolApiBase } from "../protocolApiConfig";
import {
  REVIEW_HISTORY_ACTION_STATES,
  REVIEW_HISTORY_ACTION_TARGETS,
  REVIEW_HISTORY_BLOCKING_LEVELS,
  REVIEW_HISTORY_DECISIONS,
  REVIEW_HISTORY_DETERMINATION_MODES,
  REVIEW_HISTORY_GAP_TYPES,
  REVIEW_HISTORY_RULE_KINDS,
  REVIEW_HISTORY_RUN_STATUSES,
  REVIEW_HISTORY_STAGES,
  type ReviewHistoryActionState,
  type ReviewHistoryActionTarget,
  type ReviewHistoryActionTransitionView,
  type ReviewHistoryActionView,
  type ReviewHistoryAssessmentView,
  type ReviewHistoryBlockingLevel,
  type ReviewHistoryClauseIdentityView,
  type ReviewHistoryContextView,
  type ReviewHistoryConditionView,
  type ReviewHistoryDecision,
  type ReviewHistoryDeterminationMode,
  type ReviewHistoryGapType,
  type ReviewHistoryRuleKind,
  type ReviewHistoryRunDetailView,
  type ReviewHistoryRunListView,
  type ReviewHistoryRunStatus,
  type ReviewHistoryRunSummaryView,
  type ReviewHistoryStage,
} from "./reviewHistoryTypes";

export interface ReviewHistoryHttpOptions {
  fetchImpl?: typeof fetch;
}

export interface ReviewHistoryRequestOptions {
  signal?: AbortSignal;
}

/** 正式审核历史只读仓储；页面通过 ``useLoad`` 直接消费返回的视图。 */
export interface ReviewHistoryRepository {
  listRuns(
    subjectId: string,
    reviewEpisodeId: string,
    options?: ReviewHistoryRequestOptions,
  ): Promise<ReviewHistoryRunListView>;
  getRun(
    subjectId: string,
    reviewEpisodeId: string,
    reviewRunId: string,
    options?: ReviewHistoryRequestOptions,
  ): Promise<ReviewHistoryRunDetailView>;
}

/** 结构不可信（缺字段、未知字段、未知枚举值、冻结记录自相矛盾）时拒绝展示。 */
export class ReviewHistoryDecodeError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ReviewHistoryDecodeError";
  }
}

type ObjectValue = Record<string, unknown>;

function objectValue(value: unknown, path: string): ObjectValue {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new ReviewHistoryDecodeError(`${path} 不是对象`);
  }
  return value as ObjectValue;
}

function field(source: ObjectValue, key: string, path: string): unknown {
  if (!Object.prototype.hasOwnProperty.call(source, key)) {
    throw new ReviewHistoryDecodeError(`${path}.${key} 缺失`);
  }
  return source[key];
}

/** 与后端 DTO 的 ``extra="forbid"`` 对齐：多出字段说明读到了不认识的合同版本。 */
function exactKeys(source: ObjectValue, allowed: readonly string[], path: string): void {
  const unknown = Object.keys(source).filter((key) => !allowed.includes(key));
  if (unknown.length > 0) {
    throw new ReviewHistoryDecodeError(`${path} 含未知字段：${unknown.join("、")}`);
  }
}

function requiredString(value: unknown, path: string): string {
  if (typeof value !== "string" || value.length === 0) {
    throw new ReviewHistoryDecodeError(`${path} 必须是非空文字`);
  }
  return value;
}

function nullableString(value: unknown, path: string): string | null {
  if (value === null) return null;
  return requiredString(value, path);
}

function positiveInteger(value: unknown, path: string): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 1) {
    throw new ReviewHistoryDecodeError(`${path} 必须是正整数`);
  }
  return value;
}

function nonNegativeInteger(value: unknown, path: string): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 0) {
    throw new ReviewHistoryDecodeError(`${path} 必须是非负整数`);
  }
  return value;
}

function arrayValue(value: unknown, path: string): unknown[] {
  if (!Array.isArray(value)) {
    throw new ReviewHistoryDecodeError(`${path} 必须是数组`);
  }
  return value;
}

function enumValue<T extends string>(
  value: unknown,
  values: readonly T[],
  path: string,
): T {
  if (typeof value !== "string" || !values.includes(value as T)) {
    throw new ReviewHistoryDecodeError(`${path} 包含未知值`);
  }
  return value as T;
}

/** 标识符数组：逐项非空（合同不禁止重复的数组不在此处强制去重）。 */
function stringArray(value: unknown, path: string): string[] {
  return arrayValue(value, path).map((item, index) =>
    requiredString(item, `${path}[${index}]`),
  );
}

/** 原件定位数组：review/v2 合同要求非空且不重复。 */
function uniqueStringArray(value: unknown, path: string): string[] {
  const items = stringArray(value, path);
  if (new Set(items).size !== items.length) {
    throw new ReviewHistoryDecodeError(`${path} 存在重复项`);
  }
  return items;
}

function sha256Hex(value: unknown, path: string): string {
  const text = requiredString(value, path);
  if (!/^[0-9a-f]{64}$/.test(text)) {
    throw new ReviewHistoryDecodeError(`${path} 必须是 sha256 十六进制摘要`);
  }
  return text;
}

/** 审核时间戳必须带时区，避免把无时区时间当成浏览器本地时间解释。 */
const ZONED_ISO_DATE_TIME =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/;
/** 状态转换时间只要求形态合法（合同未强制其时区）。 */
const ISO_DATE_TIME =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?$/;

function zonedTimestamp(value: unknown, path: string): string {
  const text = requiredString(value, path);
  if (!ZONED_ISO_DATE_TIME.test(text) || !Number.isFinite(Date.parse(text))) {
    throw new ReviewHistoryDecodeError(`${path} 必须是带时区的 ISO-8601 时间`);
  }
  return text;
}

function isoTimestamp(value: unknown, path: string): string {
  const text = requiredString(value, path);
  if (!ISO_DATE_TIME.test(text) || !Number.isFinite(Date.parse(text))) {
    throw new ReviewHistoryDecodeError(`${path} 必须是 ISO-8601 时间`);
  }
  return text;
}

/** 仅用于已校验时间戳的比较；不做隐式临床日期解析。 */
function timestampMillis(text: string): number {
  return Date.parse(text);
}

const CLAUSE_KEYS = [
  "rule_component_id",
  "rule_code",
  "rule_display_code",
  "rule_title",
  "rule_kind",
  "determination_mode",
] as const;

const RUN_SUMMARY_KEYS = [
  "review_run_id",
  "status",
  "stage",
  "workflow_stage_id",
  "episode_revision",
  "protocol_version_id",
  "rule_set_id",
  "rule_set_revision",
  "evidence_snapshot_v2_id",
  "complete_processing_revision_id",
  "context_id",
  "started_at",
  "completed_at",
  "supersedes_review_run_id",
] as const;

const CONTEXT_KEYS = [
  "context_id",
  "review_run_id",
  "created_at",
  "evaluator_version",
  "project_id",
  "subject_id",
  "review_episode_id",
  "episode_revision",
  "protocol_version_id",
  "rule_set_id",
  "rule_set_revision",
  "evidence_snapshot_v2_id",
  "complete_processing_revision_id",
  "stage",
  "workflow_stage_id",
  "rule_set_sha256",
  "clause_pack_sha256",
  "protocol_integrity_gate_result_id",
  "fact_count",
  "expectation_count",
  "conflict_group_count",
  "judgment_search_count",
  "subject_code", "project_name", "center_code", "center_name",
  "official_protocol_version", "workflow_stage_label",
] as const;

const ASSESSMENT_KEYS = [
  "assessment_id",
  "clause",
  "decision",
  "gap_types",
  "blocking_level",
  "used_fact_ids",
  "locator_ids",
  "gate_result_id",
  "publication_fingerprint",
  "conditions",
] as const;

const TRANSITION_KEYS = [
  "transition_id",
  "from_state",
  "to_state",
  "occurred_at",
  "reason",
  "locator_ids",
  "response_evidence",
] as const;

const ACTION_KEYS = [
  "action_id",
  "assessment_id",
  "clause",
  "control",
  "gap_type",
  "target_party",
  "requested_action",
  "acceptable_evidence",
  "due_stage",
  "blocking_level",
  "state",
  "recompute_scope",
  "trigger_locator_id",
  "record_revision",
  "gate_result_id",
  "publication_fingerprint",
  "transitions",
] as const;

function decodeClause(value: unknown, path: string): ReviewHistoryClauseIdentityView {
  const row = objectValue(value, path);
  exactKeys(row, CLAUSE_KEYS, path);
  const ruleCode = requiredString(field(row, "rule_code", path), `${path}.rule_code`);
  if (!/^(IN|EX|REQ)-\d{2}$/.test(ruleCode)) {
    throw new ReviewHistoryDecodeError(`${path}.rule_code 格式不正确`);
  }
  return {
    ruleComponentId: requiredString(
      field(row, "rule_component_id", path),
      `${path}.rule_component_id`,
    ),
    ruleCode,
    ruleDisplayCode: requiredString(
      field(row, "rule_display_code", path),
      `${path}.rule_display_code`,
    ),
    ruleTitle: requiredString(field(row, "rule_title", path), `${path}.rule_title`),
    ruleKind: enumValue<ReviewHistoryRuleKind>(
      field(row, "rule_kind", path),
      REVIEW_HISTORY_RULE_KINDS,
      `${path}.rule_kind`,
    ),
    determinationMode: enumValue<ReviewHistoryDeterminationMode>(
      field(row, "determination_mode", path),
      REVIEW_HISTORY_DETERMINATION_MODES,
      `${path}.determination_mode`,
    ),
  };
}

function decodeRunSummary(value: unknown, path: string): ReviewHistoryRunSummaryView {
  const row = objectValue(value, path);
  exactKeys(row, RUN_SUMMARY_KEYS, path);
  const status = enumValue<ReviewHistoryRunStatus>(
    field(row, "status", path),
    REVIEW_HISTORY_RUN_STATUSES,
    `${path}.status`,
  );
  const startedAt = zonedTimestamp(field(row, "started_at", path), `${path}.started_at`);
  const completedAtValue = field(row, "completed_at", path);
  const completedAt =
    completedAtValue === null
      ? null
      : zonedTimestamp(completedAtValue, `${path}.completed_at`);
  // 状态只由持久化完成时间推导（服务端合同）：两者不一致说明记录不可信。
  if ((completedAt !== null) !== (status === "completed")) {
    throw new ReviewHistoryDecodeError(`${path} 的审核状态与完成时间不一致`);
  }
  if (completedAt !== null && timestampMillis(completedAt) < timestampMillis(startedAt)) {
    throw new ReviewHistoryDecodeError(`${path} 的完成时间早于开始时间`);
  }
  const reviewRunId = requiredString(
    field(row, "review_run_id", path),
    `${path}.review_run_id`,
  );
  const supersedesReviewRunId = nullableString(
    field(row, "supersedes_review_run_id", path),
    `${path}.supersedes_review_run_id`,
  );
  if (supersedesReviewRunId !== null && supersedesReviewRunId === reviewRunId) {
    throw new ReviewHistoryDecodeError(`${path}.supersedes_review_run_id 不能指向记录自身`);
  }
  return {
    reviewRunId,
    status,
    stage: enumValue<ReviewHistoryStage>(
      field(row, "stage", path),
      REVIEW_HISTORY_STAGES,
      `${path}.stage`,
    ),
    workflowStageId: nullableString(
      field(row, "workflow_stage_id", path),
      `${path}.workflow_stage_id`,
    ),
    episodeRevision: positiveInteger(
      field(row, "episode_revision", path),
      `${path}.episode_revision`,
    ),
    protocolVersionId: requiredString(
      field(row, "protocol_version_id", path),
      `${path}.protocol_version_id`,
    ),
    ruleSetId: requiredString(field(row, "rule_set_id", path), `${path}.rule_set_id`),
    ruleSetRevision: positiveInteger(
      field(row, "rule_set_revision", path),
      `${path}.rule_set_revision`,
    ),
    evidenceSnapshotV2Id: requiredString(
      field(row, "evidence_snapshot_v2_id", path),
      `${path}.evidence_snapshot_v2_id`,
    ),
    completeProcessingRevisionId: requiredString(
      field(row, "complete_processing_revision_id", path),
      `${path}.complete_processing_revision_id`,
    ),
    contextId: requiredString(field(row, "context_id", path), `${path}.context_id`),
    startedAt,
    completedAt,
    supersedesReviewRunId,
  };
}

function decodeContext(value: unknown, path: string): ReviewHistoryContextView {
  const row = objectValue(value, path);
  exactKeys(row, CONTEXT_KEYS, path);
  return {
    subjectCode: requiredString(field(row, "subject_code", path), `${path}.subject_code`),
    projectName: requiredString(field(row, "project_name", path), `${path}.project_name`),
    centerCode: nullableString(field(row, "center_code", path), `${path}.center_code`),
    centerName: nullableString(field(row, "center_name", path), `${path}.center_name`),
    officialProtocolVersion: requiredString(field(row, "official_protocol_version", path), `${path}.official_protocol_version`),
    workflowStageLabel: requiredString(field(row, "workflow_stage_label", path), `${path}.workflow_stage_label`),
    contextId: requiredString(field(row, "context_id", path), `${path}.context_id`),
    reviewRunId: requiredString(
      field(row, "review_run_id", path),
      `${path}.review_run_id`,
    ),
    createdAt: zonedTimestamp(field(row, "created_at", path), `${path}.created_at`),
    evaluatorVersion: requiredString(
      field(row, "evaluator_version", path),
      `${path}.evaluator_version`,
    ),
    projectId: requiredString(field(row, "project_id", path), `${path}.project_id`),
    subjectId: requiredString(field(row, "subject_id", path), `${path}.subject_id`),
    reviewEpisodeId: requiredString(
      field(row, "review_episode_id", path),
      `${path}.review_episode_id`,
    ),
    episodeRevision: positiveInteger(
      field(row, "episode_revision", path),
      `${path}.episode_revision`,
    ),
    protocolVersionId: requiredString(
      field(row, "protocol_version_id", path),
      `${path}.protocol_version_id`,
    ),
    ruleSetId: requiredString(field(row, "rule_set_id", path), `${path}.rule_set_id`),
    ruleSetRevision: positiveInteger(
      field(row, "rule_set_revision", path),
      `${path}.rule_set_revision`,
    ),
    evidenceSnapshotV2Id: requiredString(
      field(row, "evidence_snapshot_v2_id", path),
      `${path}.evidence_snapshot_v2_id`,
    ),
    completeProcessingRevisionId: requiredString(
      field(row, "complete_processing_revision_id", path),
      `${path}.complete_processing_revision_id`,
    ),
    stage: enumValue<ReviewHistoryStage>(
      field(row, "stage", path),
      REVIEW_HISTORY_STAGES,
      `${path}.stage`,
    ),
    workflowStageId: nullableString(
      field(row, "workflow_stage_id", path),
      `${path}.workflow_stage_id`,
    ),
    ruleSetSha256: sha256Hex(field(row, "rule_set_sha256", path), `${path}.rule_set_sha256`),
    clausePackSha256: sha256Hex(
      field(row, "clause_pack_sha256", path),
      `${path}.clause_pack_sha256`,
    ),
    protocolIntegrityGateResultId: requiredString(
      field(row, "protocol_integrity_gate_result_id", path),
      `${path}.protocol_integrity_gate_result_id`,
    ),
    factCount: nonNegativeInteger(field(row, "fact_count", path), `${path}.fact_count`),
    expectationCount: nonNegativeInteger(
      field(row, "expectation_count", path),
      `${path}.expectation_count`,
    ),
    conflictGroupCount: nonNegativeInteger(
      field(row, "conflict_group_count", path),
      `${path}.conflict_group_count`,
    ),
    judgmentSearchCount: nonNegativeInteger(
      field(row, "judgment_search_count", path),
      `${path}.judgment_search_count`,
    ),
  };
}

function decodeUnselected(value: unknown, path: string) {
  const item = objectValue(value, path);
  exactKeys(item, ["fact_id", "locator_ids", "reason"], path);
  return {
    factId: requiredString(field(item, "fact_id", path), path),
    locatorIds: uniqueStringArray(field(item, "locator_ids", path), path),
    reason: requiredString(field(item, "reason", path), path),
  };
}

function decodeCondition(value: unknown, path: string): ReviewHistoryConditionView {
  const row = objectValue(value, path);
  exactKeys(row, ["predicate_id", "condition_text", "truth", "observed_value", "observed_unit", "fact_ids", "locator_ids", "reason_codes", "selection_note", "not_selected", "unverified_evidence", "calculation_basis"], path);
  const observedValue = field(row, "observed_value", path);
  if (observedValue !== null && typeof observedValue !== "string" && typeof observedValue !== "boolean"
      && !(typeof observedValue === "number" && Number.isFinite(observedValue))) {
    throw new ReviewHistoryDecodeError("条件记录中的值无法读取");
  }
  return {
    predicateId: requiredString(field(row, "predicate_id", path), path),
    conditionText: nullableString(field(row, "condition_text", path), path),
    truth: enumValue(field(row, "truth", path), ["true", "false", "unknown"] as const, path),
    observedValue, observedUnit: nullableString(field(row, "observed_unit", path), path),
    factIds: stringArray(field(row, "fact_ids", path), path),
    locatorIds: uniqueStringArray(field(row, "locator_ids", path), path),
    reasonCodes: stringArray(field(row, "reason_codes", path), path),
    selectionNote: nullableString(field(row, "selection_note", path), path),
    calculationBasis: stringArray(field(row, "calculation_basis", path), path),
    notSelected: arrayValue(field(row, "not_selected", path), path).map((value, index) =>
      decodeUnselected(value, `${path}.not_selected[${index}]`)),
    unverifiedEvidence: arrayValue(field(row, "unverified_evidence", path), path).map((value) => decodeUnverified(value, path)),
  };
}

function decodeUnverified(value: unknown, path: string) {
  const gap = objectValue(value, path);
  exactKeys(gap, ["locator_id", "reason_codes"], path);
  const reasonCodes = uniqueStringArray(field(gap, "reason_codes", path), path);
  if (reasonCodes.length === 0) throw new ReviewHistoryDecodeError("原文疑问缺少具体原因。");
  return { locatorId: requiredString(field(gap, "locator_id", path), path), reasonCodes };
}

function decodeAssessment(value: unknown, path: string): ReviewHistoryAssessmentView {
  const row = objectValue(value, path);
  exactKeys(row, ASSESSMENT_KEYS, path);
  const conditions = arrayValue(field(row, "conditions", path), path).map((item, index) => decodeCondition(item, `${path}.conditions[${index}]`));
  if (conditions.length === 0 || new Set(conditions.map((item) => item.predicateId)).size !== conditions.length) {
    throw new ReviewHistoryDecodeError("审核条件记录不完整或重复");
  }
  const gapTypes = arrayValue(field(row, "gap_types", path), `${path}.gap_types`).map(
    (item, index) =>
      enumValue<ReviewHistoryGapType>(
        item,
        REVIEW_HISTORY_GAP_TYPES,
        `${path}.gap_types[${index}]`,
      ),
  );
  return {
    conditions,
    assessmentId: requiredString(
      field(row, "assessment_id", path),
      `${path}.assessment_id`,
    ),
    clause: decodeClause(field(row, "clause", path), `${path}.clause`),
    decision: enumValue<ReviewHistoryDecision>(
      field(row, "decision", path),
      REVIEW_HISTORY_DECISIONS,
      `${path}.decision`,
    ),
    gapTypes,
    blockingLevel: enumValue<ReviewHistoryBlockingLevel>(
      field(row, "blocking_level", path),
      REVIEW_HISTORY_BLOCKING_LEVELS,
      `${path}.blocking_level`,
    ),
    usedFactIds: stringArray(field(row, "used_fact_ids", path), `${path}.used_fact_ids`),
    locatorIds: uniqueStringArray(field(row, "locator_ids", path), `${path}.locator_ids`),
    gateResultId: requiredString(field(row, "gate_result_id", path), `${path}.gate_result_id`),
    publicationFingerprint: sha256Hex(
      field(row, "publication_fingerprint", path),
      `${path}.publication_fingerprint`,
    ),
  };
}

function decodeTransition(
  value: unknown,
  path: string,
): ReviewHistoryActionTransitionView {
  const row = objectValue(value, path);
  exactKeys(row, TRANSITION_KEYS, path);
  const locatorIds = uniqueStringArray(field(row, "locator_ids", path), `${path}.locator_ids`);
  const response = field(row, "response_evidence", path);
  let responseEvidence: ReviewHistoryActionTransitionView["responseEvidence"] = null;
  if (response !== null) {
    const source = objectValue(response, `${path}.response_evidence`);
    exactKeys(source, ["project_id", "subject_id", "review_episode_id", "evidence_snapshot_v2_id", "complete_processing_revision_id", "locators"], path);
    responseEvidence = {
      projectId: requiredString(field(source, "project_id", path), path),
      subjectId: requiredString(field(source, "subject_id", path), path),
      reviewEpisodeId: requiredString(field(source, "review_episode_id", path), path),
      evidenceSnapshotV2Id: requiredString(field(source, "evidence_snapshot_v2_id", path), path),
      completeProcessingRevisionId: requiredString(field(source, "complete_processing_revision_id", path), path),
      locators: arrayValue(field(source, "locators", path), path).map((item, index) => decodeEvidenceLocator(item, index, path)),
    };
    const ids = responseEvidence.locators.map((item) => item.locatorId);
    if (new Set(ids).size !== ids.length || ids.length !== locatorIds.length || ids.some((id) => !locatorIds.includes(id))) {
      throw new ReviewHistoryDecodeError("办理记录与回应原件不一致。");
    }
  }
  if ((locatorIds.length > 0) !== (responseEvidence !== null)) {
    throw new ReviewHistoryDecodeError("办理原件缺少所属资料版本。");
  }
  return {
    transitionId: requiredString(
      field(row, "transition_id", path),
      `${path}.transition_id`,
    ),
    fromState: enumValue<ReviewHistoryActionState>(
      field(row, "from_state", path),
      REVIEW_HISTORY_ACTION_STATES,
      `${path}.from_state`,
    ),
    toState: enumValue<ReviewHistoryActionState>(
      field(row, "to_state", path),
      REVIEW_HISTORY_ACTION_STATES,
      `${path}.to_state`,
    ),
    occurredAt: isoTimestamp(field(row, "occurred_at", path), `${path}.occurred_at`),
    reason: requiredString(field(row, "reason", path), `${path}.reason`),
    locatorIds,
    responseEvidence,
  };
}

export function decodeAction(value: unknown, path: string): ReviewHistoryActionView {
  const row = objectValue(value, path);
  exactKeys(row, ACTION_KEYS, path);
  const rawControl = field(row, "control", path);
  let control: ReviewHistoryActionView["control"] = null;
  if (rawControl !== null) {
    const source = objectValue(rawControl, `${path}.control`);
    exactKeys(source, ["protocol_control_id", "obligation_id", "obligation_group_id", "display_label", "title"], `${path}.control`);
    control = {
      protocolControlId: requiredString(field(source, "protocol_control_id", path), path),
      obligationId: nullableString(field(source, "obligation_id", path), path),
      obligationGroupId: nullableString(field(source, "obligation_group_id", path), path),
      displayLabel: requiredString(field(source, "display_label", path), path),
      title: requiredString(field(source, "title", path), path),
    };
    if ((control.obligationId === null) === (control.obligationGroupId === null)) {
      throw new ReviewHistoryDecodeError("补充要求办理事项未明确对应范围。");
    }
  }
  const assessmentId = nullableString(field(row, "assessment_id", path), `${path}.assessment_id`);
  const clause = field(row, "clause", path) === null ? null : decodeClause(field(row, "clause", path), `${path}.clause`);
  if (control === null ? assessmentId === null || clause === null : assessmentId !== null || clause !== null) {
    throw new ReviewHistoryDecodeError("办理事项的方案要求归属不明确。");
  }
  const transitions = arrayValue(field(row, "transitions", path), `${path}.transitions`).map(
    (item, index) => decodeTransition(item, `${path}.transitions[${index}]`),
  );
  const transitionIds = transitions.map((item) => item.transitionId);
  if (new Set(transitionIds).size !== transitionIds.length) {
    throw new ReviewHistoryDecodeError(`${path}.transitions 存在重复的转换记录`);
  }
  const state = enumValue<ReviewHistoryActionState>(
    field(row, "state", path),
    REVIEW_HISTORY_ACTION_STATES,
    `${path}.state`,
  );
  // 合同不变量：系统自动关闭必须保留状态转换记录。
  if (
    state === "closed_system" &&
    !transitions.some((item) => item.toState === "closed_system")
  ) {
    throw new ReviewHistoryDecodeError(`${path} 的系统自动关闭缺少状态转换记录`);
  }
  // 当前状态只能由最后一次转换产生；否则页面会把矛盾的当前态当成事实展示。
  if (transitions.length > 0 && transitions[transitions.length - 1].toState !== state) {
    throw new ReviewHistoryDecodeError(`${path} 的当前状态与最后一次状态转换不一致`);
  }
  const recomputeScope = stringArray(
    field(row, "recompute_scope", path),
    `${path}.recompute_scope`,
  );
  if (recomputeScope.length === 0) {
    throw new ReviewHistoryDecodeError(`${path}.recompute_scope 不能为空`);
  }
  return {
    actionId: requiredString(field(row, "action_id", path), `${path}.action_id`),
    assessmentId, clause, control,
    gapType: enumValue<ReviewHistoryGapType>(
      field(row, "gap_type", path),
      REVIEW_HISTORY_GAP_TYPES,
      `${path}.gap_type`,
    ),
    targetParty: enumValue<ReviewHistoryActionTarget>(
      field(row, "target_party", path),
      REVIEW_HISTORY_ACTION_TARGETS,
      `${path}.target_party`,
    ),
    requestedAction: requiredString(
      field(row, "requested_action", path),
      `${path}.requested_action`,
    ),
    acceptableEvidence: requiredString(
      field(row, "acceptable_evidence", path),
      `${path}.acceptable_evidence`,
    ),
    dueStage: enumValue<ReviewHistoryStage>(
      field(row, "due_stage", path),
      REVIEW_HISTORY_STAGES,
      `${path}.due_stage`,
    ),
    blockingLevel: enumValue<ReviewHistoryBlockingLevel>(
      field(row, "blocking_level", path),
      REVIEW_HISTORY_BLOCKING_LEVELS,
      `${path}.blocking_level`,
    ),
    state,
    recomputeScope,
    triggerLocatorId: nullableString(
      field(row, "trigger_locator_id", path),
      `${path}.trigger_locator_id`,
    ),
    recordRevision: positiveInteger(
      field(row, "record_revision", path),
      `${path}.record_revision`,
    ),
    gateResultId: requiredString(field(row, "gate_result_id", path), `${path}.gate_result_id`),
    publicationFingerprint: sha256Hex(
      field(row, "publication_fingerprint", path),
      `${path}.publication_fingerprint`,
    ),
    transitions,
  };
}

function requireSameBinding(label: string, left: unknown, right: unknown): void {
  if (left !== right) {
    throw new ReviewHistoryDecodeError(
      `冻结输入与本次审核的 ${label} 不一致，请重新读取审核历史。`,
    );
  }
}

export function decodeReviewHistoryRunList(value: unknown): ReviewHistoryRunListView {
  const row = objectValue(value, "review_runs");
  exactKeys(row, ["subject_id", "review_episode_id", "items"], "review_runs");
  const items = arrayValue(field(row, "items", "review_runs"), "review_runs.items").map(
    (item, index) => decodeRunSummary(item, `review_runs.items[${index}]`),
  );
  const runIds = items.map((item) => item.reviewRunId);
  if (new Set(runIds).size !== runIds.length) {
    throw new ReviewHistoryDecodeError("审核记录重复，请重新读取审核历史。");
  }
  const contextIds = items.map((item) => item.contextId);
  if (new Set(contextIds).size !== contextIds.length) {
    throw new ReviewHistoryDecodeError("审核记录绑定的冻结输入重复，请重新读取审核历史。");
  }
  return {
    subjectId: requiredString(field(row, "subject_id", "review_runs"), "review_runs.subject_id"),
    reviewEpisodeId: requiredString(
      field(row, "review_episode_id", "review_runs"),
      "review_runs.review_episode_id",
    ),
    items,
  };
}

export function decodeReviewHistoryRunDetail(value: unknown): ReviewHistoryRunDetailView {
  const row = objectValue(value, "review_history");
  exactKeys(
    row,
    ["run", "context", "assessments", "actions", "missing_rule_component_ids", "evidence_locators", "controls", "missing_protocol_control_ids", "control_selection_records"],
    "review_history",
  );
  const run = decodeRunSummary(field(row, "run", "review_history"), "review_history.run");
  const context = decodeContext(field(row, "context", "review_history"), "review_history.context");

  // 冻结输入与运行必须互相绑定：两者由服务端同一快照派生，不一致即记录已损坏。
  requireSameBinding("context_id", context.contextId, run.contextId);
  requireSameBinding("review_run_id", context.reviewRunId, run.reviewRunId);
  requireSameBinding("阶段", context.stage, run.stage);
  requireSameBinding("流程节点", context.workflowStageId, run.workflowStageId);
  requireSameBinding("审核节点修订", context.episodeRevision, run.episodeRevision);
  requireSameBinding("方案版本", context.protocolVersionId, run.protocolVersionId);
  requireSameBinding("规则集", context.ruleSetId, run.ruleSetId);
  requireSameBinding("规则修订", context.ruleSetRevision, run.ruleSetRevision);
  requireSameBinding("证据快照", context.evidenceSnapshotV2Id, run.evidenceSnapshotV2Id);
  requireSameBinding(
    "完整处理修订",
    context.completeProcessingRevisionId,
    run.completeProcessingRevisionId,
  );

  const assessments = arrayValue(
    field(row, "assessments", "review_history"),
    "review_history.assessments",
  ).map((item, index) => decodeAssessment(item, `review_history.assessments[${index}]`));
  const assessmentIds = assessments.map((item) => item.assessmentId);
  if (new Set(assessmentIds).size !== assessmentIds.length) {
    throw new ReviewHistoryDecodeError("冻结结论重复，请重新读取审核历史。");
  }
  const componentIds = assessments.map((item) => item.clause.ruleComponentId);
  if (new Set(componentIds).size !== componentIds.length) {
    throw new ReviewHistoryDecodeError("同一次审核出现重复的审核要点结论。");
  }
  const assessmentById = new Map(assessments.map((item) => [item.assessmentId, item]));

  const actions = arrayValue(field(row, "actions", "review_history"), "review_history.actions").map(
    (item, index) => decodeAction(item, `review_history.actions[${index}]`),
  );
  const actionIds = actions.map((item) => item.actionId);
  if (new Set(actionIds).size !== actionIds.length) {
    throw new ReviewHistoryDecodeError("待办记录重复，请重新读取审核历史。");
  }
  actions.forEach((action, index) => {
    for (const transition of action.transitions) {
      const source = transition.responseEvidence;
      if (source !== null && (source.projectId !== context.projectId || source.subjectId !== context.subjectId
          || source.reviewEpisodeId !== context.reviewEpisodeId)) {
        throw new ReviewHistoryDecodeError("回应原件不属于本受试者的审核节点。");
      }
    }
    if (action.control !== null) return;
    const referenced = action.assessmentId === null ? undefined : assessmentById.get(action.assessmentId);
    if (referenced === undefined) {
      throw new ReviewHistoryDecodeError(
        `review_history.actions[${index}] 引用的冻结结论不属于本次审核。`,
      );
    }
    if (referenced.clause.ruleComponentId !== action.clause?.ruleComponentId) {
      throw new ReviewHistoryDecodeError(
        `review_history.actions[${index}] 的审核要点与所引用结论不一致。`,
      );
    }
  });

  const missingRuleComponentIds = uniqueStringArray(
    field(row, "missing_rule_component_ids", "review_history"),
    "review_history.missing_rule_component_ids",
  );
  const assessedComponents = new Set(componentIds);
  if (missingRuleComponentIds.some((item) => assessedComponents.has(item))) {
    throw new ReviewHistoryDecodeError("未完成的审核要点与已存储结论冲突，请重新读取审核历史。");
  }
  if (run.status === "completed" && missingRuleComponentIds.length > 0) {
    throw new ReviewHistoryDecodeError("已完成的审核缺少冻结结论，系统不会展示不完整报告。");
  }

  const controls = arrayValue(field(row, "controls", "review_history"), "review_history.controls").map((value, index) => {
    const path = `review_history.controls[${index}]`;
    const item = objectValue(value, path);
    exactKeys(item, ["protocol_control_id", "display_label", "title", "modality", "obligation_id", "obligation_group_id", "activation", "observation_truth", "statement", "status", "protocol_excerpts", "locator_ids", "reason_codes", "unverified_evidence", "calculation_basis"], path);
    return {
      protocolControlId: requiredString(field(item, "protocol_control_id", path), path),
      displayLabel: requiredString(field(item, "display_label", path), path),
      title: requiredString(field(item, "title", path), path),
      modality: enumValue(field(item, "modality", path), ["mandatory", "recommended", "best_effort"] as const, path),
      obligationId: requiredString(field(item, "obligation_id", path), path),
      obligationGroupId: requiredString(field(item, "obligation_group_id", path), path),
      activation: enumValue(field(item, "activation", path), ["true", "false", "unknown"] as const, path),
      observationTruth: enumValue(field(item, "observation_truth", path), ["true", "false", "unknown"] as const, path),
      statement: requiredString(field(item, "statement", path), path),
      status: enumValue(field(item, "status", path), ["fulfilled", "unfulfilled", "unverified", "not_applicable"] as const, path),
      protocolExcerpts: arrayValue(field(item, "protocol_excerpts", path), path).map((text) => text === null ? null : requiredString(text, path)),
      calculationBasis: stringArray(field(item, "calculation_basis", path), path),
      locatorIds: uniqueStringArray(field(item, "locator_ids", path), path),
      reasonCodes: uniqueStringArray(field(item, "reason_codes", path), path),
      unverifiedEvidence: arrayValue(field(item, "unverified_evidence", path), path).map((value) => decodeUnverified(value, path)),
    };
  });
  const controlKeys = controls.map((item) => JSON.stringify([item.protocolControlId, item.obligationId]));
  const groupActivations = new Map<string, string>();
  for (const item of controls) {
    const expectedStatus = item.activation === "false" ? "not_applicable"
      : item.activation === "unknown" || item.observationTruth === "unknown" ? "unverified"
      : item.observationTruth === "true" ? "fulfilled" : "unfulfilled";
    const groupKey = JSON.stringify([item.protocolControlId, item.obligationGroupId]);
    const priorActivation = groupActivations.get(groupKey);
    if (item.status !== expectedStatus || (priorActivation !== undefined && priorActivation !== item.activation)) {
      throw new ReviewHistoryDecodeError("补充要求与保存的适用条件不一致，暂不能展示报告。");
    }
    groupActivations.set(groupKey, item.activation);
  }
  for (const action of actions) {
    if (action.control !== null && action.gapType !== "observation_unverified") {
      throw new ReviewHistoryDecodeError("补充要求的办理原因与本次保存依据不一致。");
    }
    if (action.control !== null && !controls.some((item) => item.protocolControlId === action.control?.protocolControlId
        && (action.control.obligationId !== null ? item.obligationId === action.control.obligationId
          : item.obligationGroupId === action.control.obligationGroupId))) {
      throw new ReviewHistoryDecodeError("办理事项未对应本次保存的补充要求。");
    }
  }
  const expectedControlActions = new Set(controls.filter((item) => item.status === "unverified")
    .map((item) => JSON.stringify([item.protocolControlId,
      item.activation === "unknown" ? null : item.obligationId,
      item.activation === "unknown" ? item.obligationGroupId : null])));
  const storedControlActions = actions.flatMap((item) => item.control === null ? [] : [
    JSON.stringify([item.control.protocolControlId, item.control.obligationId, item.control.obligationGroupId]),
  ]);
  if (new Set(storedControlActions).size !== storedControlActions.length
      || storedControlActions.some((id) => !expectedControlActions.has(id))
      || (run.status === "completed" && storedControlActions.length !== expectedControlActions.size)) {
    throw new ReviewHistoryDecodeError("补充要求的待核实事项未完整保存。");
  }
  const missingProtocolControlIds = uniqueStringArray(field(row, "missing_protocol_control_ids", "review_history"), "review_history.missing_protocol_control_ids");
  if (new Set(controlKeys).size !== controls.length
      || controls.some((item) => missingProtocolControlIds.includes(item.protocolControlId))
      || (run.status === "completed" && missingProtocolControlIds.length > 0)) {
    throw new ReviewHistoryDecodeError("跨章节要求的审核记录重复或不完整，暂不能展示报告。");
  }
  const evidenceLocators = arrayValue(field(row, "evidence_locators", "review_history"), "review_history.evidence_locators")
    .map((item, index) => decodeEvidenceLocator(item, index, "review_history.evidence_locators"));
  const locatorIds = new Set(evidenceLocators.map((item) => item.locatorId));
  const referencedIds = new Set([...assessments.flatMap((item) => item.locatorIds), ...controls.flatMap((item) => item.locatorIds),
    ...controls.flatMap((item) => item.unverifiedEvidence.map((gap) => gap.locatorId)),
    ...assessments.flatMap((item) => item.conditions.flatMap((condition) => condition.unverifiedEvidence.map((gap) => gap.locatorId))),
    ...assessments.flatMap((item) => item.conditions.flatMap((condition) => condition.notSelected.flatMap((record) => record.locatorIds)))]);
  for (const assessment of assessments) {
    const factIds = new Set(assessment.usedFactIds);
    const assessmentLocators = new Set(assessment.locatorIds);
    if (assessment.conditions.some((condition) => condition.factIds.some((id) => !factIds.has(id))
        || condition.locatorIds.some((id) => !assessmentLocators.has(id))
        || new Set(condition.notSelected.map((item) => item.factId)).size !== condition.notSelected.length
        || condition.notSelected.some((item) => condition.factIds.includes(item.factId)))) {
      throw new ReviewHistoryDecodeError("条件核对与本条审核的原件出处不一致。");
    }
  }
  const controlSelectionRecords = arrayValue(field(row, "control_selection_records", "review_history"), "control_selection_records").map((value, index) => {
    const path = `control_selection_records[${index}]`;
    const item = objectValue(value, path);
    exactKeys(item, ["identity", "protocol_control_id", "display_label", "condition_role", "condition_text", "selection_note", "not_selected"], path);
    return {
      identity: requiredString(field(item, "identity", path), path),
      protocolControlId: requiredString(field(item, "protocol_control_id", path), path),
      displayLabel: requiredString(field(item, "display_label", path), path),
      conditionRole: requiredString(field(item, "condition_role", path), path),
      conditionText: requiredString(field(item, "condition_text", path), path),
      selectionNote: requiredString(field(item, "selection_note", path), path),
      notSelected: arrayValue(field(item, "not_selected", path), path).map((record, i) => decodeUnselected(record, `${path}.not_selected[${i}]`)),
    };
  });
  for (const item of controlSelectionRecords) {
    for (const record of item.notSelected) for (const id of record.locatorIds) referencedIds.add(id);
  }
  if (locatorIds.size !== evidenceLocators.length || locatorIds.size !== referencedIds.size
      || [...referencedIds].some((id) => !locatorIds.has(id))) {
    throw new ReviewHistoryDecodeError("审核结果与保存的原件出处不一致，暂不能展示报告。");
  }
  if (new Set(controlSelectionRecords.map((item) => item.identity)).size !== controlSelectionRecords.length
      || controlSelectionRecords.some((item) => !controls.some((control) => control.protocolControlId === item.protocolControlId)
        || item.notSelected.some((record) => record.locatorIds.some((id) => !evidenceLocators.some((locator) => locator.locatorId === id))))) {
    throw new ReviewHistoryDecodeError("检查选择记录与本次报告的要求或原件不一致");
  }
  return { run, context, assessments, actions, missingRuleComponentIds, evidenceLocators, controls, missingProtocolControlIds, controlSelectionRecords };
}

function reviewRunsPath(subjectId: string, reviewEpisodeId: string): string {
  return `/api/v2/subjects/${encodeURIComponent(subjectId)}/review-episodes/${encodeURIComponent(reviewEpisodeId)}/review-runs`;
}

function reviewHistoryUrl(path: string): string {
  const base = getProtocolApiBase();
  return base.length > 0 ? `${base}${path}` : path;
}

async function readJson(response: Response): Promise<unknown> {
  const text = await response.text();
  if (text.length === 0) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return null;
  }
}

async function fetchJson(
  fetchImpl: typeof fetch,
  url: string,
  options: ReviewHistoryRequestOptions | undefined,
): Promise<unknown> {
  const response = await fetchImpl(url, { method: "GET", signal: options?.signal });
  const payload = await readJson(response);
  if (!response.ok) {
    // 复用既有应用错误类型与信封解码：useLoad 已按 EligibilityReviewApiError 显示中文恢复文案。
    throw decodeEligibilityReviewError(payload, response.status);
  }
  if (payload === null || typeof payload !== "object" || Array.isArray(payload)) {
    throw decodeEligibilityReviewError(payload, response.status);
  }
  return payload;
}

/** 只读正式审核历史 HTTP 适配器；``fetchImpl`` 供测试或本地验收注入。 */
export function createReviewHistoryHttp(
  options: ReviewHistoryHttpOptions = {},
): ReviewHistoryRepository {
  const fetchImpl = options.fetchImpl ?? fetch.bind(globalThis);
  return {
    async listRuns(subjectId, reviewEpisodeId, requestOptions) {
      const payload = await fetchJson(
        fetchImpl,
        reviewHistoryUrl(reviewRunsPath(subjectId, reviewEpisodeId)),
        requestOptions,
      );
      const view = decodeReviewHistoryRunList(payload);
      if (view.subjectId !== subjectId) {
        throw new ReviewHistoryDecodeError("审核历史列表的受试者与请求不一致");
      }
      if (view.reviewEpisodeId !== reviewEpisodeId) {
        throw new ReviewHistoryDecodeError("审核历史列表的审核节点与请求不一致");
      }
      return view;
    },
    async getRun(subjectId, reviewEpisodeId, reviewRunId, requestOptions) {
      const payload = await fetchJson(
        fetchImpl,
        `${reviewHistoryUrl(reviewRunsPath(subjectId, reviewEpisodeId))}/${encodeURIComponent(reviewRunId)}`,
        requestOptions,
      );
      const view = decodeReviewHistoryRunDetail(payload);
      if (view.run.reviewRunId !== reviewRunId) {
        throw new ReviewHistoryDecodeError("审核记录与请求的运行不一致");
      }
      if (view.context.reviewRunId !== reviewRunId) {
        throw new ReviewHistoryDecodeError("冻结输入绑定的运行与请求不一致");
      }
      if (view.context.subjectId !== subjectId) {
        throw new ReviewHistoryDecodeError("冻结输入记录的受试者与请求不一致");
      }
      if (view.context.reviewEpisodeId !== reviewEpisodeId) {
        throw new ReviewHistoryDecodeError("冻结输入记录的审核节点与请求不一致");
      }
      return view;
    },
  };
}

export { EligibilityReviewApiError } from "../eligibility-review";
