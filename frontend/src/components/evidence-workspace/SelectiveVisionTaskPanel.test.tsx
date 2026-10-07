// @vitest-environment jsdom

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SelectiveVisionTaskPanel } from "./SelectiveVisionTaskPanel";

const { getSelectiveVisionTask, retrySelectiveVisionTask, cancelSelectiveVisionTask } =
  vi.hoisted(() => ({
    getSelectiveVisionTask: vi.fn(),
    retrySelectiveVisionTask: vi.fn(),
    cancelSelectiveVisionTask: vi.fn(),
  }));

vi.mock("../../api/evidence", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/evidence")>();
  return {
    ...actual,
    getSelectiveVisionTask,
    retrySelectiveVisionTask,
    cancelSelectiveVisionTask,
  };
});

function task(overrides: Record<string, unknown> = {}) {
  return {
    evidenceProcessingRevisionId: "complete-1",
    found: true,
    jobId: "job-1",
    state: "failed_final",
    stateLabel: "未完成",
    cancelRequested: false,
    progressCompleted: 0,
    progressTotal: 1,
    recoveryAction: "可以重新开始未完成的页面核验。",
    canRetry: true,
    canCancel: false,
    eligiblePageCount: 3,
    skippedPageCount: 7,
    observationPageCount: 1,
    closedPageCount: 2,
    failedPageArtifactIds: ["artifact-1"],
    closedReasonLabel: "部分页面暂时无法核验",
    failedScopeLabel: "页面视觉核验",
    createdAt: "2026-09-01T01:00:00Z",
    updatedAt: "2026-09-01T01:01:00Z",
    ...overrides,
  };
}

describe("证据工作台页面视觉核验面板", () => {
  beforeEach(() => {
    getSelectiveVisionTask.mockReset();
    retrySelectiveVisionTask.mockReset();
    cancelSelectiveVisionTask.mockReset();
  });

  it("显示中文范围与恢复入口，不渲染内部任务内容", async () => {
    getSelectiveVisionTask.mockResolvedValue(task());

    render(<SelectiveVisionTaskPanel revisionId="complete-1" />);

    expect(
      await screen.findByRole("heading", { name: "页面视觉核验" }),
    ).toBeInTheDocument();
    expect(screen.getByText("可以重新开始未完成的页面核验。")).toBeInTheDocument();
    expect(screen.getByText("需要核验的页面")).toBeInTheDocument();
    expect(screen.getByText("未完成范围：页面视觉核验")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "重新开始核验" })).toBeInTheDocument();
    expect(document.body.textContent).not.toContain("selective_vision_postprocess");
    expect(document.body.textContent).not.toContain("payload");
  });

  const completedTask = {
    state: "completed", stateLabel: "识读已保存", canRetry: false,
    closedPageCount: 0, eligiblePageCount: 3, observationPageCount: 3,
    failedPageArtifactIds: [], failedScopeLabel: null, closedReasonLabel: null,
  };

  it("无失败或遗漏的已完成识读默认收起，保留展开详情而不宣称核对完成", async () => {
    getSelectiveVisionTask.mockResolvedValue(task(completedTask));
    render(<SelectiveVisionTaskPanel revisionId="complete-1" />);
    const summary = await screen.findByText("原件补充识读已保存，内容仍需核对");
    const details = summary.closest("details");
    expect(details).not.toBeNull();
    expect(details?.open).toBe(false);
    expect(screen.getByRole("heading", { name: "页面视觉核验" })).not.toBeVisible();
    fireEvent.click(summary);
    expect(details?.open).toBe(true);
    expect(screen.getByRole("heading", { name: "页面视觉核验" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "刷新状态" })).toBeInTheDocument();
  });

  it.each([
    { closedPageCount: 1 },
    { closedPageCount: null },
    { observationPageCount: 2 },
    { eligiblePageCount: null },
    { skippedPageCount: null },
    { failedPageArtifactIds: ["artifact-1"] },
    { failedScopeLabel: "本页未核清" },
    { closedReasonLabel: "尚有未核实的范围" },
    { canRetry: true },
    { state: "running", canCancel: true },
  ])("完成标签不能收起失败、范围不明或仍需处理的任务：%j", async (overrides) => {
    getSelectiveVisionTask.mockResolvedValue(task({ ...completedTask, ...overrides }));
    render(<SelectiveVisionTaskPanel revisionId="complete-1" />);
    expect(await screen.findByRole("heading", { name: "页面视觉核验" })).toBeInTheDocument();
    expect(document.querySelector("details.evidence-completed-reading")).toBeNull();
  });

  it("停止后按同一完整版本刷新状态", async () => {
    getSelectiveVisionTask
      .mockResolvedValueOnce(
        task({
          state: "queued",
          stateLabel: "等待处理",
          canRetry: false,
          canCancel: true,
          failedScopeLabel: null,
          closedReasonLabel: null,
        }),
      )
      .mockResolvedValue(task({ state: "cancelled", stateLabel: "已停止" }));
    cancelSelectiveVisionTask.mockResolvedValue({
      jobId: "job-1",
      state: "cancelled",
      stateLabel: "已停止",
      changed: true,
    });

    render(<SelectiveVisionTaskPanel revisionId="complete-1" />);
    fireEvent.click(await screen.findByRole("button", { name: "停止核验" }));

    expect(cancelSelectiveVisionTask).toHaveBeenCalledWith("complete-1");
    await waitFor(() => expect(getSelectiveVisionTask).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("已停止")).toBeInTheDocument();
  });

  it("只对选中的失败页提供有方向的重读，不将普通重试伪装成旋转重读", async () => {
    getSelectiveVisionTask.mockResolvedValue(task());
    retrySelectiveVisionTask.mockResolvedValue({
      jobId: "new-job", state: "queued", stateLabel: "等待处理", changed: true,
    });
    render(<SelectiveVisionTaskPanel revisionId="complete-1"
      selectedPage={{ pageArtifactId: "artifact-1", pageNumber: 4, readingRotation: 270 }} />);
    fireEvent.click(await screen.findByRole("button", { name: "按当前方向重读第 4 页" }));
    await waitFor(() => expect(retrySelectiveVisionTask).toHaveBeenCalledWith(
      "complete-1", undefined, { "artifact-1": 270 },
    ));
  });
});
