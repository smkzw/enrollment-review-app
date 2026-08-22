// @vitest-environment jsdom
/**
 * 证据工作台组件测试（任务 worker_03）：
 * 深链上下文、上传方式中文说明、确认前复核分类、同名冲突处置门禁、
 * 取消不建快照、确认提交正确对象。
 */

import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  EvidenceApiError,
  decodeCommitResponse,
  decodeCorrectionResponse,
  decodeOcrPage,
  decodeProcessingRevision,
  decodeProcessingCandidateStatus,
  decodeSnapshotList,
  decodeUploadPreview,
  setEvidenceRepository,
  type EvidenceRepository,
} from "../api/evidence";
import { canSupplementEvidence, EvidencePage } from "./EvidencePage";

const SUBJECT_ID = "subject-uat-01-clear";
const EPISODE_ID = "episode-uat-01-screening-clear";
const PREVIEW_ID = "preview-abc";
const PREVIEW_SHA = "a".repeat(64);

const ITEMS = [
  {
    item_id: "item-1",
    file_name: "检查报告.pdf",
    byte_size: 2048,
    media_type: "application/pdf",
    status: "added",
    status_label: "新增资料",
    processing_hint: "process_new",
    processing_hint_label: "需要处理",
    reason: "该文件为本次新增资料。",
    next_action: "将首次处理该文件，请确认后提交。",
    logical_document_id: "logical-1",
    existing_version_id: null,
    error_detail: null,
  },
  {
    item_id: "item-2",
    file_name: "知情同意书.pdf",
    byte_size: 1024,
    media_type: "application/pdf",
    status: "duplicate",
    status_label: "内容重复",
    processing_hint: "reuse_existing",
    processing_hint_label: "复用已有处理结果",
    reason: "该文件内容与上一有效快照中已存在的资料完全相同。",
    next_action: "系统将复用已有处理结果，不会重复保存或重复识别。",
    logical_document_id: "logical-2",
    existing_version_id: null,
    error_detail: null,
  },
  {
    item_id: "item-3",
    file_name: "入院记录.docx",
    byte_size: 4096,
    media_type:
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    status: "conflict",
    status_label: "名称相同但内容不同",
    processing_hint: "require_resolution",
    processing_hint_label: "需要选择处置方式",
    reason: "存在同名文件但内容不同，系统不会自动覆盖。",
    next_action: "请选择“作为原资料的新版本”或“作为另一份资料并列保留”。",
    logical_document_id: "logical-3",
    existing_version_id: "version-3",
    error_detail: null,
  },
  {
    item_id: "item-4",
    file_name: "出院小结.zip",
    byte_size: 8192,
    media_type: "application/zip",
    status: "unsupported",
    status_label: "格式不支持",
    processing_hint: "rejected",
    processing_hint_label: "不纳入处理",
    reason: "该文件格式当前不受支持。",
    next_action: "请解压或转换为受支持的格式后重新选择。",
    logical_document_id: null,
    existing_version_id: null,
    error_detail: null,
  },
];

function makePreviewWire(overrides: Record<string, unknown> = {}) {
  return {
    preview_id: PREVIEW_ID,
    project_id: "project-synthetic-phase-iii",
    subject_id: SUBJECT_ID,
    review_episode_id: EPISODE_ID,
    upload_mode: "incremental",
    upload_mode_label: "补充资料",
    base_revision: 1,
    base_snapshot_id: "snap-0",
    status: "staged",
    status_label: "等待确认",
    items: ITEMS,
    matching_snapshot_id: null,
    matching_snapshot_status: null,
    matching_snapshot_status_label: null,
    preview_sha256: PREVIEW_SHA,
    created_at: "2026-08-19T08:00:00Z",
    created_by: "本地用户",
    ...overrides,
  };
}

function makeCommitWire(overrides: Record<string, unknown> = {}) {
  return {
    commit_id: "commit-1",
    preview_id: PREVIEW_ID,
    evidence_snapshot_id: "snap-1",
    project_id: "project-synthetic-phase-iii",
    subject_id: SUBJECT_ID,
    review_episode_id: EPISODE_ID,
    upload_mode: "incremental",
    upload_mode_label: "补充资料",
    idempotency_key: "idem-1",
    job_id: "job-1",
    created: true,
    replayed: false,
    duplicate: false,
    resolutions: [
      {
        item_id: "item-3",
        logical_document_id: "logical-3",
        resolution: "new_version",
        resolution_label: "作为原资料的新版本",
        source_document_version_id: "version-4",
        supersedes_version_id: "version-3",
      },
    ],
    snapshot: {
      evidence_snapshot_id: "snap-1",
      project_id: "project-synthetic-phase-iii",
      subject_id: SUBJECT_ID,
      review_episode_id: EPISODE_ID,
      upload_mode: "incremental",
      upload_mode_label: "补充资料",
      prior_snapshot_id: "snap-0",
      comparison_snapshot_id: null,
      status: "staged",
      status_label: "待处理",
      is_current: false,
      base_processing_revision_id: null,
      upload_job_id: "job-1",
      members: [
        {
          member_id: "member-1",
          snapshot_id: "snap-1",
          logical_document_id: "logical-1",
          source_document_version_id: "version-1",
          file_name: "检查报告.pdf",
          media_type: "application/pdf",
          version_number: 1,
          origin: "added",
          origin_label: "本次新增",
          metadata_head: {
            metadata_revision_id: "metadata-commit-1",
            source_document_version_id: "version-1",
            document_type: "检查报告",
            source_party: "研究中心",
            reason: "系统根据文件名提出建议。",
            is_auto_suggestion: true,
            supersedes_metadata_revision_id: null,
            revision: 1,
            created_at: "2026-08-19T08:00:00Z",
            created_by: "本地用户",
          },
        },
      ],
      collection_sha256: "c".repeat(64),
      created_at: "2026-08-19T08:00:00Z",
      created_by: "本地用户",
    },
    created_at: "2026-08-19T08:00:00Z",
    created_by: "本地用户",
    ...overrides,
  };
}

function makeSnapshotWire(
  snapshotId: string,
  status: string,
): Record<string, unknown> {
  return {
    evidence_snapshot_id: snapshotId,
    project_id: "project-synthetic-phase-iii",
    subject_id: SUBJECT_ID,
    review_episode_id: EPISODE_ID,
    upload_mode: "full",
    upload_mode_label: "建立完整资料快照",
    prior_snapshot_id: null,
    comparison_snapshot_id: null,
    status,
    status_label: status === "active" ? "当前有效" : "待处理",
    is_current: status === "active",
    base_processing_revision_id: status === "active" ? "base-revision-1" : null,
    upload_job_id: status === "active" ? null : "upload-job-1",
    members:
      status === "active"
        ? [
            {
              member_id: "member-active-1",
              snapshot_id: snapshotId,
              logical_document_id: "logical-1",
              source_document_version_id: "version-1",
              file_name: "筛选病历.pdf",
              media_type: "application/pdf",
              version_number: 1,
              origin: "added",
              origin_label: "本次新增",
              metadata_head: {
                metadata_revision_id: "metadata-active-1",
                source_document_version_id: "version-1",
                document_type: "筛选病历",
                source_party: "研究中心",
                reason: "系统根据文件名提出建议。",
                is_auto_suggestion: true,
                supersedes_metadata_revision_id: null,
                revision: 1,
                created_at: "2026-08-19T08:00:00Z",
                created_by: "本地用户",
              },
            },
          ]
        : [],
    collection_sha256: "b".repeat(64),
    created_at: "2026-08-19T08:00:00Z",
    created_by: "本地用户",
  };
}

function withLatestCandidate(
  snapshot: Record<string, unknown>,
  status: "staged" | "processing" | "needs_attention" | "ready",
  eventSeq: number,
): Record<string, unknown> {
  return {
    ...snapshot,
    latest_processing_candidate: {
      candidate_id: "candidate-1",
      job_id: "job-1",
      candidate_status: status,
      candidate_status_label:
        status === "needs_attention"
          ? "需要核对"
          : status === "ready"
            ? "待启用"
            : "正在处理",
      candidate_event_seq: eventSeq,
      complete_revision_id: status === "ready" ? "revision-1" : null,
    },
  };
}

