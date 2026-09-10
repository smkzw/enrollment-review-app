/**
 * Patient Profile v2 契约测试专属 wire fixture 构建器（TEST-ONLY）。
 *
 * 只被单元/契约测试 import；绝不从 index.ts 导出，绝不被任何生产模块引用，
 * 不进入正式默认路径（正式路径唯一入口是 patientProfileHttp 的严格运行时解码）。
 * 构建结果保证通过 patientProfileViewModels.ts 的全部严格校验（13 条泳道、
 * highlights ⊆ 条目、条目定位 ⊆ 深链定位、UTC 时间、真实 bbox 坐标帧等）。
 */

import type { LocatorWire } from "../evidence/evidenceProcessingTypes";
import type {
  PatientProfileHistoryWire,
  PatientProfileRevisionWire,
  ProfileDateRangeWire,
  ProfileHighlightWire,
  ProfileItemWire,
  ProfileLaneSectionWire,
  ProfileLaneWire,
} from "./patientProfileTypes";

/** 13 条泳道的稳定展示顺序（与后端 domain contract PROFILE_LANE_ORDER 一致）。 */
export const PROFILE_LANE_ORDER: readonly ProfileLaneWire[] = [
  "study_milestone",
  "demographics",
  "target_disease",
  "symptoms_signs",
  "medical_history",
  "medication",
  "non_drug_treatment",
  "test_exam_score",
  "allergy_infection_immune",
  "reproductive",
  "social_environmental",
  "special_history",
  "evidence_quality",
];

export function makeLocator(overrides: Partial<LocatorWire> = {}): LocatorWire {
  return {
    locator_id: "loc-bp-1",
    page_artifact_id: "page-artifact-1",
    ocr_page_id: "ocr-page-1",
    source_document_version_id: "version-1",
    page_number: 1,
    source_layer: "raw_ocr",
    source_layer_label: "原始识别文字",
    source_text_sha256: "a".repeat(64),
    target_id: "target-1",
    precision: "bbox",
    precision_label: "原文区域",
    degradation_reason: null,
    text_start: null,
    text_end: null,
    excerpt: "基线血压 120/80 mmHg",
    disambiguation: "unique_match",
    locator_algorithm_version: "locator-1",
    authenticity: "authenticated",
    match_confidence: 0.98,
    bbox: { x0: 110, y0: 430, x1: 650, y1: 530 },
    coordinate_frame: {
      space: "page_image_pixels",
      page_width: 1240,
      page_height: 1754,
      rotation: 0,
      transform_version: "frame-1",
    },
    coordinate_transform_version: "transform-1",
    ...overrides,
  };
}

export function makePageOnlyLocator(
  overrides: Partial<LocatorWire> = {},
): LocatorWire {
  return {
    locator_id: "loc-page-1",
    page_artifact_id: "page-artifact-2",
    ocr_page_id: "ocr-page-2",
    source_document_version_id: "version-2",
    page_number: 2,
    source_layer: "native_text",
    source_layer_label: "文档原文",
    source_text_sha256: "b".repeat(64),
    target_id: "target-2",
    precision: "page_only",
    precision_label: "仅页码",
    degradation_reason: "同页出现多处相同文字，无法确定唯一位置。",
    text_start: null,
    text_end: null,
    excerpt: null,
    disambiguation: "repeated_text_degraded",
    locator_algorithm_version: "locator-1",
    authenticity: "degraded",
    match_confidence: null,
    bbox: null,
    coordinate_frame: null,
    coordinate_transform_version: null,
    ...overrides,
  };
}

export function makeDateRange(
  overrides: Partial<ProfileDateRangeWire> = {},
): NonNullable<ProfileItemWire["start_range"]> {
  return {
    source_text: "2026-03",
    precision: "month",
    precision_label: "月",
    lower_bound: "2026-03-01",
    upper_bound: "2026-03-31",
    ...overrides,
  };
}

