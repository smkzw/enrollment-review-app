// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LocalVisualVerificationPanel } from "./LocalVisualVerificationPanel";
import { actOnLocalVisualTask, getLocalVisualTask, startLocalVisualTask, type LocalVisualTask } from "../../api/evidence/localVisualHttp";

vi.mock("../../api/evidence/localVisualHttp", () => ({
  getLocalVisualTask: vi.fn(), startLocalVisualTask: vi.fn(), actOnLocalVisualTask: vi.fn(),
}));
const region = { x0: 2, y0: 3, x1: 20, y1: 30, clockwise_degrees: 90 as const };
const task: LocalVisualTask = { found: true, jobId: "old", state: "cancelled", text: null, region,
  configurationCurrent: true, canRetry: false };
beforeEach(() => vi.resetAllMocks());

describe("LocalVisualVerificationPanel", () => {
  it("停止后可按原范围新读，查询返回的具体任务，不冒充已采用病史", async () => {
    vi.mocked(getLocalVisualTask).mockResolvedValue(task);
    vi.mocked(startLocalVisualTask).mockResolvedValue("successor");
    render(<LocalVisualVerificationPanel revisionId="rev" pageId="page" region={null} />);
    fireEvent.click(await screen.findByRole("button", { name: "重新读取原区域" }));
    await waitFor(() => expect(startLocalVisualTask).toHaveBeenCalledWith("rev", "page", region));
    await waitFor(() => expect(getLocalVisualTask).toHaveBeenCalledWith("rev", "page", expect.any(AbortSignal), "successor"));
    expect(screen.queryByRole("button", { name: "重试本次读取" })).not.toBeInTheDocument();
  });

  it("旧配置失败不可重试旧任务；按当前配置重读仍保留原范围", async () => {
    vi.mocked(getLocalVisualTask).mockResolvedValue({ ...task, state: "failed_final", configurationCurrent: false });
    vi.mocked(startLocalVisualTask).mockResolvedValue("current");
    render(<LocalVisualVerificationPanel revisionId="rev" pageId="page" region={null} />);
    fireEvent.click(await screen.findByRole("button", { name: "按当前配置读取原区域" }));
    await waitFor(() => expect(startLocalVisualTask).toHaveBeenCalledWith("rev", "page", region));
    expect(actOnLocalVisualTask).not.toHaveBeenCalled();
  });

  it("显示返回原文和未采用说明，可定位本次真实范围", async () => {
    vi.mocked(getLocalVisualTask).mockResolvedValue({ ...task, state: "completed", text: "NCS，所指对象不明。" });
    const locate = vi.fn();
    render(<LocalVisualVerificationPanel revisionId="rev" pageId="page" region={null} onLocateRegion={locate} />);
    expect(await screen.findByText("NCS，所指对象不明。")).toBeInTheDocument();
    expect(screen.getByText(/未改动病史或入排意见/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "定位本次核实区域" }));
    expect(locate).toHaveBeenCalledWith(region);
  });
});
