/**
 * V2 方案解构工作台 API 契约（与 app/api/v2/protocol_schemas.py 对齐）。
 * 组件经 mappers 消费 ViewModel，不直接使用 wire 结构。
 */

import type {
  DatePrecision,
  ProtocolSourcePrecision,
  StudyPhase,
} from "../domain/enums";

export type ConfirmableDatePrecision = Exclude<DatePrecision, "unknown">;

export interface ProtocolWorkbenchErrorBody {
  code: string;
  title: string;
  detail: string;
  recovery_action: string;
  correlation_id?: string;
}

export class ProtocolWorkbenchApiError extends Error {
  readonly code: string;
  readonly title: string;
  readonly recoveryAction: string;

  constructor(code: string, title: string, message: string, recoveryAction: string) {
    super(message);
    this.name = "ProtocolWorkbenchApiError";
    this.code = code;
    this.title = title;
    this.recoveryAction = recoveryAction;
  }
}

export interface StartDeconstructionResult {
  jobId: string;
  state: string;
  stateLabel: string;
  created: boolean;
  sourceArtifactId: string;
  fileName: string;
}

export interface ProtocolSessionView {
  jobId: string;
  jobType: string;
  state: string;
  stateLabel: string;
  progressCompleted: number;
  progressTotal: number;
  sessionKind: string;
  awaitingUser: string | null;
  awaitingUserLabel: string | null;
  sourceArtifactId: string | null;
  fileName: string | null;
  snapshotId: string | null;
  draftId: string | null;
  draftRevisionId: string | null;
  draftRevisionNumber: number | null;
  draftStatus: string | null;
  draftStatusLabel: string | null;
  selectedPhase: StudyPhase | null;
  selectedPhaseLabel: string | null;
  protocolCode: string | null;
  officialVersion: string | null;
  recoveryCheckpointId: string | null;
  recoveryStepId: string | null;
  nextAction: string;
  publishable: boolean | null;
  /** 重新解构：目标正式项目投影（sessionKind="re_deconstruction" 时有值）。 */
  targetProjectId: string | null;
  targetProjectName: string | null;
  targetProjectCode: string | null;
  targetProtocolCode: string | null;
  targetStudyPhase: StudyPhase | null;
  targetStudyPhaseLabel: string | null;
  targetOfficialVersion: string | null;
  targetRuleSetRevision: number | null;
}

export interface IdentityDecisionView {
  identityDecisionId: string;
  snapshotId: string;
  status: string;
  statusLabel: string;
  projectName: string | null;
  projectCode: string | null;
  protocolCode: string | null;
  officialVersion: string | null;
  officialDateValue: string | null;
  officialDatePrecision: DatePrecision | null;
  studyPhase: StudyPhase | null;
  studyPhaseLabel: string | null;
  confirmationRequired: boolean;
  conflictIds: string[];
  selectedCandidateIds: string[];
}

export interface PhaseCandidateView {
  candidateId: string;
  phase: StudyPhase;
  phaseLabel: string;
  rationale: string;
  sourceExcerpt: string;
}

export interface MetadataCandidateView {
  candidateId: string;
  field: string;
  fieldLabel: string;
  value: string;
  sourceLabel: string;
  sourceExcerpt: string;
  isFallback: boolean;
}

export interface MetadataConflictView {
  conflictId: string;
  field: string;
  fieldLabel: string;
  reason: string;
  candidates: ReadonlyArray<{ candidateId: string; value: string; sourceLabel: string }>;
}

export interface IdentityReviewView {
  jobId: string;
  snapshotId: string;
  confirmationRequired: boolean;
  identity: IdentityDecisionView;
  phaseCandidates: PhaseCandidateView[];
  metadataCandidates: MetadataCandidateView[];
  metadataConflicts: MetadataConflictView[];
}

export interface ConfirmIdentityInput {
  protocolCode: string;
  projectName: string;
  projectCode?: string | null;
  officialVersion: string;
  officialDateValue: string;
  officialDatePrecision: ConfirmableDatePrecision;
  studyPhase: StudyPhase;
  selectedCandidateIds?: string[];
  actor?: string;
}

