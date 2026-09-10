/**
 * Patient Profile v2 HTTP 契约（与 app/api/v2/patient_profile_schemas.py 对齐，Slice 5.5）。
 * 只描述网络载荷的原始结构；组件/页面经 patientProfileViewModels.ts 严格运行时解码后
 * 消费领域模型，不直接使用 wire 结构（spec: type-safety）。
 *
 * 服务端为每个稳定机器值投影自然中文标签（*_label），前端不自行翻译内部枚举；
 * 标签缺失或空白由运行时解码直接拒绝。
 *
 * 证据定位载荷（evidence_locators）与 Phase 4 evidence processing 的 LocatorDTO 相同，
 * 这里复用 Phase 4 的 LocatorWire 类型，不重复定义；定位真实性门禁校验与解码保持一致。
 *
 * 本契约不包含任何入排结论/行动/负责方字段（Phase 6/7 边界），前端绝不自行推导。
 */

import type { LocatorWire } from "../evidence/evidenceProcessingTypes";
import type { ReviewStage } from "../../domain/enums";

/** Profile revision 状态机器值：界面文案一律使用 status_label。 */
export type ProfileStatusWire =
  | "succeeded"
  | "generating"
  | "failed"
  | "stale";

/** 13 条主题泳道的稳定机器值（展示顺序见 features/patient-profile/model）。 */
export type ProfileLaneWire =
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

/** Profile 条目引用的已发布 v2 实体类型。 */
export type ProfileItemKindWire =
  | "fact"
  | "event"
  | "exposure"
  | "conflict"
  | "expectation";

/** 部分日期精度。 */
export type ProfileDatePrecisionWire = "day" | "month" | "year" | "unknown";

/** 事实极性。 */
export type ProfileFactPolarityWire = "affirmed" | "negated" | "unknown";

/** 时间线持续状态。 */
export type ProfileDurationStatusWire =
  | "ongoing"
  | "ended"
  | "intermittent"
  | "single"
  | "unknown";

/** 来源强度。 */
export type ProfileSourceStrengthWire =
  | "contemporaneous_objective_result"
  | "historical_primary_document"
  | "current_study_chart_direct_record"
  | "screening_record_transcription"
  | "unverifiable_source";

/** 资料期望状态。 */
export type ProfileExpectationStatusWire =
  | "observed"
  | "observed_weak"
  | "referenced_missing"
  | "absent"
  | "not_due";

/** 资料缺口类型。 */
export type ProfileGapTypeWire =
  | "record_incomplete"
  | "description_insufficient"
  | "historical_source_unavailable"
  | "referenced_file_missing"
  | "required_procedure_not_done"
  | "result_fields_missing"
  | "date_or_anchor_missing"
  | "professional_judgment"
  | "source_conflict"
  | "ocr_or_parse_risk"
  | "interpretation_conflict"
  | "future_stage_not_due"
  | "provenance_followup";

/** 首屏突出原因的完整允许集（显式结构化，绝不从阈值/关键词推导）。 */
export type ProfileHighlightReasonWire =
  | "unresolved_conflict"
  | "current_due_expectation_gap"
  | "weak_source_positive_long_term_history"
  | "structured_ocr_or_parse_risk"
  | "source_report_abnormal"
  | "source_report_critical"
  | "source_report_trend";

/** 冲突条目并列的成员类型。 */
export type ProfileConflictMemberKindWire = "fact" | "event" | "exposure";

/** 部分日期范围：来源原文、精度机器值/中文标签与确定性上下界。 */
export interface ProfileDateRangeWire {
  source_text: string | null;
  precision: ProfileDatePrecisionWire | null;
  precision_label: string | null;
  lower_bound: string | null;
  upper_bound: string | null;
}

/** 证据深链导航上下文：冻结权威元组中的 Phase 4 导航身份。 */
export interface ProfileEvidenceNavigationWire {
  project_id: string;
  subject_id: string;
  review_episode_id: string;
  evidence_snapshot_v2_id: string;
  complete_processing_revision_id: string;
}

/** 单条 Profile 条目：机器值原样 + 中文标签，不发明临床措辞。 */
export interface ProfileItemWire {
  item_id: string;
  lane: ProfileLaneWire;
  lane_label: string;
  kind: ProfileItemKindWire;
  kind_label: string;
  source_id: string;
  source_revision: number;
  title: string;
  subtitle: string | null;

  // 时间线（事件发生时间与记录时间分离）
  start_range: ProfileDateRangeWire | null;
  end_range: ProfileDateRangeWire | null;
  duration_status: ProfileDurationStatusWire | null;
  duration_status_label: string | null;
  record_time: string | null;

  // 溯源与定位
  source_strength: ProfileSourceStrengthWire | null;
  source_strength_label: string | null;
  locator_ids: string[];
  requirement_ids: string[];

  // 事实
  polarity: ProfileFactPolarityWire | null;
  polarity_label: string | null;
  asserted_object: string | null;
  value: boolean | number | string | null;
  unit: string | null;

  // 事件
  event_type: string | null;

  // 暴露
  medication_name: string | null;
  category: string | null;
  indication: string | null;
  dose: string | null;
  frequency: string | null;
  route: string | null;

  // 实体引用闭包
  fact_ids: string[];

  // 冲突
  conflict_member_kind: ProfileConflictMemberKindWire | null;
  conflict_member_ids: string[];
  conflict_resolution_revision: number | null;

  // 期望
  template_id: string | null;
  expectation_status: ProfileExpectationStatusWire | null;
  expectation_status_label: string | null;
  gap_type: ProfileGapTypeWire | null;
  gap_type_label: string | null;
  gap_detail: string | null;
  provenance_followup: boolean;
  provenance_reason: string | null;
}

/** 一条主题泳道：泳道机器值/中文标签 + 该泳道内确定排序的条目（可为空）。 */
export interface ProfileLaneSectionWire {
  lane: ProfileLaneWire;
  lane_label: string;
  items: ProfileItemWire[];
}

/** 首屏突出：条目身份 + 显式结构化原因（机器值与中文标签并列）。 */
export interface ProfileHighlightWire {
  item_id: string;
  reasons: ProfileHighlightReasonWire[];
  reason_labels: string[];
  gap_type: ProfileGapTypeWire | null;
  gap_type_label: string | null;
  detail: string | null;
}

/** 不可变 Patient Profile revision（状态/历史/证据深链一次给全）。 */
export interface PatientProfileRevisionWire {
  patient_profile_revision_id: string;
  schema_version: "phase5/v1";
  status: ProfileStatusWire;
  status_label: string;
  revision: number;
  review_stage: ReviewStage;
  review_stage_label: string;
  generated_at: string | null;
  created_at: string;
  pending_review_count: number;
  lanes: ProfileLaneSectionWire[];
  highlights: ProfileHighlightWire[];
  evidence_locators: LocatorWire[];
  evidence_navigation: ProfileEvidenceNavigationWire;
}

/** 审核节点 Profile 历史：全部 revision 按 revision 升序。 */
export interface PatientProfileHistoryWire {
  subject_id: string;
  review_episode_id: string;
  items: PatientProfileRevisionWire[];
}

/** 服务端错误信封（errors.py）：非 2xx 时 body 为 { error: {...} }。 */
export interface PatientProfileErrorEnvelope {
  error: {
    code: string;
    title: string;
    detail?: string;
    recovery_action?: string;
    correlation_id?: string;
    context?: unknown;
  };
}
