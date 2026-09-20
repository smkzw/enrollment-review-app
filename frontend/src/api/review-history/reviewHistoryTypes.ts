/**
 * 正式审核历史（review/v2 冻结记录）只读网络契约的页面视图类型。
 *
 * 对应只读端点（app/api/v2/review_history.py，固定线上合同）：
 * - GET /api/v2/subjects/{subject_id}/review-episodes/{review_episode_id}/review-runs
 * - GET /api/v2/subjects/{subject_id}/review-episodes/{review_episode_id}/review-runs/{review_run_id}
 *
 * 视图只搬运冻结记录已有的身份、判定、待办与时间：审核状态由服务端持久化时间戳推导，
 * 前端不重算判定、不把待办关闭当成规则通过、不补造缺失结论、不读取实时投影。
 * 枚举一律保留服务端 schema 取值，中文显示由页面做穷尽映射。
 */

export const REVIEW_HISTORY_RUN_STATUSES = ["completed", "in_progress"] as const;
export type ReviewHistoryRunStatus = (typeof REVIEW_HISTORY_RUN_STATUSES)[number];

export const REVIEW_HISTORY_STAGES = [
  "pre_screening",
  "screening",
  "run_in",
  "baseline",
] as const;
export type ReviewHistoryStage = (typeof REVIEW_HISTORY_STAGES)[number];

export const REVIEW_HISTORY_RULE_KINDS = [
  "inclusion",
  "exclusion",
  "required_procedure",
] as const;
export type ReviewHistoryRuleKind = (typeof REVIEW_HISTORY_RULE_KINDS)[number];

export const REVIEW_HISTORY_DETERMINATION_MODES = [
  "deterministic",
  "semantic",
  "investigator_judgment",
] as const;
export type ReviewHistoryDeterminationMode =
  (typeof REVIEW_HISTORY_DETERMINATION_MODES)[number];

export const REVIEW_HISTORY_DECISIONS = [
  "inclusion_met",
  "inclusion_not_met",
  "exclusion_not_triggered",
  "exclusion_triggered",
  "indeterminate",
  "professional_judgment",
  "conflict",
  "not_due",
  "not_applicable",
  "requirement_met",
  "requirement_not_met",
] as const;
export type ReviewHistoryDecision = (typeof REVIEW_HISTORY_DECISIONS)[number];

export const REVIEW_HISTORY_GAP_TYPES = [
  "observation_unverified",
  "record_incomplete",
  "description_insufficient",
  "historical_source_unavailable",
  "referenced_file_missing",
  "required_procedure_not_done",
  "result_fields_missing",
  "date_or_anchor_missing",
  "professional_judgment",
  "source_conflict",
  "ocr_or_parse_risk",
  "interpretation_conflict",
  "future_stage_not_due",
  "provenance_followup",
  "control_applicability_pending",] as const;
export type ReviewHistoryGapType = (typeof REVIEW_HISTORY_GAP_TYPES)[number];

export const REVIEW_HISTORY_BLOCKING_LEVELS = ["none", "attention", "blocking"] as const;
export type ReviewHistoryBlockingLevel = (typeof REVIEW_HISTORY_BLOCKING_LEVELS)[number];

export const REVIEW_HISTORY_ACTION_STATES = [
  "open",
  "closed_system",
  "closed_manual",
  "reopened",
  "superseded",
] as const;
export type ReviewHistoryActionState = (typeof REVIEW_HISTORY_ACTION_STATES)[number];

export const REVIEW_HISTORY_ACTION_TARGETS = [
  "investigator",
  "crc",
  "cra",
  "sponsor_medical_or_project",
] as const;
export type ReviewHistoryActionTarget = (typeof REVIEW_HISTORY_ACTION_TARGETS)[number];

/** 冻结条款包中的审核要点身份（官方编号与原文标题原样来自冻结修订）。 */
export interface ReviewHistoryClauseIdentityView {
  ruleComponentId: string;
  ruleCode: string;
  ruleDisplayCode: string;
  ruleTitle: string;
  ruleKind: ReviewHistoryRuleKind;
  determinationMode: ReviewHistoryDeterminationMode;
}

/** 一次正式审核的身份、冻结资料版本与持久化时间；状态只由完成时间推导。 */
export interface ReviewHistoryRunSummaryView {
  reviewRunId: string;
  status: ReviewHistoryRunStatus;
  stage: ReviewHistoryStage;
  workflowStageId: string | null;
  episodeRevision: number;
  protocolVersionId: string;
  ruleSetId: string;
  ruleSetRevision: number;
  evidenceSnapshotV2Id: string;
  completeProcessingRevisionId: string;
  contextId: string;
  /** 带时区的 ISO-8601 时间（合同要求 UTC）；页面按需格式化，不在此处解释时区。 */
  startedAt: string;
  completedAt: string | null;
  supersedesReviewRunId: string | null;
}

