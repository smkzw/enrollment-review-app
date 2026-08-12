/**
 * 映射测试：fixture wire → ViewModel 的确定性转换。
 * 期望值直接取自 contracts/v1/fixtures/uat-phase1-workspace.json 的 fixture/v1 内容。
 */

import { describe, expect, it } from "vitest";
import { workspaceFixture } from "../api/fixtureAssets";
import {
  deriveTaskState,
  mapAction,
  mapBoard,
  mapEpisodeDetail,
  mapEvidenceLocator,
  mapJob,
  mapPatientProfile,
  mapProtocolDiff,
  mapTodayWork,
  mapWorkspace,
} from "../domain/mappers";
import { toId } from "../domain/ids";
import type { JobEventWire } from "../api/wire";

const episodeById = (id: string) => {
  const episode = workspaceFixture.episodes.find(
    (candidate) => candidate.review_episode.review_episode_id === id,
  );
  if (episode === undefined) throw new Error(`fixture 缺少 episode ${id}`);
  return episode;
};

describe("看板映射", () => {
  it("workspace 含 14 个 episode、8 名受试者（6 主要 + 2 模板）、2 个阶段模板", () => {
    const board = mapBoard(workspaceFixture);
    expect(board.episodes).toHaveLength(14);
    expect(board.subjects).toHaveLength(8);
    expect(board.primarySubjectIds).toHaveLength(6);
    expect(board.templateEpisodeIds).toHaveLength(2);
    expect(board.project.projectName).toBe("合成Ⅲ期入排审核项目");
    expect(board.project.protocolVersion).toBe("V1.0");
    expect(board.project.primarySubjectCount).toBe(6);
    expect(board.project.episodeCount).toBe(14);
  });

  it("4 个独立审核节点均有一级入口且为中文阶段词", () => {
    const board = mapBoard(workspaceFixture);
    expect(board.stages.map((stage) => stage.stageLabel)).toEqual([
      "预筛期审核",
      "筛选期审核",
      "导入/洗脱期审核",
      "基线/随机前审核",
    ]);
  });

  it("明确障碍 episode 状态与计数来自 rollup", () => {
    const summary = mapBoard(workspaceFixture).episodes.find(
      (episode) => episode.episodeId === toId("episode-uat-02-screening-barrier"),
    );
    expect(summary).toBeDefined();
    expect(summary?.subjectCode).toBe("UAT-02");
    expect(summary?.mainStatus).toBe("clear_barrier");
    expect(summary?.mainStatusLabel).toBe("明确障碍");
    expect(summary?.sortRank).toBe(0);
    expect(summary?.counts.barrier).toBe(1);
    expect(summary?.counts.currentGap).toBe(0);
  });

  it("缺口/冲突 episode 分类计数与 gap 明细一致", () => {
    const summary = mapBoard(workspaceFixture).episodes.find(
      (episode) =>
        episode.episodeId === toId("episode-uat-03-screening-gap_conflict"),
    );
    expect(summary).toBeDefined();
    expect(summary?.mainStatusLabel).toBe("当前节点缺口");
    expect(summary?.counts.currentGap).toBe(10);
    expect(summary?.counts.conflict).toBe(1);
    expect(summary?.counts.professionalJudgment).toBe(1);
    expect(summary?.counts.futureAttention).toBe(2);
    const recordIncomplete = summary?.counts.gapCounts.find(
      (item) => item.gapType === "record_incomplete",
    );
    expect(recordIncomplete?.count).toBe(2);
    const conflictItem = summary?.counts.gapCounts.find(
      (item) => item.gapType === "source_conflict",
    );
    expect(conflictItem?.label).toBe("来源存在冲突");
    // 降序排序
    const counts = summary?.counts.gapCounts.map((item) => item.count) ?? [];
    expect([...counts].sort((a, b) => b - a)).toEqual(counts);
  });

  it("每名主要受试者都有筛选与基线两个独立节点（不合并）", () => {
    const board = mapBoard(workspaceFixture);
    const primary = board.subjects.filter((subject) =>
      board.primarySubjectIds.includes(subject.subjectId),
    );
    expect(primary).toHaveLength(6);
    for (const subject of primary) {
      const stages = board.episodes
        .filter((episode) => episode.subjectId === subject.subjectId)
        .map((episode) => episode.stage)
        .sort();
      expect(stages, subject.subjectCode).toEqual(["baseline", "screening"]);
    }
  });

  it("模板 episode 为独立预筛/导入阶段（不并入筛选）", () => {
    const board = mapBoard(workspaceFixture);
    const templates = board.episodes.filter((episode) =>
      board.templateEpisodeIds.includes(episode.episodeId),
    );
    expect(templates.map((episode) => episode.stage).sort()).toEqual([
      "pre_screening",
      "run_in",
    ]);
  });
});