function makeProcessingRevisionWire() {
  return {
    evidence_processing_revision_id: "processing-revision-1",
    revision_kind: "complete",
    revision_kind_label: "完整处理修订",
    evidence_snapshot_id: "snap-active",
    base_processing_revision_id: "base-revision-1",
    project_id: "project-synthetic-phase-iii",
    subject_id: SUBJECT_ID,
    review_episode_id: EPISODE_ID,
    status: "active",
    status_label: "当前有效",
    is_activatable: false,
    is_current: true,
    manifest_sha256: "a".repeat(64),
    completion_manifest_sha256: "b".repeat(64),
    pages: [
      {
        entry_id: "entry-1",
        position: 1,
        source_document_version_id: "version-1",
        page_number: 1,
        original_frame: "frame-1",
        page_artifact_id: "artifact-1",
        ocr_page_id: "ocr-page-1",
        status: "succeeded",
        status_label: "页面已就绪",
        failure_reason: null,
        image_available: true,
        page_width: 1240,
        page_height: 1754,
      },
      {
        entry_id: "entry-2",
        position: 2,
        source_document_version_id: "version-1",
        page_number: 2,
        original_frame: null,
        page_artifact_id: "artifact-2",
        ocr_page_id: null,
        status: "failed",
        status_label: "页面处理失败",
        failure_reason: "原始页面读取失败。",
        image_available: false,
        page_width: null,
        page_height: null,
      },
    ],
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

function makeOcrPageWire() {
  return {
    ocr_page_id: "ocr-page-1",
    page_artifact_id: "artifact-1",
    source_document_version_id: "version-1",
    page_number: 1,
    source_sha256: "c".repeat(64),
    raw_text: "患者否认发热。",
    raw_text_sha256: "d".repeat(64),
    status: "succeeded",
    status_label: "已识别",
    processing_revision_id: "processing-revision-1",
    is_current_revision: true,
    effective_text: "患者否认发热。",
    effective_text_sha256: "e".repeat(64),
    selected_corrections: [],
    risk_scans: [],
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
        target_id: "target-1",
        precision: "page_excerpt",
        precision_label: "页内摘录",
        degradation_reason: "未取得原始页图坐标，只保留页内摘录。",
        text_start: 0,
        text_end: 4,
        excerpt: "患者否认",
        disambiguation: "unique_match",
        locator_algorithm_version: "locator-1",
        authenticity: "degraded",
        match_confidence: 0.9,
        bbox: null,
        coordinate_frame: null,
        coordinate_transform_version: null,
      },
    ],
  };
}

function makeCorrectionResponseWire() {
  return {
    correction: {
      correction_id: "correction-1",
      ocr_page_id: "ocr-page-1",
      raw_text_sha256: "d".repeat(64),
      text_start: 0,
      text_end: "患者否认发热。".length,
      original_text: "患者否认发热。",
      corrected_text: "患者确认发热。",
      change_kind: "other_text",
      change_kind_label: "文字校对",
      requires_confirmation: false,
      confirmation_actor: null,
      confirmation_at: null,
      reason: "按原始病历校对",
      actor: "本地用户",
      base_processing_revision_id: "base-revision-1",
      supersedes_correction_id: null,
      affected_scope: [],
      created_at: "2026-08-21T00:00:00Z",
    },
    created: true,
    candidate_id: "candidate-1",
    job_id: "job-1",
    candidate_status: "staged",
    candidate_status_label: "待处理",
    candidate_event_seq: 0,
    complete_revision_id: null,
  };
}

const EPISODE = EPISODE_ID;

let fns: {
  createUploadPreview: ReturnType<
    typeof vi.fn<EvidenceRepository["createUploadPreview"]>
  >;
  cancelUploadPreview: ReturnType<
    typeof vi.fn<EvidenceRepository["cancelUploadPreview"]>
  >;
  confirmUpload: ReturnType<typeof vi.fn<EvidenceRepository["confirmUpload"]>>;
  listEvidenceSnapshots: ReturnType<
    typeof vi.fn<EvidenceRepository["listEvidenceSnapshots"]>
  >;
  getUploadPreview: ReturnType<
    typeof vi.fn<EvidenceRepository["getUploadPreview"]>
  >;
  getEvidenceSnapshot: ReturnType<
    typeof vi.fn<EvidenceRepository["getEvidenceSnapshot"]>
  >;
  getProcessingRevision: ReturnType<
    typeof vi.fn<EvidenceRepository["getProcessingRevision"]>
  >;
  getProcessingCandidate: ReturnType<
    typeof vi.fn<EvidenceRepository["getProcessingCandidate"]>
  >;
  getOcrPage: ReturnType<typeof vi.fn<EvidenceRepository["getOcrPage"]>>;
  createCorrection: ReturnType<
    typeof vi.fn<EvidenceRepository["createCorrection"]>
  >;
  createRiskReview: ReturnType<
    typeof vi.fn<EvidenceRepository["createRiskReview"]>
  >;
  createRiskPageReview: ReturnType<
    typeof vi.fn<EvidenceRepository["createRiskPageReview"]>
  >;
  buildProcessingRevision: ReturnType<
    typeof vi.fn<EvidenceRepository["buildProcessingRevision"]>
  >;
  activateProcessingRevision: ReturnType<
    typeof vi.fn<EvidenceRepository["activateProcessingRevision"]>
  >;
  reviseSourceDocumentMetadata: ReturnType<
    typeof vi.fn<EvidenceRepository["reviseSourceDocumentMetadata"]>
  >;
  listReferencedDocuments: ReturnType<
    typeof vi.fn<EvidenceRepository["listReferencedDocuments"]>
  >;
  createReferencedDocument: ReturnType<
    typeof vi.fn<EvidenceRepository["createReferencedDocument"]>
  >;
  reviseReferencedDocument: ReturnType<
    typeof vi.fn<EvidenceRepository["reviseReferencedDocument"]>
  >;
  confirmReferencedDocument: ReturnType<
    typeof vi.fn<EvidenceRepository["confirmReferencedDocument"]>
  >;
  dismissReferencedDocument: ReturnType<
    typeof vi.fn<EvidenceRepository["dismissReferencedDocument"]>
  >;
  resolveReferencedDocument: ReturnType<
    typeof vi.fn<EvidenceRepository["resolveReferencedDocument"]>
  >;
  unresolveReferencedDocument: ReturnType<
    typeof vi.fn<EvidenceRepository["unresolveReferencedDocument"]>
  >;
};

beforeEach(() => {
  fns = {
    createUploadPreview: vi.fn<EvidenceRepository["createUploadPreview"]>(() =>
      Promise.resolve(decodeUploadPreview(makePreviewWire())),
    ),
    cancelUploadPreview: vi.fn<EvidenceRepository["cancelUploadPreview"]>(() =>
      Promise.resolve(
        decodeUploadPreview(
          makePreviewWire({ status: "cancelled", status_label: "已取消" }),
        ),
      ),
    ),
    confirmUpload: vi.fn<EvidenceRepository["confirmUpload"]>(() =>
      Promise.resolve(decodeCommitResponse(makeCommitWire())),
    ),
    listEvidenceSnapshots: vi.fn<EvidenceRepository["listEvidenceSnapshots"]>(
      () =>
        Promise.resolve(
          decodeSnapshotList({
            subject_id: SUBJECT_ID,
            review_episode_id: EPISODE_ID,
            active_evidence_snapshot_id: null,
            active_evidence_processing_revision_id: null,
            items: [],
          }),
        ),
    ),
    getUploadPreview: vi.fn<EvidenceRepository["getUploadPreview"]>(),
    getEvidenceSnapshot: vi.fn<EvidenceRepository["getEvidenceSnapshot"]>(),
    getProcessingRevision: vi.fn<EvidenceRepository["getProcessingRevision"]>(),
    getProcessingCandidate:
      vi.fn<EvidenceRepository["getProcessingCandidate"]>(),
    getOcrPage: vi.fn<EvidenceRepository["getOcrPage"]>(),
    createCorrection: vi.fn<EvidenceRepository["createCorrection"]>(),
    createRiskReview: vi.fn<EvidenceRepository["createRiskReview"]>(),
    createRiskPageReview: vi.fn<EvidenceRepository["createRiskPageReview"]>(),
    buildProcessingRevision:
      vi.fn<EvidenceRepository["buildProcessingRevision"]>(),
    activateProcessingRevision:
      vi.fn<EvidenceRepository["activateProcessingRevision"]>(),
    reviseSourceDocumentMetadata:
      vi.fn<EvidenceRepository["reviseSourceDocumentMetadata"]>(),
    listReferencedDocuments: vi.fn<
      EvidenceRepository["listReferencedDocuments"]
    >(() =>
      Promise.resolve({
        subjectId: SUBJECT_ID,
        reviewEpisodeId: EPISODE_ID,
        items: [],
      }),
    ),
    createReferencedDocument:
      vi.fn<EvidenceRepository["createReferencedDocument"]>(),
    reviseReferencedDocument:
      vi.fn<EvidenceRepository["reviseReferencedDocument"]>(),
    confirmReferencedDocument:
      vi.fn<EvidenceRepository["confirmReferencedDocument"]>(),
    dismissReferencedDocument:
      vi.fn<EvidenceRepository["dismissReferencedDocument"]>(),
    resolveReferencedDocument:
      vi.fn<EvidenceRepository["resolveReferencedDocument"]>(),
    unresolveReferencedDocument:
      vi.fn<EvidenceRepository["unresolveReferencedDocument"]>(),
  };
  const repo: EvidenceRepository = {
    kind: "http",
    createUploadPreview: fns.createUploadPreview,
    getUploadPreview: fns.getUploadPreview,
    cancelUploadPreview: fns.cancelUploadPreview,
    confirmUpload: fns.confirmUpload,
    listEvidenceSnapshots: fns.listEvidenceSnapshots,
    getEvidenceSnapshot: fns.getEvidenceSnapshot,
    getProcessingRevision: fns.getProcessingRevision,
    getProcessingCandidate: fns.getProcessingCandidate,
    getOcrPage: fns.getOcrPage,
    createCorrection: fns.createCorrection,
    createRiskReview: fns.createRiskReview,
    createRiskPageReview: fns.createRiskPageReview,
    buildProcessingRevision: fns.buildProcessingRevision,
    activateProcessingRevision: fns.activateProcessingRevision,
    reviseSourceDocumentMetadata: fns.reviseSourceDocumentMetadata,
    listReferencedDocuments: fns.listReferencedDocuments,
    createReferencedDocument: fns.createReferencedDocument,
    reviseReferencedDocument: fns.reviseReferencedDocument,
    confirmReferencedDocument: fns.confirmReferencedDocument,
    dismissReferencedDocument: fns.dismissReferencedDocument,
    resolveReferencedDocument: fns.resolveReferencedDocument,
    unresolveReferencedDocument: fns.unresolveReferencedDocument,
  };
  setEvidenceRepository(repo);
  window.localStorage.clear();
  window.location.hash = "";
});

