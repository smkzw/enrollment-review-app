import { describe, expect, it } from "vitest";
import {
  EvidenceDecodeError,
  type EvidenceConflictContext,
} from "./evidenceViewModels";
import {
  conflictDifferenceRows,
  criticalCorrectionTextChanged,
  decodeBuildRevisionResponse,
  decodeCorrectionResponse,
  decodeOcrPage,
  decodeProcessingRevision,
  decodeReferencedDocument,
  decodeRiskReviewResponse,
  decodeProcessingCandidateStatus,
  isProcessingCandidatePending,
  isReviewableLocator,
} from "./evidenceProcessingViewModels";

describe("校对关键语义兜底", () => {
  it("不依赖用户所选类别识别极性、日期、数值和逻辑变化", () => {
    expect(
      criticalCorrectionTextChanged(
        "",
        "参与者否认2026-03-10使用过研究禁用治疗。",
      ),
    ).toBe(true);
    expect(criticalCorrectionTextChanged("且", "或")).toBe(true);
    expect(criticalCorrectionTextChanged("ALT", "丙氨酸氨基转移酶")).toBe(false);
  });
});

function makePageEntry(overrides: Record<string, unknown> = {}) {
  return {
    entry_id: "entry-1",
    position: 1,
    source_document_version_id: "version-1",
    page_number: 1,
    original_frame: "page-1",
    page_artifact_id: "artifact-1",
    ocr_page_id: "ocr-page-1",
    status: "succeeded",
    status_label: "页面已就绪",
    failure_reason: null,
    image_available: true,
    page_width: 1240,
    page_height: 1754,
    ...overrides,
  };
}

function makeRevision(overrides: Record<string, unknown> = {}) {
  return {
    evidence_processing_revision_id: "processing-revision-1",
    revision_kind: "complete",
    revision_kind_label: "完整处理修订",
    evidence_snapshot_id: "snapshot-1",
    base_processing_revision_id: "base-revision-1",
    project_id: "project-1",
    subject_id: "subject-1",
    review_episode_id: "episode-1",
    status: "active",
    status_label: "当前有效",
    is_activatable: false,
    is_current: true,
    manifest_sha256: "a".repeat(64),
    completion_manifest_sha256: "b".repeat(64),
    pages: [makePageEntry()],
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
    ...overrides,
  };
}

function makeOcrPage(overrides: Record<string, unknown> = {}) {
  return {
    ocr_page_id: "ocr-page-1",
    page_artifact_id: "artifact-1",
    source_document_version_id: "version-1",
    page_number: 1,
    source_sha256: "c".repeat(64),
    raw_text: "患者否认发热，体温 37.5 ℃。",
    raw_text_sha256: "d".repeat(64),
    status: "succeeded",
    status_label: "已识别",
    processing_revision_id: "processing-revision-1",
    is_current_revision: true,
    effective_text: "患者否认发热，体温 37.5 ℃。",
    effective_text_sha256: "e".repeat(64),
    selected_corrections: [],
    risk_scans: [
      {
        scan_id: "scan-1",
        ocr_page_id: "ocr-page-1",
        raw_text_sha256: "d".repeat(64),
        scanner_rule_version: "risk-1",
        flags_sha256: "f".repeat(64),
        coverage_status: "complete",
        created_at: "2026-08-21T00:00:00Z",
        flags: [
          {
            risk_id: "risk-1",
            kind: "negation_polarity",
            kind_label: "否定/肯定",
            level: "blocking",
            level_label: "需核对",
            text: "否认",
            text_start: 2,
            text_end: 4,
            detail: "请确认否定关系。",
            rule_version: "risk-1",
          },
        ],
      },
    ],
    risk_reviews: [],
    locators: [
      {
        locator_id: "locator-1",
        page_artifact_id: "artifact-1",
        ocr_page_id: "ocr-page-1",
        source_document_version_id: "version-1",
        page_number: 1,
        source_layer: "raw_ocr",
        source_layer_label: "原始识别文本",
        source_text_sha256: "d".repeat(64),
        target_id: "risk-1",
        precision: "page_excerpt",
        precision_label: "页内摘录",
        degradation_reason: "未取得原始页图坐标，只保留页内摘录。",
        text_start: 2,
        text_end: 4,
        excerpt: "否认",
        disambiguation: "unique_match",
        locator_algorithm_version: "locator-1",
        authenticity: "degraded",
        match_confidence: 0.92,
        bbox: null,
        coordinate_frame: null,
        coordinate_transform_version: null,
      },
    ],
    ...overrides,
  };
}

