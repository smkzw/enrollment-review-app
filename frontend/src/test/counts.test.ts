/**
 * 状态计数测试：阶段计数、阻断排序、缺口分类合计。
 * 期望值直接取自 workspace fixture 的 rollup 数值。
 */

import { describe, expect, it } from "vitest";
import { workspaceFixture } from "../api/fixtureAssets";
import {
  countAllStages,
  countByStage,
  episodeMatchesCategory,
  isAdditiveCategory,
  isBlockingGap,
  isProvenanceAction,
  isTodayWorkDueAction,
  sortEpisodesByBlocking,
  sortEpisodesBySubjectThenStage,
  totalGapCounts,
} from "../domain/counts";
import { mapAction, mapBoard, mapTodayWork } from "../domain/mappers";

const board = mapBoard(workspaceFixture);
const episodes = board.episodes;

describe("阶段计数", () => {
  it("筛选期：主状态 2/2/2，存在冲突与需专业判断按可叠加类别各计 2", () => {
    const summary = countByStage(episodes, "screening");
    expect(summary.total).toBe(6);
    const byStatus = Object.fromEntries(
      summary.byMainStatus.map((item) => [item.status, item.count]),
    );
    expect(byStatus.clear_barrier).toBe(2);
    expect(byStatus.current_gap).toBe(2);
    expect(byStatus.future_attention).toBe(2);
    expect(byStatus.no_clear_barrier).toBe(0);
    // 冲突/专业判断是可叠加类别：UAT-03、UAT-04 两个节点命中（主状态为当前节点缺口）
    expect(byStatus.conflict).toBe(2);
    expect(byStatus.professional_judgment).toBe(2);
  });

  it("基线期：未发现明确障碍 2、明确障碍 2、当前节点缺口 2，冲突/专业判断各 2", () => {
    const summary = countByStage(episodes, "baseline");
    expect(summary.total).toBe(6);
    const byStatus = Object.fromEntries(
      summary.byMainStatus.map((item) => [item.status, item.count]),
    );
    expect(byStatus.no_clear_barrier).toBe(2);
    expect(byStatus.clear_barrier).toBe(2);
    expect(byStatus.current_gap).toBe(2);
    expect(byStatus.conflict).toBe(2);
    expect(byStatus.professional_judgment).toBe(2);
  });

  it("阶段分类计数与 rollup 合计一致（六类分开）", () => {
    const summary = countByStage(episodes, "screening");
    expect(summary.byCategory.barrier).toBe(2);
    expect(summary.byCategory.gap).toBe(20);
    expect(summary.byCategory.conflict).toBe(2);
    expect(summary.byCategory.professionalJudgment).toBe(2);
    expect(summary.byCategory.provenanceFollowup).toBe(2);
    expect(summary.byCategory.futureAttention).toBe(12);
  });

  it("四个阶段计数齐备且阶段词为中文", () => {
    const all = countAllStages(episodes);
    expect(all.map((item) => item.stageLabel)).toEqual([
      "预筛期",
      "筛选期",
      "导入/洗脱期",
      "基线/随机前",
    ]);
    expect(all.reduce((sum, item) => sum + item.total, 0)).toBe(14);
  });
});

describe("阻断排序", () => {
  it("按阻断程度升序：明确障碍在前，未发现明确障碍在后", () => {
    const sorted = sortEpisodesByBlocking(episodes);
    const rank = (episodeId: string) =>
      sorted.findIndex((item) => item.episodeId === episodeId);
    expect(rank("episode-uat-02-screening-barrier")).toBeLessThan(
      rank("episode-uat-03-screening-gap_conflict"),
    );
    expect(rank("episode-uat-03-screening-gap_conflict")).toBeLessThan(
      rank("episode-uat-01-screening-clear"),
    );
    expect(rank("episode-uat-01-baseline-clear")).toBeGreaterThan(
      rank("episode-uat-06-baseline-barrier"),
    );
    // 稳定：长度不变
    expect(sorted).toHaveLength(14);
  });

  it("默认看板顺序：受试者代号 + 阶段顺序，筛选在前基线在后", () => {
    const sorted = sortEpisodesBySubjectThenStage(episodes);
    const uat01 = sorted.filter((item) => item.subjectCode === "UAT-01");
    expect(uat01.map((item) => item.stage)).toEqual(["screening", "baseline"]);
    const first = sorted[0];
    expect(first.subjectCode).toBe("UAT-01");
  });
});

describe("缺口类型合计与阻断语义", () => {
  it("全部对象缺口合计与 fixture 一致（记录不完整 10、来源冲突 5）", () => {
    const totals = totalGapCounts(episodes);
    const byType = Object.fromEntries(
      totals.map((item) => [item.gapType, item.count]),
    );
    expect(byType.record_incomplete).toBe(10);
    expect(byType.source_conflict).toBe(5);
    expect(byType.professional_judgment).toBe(5);
    expect(byType.provenance_followup).toBe(8);
    expect(byType.future_stage_not_due).toBe(28);
    // 降序排列
    const counts = totals.map((item) => item.count);
    expect([...counts].sort((a, b) => b - a)).toEqual(counts);
  });

  it("溯源待办与后续到期不阻断；其余缺口类型阻断", () => {
    expect(isBlockingGap("provenance_followup")).toBe(false);
    expect(isBlockingGap("future_stage_not_due")).toBe(false);
    expect(isBlockingGap("record_incomplete")).toBe(true);
    expect(isBlockingGap("source_conflict")).toBe(true);
    expect(isBlockingGap("required_procedure_not_done")).toBe(true);
    expect(isBlockingGap("professional_judgment")).toBe(true);
  });
});