async function openValid(user: ReturnType<typeof userEvent.setup>) {
  window.location.hash = `#/subjects/${SUBJECT_ID}/evidence?episode=${EPISODE}`;
  render(<EvidencePage />);
  await screen.findByText(/界面试用项目 · Ⅲ期/);
  return user;
}

function useActiveSnapshotForSupplementTests() {
  fns.listEvidenceSnapshots.mockResolvedValue(
    decodeSnapshotList({
      subject_id: SUBJECT_ID,
      review_episode_id: EPISODE_ID,
      active_evidence_snapshot_id: "snap-active",
      active_evidence_processing_revision_id: null,
      items: [makeSnapshotWire("snap-active", "active")],
    }),
  );
}

async function openActiveUpload(user: ReturnType<typeof userEvent.setup>) {
  useActiveSnapshotForSupplementTests();
  await openValid(user);
  await user.click(
    await screen.findByRole("button", { name: "补充或重建资料" }),
  );
}

async function expandCurrentCorrectionTools(
  user: ReturnType<typeof userEvent.setup>,
) {
  await user.click(
    await screen.findByRole("button", { name: "需要修订识别文字" }),
  );
}

async function confirmCriticalCorrectionWhenShown(
  user: ReturnType<typeof userEvent.setup>,
): Promise<void> {
  const confirmation = screen.queryByRole("checkbox", {
    name: /逐字核对这项关键变化/,
  });
  if (confirmation !== null && !confirmation.hasAttribute("checked")) {
    await user.click(confirmation);
  }
}