export function makeFactItem(
  overrides: Partial<ProfileItemWire> = {},
): ProfileItemWire {
  return {
    item_id: "item-fact-1",
    lane: "demographics",
    lane_label: "人口学/基线",
    kind: "fact",
    kind_label: "事实",
    source_id: "fact-source-1",
    source_revision: 1,
    title: "基线血压 120/80 mmHg",
    subtitle: "筛选日测量",
    start_range: makeDateRange(),
    end_range: null,
    duration_status: "single",
    duration_status_label: "单次",
    record_time: "2026-08-22T12:00:00Z",
    source_strength: "current_study_chart_direct_record",
    source_strength_label: "当前研究病历直接记录",
    locator_ids: ["loc-bp-1"],
    requirement_ids: ["req-1"],
    polarity: "affirmed",
    polarity_label: "肯定",
    asserted_object: "血压",
    value: "120/80",
    unit: "mmHg",
    event_type: null,
    medication_name: null,
    category: null,
    indication: null,
    dose: null,
    frequency: null,
    route: null,
    fact_ids: [],
    conflict_member_kind: null,
    conflict_member_ids: [],
    conflict_resolution_revision: null,
    template_id: null,
    expectation_status: null,
    expectation_status_label: null,
    gap_type: null,
    gap_type_label: null,
    gap_detail: null,
    provenance_followup: false,
    provenance_reason: null,
    ...overrides,
  };
}

export function makeEventItem(
  overrides: Partial<ProfileItemWire> = {},
): ProfileItemWire {
  return {
    ...makeFactItem({
      item_id: "item-event-1",
      lane: "symptoms_signs",
      lane_label: "症状体征",
      kind: "event",
      kind_label: "事件",
      source_id: "event-source-1",
      title: "发热",
      event_type: "symptom",
      locator_ids: ["loc-fever-1"],
      polarity: null,
      polarity_label: null,
      asserted_object: null,
      value: null,
      unit: null,
      duration_status: "ongoing",
      duration_status_label: "持续",
    }),
    ...overrides,
  };
}

export function makeExposureItem(
  overrides: Partial<ProfileItemWire> = {},
): ProfileItemWire {
  return {
    ...makeFactItem({
      item_id: "item-exposure-1",
      lane: "medication",
      lane_label: "药物暴露",
      kind: "exposure",
      kind_label: "用药暴露",
      source_id: "exposure-source-1",
      title: "阿司匹林",
      medication_name: "阿司匹林",
      category: "抗血小板药",
      indication: "心血管预防",
      dose: "100 mg",
      frequency: "每日一次",
      route: "口服",
      duration_status: "ongoing",
      duration_status_label: "持续",
      locator_ids: ["loc-page-1"],
    }),
    ...overrides,
  };
}

export function makeConflictItem(
  overrides: Partial<ProfileItemWire> = {},
): ProfileItemWire {
  return {
    ...makeFactItem({
      item_id: "item-conflict-1",
      lane: "evidence_quality",
      lane_label: "证据冲突与资料质量",
      kind: "conflict",
      kind_label: "证据冲突",
      source_id: "conflict-source-1",
      title: "吸烟史来源不一致",
      conflict_member_kind: "fact",
      conflict_member_ids: ["fact-9", "fact-10"],
      conflict_resolution_revision: 2,
      locator_ids: ["loc-bp-1"],
    }),
    ...overrides,
  };
}

export function makeExpectationItem(
  overrides: Partial<ProfileItemWire> = {},
): ProfileItemWire {
  return {
    ...makeFactItem({
      item_id: "item-expectation-1",
      lane: "test_exam_score",
      lane_label: "检验检查/评分",
      kind: "expectation",
      kind_label: "资料期望",
      source_id: "expectation-source-1",
      title: "基线血常规",
      template_id: "template-1",
      expectation_status: "referenced_missing",
      expectation_status_label: "已引用未提供",
      gap_type: "referenced_file_missing",
      gap_type_label: "已引用文件未提供",
      gap_detail: "筛选记录引用基线血常规报告，但资料包中未提供该文件。",
      provenance_followup: true,
      provenance_reason: "需溯源核对",
      locator_ids: ["loc-page-1"],
    }),
    ...overrides,
  };
}

export function makeLaneSection(
  lane: ProfileLaneWire,
  items: ProfileItemWire[],
  overrides: Partial<ProfileLaneSectionWire> = {},
): ProfileLaneSectionWire {
  return {
    lane,
    lane_label: laneLabelFor(lane),
    items,
    ...overrides,
  };
}