describe("关注类别共享匹配（B2 修复）", () => {
  it("存在冲突与需专业判断是可叠加类别，其余类别不是", () => {
    expect(isAdditiveCategory("conflict")).toBe(true);
    expect(isAdditiveCategory("professional_judgment")).toBe(true);
    expect(isAdditiveCategory("clear_barrier")).toBe(false);
    expect(isAdditiveCategory("current_gap")).toBe(false);
    expect(isAdditiveCategory("future_attention")).toBe(false);
    expect(isAdditiveCategory("no_clear_barrier")).toBe(false);
  });

  it("计数大于零时对应筛选必命中：冲突或专业判断筛选结果不为空（不变量）", () => {
    const conflictEpisodes = episodes.filter(
      (episode) => episode.counts.conflict > 0,
    );
    const judgmentEpisodes = episodes.filter(
      (episode) => episode.counts.professionalJudgment > 0,
    );
    expect(conflictEpisodes.length).toBeGreaterThan(0);
    expect(judgmentEpisodes.length).toBeGreaterThan(0);
    for (const episode of conflictEpisodes) {
      expect(episodeMatchesCategory(episode, "conflict")).toBe(true);
    }
    for (const episode of judgmentEpisodes) {
      expect(episodeMatchesCategory(episode, "professional_judgment")).toBe(
        true,
      );
    }
  });

  it("可叠加命中：主状态为缺口/障碍的节点可同时命中冲突与专业判断", () => {
    const gapConflict = episodes.find(
      (episode) => episode.episodeId === "episode-uat-03-screening-gap_conflict",
    );
    expect(gapConflict).toBeDefined();
    expect(gapConflict?.mainStatus).toBe("current_gap");
    expect(episodeMatchesCategory(gapConflict as never, "current_gap")).toBe(
      true,
    );
    expect(episodeMatchesCategory(gapConflict as never, "conflict")).toBe(true);
    expect(
      episodeMatchesCategory(gapConflict as never, "professional_judgment"),
    ).toBe(true);
  });

  it("非叠加类别只按主状态唯一命中", () => {
    const clearBarrier = episodes.find(
      (episode) => episode.episodeId === "episode-uat-02-screening-barrier",
    );
    expect(clearBarrier).toBeDefined();
    expect(episodeMatchesCategory(clearBarrier as never, "clear_barrier")).toBe(
      true,
    );
    // 该节点未发现冲突，不命中冲突类别
    expect(episodeMatchesCategory(clearBarrier as never, "conflict")).toBe(
      false,
    );
  });

  it("看板计数与筛选共用同一匹配：筛选期冲突计数等于命中节点数", () => {
    const summary = countByStage(episodes, "screening");
    const conflictCount = summary.byMainStatus.find(
      (item) => item.status === "conflict",
    )?.count;
    const matched = episodes.filter(
      (episode) =>
        episode.stage === "screening" &&
        episodeMatchesCategory(episode, "conflict"),
    ).length;
    expect(conflictCount).toBe(matched);
    expect(matched).toBeGreaterThan(0);
  });
});

describe("行动分类与今日工作口径（I1/I5 修复）", () => {
  it("溯源提醒按缺口类型独立识别，不并入阻断或笼统关注", () => {
    const allActionViews = workspaceFixture.episodes.flatMap((episode) =>
      episode.actions.map((action) => mapAction(action, episode)),
    );
    const provenanceViews = allActionViews.filter(isProvenanceAction);
    expect(provenanceViews.length).toBeGreaterThan(0);
    for (const action of provenanceViews) {
      expect(action.gapType).toBe("provenance_followup");
      expect(action.blockingLevel).toBe("none");
    }
    // 其余行动不属于溯源提醒类别
    const nonProvenance = allActionViews.filter(
      (action) => !isProvenanceAction(action),
    );
    expect(
      nonProvenance.every((action) => action.gapType !== "provenance_followup"),
    ).toBe(true);
  });

  it("今日工作只含当前节点到期、开放且需关注或阻断的行动", () => {
    const today = mapTodayWork(workspaceFixture);
    expect(today.dueActions.length).toBeGreaterThan(0);
    for (const action of today.dueActions) {
      expect(action.state).toBe("open");
      expect(action.blockingLevel).not.toBe("none");
      expect(isProvenanceAction(action)).toBe(false);
    }
    // 与纯谓词一致：任一到期行动在其节点上命中
    const board = mapBoard(workspaceFixture);
    const episode = board.episodes.find(
      (item) => item.episodeId === today.dueActions[0].episodeId,
    );
    expect(episode).toBeDefined();
    expect(
      isTodayWorkDueAction(today.dueActions[0], episode?.stage as never),
    ).toBe(true);
  });

  it("溯源待办行动（不阻断）不属于今日工作口径", () => {
    const today = mapTodayWork(workspaceFixture);
    expect(
      today.dueActions.every(
        (action) => action.gapType !== "provenance_followup",
      ),
    ).toBe(true);
  });
});
