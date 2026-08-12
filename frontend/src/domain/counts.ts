/**
 * 状态计数与排序辅助：供项目看板筛选/排序/分类计数使用。
 * 全部为纯函数；计数以 fixture rollup 的确定性数值为准，
 * 前端不重新推导审核结论（后端 rollup 是唯一事实源）。
 */

import { gapTypeLabel, mainStatusLabel, stageLabel } from "./labels";
import type { EpisodeMainStatus, GapType, ReviewStage } from "./enums";
import type {
  EpisodeCountsView,
  EpisodeSummaryView,
  GapCountItemView,
} from "./viewModels";

export interface StageCountSummary {
  stage: ReviewStage;
  stageLabel: string;
  total: number;
  /** 主状态计数：明确障碍/当前节点缺口/存在冲突/需专业判断/后续节点关注/未发现明确障碍 */
  byMainStatus: ReadonlyArray<{ status: EpisodeMainStatus; label: string; count: number }>;
  /** 分类计数汇总（按阻断程度）：明确障碍、记录/证据缺口、冲突、专业判断、溯源待办、后续关注 */
  byCategory: {
    barrier: number;
    gap: number;
    conflict: number;
    professionalJudgment: number;
    provenanceFollowup: number;
    futureAttention: number;
  };
}

export const MAIN_STATUS_ORDER: readonly EpisodeMainStatus[] = [
  "clear_barrier",
  "current_gap",
  "conflict",
  "professional_judgment",
  "future_attention",
  "no_clear_barrier",
];

/** 阻断程度排序：0=明确障碍 … 5=未发现明确障碍，与 fixture sort_rank 语义一致 */
export function blockingRank(episode: EpisodeSummaryView): number {
  return MAIN_STATUS_ORDER.indexOf(episode.mainStatus);
}

/** 按阻断程度升序（明确障碍最前）；同级别按受试者代号稳定排序 */
export function sortEpisodesByBlocking(
  episodes: ReadonlyArray<EpisodeSummaryView>,
): EpisodeSummaryView[] {
  return [...episodes].sort(
    (a, b) =>
      blockingRank(a) - blockingRank(b) ||
      a.subjectCode.localeCompare(b.subjectCode, "zh") ||
      a.episodeId.localeCompare(b.episodeId, "zh"),
  );
}

/** 按受试者代号、阶段顺序稳定排序（看板默认顺序） */
export function sortEpisodesBySubjectThenStage(
  episodes: ReadonlyArray<EpisodeSummaryView>,
): EpisodeSummaryView[] {
  const stageRank: Record<ReviewStage, number> = {
    pre_screening: 0,
    screening: 1,
    run_in: 2,
    baseline: 3,
  };
  return [...episodes].sort(
    (a, b) =>
      a.subjectCode.localeCompare(b.subjectCode, "zh") ||
      stageRank[a.stage] - stageRank[b.stage] ||
      a.episodeId.localeCompare(b.episodeId, "zh"),
  );
}

export function countByStage(
  episodes: ReadonlyArray<EpisodeSummaryView>,
  stage: ReviewStage,
): StageCountSummary {
  const selected = episodes.filter((episode) => episode.stage === stage);
  const byMainStatus = MAIN_STATUS_ORDER.map((status) => ({
    status,
    label: mainStatusLabel[status],
    count: selected.filter((episode) => episode.mainStatus === status).length,
  }));
  const category = (predicate: (counts: EpisodeCountsView) => number) =>
    selected.reduce((sum, episode) => sum + predicate(episode.counts), 0);
  return {
    stage,
    stageLabel: stageLabel[stage],
    total: selected.length,
    byMainStatus,
    byCategory: {
      barrier: category((counts) => counts.barrier),
      gap: category((counts) => counts.currentGap),
      conflict: category((counts) => counts.conflict),
      professionalJudgment: category((counts) => counts.professionalJudgment),
      provenanceFollowup: category((counts) => counts.provenanceFollowup),
      futureAttention: category((counts) => counts.futureAttention),
    },
  };
}

export function countAllStages(
  episodes: ReadonlyArray<EpisodeSummaryView>,
): ReadonlyArray<StageCountSummary> {
  const stages: ReviewStage[] = ["pre_screening", "screening", "run_in", "baseline"];
  return stages.map((stage) => countByStage(episodes, stage));
}

/** 全部对象的缺口类型合计（用于看板分类计数与今日工作） */
export function totalGapCounts(
  episodes: ReadonlyArray<EpisodeSummaryView>,
): ReadonlyArray<GapCountItemView> {
  const totals = new Map<GapType, number>();
  for (const episode of episodes) {
    for (const item of episode.counts.gapCounts) {
      totals.set(item.gapType, (totals.get(item.gapType) ?? 0) + item.count);
    }
  }
  return [...totals.entries()]
    .map(([gapType, count]) => ({
      gapType,
      label: gapTypeLabel[gapType],
      count,
    }))
    .filter((item) => item.count > 0)
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label, "zh"));
}

/** 当前节点缺口是否阻断：gapType 属于阻断类缺口（排除后续到期与溯源待办） */
const NON_BLOCKING_GAPS: ReadonlySet<GapType> = new Set([
  "future_stage_not_due",
  "provenance_followup",
]);

export function isBlockingGap(gapType: GapType): boolean {
  return !NON_BLOCKING_GAPS.has(gapType);
}
