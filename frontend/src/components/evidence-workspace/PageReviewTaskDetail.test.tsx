// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { PageReviewTaskDetail } from "./PageReviewTaskDetail";
const { start, status, conflicts } = vi.hoisted(() => ({ start: vi.fn(async () => "aux"),
  status: { reviewStatus: "ready" }, conflicts: vi.fn(async () => [{ pageIndex: 0, fileName: "报告.pdf", pageNumber: 1, fieldCount: 1 }]) }));
vi.mock("../../api/page-review/pageReviewHttp", () => ({ createPageReviewHttp: () => ({ status: async () => ({
  reviewStatus: status.reviewStatus, totalPages: 1, acceptedPages: 1, unrelatedPages: 0, pendingPages: 0, failedPages: 0,
}) }) }));
vi.mock("../../api/page-review/targetedReviewHttp", () => ({
  getReviewConflicts: conflicts,
  startTargetedReview: start,
}));
vi.mock("./TargetedReviewDetail", () => ({ TargetedReviewDetail: ({ jobId }: { jobId: string }) => <p>复核记录 {jobId}</p> }));
afterEach(() => { cleanup(); status.reviewStatus = "ready"; });
it("从原页启动服务端受限复核，不传轮次或模型参数", async () => {
  render(<PageReviewTaskDetail subjectId="subject" episodeId="episode" jobId="original" />);
  fireEvent.click(await screen.findByRole("button", { name: "复核原件" }));
  await screen.findByText("复核记录 aux");
  expect(start).toHaveBeenCalledWith("subject", "episode", "original", 0);
  fireEvent.click(screen.getByRole("button", { name: "返回页面判读概况" }));
  expect(screen.getByText("报告.pdf · 第 1 页")).toBeInTheDocument();
});

it.each(["stopped", "needs_reread"])("%s 不把空列表说成未发现分歧", async (state) => {
  status.reviewStatus = state;
  conflicts.mockResolvedValueOnce([]);
  render(<PageReviewTaskDetail subjectId="subject" episodeId="episode" jobId="original" />);
  expect(await screen.findByText("资料判读尚未完成，暂不能据此确认是否存在读法分歧。")).toBeInTheDocument();
  expect(screen.queryByText(/本次未发现/)).not.toBeInTheDocument();
});
