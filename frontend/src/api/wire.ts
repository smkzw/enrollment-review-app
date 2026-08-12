/**
 * Wire 类型：`contracts/v1/fixtures/*.json` 的原始结构子集。
 * 只在 api 层出现；组件经 mappers.ts 消费 ViewModel。
 * 枚举值来自 `contracts/v1/schema/fixture-v1.schema.json` 与
 * `contracts/v1/schema/uat-phase1-workspace.schema.json`。
 */

import type {
  ActionState,
  ActionTarget,
  BlockingLevel,
  Comparator,
  ComponentDecision,
  DatePrecision,
  EpisodeMainStatus,
  ExpectationStatus,
  FactPolarity,
  GapType,
  JobEventType,
  LocatorPrecision,
  LogicalOperator,
  ProfileLane,
  ReviewStage,
  RuleKind,
} from "../domain/enums";

export interface DateValueWire {
  value: string;
  precision: DatePrecision;
  source_text: string | null;
}

export interface SubjectWire {
  subject_id: string;
  subject_code: string;
  center_code: string;
  center_name: string;
  project_id: string;
  age_years: number | null;
  sex: string | null;
  revision: number;
  schema_version: string;
}

export interface ProtocolDocumentVersionWire {
  protocol_version_id: string;
  protocol_code: string;
  official_version: string;
  official_date: DateValueWire | null;
  sha256: string;
}

export interface ProjectWire {
  project_id: string;
  project_code: string;
  project_name: string;
  study_phase: string;
  protocol_version: ProtocolDocumentVersionWire;
  rule_set_id: string;
  schema_version: string;
}

export interface ReviewEpisodeWire {
  review_episode_id: string;
  subject_id: string;
  project_id: string;
  rule_set_id: string;
  study_phase: string;
  stage: ReviewStage;
  protocol_version_id: string;
  rule_set_revision: number;
  evidence_snapshot_id: string;
  revision: number;
  schema_version: string;
  anchor_dates?: {
    icf_date?: DateValueWire;
    screening_date?: DateValueWire;
    baseline_date?: DateValueWire;
    randomization_date?: DateValueWire;
    event_date?: DateValueWire;
  };
  due_at: string | null;
}

export interface GapCountsWire {
  record_incomplete?: number;
  description_insufficient?: number;
  historical_source_unavailable?: number;
  referenced_file_missing?: number;
  required_procedure_not_done?: number;
  result_fields_missing?: number;
  date_or_anchor_missing?: number;
  professional_judgment?: number;
  source_conflict?: number;
  interpretation_conflict?: number;
  ocr_or_parse_risk?: number;
  future_stage_not_due?: number;
  provenance_followup?: number;
}

export interface EpisodeRollupWire {
  review_episode_id: string;
  main_status: EpisodeMainStatus;
  sort_rank: number;
  barrier_count: number;
  current_gap_count: number;
  conflict_count: number;
  professional_judgment_count: number;
  future_attention_count: number;
  provenance_followup_count: number;
  gap_counts: GapCountsWire;
  gate_result_id: string;
  publication_fingerprint: string;
  input_action_ids: string[];
  input_assessment_ids: string[];
  input_expectation_ids: string[];
}

export interface WorkflowStageWire {
  workflow_stage_id: string;
  stage: ReviewStage;
  display_name: string;
  visit_window: string;
  review_required: boolean;
  due_requirement_ids: string[];
  schema_version: string;
}

export interface EvidenceSpanWire {
  evidence_span_id: string;
  source_document_version_id: string;
  page_number: number;
  precision: LocatorPrecision;
  locator_algorithm_version: string;
  bbox: { x0: number; y0: number; x1: number; y1: number } | null;
  text_start: number | null;
  text_end: number | null;
  excerpt: string | null;
  degradation_reason: string | null;
  anchor_hash: string | null;
  match_confidence: number | null;
  schema_version: string;
}

export interface SourceDocumentWire {
  source_document_version_id: string;
  file_name: string;
  document_type: string;
  review_stage: ReviewStage;
  source_party: string;
  upload_mode: string;
  sha256: string;
  schema_version: string;
}

export interface EvidenceSnapshotWire {
  evidence_snapshot_id: string;
  subject_id: string;
  review_episode_id: string;
  source_document_version_ids: string[];
  upload_mode: string;
  created_at: string;
  prior_snapshot_id: string | null;
  schema_version: string;
}

export interface ProfileEventWire {
  event_id: string;
  lane: ProfileLane;
  event_type: string;
  title: string;
  risk_labels: string[];
  is_abnormal: boolean;
  is_critical: boolean;
  has_trend_change: boolean;
  start_date: DateValueWire | null;
  end_date: DateValueWire | null;
  related_rule_component_ids: string[];
  fact_ids: string[];
  evidence_span_ids: string[];
  schema_version: string;
}

export interface PatientProfileWire {
  patient_profile_id: string;
  subject_id: string;
  review_episode_id: string;
  stale: boolean;
  highlighted_event_ids: string[];
  missing_expectation_ids: string[];
  events: ProfileEventWire[];
  schema_version: string;
}

export interface EvidenceExpectationWire {
  expectation_id: string;
  requirement_id: string;
  review_episode_id: string;
  gap_type: GapType;
  status: ExpectationStatus;
  evidence_span_ids: string[];
  schema_version: string;
}

