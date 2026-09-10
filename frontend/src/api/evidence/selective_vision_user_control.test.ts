/** 选择性视觉核验用户控制：任务状态解码只暴露中文业务字段，人工重试闭环复用现有任务接口。 */

import { describe, expect, it, vi } from "vitest";
import {
  decodeEvidenceJobProgress,
  decodeEvidenceJobStatus,
  decodeSelectiveVisionTask,
} from "./evidenceJobViewModels";
import {
  cancelSelectiveVisionTask,
  getEvidenceJobDetail,
  getSelectiveVisionTask,
  retryEvidenceJob,
} from "./evidenceJobHttp";
import { EvidenceApiError, EvidenceDecodeError } from "./evidenceViewModels";

/** 模拟 /api/v2/jobs/{id} 的完整线格式：业务字段之外还夹带内部工程字段。 */
function selectiveVisionStatusPayload() {
  return {
    job_id: "job-svo-1",
    job_type: "selective_vision_postprocess",
    state: "failed_final",
    state_label: "未完成，需要处理",
    cancel_requested: false,
    progress_completed: 0,
    progress_total: 1,
    // —— 以下为内部工程字段：用户界面投影不得携带 ——
    error_code: "SELECTIVE_VISION_PLAN_VERSION_UNSUPPORTED",
    error_classification: "non_retryable",
    retryable_scope: ["run_selective_vision"],
    lease_generation: 3,
    recovery_action: "可以点击“重新处理失败部分”；已完成内容不会重复处理。",
    created_at: "2026-08-31T12:00:00Z",
    updated_at: "2026-08-31T12:01:00Z",
    last_event_seq: 2,
    steps: [
      {
        step_id: "run_selective_vision",
        name: "选择性视觉后处理",
        state: "failed_final",
        state_label: "未完成，需要处理",
        attempt: 1,
        max_attempts: 3,
        retryable: true,
        error_code: "SELECTIVE_VISION_PLAN_VERSION_UNSUPPORTED",
        error_classification: "non_retryable",
      },
    ],
    events: [
      {
        seq: 1,
        job_event_id: "event-svo-1",
        job_id: "job-svo-1",
        event_type: "step_failed",
        event_type_label: "本项处理未完成",
        step_id: "run_selective_vision",
        occurred_at: "2026-08-31T12:01:00Z",
        attempt: 1,
        checkpoint_id: null,
        retryable: false,
        progress_completed: 0,
        progress_total: 1,
        payload: { error_code: "SELECTIVE_VISION_PLAN_VERSION_UNSUPPORTED" },
      },
    ],
  };
}

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("选择性视觉任务状态解码", () => {
  it("解码结果只包含业务字段，不携带错误分类/载荷/租约等内部字段", () => {
    const view = decodeEvidenceJobStatus(selectiveVisionStatusPayload());

    expect(Object.keys(view).sort()).toEqual(
      [
        "cancelRequested",
        "createdAt",
        "events",
        "isPageReview",
        "isTargetedReview",
        "jobId",
        "progressCompleted",
        "progressTotal",
        "recoveryAction",
        "state",
        "stateLabel",
        "steps",
        "updatedAt",
      ].sort(),
    );
    const rendered = JSON.stringify(view);
    for (const marker of [
      "SELECTIVE_VISION_PLAN_VERSION_UNSUPPORTED",
      "error_classification",
      "lease_generation",
      "non_retryable",
      "last_event_seq",
      '"payload"',
    ]) {
      expect(rendered).not.toContain(marker);
    }
    // stepId 属于既有任务视图合同（组件只作 key 用，不渲染）；步骤展示名必须是中文。
    expect(view.steps[0]?.name).toBe("选择性视觉后处理");
    // 中文业务标签原样保留，供界面直接渲染。
    expect(view.stateLabel).toBe("未完成，需要处理");
    expect(view.recoveryAction).toContain("重新处理失败部分");
    expect(view.steps[0]?.stateLabel).toBe("未完成，需要处理");
    expect(view.events[0]?.eventTypeLabel).toBe("本项处理未完成");
  });

  it("缺少中文状态标签时大声失败，不猜测渲染原始状态", () => {
    const payload = selectiveVisionStatusPayload();
    delete (payload as Record<string, unknown>).state_label;
    expect(() => decodeEvidenceJobStatus(payload)).toThrow(EvidenceDecodeError);
  });

  it("页面进度解码同样只包含业务字段", () => {
    const view = decodeEvidenceJobProgress({
      job_id: "job-svo-1",
      job_state: "failed_final",
      job_state_label: "未完成，需要处理",
      total_pages: 1,
      completed_pages: 0,
      failed_pages: 1,
      pending_pages: 0,
      scope_note: "本次视觉核验覆盖扫描件与低置信页面。",
      files: [],
      // 内部夹带字段必须被丢弃
      lease_generation: 1,
      payload: { anything: true },
    });

    expect(Object.keys(view).sort()).toEqual(
      [
        "completedPages",
        "failedPages",
        "files",
        "jobId",
        "jobState",
        "jobStateLabel",
        "pendingPages",
        "scopeNote",
        "totalPages",
      ].sort(),
    );
    expect(JSON.stringify(view)).not.toContain("lease_generation");
  });
});

