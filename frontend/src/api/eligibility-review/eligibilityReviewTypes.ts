/** 入排审核只读投影的网络契约。中文字段由服务端提供，前端不重新推导。 */

export type EligibilityRuleKindWire =
  | "inclusion"
  | "exclusion"
  | "required_procedure";

export type EligibilityDecisionWire =
  | "inclusion_met"
  | "inclusion_not_met"
  | "requirement_met"
  | "requirement_not_met"
  | "exclusion_triggered"
  | "exclusion_not_triggered"
  | "professional_judgment"
  | "conflict"
  | "not_due"
  | "not_applicable";

export type EligibilityDeterminationModeWire =
  | "deterministic"
  | "semantic"
  | "investigator_judgment";

export interface EligibilityFactRefWire {
  fact_id: string;
  locator_id: string | null;
  page_number: number | null;
}

export interface EligibilityClauseWire {
  rule_code: string;
  rule_kind: EligibilityRuleKindWire;
  text_summary: string;
  parent_rule_code: string | null;
  decision: EligibilityDecisionWire;
  decision_label: string;
  reason: string;
  fact_refs: EligibilityFactRefWire[];
  gap_type: string | null;
  determination_mode: EligibilityDeterminationModeWire;
}

export interface EligibilityReviewWire {
  subject_id: string;
  review_episode_id: string;
  rule_set_id: string;
  rule_set_revision: number;
  evidence_snapshot_v2_id: string;
  complete_processing_revision_id: string;
  clauses: EligibilityClauseWire[];
}
