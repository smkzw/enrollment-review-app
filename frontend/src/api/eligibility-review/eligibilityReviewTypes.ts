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
  | "indeterminate"
  | "conflict"
  | "not_due"
  | "not_applicable";

export type EligibilityDeterminationModeWire =
  | "deterministic"
  | "semantic"
  | "investigator_judgment";

export interface EligibilityFactRefWire {
  excerpt: string | null;
  source_document_version_id: string | null;
  page_artifact_id: string | null;
  fact_id: string;
  locator_id: string | null;
  page_number: number | null;
}

export interface EligibilityClauseWire {
  rule_component_id: string;
  rule_code: string;
  rule_kind: EligibilityRuleKindWire;
  text_summary: string;
  source_text?: string | null;
  parent_rule_code: string | null;
  decision: EligibilityDecisionWire;
  decision_label: string;
  reason: string;
  fact_refs: EligibilityFactRefWire[];
  gap_type: string | null;
  determination_mode: EligibilityDeterminationModeWire;
}

export type EligibilityControlStatusWire =
  | "fulfilled"
  | "unfulfilled"
  | "unverified"
  | "not_applicable";

export interface EligibilityControlObligationWire {
  obligation_id: string;
  obligation_group_id: string;
  statement: string;
  status: EligibilityControlStatusWire;
  status_label: string;
  reason: string;
  fact_refs: EligibilityFactRefWire[];
}

export interface EligibilityControlWire {
  protocol_control_id: string;
  display_label: string;
  title: string;
  source_span_ids: string[];
  obligations: EligibilityControlObligationWire[];
}

export interface EligibilityReviewWire {
  unassigned_conflicts?: { conflict_group_id: string; member_kind: "event" | "exposure"; member_ids: string[] }[];
  subject_id: string;
  review_episode_id: string;
  rule_set_id: string;
  rule_set_revision: number;
  evidence_snapshot_v2_id: string;
  complete_processing_revision_id: string;
  clauses: EligibilityClauseWire[];
  controls?: EligibilityControlWire[];
}
