/**
 * 映射测试：fixture wire → ViewModel 的确定性转换。
 * 期望值直接取自 contracts/v1/fixtures/uat-phase1-workspace.json 的 fixture/v1 内容。
 */

import { describe, expect, it } from "vitest";
import { workspaceFixture } from "../api/fixtureAssets";
import {
  deriveTaskState,
  formatTimeConstraint,
  mapAction,
  mapBoard,
  mapConflictGroup,
  mapEpisodeDetail,
  mapEvidenceLocator,
  mapJob,
  mapPatientProfile,
  mapProtocolDiff,
  mapTodayWork,
  mapWorkspace,
} from "../domain/mappers";
import { toId } from "../domain/ids";
import type { ConflictGroupWire, JobEventWire, TimeConstraintWire } from "../api/wire";

const episodeById = (id: string) => {
  const episode = workspaceFixture.episodes.find(
    (candidate) => candidate.review_episode.review_episode_id === id,
  );
  if (episode === undefined) throw new Error(`fixture 缺少 episode ${id}`);
  return episode;
};

describe("时间窗中文显示", () => {
  const base: TimeConstraintWire = {
    anchor_type: "first_dose_date",
    direction: "before",
    lower_bound_days: null,
    upper_bound_days: null,
    lower_bound: null,
    upper_bound: null,
    lower_bound_inclusive: true,
    upper_bound_inclusive: true,
    half_life_multiplier: null,
    allow_partial_date: false,
  };

  it("区分超过7天与至少7天", () => {
    expect(formatTimeConstraint({
      ...base,
      lower_bound_days: 7,
      lower_bound_inclusive: false,
    })).toBe("首次给药前超过 7 天");
    expect(formatTimeConstraint({ ...base, lower_bound_days: 7 })).toBe(
      "首次给药前至少 7 天",
    );
  });

  it("区分7天内与少于7天", () => {
    expect(formatTimeConstraint({ ...base, upper_bound_days: 7 })).toBe(
      "首次给药前 7 天内",
    );
    expect(formatTimeConstraint({
      ...base,
      upper_bound_days: 7,
      upper_bound_inclusive: false,
    })).toBe("首次给药前少于 7 天");
  });
});

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
    expect(view.gapLabel).toBe("来源待补充核实");
    expect(view.blockingLevel).toBe("none");
    expect(view.targetPartyLabel).toBe("CRA");
  });
});

