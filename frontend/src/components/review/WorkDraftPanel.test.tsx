// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
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
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

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