describe("isReviewableLocator", () => {
  it("保留可读文字定位并从通用定位清单排除纯标点", () => {
    const baseLocator = (makeOcrPage().locators as Array<Record<string, unknown>>)[0];
    if (baseLocator === undefined) throw new Error("测试定位缺失");
    const [readable, punctuation] = decodeOcrPage(
      makeOcrPage({
        locators: [
          baseLocator,
          {
            ...baseLocator,
            locator_id: "locator-punctuation",
            target_id: "risk-decimal",
            excerpt: ".",
          },
        ],
      }),
    ).locators;

    expect(readable && isReviewableLocator(readable)).toBe(true);
    expect(punctuation && isReviewableLocator(punctuation)).toBe(false);
  });
});

function makeCandidateResult(overrides: Record<string, unknown> = {}) {
  return {
    candidate_id: "candidate-1",
    job_id: "job-1",
    candidate_status: "staged",
    candidate_status_label: "待处理",
    candidate_event_seq: 0,
    complete_revision_id: null,
    ...overrides,
  };
}

function makeCorrection(overrides: Record<string, unknown> = {}) {
  return {
    correction_id: "correction-1",
    ocr_page_id: "ocr-page-1",
    raw_text_sha256: "d".repeat(64),
    text_start: 0,
    text_end: 2,
    original_text: "患者",
    corrected_text: "病人",
    change_kind: "other_text",
    change_kind_label: "文字校对",
    requires_confirmation: false,
    confirmation_actor: null,
    confirmation_at: null,
    reason: "按原始病历校对",
    actor: "本地用户",
    base_processing_revision_id: "processing-revision-1",
    supersedes_correction_id: null,
    affected_scope: [],
    created_at: "2026-08-21T00:00:00Z",
    ...overrides,
  };
}

function makeRiskReview() {
  return {
    review_id: "review-1",
    risk_flag_id: "scan-1:risk-1",
    decision: "confirmed_as_read",
    decision_label: "确认识别无误",
    reason: "已与原始资料核对",
    actor: "本地用户",
    base_processing_revision_id: "processing-revision-1",
    expected_revision: 1,
    created_at: "2026-08-21T00:00:00Z",
  };
}

