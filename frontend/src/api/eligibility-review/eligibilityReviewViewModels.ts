import type {
  EligibilityClauseWire,
  EligibilityControlStatusWire,
  EligibilityControlWire,
  EligibilityDecisionWire,
  EligibilityDeterminationModeWire,
  EligibilityFactRefWire,
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

export interface EligibilityClauseView {
  ruleComponentId: string;
  ruleCode: string;
  ruleKind: EligibilityRuleKind;
  textSummary: string;
  sourceText?: string | null;
  parentRuleCode: string | null;
  decision: EligibilityDecision;
  decisionLabel: string;
  reason: string;
  factRefs: EligibilityFactRefView[];
  gapType: string | null;
  determinationMode: EligibilityDeterminationMode;
  actionOwner: EligibilityActionTarget | null;
  actionDetail: string | null;
  actionEvidence: string | null;
}

export type EligibilityControlStatus = EligibilityControlStatusWire;

export interface EligibilityControlObligationView {
  obligationId: string;
  obligationGroupId: string;
  statement: string;
  status: EligibilityControlStatus;
  statusLabel: string;
  reason: string;
  factRefs: EligibilityFactRefView[];
  continuingNote?: string | null;
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
];
const DETERMINATION_MODES: readonly EligibilityDeterminationMode[] = [
  "deterministic",
  "semantic",
  "investigator_judgment",
];
const CONTROL_STATUSES: readonly EligibilityControlStatus[] = [
  "fulfilled",
  "unfulfilled",
  "unverified",
  "not_applicable",
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

function decodeClause(value: unknown, index: number): EligibilityClauseView {
  const path = `clauses[${index}]`;
  const row = objectValue(value, path);
  const ruleCode = requiredString(field(row, "rule_code", path), `${path}.rule_code`);
  if (!/^(IN|EX|REQ)-\d{2}$/.test(ruleCode)) {
    throw new EligibilityReviewDecodeError(`${path}.rule_code 格式不正确`);
  }
  const parentRuleCode = nullableString(
    field(row, "parent_rule_code", path),
    `${path}.parent_rule_code`,
  );
  if (parentRuleCode !== null && !/^(IN|EX|REQ)-\d{2}$/.test(parentRuleCode)) {
    throw new EligibilityReviewDecodeError(`${path}.parent_rule_code 格式不正确`);
  }
  const refs = arrayValue(field(row, "fact_refs", path), `${path}.fact_refs`);
  return {
    ruleCode,
    ruleComponentId: requiredString(field(row, "rule_component_id", path), `${path}.rule_component_id`),
    ruleKind: enumValue(
      field(row, "rule_kind", path),
      RULE_KINDS,
      `${path}.rule_kind`,
    ),
    textSummary: requiredString(
      field(row, "text_summary", path),
      `${path}.text_summary`,
    ),
    sourceText: "source_text" in row
      ? nullableString(row.source_text, `${path}.source_text`) : null,
    parentRuleCode,
    decision: enumValue(field(row, "decision", path), DECISIONS, `${path}.decision`),
    decisionLabel: requiredString(
      field(row, "decision_label", path),
      `${path}.decision_label`,
    ),
    reason: requiredString(field(row, "reason", path), `${path}.reason`),
    factRefs: refs.map((value, index) => decodeFactRef(value, index)),
    gapType: nullableString(field(row, "gap_type", path), `${path}.gap_type`),
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
        status: enumValue(field(obligation, "status", obligationPath), CONTROL_STATUSES, `${obligationPath}.status`),
        statusLabel: requiredString(field(obligation, "status_label", obligationPath), `${obligationPath}.status_label`),
        reason: requiredString(field(obligation, "reason", obligationPath), `${obligationPath}.reason`),
        factRefs: refs.map((item, refIndex) => decodeFactRef(item, refIndex, `${obligationPath}.fact_refs`)),
        continuingNote: obligation.continuing_note == null
          ? null
          : requiredString(obligation.continuing_note, `${obligationPath}.continuing_note`),
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
  if (new Set(decodedClauses.map((clause) => clause.ruleComponentId)).size !== decodedClauses.length) {
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
    controls,
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
