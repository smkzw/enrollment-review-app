// @vitest-environment jsdom

import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import type { ProfileEvidenceNavigationView } from "../../api/patient-profile";
import type { JudgmentSearchHttp } from "../../api/judgment-search/judgmentSearchHttp";
import { JudgmentSearchCard } from "./JudgmentSearchCard";

const navigation: ProfileEvidenceNavigationView = {
  projectId: "project-1",
  subjectId: "subject-1",
  reviewEpisodeId: "episode-1",
  evidenceSnapshotV2Id: "snapshot-1",
  completeProcessingRevisionId: "revision-1",
};

const runningStatus = {
  jobId: "job-1",
  state: "running" as const,
  stateLabel: "正在处理",
  totalPages: 3,
  completedReads: 1,
  totalReads: 3,
  requirementResults: [
    {
      requirementId: "req-1",
      status: "coverage_incomplete" as const,
      statusLabel: "检索尚未完成（部分页面未读取或内容不清）",
      foundCandidateCount: 0,
    },
  ],
  canResume: false,
};

const candidate = {
  lane: "main-A" as const,
  channel: "handwritten" as const,
  sourceDocumentVersionId: "doc-1",
  pageArtifactId: "page-1",
  pageNumber: 2,
  excerpts: [
    {
      text: "研究者判断文字",
      bbox: null,
      coordinateConvention: "unverified" as const,
      uncertaintyNote: null,
    },
  ],
};

const results = {
  jobId: "job-1",
  state: "completed" as const,
  searchedPageCount: 3,
  results: [
    {
      requirementId: "req-1",
      status: "candidates_present" as const,
      statusLabel: "已发现疑似研究者书面判断的内容，待人工核对原件",
      foundCandidates: [candidate],
      incompletePages: [],
    },
  ],
};

function makeApi(overrides: Partial<JudgmentSearchHttp> = {}): JudgmentSearchHttp {
  return {
    start: vi.fn(async () => ({
      jobId: "job-1",
      state: "queued" as const,
      stateLabel: "等待处理",
      created: true,
    })),
    status: vi.fn(async () => runningStatus),
    results: vi.fn(async () => results),
    resume: vi.fn(async () => ({
      jobId: "job-1",
      state: "queued" as const,
      changed: true,
      stateLabel: "等待处理",
    })),
    ...overrides,
  };
}

function renderCard(http: JudgmentSearchHttp) {
  return render(
    <JudgmentSearchCard
      subjectId="subject-1"
      reviewEpisodeId="episode-1"
      evidenceNavigation={navigation}
      onSelectCandidate={vi.fn()}
      http={http}
    />,
  );
}

describe("JudgmentSearchCard", () => {
  beforeEach(() => window.localStorage.clear());
  afterEach(() => vi.useRealTimers());

  it("无任务时显示说明和开始按钮，开始后显示运行进度与要求状态", async () => {
    const api = makeApi();
    const user = userEvent.setup();
    renderCard(api);

    expect(screen.getByRole("heading", { name: "书面判断检索" })).toBeInTheDocument();
    expect(screen.getByText("在本次提交的资料中查找研究者书写的判断文字。")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "开始查找书面判断" }));
    expect(await screen.findByText(/正在查找研究者书面判断/)).toBeInTheDocument();
    expect(screen.getByText("检索尚未完成（部分页面未读取或内容不清）")).toBeInTheDocument();
    expect(window.localStorage.getItem("judgment-search-job:subject-1:episode-1")).toBe("job-1");
  });

  it("运行状态按 2.5 秒轮询，完成后展示候选并支持跳原件页回调", async () => {
    vi.useFakeTimers();
    const completedStatus = { ...runningStatus, state: "completed" as const, completedReads: 3 };
    const api = makeApi({
      status: vi.fn()
        .mockResolvedValueOnce(runningStatus)
        .mockResolvedValueOnce(completedStatus),
    });
    const onSelectCandidate = vi.fn();
    render(
      <JudgmentSearchCard
        subjectId="subject-1"
        reviewEpisodeId="episode-1"
        evidenceNavigation={navigation}
        onSelectCandidate={onSelectCandidate}
        http={api}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "开始查找书面判断" }));
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(api.status).toHaveBeenCalledTimes(1);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_499);
    });
    expect(api.status).toHaveBeenCalledTimes(1);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(api.status).toHaveBeenCalledTimes(2);
    expect(screen.getByText("已发现疑似研究者书面判断的内容，待人工核对原件")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "候选 1 条" }));
    fireEvent.click(screen.getByRole("button", { name: /第 2 页 · 第一次识别/ }));
    expect(onSelectCandidate).toHaveBeenCalledWith({ page_artifact_id: "page-1", page_number: 2 });
  });

  it("取消任务显示继续查找并调用恢复接口", async () => {
    window.localStorage.setItem("judgment-search-job:subject-1:episode-1", "job-1");
    const api = makeApi({
      status: vi.fn(async () => ({ ...runningStatus, state: "cancelled" as const, canResume: true })),
    });
    const user = userEvent.setup();
    renderCard(api);
    await screen.findByRole("button", { name: "继续查找" });
    await user.click(screen.getByRole("button", { name: "继续查找" }));
    expect(api.resume).toHaveBeenCalledWith("subject-1", "episode-1", "job-1", expect.anything());
  });

  it("接口错误显示中文错误并允许重试", async () => {
    const api = makeApi({
      start: vi.fn(async () => {
        throw new Error("检索服务暂时不可用，请稍后重试。");
      }),
    });
    const user = userEvent.setup();
    renderCard(api);
    await user.click(screen.getByRole("button", { name: "开始查找书面判断" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("检索服务暂时不可用，请稍后重试。");
    expect(screen.getByRole("button", { name: "重试" })).toBeInTheDocument();
  });

  it("刷新后从 localStorage 恢复任务并读取状态", async () => {
    window.localStorage.setItem("judgment-search-job:subject-1:episode-1", "restored-job");
    const api = makeApi({
      status: vi.fn(async () => ({ ...runningStatus, jobId: "restored-job" })),
    });
    renderCard(api);
    await waitFor(() => {
      expect(api.status).toHaveBeenCalledWith("subject-1", "episode-1", "restored-job", expect.anything());
    });
    expect(await screen.findByText(/已查 1\/3 页/)).toBeInTheDocument();
  });
});
