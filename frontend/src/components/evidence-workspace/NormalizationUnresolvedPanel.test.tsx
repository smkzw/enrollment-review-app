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

describe("NormalizationUnresolvedPanel", () => {
  it.each([0, 1, 101, 250])("%s项均可访问，不做前100项截断", async (total) => {
    read.mockImplementation(async (_subject, _episode, _job, offset) => page(total, offset));
    render(<NormalizationUnresolvedPanel subjectId="s" episodeId="e" jobId="j" />);
    await screen.findByRole("heading", { name: `尚未整理清楚的资料（${total}项）` });
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
    await screen.findByRole("heading", { name: "尚未整理清楚的资料（101项）" });
    fireEvent.click(screen.getByRole("button", {name: "加载更多"}));
    await screen.findByRole("alert");
    expect(screen.getAllByRole("link")).toHaveLength(50);
    expect(read.mock.calls.at(-1)?.[4]).toMatchObject({expectedContentSha256: "a".repeat(64)});
    fireEvent.click(screen.getByRole("button", {name: "重新读取"}));
    await waitFor(() => expect(read.mock.calls.at(-1)?.[3]).toBe(0));
    await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
    expect(screen.getByText(/不能证明图片、手写/)).toBeVisible();
  });
});
