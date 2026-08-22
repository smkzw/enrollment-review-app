import { describe, expect, it, vi } from "vitest";
import { EvidenceApiError, EvidenceDecodeError } from "./evidenceViewModels";
import { createEvidenceHttp } from "./evidenceHttp";

function revisionWire() {
  return {
    evidence_processing_revision_id: "revision-1",
    revision_kind: "complete",
    revision_kind_label: "完整处理修订",
    evidence_snapshot_id: "snapshot-1",
    base_processing_revision_id: null,
    project_id: "project-1",
    subject_id: "subject-1",
    review_episode_id: "episode-1",
    status: "active",
    status_label: "当前有效",
    is_activatable: false,
    is_current: true,
    manifest_sha256: "a".repeat(64),
    completion_manifest_sha256: null,
    pages: [{
      entry_id: "entry-1",
      position: 1,
      source_document_version_id: "version-1",
      page_number: 1,
      original_frame: null,
      page_artifact_id: "artifact-1",
      ocr_page_id: "ocr-page-1",
      status: "succeeded",
      status_label: "页面已就绪",
      failure_reason: null,
      image_available: true,
      page_width: 1240,
      page_height: 1754,
    }],
    risk_flag_count: 0,
    pending_risk_flag_count: 0,
    locator_ids: [],
    risk_scan_ids: [],
    risk_review_ids: [],
    correction_ids: [],
    metadata_revision_ids: [],
    referenced_document_revision_ids: [],
    resolution_revision_ids: [],
    gates: [],
    created_at: "2026-08-21T00:00:00Z",
    created_by: "本地用户",
  };
}

function pageWire() {
  return {
    ocr_page_id: "ocr-page-1",
    page_artifact_id: "artifact-1",
    source_document_version_id: "version-1",
    page_number: 1,
    source_sha256: "a".repeat(64),
    raw_text: "原始文字",
    raw_text_sha256: "b".repeat(64),
    status: "succeeded",
    status_label: "已识别",
    processing_revision_id: "revision-1",
    is_current_revision: true,
    effective_text: null,
    effective_text_sha256: null,
    selected_corrections: [],
    risk_scans: [],
    risk_reviews: [],
    locators: [],
  };
}

function correctionResponseWire() {
  return {
    correction: {
      correction_id: "correction-1",
      ocr_page_id: "ocr-page-1",
      raw_text_sha256: "a".repeat(64),
      text_start: 0,
      text_end: 2,
      original_text: "原文",
      corrected_text: "校对",
      change_kind: "other_text",
      change_kind_label: "文字校对",
      requires_confirmation: false,
      confirmation_actor: null,
      confirmation_at: null,
      reason: "我的说明",
      actor: "本地用户",
      base_processing_revision_id: "revision-1",
      supersedes_correction_id: null,
      affected_scope: [],
      created_at: "2026-08-21T00:00:00Z",
    },
    created: true,
    candidate_id: "candidate-1",
    job_id: "job-1",
    candidate_status: "staged",
    candidate_status_label: "待处理",
    candidate_event_seq: 3,
    complete_revision_id: null,
  };
}

function riskReviewResponseWire() {
  return {
    review: {
      review_id: "review-1",
      risk_flag_id: "scan-1:risk-1",
      decision: "confirmed_as_read",
      decision_label: "确认识别无误",
      reason: "已与原始资料核对",
      actor: "本地用户",
      base_processing_revision_id: "revision-1",
      expected_revision: 1,
      created_at: "2026-08-21T00:00:00Z",
    },
    created: true,
    candidate_id: "candidate-2",
    job_id: "job-2",
    candidate_status: "processing",
    candidate_status_label: "处理中",
    candidate_event_seq: 4,
    complete_revision_id: null,
  };
}