describe("Patient Profile 映射", () => {
  it("首屏风险事件、泳道与应备证据覆盖", () => {
    const episode = episodeById("episode-uat-03-screening-gap_conflict");
    const profile = mapPatientProfile(
      episode.patient_profile,
      episode,
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
      episode,
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

  it("区分事件原始依据、审核判断依据、关联规则资料与无独立定位", () => {
    const clearEpisode = episodeById("episode-uat-01-screening-clear");
    const clearProfile = mapPatientProfile(
      clearEpisode.patient_profile,
      clearEpisode,
    );
    const clearEvents = clearProfile.lanes.flatMap((lane) => lane.events);
    expect(
      clearEvents.find((event) => event.title === "当前未发现明确障碍")
        ?.evidenceRelation,
    ).toBe("review_basis");
    expect(
      clearEvents.find((event) => event.title === "阑尾切除术")
        ?.evidenceRelation,
    ).toBe("unavailable");

    const gapEpisode = episodeById("episode-uat-03-screening-gap_conflict");
    const gapProfile = mapPatientProfile(
      gapEpisode.patient_profile,
      gapEpisode,
    );
    const gapEvents = gapProfile.lanes.flatMap((lane) => lane.events);
    expect(
      gapEvents.find((event) => event.title === "合并用药时间轴待核对")
        ?.evidenceRelation,
    ).toBe("related_rule");
    expect(
      gapEvents.find((event) => event.title === "资料缺口与冲突待处理")
        ?.evidenceTargetComponentId,
    ).toBe(toId("component-ex-01"));
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
    expect(component?.decision?.decisionLabel).toMatch(/^(已触发|无法判定|需专业判断|存在冲突|尚未到期|不适用)$/);
  });

  it("规则组件带判断、缺口词与证据链接", () => {
    const detail = mapEpisodeDetail(episodeById("episode-uat-03-screening-gap_conflict"));
    const in01 = detail.rules.find((rule) => rule.officialCode === "IN-01");
    const component = in01?.components[0];
    expect(component?.decision?.decisionLabel).toBe("无法判定");
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

describe("冲突来源并列映射（B1）", () => {
  const gapDetail = () =>
    mapEpisodeDetail(episodeById("episode-uat-03-screening-gap_conflict"));

  it("未解决冲突组并列投影每个事实：立场/值 + 来源文件、页码、摘录、精度", () => {
    const conflicts = gapDetail().conflicts;
    expect(conflicts).toHaveLength(1);
    const group = conflicts[0];
    expect(group.resolved).toBe(false);
    // 两个事实并列，不自动选择来源
    expect(group.facts).toHaveLength(2);
    expect(group.facts.map((fact) => fact.polarityLabel).sort()).toEqual([
      "明确否认",
      "明确记载",
    ]);
    for (const fact of group.facts) {
      expect(fact.evidence.length).toBeGreaterThan(0);
      for (const locator of fact.evidence) {
        expect(locator.fileName).toBe("合成筛选资料.pdf");
        expect(locator.pageNumber).toBe(4);
        expect(locator.precisionLabel).toBe("仅页码");
      }
    }
  });

  it("受影响子项显示编号与资料版本版本为人读中文，原始 ID 不作为标签", () => {
    const group = gapDetail().conflicts[0];
    expect(group.affectedDisplayCodes).toEqual(["EX-01a"]);
    expect(group.snapshotVersion).toBe("第 1 版（2026-08-12 整理）");
    // 显示层投影为中文编号，原始组件 ID 不作为主标签出现
    expect(group.affectedDisplayCodes.join(" ")).not.toMatch(/component-/);
    expect(group.affectedDisplayCodes.join(" ")).not.toMatch(/^REQ-/);
  });

  it("已解决冲突组不被当作未解决冲突展示", () => {
    const resolved: ConflictGroupWire = {
      conflict_group_id: "conflict-resolved",
      fact_ids: [],
      affected_rule_component_ids: ["component-in-01"],
      resolution_evidence_span_ids: [],
      resolved: true,
      schema_version: "fixture/v1",
    };
    const view = mapConflictGroup(resolved, episodeById("episode-uat-03-screening-gap_conflict"));
    expect(view.resolved).toBe(true);
    expect(view.facts).toHaveLength(0);
  });
});

describe("应备证据与资料版本版本映射（I3/I4）", () => {
  it("期望条目投影所属规则编号、具体要求与到期节点", () => {
    const detail = mapEpisodeDetail(
      episodeById("episode-uat-03-screening-gap_conflict"),
    );
    const expectations = detail.expectations;
    const age = expectations.find(
      (item) => item.requirementId === toId("req-age"),
    );
    expect(age?.displayCode).toBe("IN-01");
    expect(age?.requirementDescription).toBe(
      "筛选节点应有可定位的年龄记录。",
    );
    expect(age?.dueStageLabel).toBe("筛选期");
    const risk = expectations.find(
      (item) => item.requirementId === toId("req-composite-risk"),
    );
    expect(risk?.displayCode).toBe("EX-01a");
    const future = expectations.find(
      (item) => item.requirementId === toId("req-future"),
    );
    expect(future?.displayCode).toBe("EX-03a");
    expect(future?.dueStageLabel).toBe("基线/随机前");
  });

  it("资料详情来源文档与冲突组携带同一人读快照版本", () => {
    const episode = episodeById("episode-uat-03-screening-gap_conflict");
    const detail = mapEpisodeDetail(episode);
    expect(detail.sourceDocuments[0].snapshotVersion).toBe(
      "第 1 版（2026-08-12 整理）",
    );
    expect(detail.conflicts[0].snapshotVersion).toBe(
      "第 1 版（2026-08-12 整理）",
    );
  });

  it("Patient Profile 应备证据同样带规则编号与到期节点", () => {
    const episode = episodeById("episode-uat-03-screening-gap_conflict");
    const profile = mapPatientProfile(
      episode.patient_profile,
      episode,
    );
    const age = profile.expectations.find(
      (item) => item.requirementId === toId("req-age"),
    );
    expect(age?.displayCode).toBe("IN-01");
    expect(age?.dueStageLabel).toBe("筛选期");
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
    expect(diff.sourceRefsByRuleCode["EX-05"]).toEqual(["protocol-v2-draft:p12"]);
    expect(diff.sourceRefsByRuleCode["必做-02"]).toEqual(["protocol-v1:p10"]);
    expect(diff.sourceRefsByRuleCode["EX-01"]).toEqual([
      "protocol-v1:p10",
      "protocol-v2-draft:p12",
    ]);
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
