// @vitest-environment jsdom
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { FactNormalizationApiError, setFactNormalizationRepository } from "../../api/fact-normalization";
import { ProfileNormalizationStatus } from "../../components/profile/ProfileNormalizationStatus";
import { useFactNormalizationJob } from "./useFactNormalizationJob";
import { pageReviewStorageKey, usePageReviewJob } from "./usePageReviewJob";

const pages = vi.hoisted(() => ({ start: vi.fn(), status: vi.fn(), resume: vi.fn() }));
vi.mock("../../api/page-review/pageReviewHttp", async (original) => ({
  ...await original<object>(), createPageReviewHttp: () => pages,
}));
const ready = { jobId: "child", state: "completed", reviewStatus: "ready", totalPages: 1,
  acceptedPages: 1, unrelatedPages: 0, failedPages: 0, pendingPages: 0, canReread: false };

function Flow() {
  const flow = useFactNormalizationJob({ subjectId: "s", reviewEpisodeId: "e", pollIntervalMs: 10 });
  return <><button onClick={() => void flow.start()}>整理</button>
    <ProfileNormalizationStatus state={flow.state} onRetry={() => void flow.retry()} /></>;
}
function PageOnly({ subjectId, onReady }: { subjectId: string; onReady: () => void }) {
  const flow = usePageReviewJob({ subjectId, reviewEpisodeId: "e", onReady, pollIntervalMs: 10 });
  return <><button onClick={() => void flow.start()}>读页</button>
    {flow.completedReview && <span>已完成任务：{flow.completedReview.jobId}</span>}
    <ProfileNormalizationStatus state={flow.state} onRetry={() => void flow.retry()} /></>;
}

beforeEach(() => { localStorage.clear(); pages.start.mockReset(); pages.status.mockReset(); pages.resume.mockReset(); });
afterEach(() => { setFactNormalizationRepository(null); localStorage.clear(); });

it("停止后由用户继续同一任务，不自动恢复或新建", async () => {
  localStorage.setItem(pageReviewStorageKey("s", "e"), "child");
  pages.status.mockResolvedValueOnce({ ...ready, state: "cancelled", reviewStatus: "stopped",
    acceptedPages: 0, pendingPages: 1 }).mockResolvedValue(ready);
  pages.resume.mockResolvedValue("child");
  const onReady = vi.fn();
  render(<PageOnly subjectId="s" onReady={onReady} />);
  const button = await screen.findByRole("button", { name: "继续识别" });
  expect(pages.resume).not.toHaveBeenCalled();
  await userEvent.click(button);
  await waitFor(() => expect(onReady).toHaveBeenCalledOnce());
  expect(pages.resume).toHaveBeenCalledWith("s", "e", "child", expect.any(AbortSignal));
  expect(pages.start).not.toHaveBeenCalled();
});

it("失败页重读完成后自动继续整理，成功历史不重新提交", async () => {
  const start = vi.fn().mockRejectedValueOnce(new FactNormalizationApiError(
    "PAGE_COVERAGE_NOT_READY", "资料识别尚未完成", "请先判读", "请先判读", 409,
  )).mockResolvedValue({ jobId: "normalizer", runId: "run", created: true, state: "queued", stateLabel: "等待", recoveryAction: "" });
  setFactNormalizationRepository({ kind: "http", startFactNormalization: start,
    getFactNormalizationJobStatus: vi.fn().mockResolvedValue({ jobId: "normalizer", state: "completed",
      stateLabel: "完成", cancelRequested: false, progressCompleted: 1, progressTotal: 1,
      recoveryAction: "", createdAt: "2026-09-06", updatedAt: "2026-09-06" }),
    retryFactNormalizationJob: vi.fn(),
  });
  pages.start.mockResolvedValueOnce("root").mockResolvedValueOnce("child");
  pages.status.mockImplementation(async (_s, _e, id) => id === "root" ? {
    ...ready, jobId: "root", reviewStatus: "needs_reread", acceptedPages: 0, failedPages: 1, canReread: true,
  } : ready);
  render(<Flow />);
  await userEvent.click(screen.getByRole("button", { name: "整理" }));
  await userEvent.click(await screen.findByRole("button", { name: "重读未完成资料" }));
  await waitFor(() => expect(start).toHaveBeenCalledTimes(2));
  expect(pages.start).toHaveBeenCalledTimes(2);
  expect(pages.start.mock.calls[1][2]).toBe("root");
  expect(localStorage.getItem(pageReviewStorageKey("s", "e"))).toBeNull();
  expect(localStorage.getItem(`${pageReviewStorageKey("s", "e")}:completed`)).toBe("child");
});

it("刷新恢复读取持久身份，不新建任务", async () => {
  localStorage.setItem(pageReviewStorageKey("s", "e"), "child");
  pages.status.mockResolvedValue(ready);
  const onReady = vi.fn();
  render(<PageOnly subjectId="s" onReady={onReady} />);
  await waitFor(() => expect(onReady).toHaveBeenCalledOnce());
  expect(pages.start).not.toHaveBeenCalled();
});

it("切换受试者后丢弃迟到结果，也不整理新受试者", async () => {
  let resolve: (value: unknown) => void = () => {};
  pages.start.mockResolvedValue("child");
  pages.status.mockImplementation(() => new Promise((done) => { resolve = done; }));
  const onReady = vi.fn();
  const view = render(<PageOnly subjectId="s" onReady={onReady} />);
  await userEvent.click(screen.getByRole("button", { name: "读页" }));
  await waitFor(() => expect(pages.status).toHaveBeenCalledOnce());
  const signal = pages.status.mock.calls[0][3] as AbortSignal;
  view.rerender(<PageOnly subjectId="other" onReady={onReady} />);
  await act(async () => { resolve(ready); });
  expect(signal.aborted).toBe(true);
  expect(onReady).not.toHaveBeenCalled();
  expect(screen.queryByLabelText("资料识别进度")).not.toBeInTheDocument();
});

it("已完成入口刷新后只查询服务端，不再次触发整理", async () => {
  localStorage.setItem(`${pageReviewStorageKey("s", "e")}:completed`, "child");
  pages.status.mockResolvedValue(ready);
  const onReady = vi.fn();
  const view = render(<PageOnly subjectId="s" onReady={onReady} />);
  expect(await screen.findByText("已完成任务：child")).toBeInTheDocument();
  expect(onReady).not.toHaveBeenCalled();
  expect(pages.start).not.toHaveBeenCalled();
  view.rerender(<PageOnly subjectId="other" onReady={onReady} />);
  expect(screen.queryByText("已完成任务：child")).not.toBeInTheDocument();
});

it("本机完成记录未经服务端确认不显示为已完成，也不发起任务", async () => {
  localStorage.setItem(`${pageReviewStorageKey("s", "e")}:completed`, "child");
  pages.status.mockResolvedValue({ ...ready, reviewStatus: "needs_reread" });
  const onReady = vi.fn();
  render(<PageOnly subjectId="s" onReady={onReady} />);
  await waitFor(() => expect(pages.status).toHaveBeenCalledOnce());
  expect(screen.queryByText("已完成任务：child")).not.toBeInTheDocument();
  expect(onReady).not.toHaveBeenCalled();
  expect(pages.start).not.toHaveBeenCalled();
});
