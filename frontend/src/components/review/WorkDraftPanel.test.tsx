// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { WorkDraftPanel } from "./WorkDraftPanel";
import type { CatalogEpisodeView } from "../../api/catalog/catalogTypes";

const episode: CatalogEpisodeView = {
  reviewEpisodeId: "episode", subjectId: "subject", projectId: "project", ruleSetId: "rules",
  studyPhase: "phase_iii", studyPhaseLabel: "III期", stage: "screening", stageLabel: "筛选",
  protocolVersionId: "protocol", ruleSetRevision: 1, evidenceSnapshotId: null,
  workflowStageId: "screen", workflowStageLabel: "筛选", visitWindow: null,
  latestEvidenceSnapshotId: "snapshot", activeEvidenceSnapshotId: "snapshot",
  activeEvidenceProcessingRevisionId: "complete", anchorDates: {}, dueAt: null, revision: 1,
};

beforeEach(() => localStorage.clear());
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.useRealTimers(); });

it("重新打开已完成工作稿不会触发反复加载", async () => {
  localStorage.setItem("work-draft-job:episode", "finished");
  const fetched = vi.fn().mockResolvedValue({ ok: true, json: async () => ({
    job_id: "finished", state: "completed", review_run_id: "saved-result",
  }) });
  vi.stubGlobal("fetch", fetched);
  const completed = vi.fn();
  render(<WorkDraftPanel episode={episode} onCompleted={completed} />);
  await screen.findByText("工作稿已保存，未签发。");
  expect(completed).not.toHaveBeenCalled();
  expect(screen.getByRole("button", { name: "更新工作稿" })).toBeEnabled();
});

it("新任务完成后只刷新一次并保存恢复位置", async () => {
  const fetched = vi.fn().mockImplementation(async (_url, options) => ({
    ok: true, json: async () => options.method === "POST"
      ? {job_id: "new-job", state: "queued", review_run_id: null}
      : {job_id: "new-job", state: "completed", review_run_id: "new-result"},
  }));
  vi.stubGlobal("fetch", fetched);
  const completed = vi.fn();
  render(<WorkDraftPanel episode={episode} onCompleted={completed} />);
  fireEvent.click(screen.getByRole("button", {name: "开始审核"}));
  await waitFor(() => expect(completed).toHaveBeenCalledExactlyOnceWith("new-result"));
  expect(localStorage.getItem("work-draft-job:episode")).toBe("new-job");
});

it("失败回执保留旧结果，不调用完成通知", async () => {
  localStorage.setItem("work-draft-job:episode", "failed-job");
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ok: true, json: async () => ({
    job_id: "failed-job", state: "failed_final", review_run_id: null,
  })}));
  const completed = vi.fn();
  render(<WorkDraftPanel episode={episode} onCompleted={completed} />);
  await screen.findByRole("alert");
  expect(screen.getByRole("alert")).toHaveTextContent("旧结果未改变");
  expect(completed).not.toHaveBeenCalled();
});

it("核实命令沿用既有轮询，只在实际保存后通知并保留恢复位置", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ok: true, json: async () => ({
    job_id: "confirmed-job", state: "completed", review_run_id: "confirmed-result",
  })}));
  const completed = vi.fn();
  render(<WorkDraftPanel episode={episode} initialJob={{job_id: "confirmed-job", state: "queued", review_run_id: null}} onCompleted={completed} />);
  await waitFor(() => expect(completed).toHaveBeenCalledExactlyOnceWith("confirmed-result"));
  expect(localStorage.getItem("work-draft-job:episode")).toBe("confirmed-job");
});


