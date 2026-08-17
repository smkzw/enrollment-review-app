/**
 * HTTP 方案解构仓储契约测试：错误信封解码与 wire 归一化（mock fetch）。
 */

import { describe, expect, it, vi } from "vitest";
import { createProtocolWorkbenchHttp } from "./protocolWorkbenchHttp";
import { ProtocolWorkbenchApiError } from "./protocolWorkbenchTypes";

const SESSION_WIRE = {
  job_id: "job-http-1",
  job_type: "protocol_deconstruction",
  state: "await_identity",
  state_label: "等待身份确认",
  progress_completed: 4,
  progress_total: 9,
  session_kind: "first_deconstruction",
  awaiting_user: "identity",
  awaiting_user_label: "等待确认方案身份与期别",
  source_artifact_id: "artifact-1",
  file_name: "测试方案.docx",
  snapshot_id: "snapshot-1",
  draft_id: null,
  draft_revision_id: null,
  draft_revision_number: null,
  draft_status: null,
  draft_status_label: null,
  selected_phase: null,
  selected_phase_label: null,
  protocol_code: null,
  official_version: null,
  recovery_checkpoint_id: null,
  recovery_step_id: null,
  next_action: "核对方案编号、版本与研究期别",
  publishable: null,
};

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("protocolWorkbenchHttp", () => {
  it("getSession 归一化 snake_case 响应", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, SESSION_WIRE));
    const repo = createProtocolWorkbenchHttp({ fetchImpl });

    const session = await repo.getSession("job-http-1");

    expect(repo.kind).toBe("http");
    expect(fetchImpl).toHaveBeenCalledWith(
      "/api/v2/protocol/deconstructions/job-http-1",
      expect.objectContaining({ method: "GET" }),
    );
    expect(session.jobId).toBe("job-http-1");
    expect(session.stateLabel).toBe("等待身份确认");
    expect(session.fileName).toBe("测试方案.docx");
    expect(session.progressCompleted).toBe(4);
  });

  it("解码中文错误信封为 ProtocolWorkbenchApiError", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(404, {
        error: {
          code: "NOT_FOUND",
          title: "任务不存在",
          detail: "找不到对应的任务，可能已被清理或任务编号有误。",
          recovery_action: "请检查任务编号，或返回任务列表重新选择。",
          correlation_id: "abc123",
        },
      }),
    );
    const repo = createProtocolWorkbenchHttp({ fetchImpl });

    await expect(repo.getSession("missing")).rejects.toBeInstanceOf(ProtocolWorkbenchApiError);
    try {
      await repo.getSession("missing");
    } catch (error) {
      expect(error).toBeInstanceOf(ProtocolWorkbenchApiError);
      const apiError = error as ProtocolWorkbenchApiError;
      expect(apiError.code).toBe("NOT_FOUND");
      expect(apiError.title).toBe("任务不存在");
      expect(apiError.message).toContain("找不到对应");
      expect(apiError.recoveryAction).toContain("返回任务列表");
    }
  });

  it("startDeconstruction 发送 multipart 并归一化响应", async () => {
    const fetchImpl = vi.fn(async (_url, init) => {
      expect(init?.method).toBe("POST");
      expect(init?.body).toBeInstanceOf(FormData);
      const form = init?.body as FormData;
      expect(form.get("idempotency_key")).toBe("upload-key-1");
      expect(form.get("actor")).toBe("用户");
      return jsonResponse(201, {
        job_id: "job-new-1",
        state: "await_identity",
        state_label: "等待身份确认",
        created: true,
        source_artifact_id: "artifact-new",
        file_name: "方案.docx",
      });
    });
    const repo = createProtocolWorkbenchHttp({ fetchImpl });
    const file = new File(["content"], "方案.docx", {
      type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    });

    const result = await repo.startDeconstruction(file, "upload-key-1");

    expect(result.jobId).toBe("job-new-1");
    expect(result.fileName).toBe("方案.docx");
    expect(result.created).toBe(true);
  });

  it("confirmIdentity 发送 snake_case JSON 正文", async () => {
    const fetchImpl = vi.fn(async (_url, init) => {
      const body = JSON.parse(String(init?.body)) as Record<string, unknown>;
      expect(body.protocol_code).toBe("TEST-001");
      expect(body.study_phase).toBe("phase_ii");
      return jsonResponse(200, { ...SESSION_WIRE, awaiting_user: "review" });
    });
    const repo = createProtocolWorkbenchHttp({ fetchImpl });

    await repo.confirmIdentity("job-http-1", {
      protocolCode: "TEST-001",
      projectName: "测试研究",
      officialVersion: "V1.0",
      officialDateValue: "2026-08-17",
      officialDatePrecision: "day",
      studyPhase: "phase_ii",
    });

    expect(fetchImpl).toHaveBeenCalledWith(
      "/api/v2/protocol/deconstructions/job-http-1/identity/confirm",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("传递 AbortSignal 至 fetch", async () => {
    const controller = new AbortController();
    const fetchImpl = vi.fn(async (_url, init) => {
      expect(init?.signal).toBe(controller.signal);
      return jsonResponse(200, SESSION_WIRE);
    });
    const repo = createProtocolWorkbenchHttp({ fetchImpl });

    await repo.getSession("job-http-1", { signal: controller.signal });
  });
});