describe("证据处理领域解码", () => {
  it("风险汇总缺失时拒绝解码，不把合同缺口猜成零风险", () => {
    const revision: Record<string, unknown> = makeRevision();
    delete revision.risk_flag_count;
    expect(() => decodeProcessingRevision(revision)).toThrow(EvidenceDecodeError);
  });

  it("从 pages 清单保留真实页 ID，并把失败页标为不可打开", () => {
    const revision = decodeProcessingRevision(
      makeRevision({
        risk_flag_count: 12,
        pending_risk_flag_count: 7,
        pages: [
          makePageEntry(),
          makePageEntry({
            entry_id: "entry-2",
            position: 2,
            page_number: 2,
            page_artifact_id: "artifact-2",
            ocr_page_id: null,
            status: "failed",
            status_label: "页面处理失败",
            failure_reason: "原始页面无法读取。",
          }),
        ],
      }),
    );
    expect(revision.pages[0]).toMatchObject({ ocrPageId: "ocr-page-1", canOpen: true });
    expect(revision.pages[1]).toMatchObject({ ocrPageId: null, canOpen: false, failureReason: "原始页面无法读取。" });
    expect(revision).toMatchObject({ riskFlagCount: 12, pendingRiskFlagCount: 7 });
  });

  it("拒绝失败页携带可打开识别页 ID，避免前端猜测或伪造链接", () => {
    expect(() =>
      decodeProcessingRevision(
        makeRevision({ pages: [makePageEntry({ status: "failed", failure_reason: "处理失败" })] }),
      ),
    ).toThrow(EvidenceDecodeError);
  });

  it("并列投影原始文本、风险和降级定位原因", () => {
    const page = decodeOcrPage(makeOcrPage());
    expect(page.rawText).toContain("否认");
    expect(page.effectiveText).toContain("37.5");
    expect(page.riskScans[0]?.flags[0]?.riskFlagId).toBe("scan-1:risk-1");
    expect(page.locators[0]).toMatchObject({
      precision: "page_excerpt",
      degradationReason: "未取得原始页图坐标，只保留页内摘录。",
    });
  });

  it("只接受通过真实性核验且落在原始页范围内的区域坐标", () => {
    const wire: any = makeOcrPage();
    wire.locators = [
      {
        ...wire.locators[0],
        precision: "bbox",
        precision_label: "原文区域",
        degradation_reason: null,
        authenticity: "authenticated",
        bbox: { x0: 100, y0: 200, x1: 400, y1: 320 },
        coordinate_frame: {
          space: "page_image_pixels",
          page_width: 1240,
          page_height: 1754,
          rotation: 0,
          transform_version: "transform-1",
        },
        coordinate_transform_version: "transform-1",
      },
    ];
    const page = decodeOcrPage(wire);
    expect(page.locators[0]).toMatchObject({
      precision: "bbox",
      authenticity: "authenticated",
      bbox: { x0: 100, y0: 200, x1: 400, y1: 320 },
    });

    wire.locators[0]!.bbox = { x0: 100, y0: 200, x1: 1400, y1: 320 };
    expect(() => decodeOcrPage(wire)).toThrow("区域定位超出原始资料页范围");
  });

  it("拒绝降级定位夹带区域坐标，避免前端绘制推测红框", () => {
    const wire: any = makeOcrPage();
    wire.locators[0]!.bbox = { x0: 100, y0: 200, x1: 400, y1: 320 };
    wire.locators[0]!.coordinate_frame = {
      space: "page_image_pixels",
      page_width: 1240,
      page_height: 1754,
      rotation: 0,
      transform_version: "transform-1",
    };
    expect(() => decodeOcrPage(wire)).toThrow("降级定位不得携带区域坐标");
  });

  it("被提及资料解码保留确认状态与当前满足修订", () => {
    const item = decodeReferencedDocument({
      revision_id: "ref-revision-1",
      referenced_document_id: "ref-1",
      project_id: "project-1",
      subject_id: "subject-1",
      review_episode_id: "episode-1",
      description: "既往影像报告",
      document_type: "影像",
      source_party: "外院",
      origin: "manual",
      origin_label: "手工登记",
      pattern_version: null,
      status: "confirmed",
      status_label: "已确认",
      user_reviewed: true,
      reason: "已与研究中心确认",
      revision: 2,
      supersedes_revision_id: "ref-revision-0",
      trigger_locator_id: "locator-1",
      resolution: {
        resolution_revision_id: "resolution-1",
        status: "provided",
        status_label: "已提供",
        source_document_version_id: "version-1",
        revision: 1,
        created_by: "本地用户",
        created_at: "2026-08-21T00:00:00Z",
      },
      created_at: "2026-08-21T00:00:00Z",
      created_by: "本地用户",
    });
    expect(item.statusLabel).toBe("已确认");
    expect(item.resolution?.sourceDocumentVersionId).toBe("version-1");
  });

  it("把 409 的字段差异解码为自然中文行", () => {
    const context: EvidenceConflictContext = {
      submitted: { description: "本次输入" },
      currentRecord: { description: "服务端当前" },
      fieldDiff: {
        description: { submitted: "本次输入", current: "服务端当前" },
      },
    };
    expect(conflictDifferenceRows(context)).toEqual([
      { field: "资料说明", submitted: "本次输入", current: "服务端当前" },
    ]);
  });

  it("解码校对、风险核对和显式生成的异步返回，并保留中文状态", () => {
    const correction = decodeCorrectionResponse({
      ...makeCandidateResult(),
      correction: makeCorrection(),
      created: true,
    });
    expect(correction).toMatchObject({
      candidateId: "candidate-1",
      jobId: "job-1",
      candidateStatus: "staged",
      candidateStatusLabel: "待处理",
      created: true,
    });

    const riskReview = decodeRiskReviewResponse({
      ...makeCandidateResult({ candidate_status: "processing", candidate_status_label: "处理中" }),
      review: makeRiskReview(),
      created: true,
    });
    expect(riskReview.candidateStatusLabel).toBe("处理中");

    const build = decodeBuildRevisionResponse({
      ...makeCandidateResult({ candidate_status: "ready", candidate_status_label: "待发布" }),
      created: true,
      revision: makeRevision({ status: "ready", status_label: "待发布", is_current: false, is_activatable: true }),
    });
    expect(build.revision?.status).toBe("ready");
    expect(build.candidateStatusLabel).toBe("待发布");
    expect(isProcessingCandidatePending(correction.candidateStatus)).toBe(true);
    expect(isProcessingCandidatePending(build.candidateStatus)).toBe(false);

    expect(
      decodeProcessingCandidateStatus({
        ...makeCandidateResult({
          candidate_status: "needs_attention",
          candidate_status_label: "需要关注",
        }),
        candidate_event_seq: 2,
        complete_revision_id: null,
      }),
    ).toMatchObject({
      candidateStatus: "needs_attention",
      candidateEventSeq: 2,
      completeRevisionId: null,
    });
  });

  it("解码来源锚定的零长度插入，并拒绝范围与空原文不一致", () => {
    const insertion = makeCorrection({
      text_start: 15,
      text_end: 15,
      original_text: "",
      corrected_text: "复查日期 2026-08-21。",
      change_kind: "date",
      change_kind_label: "日期",
      requires_confirmation: true,
      confirmation_actor: "复核人",
      confirmation_at: "2026-08-21T00:00:00Z",
    });
    const response = decodeCorrectionResponse({
      ...makeCandidateResult(),
      correction: insertion,
      created: true,
    });
    expect(response.correction).toMatchObject({
      textStart: 15,
      textEnd: 15,
      originalText: "",
      correctedText: "复查日期 2026-08-21。",
    });

    const rawText = "患者否认发热，体温 37.5 ℃。";
    const page = decodeOcrPage(
      makeOcrPage({
        raw_text: rawText,
        selected_corrections: [
          makeCorrection({
            text_start: rawText.length,
            text_end: rawText.length,
            original_text: "",
            corrected_text: "复查日期 2026-08-21。",
          }),
        ],
      }),
    );
    expect(page.selectedCorrections[0]?.originalText).toBe("");

    expect(() =>
      decodeCorrectionResponse({
        ...makeCandidateResult(),
        correction: makeCorrection({
          text_start: 2,
          text_end: 2,
          original_text: "否认",
        }),
        created: true,
      }),
    ).toThrow(EvidenceDecodeError);
    expect(() =>
      decodeCorrectionResponse({
        ...makeCandidateResult(),
        correction: makeCorrection({
          text_start: 2,
          text_end: 4,
          original_text: "",
        }),
        created: true,
      }),
    ).toThrow(EvidenceDecodeError);
  });
});
