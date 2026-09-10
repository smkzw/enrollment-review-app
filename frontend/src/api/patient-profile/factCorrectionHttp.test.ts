import { describe, expect, it } from "vitest";
import type { FactCorrectionRequestInput } from "./factCorrectionTypes";
import { createPatientProfileHttp } from "./patientProfileHttp";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function correctionImpact() {
  return {
    scope_kind: "node",
    scope_kind_label: "审核节点全部事实",
    fallback_reason: "将重新整理本审核节点全部事实",
    affected_locator_ids: ["locator-1"],
    affected_document_ids: ["document-1"],
    affected_fact_ids: ["fact-1"],
    affected_event_ids: [],
    affected_exposure_ids: [],
    affected_conflict_group_ids: ["conflict-1"],
    affected_rule_link_ids: ["rule-link-1"],
    affected_expectation_ids: [],
    affected_profile_revision_ids: ["profile-revision-1"],
  };
}

function correctionPreview() {
  return {
    target_kind: "fact",
    target_kind_label: "事实",
    target_id: "fact-1",
    locator_ids: ["locator-1"],
    old_snapshot: {
      kind: "fact",
      asserted_object: "血压",
      value: "120/80",
      unit: "mmHg",
    },
    new_snapshot: {
      kind: "fact",
      asserted_object: "血压",
      value: "130/85",
      unit: "mmHg",
    },
    impact: correctionImpact(),
  };
}

function submitResponse(created: boolean) {
  return {
    job_id: "job-correction-1",
    correction_id: "correction-1",
    created,
    state: "queued",
    state_label: "等待处理",
    recovery_action: "请等待处理完成。",
  };
}

function statusResponse() {
  return {
    job_id: "job-correction-1",
    state: "failed_retryable",
    state_label: "未完成，稍后重试",
    cancel_requested: false,
    progress_completed: 1,
    progress_total: 2,
    error_code: "STALE_AUTHORITY",
    error_classification: "资料已变化",
    retryable_scope: ["本次修订"],
    recovery_action: "请返回档案重新核对。",
    created_at: "2026-08-23T08:00:00Z",
    updated_at: "2026-08-23T08:01:00Z",
    last_event_seq: 3,
  };
}

function historyResponse() {
  return {
    subject_id: "subject-1",
    review_episode_id: "episode-1",
    items: [
      {
        correction_id: "correction-1",
        target_kind: "fact",
        target_kind_label: "事实",
        target_id: "fact-1",
        new_entity_id: "fact-2",
        patient_profile_revision_id: "profile-revision-2",
        patient_profile_revision: 2,
        reason: "原始报告数值与档案记录不一致。",
        operator_id: "local-reviewer",
        locator_ids: ["locator-1"],
        corrected_at: "2026-08-23T08:00:00Z",
        old_snapshot: { kind: "fact", value: "120/80" },
        new_snapshot: { kind: "fact", value: "130/85" },
        impact: correctionImpact(),
      },
    ],
  };
}

const requestInput: FactCorrectionRequestInput = {
  targetKind: "fact",
  targetId: "fact-1",
  locatorIds: ["locator-1"],
  reason: "原始报告数值与档案记录不一致。",
  updates: {
    assertedObject: "血压",
    value: "130/85",
    unit: "mmHg",
    polarity: "affirmed",
    dateRange: {
      sourceText: "2026年3月",
      precision: "month",
      lowerBound: "2026-03-01",
      upperBound: "2026-03-31",
    },
  },
};

describe("Patient Profile fact-correction HTTP contract", () => {
  it("maps a preview request and keeps preview read-only", async () => {
    const calls: Array<{ input: RequestInfo | URL; init?: RequestInit }> = [];
    const repo = createPatientProfileHttp({
      fetchImpl: ((input, init) => {
        calls.push({ input, init });
        return Promise.resolve(jsonResponse(correctionPreview()));
      }) as typeof fetch,
    });

    const preview = await repo.previewFactCorrection("subject 1", "episode/1", requestInput);
    expect(preview.impact.scopeKind).toBe("node");
    expect(preview.impact.affectedConflictGroupIds).toEqual(["conflict-1"]);
    expect(calls).toHaveLength(1);
    expect(String(calls[0].input)).toBe(
      "/api/v2/subjects/subject%201/review-episodes/episode%2F1/fact-corrections/preview",
    );
    expect(calls[0].init?.method).toBe("POST");
    expect(JSON.parse(String(calls[0].init?.body))).toEqual({
      target_kind: "fact",
      target_id: "fact-1",
      locator_ids: ["locator-1"],
      reason: requestInput.reason,
      asserted_object: "血压",
      value: "130/85",
      unit: "mmHg",
      polarity: "affirmed",
      date_range: {
        source_text: "2026年3月",
        precision: "month",
        lower_bound: "2026-03-01",
        upper_bound: "2026-03-31",
      },
    });
  });

  it("decodes both created and HTTP 200 idempotent submit responses without changing the request", async () => {
    const bodies: string[] = [];
    const responses = [submitResponse(true), submitResponse(false)];
    const repo = createPatientProfileHttp({
      fetchImpl: ((input, init) => {
        expect(String(input)).toContain("/fact-corrections");
        bodies.push(String(init?.body));
        return Promise.resolve(jsonResponse(responses.shift()));
      }) as typeof fetch,
    });

    const first = await repo.submitFactCorrection("subject-1", "episode-1", requestInput);
    const second = await repo.submitFactCorrection("subject-1", "episode-1", requestInput);
    expect(first.created).toBe(true);
    expect(second.created).toBe(false);
    expect(second.jobId).toBe(first.jobId);
    expect(bodies[1]).toBe(bodies[0]);
  });

  it("decodes immutable history, conflict impact and stale status", async () => {
    const repo = createPatientProfileHttp({
      fetchImpl: ((input) => {
        if (String(input).includes("fact-corrections")) return Promise.resolve(jsonResponse(historyResponse()));
        return Promise.resolve(jsonResponse(statusResponse()));
      }) as typeof fetch,
    });

    const history = await repo.listFactCorrectionHistory("subject-1", "episode-1");
    const status = await repo.getFactCorrectionJobStatus("job-correction-1");
    expect(history.items[0]?.reason).toContain("原始报告");
    expect(history.items[0]?.impact.affectedConflictGroupIds).toEqual(["conflict-1"]);
    expect(history.items[0]?.profileRevision).toBe(2);
    expect(status.state).toBe("failed_retryable");
    expect(status.errorCode).toBe("STALE_AUTHORITY");
  });
});
