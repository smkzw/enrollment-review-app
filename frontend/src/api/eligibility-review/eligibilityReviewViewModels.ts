import type {
  EligibilityClauseWire,
  EligibilityControlStatusWire,
  EligibilityControlWire,
  EligibilityDecisionWire,
  EligibilityDeterminationModeWire,
  EligibilityFactRefWire,
  EligibilityLimitationKindWire,
  EligibilityRuleKindWire,
} from "./eligibilityReviewTypes";

export type EligibilityRuleKind = EligibilityRuleKindWire;
export type EligibilityDecision = EligibilityDecisionWire;
export type EligibilityDeterminationMode = EligibilityDeterminationModeWire;

export interface EligibilityFactRefView {
  excerpt: string | null;
  sourceDocumentVersionId: string | null;
  pageArtifactId: string | null;
  factId: string;
  locatorId: string | null;
  pageNumber: number | null;
}

export interface EligibilitySourceReadRefView {
  sourceDocumentVersionId: string;
  pageArtifactId: string;
  pageNumber: number;
  excerpt: string | null;
  disposition: "mentioned" | "not_seen" | "unresolved";
}

export interface EligibilityClauseView {
  ruleComponentId: string;
  ruleCode: string;
  ruleKind: EligibilityRuleKind;
  textSummary: string;
  sourceText?: string | null;
  parentRuleCode: string | null;
  decision: EligibilityDecision;
  confidence?: "high" | "low" | null;
  confidenceReason?: string | null;
  canConfirm?: boolean;
  confirmationKind?: "medical_manager" | "builder_verification" | null;
  decisionLabel: string;
  reason: string;
  reasonParts?: Array<{ conditionId: string; conditionText: string; reasonText: string; requiresAttention: boolean }>;
  factRefs: EligibilityFactRefView[];
  sourceReadRefs?: EligibilitySourceReadRefView[];
  gapType: string | null;
  determinationMode: EligibilityDeterminationMode;
  limitationKind?: EligibilityLimitationKindWire | null;
  actionOwner: EligibilityActionTarget | null;
  actionDetail: string | null;
  actionEvidence: string | null;
}

export type EligibilityControlStatus = EligibilityControlStatusWire;

export interface EligibilityControlObligationView {
  obligationId: string;
  obligationGroupId: string;
  statement: string;
  sourceExcerpts: string[];
  status: EligibilityControlStatus;
  statusLabel: string;
  limitationKind?: EligibilityLimitationKindWire | null;
  reason: string;
  factRefs: EligibilityFactRefView[];
  sourceReadRefs?: EligibilitySourceReadRefView[];
  continuingNote?: string | null;
  actionOwner?: EligibilityActionTarget | null;
  actionDetail?: string | null;
  actionEvidence?: string | null;
}

export interface EligibilityControlView {
  protocolControlId: string;
  displayLabel: string;
  title: string;
  sourceSpanIds: string[];
  obligations: EligibilityControlObligationView[];
}

export type EligibilityActionTarget =
  | "investigator"
  | "crc"
  | "cra"
  | "sponsor_medical_or_project";

export interface EligibilityReviewView {
  verificationOnly?: boolean;
  componentClauses?: EligibilityClauseView[];
  reviewRunId?: string | null;
  systemIssues?: { kind: string; affectedCodes: string[]; detail: string; alternative: string; pageArtifactId?: string | null; pageNumber?: number | null }[];
  workDraftState?: "not_started" | "current" | "source_changed" | "method_changed";
  unassignedConflicts?: { conflictGroupId: string; memberKind: "event" | "exposure"; memberIds: string[] }[];
  subjectId: string;
  reviewEpisodeId: string;
  ruleSetId: string;
  ruleSetRevision: number;
  evidenceSnapshotV2Id: string;
  completeProcessingRevisionId: string;
  clauses: EligibilityClauseView[];
  controls: EligibilityControlView[];
}

export class EligibilityReviewApiError extends Error {
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
    this.name = "EligibilityReviewApiError";
    this.code = code;
    this.title = title;
    this.recoveryAction = recoveryAction;
    this.statusCode = statusCode;
  }
}

export class EligibilityReviewDecodeError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "EligibilityReviewDecodeError";
  }
}

type ObjectValue = Record<string, unknown>;

function objectValue(value: unknown, path: string): ObjectValue {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new EligibilityReviewDecodeError(`${path} 不是对象`);
  }
  return value as ObjectValue;
}

