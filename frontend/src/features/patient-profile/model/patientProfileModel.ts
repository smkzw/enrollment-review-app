/**
 * Patient Profile v2 领域 ViewModel 适配（Slice 5.6，worker_01）。
 *
 * 消费 patientProfileViewModels.ts 严格解码后的领域视图，产出页面可直接渲染的
 * ViewModel：
 * - 13 条泳道按稳定展示顺序（含空泳道，绝不静默省略临床类别）；
 * - 后端首屏 highlights 原样透出（唯一首屏依据，前端绝不推导）；
 * - 状态语义（生成中/失败/陈旧/已生成空态）供页面状态呈现；
 * - 冲突与资料期望条目分组；定位索引 locatorById 供 Phase 4 原件深链。
 *
 * 本层不推导任何 Phase 6/7 入排结论、行动数量、负责方或通过/不通过语言。
 */

import type {
  LocatorView,
  PatientProfileRevisionView,
  ProfileEvidenceNavigationView,
  ProfileHighlightView,
  ProfileItemView,
  ProfileLaneWire,
  ProfileStatusWire,
} from "../../../api/patient-profile";
import type { ReviewStage } from "../../../domain/enums";

/** 13 条主题泳道的稳定展示顺序（与后端 domain contract PROFILE_LANE_ORDER 一致）。 */
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

/** 档案生成/记录时间统一按本机业务时区展示，不向用户暴露 UTC 技术标记。 */
export function formatProfileDateTime(iso: string | null): string | null {
  if (iso === null) return null;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return null;
  return `${new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date)}（北京时间）`;
}

export interface ProfileLaneModel {
  lane: ProfileLaneWire;
  laneLabel: string;
  items: ReadonlyArray<ProfileItemView>;
  /** 泳道内无结构化条目（空泳道仍展示；是否构成缺口由应备证据覆盖决定，此处不判断）。 */
  readonly isEmpty: boolean;
}

export interface ProfileHighlightModel {
  itemId: string;
  reasons: ReadonlyArray<ProfileHighlightView["reasons"][number]>;
  reasonLabels: ReadonlyArray<string>;
  gapType: ProfileHighlightView["gapType"];
  gapTypeLabel: ProfileHighlightView["gapTypeLabel"];
  detail: ProfileHighlightView["detail"];
}

export interface PatientProfileModel {
  revisionId: string;
  schemaVersion: string;
  status: ProfileStatusWire;
  statusLabel: string;
  revision: number;
  reviewStage: ReviewStage;
  reviewStageLabel: string;
  generatedAt: string | null;
  createdAt: string;
  pendingReviewCount: number;
  /** 13 条泳道，稳定展示顺序，含空泳道。 */
  lanes: ReadonlyArray<ProfileLaneModel>;
  /** 后端首屏突出集合（唯一首屏依据）。 */
  highlights: ReadonlyArray<ProfileHighlightModel>;
  /** 首屏突出条目 ID 集合。 */
  highlightedItemIds: ReadonlySet<string>;
  /** 深链定位（Phase 4 原件查看）。 */
  evidenceLocators: ReadonlyArray<LocatorView>;
  /** 定位索引：locatorId -> LocatorView。 */
  locatorById: ReadonlyMap<string, LocatorView>;
  /** 条目索引：itemId -> ProfileItemView。 */
  itemById: ReadonlyMap<string, ProfileItemView>;
  evidenceNavigation: ProfileEvidenceNavigationView;
  /** 全部条目，按 13 条泳道顺序展平。 */
  items: ReadonlyArray<ProfileItemView>;
  itemCount: number;
  /** 冲突条目（kind=conflict，并列成员、解决修订由条目字段携带）。 */
  conflictItems: ReadonlyArray<ProfileItemView>;
  /** 资料期望条目（kind=expectation）。 */
  expectationItems: ReadonlyArray<ProfileItemView>;

  /** 生成中：档案尚未完成，泳道内容可能为空。 */
  readonly isGenerating: boolean;
  /** 生成失败：显式失败状态记录，不做重试判断。 */
  readonly isFailed: boolean;
  /** 陈旧：资料已更新，档案待重新生成（仍展示历史档案内容）。 */
  readonly isStale: boolean;
  /** 已生成但没有任何结构化条目（空档案态，区别于生成中/失败）。 */
  readonly isEmpty: boolean;
}

/** 解析条目的深链定位：返回条目 locator_ids 在深链中的真实定位（未命中则跳过）。 */
export function locatorsForItem(
  model: PatientProfileModel,
  item: ProfileItemView,
): ReadonlyArray<LocatorView> {
  const resolved: LocatorView[] = [];
  for (const locatorId of item.locatorIds) {
    const locator = model.locatorById.get(locatorId);
    if (locator !== undefined) resolved.push(locator);
  }
  return resolved;
}

export function adaptPatientProfile(
  revision: PatientProfileRevisionView,
): PatientProfileModel {
  const laneByKey = new Map<ProfileLaneWire, PatientProfileRevisionView["lanes"][number]>();
  for (const section of revision.lanes) {
    laneByKey.set(section.lane, section);
  }
  const lanes: ReadonlyArray<ProfileLaneModel> = PROFILE_LANE_ORDER.map(
    (lane) => {
      const section = laneByKey.get(lane);
      if (section === undefined) {
        throw new Error(`病历档案缺少主题分区：${lane}`);
      }
      return {
        lane: section.lane,
        laneLabel: section.laneLabel,
        items: section.items,
        isEmpty: section.items.length === 0,
      };
    },
  );
  const items = lanes.flatMap((lane) => lane.items);
  const locatorById = new Map<string, LocatorView>();
  for (const locator of revision.evidenceLocators) {
    locatorById.set(locator.locatorId, locator);
  }
  const itemById = new Map<string, ProfileItemView>();
  for (const item of items) {
    itemById.set(item.itemId, item);
  }
  const highlightedItemIds = new Set(
    revision.highlights.map((highlight) => highlight.itemId),
  );
  const conflictItems = items.filter((item) => item.kind === "conflict");
  const expectationItems = items.filter((item) => item.kind === "expectation");
  const status = revision.status;

  return {
    revisionId: revision.revisionId,
    schemaVersion: revision.schemaVersion,
    status,
    statusLabel: revision.statusLabel,
    revision: revision.revision,
    reviewStage: revision.reviewStage,
    reviewStageLabel: revision.reviewStageLabel,
    generatedAt: revision.generatedAt,
    createdAt: revision.createdAt,
    pendingReviewCount: revision.pendingReviewCount,
    lanes,
    highlights: revision.highlights.map((highlight) => ({
      itemId: highlight.itemId,
      reasons: highlight.reasons,
      reasonLabels: highlight.reasonLabels,
      gapType: highlight.gapType,
      gapTypeLabel: highlight.gapTypeLabel,
      detail: highlight.detail,
    })),
    highlightedItemIds,
    evidenceLocators: revision.evidenceLocators,
    locatorById,
    itemById,
    evidenceNavigation: revision.evidenceNavigation,
    items,
    itemCount: items.length,
    conflictItems,
    expectationItems,
    isGenerating: status === "generating",
    isFailed: status === "failed",
    isStale: status === "stale",
    isEmpty: status === "succeeded" && items.length === 0,
  };
}