export interface DraftRevisionView {
  jobId: string;
  revisionId: string;
  draftId: string;
  revisionNumber: number;
  status: string;
  statusLabel: string;
  reason: string;
  reasonLabel: string;
  actor: string;
  createdAt: string;
  studyPhase: StudyPhase;
  studyPhaseLabel: string;
  protocolCode: string | null;
  officialVersion: string | null;
  ruleCount: number;
  workflowStageCount: number;
  content: Record<string, unknown>;
  diff: ProtocolDraftDiffWire | null;
}

export type ProtocolDiffEntityKind = "rule" | "component" | "requirement";

export type ProtocolJsonValue =
  | string
  | number
  | boolean
  | null
  | ProtocolJsonValue[]
  | { [key: string]: ProtocolJsonValue };

export type ProtocolPredicateValue = string | number | boolean | Array<string | number | boolean>;

export type ProtocolLogicPayload =
  | {
      kind: "predicate";
      predicate: {
        subject: string;
        attribute: string;
        comparator: "eq" | "ne" | "gt" | "gte" | "lt" | "lte" | "in" | "not_in" | "exists";
        value?: ProtocolPredicateValue;
        unit?: string | null;
        applicable_population?: string | null;
        requires_professional_judgment?: boolean;
        unit_match_policy?: string;
      };
    }
  | {
      kind: "logical";
      operator: "all" | "any" | "not";
      children: ProtocolLogicPayload[];
    };

export interface ProtocolTimeQuantityPayload {
  value: number;
  unit: "day" | "week" | "month" | "year";
}

export interface ProtocolTimeEntryPayload {
  scope: "main" | "exception";
  time_constraint: null | {
    anchor_type: "icf_date" | "screening_date" | "baseline_date" | "randomization_date" | "first_dose_date" | "study_drug_administration_date" | "last_dose_date" | "study_completion_date" | "event_date";
    direction: "before" | "after" | "on";
    lower_bound_days?: number | null;
    upper_bound_days?: number | null;
    lower_bound?: ProtocolTimeQuantityPayload | null;
    upper_bound?: ProtocolTimeQuantityPayload | null;
    half_life_multiplier?: number | null;
    allow_partial_date?: boolean;
  };
  occurrence_window: null | {
    duration: ProtocolTimeQuantityPayload;
    minimum_count?: number | null;
  };
  prospective_window: null | {
    anchor_type: "study_drug_administration_date" | "last_dose_date" | "study_completion_date";
    upper_bound: ProtocolTimeQuantityPayload;
  };
  prospective_period: null | {
    period: "treatment_period" | "study_period";
  };
}

export interface ProtocolOriginalTextPayload {
  source_text?: string;
  title?: string;
  source_binding?: null | {
    source_refs: string[];
    source_excerpts: string[];
  };
  verbatim_fragments?: Array<{
    source_term: string | null;
    source_clause: string | null;
    source_clauses: string[];
  }>;
}

export interface ProtocolEvidencePayload {
  fact_type: string;
  required_source_types: string[];
  allows_screening_record_transcription: boolean;
  requires_contemporaneous_objective_source: boolean;
  source_validity_window: ProtocolTimeQuantityPayload | null;
  description: string;
}

export interface ProtocolEvidenceWrapperPayload {
  evidence: ProtocolEvidencePayload;
}

export interface ProtocolDueStagePayload {
  fact_type: string;
  due_stages: Array<"pre_screening" | "screening" | "run_in" | "baseline">;
}

export type ProtocolDiffPayload =
  | ProtocolLogicPayload
  | ProtocolTimeEntryPayload[]
  | ProtocolOriginalTextPayload
  | ProtocolEvidencePayload
  | ProtocolEvidenceWrapperPayload
  | ProtocolEvidencePayload[]
  | Array<ProtocolEvidencePayload | ProtocolEvidenceWrapperPayload>
  | ProtocolDueStagePayload[];

export interface ProtocolCategoryChangeWire {
  stable_ref: string;
  kind: ProtocolDiffEntityKind;
  previous: ProtocolDiffPayload | null;
  current: ProtocolDiffPayload | null;
}