function field(source: ObjectValue, key: string, path: string): unknown {
  if (!(key in source)) {
    throw new EligibilityReviewDecodeError(`${path}.${key} 缺失`);
  }
  return source[key];
}

function requiredString(value: unknown, path: string): string {
  if (typeof value !== "string" || value.length === 0) {
    throw new EligibilityReviewDecodeError(`${path} 必须是非空文字`);
  }
  return value;
}

function nullableString(value: unknown, path: string): string | null {
  if (value === null) return null;
  return requiredString(value, path);
}

function positiveInteger(value: unknown, path: string): number {
  if (typeof value !== "number" || !Number.isInteger(value) || value < 1) {
    throw new EligibilityReviewDecodeError(`${path} 必须是正整数`);
  }
  return value;
}

function nullablePositiveInteger(value: unknown, path: string): number | null {
  if (value === null) return null;
  return positiveInteger(value, path);
}

function arrayValue(value: unknown, path: string): unknown[] {
  if (!Array.isArray(value)) {
    throw new EligibilityReviewDecodeError(`${path} 必须是数组`);
  }
  return value;
}


function decodeReasonParts(value: unknown, path: string): NonNullable<EligibilityClauseView["reasonParts"]> {
  if (value === undefined) return [];
  const seen = new Set<string>();
  return arrayValue(value, path).map((raw, index) => {
    const row = objectValue(raw, `${path}[${index}]`);
    const conditionId = requiredString(row.condition_id, `${path}[${index}].condition_id`);
    if (seen.has(conditionId) || typeof row.requires_attention !== "boolean") {
      throw new EligibilityReviewDecodeError(`${path} 条件重复或核对状态不正确`);
    }
    seen.add(conditionId);
    return { conditionId, conditionText: requiredString(row.condition_text, `${path}[${index}].condition_text`),
      reasonText: requiredString(row.reason_text, `${path}[${index}].reason_text`), requiresAttention: row.requires_attention };
  });
}

function enumValue<T extends string>(
  value: unknown,
  values: readonly T[],
  path: string,
): T {
  if (typeof value !== "string" || !values.includes(value as T)) {
    throw new EligibilityReviewDecodeError(`${path} 包含未知值`);
  }
  return value as T;
}

function optionalEnumValue<T extends string>(
  value: unknown,
  values: readonly T[],
  path: string,
): T | null {
  if (value === null || value === undefined) return null;
  return enumValue(value, values, path);
}

const ACTION_TARGETS: readonly EligibilityActionTarget[] = [
  "investigator",
  "crc",
  "cra",
  "sponsor_medical_or_project",
];

const RULE_KINDS: readonly EligibilityRuleKind[] = [
  "inclusion",
  "exclusion",
  "required_procedure",
  "medication",
];
const DECISIONS: readonly EligibilityDecision[] = [
  "inclusion_met",
  "inclusion_not_met",
  "requirement_met",
  "requirement_not_met",
  "exclusion_triggered",
  "exclusion_not_triggered",
  "professional_judgment",
  "indeterminate",
  "conflict",
  "not_due",
  "not_applicable",
  "system_issue",
];
const DETERMINATION_MODES: readonly EligibilityDeterminationMode[] = [
  "deterministic",
  "semantic",
  "investigator_judgment",
  "restricted",
];
const CONTROL_STATUSES: readonly EligibilityControlStatus[] = [
  "fulfilled",
  "unfulfilled",
  "unverified",
  "restricted",
  "not_applicable",
];

const LIMITATION_KINDS: readonly EligibilityLimitationKindWire[] = [
  "interpretation_unresolved", "consumer_unavailable",
];

function decodeFactRef(value: unknown, index: number, parentPath = "clauses[].fact_refs"): EligibilityFactRefView {
  const path = `${parentPath}[${index}]`;
  const row = objectValue(value, path);
  return {
    excerpt: nullableString(field(row, "excerpt", path), `${path}.excerpt`),
    factId: requiredString(field(row, "fact_id", path), `${path}.fact_id`),
    sourceDocumentVersionId: nullableString(field(row, "source_document_version_id", path), `${path}.source_document_version_id`),
    pageArtifactId: nullableString(field(row, "page_artifact_id", path), `${path}.page_artifact_id`),
    locatorId: nullableString(field(row, "locator_id", path), `${path}.locator_id`),
    pageNumber: nullablePositiveInteger(
      field(row, "page_number", path),
      `${path}.page_number`,
    ),
  };
}

