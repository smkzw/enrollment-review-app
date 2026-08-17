/**
 * HTTP 方案解构仓储契约测试：错误信封解码与 wire 归一化（mock fetch）。
 */

import { describe, expect, it, vi } from "vitest";
import { createProtocolWorkbenchHttp } from "./protocolWorkbenchHttp";
import {
  normalizeIdentityReview,
  normalizeSession,
  normalizeSources,
} from "./protocolWorkbenchNormalize";
import { ProtocolWorkbenchApiError } from "./protocolWorkbenchTypes";

const SESSION_WIRE = {
  job_id: "job-http-1",
  job_type: "protocol_deconstruction",
  state: "await_identity",
  state_label: "等待方案信息确认",
  progress_completed: 4,
  progress_total: 9,
  session_kind: "first_deconstruction",
  awaiting_user: "identity",
  awaiting_user_label: "等待确认方案信息与研究期别",
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
    expect(session.stateLabel).toBe("等待方案信息确认");
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
        state_label: "等待方案信息确认",
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

  it("拒绝无法识别的研究期别投影", () => {
    expect(() =>
      normalizeSession({ ...SESSION_WIRE, selected_phase: "phase_unknown" }),
    ).toThrow("不是有效研究期别");
  });

  it("将来源响应的研究期别保持为受限枚举", () => {
    const sources = normalizeSources({
      job_id: "job-http-1",
      snapshot_id: "snapshot-1",
      selected_phase: "phase_iii",
      selected_phase_label: "III 期",
      source_spans: {},
      source_materials: {},
    });

    expect(sources.selectedPhase).toBe("phase_iii");
    expect(() =>
      normalizeSources({
        job_id: "job-http-1",
        snapshot_id: "snapshot-1",
        selected_phase: "phase_unknown",
        selected_phase_label: "未知期别",
        source_spans: {},
        source_materials: {},
      }),
    ).toThrow("不是有效研究期别");
  });

  it("将身份响应中的畸形候选归一化为可恢复错误", () => {
    const malformed = {
      job_id: "job-http-1",
      snapshot_id: "snapshot-1",
      confirmation_required: true,
      identity: {
        identity_decision_id: "identity-1",
        snapshot_id: "snapshot-1",
        status: "needs_confirmation",
        status_label: "需要确认",
        project_name: null,
        project_code: null,
        protocol_code: null,
        official_version: null,
        official_date_value: null,
        official_date_precision: null,
        study_phase: null,
        study_phase_label: null,
        confirmation_required: true,
        conflict_ids: [],
        selected_candidate_ids: [],
      },
      phase_candidates: [null],
      metadata_candidates: [],
      metadata_conflicts: [],
    } as unknown as Parameters<typeof normalizeIdentityReview>[0];

    expect(() => normalizeIdentityReview(malformed)).toThrow("应为对象");
  });

  it("listOfficialProjects 归一化正式项目列表", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(200, {
        projects: [
          {
            project_id: "project-1",
            project_code: "TEST",
            project_name: "测试研究",
            study_phase: "phase_ii",
            study_phase_label: "II 期",
            protocol_code: "TEST-001",
            official_version: "V1.0",
            official_date_value: "2026-08-14",
            official_date_precision: "day",
            rule_set_id: "ruleset-1",
            rule_set_revision: 1,
          },
        ],
      }),
    );
    const repo = createProtocolWorkbenchHttp({ fetchImpl });
    const projects = await repo.listOfficialProjects();
    expect(fetchImpl).toHaveBeenCalledWith(
      "/api/v2/protocol/projects",
      expect.objectContaining({ method: "GET" }),
    );
    expect(projects).toHaveLength(1);
    expect(projects[0]!.projectName).toBe("测试研究");
    expect(projects[0]!.studyPhaseLabel).toBe("II 期");
    expect(projects[0]!.officialVersion).toBe("V1.0");
  });

  it("getDraftComparison 解码基线、候选与差异", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(200, {
        job_id: "job-redo-1",
        baseline: {
          revision_id: "rev-base",
          draft_id: "draft-base",
          protocol_version_id: "protocol-version-1",
          official_version: "V1.0",
          revision_number: 1,
          status: "published",
          rule_count: 2,
          workflow_stage_count: 1,
          is_formal_baseline: true,
          content: { proposed_rules: [] },
          source_refs: ["span-1"],
        },
        candidate: {
          revision_id: "rev-cand",
          draft_id: "draft-cand",
          protocol_version_id: "protocol-version-2",
          official_version: "V2.1",
          revision_number: 1,
          status: "saved",
          rule_count: 2,
          workflow_stage_count: 1,
          is_formal_baseline: false,
          content: { proposed_rules: [] },
          source_refs: ["span-2"],
        },
        diff: {
          added_rule_codes: [],
          rule_diffs: [
            {
              official_code: "IN-01",
              added: false,
              removed: false,
              original_text_changes: [],
              logic_changes: [],
              time_window_changes: [],
              exception_changes: [],
              evidence_changes: [],
              due_stage_changes: [],
            },
          ],
        },
        source_bound: true,
      }),
    );
    const repo = createProtocolWorkbenchHttp({ fetchImpl });
    const comparison = await repo.getDraftComparison("job-redo-1");
    expect(fetchImpl).toHaveBeenCalledWith(
      "/api/v2/protocol/deconstructions/job-redo-1/draft/comparison",
      expect.objectContaining({ method: "GET" }),
    );
    expect(comparison.baseline.isFormalBaseline).toBe(true);
    expect(comparison.candidate.officialVersion).toBe("V2.1");
    expect(comparison.sourceBound).toBe(true);
    expect(comparison.diff.rule_diffs).toBeDefined();
  });

  it("submitFeedback 发送 snake_case 反馈正文", async () => {
    const fetchImpl = vi.fn(async (_url, init) => {
      const body = JSON.parse(String(init?.body)) as Record<string, unknown>;
      expect(body.expected_revision_id).toBe("rev-cand");
      expect(body.feedback_kind).toBe("clarification");
      expect(body.feedback_note).toContain("补充解释");
      expect(body.draft).toEqual({ proposed_rules: [] });
      return jsonResponse(200, {
        job_id: "job-redo-1",
        revision_id: "rev-cand-2",
        draft_id: "draft-cand",
        revision_number: 2,
        status: "saved",
        status_label: "已保存",
        reason: "clarification_feedback",
        reason_label: "补充解释",
        actor: "用户",
        created_at: "2026-08-17T10:00:00Z",
        study_phase: "phase_ii",
        study_phase_label: "II 期",
        protocol_code: "TEST-001",
        official_version: "V2.1",
        rule_count: 2,
        workflow_stage_count: 1,
        content: { proposed_rules: [] },
        diff: null,
      });
    });
    const repo = createProtocolWorkbenchHttp({ fetchImpl });
    const revision = await repo.submitFeedback("job-redo-1", {
      expectedRevisionId: "rev-cand",
      draft: { proposed_rules: [] },
      feedbackKind: "clarification",
      feedbackNote: "这是一条补充解释",
    });
    expect(revision.revisionNumber).toBe(2);
    expect(revision.reasonLabel).toBe("补充解释");
  });

  it("startDeconstruction 携带 project_id 进入重新解构", async () => {
    const fetchImpl = vi.fn(async (_url, init) => {
      const form = init?.body as FormData;
      expect(form.get("project_id")).toBe("project-1");
      return jsonResponse(201, {
        job_id: "job-redo-new",
        state: "await_identity",
        state_label: "等待方案信息确认",
        created: true,
        source_artifact_id: "artifact-redo",
        file_name: "新版方案.docx",
      });
    });
    const repo = createProtocolWorkbenchHttp({ fetchImpl });
    const file = new File(["content"], "新版方案.docx", { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" });
    const result = await repo.startDeconstruction(file, "redo-key", { projectId: "project-1" });
    expect(result.jobId).toBe("job-redo-new");
    expect(result.stateLabel).toBe("等待方案信息确认");
  });
});
