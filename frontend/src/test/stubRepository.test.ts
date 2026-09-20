/**
 * stub 仓储测试：版本化异步接口的确定性、错误边界与中文文案。
 */

import { describe, expect, it } from "vitest";
import {
  createStubRepository,
  getDefaultRepository,
  StubApiError,
} from "../api";
import { toId, type SubjectId } from "../domain/ids";

const repository = createStubRepository();
const subjectId = (id: string): SubjectId => toId<SubjectId>(id);

describe("stub 仓储：workspace 视图", () => {
  it("getWorkspace 解析并保持 fixture/v1 版本", async () => {
    const workspace = await repository.getWorkspace();
    expect(workspace.schemaVersion).toBe("fixture/v1");
    expect(workspace.workspaceId).toBe("uat-phase1-workspace");
    expect(workspace.board.episodes).toHaveLength(14);
    expect(workspace.board.subjects).toHaveLength(8);
    expect(workspace.jobs).toHaveLength(14);
  });

  it("getBoard 项目与阶段信息完整", async () => {
    const board = await repository.getBoard();
    expect(board.project.protocolVersion).toBe("V1.0");
    expect(board.stages).toHaveLength(4);
    expect(board.stages.map((stage) => stage.stageLabel)).toContain("筛选期审核");
  });

  it("getDefaultRepository 返回单例且接口一致", async () => {
    const first = getDefaultRepository();
    const second = getDefaultRepository();
    expect(first).toBe(second);
    const workspace = await first.getWorkspace();
    expect(workspace.board.episodes.length).toBe(14);
  });
});

describe("stub 仓储：episode 与 profile", () => {
  it("明确障碍受试者筛选节点详情", async () => {
    const detail = await repository.getEpisodeDetail(
      subjectId("subject-uat-02-barrier"),
      "screening",
    );
    expect(detail.episode.mainStatusLabel).toBe("明确障碍");
    expect(detail.episode.stageLabel).toBe("筛选期");
    expect(detail.subject.subjectCode).toBe("UAT-02");
    expect(detail.rules.length).toBeGreaterThan(0);
    expect(detail.reviewRunId).not.toBeNull();
  });

  it("缺口受试者基线节点阶段词正确且不混入筛选结论", async () => {
    const detail = await repository.getEpisodeDetail(
      subjectId("subject-uat-03-gap_conflict"),
      "baseline",
    );
    expect(detail.episode.stageLabel).toBe("基线/随机前");
    expect(detail.episode.mainStatusLabel).toBe("当前节点缺口");
  });

  it("Patient Profile 首屏含风险泳道与应备证据", async () => {
    const profile = await repository.getPatientProfile(
      subjectId("subject-uat-03-gap_conflict"),
      "screening",
    );
    expect(profile.missingExpectationIds).toHaveLength(5);
    expect(profile.lanes.length).toBeGreaterThan(0);
    for (const lane of profile.lanes) {
      expect(lane.laneLabel.length).toBeGreaterThan(0);
    }
  });

  it("受试者各审核节点入口齐备（筛选与基线两个独立节点）", async () => {
    const episodes = await repository.getSubjectEpisodes(
      subjectId("subject-uat-05-clear"),
    );
    expect(episodes.map((item) => item.stage).sort()).toEqual([
      "baseline",
      "screening",
    ]);
  });
});

describe("stub 仓储：今日工作、行动与任务", () => {
  it("今日工作到期行动均为中文状态且责任方为合同词", async () => {
    const today = await repository.getTodayWork();
    expect(today.dueActions.length).toBeGreaterThan(0);
    for (const action of today.dueActions) {
      expect(action.stateLabel).toBe("待处理");
      expect(action.blockingLevel).not.toBe("none");
      expect(action.targetPartyLabel).toMatch(
        /^(研究者方|研究协调员|临床监查员|申办方医学或项目组)$/,
      );
      expect(action.gapLabel.length).toBeGreaterThan(0);
    }
  });

  it("getActions 返回全部行动（含溯源待办与后续节点行动）", async () => {
    const [actions, today] = await Promise.all([
      repository.getActions(),
      repository.getTodayWork(),
    ]);
    expect(actions.length).toBeGreaterThan(today.dueActions.length);
    expect(actions.some((action) => action.gapLabel === "来源待补充核实")).toBe(true);
    expect(actions.some((action) => action.blockingLevel === "none")).toBe(
      true,
    );
    for (const action of actions) {
      expect(action.stateLabel.length).toBeGreaterThan(0);
    }
  });

  it("任务视图：全部任务有中文状态词，已完成任务进度完整", async () => {
    const jobs = await repository.getJobs();
    expect(jobs.length).toBe(14);
    const completed = jobs.filter((job) => job.state === "completed");
    expect(completed.length).toBeGreaterThan(0);
    for (const job of completed) {
      expect(job.stateLabel).toBe("已完成");
      expect(job.progressCompleted).toBe(job.progressTotal);
    }
    // 每个任务都可解释当前状态（无内部术语）
    for (const job of jobs) {
      expect(job.stateLabel.length).toBeGreaterThan(0);
    }
  });

  it("方案差异视图带草稿版本与来源定位", async () => {
    const diff = await repository.getProtocolDiff();
    expect(diff.proposedProtocolVersionId).toBe("protocol-v2-draft");
    expect(diff.addedRuleCodes).toEqual(["EX-05"]);
    expect(diff.sourceRefs.length).toBeGreaterThan(0);
  });
});

describe("stub 仓储：错误边界", () => {
  it("未知受试者返回中文错误且不抛堆栈", async () => {
    await expect(
      repository.getSubjectEpisodes(subjectId("subject-does-not-exist")),
    ).rejects.toBeInstanceOf(StubApiError);
    try {
      await repository.getSubjectEpisodes(subjectId("subject-does-not-exist"));
      expect.unreachable("应当抛出 StubApiError");
    } catch (error) {
      expect(error).toBeInstanceOf(StubApiError);
      const apiError = error as StubApiError;
      expect(apiError.code).toBe("subject_not_found");
      expect(apiError.message).toBe("未找到这位受试者。");
      expect(apiError.detail).toContain("subject-does-not-exist");
    }
  });

  it("受试者缺少指定阶段时返回中文错误", async () => {
    await expect(
      repository.getEpisodeDetail(subjectId("subject-uat-01-clear"), "run_in"),
    ).rejects.toBeInstanceOf(StubApiError);
    try {
      await repository.getEpisodeDetail(
        subjectId("subject-uat-01-clear"),
        "run_in",
      );
      expect.unreachable("应当抛出 StubApiError");
    } catch (error) {
      const apiError = error as StubApiError;
      expect(apiError.code).toBe("episode_not_found");
      expect(apiError.message).toBe("未找到该受试者在此审核节点的资料。");
    }
  });
});

describe("stub 仓储：确定性", () => {
  it("重复调用返回相同结果", async () => {
    const [first, second] = await Promise.all([
      repository.getBoard(),
      repository.getBoard(),
    ]);
    expect(JSON.stringify(first)).toBe(JSON.stringify(second));
    const [jobsA, jobsB] = await Promise.all([
      repository.getJobs(),
      repository.getJobs(),
    ]);
    expect(JSON.stringify(jobsA)).toBe(JSON.stringify(jobsB));
  });
});