function decodeSourceReads(value: unknown, path: string): EligibilitySourceReadRefView[] {
  if (value === undefined) return [];
  return arrayValue(value, path).map((item, index) => {
    const child = `${path}[${index}]`;
    const row = objectValue(item, child);
    const pageNumber = nullablePositiveInteger(field(row, "page_number", child), `${child}.page_number`);
    if (pageNumber === null) throw new EligibilityReviewDecodeError(`${child}.page_number 不得为空`);
    return {
      sourceDocumentVersionId: requiredString(field(row, "source_document_version_id", child), `${child}.source_document_version_id`),
      pageArtifactId: requiredString(field(row, "page_artifact_id", child), `${child}.page_artifact_id`),
      pageNumber,
      excerpt: nullableString(field(row, "excerpt", child), `${child}.excerpt`),
      disposition: enumValue(field(row, "disposition", child), ["mentioned", "not_seen", "unresolved"] as const, `${child}.disposition`),
    };
  });
}

function decodeClause(value: unknown, index: number): EligibilityClauseView {
  const path = `clauses[${index}]`;
  const row = objectValue(value, path);
  const ruleCode = requiredString(field(row, "rule_code", path), `${path}.rule_code`);
  const ruleKind = enumValue(field(row, "rule_kind", path), RULE_KINDS, `${path}.rule_kind`);
  if (!(ruleKind === "medication" ? /^用药\d{2,}$/ : /^(IN|EX|REQ)-\d{2}$/).test(ruleCode)) {
    throw new EligibilityReviewDecodeError(`${path}.rule_code 格式不正确`);
  }
  const parentRuleCode = nullableString(
    field(row, "parent_rule_code", path),
    `${path}.parent_rule_code`,
  );
  if (parentRuleCode !== null && !/^(IN|EX|REQ)-\d{2}$/.test(parentRuleCode)) {
    throw new EligibilityReviewDecodeError(`${path}.parent_rule_code 格式不正确`);
  }
  if (ruleKind === "medication" && parentRuleCode !== null) throw new EligibilityReviewDecodeError("用药要求不能伪装成官方入排子项");
  const refs = arrayValue(field(row, "fact_refs", path), `${path}.fact_refs`);
  if (row.can_confirm != null && typeof row.can_confirm !== "boolean") throw new EligibilityReviewDecodeError("核实操作记录不完整");
  return {
    ruleCode,
    ruleComponentId: requiredString(field(row, "rule_component_id", path), `${path}.rule_component_id`),
    ruleKind,
    textSummary: requiredString(
      field(row, "text_summary", path),
      `${path}.text_summary`,
    ),
    sourceText: "source_text" in row
      ? nullableString(row.source_text, `${path}.source_text`) : null,
    parentRuleCode,
    decision: enumValue(field(row, "decision", path), DECISIONS, `${path}.decision`),
    confidence: optionalEnumValue(row.confidence, ["high", "low"] as const, `${path}.confidence`),
    confidenceReason: row.confidence_reason == null ? null : requiredString(row.confidence_reason, `${path}.confidence_reason`),
    canConfirm: row.can_confirm === true,
    confirmationKind: optionalEnumValue(row.confirmation_kind ?? null, ["medical_manager", "builder_verification"] as const, `${path}.confirmation_kind`),
    decisionLabel: requiredString(
      field(row, "decision_label", path),
      `${path}.decision_label`,
    ),
    reason: requiredString(field(row, "reason", path), `${path}.reason`),
    reasonParts: decodeReasonParts(row.reason_parts, `${path}.reason_parts`),
    factRefs: refs.map((value, index) => decodeFactRef(value, index)),
    sourceReadRefs: decodeSourceReads(row.source_read_refs, `${path}.source_read_refs`),
    gapType: nullableString(field(row, "gap_type", path), `${path}.gap_type`),
    limitationKind: optionalEnumValue(row.limitation_kind ?? null, LIMITATION_KINDS, `${path}.limitation_kind`),
    determinationMode: enumValue(
      field(row, "determination_mode", path),
      DETERMINATION_MODES,
      `${path}.determination_mode`,
    ),
    actionOwner: optionalEnumValue(
      field(row, "action_owner", path),
      ACTION_TARGETS,
      `${path}.action_owner`,
    ),
    actionDetail: nullableString(field(row, "action_detail", path), `${path}.action_detail`),
    actionEvidence: nullableString(field(row, "action_evidence", path), `${path}.action_evidence`),
  };
}

