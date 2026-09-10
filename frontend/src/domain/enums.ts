/**
 * 领域枚举：值与 `contracts/v1/schema/fixture-v1.schema.json` 枚举一致。
 * 中文显示词不在此处，统一在 labels.ts 通过穷尽映射生成。
 */

export type ReviewStage =
  | "pre_screening"
  | "screening"
  | "run_in"
  | "baseline";

export type EpisodeMainStatus =
  | "clear_barrier"
  | "current_gap"
  | "conflict"
  | "professional_judgment"
  | "future_attention"
  | "no_clear_barrier";

export type ComponentDecision =
  | "inclusion_met"
  | "inclusion_not_met"
  | "exclusion_not_triggered"
  | "exclusion_triggered"
  | "indeterminate"
  | "professional_judgment"
  | "conflict"
  | "not_due"
  | "not_applicable"
  | "requirement_met"
  | "requirement_not_met";

export type GapType =
  | "observation_unverified"
  | "record_incomplete"
  | "description_insufficient"
  | "historical_source_unavailable"
  | "referenced_file_missing"
  | "required_procedure_not_done"
  | "result_fields_missing"
  | "date_or_anchor_missing"
  | "professional_judgment"
  | "source_conflict"
  | "interpretation_conflict"
  | "ocr_or_parse_risk"
  | "future_stage_not_due"
  | "provenance_followup";

export type BlockingLevel = "none" | "attention" | "blocking";

export type ActionState =
  | "open"
  | "closed_system"
  | "closed_manual"
  | "reopened"
  | "superseded";

export type ActionTarget =
  | "investigator"
  | "crc"
  | "cra"
  | "sponsor_medical_or_project";

export type LocatorPrecision = "bbox" | "text_range" | "page_excerpt" | "page_only";

/** 方案结构来源还可能只能回溯到文档结构块，不能冒充页码定位。 */
export type ProtocolSourcePrecision = LocatorPrecision | "block";

export type StudyPhase =
  | "phase_ii"
  | "phase_iii"
  | "seamless_phase_ii_iii"
  | "other";

export type ExpectationStatus =
  | "observed"
  | "observed_weak"
  | "referenced_missing"
  | "absent"
  | "not_due";

export type ProfileLane =
  | "study_milestone"
  | "demographics"
  | "target_disease"
  | "symptoms_signs"
  | "medical_history"
  | "medication"
  | "non_drug_treatment"
  | "test_exam_score"
  | "allergy_infection_immune"
  | "reproductive"
  | "social_environmental"
  | "special_history"
  | "evidence_quality";

export type JobEventType =
  | "created"
  | "step_started"
  | "step_completed"
  | "step_failed"
  | "retry_scheduled"
  | "cancel_requested"
  | "cancelled"
  | "completed";

export type LogicalOperator = "all" | "any" | "not";

export type RuleKind = "inclusion" | "exclusion" | "required_procedure";

export type Comparator =
  | "eq"
  | "ne"
  | "gt"
  | "gte"
  | "lt"
  | "lte"
  | "in"
  | "not_in"
  | "exists";

export type FactPolarity = "affirmed" | "negated" | "unknown";

export type DatePrecision = "day" | "month" | "year" | "unknown";

/**
 * 任务可见状态：由 Job 事件序列推导，对应交互合同 1.3 节中文任务词。
 */
export type TaskState =
  | "queued"
  | "running"
  | "completed"
  | "partial"
  | "failed"
  | "resumable"
  | "cancelled"
  | "stale";
