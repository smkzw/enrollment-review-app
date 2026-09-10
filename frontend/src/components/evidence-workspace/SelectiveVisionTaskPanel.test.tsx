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
});