function decodeControl(value: unknown, index: number): EligibilityControlView {
  const path = `controls[${index}]`;
  const row = objectValue(value, path);
  const obligations = arrayValue(field(row, "obligations", path), `${path}.obligations`)
    .map((value, obligationIndex) => {
      const obligationPath = `${path}.obligations[${obligationIndex}]`;
      const obligation = objectValue(value, obligationPath);
      const refs = arrayValue(
        field(obligation, "fact_refs", obligationPath),
        `${obligationPath}.fact_refs`,
      );
      return {
        obligationId: requiredString(field(obligation, "obligation_id", obligationPath), `${obligationPath}.obligation_id`),
        obligationGroupId: requiredString(field(obligation, "obligation_group_id", obligationPath), `${obligationPath}.obligation_group_id`),
        statement: requiredString(field(obligation, "statement", obligationPath), `${obligationPath}.statement`),
        sourceExcerpts: obligation.source_excerpts == null ? []
          : arrayValue(obligation.source_excerpts, `${obligationPath}.source_excerpts`)
            .map((item) => requiredString(item, `${obligationPath}.source_excerpts[]`)),
        status: enumValue(field(obligation, "status", obligationPath), CONTROL_STATUSES, `${obligationPath}.status`),
        statusLabel: requiredString(field(obligation, "status_label", obligationPath), `${obligationPath}.status_label`),
        limitationKind: optionalEnumValue(obligation.limitation_kind ?? null, LIMITATION_KINDS, `${obligationPath}.limitation_kind`),
        reason: requiredString(field(obligation, "reason", obligationPath), `${obligationPath}.reason`),
        factRefs: refs.map((item, refIndex) => decodeFactRef(item, refIndex, `${obligationPath}.fact_refs`)),
        sourceReadRefs: decodeSourceReads(obligation.source_read_refs, `${obligationPath}.source_read_refs`),
        continuingNote: obligation.continuing_note == null
          ? null
          : requiredString(obligation.continuing_note, `${obligationPath}.continuing_note`),
        actionOwner: optionalEnumValue(
          field(obligation, "action_owner", obligationPath),
          ACTION_TARGETS,
          `${obligationPath}.action_owner`,
        ),
        actionDetail: nullableString(field(obligation, "action_detail", obligationPath), `${obligationPath}.action_detail`),
        actionEvidence: nullableString(field(obligation, "action_evidence", obligationPath), `${obligationPath}.action_evidence`),
      };
    });
  const obligationIds = obligations.map((item) => `${item.obligationGroupId}:${item.obligationId}`);
  if (new Set(obligationIds).size !== obligationIds.length) {
    throw new EligibilityReviewDecodeError(`${path} 包含重复的补充要求事项`);
  }
  return {
    protocolControlId: requiredString(field(row, "protocol_control_id", path), `${path}.protocol_control_id`),
    displayLabel: requiredString(field(row, "display_label", path), `${path}.display_label`),
    title: requiredString(field(row, "title", path), `${path}.title`),
    sourceSpanIds: arrayValue(field(row, "source_span_ids", path), `${path}.source_span_ids`)
      .map((item) => requiredString(item, `${path}.source_span_ids[]`)),
    obligations,
  };
}

