import { describe, expect, it } from "vitest";
import {
  decodeEvidenceJobProgress,
  decodeEvidenceJobStatus,
} from "./evidenceJobViewModels";

describe("资料整理任务解码", () => {
  it("只投影用户需要的状态、阶段和处理记录", () => {
    const result = decodeEvidenceJobStatus({
      job_id: "job-1",
      job_type: "evidence_processing",
      state: "completed",
      state_label: "已完成",
      cancel_requested: false,
      progress_completed: 1,
      progress_total: 1,
      error_code: null,
      error_classification: "internal-only",
      retryable_scope: [],
      recovery_action: "本次处理已完成。",
      created_at: "2026-08-21T08:00:00Z",
      updated_at: "2026-08-21T08:01:00Z",
      last_event_seq: 2,
      steps: [{
        step_id: "evidence_processing",
        name: "evidence_processing",
        state: "completed",
        state_label: "已完成",
        attempt: 1,
        max_attempts: 2,
        retryable: true,
        error_code: null,
        error_classification: null,
        retry_not_before: null,
        depends_on: [],
      }],
      events: [{
        seq: 1,
        job_event_id: "event-1",
        event_type: "completed",
        event_type_label: "本次处理已完成",
        step_id: null,
        occurred_at: "2026-08-21T08:01:00Z",
        attempt: 1,
        checkpoint_id: "hidden",
        retryable: false,
        progress_completed: 1,
        progress_total: 1,
        payload: { hidden: true },
      }],
    });

    expect(result.stateLabel).toBe("已完成");
    expect(result.steps[0]?.name).toBe("evidence_processing");
    expect(result).not.toHaveProperty("jobType");
    expect(result).not.toHaveProperty("errorClassification");
    expect(result.events[0]).not.toHaveProperty("payload");
  });

  it("投影每份文件的页级完成、失败和等待数量", () => {
    const result = decodeEvidenceJobProgress({
      job_id: "job-1",
      job_state: "running",
      job_state_label: "正在处理",
      total_pages: 6,
      completed_pages: 3,
      failed_pages: 1,
      pending_pages: 2,
      scope_note: "当前进度仅覆盖需要文字识别的页面。",
      files: [{
        source_document_version_id: "doc-1",
        file_name: "筛选病历.pdf",
        page_total: 6,
        page_succeeded: 3,
        page_failed: 1,
        status: "partial",
        status_label: "部分完成",
      }],
    });

    expect(result.files[0]).toMatchObject({
      fileName: "筛选病历.pdf",
      pageTotal: 6,
      pageSucceeded: 3,
      pageFailed: 1,
    });
  });
});
