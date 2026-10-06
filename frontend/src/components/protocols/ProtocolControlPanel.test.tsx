// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ProtocolControlPanel } from "./ProtocolControlPanel";
import type { useProtocolControls } from "./useProtocolControls";

describe("ProtocolControlPanel stopped reason", () => {
  it.each([
    "原文已保存，仍需核清它与审核要求的对应关系",
    "原文支持的补充要求尚未接通可靠核验，由系统建设继续处理",
    "本次补充要求修订尚未完成，已核清的部分仍保留",
  ])("显示已保存原因而不声称采用：%s", (statusLabel) => {
    const controls: ReturnType<typeof useProtocolControls> = {
      state: {
        sourceJobId: "source", draftRevisionId: "revision", status: "stopped",
        job: {
          jobId: "control", sourceJobId: "source", state: "failed_final", status: "stopped",
          statusLabel, checkpointId: null, candidateCount: null,
        },
      },
      retry: vi.fn(), retryFailed: vi.fn(), retrying: false,
    };
    render(<ProtocolControlPanel controls={controls} />);
    expect(screen.getByText(statusLabel + "。")).toBeVisible();
    expect(screen.getByText(/当前方案暂不能发布/)).toBeVisible();
    expect(screen.getByRole("button", { name: "继续整理未完成部分" })).toBeEnabled();
  });
});