describe("证据定位映射", () => {
  it("仅页码定位：无坐标框、无文本范围、有降级原因", () => {
    const episode = episodeById("episode-uat-03-screening-gap_conflict");
    const span = episode.evidence_spans.find(
      (candidate) => candidate.evidence_span_id === "span-uat-03-screening-gap-page",
    );
    expect(span).toBeDefined();
    const locator = mapEvidenceLocator(span!, episode.source_documents);
    expect(locator.precision).toBe("page_only");
    expect(locator.precisionLabel).toBe("仅页码");
    expect(locator.pageNumber).toBe(4);
    expect(locator.bbox).toBeNull();
    expect(locator.textRange).toBeNull();
    expect(locator.degradationReason).toBe("扫描页无法稳定定位字符或坐标。");
    expect(locator.fileName).toBe("合成筛选资料.pdf");
  });

  it("坐标区域定位：bbox 存在、文本范围为空", () => {
    const episode = episodeById("episode-uat-01-screening-clear");
    const span = episode.evidence_spans.find(
      (candidate) => candidate.evidence_span_id === "span-uat-01-screening-clear-age",
    );
    const locator = mapEvidenceLocator(span!, episode.source_documents);
    expect(locator.precisionLabel).toBe("坐标区域");
    expect(locator.bbox).not.toBeNull();
    expect(locator.bbox?.x0).toBeLessThan(locator.bbox?.x1 ?? 0);
    expect(locator.excerpt).toBe("年龄：36岁");
  });

  it("文本范围定位：textRange 存在、bbox 为空", () => {
    const episode = episodeById("episode-uat-01-screening-clear");
    const span = episode.evidence_spans.find(
      (candidate) =>
        candidate.evidence_span_id === "span-uat-01-screening-clear-history",
    );
    const locator = mapEvidenceLocator(span!, episode.source_documents);
    expect(locator.precisionLabel).toBe("文本范围");
    expect(locator.textRange).not.toBeNull();
    expect(locator.textRange!.start).toBeLessThan(locator.textRange!.end);
    expect(locator.bbox).toBeNull();
  });

  it("四级定位在 fixture 中齐备（坐标/文本/摘录/页码）", () => {
    const precisions = new Set(
      workspaceFixture.episodes.flatMap((episode) =>
        episode.evidence_spans.map((span) => span.precision),
      ),
    );
    expect(precisions).toEqual(
      new Set(["bbox", "text_range", "page_excerpt", "page_only"]),
    );
  });
});

describe("行动映射", () => {
  it("行动带对象、责任方、可关闭证据与到期节点中文词", () => {
    const episode = episodeById("episode-uat-03-screening-gap_conflict");
    const wire = episode.actions.find(
      (action) => action.action_id === "action-uat-03-screening-gap-age",
    );
    const view = mapAction(wire!, episode);
    expect(view.subjectCode).toBe("UAT-03");
    expect(view.displayCode).toBe("IN-01");
    expect(view.gapLabel).toBe("记录不完整");
    expect(view.blockingLabel).toBe("阻断当前节点");
    expect(view.blockingBadge).toBe("阻断");
    expect(view.targetPartyLabel).toBe("研究者方");
    expect(view.dueStageLabel).toBe("筛选期");
    expect(view.stateLabel).toBe("待处理");
    expect(view.requestedAction.length).toBeGreaterThan(0);
    expect(view.acceptableEvidence.length).toBeGreaterThan(0);
  });

  it("溯源待办行动不阻断（blocking_level=none）", () => {
    const episode = episodeById("episode-uat-01-screening-clear");
    const wire = episode.actions.find(
      (action) => action.action_id === "action-uat-01-screening-clear-provenance",
    );
    const view = mapAction(wire!, episode);
    expect(view.gapLabel).toBe("溯源待办");
    expect(view.blockingLevel).toBe("none");
    expect(view.targetPartyLabel).toBe("CRA");
  });
});

