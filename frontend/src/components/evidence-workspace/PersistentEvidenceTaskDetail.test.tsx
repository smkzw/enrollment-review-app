// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
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

describe("真实资料整理详情", () => {
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
    getEvidenceJobDetail.mockResolvedValue({
      status: {
        jobId: "job-1",
        state: "failed_final",
        stateLabel: "未完成，需要处理",
        cancelRequested: false,
        progressCompleted: 1,
        progressTotal: 1,
        recoveryAction: "可以重新处理失败部分。",
        createdAt: "2026-08-21T08:00:00Z",
        updatedAt: "2026-08-21T08:01:00Z",
        steps: [{
          stepId: "evidence_processing",
          name: "evidence_processing",
          state: "failed_final",
          stateLabel: "未完成，需要处理",
          attempt: 1,
          maxAttempts: 2,
          retryable: true,
        }],
        events: [{
          eventId: "event-1",
          eventType: "failed",
          eventTypeLabel: "本次处理未完成",
          occurredAt: "2026-08-21T08:01:00Z",
          attempt: 1,
          retryable: false,
          progressCompleted: 1,
          progressTotal: 1,
        }],
      },
      progress: {
        jobId: "job-1",
        jobState: "failed_final",
        jobStateLabel: "未完成，需要处理",
        totalPages: 5,
        completedPages: 4,
        failedPages: 1,
        pendingPages: 0,
        scopeNote: "当前进度仅覆盖需要文字识别的页面。",
        files: [{
          sourceDocumentVersionId: "doc-1",
          fileName: "筛选病历.pdf",
          pageTotal: 5,
          pageSucceeded: 4,
          pageFailed: 1,
          status: "partial",
          statusLabel: "部分完成",
        }],
      },
    });
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("显示自然中文进度、文件和返回受试者资料入口", async () => {
    render(
      <PersistentEvidenceTaskDetail
        jobId="job-1"
        subjectId="subject-1"
        reviewEpisodeId="episode-1"
      />,
    );

    expect(await screen.findByRole("heading", { name: "本次处理概况" })).toBeInTheDocument();
    expect(screen.getByText("筛选病历.pdf")).toBeInTheDocument();
    expect(screen.getByText(/已完成 4 页 · 需要处理 1 页/)).toBeInTheDocument();
    expect(screen.getByText("整理原始资料")).toBeInTheDocument();
    expect(screen.getByText("SA03009")).toBeInTheDocument();
    expect(screen.getByText(/03｜杭州市第一人民医院/)).toBeInTheDocument();
    expect(screen.getByText("筛选期审核")).toBeInTheDocument();
    expect(screen.getByText("V1.0")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "返回该受试者资料" }))
      .toHaveAttribute("href", "#/subjects/subject-1/evidence?episode=episode-1");
    const body = document.body.textContent ?? "";
    expect(body).not.toContain("evidence_processing");
    expect(body).not.toContain("error_classification");
  });

  it("将 UTC 时间稳定显示为中文本地日期时间", async () => {
    render(
      <PersistentEvidenceTaskDetail
        jobId="job-1"
        subjectId="subject-1"
        reviewEpisodeId="episode-1"
      />,
    );

    await screen.findByRole("heading", { name: "本次处理概况" });
    expect(screen.getAllByText("2026年8月21日 16:01:00")).toHaveLength(2);
    expect(document.body).not.toHaveTextContent("2026-08-21 08:01");
  });

  it("长任务处理期间明确显示服务仍在工作及最近确认时间", async () => {
    const active = await getEvidenceJobDetail();
    getEvidenceJobDetail.mockResolvedValueOnce({
      ...active,
      status: {
        ...active.status,
        state: "running",
        stateLabel: "正在整理",
        recoveryAction: "系统正在继续整理资料。",
        updatedAt: "2026-08-21T08:02:03Z",
      },
    });

    render(
      <PersistentEvidenceTaskDetail
        jobId="job-1"
        subjectId="subject-1"
        reviewEpisodeId="episode-1"
      />,
    );

    expect(
      await screen.findByText(/系统仍在持续处理/),
    ).toBeInTheDocument();
    expect(screen.getAllByText("2026年8月21日 16:02:03")).toHaveLength(2);
  });
});