describe("选择性视觉任务人工重试闭环", () => {
  it("重试后重新读取任务状态，返回最新业务投影", async () => {
    const calls: Array<{ path: string; method: string }> = [];
    const fetchImpl = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const target = String(input);
      const method = init?.method ?? "GET";
      calls.push({ path: target, method });
      if (target.endsWith("/retry")) {
        return jsonResponse({
          job_id: "job-svo-1",
          state: "queued",
          state_label: "等待处理",
          changed: true,
        });
      }
      const payload = selectiveVisionStatusPayload();
      return jsonResponse({
        ...payload,
        state: "queued",
        state_label: "等待处理",
      });
    });

    const status = await retryEvidenceJob("job-svo-1", fetchImpl);

    expect(calls.map((call) => call.method)).toEqual(["POST", "GET"]);
    expect(calls[0]?.path).toContain("/api/v2/jobs/job-svo-1/retry");
    expect(calls[1]?.path).toContain("/api/v2/jobs/job-svo-1");
    expect(calls[1]?.path).not.toContain("/retry");
    expect(status.state).toBe("queued");
    expect(status.stateLabel).toBe("等待处理");
  });

  it("重试被拒绝时抛出带中文恢复指引的应用错误，不泄露内部细节", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(
        {
          error: {
            code: "JOB_STATE_CONFLICT",
            title: "任务当前状态不允许该操作",
            detail: "只有失败的任务可以重试",
            recovery_action: "请等待当前处理结束，或刷新任务状态后重试。",
          },
        },
        409,
      ),
    );

    const error = await retryEvidenceJob("job-svo-1", fetchImpl).then(
      () => null,
      (value: unknown) => value,
    );
    expect(error).toBeInstanceOf(EvidenceApiError);
    const apiError = error as EvidenceApiError;
    expect(apiError.statusCode).toBe(409);
    expect(apiError.code).toBe("JOB_STATE_CONFLICT");
    expect(apiError.recoveryAction).toContain("刷新");
    expect(JSON.stringify({ message: apiError.message, title: apiError.title })).not.toContain(
      "run_selective_vision",
    );
  });

  it("状态与页面进度不属于同一任务时拒绝渲染（刷新一致性护栏）", async () => {
    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
      const target = String(input);
      if (target.endsWith("/evidence-progress")) {
        return jsonResponse({
          job_id: "job-other",
          job_state: "completed",
          job_state_label: "已完成",
          total_pages: 1,
          completed_pages: 1,
          failed_pages: 0,
          pending_pages: 0,
          scope_note: "当前进度仅覆盖需要文字识别的页面。",
          files: [],
        });
      }
      return jsonResponse({
        ...selectiveVisionStatusPayload(),
        state: "completed",
        state_label: "已完成",
      });
    });

    await expect(getEvidenceJobDetail("job-svo-1", undefined, fetchImpl)).rejects.toMatchObject(
      { code: "MISMATCHED_RESPONSE" } satisfies Partial<EvidenceApiError>,
    );
  });
});

describe("修订级页面视觉核验接口", () => {
  it("只解码中文业务字段并保留完整修订身份", () => {
    const view = decodeSelectiveVisionTask({
      evidence_processing_revision_id: "complete-1",
      found: true,
      job_id: "job-1",
      state: "failed_final",
      state_label: "未完成",
      cancel_requested: false,
      progress_completed: 0,
      progress_total: 1,
      recovery_action: "请重新开始未完成的页面核验。",
      can_retry: true,
      can_cancel: false,
      eligible_page_count: 3,
      skipped_page_count: 7,
      observation_page_count: 1,
      closed_page_count: 2,
      closed_reason_label: "部分页面暂时无法核验",
      failed_scope_label: "页面视觉核验",
      created_at: "2026-09-01T01:00:00Z",
      updated_at: "2026-09-01T01:01:00Z",
      payload: { model: "internal-model" },
      lease_generation: 4,
    });

    expect(view.evidenceProcessingRevisionId).toBe("complete-1");
    expect(view.failedScopeLabel).toBe("页面视觉核验");
    expect(JSON.stringify(view)).not.toContain("internal-model");
    expect(JSON.stringify(view)).not.toContain("lease_generation");
  });

  it("查询与停止始终使用资料版本接口", async () => {
    const calls: Array<{ path: string; method: string }> = [];
    const fetchImpl = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ path: String(input), method: init?.method ?? "GET" });
      if (init?.method === "POST") {
        return jsonResponse({
          job_id: "job-1",
          state: "cancelled",
          state_label: "已停止",
          changed: true,
        });
      }
      return jsonResponse({
        evidence_processing_revision_id: "complete-1",
        found: false,
        job_id: null,
        state: null,
        state_label: "暂无页面视觉核验任务",
        cancel_requested: false,
        progress_completed: 0,
        progress_total: 0,
        recovery_action: "重新处理资料后会自动建立。",
        can_retry: false,
        can_cancel: false,
        eligible_page_count: null,
        skipped_page_count: null,
        observation_page_count: null,
        closed_page_count: null,
        closed_reason_label: null,
        failed_scope_label: null,
        created_at: null,
        updated_at: null,
      });
    });

    await getSelectiveVisionTask("complete-1", undefined, fetchImpl);
    await cancelSelectiveVisionTask("complete-1", fetchImpl);

    expect(calls).toEqual([
      {
        path: "/api/v2/evidence-processing-revisions/complete-1/selective-vision-task",
        method: "GET",
      },
      {
        path: "/api/v2/evidence-processing-revisions/complete-1/selective-vision-task/cancel",
        method: "POST",
      },
    ]);
  });
});
