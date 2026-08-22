import { describe, expect, it, vi } from "vitest";
import { getEvidenceJobDetail } from "./evidenceJobHttp";
import { EvidenceApiError } from "./evidenceViewModels";

function statusPayload(state = "completed") {
  return {
    job_id: "job-1",
    job_type: "evidence_processing",
    state,
    state_label: state === "completed" ? "已完成" : "未完成，需要处理",
    cancel_requested: false,
    progress_completed: 1,
    progress_total: 1,
    error_code: null,
    error_classification: null,
    retryable_scope: [],
    recovery_action: "请核对当前进度。",
    created_at: "2026-08-21T08:00:00Z",
    updated_at: "2026-08-21T08:01:00Z",
    last_event_seq: 1,
    steps: [],
    events: [],
  };
}

function progressPayload(failedPages: number) {
  return {
    job_id: "job-1",
    job_state: failedPages > 0 ? "failed_final" : "completed",
    job_state_label: failedPages > 0 ? "未完成，需要处理" : "已完成",
    total_pages: 2,
    completed_pages: 2 - failedPages,
    failed_pages: failedPages,
    pending_pages: 0,
    scope_note: "当前进度仅覆盖需要文字识别的页面。",
    files: [],
  };
}

describe("资料整理任务读取", () => {
  it("拒绝总体已完成但仍有失败页的矛盾组合", async () => {
    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
      const target = String(input);
      const payload = target.endsWith("/evidence-progress")
        ? progressPayload(1)
        : statusPayload("completed");
      return new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });

    await expect(getEvidenceJobDetail("job-1", undefined, fetchImpl))
      .rejects.toMatchObject({ code: "INCONSISTENT_PROGRESS" } satisfies Partial<EvidenceApiError>);
  });
});