export function decodeEligibilityReview(value: unknown): EligibilityReviewView {
  const row = objectValue(value, "eligibility_review");
  const clauses = arrayValue(field(row, "clauses", "eligibility_review"), "clauses");
  const decodedClauses = clauses.map(decodeClause);
  const componentClauses = row.component_clauses == null ? [] : arrayValue(row.component_clauses, "eligibility_review.component_clauses").map(decodeClause);
  const allIdentities = [...decodedClauses, ...componentClauses].map(clause => clause.ruleComponentId);
  if (new Set(allIdentities).size !== allIdentities.length) {
    throw new EligibilityReviewDecodeError("审核要点重复，请重新读取审核结果。");
  }
  const unassignedConflicts = ("unassigned_conflicts" in row
      ? arrayValue(row.unassigned_conflicts, "unassigned_conflicts") : []).map((value, index) => {
      const path = `unassigned_conflicts[${index}]`;
      const item = objectValue(value, path);
      const members = arrayValue(field(item, "member_ids", path), `${path}.member_ids`)
        .map((member) => requiredString(member, `${path}.member_ids[]`));
      if (members.length < 2 || new Set(members).size !== members.length) {
        throw new EligibilityReviewDecodeError("争议记录的来源成员不完整或重复");
      }
      return {
        conflictGroupId: requiredString(field(item, "conflict_group_id", path), `${path}.conflict_group_id`),
        memberKind: enumValue(field(item, "member_kind", path), ["event", "exposure"] as const, `${path}.member_kind`),
        memberIds: members,
      };
    });
  if (new Set(unassignedConflicts.map((item) => item.conflictGroupId)).size !== unassignedConflicts.length) {
    throw new EligibilityReviewDecodeError("争议记录重复，请重新读取审核结果。");
  }
  const controls = ("controls" in row
    ? arrayValue(row.controls, "controls") : []).map(decodeControl);
  if (new Set(controls.map((item) => item.protocolControlId)).size !== controls.length) {
    throw new EligibilityReviewDecodeError("补充要求重复，请重新读取审核结果。");
  }
  if (decodedClauses.length === 0 && controls.length === 0) {
    throw new EligibilityReviewDecodeError("当前方案没有可审核的官方条款或补充要求");
  }
  return {
    unassignedConflicts,
    workDraftState: "work_draft_state" in row
      ? enumValue(row.work_draft_state, ["not_started", "current", "source_changed", "method_changed"] as const, "work_draft_state")
      : "not_started",
    subjectId: requiredString(field(row, "subject_id", "eligibility_review"), "subject_id"),
    reviewEpisodeId: requiredString(
      field(row, "review_episode_id", "eligibility_review"),
      "review_episode_id",
    ),
    ruleSetId: requiredString(field(row, "rule_set_id", "eligibility_review"), "rule_set_id"),
    ruleSetRevision: positiveInteger(
      field(row, "rule_set_revision", "eligibility_review"),
      "rule_set_revision",
    ),
    evidenceSnapshotV2Id: requiredString(
      field(row, "evidence_snapshot_v2_id", "eligibility_review"),
      "evidence_snapshot_v2_id",
    ),
    completeProcessingRevisionId: requiredString(
      field(row, "complete_processing_revision_id", "eligibility_review"),
      "complete_processing_revision_id",
    ),
    clauses: decodedClauses,
    componentClauses,
    controls,
    reviewRunId: row.review_run_id == null ? null : requiredString(row.review_run_id, "eligibility_review.review_run_id"),
    verificationOnly: row.verification_only === true,
    systemIssues: row.system_issues == null ? [] : arrayValue(row.system_issues, "eligibility_review.system_issues").map((value, index) => {
      const issue = objectValue(value, `system_issues[${index}]`);
      return { kind: requiredString(issue.kind, "system_issue.kind"),
        affectedCodes: arrayValue(issue.affected_codes, "system_issue.affected_codes").map(value => requiredString(value, "system_issue.code")),
        pageArtifactId: issue.page_artifact_id == null ? null : requiredString(issue.page_artifact_id, "system_issue.page_artifact_id"),
        pageNumber: issue.page_number == null ? null : positiveInteger(issue.page_number, "system_issue.page_number"),
        detail: requiredString(issue.detail, "system_issue.detail"), alternative: requiredString(issue.alternative, "system_issue.alternative") };
    }),
  };
}

export function decodeEligibilityReviewError(
  value: unknown,
  statusCode: number,
): EligibilityReviewApiError {
  const envelope =
    typeof value === "object" && value !== null && !Array.isArray(value)
      ? value as ObjectValue
      : {};
  const errorValue = envelope.error;
  const error =
    typeof errorValue === "object" && errorValue !== null && !Array.isArray(errorValue)
      ? errorValue as ObjectValue
      : {};
  const detail =
    typeof error.detail === "string" && error.detail.length > 0
      ? error.detail
      : "暂时无法读取入排审核结果。";
  return new EligibilityReviewApiError(
    typeof error.code === "string" && error.code.length > 0 ? error.code : "INVALID_RESPONSE",
    typeof error.title === "string" && error.title.length > 0 ? error.title : "读取失败",
    detail,
    typeof error.recovery_action === "string" && error.recovery_action.length > 0
      ? error.recovery_action
      : "请稍后重试。",
    statusCode,
  );
}

// Keep wire imports visible to ensure this decoder remains aligned with the API contract.
export type {
  EligibilityClauseWire,
  EligibilityControlWire,
  EligibilityFactRefWire,
};