it("连续保存日期使用回执修订，外部新修订也同步", async () => {
  const fetched = vi.fn().mockResolvedValue({ok: true, json: async () => ({revision: 2})});
  vi.stubGlobal("fetch", fetched);
  const dated = {...episode, anchorDates: {screening_date: {value: "2025-08-08", precision: "day"}}};
  const view = render(<WorkDraftPanel episode={dated} />);
  fireEvent.click(screen.getByRole("button", {name: "保存日期"}));
  await screen.findByText("日期已保存，请按此范围更新工作稿。");
  fireEvent.click(screen.getByRole("button", {name: "保存日期"}));
  await waitFor(() => expect(fetched).toHaveBeenCalledTimes(2));
  expect(JSON.parse(fetched.mock.calls[1][1].body).expected_revision).toBe(2);
  view.rerender(<WorkDraftPanel episode={{...dated, revision: 3}} />);
  await waitFor(() => expect(screen.getByRole("button", {name: "保存日期"})).toBeEnabled());
  fireEvent.click(screen.getByRole("button", {name: "保存日期"}));
  await waitFor(() => expect(fetched).toHaveBeenCalledTimes(3));
  expect(JSON.parse(fetched.mock.calls[2][1].body).expected_revision).toBe(3);
});

it("资料截至日单独保存，不移动筛选开始日；切换节点不带旧范围", async () => {
  const fetched = vi.fn().mockResolvedValue({ok: true, json: async () => ({revision: 2})});
  vi.stubGlobal("fetch", fetched);
  const dated = {...episode, anchorDates: {screening_date: {value: "2025-08-08", precision: "day"}}};
  const view = render(<WorkDraftPanel episode={dated} />);
  fireEvent.change(screen.getByLabelText("本次资料截至"), {target: {value: "2025-08-15"}});
  fireEvent.click(screen.getByRole("button", {name: "保存资料范围"}));
  await screen.findByText("日期已保存，请按此范围更新工作稿。");
  expect(fetched.mock.calls[0][0]).toMatch(/\/evidence-cutoff$/);
  expect(JSON.parse(fetched.mock.calls[0][1].body)).toEqual({evidence_cutoff_date: "2025-08-15", expected_revision: 1});
  expect(screen.getByLabelText("本节点开始日")).toHaveValue("2025-08-08");
  view.rerender(<WorkDraftPanel episode={{...episode, reviewEpisodeId: "another"}} />);
  expect(screen.getByLabelText("本次资料截至")).toHaveValue("");
  expect(screen.queryByText("日期已保存，请按此范围更新工作稿。")).not.toBeInTheDocument();
});


it("等待人工核对不是持续生成，也不报告完成", async () => {
  vi.useFakeTimers();
  localStorage.setItem("work-draft-job:episode", "waiting-job");
  const fetched = vi.fn().mockResolvedValue({ok: true, json: async () => ({
    job_id: "waiting-job", state: "waiting_user", review_run_id: null,
  })});
  vi.stubGlobal("fetch", fetched);
  const completed = vi.fn();
  render(<WorkDraftPanel episode={episode} onCompleted={completed} />);
  await act(async () => { await vi.advanceTimersByTimeAsync(500); });
  expect(screen.getByText("本次处理需要人工核对，请查看任务详情。")).toBeInTheDocument();
  const initialReads = fetched.mock.calls.length;
  await act(async () => { await vi.advanceTimersByTimeAsync(6000); });
  expect(fetched).toHaveBeenCalledTimes(initialReads);
  expect(completed).not.toHaveBeenCalled();
});

it("停止请求继续等安全终态，不当作坏回执或完成", async () => {
  vi.useFakeTimers();
  localStorage.setItem("work-draft-job:episode", "stopping-job");
  let cancelled = false;
  vi.stubGlobal("fetch", vi.fn().mockImplementation(async () => ({ok: true, json: async () => ({
    job_id: "stopping-job", state: cancelled ? "cancelled" : "cancel_requested", review_run_id: null,
  })})));
  const completed = vi.fn();
  render(<WorkDraftPanel episode={episode} onCompleted={completed} />);
  await act(async () => { await vi.advanceTimersByTimeAsync(500); });
  expect(screen.getByText("正在停止本次处理，原件与已有结果保留。")).toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(screen.getByRole("button", {name: "开始审核"})).toBeDisabled();
  cancelled = true;
  await act(async () => { await vi.advanceTimersByTimeAsync(2500); });
  expect(screen.getByText("本次处理已停止，原件与已有结果保留。")).toBeInTheDocument();
  expect(screen.getByRole("button", {name: "开始审核"})).toBeEnabled();
  expect(completed).not.toHaveBeenCalled();
});