describe("Patient Profile 映射", () => {
  it("首屏风险事件、泳道与应备证据覆盖", () => {
    const episode = episodeById("episode-uat-03-screening-gap_conflict");
    const profile = mapPatientProfile(
      episode.patient_profile,
      episode.evidence_spans,
      episode.source_documents,
      episode.evidence_expectations,
    );
    expect(profile.subjectId).toBe(toId("subject-uat-03-gap_conflict"));
    expect(profile.highlightedEventIds).toHaveLength(1);
    expect(profile.missingExpectationIds).toHaveLength(5);
    expect(profile.lanes.length).toBeGreaterThan(0);
    for (const lane of profile.lanes) {
      expect(lane.laneLabel.length).toBeGreaterThan(0);
      expect(lane.events.length).toBeGreaterThan(0);
    }
    const expectations = profile.expectations;
    const absent = expectations.find((item) => item.status === "absent");
    expect(absent?.statusLabel).toBe("尚未见到");
    const notDue = expectations.find((item) => item.status === "not_due");
    expect(notDue?.statusLabel).toBe("后续节点尚未到期");
    expect(profile.stale).toBe(false);
  });

  it("风险事件带证据定位与关联规则", () => {
    const episode = episodeById("episode-uat-03-screening-gap_conflict");
    const profile = mapPatientProfile(
      episode.patient_profile,
      episode.evidence_spans,
      episode.source_documents,
      episode.evidence_expectations,
    );
    const eventsWithEvidence = profile.lanes.flatMap((lane) => lane.events);
    expect(eventsWithEvidence.length).toBeGreaterThan(0);
    for (const event of eventsWithEvidence) {
      for (const locator of event.evidence) {
        expect(locator.precisionLabel).toMatch(
          /^(坐标区域|文本范围|页内摘录|仅页码)$/,
        );
      }
    }
  });
});

describe("规则树映射", () => {
  it("EX-01a 为全部满足父逻辑，含任一满足/不满足以下条件子项与例外条件", () => {
    const detail = mapEpisodeDetail(episodeById("episode-uat-03-screening-gap_conflict"));
    const ex01 = detail.rules.find((rule) => rule.officialCode === "EX-01");
    expect(ex01?.kindLabel).toBe("排除条件");
    const component = ex01?.components[0];
    expect(component?.displayCode).toBe("EX-01a");
    expect(component?.expression.kind).toBe("logic");
    if (component?.expression.kind === "logic") {
      expect(component.expression.operatorLabel).toBe("全部满足");
      expect(component.expression.children.length).toBeGreaterThanOrEqual(3);
      const ops = component.expression.children
        .filter((child) => child.kind === "logic")
        .map((child) => (child.kind === "logic" ? child.operatorLabel : ""));
      expect(ops).toContain("任一满足");
      expect(ops).toContain("不满足以下条件");
    }
    expect(component?.exceptionExpression?.kind).toBe("logic");
    expect(component?.decision?.decisionLabel).toMatch(/^(已触发|暂不能明确|需专业判断|存在冲突|尚未到期|不适用)$/);
  });

  it("规则组件带判断、缺口词与证据链接", () => {
    const detail = mapEpisodeDetail(episodeById("episode-uat-03-screening-gap_conflict"));
    const in01 = detail.rules.find((rule) => rule.officialCode === "IN-01");
    const component = in01?.components[0];
    expect(component?.decision?.decisionLabel).toBe("暂不能明确");
    expect(component?.decision?.gapLabels).toContain("记录不完整");
    expect(component?.decision?.blockingLevel).toBe("blocking");
  });

  it("必做检查使用中文显示编号，内部 REQ 标记不进入界面", () => {
    const detail = mapEpisodeDetail(
      episodeById("episode-uat-03-screening-gap_conflict"),
    );
    const required = detail.rules.filter(
      (rule) => rule.kind === "required_procedure",
    );
    expect(required.map((rule) => rule.officialCode)).toEqual([
      "必做-01",
      "必做-02",
    ]);
    expect(required.flatMap((rule) => rule.components.map((item) => item.displayCode)))
      .toEqual(["必做-01a", "必做-02a"]);
    expect(JSON.stringify(required)).not.toContain("REQ-");
  });

  it("时间约束按冻结合同字段显示完整中文，不丢失随机锚点与天数", () => {
    const detail = mapEpisodeDetail(
      episodeById("episode-uat-03-screening-gap_conflict"),
    );
    const component = detail.rules
      .find((rule) => rule.officialCode === "EX-01")
      ?.components[0];
    const predicates = component?.expression.kind === "logic"
      ? component.expression.children.flatMap((child) =>
          child.kind === "logic" ? child.children : [child],
        )
      : [];
    const timeWindows = predicates
      .filter((child) => child.kind === "predicate")
      .map((child) => (child.kind === "predicate" ? child.timeConstraint : null))
      .filter((value): value is string => value !== null);
    expect(timeWindows).toContain("随机前 28 天内");
    expect(JSON.stringify(detail)).not.toMatch(/undefined/);
  });
});