/** 冻结输入快照的身份、来源指纹与内容规模；不含重新解释或推导结论。 */
export interface ReviewHistoryContextView {
  contextId: string;
  reviewRunId: string;
  createdAt: string;
  evaluatorVersion: string;
  projectId: string;
  subjectId: string;
  reviewEpisodeId: string;
  episodeRevision: number;
  protocolVersionId: string;
  ruleSetId: string;
  ruleSetRevision: number;
  evidenceSnapshotV2Id: string;
  completeProcessingRevisionId: string;
  stage: ReviewHistoryStage;
  workflowStageId: string | null;
  ruleSetSha256: string;
  clausePackSha256: string;
  protocolIntegrityGateResultId: string;
  factCount: number;
  expectationCount: number;
  conflictGroupCount: number;
  judgmentSearchCount: number;
  subjectCode: string;
  projectName: string;
  centerCode: string | null;
  centerName: string | null;
  officialProtocolVersion: string;
  workflowStageLabel: string;
}

/** 一条已存储的冻结结论：判定原样返回，不在前端重算阻断级别。 */
export interface ReviewHistoryAssessmentView {
  assessmentId: string;
  clause: ReviewHistoryClauseIdentityView;
  decision: ReviewHistoryDecision;
  gapTypes: ReviewHistoryGapType[];
  blockingLevel: ReviewHistoryBlockingLevel;
  usedFactIds: string[];
  locatorIds: string[];
  gateResultId: string;
  publicationFingerprint: string;
  conditions: ReviewHistoryConditionView[];
}

export interface ReviewHistoryConditionView {
  predicateId: string;
  conditionText: string | null;
  truth: "true" | "false" | "unknown";
  observedValue: string | number | boolean | null;
  observedUnit: string | null;
  factIds: string[];
  locatorIds: string[];
  reasonCodes: string[];
  selectionNote: string | null;
  calculationBasis: string[];
  notSelected: { factId: string; locatorIds: string[]; reason: string }[];
  unverifiedEvidence: { locatorId: string; reasonCodes: string[] }[];
}

/** 待办状态转换的冻结历史（关闭待办不等于规则通过）。 */
export interface ReviewHistoryActionTransitionView {
  transitionId: string;
  fromState: ReviewHistoryActionState;
  toState: ReviewHistoryActionState;
  occurredAt: string;
  reason: string;
  locatorIds: string[];
  responseEvidence: ReviewResponseEvidenceView | null;
}

export interface ReviewResponseEvidenceView {
  projectId: string;
  subjectId: string;
  reviewEpisodeId: string;
  evidenceSnapshotV2Id: string;
  completeProcessingRevisionId: string;
  locators: import("../evidence").LocatorView[];
}

/** 一条已存储待办的当前修订与完整转换记录。 */
export interface ReviewHistoryActionView {
  actionId: string;
  assessmentId: string | null;
  clause: ReviewHistoryClauseIdentityView | null;
  control: { protocolControlId: string; obligationId: string | null; obligationGroupId: string | null; displayLabel: string; title: string } | null;
  gapType: ReviewHistoryGapType;
  targetParty: ReviewHistoryActionTarget;
  requestedAction: string;
  acceptableEvidence: string;
  dueStage: ReviewHistoryStage;
  blockingLevel: ReviewHistoryBlockingLevel;
  state: ReviewHistoryActionState;
  recomputeScope: string[];
  triggerLocatorId: string | null;
  recordRevision: number;
  gateResultId: string;
  publicationFingerprint: string;
  transitions: ReviewHistoryActionTransitionView[];
}

/** 审核节点的正式 V2 历史列表；空列表是合法状态。 */
export interface ReviewHistoryRunListView {
  subjectId: string;
  reviewEpisodeId: string;
  items: ReviewHistoryRunSummaryView[];
}

/** 单次正式审核的冻结历史（运行 + 冻结输入 + 结论 + 待办）。 */
export interface ReviewHistoryControlView {
  protocolControlId: string;
  displayLabel: string;
  title: string;
  modality: "mandatory" | "recommended" | "best_effort";
  obligationId: string;
  obligationGroupId: string;
  activation: "true" | "false" | "unknown";
  observationTruth: "true" | "false" | "unknown";
  statement: string;
  status: "fulfilled" | "unfulfilled" | "unverified" | "not_applicable";
  protocolExcerpts: (string | null)[];
  calculationBasis: string[];
  locatorIds: string[];
  reasonCodes: string[];
  unverifiedEvidence: { locatorId: string; reasonCodes: string[] }[];
}

export interface ReviewHistoryRunDetailView {
  controlSelectionRecords: {
    identity: string; protocolControlId: string; displayLabel: string;
    conditionRole: string; conditionText: string; selectionNote: string;
    notSelected: { factId: string; locatorIds: string[]; reason: string }[];
  }[];
  run: ReviewHistoryRunSummaryView;
  context: ReviewHistoryContextView;
  assessments: ReviewHistoryAssessmentView[];
  actions: ReviewHistoryActionView[];
  missingRuleComponentIds: string[];
  evidenceLocators: import("../evidence").LocatorView[];
  controls: ReviewHistoryControlView[];
  missingProtocolControlIds: string[];
}
