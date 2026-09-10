import { describe, expect, it } from "vitest";
import {
  decodeFactNormalizationCommand,
  decodeFactNormalizationJobStatus,
  decodeFactNormalizationError,
  factNormalizationDisplayPhase,
  factNormalizationPhaseTitle,
  factNormalizationRecoveryHint,
  FactNormalizationDecodeError,
} from "./factNormalizationViewModels";

describe("个例档案整理解码与中文投影", () => {
  it("解码命令响应并保留幂等复用标记", () => {
    const view = decodeFactNormalizationCommand({
      job_id: "job-1",
      run_id: "run-1",
      created: false,
      state: "queued",
      state_label: "等待处理",
      recovery_action: "无需操作，正在等待开始。",
    });
    expect(view.jobId).toBe("job-1");
    expect(view.runId).toBe("run-1");
    expect(view.created).toBe(false);
    expect(view.state).toBe("queued");
  });

  it("解码标准任务状态", () => {
    const view = decodeFactNormalizationJobStatus({
      job_id: "job-1",
      state: "running",
      state_label: "正在处理",
      cancel_requested: false,
      progress_completed: 1,
      progress_total: 3,
      recovery_action: "正在处理；关闭页面不会中断已经确认的工作。",
      created_at: "2026-08-23T10:00:00Z",
      updated_at: "2026-08-23T10:01:00Z",
    });
    expect(view.progressCompleted).toBe(1);
    expect(view.progressTotal).toBe(3);
  });

  it("未知状态拒绝解码", () => {
    expect(() =>
      decodeFactNormalizationJobStatus({
        job_id: "job-1",
        state: "pipeline_running",
        state_label: "running",
        cancel_requested: false,
        progress_completed: 0,
        progress_total: 1,
        recovery_action: "x",
        created_at: "2026-08-23T10:00:00Z",
        updated_at: "2026-08-23T10:00:00Z",
      }),
    ).toThrow(FactNormalizationDecodeError);
  });

  it("五类精简中文相位与恢复动作", () => {
    expect(factNormalizationDisplayPhase("queued")).toBe("queued");
    expect(factNormalizationDisplayPhase("running")).toBe("running");
    expect(factNormalizationDisplayPhase("completed")).toBe("succeeded");
    expect(factNormalizationDisplayPhase("failed_retryable")).toBe("failed");
    expect(factNormalizationDisplayPhase("completed", { profileStale: true })).toBe("stale");

    expect(factNormalizationPhaseTitle("queued")).toBe("个例档案整理排队中");
    expect(factNormalizationPhaseTitle("running")).toBe("正在整理个例档案");
    expect(factNormalizationPhaseTitle("succeeded")).toBe("个例档案已整理完成");
    expect(factNormalizationPhaseTitle("failed")).toBe("个例档案整理未完成");
    expect(factNormalizationPhaseTitle("stale")).toBe("资料已更新，需重新整理个例档案");

    expect(factNormalizationRecoveryHint("failed")).toContain("重新整理个例档案");
    expect(factNormalizationRecoveryHint("stale")).toContain("上一版内容仍可查阅");
  });

  it("错误信封解码为中文恢复动作", () => {
    const error = decodeFactNormalizationError(
      {
        error: {
          code: "STALE_AUTHORITY",
          title: "资料已变化",
          detail: "当前资料版本已更新。",
          recovery_action: "请重新整理个例档案。",
          correlation_id: "local-correlation-1",
          context: null,
        },
      },
      409,
    );
    expect(error.statusCode).toBe(409);
    expect(error.recoveryAction).toBe("请重新整理个例档案。");
    expect(error.message).not.toMatch(/pipeline|schema|provider/i);
  });
});