describe("证据工作台", () => {
  it("深链显示固定上下文带：项目、受试者、审核节点、方案版本", async () => {
    const user = userEvent.setup();
    await openValid(user);
    const band = screen.getByLabelText("当前资料上下文");
    expect(band).toHaveTextContent("界面试用项目 · Ⅲ期");
    expect(band).toHaveTextContent("UAT-01");
    expect(band).toHaveTextContent("筛选期");
    expect(band).toHaveTextContent("V1.0");
    // 无任何快照时不冒充为已建立但尚未启用。
    await waitFor(() => {
      expect(band).toHaveTextContent("尚未建立资料版本");
    });
    expect(band).not.toHaveTextContent("第 1 版");
  });

  it("正式模式只在存在当前有效资料时允许补充资料", () => {
    expect(canSupplementEvidence(null)).toBe(false);
    expect(canSupplementEvidence("snap-active")).toBe(true);
  });

  it("当前资料版本只由活动指针确定，历史 active 不再标成当前", async () => {
    const user = userEvent.setup();
    const historical = {
      ...makeSnapshotWire("snap-history", "active"),
      is_current: false,
      status_label: "当前有效",
      base_processing_revision_id: "base-history",
      created_at: "2026-08-18T08:00:00Z",
    };
    fns.listEvidenceSnapshots.mockImplementation(() =>
      Promise.resolve(
        decodeSnapshotList({
          subject_id: SUBJECT_ID,
          review_episode_id: EPISODE_ID,
          active_evidence_snapshot_id: "snap-active",
          active_evidence_processing_revision_id: null,
          items: [
            historical,
            makeSnapshotWire("snap-staged", "staged"),
            makeSnapshotWire("snap-active", "active"),
          ],
        }),
      ),
    );
    await openValid(user);
    await waitFor(() => {
      expect(screen.getByLabelText("当前资料上下文")).toHaveTextContent(
        "当前有效",
      );
    });
    expect(
      screen.getByText("历史资料", { selector: ".chip" }),
    ).toBeInTheDocument();
    expect(screen.getAllByText("当前有效", { selector: ".chip" })).toHaveLength(
      1,
    );
  });

  it("快照加载时只显示中性读取状态，不瞬时误报无有效版本", async () => {
    const user = userEvent.setup();
    let resolveSnapshots!: (
      value: ReturnType<typeof decodeSnapshotList>,
    ) => void;
    fns.listEvidenceSnapshots.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveSnapshots = resolve;
        }),
    );

    await openValid(user);

    expect(screen.getByText("正在读取当前资料版本…")).toBeInTheDocument();
    expect(screen.queryByText(/尚无有效资料版本/)).toBeNull();
    expect(screen.queryByRole("radio", { name: "补充资料" })).toBeNull();

    await act(async () => {
      resolveSnapshots(
        decodeSnapshotList({
          subject_id: SUBJECT_ID,
          review_episode_id: EPISODE_ID,
          active_evidence_snapshot_id: null,
          active_evidence_processing_revision_id: null,
          items: [],
        }),
      );
    });
    expect(
      await screen.findByRole("radio", { name: "建立完整资料快照" }),
    ).toBeInTheDocument();
  });

  it("有当前有效资料时上传区默认收起，可明确展开两种方式", async () => {
    const user = userEvent.setup();
    useActiveSnapshotForSupplementTests();

    await openValid(user);

    expect(
      await screen.findByText("当前有效资料可在下方查看。"),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.getByText("当前资料", { selector: ".chip" }),
      ).toBeInTheDocument(),
    );
    expect(screen.queryByText("本次新增", { selector: ".chip" })).toBeNull();
    expect(screen.queryByRole("radio", { name: "补充资料" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "补充或重建资料" }));
    expect(screen.getByRole("radio", { name: "补充资料" })).toBeInTheDocument();
    expect(
      screen.getByRole("radio", { name: "建立完整资料快照" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("radio", { name: "补充资料" }));
    await user.click(screen.getByRole("button", { name: "暂不补充" }));
    expect(
      await screen.findByText("当前有效资料可在下方查看。"),
    ).toBeInTheDocument();
    expect(screen.queryByRole("radio", { name: "补充资料" })).toBeNull();
  });

  it("从活动处理修订 pages 发现真实页，只为非空 ocr_page_id 请求详情", async () => {
    const user = userEvent.setup();
    fns.listEvidenceSnapshots.mockImplementation(() =>
      Promise.resolve(
        decodeSnapshotList({
          subject_id: SUBJECT_ID,
          review_episode_id: EPISODE_ID,
          active_evidence_snapshot_id: "snap-active",
          active_evidence_processing_revision_id: "processing-revision-1",
          items: [makeSnapshotWire("snap-active", "active")],
        }),
      ),
    );
    fns.getProcessingRevision.mockResolvedValue(
      decodeProcessingRevision(makeProcessingRevisionWire()),
    );
    fns.getOcrPage.mockResolvedValue(decodeOcrPage(makeOcrPageWire()));
    await openValid(user);
    expect(await screen.findByText("原始识别")).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: "校对后文本" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "查看 1 处原件定位" }));
    expect(
      await screen.findByText(/未取得原始页图坐标，只保留页内摘录/),
    ).toBeInTheDocument();
    expect((await screen.findAllByText("原始页面读取失败。")).length).toBe(2);
    expect((await screen.findAllByText("筛选病历.pdf")).length).toBe(5);
    expect(
      within(screen.getByLabelText("识别页清单")).getByRole("button", {
        name: /第 2 页/,
      }),
    ).toBeEnabled();
    expect(fns.getProcessingRevision).toHaveBeenCalledWith(
      "processing-revision-1",
    );
    expect(fns.getOcrPage).toHaveBeenCalledTimes(1);
    expect(fns.getOcrPage).toHaveBeenCalledWith(
      "ocr-page-1",
      "processing-revision-1",
      expect.anything(),
    );
    expect(fns.getOcrPage).not.toHaveBeenCalledWith(
      "entry-2",
      expect.anything(),
      expect.anything(),
    );
  });

  it("待启用快照与基础处理版本严格配对时允许先核对原文", async () => {
    const user = userEvent.setup();
    const activeShape = makeSnapshotWire("snap-active", "active");
    fns.listEvidenceSnapshots.mockResolvedValue(
      decodeSnapshotList({
        subject_id: SUBJECT_ID,
        review_episode_id: EPISODE_ID,
        active_evidence_snapshot_id: null,
        active_evidence_processing_revision_id: null,
        items: [
          {
            ...makeSnapshotWire("snap-pending", "staged"),
            base_processing_revision_id: "processing-revision-1",
            members: activeShape.members,
          },
        ],
      }),
    );
    fns.getProcessingRevision.mockResolvedValue(
      decodeProcessingRevision({
        ...makeProcessingRevisionWire(),
        evidence_snapshot_id: "snap-pending",
        revision_kind: "base",
        revision_kind_label: "基础处理修订",
        status: "ready",
        status_label: "待发布",
        is_current: false,
      }),
    );
    fns.getOcrPage.mockResolvedValue(decodeOcrPage(makeOcrPageWire()));
    const buildResult = {
      candidateId: "candidate-pending",
      jobId: "job-pending",
      candidateStatus: "staged",
      candidateStatusLabel: "等待处理",
      candidateEventSeq: null,
      completeRevisionId: null,
      created: true,
      revision: null,
    } as const;
    let resolveBuild!: (value: typeof buildResult) => void;
    fns.buildProcessingRevision.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveBuild = resolve;
        }),
    );

    await openValid(user);

    expect(await screen.findByText("原始识别")).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: "校对后文本" }),
    ).toBeInTheDocument();
    expect(fns.getOcrPage).toHaveBeenCalledWith(
      "ocr-page-1",
      "processing-revision-1",
      expect.anything(),
    );
    expect(screen.getByLabelText("当前资料上下文")).toHaveTextContent(
      "尚未启用",
    );
    expect(screen.getByText("待识别核对")).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", {
        name: "检查核对结果并生成资料版本",
      }),
    );
    await waitFor(() =>
      expect(fns.buildProcessingRevision).toHaveBeenCalledTimes(1),
    );
    expect(screen.getByRole("textbox", { name: "校对后文本" })).toBeDisabled();
    resolveBuild(buildResult);
    const buildRequest = fns.buildProcessingRevision.mock.calls[0]?.[0];
    expect(buildRequest).toEqual(
      expect.objectContaining({
        evidence_snapshot_id: "snap-pending",
        base_processing_revision_id: "processing-revision-1",
      }),
    );
    expect(buildRequest).not.toHaveProperty("scanner_rule_version");
  });

  it("活动指针与处理版本不成对时停止核对，不开放任何页", async () => {
    const user = userEvent.setup();
    fns.listEvidenceSnapshots.mockResolvedValue(
      decodeSnapshotList({
        subject_id: SUBJECT_ID,
        review_episode_id: EPISODE_ID,
        active_evidence_snapshot_id: "snap-active",
        active_evidence_processing_revision_id: "processing-revision-1",
        items: [makeSnapshotWire("snap-active", "active")],
      }),
    );
    fns.getProcessingRevision.mockResolvedValue(
      decodeProcessingRevision({
        ...makeProcessingRevisionWire(),
        evidence_snapshot_id: "another-snapshot",
        is_current: false,
      }),
    );
    await openValid(user);
    expect(
      await screen.findByText(/当前资料版本与处理版本不一致/),
    ).toBeInTheDocument();
    expect(fns.getOcrPage).not.toHaveBeenCalled();
  });

  it("OCR 校对冲突只在 OCR 区显示并保留输入，不污染被提及资料区", async () => {
    const user = userEvent.setup();
    fns.listEvidenceSnapshots.mockResolvedValue(
      decodeSnapshotList({
        subject_id: SUBJECT_ID,
        review_episode_id: EPISODE_ID,
        active_evidence_snapshot_id: "snap-active",
        active_evidence_processing_revision_id: "processing-revision-1",
        items: [makeSnapshotWire("snap-active", "active")],
      }),
    );
    fns.getProcessingRevision.mockResolvedValue(
      decodeProcessingRevision(makeProcessingRevisionWire()),
    );
    fns.getOcrPage.mockResolvedValue(decodeOcrPage(makeOcrPageWire()));
    const conflict = new EvidenceApiError(
      "STALE_REVISION",
      "资料已发生变化",
      "系统已有更新，请核对差异。",
      "请确认当前值后再决定是否提交。",
      409,
      {
        submitted: { corrected_text: "患者确认发热。" },
        currentRecord: { corrected_text: "患者否认发热。" },
        fieldDiff: {
          corrected_text: {
            submitted: "患者确认发热。",
            current: "患者否认发热。",
          },
        },
      },
    );
    fns.createCorrection.mockRejectedValue(conflict);
    await openValid(user);
    await expandCurrentCorrectionTools(user);
    const corrected = await screen.findByRole("textbox", {
      name: "校对后文本",
    });
    await user.type(corrected, "患者确认发热。");
    await user.type(
      screen.getByRole("textbox", { name: "校对说明" }),
      "按原始病历校对",
    );
    expect(screen.getByRole("combobox", { name: "变化类别" })).toHaveValue(
      "other_text",
    );
    await user.selectOptions(
      screen.getByRole("combobox", { name: "变化类别" }),
      "polarity",
    );
    expect(screen.getByRole("combobox", { name: "变化类别" })).toHaveValue(
      "polarity",
    );
    expect(
      screen.getByText("请逐字核对并确认这项关键语义变化。"),
    ).toBeInTheDocument();
    await confirmCriticalCorrectionWhenShown(user);
    await user.click(screen.getByRole("button", { name: "提交校对" }));

    expect(
      await screen.findByRole("alert", { name: "资料已发生变化" }),
    ).toBeInTheDocument();
    expect(corrected).toHaveValue("患者确认发热。");
    const referencedRegion = screen.getByRole("region", {
      name: "资料中提及但未提供",
    });
    expect(within(referencedRegion).queryByRole("alert")).toBeNull();
  });

  it("保存校对后明确提示后台生成，并阻止处理期间再次提交", async () => {
    const user = userEvent.setup();
    fns.listEvidenceSnapshots.mockResolvedValue(
      decodeSnapshotList({
        subject_id: SUBJECT_ID,
        review_episode_id: EPISODE_ID,
        active_evidence_snapshot_id: "snap-active",
        active_evidence_processing_revision_id: "processing-revision-1",
        items: [makeSnapshotWire("snap-active", "active")],
      }),
    );
    fns.getProcessingRevision.mockResolvedValue(
      decodeProcessingRevision(makeProcessingRevisionWire()),
    );
    fns.getOcrPage.mockResolvedValue(decodeOcrPage(makeOcrPageWire()));
    fns.createCorrection.mockResolvedValue(
      decodeCorrectionResponse(makeCorrectionResponseWire()),
    );
    await openValid(user);
    await expandCurrentCorrectionTools(user);

    await user.type(
      await screen.findByRole("textbox", { name: "校对后文本" }),
      "患者确认发热。",
    );
    await user.type(
      screen.getByRole("textbox", { name: "校对说明" }),
      "按原始病历校对",
    );
    await confirmCriticalCorrectionWhenShown(user);
    await user.click(screen.getByRole("button", { name: "提交校对" }));
    expect(
      await screen.findByText("已保存，正在生成核对后的资料版本"),
    ).toBeInTheDocument();

    await expandCurrentCorrectionTools(user);
    await user.type(
      screen.getByRole("textbox", { name: "校对后文本" }),
      "患者确认发热。",
    );
    await user.type(
      screen.getByRole("textbox", { name: "校对说明" }),
      "再次核对",
    );
    await confirmCriticalCorrectionWhenShown(user);
    await user.click(screen.getByRole("button", { name: "提交校对" }));
    expect(fns.createCorrection).toHaveBeenCalledTimes(1);
    expect(
      screen.getByText("已保存，正在生成核对后的资料版本"),
    ).toBeInTheDocument();
  });

  it("后台转为待核对后恢复同一候选并携带事件序号继续提交", async () => {
    const user = userEvent.setup();
    fns.listEvidenceSnapshots.mockResolvedValue(
      decodeSnapshotList({
        subject_id: SUBJECT_ID,
        review_episode_id: EPISODE_ID,
        active_evidence_snapshot_id: "snap-active",
        active_evidence_processing_revision_id: "processing-revision-1",
        items: [makeSnapshotWire("snap-active", "active")],
      }),
    );
    fns.getProcessingRevision.mockResolvedValue(
      decodeProcessingRevision(makeProcessingRevisionWire()),
    );
    fns.getOcrPage.mockResolvedValue(decodeOcrPage(makeOcrPageWire()));
    fns.createCorrection.mockResolvedValue(
      decodeCorrectionResponse(makeCorrectionResponseWire()),
    );
    fns.getProcessingCandidate.mockResolvedValue(
      decodeProcessingCandidateStatus({
        candidate_id: "candidate-1",
        job_id: "job-1",
        candidate_status: "needs_attention",
        candidate_status_label: "需要关注",
        candidate_event_seq: 2,
        complete_revision_id: null,
      }),
    );
    await openValid(user);
    await expandCurrentCorrectionTools(user);

    await user.type(
      await screen.findByRole("textbox", { name: "校对后文本" }),
      "患者确认发热。",
    );
    await user.type(
      screen.getByRole("textbox", { name: "校对说明" }),
      "首次核对",
    );
    await confirmCriticalCorrectionWhenShown(user);
    await user.click(screen.getByRole("button", { name: "提交校对" }));
    expect(
      await screen.findByText(
        "已保存，生成核对后的资料版本前需要完成识别核对。",
        {},
        { timeout: 2_000 },
      ),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(fns.getOcrPage.mock.calls.length).toBeGreaterThanOrEqual(3),
    );

    await expandCurrentCorrectionTools(user);
    await user.type(
      screen.getByRole("textbox", { name: "校对后文本" }),
      "患者确认发热。",
    );
    await user.type(
      screen.getByRole("textbox", { name: "校对说明" }),
      "继续核对",
    );
    await confirmCriticalCorrectionWhenShown(user);
    await user.click(screen.getByRole("button", { name: "提交校对" }));
    expect(fns.createCorrection).toHaveBeenCalledTimes(2);
    expect(fns.createCorrection.mock.calls[1]?.[1]).toMatchObject({
      target_candidate_id: "candidate-1",
      expected_candidate_event_seq: 2,
    });
  });

  it("候选先恢复、活动资料后载入时仍持续跟踪同一候选", async () => {
    const user = userEvent.setup();
    const storageKey = `evidence-processing-candidate:${EPISODE}`;
    window.localStorage.setItem(storageKey, "candidate-1");
    let resolveSnapshots!: (
      value: ReturnType<typeof decodeSnapshotList>,
    ) => void;
    fns.listEvidenceSnapshots.mockReturnValue(
      new Promise((resolve) => {
        resolveSnapshots = resolve;
      }),
    );
    fns.getProcessingRevision.mockResolvedValue(
      decodeProcessingRevision(makeProcessingRevisionWire()),
    );
    fns.getOcrPage.mockResolvedValue(decodeOcrPage(makeOcrPageWire()));
    fns.getProcessingCandidate
      .mockResolvedValueOnce(
        decodeProcessingCandidateStatus({
          candidate_id: "candidate-1",
          job_id: "job-1",
          candidate_status: "staged",
          candidate_status_label: "待处理",
          candidate_event_seq: 0,
          complete_revision_id: null,
        }),
      )
      .mockResolvedValue(
        decodeProcessingCandidateStatus({
          candidate_id: "candidate-1",
          job_id: "job-1",
          candidate_status: "needs_attention",
          candidate_status_label: "需要关注",
          candidate_event_seq: 2,
          complete_revision_id: null,
        }),
      );

    await openValid(user);
    expect(
      await screen.findByText("已保存，正在生成核对后的资料版本"),
    ).toBeInTheDocument();
    resolveSnapshots(
      decodeSnapshotList({
        subject_id: SUBJECT_ID,
        review_episode_id: EPISODE_ID,
        active_evidence_snapshot_id: "snap-active",
        active_evidence_processing_revision_id: "processing-revision-1",
        items: [
          withLatestCandidate(
            makeSnapshotWire("snap-active", "active"),
            "needs_attention",
            2,
          ),
        ],
      }),
    );
    expect(
      await screen.findByText(
        "已保存，生成核对后的资料版本前需要完成识别核对。",
        {},
        { timeout: 3_000 },
      ),
    ).toBeInTheDocument();
    expect(window.localStorage.getItem(storageKey)).toBe("candidate-1");
  });

  it("候选轮询短暂失败后自动退避并恢复最新状态", async () => {
    const user = userEvent.setup();
    const storageKey = `evidence-processing-candidate:${EPISODE}`;
    window.localStorage.setItem(storageKey, "candidate-1");
    fns.listEvidenceSnapshots.mockResolvedValue(
      decodeSnapshotList({
        subject_id: SUBJECT_ID,
        review_episode_id: EPISODE_ID,
        active_evidence_snapshot_id: "snap-active",
        active_evidence_processing_revision_id: "processing-revision-1",
        items: [
          withLatestCandidate(
            makeSnapshotWire("snap-active", "active"),
            "processing",
            1,
          ),
        ],
      }),
    );
    fns.getProcessingRevision.mockResolvedValue(
      decodeProcessingRevision(makeProcessingRevisionWire()),
    );
    fns.getOcrPage.mockResolvedValue(decodeOcrPage(makeOcrPageWire()));
    fns.getProcessingCandidate
      .mockRejectedValueOnce(new Error("暂时无法连接"))
      .mockResolvedValue(
        decodeProcessingCandidateStatus({
          candidate_id: "candidate-1",
          job_id: "job-1",
          candidate_status: "needs_attention",
          candidate_status_label: "需要关注",
          candidate_event_seq: 2,
          complete_revision_id: null,
        }),
      );

    await openValid(user);
    expect(
      await screen.findByText(
        "已保存，生成核对后的资料版本前需要完成识别核对。",
        {},
        { timeout: 4_000 },
      ),
    ).toBeInTheDocument();
    expect(fns.getProcessingCandidate).toHaveBeenCalledTimes(2);
    expect(window.localStorage.getItem(storageKey)).toBe("candidate-1");
  });

  it("页面恢复候选时遇到临时连接失败仍保留恢复锚点", async () => {
    const user = userEvent.setup();
    const storageKey = `evidence-processing-candidate:${EPISODE}`;
    window.localStorage.setItem(storageKey, "candidate-1");
    fns.listEvidenceSnapshots.mockReturnValue(new Promise(() => undefined));
    fns.getProcessingCandidate.mockRejectedValue(new Error("暂时无法连接"));

    await openValid(user);
    await waitFor(() =>
      expect(fns.getProcessingCandidate).toHaveBeenCalledWith(
        "candidate-1",
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      ),
    );
    expect(window.localStorage.getItem(storageKey)).toBe("candidate-1");
    expect(
      await screen.findByText(/这部分资料暂时打不开。已经保存目前进度/),
    ).toBeInTheDocument();
  });

  it("系统确认候选不存在时清除失效恢复锚点", async () => {
    const user = userEvent.setup();
    const storageKey = `evidence-processing-candidate:${EPISODE}`;
    window.localStorage.setItem(storageKey, "candidate-missing");
    fns.listEvidenceSnapshots.mockReturnValue(new Promise(() => undefined));
    fns.getProcessingCandidate.mockRejectedValue(
      new EvidenceApiError(
        "PROCESSING_CANDIDATE_NOT_FOUND",
        "未找到资料处理任务",
        "该资料处理任务不存在。",
        "请重新提交核对。",
        404,
      ),
    );

    await openValid(user);
    await waitFor(() =>
      expect(window.localStorage.getItem(storageKey)).toBeNull(),
    );
    expect(
      screen.queryByText("该资料处理任务不存在。"),
    ).not.toBeInTheDocument();
  });

  it.each(["晚到成功", "晚到不存在"])(
    "旧候选恢复%s时不会覆盖或删除刚创建的新候选",
    async (outcome) => {
      const user = userEvent.setup();
      const storageKey = `evidence-processing-candidate:${EPISODE}`;
      window.localStorage.setItem(storageKey, "candidate-old");
      let resolveRestore!: (
        value: ReturnType<typeof decodeProcessingCandidateStatus>,
      ) => void;
      let rejectRestore!: (reason: unknown) => void;
      fns.getProcessingCandidate.mockReturnValue(
        new Promise((resolve, reject) => {
          resolveRestore = resolve;
          rejectRestore = reject;
        }),
      );
      let resolveSnapshots!: (
        value: ReturnType<typeof decodeSnapshotList>,
      ) => void;
      fns.listEvidenceSnapshots.mockReturnValue(
        new Promise((resolve) => {
          resolveSnapshots = resolve;
        }),
      );
      fns.getProcessingRevision.mockResolvedValue(
        decodeProcessingRevision(makeProcessingRevisionWire()),
      );
      fns.getOcrPage.mockResolvedValue(decodeOcrPage(makeOcrPageWire()));
      fns.createCorrection.mockResolvedValue(
        decodeCorrectionResponse({
          ...makeCorrectionResponseWire(),
          candidate_id: "candidate-new",
          job_id: "job-new",
          candidate_status: "terminal_failure",
          candidate_status_label: "未能生成",
        }),
      );

      await openValid(user);
      await waitFor(() =>
        expect(fns.getProcessingCandidate).toHaveBeenCalledWith(
          "candidate-old",
          expect.objectContaining({ signal: expect.any(AbortSignal) }),
        ),
      );
      resolveSnapshots(
        decodeSnapshotList({
          subject_id: SUBJECT_ID,
          review_episode_id: EPISODE_ID,
          active_evidence_snapshot_id: "snap-active",
          active_evidence_processing_revision_id: "processing-revision-1",
          items: [makeSnapshotWire("snap-active", "active")],
        }),
      );
      await expandCurrentCorrectionTools(user);
      await user.type(
        await screen.findByRole("textbox", { name: "校对后文本" }),
        "患者确认发热。",
      );
      await user.type(
        screen.getByRole("textbox", { name: "校对说明" }),
        "按原始病历核对",
      );
      await confirmCriticalCorrectionWhenShown(user);
      await user.click(screen.getByRole("button", { name: "提交校对" }));
      await waitFor(() =>
        expect(window.localStorage.getItem(storageKey)).toBe("candidate-new"),
      );

      if (outcome === "晚到成功") {
        resolveRestore(
          decodeProcessingCandidateStatus({
            candidate_id: "candidate-old",
            job_id: "job-old",
            candidate_status: "ready",
            candidate_status_label: "已生成",
            candidate_event_seq: 3,
            complete_revision_id: "revision-old",
          }),
        );
      } else {
        rejectRestore(
          new EvidenceApiError(
            "PROCESSING_CANDIDATE_NOT_FOUND",
            "未找到资料处理任务",
            "该资料处理任务不存在。",
            "请重新提交核对。",
            404,
          ),
        );
      }

      expect(
        await screen.findByText(
          "已保存，但核对后的资料版本未能生成，请重新核对后再试。",
        ),
      ).toBeInTheDocument();
      expect(window.localStorage.getItem(storageKey)).toBe("candidate-new");
      expect(
        screen.queryByText("核对后的资料版本已生成，尚未启用。"),
      ).not.toBeInTheDocument();
    },
  );

  it("切换识别页时不会把上一页的未提交校对带到下一页", async () => {
    const user = userEvent.setup();
    fns.listEvidenceSnapshots.mockResolvedValue(
      decodeSnapshotList({
        subject_id: SUBJECT_ID,
        review_episode_id: EPISODE_ID,
        active_evidence_snapshot_id: "snap-active",
        active_evidence_processing_revision_id: "processing-revision-1",
        items: [makeSnapshotWire("snap-active", "active")],
      }),
    );
    const revisionWire = makeProcessingRevisionWire();
    revisionWire.pages[1] = {
      entry_id: "entry-2",
      position: 2,
      source_document_version_id: "version-1",
      page_number: 2,
      original_frame: "frame-2",
      page_artifact_id: "artifact-2",
      ocr_page_id: "ocr-page-2",
      status: "succeeded",
      status_label: "页面已就绪",
      failure_reason: null,
      image_available: true,
      page_width: 1240,
      page_height: 1754,
    };
    fns.getProcessingRevision.mockResolvedValue(
      decodeProcessingRevision(revisionWire),
    );
    const firstPage = decodeOcrPage(makeOcrPageWire());
    const secondPage = decodeOcrPage({
      ...makeOcrPageWire(),
      ocr_page_id: "ocr-page-2",
      page_artifact_id: "artifact-2",
      page_number: 2,
      raw_text: "患者肯定咳嗽。",
      raw_text_sha256: "f".repeat(64),
      effective_text: "患者肯定咳嗽。",
      effective_text_sha256: "1".repeat(64),
      locators: [],
    });
    fns.getOcrPage.mockImplementation((ocrPageId) =>
      Promise.resolve(ocrPageId === "ocr-page-2" ? secondPage : firstPage),
    );
    await openValid(user);
    await expandCurrentCorrectionTools(user);
    const corrected = await screen.findByRole("textbox", {
      name: "校对后文本",
    });
    await user.type(corrected, "第一页未提交内容");
    await user.click(
      within(screen.getByLabelText("识别页清单")).getByRole("button", {
        name: /第 2 页/,
      }),
    );

    await waitFor(() => {
      expect(
        screen.getByText("患者肯定咳嗽。", { selector: "pre[tabindex]" }),
      ).toBeInTheDocument();
    });
    await expandCurrentCorrectionTools(user);
    expect(screen.getByRole("textbox", { name: "校对后文本" })).toHaveValue("");
  });

  it("只有 STAGED 候选时不冒充当前版本，显示尚未启用", async () => {
    const user = userEvent.setup();
    fns.listEvidenceSnapshots.mockImplementation(() =>
      Promise.resolve(
        decodeSnapshotList({
          subject_id: SUBJECT_ID,
          review_episode_id: EPISODE_ID,
          active_evidence_snapshot_id: null,
          active_evidence_processing_revision_id: null,
          items: [makeSnapshotWire("snap-staged", "staged")],
        }),
      ),
    );
    await openValid(user);
    await waitFor(() => {
      expect(screen.getByLabelText("当前资料上下文")).toHaveTextContent(
        "尚未启用",
      );
    });
    expect(screen.getByLabelText("识别页清单")).toHaveTextContent(
      "当前资料尚未形成可核对的识别版本",
    );
    expect(screen.queryByText("正在读取识别页清单…")).toBeNull();
  });

  it("处理候选尚未生成时仍用上传任务编号打开处理详情", async () => {
    const user = userEvent.setup();
    fns.listEvidenceSnapshots.mockResolvedValue(
      decodeSnapshotList({
        subject_id: SUBJECT_ID,
        review_episode_id: EPISODE_ID,
        active_evidence_snapshot_id: null,
        active_evidence_processing_revision_id: null,
        items: [makeSnapshotWire("snap-uploading", "processing")],
      }),
    );

    await openValid(user);

    const taskLink = await screen.findByRole("link", {
      name: "查看本次资料进度",
    });
    expect(taskLink.getAttribute("href")).toContain("job=upload-job-1");
  });

  it("重新进入时从服务端恢复待核对状态并锁定新上传", async () => {
    const user = userEvent.setup();
    const activeShape = makeSnapshotWire("snap-active", "active");
    fns.listEvidenceSnapshots.mockResolvedValue(
      decodeSnapshotList({
        subject_id: SUBJECT_ID,
        review_episode_id: EPISODE_ID,
        active_evidence_snapshot_id: null,
        active_evidence_processing_revision_id: null,
        items: [
          {
            ...makeSnapshotWire("snap-pending", "processing"),
            is_current: false,
            base_processing_revision_id: "processing-revision-1",
            members: activeShape.members,
            latest_processing_candidate: {
              candidate_id: "candidate-persisted",
              job_id: "job-persisted",
              candidate_status: "needs_attention",
              candidate_status_label: "需要核对",
              candidate_event_seq: 3,
              complete_revision_id: null,
            },
          },
        ],
      }),
    );
    fns.getProcessingRevision.mockResolvedValue(
      decodeProcessingRevision({
        ...makeProcessingRevisionWire(),
        evidence_snapshot_id: "snap-pending",
        revision_kind: "base",
        revision_kind_label: "基础处理修订",
        status: "ready",
        status_label: "待发布",
        is_current: false,
      }),
    );
    fns.getOcrPage.mockResolvedValue(decodeOcrPage(makeOcrPageWire()));

    await openValid(user);

    expect(
      await screen.findByText(/生成核对后的资料版本前需要完成识别核对/),
    ).toBeInTheDocument();
    expect(screen.queryByRole("radio", { name: "补充资料" })).toBeNull();
    expect(
      screen.getByRole("button", { name: "还有内容待核对" }),
    ).toBeDisabled();
    await waitFor(() =>
      expect(
        window.localStorage.getItem(
          `evidence-processing-candidate:${EPISODE_ID}`,
        ),
      ).toBe("candidate-persisted"),
    );
    expect(fns.buildProcessingRevision).not.toHaveBeenCalled();
  });

  it("快照读取失败时资料版本显示诚实未知状态", async () => {
    const user = userEvent.setup();
    fns.listEvidenceSnapshots.mockImplementation(() =>
      Promise.reject(new Error("boom")),
    );
    await openValid(user);
    await waitFor(() => {
      expect(screen.getByLabelText("当前资料上下文")).toHaveTextContent(
        "暂时无法读取",
      );
    });
  });

  it("首屏提供两种上传方式与中文说明，无内部术语", async () => {
    const user = userEvent.setup();
    await openValid(user);
    expect(
      await screen.findByRole("radio", { name: "补充资料" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("radio", { name: "建立完整资料快照" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/尚无有效资料版本，请先选择「建立完整资料快照」/),
    ).toBeInTheDocument();
    // 界面不暴露内部英文/技术词
    expect(
      screen.queryByText(
        /incremental|full|Job|schema|payload|缓存|门禁|修订号/i,
      ),
    ).toBeNull();
  });

  it("切换方式时显示对应中文说明", async () => {
    const user = userEvent.setup();
    await openActiveUpload(user);
    await user.click(screen.getByRole("radio", { name: "补充资料" }));
    expect(
      screen.getByText(/在上一有效快照的全部资料基础上/),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("radio", { name: "建立完整资料快照" }));
    expect(
      screen.getByText(/本次选择的文件构成新的完整资料集合/),
    ).toBeInTheDocument();
  });

  it("审核节点不属于该受试者时显示未找到提示", async () => {
    window.location.hash = `#/subjects/${SUBJECT_ID}/evidence?episode=episode-uat-02-screening-barrier`;
    render(<EvidencePage />);
    expect(await screen.findByText(/未找到这个审核节点/)).toBeInTheDocument();
  });

  it("上传文件后展示复核分类，同名冲突未处置时确认禁用", async () => {
    const user = userEvent.setup();
    await openActiveUpload(user);
    await user.click(screen.getByRole("radio", { name: "补充资料" }));
    const input = screen.getByLabelText("选择文件");
    await user.upload(input, [
      new File(["a"], "检查报告.pdf", { type: "application/pdf" }),
      new File(["b"], "知情同意书.pdf", { type: "application/pdf" }),
      new File(["c"], "入院记录.docx", {
        type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      }),
      new File(["d"], "出院小结.zip", { type: "application/zip" }),
    ]);
    expect(
      await screen.findByRole("heading", { name: /确认前复核/ }),
    ).toBeInTheDocument();
    const review = screen.getByLabelText("确认前复核");
    expect(within(review).getByText("检查报告.pdf")).toBeInTheDocument();
    expect(within(review).getByText("新增资料")).toBeInTheDocument();
    expect(within(review).getByText("内容重复")).toBeInTheDocument();
    expect(within(review).getByText("名称相同但内容不同")).toBeInTheDocument();
    expect(within(review).getByText("格式不支持")).toBeInTheDocument();
    // 冲突未处置：确认禁用
    expect(screen.getByRole("button", { name: "确认上传" })).toBeDisabled();
    expect(
      screen.getByText(/还有 1 份同名文件未选择处置方式/),
    ).toBeInTheDocument();
  });

  it("解决同名冲突后确认可用，提交正确的受试者/节点与处置", async () => {
    const user = userEvent.setup();
    await openActiveUpload(user);
    await user.click(screen.getByRole("radio", { name: "补充资料" }));
    const input = screen.getByLabelText("选择文件");
    await user.upload(input, [
      new File(["a"], "检查报告.pdf", { type: "application/pdf" }),
      new File(["b"], "知情同意书.pdf", { type: "application/pdf" }),
      new File(["c"], "入院记录.docx", {
        type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      }),
      new File(["d"], "出院小结.zip", { type: "application/zip" }),
    ]);
    await screen.findByText("确认前复核");
    await user.click(screen.getByLabelText("作为原资料的新版本"));
    const confirm = screen.getByRole("button", { name: "确认上传" });
    expect(confirm).toBeEnabled();
    await user.click(confirm);

    await screen.findByText(/已建立资料快照/);
    expect(fns.confirmUpload).toHaveBeenCalledWith(
      PREVIEW_ID,
      expect.objectContaining({
        preview_sha256: PREVIEW_SHA,
        upload_mode: "incremental",
        base_revision: 1,
        resolutions: { "item-3": "new_version" },
      }),
    );
    // 受试者/节点上下文保持正确
    const band = screen.getByLabelText("当前资料上下文");
    expect(band).toHaveTextContent("UAT-01");
    expect(band).toHaveTextContent("筛选期");
  });

  it("只有不支持文件时不允许建立空资料快照", async () => {
    const user = userEvent.setup();
    fns.createUploadPreview.mockResolvedValueOnce(
      decodeUploadPreview(makePreviewWire({ items: [ITEMS[3]] })),
    );
    await openValid(user);
    await user.click(
      await screen.findByRole("radio", { name: "建立完整资料快照" }),
    );
    const input = screen.getByLabelText("选择文件");
    await user.upload(
      input,
      new File(["archive"], "资料压缩包.zip", { type: "application/zip" }),
    );
    const review = await screen.findByLabelText("确认前复核");
    expect(within(review).getByText("格式不支持")).toBeInTheDocument();
    expect(within(review).getByText(/没有可纳入的资料/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "确认上传" })).toBeDisabled();
  });

  it("所选资料全部重复时不诱导再次上传，直接返回当前资料", async () => {
    const user = userEvent.setup();
    fns.createUploadPreview.mockResolvedValueOnce(
      decodeUploadPreview(makePreviewWire({ items: [ITEMS[1]] })),
    );
    await openActiveUpload(user);
    await user.click(screen.getByRole("radio", { name: "补充资料" }));
    await user.upload(
      screen.getByLabelText("选择文件"),
      new File(["same"], "知情同意书.pdf", { type: "application/pdf" }),
    );

    expect(
      await screen.findByText(
        "所选资料已在当前版本中，无需再次上传或建立资料快照。",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "确认上传" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "返回已有资料" }));
    expect(
      await screen.findByText("当前有效资料可在下方查看。"),
    ).toBeInTheDocument();
    expect(fns.cancelUploadPreview).toHaveBeenCalledTimes(1);
    expect(fns.confirmUpload).not.toHaveBeenCalled();
  });

  it("整组资料已有待处理版本时不允许再次确认", async () => {
    const user = userEvent.setup();
    fns.createUploadPreview.mockResolvedValueOnce(
      decodeUploadPreview(
        makePreviewWire({
          upload_mode: "full",
          upload_mode_label: "建立完整资料快照",
          items: [ITEMS[0]],
          matching_snapshot_id: "snap-pending",
          matching_snapshot_status: "processing",
          matching_snapshot_status_label: "正在整理",
        }),
      ),
    );
    await openValid(user);
    await user.click(
      await screen.findByRole("radio", { name: "建立完整资料快照" }),
    );
    await user.upload(
      screen.getByLabelText("选择文件"),
      new File(["same-pending"], "检查报告.pdf", { type: "application/pdf" }),
    );

    expect(
      await screen.findByText(/这组资料已经形成正在整理/),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "确认上传" })).toBeNull();
    expect(
      screen.getByRole("button", { name: "返回已有资料" }),
    ).toBeInTheDocument();
  });

  it("取消预览不建立快照，回到当前资料阅读态", async () => {
    const user = userEvent.setup();
    await openActiveUpload(user);
    await user.click(screen.getByRole("radio", { name: "补充资料" }));
    const input = screen.getByLabelText("选择文件");
    await user.upload(input, [
      new File(["a"], "检查报告.pdf", { type: "application/pdf" }),
      new File(["c"], "入院记录.docx", {
        type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      }),
    ]);
    await screen.findByText("确认前复核");
    await user.click(screen.getByRole("button", { name: "取消预览" }));
    expect(
      await screen.findByText("当前有效资料可在下方查看。"),
    ).toBeInTheDocument();
    expect(fns.cancelUploadPreview).toHaveBeenCalledTimes(1);
    expect(fns.confirmUpload).not.toHaveBeenCalled();
    // 回到阅读态：上传方式和文件入口都收起
    expect(screen.queryByLabelText("选择文件")).not.toBeInTheDocument();
    expect(screen.queryByRole("radio", { name: "补充资料" })).toBeNull();
  });

  it("有活动预览时锁定上传方式并隐藏再次选文件，不静默丢引用", async () => {
    const user = userEvent.setup();
    await openActiveUpload(user);
    await user.click(screen.getByRole("radio", { name: "补充资料" }));
    await user.upload(screen.getByLabelText("选择文件"), [
      new File(["a"], "检查报告.pdf", { type: "application/pdf" }),
      new File(["c"], "入院记录.docx", {
        type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      }),
    ]);
    await screen.findByText("确认前复核");
    // 方式锁定：两个 radio 均禁用
    expect(screen.getByRole("radio", { name: "补充资料" })).toBeDisabled();
    expect(
      screen.getByRole("radio", { name: "建立完整资料快照" }),
    ).toBeDisabled();
    expect(
      screen.getByText(/如需更换上传方式，请先点击「取消预览」/),
    ).toBeInTheDocument();
    // 再次选文件入口隐藏
    expect(screen.queryByLabelText("选择文件")).not.toBeInTheDocument();
    // 取消后恢复可选
    await user.click(screen.getByRole("button", { name: "取消预览" }));
    await screen.findByText("当前有效资料可在下方查看。");
    expect(
      screen.getByRole("button", { name: "补充或重建资料" }),
    ).toBeEnabled();
    expect(
      screen.queryByRole("radio", { name: "建立完整资料快照" }),
    ).toBeNull();
  });

  it("确认重试复用同一幂等键；新预览使用新键", async () => {
    const user = userEvent.setup();
    await openActiveUpload(user);
    await user.click(screen.getByRole("radio", { name: "补充资料" }));
    await user.upload(screen.getByLabelText("选择文件"), [
      new File(["a"], "检查报告.pdf", { type: "application/pdf" }),
      new File(["b"], "知情同意书.pdf", { type: "application/pdf" }),
      new File(["c"], "入院记录.docx", {
        type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      }),
      new File(["d"], "出院小结.zip", { type: "application/zip" }),
    ]);
    await screen.findByText("确认前复核");
    await user.click(screen.getByLabelText("作为原资料的新版本"));

    // 第一次确认：网络错误（服务端可能已成功），响应中断
    fns.confirmUpload.mockRejectedValueOnce(new Error("network down"));
    await user.click(screen.getByRole("button", { name: "确认上传" }));
    await screen.findByText(/网络|暂时打不开|temporarily/i);

    // 第二次确认成功：必须复用完全相同的幂等键（同键回放，不会重复建快照）
    await user.click(screen.getByRole("button", { name: "确认上传" }));
    await screen.findByText(/已建立资料快照/);
    const firstKey = fns.confirmUpload.mock.calls[0][1].idempotency_key;
    const secondKey = fns.confirmUpload.mock.calls[1][1].idempotency_key;
    expect(firstKey.length).toBeGreaterThan(0);
    expect(secondKey).toBe(firstKey);

    // 新预览 → 新幂等生命周期
    await user.click(screen.getByRole("button", { name: "继续补充资料" }));
    await user.click(screen.getByRole("radio", { name: "补充资料" }));
    await user.upload(screen.getByLabelText("选择文件"), [
      new File(["a"], "检查报告.pdf", { type: "application/pdf" }),
      new File(["b"], "知情同意书.pdf", { type: "application/pdf" }),
      new File(["c"], "入院记录.docx", {
        type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      }),
      new File(["d"], "出院小结.zip", { type: "application/zip" }),
    ]);
    await screen.findByText("确认前复核");
    await user.click(screen.getByLabelText("作为原资料的新版本"));
    await user.click(screen.getByRole("button", { name: "确认上传" }));
    await screen.findByText(/已建立资料快照/);
    const thirdKey = fns.confirmUpload.mock.calls[2][1].idempotency_key;
    expect(thirdKey).not.toBe(firstKey);
  });

  it("移除文件按非遗漏条目次序映射，完整资料遗漏行不占文件下标", async () => {
    const user = userEvent.setup();
    const omissionItem = {
      item_id: "item-5",
      file_name: "既往病历.pdf",
      byte_size: 4096,
      media_type: "application/pdf",
      status: "full_snapshot_omission",
      status_label: "完整资料中未选择",
      processing_hint: "omitted",
      processing_hint_label: "不纳入本次快照",
      reason: "该资料存在于上一有效快照，但本次未选择。",
      next_action: "如确认遗漏，请重新选择该文件；完整资料快照只包含本次选择。",
      logical_document_id: "logical-5",
      existing_version_id: "version-5",
      error_detail: null,
    };
    fns.createUploadPreview.mockResolvedValueOnce(
      decodeUploadPreview(
        makePreviewWire({
          upload_mode: "full",
          upload_mode_label: "建立完整资料快照",
          items: [...ITEMS, omissionItem],
        }),
      ),
    );
    await openValid(user);
    await user.click(
      await screen.findByRole("radio", { name: "建立完整资料快照" }),
    );
    await user.upload(screen.getByLabelText("选择文件"), [
      new File(["a"], "检查报告.pdf", { type: "application/pdf" }),
      new File(["b"], "知情同意书.pdf", { type: "application/pdf" }),
      new File(["c"], "入院记录.docx", {
        type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      }),
      new File(["d"], "出院小结.zip", { type: "application/zip" }),
    ]);
    await screen.findByText("确认前复核");
    expect(
      within(screen.getByLabelText("确认前复核")).getAllByText(
        "完整资料中未选择",
      ).length,
    ).toBeGreaterThan(0);

    // 移除 检查报告.pdf（item-1）：先取消旧预览，再用剩余 3 份文件重新生成
    const review = screen.getByLabelText("确认前复核");
    const removeButtons = within(review).getAllByRole("button", {
      name: "移除",
    });
    await user.click(removeButtons[0]);
    await waitFor(() => {
      expect(fns.cancelUploadPreview).toHaveBeenCalledWith(PREVIEW_ID);
    });
    await waitFor(() => {
      expect(fns.createUploadPreview).toHaveBeenCalledTimes(2);
    });
    const secondInput = fns.createUploadPreview.mock.calls[1][0];
    expect(secondInput.uploadMode).toBe("full");
    expect(secondInput.files).toHaveLength(3);
    expect(secondInput.files[0].name).toBe("知情同意书.pdf");
  });

  it("移除时取消清理失败：保留当前预览、显示后端中文错误、不新建预览", async () => {
    const user = userEvent.setup();
    fns.cancelUploadPreview.mockRejectedValueOnce(
      new EvidenceApiError(
        "PREVIEW_CLEANUP_FAILED",
        "取消清理未完成",
        "预览已记录取消，但临时文件清理尚未完成。",
        "请重试取消以完成清理；系统不会使用该预览进行确认。",
      ),
    );
    await openActiveUpload(user);
    await user.click(screen.getByRole("radio", { name: "补充资料" }));
    await user.upload(screen.getByLabelText("选择文件"), [
      new File(["a"], "检查报告.pdf", { type: "application/pdf" }),
      new File(["b"], "知情同意书.pdf", { type: "application/pdf" }),
      new File(["c"], "入院记录.docx", {
        type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      }),
      new File(["d"], "出院小结.zip", { type: "application/zip" }),
    ]);
    await screen.findByText("确认前复核");
    const beforeCreates = fns.createUploadPreview.mock.calls.length;
    const review = screen.getByLabelText("确认前复核");
    await user.click(
      within(review).getAllByRole("button", { name: "移除" })[0],
    );
    // 后端中文错误可见，原预览仍可见，未生成新预览
    expect(await screen.findByText(/临时文件清理尚未完成/)).toBeInTheDocument();
    expect(screen.getByLabelText("确认前复核")).toBeInTheDocument();
    expect(fns.createUploadPreview.mock.calls.length).toBe(beforeCreates);
  });
});
