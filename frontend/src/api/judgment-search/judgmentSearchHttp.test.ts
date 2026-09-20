import { describe, expect, it, vi } from "vitest";
import {
  createJudgmentSearchHttp,
  decodeJudgmentSearchResults,
  decodeJudgmentSearchStatus,
  JudgmentSearchDecodeError,
} from "./judgmentSearchHttp";

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const statusPayload = {
  job_id: "job-1",
  state: "running",
  state_label: "正在处理",
  total_pages: 3,
  completed_reads: 1,
  total_reads: 3,
  requirement_results: [
    {
      requirement_id: "req-1",
      status: "coverage_incomplete",
      status_label: "检索尚未完成（部分页面未读取或内容不清）",
      found_candidate_count: 0,
    },
  ],
  can_resume: false,
};

const resultPayload = {
  job_id: "job-1",
  state: "completed",
  searched_page_count: 3,
  results: [
    {
      requirement_id: "req-1",
      requirement_label: "ALT 升高的研究者临床意义判断",
      status: "candidates_present",
      status_label: "已发现疑似研究者书面判断的内容，待人工核对原件",
      found_candidates: [
        {
          lane: "main-A",
          lane_label: "第一次识别",
          channel: "handwritten",
          channel_label: "手写内容",
          source_document_version_id: "doc-1",
          page_artifact_id: "page-1",
          page_number: 2,
          excerpts: [
            {
              text: "研究者判断文字",
              bbox: null,
              coordinate_convention: "unverified",
              uncertainty_note: null,
            },
          ],
        },
      ],
      incomplete_pages: [],
    },
  ],
};

describe("判断检索 HTTP client", () => {
  it("不同原件的同一页码保留独立来源身份", () => {
    const payload = {
      ...resultPayload,
      results: [{ ...resultPayload.results[0], incomplete_pages: [
        { source_document_version_id: "doc-a", page_artifact_id: "page-a", page_number: 1, reasons: ["尚未读完"] },
        { source_document_version_id: "doc-b", page_artifact_id: "page-b", page_number: 1, reasons: ["内容不清"] },
      ] }],
    };
    expect(decodeJudgmentSearchResults(payload).results[0]?.incompletePages).toEqual([
      { sourceDocumentVersionId: "doc-a", pageArtifactId: "page-a", pageNumber: 1, reasons: ["尚未读完"] },
      { sourceDocumentVersionId: "doc-b", pageArtifactId: "page-b", pageNumber: 1, reasons: ["内容不清"] },
    ]);
    const missingIdentity = {
      ...payload,
      results: [{ ...payload.results[0], incomplete_pages: [{ page_number: 1, reasons: [] }] }],
    };
    expect(() => decodeJudgmentSearchResults(missingIdentity)).toThrow(JudgmentSearchDecodeError);
  });

  it("四个端点使用正确路径、方法和严格视图", async () => {
    const fetchImpl = vi.fn()
      .mockResolvedValueOnce(response({ job_id: "job-1", state: "queued", state_label: "等待处理", created: true }))
      .mockResolvedValueOnce(response(statusPayload))
      .mockResolvedValueOnce(response(resultPayload))
      .mockResolvedValueOnce(response({ job_id: "job-1", state: "queued", changed: true, state_label: "等待处理" }));
    const api = createJudgmentSearchHttp({ fetchImpl });

    await expect(api.start("subject/1", "episode/1")).resolves.toMatchObject({ jobId: "job-1", created: true });
    await expect(api.status("subject/1", "episode/1", "job-1")).resolves.toMatchObject({ completedReads: 1 });
    await expect(api.results("subject/1", "episode/1", "job-1")).resolves.toMatchObject({ searchedPageCount: 3 });
    await expect(api.resume("subject/1", "episode/1", "job-1")).resolves.toMatchObject({ changed: true });

    expect(fetchImpl).toHaveBeenNthCalledWith(
      1,
      "/api/v2/subjects/subject%2F1/review-episodes/episode%2F1/judgment-search-jobs",
      expect.objectContaining({ method: "POST", body: "{}" }),
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      3,
      "/api/v2/subjects/subject%2F1/review-episodes/episode%2F1/judgment-search-jobs/job-1/results",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("缺少必填字段时抛出带中文路径的严格解码错误", () => {
    const invalid = { ...statusPayload } as Record<string, unknown>;
    delete invalid.state_label;
    expect(() => decodeJudgmentSearchStatus(invalid)).toThrow("status.state_label 缺少字段");
    expect(() => decodeJudgmentSearchStatus(invalid)).toThrow(JudgmentSearchDecodeError);
  });

  it("发现未知字段时拒绝响应，而不是静默忽略", () => {
    expect(() => decodeJudgmentSearchStatus({ ...statusPayload, extra: true })).toThrow("status 含未知字段");
  });

  it("字段类型不符时拒绝响应并指出字段位置", () => {
    expect(() => decodeJudgmentSearchResults({ ...resultPayload, searched_page_count: "3" })).toThrow(
      "results.searched_page_count 应为非负整数",
    );
  });

  it("结果端点只允许 status 为 null，其他字段仍严格校验", () => {
    const pending = {
      ...resultPayload,
      results: [{ ...resultPayload.results[0], status: null, found_candidates: [] }],
    };
    expect(decodeJudgmentSearchResults(pending).results[0]?.status).toBeNull();
    expect(() => decodeJudgmentSearchStatus({ ...statusPayload, requirement_results: [{ ...statusPayload.requirement_results[0], status: null }] })).toThrow();
  });
});
