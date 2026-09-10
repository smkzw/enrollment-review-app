// @vitest-environment jsdom

/** 选择性视觉核验在证据工作台持久任务详情中的中文状态、重试与取消文案（无内部字段渲染）。 */

import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PersistentEvidenceTaskDetail } from "./PersistentEvidenceTaskDetail";

const { getEvidenceJobDetail, retryEvidenceJob, getEvidenceContext } = vi.hoisted(() => ({
  getEvidenceJobDetail: vi.fn(),
  retryEvidenceJob: vi.fn(),
  getEvidenceContext: vi.fn(),
}));

vi.mock("../../api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api")>();
  return { ...actual, getCatalogRepository: () => ({ getEvidenceContext }) };
});

vi.mock("../../api/evidence", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/evidence")>();
  return { ...actual, getEvidenceJobDetail, retryEvidenceJob };
});

function selectiveVisionStatus(state: string, stateLabel: string, recoveryAction: string) {
  return {
    status: {
      jobId: "job-svo-1",
      state,
      stateLabel,
      cancelRequested: state === "cancel_requested",
      progressCompleted: 0,
      progressTotal: 1,
      recoveryAction,
      createdAt: "2026-08-31T12:00:00Z",
      updatedAt: "2026-08-31T12:01:00Z",
      steps: [
        {
          stepId: "run_selective_vision",
          name: "选择性视觉后处理",
          state,
          stateLabel,
          attempt: 1,
          maxAttempts: 3,
          retryable: state === "failed_final" || state === "failed_retryable",
        },
      ],
      events: [
        {
          eventId: "event-svo-1",
          eventType: "step_failed",
          eventTypeLabel: "本项处理未完成",
          occurredAt: "2026-08-31T12:01:00Z",
          attempt: 1,
          retryable: false,
          progressCompleted: 0,
          progressTotal: 1,
        },
      ],
    },
    progress: {
      jobId: "job-svo-1",
      jobState: state,
      jobStateLabel: stateLabel,
      totalPages: 1,
      completedPages: 0,
      failedPages: state === "failed_final" ? 1 : 0,
      pendingPages: state === "failed_final" ? 0 : 1,
      scopeNote: "本次核验覆盖扫描件、复杂表格与识别低置信页面。",
      files: [],
    },
  };
}

describe("证据工作台中的选择性视觉核验任务", () => {
  beforeEach(() => {
    vi.stubEnv("TZ", "Asia/Shanghai");
    window.location.hash = "";
    getEvidenceJobDetail.mockReset();
    retryEvidenceJob.mockReset();
    getEvidenceContext.mockReset();
    getEvidenceContext.mockResolvedValue({
      project: {
        projectId: "project-1",
        projectCode: "D001-02",
        projectName: "评价 D001 治疗斑块状银屑病的临床研究",
        studyPhase: "II",
        studyPhaseLabel: "Ⅱ期",
        protocolCode: "D001-02-002",
        officialVersion: "V1.0",
        officialDateValue: "2025-12-10",
        officialDatePrecision: "day",
        ruleSetId: "rules-1",
        ruleSetRevision: 1,
      },
      subject: {
        subjectId: "subject-1",
        subjectCode: "SA03009",
        projectId: "project-1",
        centerCode: "03",
        centerName: "杭州市第一人民医院",
        sex: null,
        ageYears: null,
        revision: 1,
      },
      episode: {
        reviewEpisodeId: "episode-1",
        subjectId: "subject-1",
        projectId: "project-1",
        ruleSetId: "rules-1",
        studyPhase: "II",
        studyPhaseLabel: "Ⅱ期",
        stage: "screening",
        stageLabel: "筛选期审核",
        protocolVersionId: "protocol-1",
        ruleSetRevision: 1,
        evidenceSnapshotId: null,
        workflowStageId: "stage-1",
        workflowStageLabel: "筛选期审核",
        visitWindow: "D-28~D-1",
        latestEvidenceSnapshotId: null,
        activeEvidenceSnapshotId: null,
        activeEvidenceProcessingRevisionId: null,
        anchorDates: {},
        dueAt: null,
        revision: 1,
      },
    });
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("失败任务显示中文状态、步骤名与失败范围恢复入口，不渲染任何工程字段", async () => {
    getEvidenceJobDetail.mockResolvedValue(
      selectiveVisionStatus("failed_final", "未完成，需要处理", "可以点击“重新处理失败部分”；已完成内容不会重复处理。"),
    );

    render(
      <PersistentEvidenceTaskDetail
        jobId="job-svo-1"
        subjectId="subject-1"
        reviewEpisodeId="episode-1"
      />,
    );

    expect(await screen.findByRole("heading", { name: "本次处理概况" })).toBeInTheDocument();
    expect(screen.getByText("选择性视觉后处理")).toBeInTheDocument();
    expect(
      screen.getByText("可以点击“重新处理失败部分”；已完成内容不会重复处理。"),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "重新处理失败部分" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "刷新进度" })).toBeInTheDocument();

    const body = document.body.textContent ?? "";
    for (const marker of [
      "run_selective_vision",
      "selective_vision_postprocess",
      "SELECTIVE_VISION_PLAN_VERSION_UNSUPPORTED",
      "failed_final",
      "error_code",
      "error_classification",
      "payload",
      "lease",
      "mock-vlm",
      "prompt_tokens",
    ]) {
      expect(body).not.toContain(marker);
    }
  });

  it("点击重新处理调用重试接口并刷新到最新状态", async () => {
    const failed = selectiveVisionStatus(
      "failed_final",
      "未完成，需要处理",
      "可以点击“重新处理失败部分”；已完成内容不会重复处理。",
    );
    const queued = selectiveVisionStatus("queued", "等待处理", "无需操作，正在等待开始。");
    getEvidenceJobDetail.mockResolvedValueOnce(failed).mockResolvedValue(queued);
    retryEvidenceJob.mockResolvedValue(undefined);

    render(
      <PersistentEvidenceTaskDetail
        jobId="job-svo-1"
        subjectId="subject-1"
        reviewEpisodeId="episode-1"
      />,
    );

    fireEvent.click(await screen.findByRole("button", { name: "重新处理失败部分" }));

    expect(retryEvidenceJob).toHaveBeenCalledWith("job-svo-1");
    // 刷新后进入 queued 视图：恢复动作文案切换，重试入口消失。
    expect(await screen.findByText(/无需操作，正在等待开始/)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "重新处理失败部分" }),
    ).not.toBeInTheDocument();
  });

  it("取消请求受理后显示正在停止的中文反馈，且不提供重试入口", async () => {
    getEvidenceJobDetail.mockResolvedValue(
      selectiveVisionStatus(
        "cancel_requested",
        "正在停止",
        "停止请求已受理，将在当前内容保存完成后停止。",
      ),
    );

    render(
      <PersistentEvidenceTaskDetail
        jobId="job-svo-1"
        subjectId="subject-1"
        reviewEpisodeId="episode-1"
      />,
    );

    expect(await screen.findByText(/系统正在按安全节点停止本次整理/)).toBeInTheDocument();
    expect(screen.getByText(/停止请求已受理/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "重新处理失败部分" })).not.toBeInTheDocument();
  });
});
