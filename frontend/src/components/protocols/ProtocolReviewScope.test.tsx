// @vitest-environment jsdom
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { decodeReviewScope } from "../../api/protocolReviewScope";
import { ProtocolReviewScope } from "./ProtocolReviewScope";

function view(job = "job", revision = "rev") {
  return { job_id: job, draft_revision_id: revision, scope_content_hash: "c".repeat(64),
    clinical_adoption_applied: false, diagnostics: [],
    candidates: [{ candidate_key: "source-1", scope_kind: "medication_section", label: "合并用药",
      source_span_ids: ["span"], official_codes: [], visit_instance: null, clinically_confirmed: false }],
    source_records: [{ source_span_id: "span", raw_text: "检查期间有源用药记录。", render_page: 7, identity_status: "ok" }] };
}
afterEach(() => vi.unstubAllGlobals());

describe("方案范围原文", () => {
  it("按需读取、分类下钻，不冒称新增内容已采用", async () => {
    const user = userEvent.setup();
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify(view())));
    vi.stubGlobal("fetch", fetcher);
    render(<ProtocolReviewScope jobId="job" revisionId="rev" />);
    expect(fetcher).not.toHaveBeenCalled();
    await user.click(screen.getByText("查看审核范围"));
    expect(await screen.findByText(/不代表这些内容已经审定/)).toBeVisible();
    await user.click(screen.getByText("用药与伴随治疗章节"));
    await user.click(screen.getByText("合并用药"));
    expect(screen.getByText("第7页")).toBeVisible();
    expect(screen.getByText("检查期间有源用药记录。")).toBeVisible();
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("span")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /批准|发布/ })).not.toBeInTheDocument();
  });
  it("读取失败不显示空范围成功", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("保存的来源不可读")));
    render(<ProtocolReviewScope jobId="job" revisionId="rev" />);
    await userEvent.click(screen.getByText("查看审核范围"));
    expect(await screen.findByRole("alert")).toHaveTextContent("保存的来源不可读");
    expect(screen.queryByText("0项")).not.toBeInTheDocument();
  });
  it("同一页不反复标注页码，重复标题不再占一段，正文仍完整保留", async () => {
    const data = view();
    data.candidates[0].source_span_ids = ["heading", "span", "other"];
    data.source_records.unshift({ ...data.source_records[0], source_span_id: "heading", raw_text: "合并用药" });
    data.source_records.push({ ...data.source_records[1], source_span_id: "other", raw_text: "另一项来源内容。" });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(data))));
    render(<ProtocolReviewScope jobId="job" revisionId="rev" />);
    await userEvent.click(screen.getByText("查看审核范围"));
    await userEvent.click(await screen.findByText("用药与伴随治疗章节"));
    await userEvent.click(screen.getByText("合并用药"));
    expect(screen.getAllByText("合并用药")).toHaveLength(1);
    expect(screen.getAllByText("第7页")).toHaveLength(1);
    expect(screen.getByText("另一项来源内容。")).toBeVisible();
    expect(screen.getByText("检查期间有源用药记录。")).toBeVisible();
  });
  it("切换项目后旧响应不能出现在新项目", async () => {
    let resolveOld!: (response: Response) => void;
    vi.stubGlobal("fetch", vi.fn()
      .mockImplementationOnce(() => new Promise<Response>(resolve => { resolveOld = resolve; }))
      .mockResolvedValue(new Response(JSON.stringify({ ...view("new-job", "new-rev"), candidates: [] }))));
    const mounted = render(<ProtocolReviewScope jobId="job" revisionId="rev" />);
    await userEvent.click(screen.getByText("查看审核范围"));
    mounted.rerender(<ProtocolReviewScope jobId="new-job" revisionId="new-rev" />);
    await screen.findByText(/不代表这些内容已经审定/);
    await act(async () => resolveOld(new Response(JSON.stringify(view()))));
    expect(screen.queryByText("合并用药")).not.toBeInTheDocument();
  });
  it("拒绝错误任务、修订及伪造采用身份", () => {
    expect(() => decodeReviewScope(view(), "other", "rev")).toThrow(/不一致/);
    expect(() => decodeReviewScope(view(), "job", "other")).toThrow(/不一致/);
    expect(() => decodeReviewScope({ ...view(), clinical_adoption_applied: true }, "job", "rev")).toThrow();
    expect(() => decodeReviewScope({ ...view(), candidates: [{ ...view().candidates[0], clinically_confirmed: true }] }, "job", "rev")).toThrow();
  });
});