function riskPageReviewResponseWire() {
  const review = riskReviewResponseWire().review;
  return {
    page_review: {
      page_review_id: "page-review-1",
      ocr_page_id: "ocr-page-1",
      scan_id: "scan-1",
      raw_text_sha256: "b".repeat(64),
      scanner_rule_version: "risk-1",
      decision: "confirmed_as_read",
      decision_label: "已对照原件确认",
      reason: "已对照右侧原件逐项核对本页识别内容",
      actor: "本地用户",
      base_processing_revision_id: "revision-1",
      expected_revision: 1,
      covered_flag_ids: ["scan-1:risk-1"],
      created_review_ids: ["review-1"],
      covered_flag_sha256: "d".repeat(64),
      created_at: "2026-08-21T00:00:00Z",
    },
    reviews: [review],
    created: true,
    candidate_id: "candidate-2",
    job_id: "job-2",
    candidate_status: "processing",
    candidate_status_label: "处理中",
    candidate_event_seq: 4,
    complete_revision_id: null,
  };
}

function metadataResponseWire(overrides: Record<string, unknown> = {}) {
  return {
    metadata: {
      metadata_revision_id: "metadata-2",
      source_document_version_id: "version-1",
      document_type: "影像学检查",
      source_party: "中心影像科",
      reason: "已与原始资料核对。",
      is_auto_suggestion: false,
      supersedes_metadata_revision_id: "metadata-1",
      revision: 2,
      created_at: "2026-08-21T00:00:00Z",
      created_by: "医学监查员",
      ...overrides,
    },
    created: true,
  };
}

