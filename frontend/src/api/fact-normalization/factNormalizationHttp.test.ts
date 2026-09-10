import { describe, expect, it, vi } from "vitest";
import { createFactNormalizationHttp } from "./factNormalizationHttp";
import {
  factNormalizationCommandPath,
  factNormalizationJobPath,
  factNormalizationJobRetryPath,
} from "./endpoints";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("个例档案整理 HTTP 仓储", () => {
  it("命令路径集中在 endpoints，请求体只含幂等意图", async () => {
    const fetchImpl = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toBe(
        factNormalizationCommandPath("subject-1", "episode-1"),
      );
      expect(init?.method).toBe("POST");
      expect(JSON.parse(String(init?.body))).toEqual({
        idempotency_intent: "client-intent-1",
      });
      return jsonResponse({
        job_id: "job-1",
        run_id: "run-1",
        created: true,
        state: "queued",
        state_label: "等待处理",
        recovery_action: "无需操作，正在等待开始。",
      });
    });

    const repo = createFactNormalizationHttp({ fetchImpl: fetchImpl as typeof fetch });
    const result = await repo.startFactNormalization("subject-1", "episode-1", {
      idempotencyKey: "client-intent-1",
    });
    expect(result.jobId).toBe("job-1");
    expect(result.runId).toBe("run-1");
    expect(result.created).toBe(true);
  });

  it("任务状态与重试走标准 /api/v2/jobs 路径", async () => {
    const fetchImpl = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === factNormalizationJobRetryPath("job-1")) {
        expect(init?.method).toBe("POST");
        return jsonResponse({
          job_id: "job-1",
          state: "queued",
          state_label: "等待处理",
          changed: true,
        });
      }
      expect(url).toBe(factNormalizationJobPath("job-1"));
      return jsonResponse({
        job_id: "job-1",
        state: "failed_retryable",
        state_label: "未完成，稍后重试",
        cancel_requested: false,
        progress_completed: 1,
        progress_total: 2,
        recovery_action: "请点击重新整理个例档案。",
        created_at: "2026-08-23T10:00:00Z",
        updated_at: "2026-08-23T10:01:00Z",
      });
    });

    const repo = createFactNormalizationHttp({ fetchImpl: fetchImpl as typeof fetch });
    const status = await repo.getFactNormalizationJobStatus("job-1");
    expect(status.state).toBe("failed_retryable");
    expect(status.recoveryAction).toContain("重新整理个例档案");

    const action = await repo.retryFactNormalizationJob("job-1");
    expect(action.changed).toBe(true);
  });

  it("保留标准错误信封中的具体问题与恢复动作", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(
        {
          error: {
            code: "FACT_NORMALIZATION_CONFIG_UNAVAILABLE",
            title: "个例档案暂时无法整理",
            detail: "当前没有可用的个例档案整理配置。",
            recovery_action: "请启动本机模型服务后重新整理。",
            correlation_id: "local-correlation-1",
            context: null,
          },
        },
        409,
      ),
    );

    const repo = createFactNormalizationHttp({ fetchImpl: fetchImpl as typeof fetch });

    await expect(
      repo.startFactNormalization("subject-1", "episode-1", {
        idempotencyKey: "client-intent-1",
      }),
    ).rejects.toMatchObject({
      code: "FACT_NORMALIZATION_CONFIG_UNAVAILABLE",
      title: "个例档案暂时无法整理",
      message: "当前没有可用的个例档案整理配置。",
      recoveryAction: "请启动本机模型服务后重新整理。",
      statusCode: 409,
    });
  });
});
