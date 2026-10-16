// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NormalizationUnresolvedPanel } from "./NormalizationUnresolvedPanel";
import { getFactNormalizationRepository } from "../../api/fact-normalization";
import { decodeNormalizationUnresolved } from "../../api/fact-normalization/factNormalizationViewModels";

vi.mock("../../api/fact-normalization", () => ({ getFactNormalizationRepository: vi.fn() }));
const read = vi.fn();
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(getFactNormalizationRepository).mockReturnValue({ kind: "http",
    getCurrentFactNormalizationJob: vi.fn(async () => null),
    getNormalizationUnresolved: read, startFactNormalization: vi.fn(),
    getFactNormalizationJobStatus: vi.fn(), retryFactNormalizationJob: vi.fn() });
});
afterEach(cleanup);

function page(total: number, offset = 0) {
  return { jobId: "j", contentSha256: "a".repeat(64), total, offset, hasMore: offset + Math.min(50, total - offset) < total,
    isCurrent: true, textAccountingApplied: true, evidenceSnapshotId: "snapshot-frozen", processingRevisionId: "revision-frozen",
    items: Array.from({ length: Math.min(50, total - offset) }, (_, index) => ({
      itemId: `item-${index + offset}`, kind: "unquoted_text" as const, message: `文字${index + offset}待核对`, reason: "原文已保留，不代表缺少检查。",
      sources: [{ sourceDocumentVersionId: "doc", pageArtifactId: `page-${index + offset}`,
        pageNumber: index + offset + 1, fileName: "病历原件.pdf" }],
    })) };
}

async function openOtherText() {
  const summary = await screen.findByText("查看原件读取提示");
  if (!summary.closest("details")?.open) fireEvent.click(summary);
  fireEvent.click(await screen.findByText(/^其他待核对文字/));
}

