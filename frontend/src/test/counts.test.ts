/**
 * 状态计数测试：阶段计数、阻断排序、缺口分类合计。
 * 期望值直接取自 workspace fixture 的 rollup 数值。
 */

import { describe, expect, it } from "vitest";
import { workspaceFixture } from "../api/fixtureAssets";
import {
  countAllStages,
  countByStage,
  isBlockingGap,
  sortEpisodesByBlocking,
  sortEpisodesBySubjectThenStage,
  totalGapCounts,
} from "../domain/counts";
import { mapBoard } from "../domain/mappers";

const board = mapBoard(workspaceFixture);
const episodes = board.episodes;

describe("阶段计数", () => {
  it("筛选期：明确障碍 2、当前节点缺口 2、后续关注 2（与 fixture 一致）", () => {
    const summary = countByStage(episodes, "screening");
    expect(summary.total).toBe(6);
    const byStatus = Object.fromEntries(
      summary.byMainStatus.map((item) => [item.status, item.count]),
    );
    expect(byStatus.clear_barrier).toBe(2);
    expect(byStatus.current_gap).toBe(2);
    expect(byStatus.future_attention).toBe(2);
    expect(byStatus.no_clear_barrier).toBe(0);
    expect(byStatus.conflict).toBe(0);
    expect(byStatus.professional_judgment).toBe(0);
  });

  it("基线期：未发现明确障碍 2、明确障碍 2、当前节点缺口 2", () => {
    const summary = countByStage(episodes, "baseline");
    expect(summary.total).toBe(6);
    const byStatus = Object.fromEntries(
      summary.byMainStatus.map((item) => [item.status, item.count]),
    );
    expect(byStatus.no_clear_barrier).toBe(2);
    expect(byStatus.clear_barrier).toBe(2);
    expect(byStatus.current_gap).toBe(2);
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
