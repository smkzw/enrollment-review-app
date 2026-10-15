// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { TargetedReviewDetail } from "./TargetedReviewDetail";

vi.mock("../../api/page-review/targetedReviewHttp", () => ({ getTargetedReviewDetail: async () => ({
  state: "completed", label: "两轮复核后仍有分歧，请核对原件", rounds: 2, fileName: "检验报告.pdf", pageNumber: 1,
  imageUrl: "/source-image", excerpts: [{ round: 0, reader: 1, field: "白细胞计数", value: "3.2 ↓", excerpt: "原始摘录", context: [] },
    { round: 2, reader: 2, field: "白细胞计数", value: "3.2 ↓", excerpt: "二轮摘录", context: [] }],
}) }));
afterEach(cleanup);
it("切换轮次并放大原件，不显示采信或第三轮按钮", async () => {
  render(<TargetedReviewDetail subjectId="subject" episodeId="episode" jobId="job" />);
  await screen.findByText("原始摘录");
  fireEvent.click(screen.getByRole("button", { name: "第二轮" }));
  expect(screen.getByText("二轮摘录")).toBeInTheDocument();
  expect(screen.queryByText("原始摘录")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "放大原件" }));
  expect(screen.getByRole("img")).toHaveStyle({ width: "125%" });
  expect(screen.queryByRole("button", { name: /采信|第三轮/ })).not.toBeInTheDocument();
  expect(screen.getByText(/正式事实未改动/)).toBeInTheDocument();
});