describe("NormalizationUnresolvedPanel", () => {
  it("已读记录可单独重新核验，历史或新核验结果不再提供递归入口", async () => {
    read.mockResolvedValue({ ...page(1), runId: "failed-new-run", revalidationSourceRunId: "saved-run", canRevalidateSaved: true });
    const onRevalidate = vi.fn().mockResolvedValue("new-job");
    const view = render(<NormalizationUnresolvedPanel subjectId="s" episodeId="e" jobId="j" onRevalidate={onRevalidate} />);
    const button = await screen.findByRole("button", {name: "重新核验已读记录（不重读原件）", hidden: true});
    expect(button).not.toBeVisible();
    fireEvent.click(screen.getByText("查看原件读取提示"));
    expect(button).toBeVisible();
    fireEvent.click(button);
    await waitFor(() => expect(onRevalidate).toHaveBeenCalledWith("saved-run"));
    read.mockResolvedValue({ ...page(1), jobId: "new-job", runId: "new-run", canRevalidateSaved: false });
    view.rerender(<NormalizationUnresolvedPanel subjectId="s" episodeId="e" jobId="new-job" onRevalidate={onRevalidate} />);
    await waitFor(() => expect(screen.queryByRole("button", {name: /重新核验已读记录/, hidden: true})).not.toBeInTheDocument());
  });
  it("读取提示默认收起，展开后具体疑问优先、其他文字可逐项回源", async () => {
    const result = page(3);
    read.mockResolvedValue({ ...result, items: [
      { ...result.items[0], kind: "reading_uncertainty", message: "批注对象待核对" },
      { ...result.items[1], sourceExcerpt: "检验报告单" }, result.items[2],
    ] });
    render(<NormalizationUnresolvedPanel subjectId="s" episodeId="e" jobId="j" />);
    expect(await screen.findByText("批注对象待核对")).not.toBeVisible();
    fireEvent.click(screen.getByText("查看原件读取提示"));
    expect(screen.getByText("批注对象待核对")).toBeVisible();
    const links = screen.getAllByRole("link");
    expect(links).toHaveLength(3);
    expect(links[0]).toBeVisible();
    expect(links[1]).not.toBeVisible();
    expect(links[2]).not.toBeVisible();
    expect(screen.getByText("检验报告单")).not.toBeVisible();
    await openOtherText();
    expect(screen.getByText("检验报告单")).toBeVisible();
    expect(screen.getAllByRole("link")).toHaveLength(3);
    expect(screen.getByText(/尚未核清的内容仍保留/)).toBeVisible();
  });
  it("仅继续失败页，保留当前任务来源；历史版本不提供续读", async () => {
    read.mockResolvedValue({ ...page(1), runId: "old-run", failedPageCount: 6 });
    const onContinue = vi.fn().mockResolvedValue("new-job");
    const view = render(<NormalizationUnresolvedPanel subjectId="s" episodeId="e" jobId="j" onContinue={onContinue} />);
    const continueButton = await screen.findByRole("button", {name: "重新核对6页待核内容"});
    expect(continueButton).toBeVisible();
    expect(screen.getByRole("link")).not.toBeVisible();
    fireEvent.click(continueButton);
    await waitFor(() => expect(onContinue).toHaveBeenCalledOnce());
    expect(onContinue).toHaveBeenCalledWith("old-run");
    read.mockResolvedValue({ ...page(1), jobId: "historical", runId: "old-run", failedPageCount: 6, isCurrent: false });
    view.rerender(<NormalizationUnresolvedPanel subjectId="s" episodeId="e" jobId="historical" onContinue={onContinue} />);
    await screen.findByText(/这是历史资料版本/);
    expect(screen.queryByRole("button", {name: "重新核对6页待核内容"})).not.toBeInTheDocument();
  });
  it.each([0, 1, 101, 250])("%s项均可访问，不做前100项截断", async (total) => {
    read.mockImplementation(async (_subject, _episode, _job, offset) => page(total, offset));
    render(<NormalizationUnresolvedPanel subjectId="s" episodeId="e" jobId="j" />);
    await screen.findByRole("heading", { name: "资料读取提示" });
    if (total > 0) expect(await screen.findByLabelText("读取提示数量")).toHaveTextContent(`（${total}项）`);
    else await screen.findByText(/暂无待核对/);
    if (total > 0) await openOtherText();
    for (let offset = 50; offset < total; offset += 50) {
      fireEvent.click(screen.getByRole("button", { name: "加载更多" }));
      await waitFor(() => expect(screen.getAllByRole("link")).toHaveLength(Math.min(offset + 50, total)));
    }
    expect(screen.queryAllByRole("link")).toHaveLength(total);
    expect(screen.queryByRole("button", { name: "加载更多" })).not.toBeInTheDocument();
  });

  it("历史及旧覆盖记录如实标明，来源始终指向冻结版本和确切页面", async () => {
    read.mockResolvedValue({ ...page(1), isCurrent: false, textAccountingApplied: false });
    render(<NormalizationUnresolvedPanel subjectId="s" episodeId="e" jobId="j" />);
    expect(await screen.findByText(/这是历史资料版本/)).toBeVisible();
    expect(screen.getByText(/这次记录未逐段/)).toBeVisible();
    await openOtherText();
    const href = screen.getByRole("link").getAttribute("href")!;
    expect(href).toContain("ocrSnapshot=snapshot-frozen");
    expect(href).toContain("ocrRevision=revision-frozen");
    expect(href).toContain("sourcePage=page-0");
    expect(href).toContain("episode=e");
  });

  it("读取失败保留失败状态，可重试；不把失败当无待核对", async () => {
    read.mockRejectedValueOnce(new Error("failed")).mockResolvedValueOnce(page(1));
    render(<NormalizationUnresolvedPanel subjectId="s" episodeId="e" jobId="j" />);
    expect(await screen.findByRole("alert")).toBeVisible();
    expect(screen.queryByText(/暂无待核对/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "重新读取" }));
    await openOtherText();
    expect(await screen.findByRole("link")).toBeVisible();
  });

  it("切换受试者或节点清空旧来源，不接收迟到回答", async () => {
    let finish!: (value: ReturnType<typeof page>) => void;
    read.mockImplementationOnce(() => new Promise((resolve) => { finish = resolve; }))
      .mockResolvedValue({ ...page(0), jobId: "j2" });
    const result = render(<NormalizationUnresolvedPanel subjectId="s" episodeId="e" jobId="j" />);
    result.rerender(<NormalizationUnresolvedPanel subjectId="s2" episodeId="e2" jobId="j2" />);
    await screen.findByText(/暂无待核对/);
    finish(page(1));
    await waitFor(() => expect(screen.queryByRole("link")).not.toBeInTheDocument());
  });

  it("解码拒绝遗漏范围、重复项目和假的分页终态", () => {
    const wire = { job_id: "j", run_id: "r", content_sha256: "a".repeat(64), total: 1, offset: 0, has_more: false, is_current: true,
      text_accounting_applied: true, evidence_snapshot_id: "s", processing_revision_id: "p",
      items: [{ item_id: "i", kind: "reading_uncertainty", message: "待核对", reason: "保留原文", sources: [] }] };
    expect(decodeNormalizationUnresolved(wire).items).toHaveLength(1);
    expect(decodeNormalizationUnresolved({ ...wire, items: [{ ...wire.items[0],
      source_text_range: { excerpt: "报告日期" } }] }).items[0].sourceExcerpt).toBe("报告日期");
    expect(() => decodeNormalizationUnresolved({ ...wire, items: [{ ...wire.items[0],
      source_text_range: { excerpt: 123 } }] })).toThrow();
    expect(() => decodeNormalizationUnresolved({ ...wire, total: undefined })).toThrow();
    expect(() => decodeNormalizationUnresolved({ ...wire, has_more: true })).toThrow();
    expect(() => decodeNormalizationUnresolved({ ...wire, total: 2, items: [...wire.items, ...wire.items] })).toThrow();
    expect(() => decodeNormalizationUnresolved({ ...wire, content_sha256: "unknown" })).toThrow();
    expect(() => decodeNormalizationUnresolved({ ...wire, items: [{...wire.items[0], kind: undefined}] })).toThrow();
  });

  it("续读后清单变化不会拼接旧分页，重新读取从第一页开始", async () => {
    read.mockImplementation(async (_s, _e, _j, offset) => offset === 0 ? page(101)
      : { ...page(101, offset), contentSha256: "b".repeat(64) });
    render(<NormalizationUnresolvedPanel subjectId="s" episodeId="e" jobId="j" />);
    await screen.findByRole("heading", { name: "资料读取提示" });
    await openOtherText();
    fireEvent.click(screen.getByRole("button", {name: "加载更多"}));
    await screen.findByRole("alert");
    expect(screen.getAllByRole("link")).toHaveLength(50);
    expect(read.mock.calls.at(-1)?.[4]).toMatchObject({expectedContentSha256: "a".repeat(64)});
    fireEvent.click(screen.getByRole("button", {name: "重新读取"}));
    await waitFor(() => expect(read.mock.calls.at(-1)?.[3]).toBe(0));
    await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
    expect(screen.getByText(/尚未核清的内容仍保留/)).not.toBeVisible();
    fireEvent.click(screen.getByText("查看原件读取提示"));
    expect(screen.getByText(/尚未核清的内容仍保留/)).toBeVisible();
  });
});
