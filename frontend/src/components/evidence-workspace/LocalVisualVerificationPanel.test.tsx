// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LocalVisualVerificationPanel } from "./LocalVisualVerificationPanel";
import { actOnLocalVisualTask, getLocalVisualTask, startLocalVisualTask, type LocalVisualTask } from "../../api/evidence/localVisualHttp";

vi.mock("../../api/evidence/localVisualHttp", async (original) => ({
  ...await original<typeof import("../../api/evidence/localVisualHttp")>(),
  getLocalVisualTask: vi.fn(), startLocalVisualTask: vi.fn(), actOnLocalVisualTask: vi.fn(),
}));
const region = { x0: 2, y0: 3, x1: 20, y1: 30, clockwise_degrees: 90 as const };
const task: LocalVisualTask = { found: true, jobId: "old", state: "cancelled", text: null, region,
  configurationCurrent: true, canRetry: false };
beforeEach(() => vi.resetAllMocks());

describe("LocalVisualVerificationPanel", () => {
  it("模型未返回不能显示成原件不清；查看记录不自动重试", async () => {
    const failureMessage = "视觉模型未在限定时间内返回，尚未取得可核实的回答。原件与原有核对结果不变。";
    vi.mocked(getLocalVisualTask).mockResolvedValue({ ...task, state: "failed_final", canRetry: true, failureMessage });
    render(<LocalVisualVerificationPanel revisionId="rev" pageId="page" region={null} />);
    expect(await screen.findByRole("alert")).toHaveTextContent(failureMessage);
    expect(screen.queryByText(/字迹不清/)).not.toBeInTheDocument();
    expect(startLocalVisualTask).not.toHaveBeenCalled();
    expect(actOnLocalVisualTask).not.toHaveBeenCalled();
  });
  it.each([true, false])("清楚摘录仅转入校对入口；旧配置不能转入：现行=%s", async (configurationCurrent) => {
    const item = { label: "接收时间", raw_value: "2026-02-03 10:12", raw_unit: null,
      reference_text: null, time_label: "接收时间", annotation_target: null,
      excerpt: "接收时间：2026-02-03 10:12", position: "页底", script: "printed" as const,
      legibility: "clear" as const, proposed_bbox: { x0: 0, y0: 0, x1: 1000, y1: 1000 } };
    vi.mocked(getLocalVisualTask).mockResolvedValue({ ...task, state: "completed", text: "逐项摘录",
      configurationCurrent, readingRegion: region,
      structuredRead: { items: [item, { ...item, legibility: "partial" }], unresolved: [] } });
    const prepare = vi.fn();
    const locate = vi.fn();
    render(<LocalVisualVerificationPanel revisionId="rev" pageId="page" region={null}
      onPrepareCorrection={prepare} onLocateRegion={locate} />);
    fireEvent.click(await screen.findByText("查看本次读取结果（尚未采用）"));
    if (configurationCurrent) {
      fireEvent.click(screen.getByRole("button", { name: "将第1项接收时间转到文字校对" }));
      expect(prepare).toHaveBeenCalledWith({ revisionId: "rev", pageId: "page", jobId: "old", itemIndex: 0,
        excerpt: item.excerpt });
      expect(locate).toHaveBeenCalledWith(region);
    } else {
      expect(screen.queryByRole("button", { name: /转到文字校对/ })).not.toBeInTheDocument();
      expect(prepare).not.toHaveBeenCalled();
    }
    expect(screen.queryByRole("button", { name: /将第2项/ })).not.toBeInTheDocument();
    expect(startLocalVisualTask).not.toHaveBeenCalled();
    expect(actOnLocalVisualTask).not.toHaveBeenCalled();
  });
  it("按用户选择逐项读取，不在选择方式时自动调用", async () => {
    vi.mocked(getLocalVisualTask).mockResolvedValue(task);
    vi.mocked(startLocalVisualTask).mockResolvedValue("localized");
    render(<LocalVisualVerificationPanel revisionId="rev" pageId="page" region={region} />);
    fireEvent.change(screen.getByRole("combobox", { name: "局部读取方式" }), { target: { value: "localized_candidate" } });
    expect(startLocalVisualTask).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "核实所选区域" }));
    await waitFor(() => expect(startLocalVisualTask).toHaveBeenCalledWith("rev", "page", { ...region, read_format: "localized_candidate" }));
  });
  it("逐项回原件不采用事实；越界、字迹与归属疑问仍保留", async () => {
    const one = { label: "日期", raw_value: "2026-01-02", raw_unit: null, reference_text: null, time_label: null,
      annotation_target: null, excerpt: "日期：2026-01-02", position: "右下角", script: "printed" as const, legibility: "clear" as const,
      proposed_bbox: { x0: 200, y0: 200, x1: 800, y1: 800 } };
    vi.mocked(getLocalVisualTask).mockResolvedValue({ ...task, state: "completed", text: "逐项原文",
      region: { x0: 20, y0: 20, x1: 80, y1: 80, clockwise_degrees: 270 },
      readingRegion: { x0: 0, y0: 0, x1: 100, y1: 100, clockwise_degrees: 270 },
      structuredRead: { items: [one, { ...one, label: "批注", script: "handwritten", legibility: "partial",
        proposed_bbox: { ...one.proposed_bbox, x0: 199 } }], unresolved: ["批注日期未读清"] } });
    const locate = vi.fn();
    render(<LocalVisualVerificationPanel revisionId="rev" pageId="page" region={null} onLocateRegion={locate} />);
    fireEvent.click(await screen.findByText("查看本次读取结果（尚未采用）"));
    await screen.findByRole("table", { name: "待核实的局部读取项目" });
    expect(screen.getByText(/范围超出本次圈选/)).toBeVisible();
    expect(screen.getByText("批注日期未读清")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "查看第1项日期所指原件区域" }));
    expect(locate).toHaveBeenCalledWith({ x0: 20, y0: 20, x1: 80, y1: 80, clockwise_degrees: 270 });
    expect(screen.getByText("批注日期未读清")).not.toBeVisible();
    expect(screen.queryByRole("button", { name: /查看第2项/ })).not.toBeInTheDocument();
    expect(screen.getByText(/范围超出本次圈选/)).toBeInTheDocument();
    expect(screen.getByText("批注日期未读清")).toBeInTheDocument();
    expect(startLocalVisualTask).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: /采用|确认病史/ })).not.toBeInTheDocument();
  });
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
    const result = await screen.findByText("NCS，所指对象不明。");
    expect(result).not.toBeVisible();
    fireEvent.click(screen.getByText("查看本次读取结果（尚未采用）"));
    expect(result).toBeVisible();
    expect(screen.getByText(/未改动病史或入排意见/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "定位本次核实区域" }));
    expect(locate).toHaveBeenCalledWith(region);
  });

  it("保留周边只改变读取请求，圈选范围和定位仍是用户选中的原范围", async () => {
    vi.mocked(getLocalVisualTask).mockResolvedValue({ ...task, region: { ...region, include_context: true } });
    vi.mocked(startLocalVisualTask).mockResolvedValue("focused");
    const locate = vi.fn();
    render(<LocalVisualVerificationPanel revisionId="rev" pageId="page" region={region} onLocateRegion={locate} />);
    const option = screen.getByRole("checkbox", { name: "保留周边作参考" });
    expect(option).not.toBeChecked();
    fireEvent.click(option);
    fireEvent.click(screen.getByRole("button", { name: "核实所选区域" }));
    await waitFor(() => expect(startLocalVisualTask).toHaveBeenCalledWith("rev", "page", { ...region, include_context: true }));
    fireEvent.click(await screen.findByRole("button", { name: "定位本次核实区域" }));
    expect(locate).toHaveBeenCalledWith({ ...region, include_context: true });
  });

  it("正在读取时不能更改周边选项，换页后不沿用前一页的选项", async () => {
    vi.mocked(getLocalVisualTask).mockResolvedValue({ ...task, state: "running" });
    const view = render(<LocalVisualVerificationPanel key="page" revisionId="rev" pageId="page" region={{ ...region, include_context: true }} />);
    await waitFor(() => expect(screen.getByRole("checkbox", { name: "保留周边作参考" })).toBeChecked());
    expect(screen.getByRole("checkbox", { name: "保留周边作参考" })).toBeDisabled();
    vi.mocked(getLocalVisualTask).mockResolvedValue({ ...task, state: "cancelled" });
    view.rerender(<LocalVisualVerificationPanel key="next" revisionId="rev" pageId="next" region={region} />);
    await waitFor(() => expect(screen.getByRole("checkbox", { name: "保留周边作参考" })).not.toBeChecked());
  });

  it("同页改选仍可回看旧结果，但明确旧范围且新读取不被旧框替换", async () => {
    vi.mocked(getLocalVisualTask).mockResolvedValue({ ...task, state: "completed", text: "此前原文" });
    vi.mocked(startLocalVisualTask).mockResolvedValue("new-region");
    const locate = vi.fn();
    const view = render(<LocalVisualVerificationPanel revisionId="rev" pageId="page" region={region} onLocateRegion={locate} />);
    await screen.findByRole("button", { name: "定位本次核实区域" });
    const next = { ...region, x0: 22, x1: 40 };
    view.rerender(<LocalVisualVerificationPanel revisionId="rev" pageId="page" region={next} onLocateRegion={locate} />);
    expect(screen.queryByRole("button", { name: "定位本次核实区域" })).not.toBeInTheDocument();
    expect(screen.getByText("查看此前区域的读取结果（尚未采用）")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "定位此前核实区域" }));
    expect(locate).toHaveBeenCalledWith(region);
    fireEvent.click(screen.getByRole("button", { name: "核实所选区域" }));
    await waitFor(() => expect(startLocalVisualTask).toHaveBeenCalledWith("rev", "page", next));
  });

  it.each([true, false])("同页改选后旧任务重读按钮明确指向此前范围：配置现行=%s", async (configurationCurrent) => {
    vi.mocked(getLocalVisualTask).mockResolvedValue({ ...task, configurationCurrent });
    vi.mocked(startLocalVisualTask).mockResolvedValue("old-restart");
    render(<LocalVisualVerificationPanel revisionId="rev" pageId="page" region={{ ...region, x0: 22, x1: 40 }} />);
    const name = configurationCurrent ? "重新读取此前区域" : "按当前配置读取此前区域";
    fireEvent.click(await screen.findByRole("button", { name }));
    await waitFor(() => expect(startLocalVisualTask).toHaveBeenCalledWith("rev", "page", region));
  });
});
