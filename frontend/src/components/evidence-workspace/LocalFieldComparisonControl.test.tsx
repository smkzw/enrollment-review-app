// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { LocalFieldComparisonControl } from "./LocalFieldComparisonControl";
import { getLocalFieldComparison, startLocalFieldComparison, actOnLocalVisualTask } from "../../api/evidence/localVisualHttp";

vi.mock("../../api/evidence/localVisualHttp", () => ({
  getLocalFieldComparison: vi.fn(), startLocalFieldComparison: vi.fn(), actOnLocalVisualTask: vi.fn(),
}));
const absent = { found: false, jobId: null, state: null, canRetry: false, failureMessage: null, outcome: null };
beforeEach(() => vi.resetAllMocks());

it("查看不自动读取，点击只提交所选来源和项目", async () => {
  vi.mocked(getLocalFieldComparison).mockResolvedValue(absent);
  vi.mocked(startLocalFieldComparison).mockResolvedValue("comparison");
  render(<LocalFieldComparisonControl revisionId="rev" pageId="page" visualJobId="visual" itemIndex={2} />);
  const button = await screen.findByRole("button", { name: "核对这一项" });
  await waitFor(() => expect(button).toBeEnabled());
  expect(startLocalFieldComparison).not.toHaveBeenCalled();
  fireEvent.click(button);
  await waitFor(() => expect(startLocalFieldComparison).toHaveBeenCalledWith("rev", "page", "visual", 2));
});

it("核对一致仍未采用，恢复按钮只重试原任务", async () => {
  vi.mocked(getLocalFieldComparison).mockResolvedValue({ ...absent, found: true, jobId: "failed",
    state: "failed_final", canRetry: true, failureMessage: "此处读取未完成，不是资料缺失" });
  render(<LocalFieldComparisonControl revisionId="rev" pageId="page" visualJobId="visual" itemIndex={0} />);
  fireEvent.click(await screen.findByRole("button", { name: "重试未完成的核对" }));
  await waitFor(() => expect(actOnLocalVisualTask).toHaveBeenCalledWith("failed", "retry"));
  expect(startLocalFieldComparison).not.toHaveBeenCalled();
});

it("完成只展示候选说明，不出现采用按钮", async () => {
  vi.mocked(getLocalFieldComparison).mockResolvedValue({ ...absent, found: true, jobId: "done", state: "completed",
    outcome: { itemIndex: 0, agreement: true, reasons: ["摘录一致，位置仍须核对"] } });
  render(<LocalFieldComparisonControl revisionId="rev" pageId="page" visualJobId="visual" itemIndex={0} />);
  expect(await screen.findByText("原文核对一致，尚未采用")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /确认病史|采用此项/ })).not.toBeInTheDocument();
  expect(startLocalFieldComparison).not.toHaveBeenCalled();
});

it("不可重试的失败保留旧任务，显式发起新核对", async () => {
  vi.mocked(getLocalFieldComparison).mockResolvedValue({ ...absent, found: true, jobId: "failed",
    state: "failed_final", canRetry: false, failureMessage: "本次配置无法核对" });
  vi.mocked(startLocalFieldComparison).mockResolvedValue("successor");
  render(<LocalFieldComparisonControl revisionId="rev" pageId="page" visualJobId="visual" itemIndex={0} />);
  fireEvent.click(await screen.findByRole("button", { name: "重新发起项目核对" }));
  await waitFor(() => expect(startLocalFieldComparison).toHaveBeenCalledWith("rev", "page", "visual", 0));
  expect(actOnLocalVisualTask).not.toHaveBeenCalled();
});