export interface ProtocolRuleDiffWire {
  official_code: string;
  added: boolean;
  removed: boolean;
  added_component_refs: string[];
  removed_component_refs: string[];
  original_text_changes: ProtocolCategoryChangeWire[];
  logic_changes: ProtocolCategoryChangeWire[];
  time_window_changes: ProtocolCategoryChangeWire[];
  exception_changes: ProtocolCategoryChangeWire[];
  evidence_changes: ProtocolCategoryChangeWire[];
  due_stage_changes: ProtocolCategoryChangeWire[];
}

export interface ProtocolDraftDiffWire {
  added_rule_codes: string[];
  removed_rule_codes: string[];
  modified_rule_codes: string[];
  added_workflow_stage_ids: string[];
  removed_workflow_stage_ids: string[];
  modified_workflow_stage_ids: string[];
  changed_component_ids: string[];
  changed_requirement_ids: string[];
  changed_procedure_mapping_ids: string[];
  source_scope_changed: boolean;
  workflow_visit_rewritten: boolean;
  clarification_semantics_changed: boolean;
  rule_diffs: ProtocolRuleDiffWire[];
}

export interface IntegrityIssueView {
  issueCode: string;
  checkName: string;
  level: string;
  problem: string;
  impact: string;
  nextAction: string;
  affectedRefs: string[];
  repairScope: string[];
}

export interface IntegrityCheckView {
  checkName: string;
  passed: boolean;
  issueCount: number;
}

export interface IntegrityView {
  jobId: string;
  publishable: boolean;
  blockingCount: number;
  reviewCount: number;
  reminderCount: number;
  summary: string;
  checks: IntegrityCheckView[];
  issues: IntegrityIssueView[];
}

export interface SourceSpanView {
  sourceSpanId: string;
  sourceRef: string;
  pageLabel: string | null;
  excerpt: string;
  precision: ProtocolSourcePrecision;
  precisionLabel: string;
  degradationReason: string | null;
}

export interface SourcesView {
  jobId: string;
  snapshotId: string;
  selectedPhase: StudyPhase;
  selectedPhaseLabel: string;
  sourceSpans: Record<string, unknown>;
  sourceMaterials: Record<string, unknown>;
}

export interface PublishResultView {
  jobId: string;
  projectId: string;
  protocolVersionId: string;
  ruleSetId: string;
  ruleSetRevision: number;
  replay: boolean;
}

export interface OfficialProjectView {
  projectId: string;
  projectCode: string;
  projectName: string;
  studyPhase: StudyPhase;
  studyPhaseLabel: string;
  protocolCode: string;
  officialVersion: string;
  officialDateValue: string | null;
  officialDatePrecision: DatePrecision | null;
  ruleSetId: string;
  ruleSetRevision: number;
}

export interface ProjectVersionView {
  ruleSetRevision: number;
  protocolVersionId: string;
  officialVersion: string;
  officialDateValue: string | null;
  officialDatePrecision: DatePrecision | null;
  sha256: string;
  ruleCount: number;
  publishedAt: string;
}

export interface ProjectOfficialVersionView {
  project: OfficialProjectView;
  versions: ProjectVersionView[];
  publicationCount: number;
}

export interface DraftComparisonSideView {
  revisionId: string;
  draftId: string;
  protocolVersionId: string;
  officialVersion: string | null;
  revisionNumber: number | null;
  status: string | null;
  ruleCount: number;
  workflowStageCount: number;
  isFormalBaseline: boolean;
  content: Record<string, unknown>;
  sourceRefs: string[];
}

export interface DraftComparisonView {
  jobId: string;
  baseline: DraftComparisonSideView;
  candidate: DraftComparisonSideView;
  diff: ProtocolDraftDiffWire;
  sourceBound: boolean;
}

export type FeedbackKind = "source_error" | "clarification";

export interface FeedbackInput {
  expectedRevisionId: string;
  feedbackKind: FeedbackKind;
  targetRuleCode: string;
  feedbackNote: string;
  actor?: string;
}

/** 手工修订草稿输入（继续编辑）：提交完整草稿快照，乐观并发校验链头。 */
export interface ManualEditInput {
  expectedRevisionId: string;
  draft: Record<string, unknown>;
  actor?: string;
}