describe("证据处理 HTTP 仓储", () => {
  it("一次提交并解码整页风险核对", async () => {
    const fetchImpl = vi.fn<typeof fetch>(async () =>
      new Response(JSON.stringify(riskPageReviewResponseWire()), { status: 200 }),
    );
    const repository = createEvidenceHttp({ fetchImpl });
    const result = await repository.createRiskPageReview("ocr-page-1", {
      scan_id: "scan-1",
      decision: "confirmed_as_read",
      reason: "已对照右侧原件逐项核对本页识别内容",
      base_processing_revision_id: "revision-1",
      expected_revision: 1,
      idempotency_key: "page-review-idem",
    });

    expect(result).toMatchObject({
      pageReviewId: "page-review-1",
      coveredFlagIds: ["scan-1:risk-1"],
      candidateStatus: "processing",
    });
    expect(fetchImpl.mock.calls[0]?.[0]).toContain(
      "/ocr-pages/ocr-page-1/risk-page-reviews",
    );
  });

  it("PATCH 追加资料信息修订并完整解码响应", async () => {
    const fetchImpl = vi.fn<typeof fetch>(async () =>
      new Response(JSON.stringify(metadataResponseWire({
        source_document_version_id: "version/1",
      })), { status: 201 }),
    );
    const repository = createEvidenceHttp({ fetchImpl });
    const result = await repository.reviseSourceDocumentMetadata("version/1", {
      document_type: "影像学检查",
      source_party: "中心影像科",
      reason: "已与原始资料核对。",
      expected_metadata_revision: 1,
      idempotency_key: "metadata-idem-1",
      actor: "医学监查员",
    });

    expect(result).toMatchObject({
      created: true,
      metadata: {
        metadataRevisionId: "metadata-2",
        sourceDocumentVersionId: "version/1",
        documentType: "影像学检查",
        sourceParty: "中心影像科",
        revision: 2,
      },
    });
    expect(fetchImpl.mock.calls[0]?.[0]).toContain(
      "/source-document-versions/version%2F1/metadata",
    );
    expect(fetchImpl.mock.calls[0]?.[1]).toMatchObject({
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
    });
    expect(JSON.parse(String(fetchImpl.mock.calls[0]?.[1]?.body))).toEqual({
      document_type: "影像学检查",
      source_party: "中心影像科",
      reason: "已与原始资料核对。",
      expected_metadata_revision: 1,
      idempotency_key: "metadata-idem-1",
      actor: "医学监查员",
    });
  });

  it("资料信息修订冲突保留服务端当前值和自然中文恢复提示", async () => {
    const fetchImpl = vi.fn<typeof fetch>(async () =>
      new Response(JSON.stringify({
        error: {
          code: "STALE_REVISION",
          title: "资料信息已发生变化",
          detail: "其他窗口已更新这份资料的类型或来源方。",
          recovery_action: "请核对系统当前记录后再提交。",
          context: {
            submitted: { expected_metadata_revision: 1 },
            current_record: { revision: 2, document_type: "影像学检查" },
            field_diff: { revision: { submitted: 1, current: 2 } },
          },
        },
      }), { status: 409 }),
    );
    const repository = createEvidenceHttp({ fetchImpl });

    await expect(repository.reviseSourceDocumentMetadata("version-1", {
      document_type: "检查报告",
      source_party: "研究中心",
      reason: "已核对。",
      expected_metadata_revision: 1,
      idempotency_key: "metadata-idem-conflict",
    })).rejects.toMatchObject({
      statusCode: 409,
      message: "其他窗口已更新这份资料的类型或来源方。",
      recoveryAction: "请核对系统当前记录后再提交。",
      conflictContext: {
        currentRecord: { revision: 2, document_type: "影像学检查" },
      },
    });
  });

  it.each([
    ["缺少创建人", metadataResponseWire({ created_by: undefined })],
    [
      "响应指向另一份资料",
      metadataResponseWire({ source_document_version_id: "version-other" }),
    ],
  ])("拒绝无法可信使用的资料信息响应：%s", async (_label, payload) => {
    const fetchImpl = vi.fn<typeof fetch>(async () =>
      new Response(JSON.stringify(payload), { status: 200 }),
    );
    const repository = createEvidenceHttp({ fetchImpl });
    await expect(repository.reviseSourceDocumentMetadata("version-1", {
      document_type: "检查报告",
      source_party: "研究中心",
      reason: "已核对。",
      expected_metadata_revision: 1,
      idempotency_key: "metadata-idem-invalid",
    })).rejects.toBeInstanceOf(EvidenceDecodeError);
  });

  it("使用活动修订 ID 查询真实处理修订和页详情", async () => {
    const fetchImpl = vi.fn<typeof fetch>(async (input) => {
      const url = String(input);
      return new Response(JSON.stringify(url.includes("ocr-pages") ? pageWire() : revisionWire()), { status: 200 });
    });
    const repository = createEvidenceHttp({ fetchImpl });
    const revision = await repository.getProcessingRevision("revision 1");
    const page = await repository.getOcrPage("ocr page/1", revision.revisionId);
    expect(revision.pages[0]?.ocrPageId).toBe("ocr-page-1");
    expect(page.ocrPageId).toBe("ocr-page-1");
    expect(fetchImpl.mock.calls[0]?.[0]).toContain("evidence-processing-revisions/revision%201");
    expect(fetchImpl.mock.calls[1]?.[0]).toContain("ocr-pages/ocr%20page%2F1?processing_revision_id=revision-1");
  });

  it("把 HTTP 409 解码为带服务端当前差异的 EvidenceApiError", async () => {
    const fetchImpl = vi.fn<typeof fetch>(async () =>
      new Response(JSON.stringify({
        error: {
          code: "STALE_REVISION",
          title: "资料已发生变化",
          detail: "服务端已有更新，请核对差异。",
          recovery_action: "请核对后再提交。",
          context: {
            submitted: { reason: "我的说明" },
            current_record: { reason: "服务端说明" },
            field_diff: { reason: { submitted: "我的说明", current: "服务端说明" } },
          },
        },
      }),
      { status: 409 },
    ));
    const repository = createEvidenceHttp({ fetchImpl });
    await expect(repository.createCorrection("ocr-page-1", {
      raw_text_sha256: "a".repeat(64),
      text_start: 0,
      text_end: 2,
      original_text: "原文",
      corrected_text: "校对",
      change_kind: "other_text",
      reason: "我的说明",
      base_processing_revision_id: "revision-1",
      expected_revision: 1,
      idempotency_key: "idem-1",
    })).rejects.toMatchObject({ statusCode: 409 });
    try {
      await repository.createCorrection("ocr-page-1", {
        raw_text_sha256: "a".repeat(64), text_start: 0, text_end: 2,
        original_text: "原文", corrected_text: "校对", change_kind: "other_text",
        reason: "我的说明", base_processing_revision_id: "revision-1",
        expected_revision: 1, idempotency_key: "idem-2",
      });
    } catch (error) {
      expect(error).toBeInstanceOf(EvidenceApiError);
      expect((error as EvidenceApiError).conflictContext?.currentRecord.reason).toBe("服务端说明");
    }
  });

  it("转发候选续接字段，并解码三类异步处理返回", async () => {
    const fetchImpl = vi.fn<typeof fetch>(async (input) => {
      const url = String(input);
      const payload = url.includes("/evidence-processing-candidates/")
        ? {
            candidate_id: "candidate-3",
            job_id: "job-3",
            candidate_status: "needs_attention",
            candidate_status_label: "需要关注",
            candidate_event_seq: 2,
            complete_revision_id: null,
          }
        : url.includes("/corrections")
        ? correctionResponseWire()
        : url.includes("/risk-reviews")
          ? riskReviewResponseWire()
          : {
              candidate_id: "candidate-3",
              job_id: "job-3",
              candidate_status: "ready",
              candidate_status_label: "待发布",
              candidate_event_seq: 5,
              complete_revision_id: "revision-1",
              created: true,
              revision: { ...revisionWire(), status: "ready", status_label: "待发布", is_current: false, is_activatable: true },
            };
      return new Response(JSON.stringify(payload), { status: 200 });
    });
    const repository = createEvidenceHttp({ fetchImpl });
    const correction = await repository.createCorrection("ocr-page-1", {
      raw_text_sha256: "a".repeat(64),
      text_start: 0,
      text_end: 2,
      original_text: "原文",
      corrected_text: "校对",
      change_kind: "other_text",
      reason: "我的说明",
      base_processing_revision_id: "revision-1",
      expected_revision: 1,
      idempotency_key: "idem-1",
      target_candidate_id: "candidate-existing",
      expected_candidate_event_seq: 3,
    });
    expect(correction.candidateStatusLabel).toBe("待处理");
    expect(JSON.parse(String(fetchImpl.mock.calls[0]?.[1]?.body))).toMatchObject({
      target_candidate_id: "candidate-existing",
      expected_candidate_event_seq: 3,
    });

    const riskReview = await repository.createRiskReview("ocr-page-1", {
      risk_flag_id: "scan-1:risk-1",
      decision: "confirmed_as_read",
      reason: "已与原始资料核对",
      base_processing_revision_id: "revision-1",
      expected_revision: 1,
      idempotency_key: "idem-2",
      target_candidate_id: "candidate-existing",
      expected_candidate_event_seq: 4,
    });
    expect(riskReview.candidateStatusLabel).toBe("处理中");
    expect(JSON.parse(String(fetchImpl.mock.calls[1]?.[1]?.body))).toMatchObject({
      target_candidate_id: "candidate-existing",
      expected_candidate_event_seq: 4,
    });

    const build = await repository.buildProcessingRevision({
      evidence_snapshot_id: "snapshot-1",
      base_processing_revision_id: "revision-1",
      expected_revision: 1,
      idempotency_key: "idem-3",
      selected_locator_ids: ["locator-1"],
    });
    expect(build).toMatchObject({
      candidateId: "candidate-3",
      jobId: "job-3",
      candidateStatus: "ready",
      revision: { status: "ready" },
    });
    expect(fetchImpl.mock.calls[2]?.[0]).toContain("evidence-processing-revisions/build");

    const candidate = await repository.getProcessingCandidate("candidate-3");
    expect(candidate).toMatchObject({
      candidateId: "candidate-3",
      candidateStatus: "needs_attention",
      candidateEventSeq: 2,
      completeRevisionId: null,
    });
    expect(fetchImpl.mock.calls[3]?.[0]).toContain(
      "evidence-processing-candidates/candidate-3",
    );
  });
});