/** 泳道中文标签（与后端 PROFILE_LANE_LABELS 一致，fixture 展示用途）。 */
export function laneLabelFor(lane: ProfileLaneWire): string {
  const labels: Record<ProfileLaneWire, string> = {
    study_milestone: "研究节点",
    demographics: "人口学/基线",
    target_disease: "目标疾病",
    symptoms_signs: "症状体征",
    medical_history: "病史",
    medication: "药物暴露",
    non_drug_treatment: "非药物治疗/操作",
    test_exam_score: "检验检查/评分",
    allergy_infection_immune: "过敏/感染/免疫",
    reproductive: "生育",
    social_environmental: "社会环境",
    special_history: "家族史/特殊经历",
    evidence_quality: "证据冲突与资料质量",
  };
  return labels[lane];
}

export function makeHighlight(
  overrides: Partial<ProfileHighlightWire> = {},
): ProfileHighlightWire {
  return {
    item_id: "item-fact-1",
    reasons: ["source_report_abnormal"],
    reason_labels: ["原报告异常"],
    gap_type: null,
    gap_type_label: null,
    detail: null,
    ...overrides,
  };
}

/** 构建通过严格解码的完整 13 泳道 revision wire。 */
export function makeRevision(
  overrides: Partial<PatientProfileRevisionWire> = {},
): PatientProfileRevisionWire {
  const lanes: ProfileLaneSectionWire[] = PROFILE_LANE_ORDER.map((lane) => {
    if (lane === "demographics") {
      return makeLaneSection(lane, [makeFactItem()]);
    }
    if (lane === "symptoms_signs") {
      return makeLaneSection(lane, [makeEventItem()]);
    }
    if (lane === "medication") {
      return makeLaneSection(lane, [makeExposureItem()]);
    }
    if (lane === "evidence_quality") {
      return makeLaneSection(lane, [makeConflictItem()]);
    }
    if (lane === "test_exam_score") {
      return makeLaneSection(lane, [makeExpectationItem()]);
    }
    return makeLaneSection(lane, []);
  });
  return {
    patient_profile_revision_id: "profile-revision-1",
    schema_version: "phase5/v1",
    status: "succeeded",
    status_label: "已生成",
    revision: 1,
    review_stage: "screening",
    review_stage_label: "筛选",
    generated_at: "2026-08-22T12:00:00Z",
    created_at: "2026-08-22T12:00:00Z",
    pending_review_count: 0,
    lanes,
    highlights: [makeHighlight()],
    evidence_locators: [
      makeLocator(),
      makeLocator({
        locator_id: "loc-fever-1",
        target_id: "target-fever-1",
        excerpt: "体温 38.2°C，伴发热",
        bbox: { x0: 110, y0: 620, x1: 650, y1: 730 },
      }),
      makePageOnlyLocator(),
    ],
    evidence_navigation: {
      project_id: "project-1",
      subject_id: "subject-1",
      review_episode_id: "episode-1",
      evidence_snapshot_v2_id: "snapshot-1",
      complete_processing_revision_id: "complete-rev-1",
    },
    ...overrides,
  };
}

export function makeHistory(
  overrides: Partial<PatientProfileHistoryWire> = {},
): PatientProfileHistoryWire {
  return {
    subject_id: "subject-1",
    review_episode_id: "episode-1",
    items: [
      makeRevision({ revision: 1, patient_profile_revision_id: "profile-revision-1" }),
      makeRevision({
        revision: 2,
        patient_profile_revision_id: "profile-revision-2",
        status: "stale",
        status_label: "资料已更新，档案待重新生成",
      }),
    ],
    ...overrides,
  };
}

export function makeErrorEnvelope(): {
  error: {
    code: string;
    title: string;
    detail: string;
    recovery_action: string;
    correlation_id: string;
  };
} {
  return {
    error: {
      code: "NOT_FOUND",
      title: "未找到",
      detail: "该审核节点还没有生成病历档案。",
      recovery_action: "请先完成资料整理并生成档案，或从项目目录选择其他审核节点。",
      correlation_id: "0123456789abcdef0123456789abcdef",
    },
  };
}