export interface ActionWire {
  action_id: string;
  assessment_id: string | null;
  rule_component_id: string;
  gap_type: GapType;
  target_party: ActionTarget;
  requested_action: string;
  acceptable_evidence: string;
  due_stage: ReviewStage;
  blocking_level: BlockingLevel;
  state: ActionState;
  recompute_scope: string[];
  review_run_id: string;
  revision: number;
  schema_version: string;
}

export interface ConflictGroupWire {
  conflict_group_id: string;
  fact_ids: string[];
  affected_rule_component_ids: string[];
  resolution_evidence_span_ids: string[];
  resolved: boolean;
  schema_version: string;
}

export interface FactWire {
  fact_id: string;
  fact_type: string;
  polarity: FactPolarity;
  certainty: number | null;
  value: boolean | number | string | null;
  unit: string | null;
  evidence_span_ids: string[];
  conflict_group_id: string | null;
  schema_version: string;
}

export interface FinalAssessmentWire {
  assessment_id: string;
  rule_component_id: string;
  decision: ComponentDecision;
  blocking_level: BlockingLevel;
  gap_types: GapType[];
  review_run_id: string;
  evidence_snapshot_id: string;
  evidence_span_ids: string[];
  schema_version: string;
}

export interface JobEventWire {
  job_event_id: string;
  job_id: string;
  event_type: JobEventType;
  occurred_at: string;
  attempt: number;
  step_id: string | null;
  checkpoint_id: string | null;
  progress_completed: number;
  progress_total: number;
  retryable: boolean;
  payload: Record<string, unknown>;
  schema_version: string;
}

export interface ReviewRunWire {
  review_run_id: string;
  review_episode_id: string;
  protocol_version_id: string;
  rule_set_revision: number;
  evidence_snapshot_id: string;
  started_at: string;
  completed_at: string | null;
  supersedes_review_run_id: string | null;
  schema_version: string;
}

export interface ReviewRunDiffWire {
  review_run_diff_id: string;
  prior_review_run_id: string;
  current_review_run_id: string;
  component_diffs: ReadonlyArray<{
    rule_component_id: string;
    prior_decision: ComponentDecision | null;
    current_decision: ComponentDecision | null;
  }>;
  schema_version: string;
}

export interface PredicateWire {
  predicate_id: string;
  subject: string;
  attribute: string;
  comparator: Comparator;
  value: boolean | number | string | null;
  unit: string | null;
  unit_match_policy: string | null;
  requires_professional_judgment: boolean;
  applicable_population: string | null;
}

export type AnchorTypeWire =
  | "icf_date"
  | "screening_date"
  | "baseline_date"
  | "randomization_date"
  | "event_date";

export type TimeDirectionWire = "before" | "after" | "on";

export interface TimeConstraintWire {
  anchor_type: AnchorTypeWire;
  direction: TimeDirectionWire;
  lower_bound_days: number | null;
  upper_bound_days: number | null;
  half_life_multiplier: number | null;
  allow_partial_date: boolean;
}

export interface ExpressionWire {
  kind: "predicate" | "logical";
  predicate?: PredicateWire;
  operator?: LogicalOperator;
  children?: ExpressionWire[];
  time_constraint?: TimeConstraintWire | null;
}

export interface EvidenceRequirementWire {
  requirement_id: string;
  rule_component_id: string;
  fact_type: string;
  due_stage: ReviewStage;
  description: string;
  required_source_types: string[];
  requires_contemporaneous_objective_source: boolean;
  allows_screening_record_transcription: boolean;
  schema_version: string;
}

export interface RuleComponentWire {
  rule_component_id: string;
  parent_rule_id: string;
  display_code: string;
  title: string;
  expression: ExpressionWire;
  exception_expression: ExpressionWire | null;
  evidence_requirements: EvidenceRequirementWire[];
  schema_version: string;
}

export interface RuleWire {
  rule_id: string;
  official_code: string;
  kind: RuleKind;
  source_text: string;
  study_phase: string;
  components: RuleComponentWire[];
  schema_version: string;
}

export interface RuleSetWire {
  rule_set_id: string;
  protocol_version_id: string;
  revision: number;
  rules: RuleWire[];
  schema_version: string;
}

export interface ProtocolDiffWire {
  current_protocol_version_id: string;
  proposed_protocol_version_id: string;
  added_rule_codes: string[];
  deleted_rule_codes: string[];
  changed_logic_or_window_codes: string[];
  current_rule_set: RuleSetWire;
  proposed_rule_set_draft: RuleSetWire;
  source_refs: string[];
  schema_version: string;
}

export interface EpisodeFixtureWire {
  fixture_id: string;
  scenario: string;
  schema_version: string;
  subject: SubjectWire;
  project: ProjectWire;
  review_episode: ReviewEpisodeWire;
  episode_rollup: EpisodeRollupWire;
  workflow_stages: WorkflowStageWire[];
  patient_profile: PatientProfileWire;
  evidence_spans: EvidenceSpanWire[];
  source_documents: SourceDocumentWire[];
  evidence_snapshot: EvidenceSnapshotWire;
  evidence_expectations: EvidenceExpectationWire[];
  actions: ActionWire[];
  conflict_groups: ConflictGroupWire[];
  facts: FactWire[];
  final_assessments: FinalAssessmentWire[];
  rule_set: RuleSetWire;
  review_runs: ReviewRunWire[];
  review_run_diffs: ReviewRunDiffWire[];
  job_events: JobEventWire[];
}

export interface WorkspaceFixtureWire {
  workspace_id: string;
  schema_version: string;
  primary_subject_ids: string[];
  stage_template_episode_ids: string[];
  protocol_diff: ProtocolDiffWire;
  episodes: EpisodeFixtureWire[];
}