describe("任务状态推导", () => {
  const event = (
    overrides: Partial<JobEventWire>,
  ): JobEventWire => ({
    job_event_id: "e",
    job_id: "job",
    event_type: "created",
    occurred_at: "2026-08-12T12:00:00Z",
    attempt: 1,
    step_id: null,
    checkpoint_id: null,
    progress_completed: 0,
    progress_total: 2,
    retryable: false,
    payload: {},
    schema_version: "fixture/v1",
    ...overrides,
  });

  it("事件序列 → 合同任务状态映射", () => {
    expect(deriveTaskState([event({})])).toBe("queued");
    expect(deriveTaskState([event({}), event({ event_type: "step_started" })])).toBe(
      "running",
    );
    expect(
      deriveTaskState([
        event({}),
        event({ event_type: "step_failed", retryable: true }),
      ]),
    ).toBe("failed");
    expect(
      deriveTaskState([
        event({}),
        event({ event_type: "step_failed", retryable: true, checkpoint_id: "c1" }),
      ]),
    ).toBe("resumable");
    expect(
      deriveTaskState([
        event({}),
        event({ event_type: "step_failed", retryable: false }),
      ]),
    ).toBe("partial");
    expect(
      deriveTaskState([event({}), event({ event_type: "completed" })]),
    ).toBe("completed");
    expect(
      deriveTaskState([
        event({}),
        event({ event_type: "step_failed" }),
        event({ event_type: "cancel_requested" }),
      ]),
    ).toBe("cancelled");
  });

  it("gap 受试者任务经历失败→重试→完成，最终为已完成", () => {
    const episode = episodeById("episode-uat-03-screening-gap_conflict");
    const job = mapJob(episode);
    expect(job).not.toBeNull();
    expect(job?.state).toBe("completed");
    expect(job?.stateLabel).toBe("已完成");
    expect(job?.progressCompleted).toBe(2);
    expect(job?.progressTotal).toBe(2);
    const labels = job?.events.map((item) => item.eventTypeLabel);
    expect(labels).toContain("一项资料整理失败");
    expect(labels).toContain("已安排重试");
  });
});

describe("今日工作与方案差异", () => {
  it("今日工作含到期行动、明确障碍与冲突", () => {
    const today = mapTodayWork(workspaceFixture);
    expect(today.dueActions.length).toBeGreaterThan(0);
    for (const action of today.dueActions) {
      expect(action.stateLabel).toBe("待处理");
      expect(action.blockingLevel).not.toBe("none");
    }
    const barrierCodes = today.barriers.map((item) => item.subjectCode);
    expect(barrierCodes).toEqual(expect.arrayContaining(["UAT-02", "UAT-06"]));
    expect(today.conflicts.length).toBeGreaterThan(0);
    for (const conflict of today.conflicts) {
      expect(conflict.counts.conflict).toBeGreaterThan(0);
    }
  });

  it("方案差异：新增 EX-05、删除必做-02、变化 EX-01，且未发布为草稿", () => {
    const diff = mapProtocolDiff(workspaceFixture.protocol_diff);
    expect(diff.addedRuleCodes).toEqual(["EX-05"]);
    expect(diff.deletedRuleCodes).toEqual(["必做-02"]);
    expect(diff.changedRuleCodes).toEqual(["EX-01"]);
    expect(diff.currentProtocolVersionId).toBe("protocol-v1");
    expect(diff.proposedProtocolVersionId).toBe("protocol-v2-draft");
    expect(diff.sourceRefs).toContain("protocol-v1:p10");
    const changes = mapTodayWork(workspaceFixture).recentChanges;
    expect(changes.some((change) => change.title.includes("方案新增条件 EX-05"))).toBe(
      true,
    );
    expect(
      changes.some((change) => change.title.includes("方案删除条件 必做-02")),
    ).toBe(true);
    expect(JSON.stringify(changes)).not.toContain("REQ-");
  });

  it("workspace 视图完整：board/today/protocolDiff/jobs 齐备", () => {
    const view = mapWorkspace(workspaceFixture);
    expect(view.schemaVersion).toBe("fixture/v1");
    expect(view.board.episodes).toHaveLength(14);
    expect(view.jobs).toHaveLength(14);
    expect(view.reviewDiffs).toHaveLength(0);
  });
});
