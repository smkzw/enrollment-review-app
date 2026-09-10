/**
 * 证据工作台 e2e 合成 V2 数据与路由拦截（任务 worker_03）。
 * 只使用干净的合成 V2 数据；拦截 /api/v2/** 使构建产物在真实浏览器中
 * 走完整解码/渲染路径，不依赖本机 V2 服务或真实临床资料。
 */

import type { Page } from "@playwright/test";

export const SUBJECT_ID = "subject-uat-01-clear";
export const EPISODE_ID = "episode-uat-01-screening-clear";
export const PREVIEW_ID = "preview-e2e-0001";
export const PREVIEW_SHA = "e2e".repeat(21) + "0"; // 64 hex chars
export const SNAPSHOT_ID = "snap-e2e-0001";
export const JOB_ID = "job-e2e-0001";
const PROJECT_ID = "project-synthetic-phase-iii";

const CATALOG_PROJECT = {
  project_id: PROJECT_ID,
  project_code: "UAT-PHASE-III",
  project_name: "界面试用项目",
  study_phase: "phase_iii",
  study_phase_label: "Ⅲ期",
  protocol_code: "UAT-PROTOCOL-001",
  official_version: "V1.0",
  official_date_value: "2026-08-19",
  official_date_precision: "day",
  rule_set_id: "rules-e2e-phase-iii",
  rule_set_revision: 1,
};

const CATALOG_SUBJECT = {
  subject_id: SUBJECT_ID,
  subject_code: "UAT-01",
  project_id: PROJECT_ID,
  center_code: "UAT",
  center_name: "界面试用中心",
  sex: "女",
  age_years: 42,
  revision: 1,
};

const CATALOG_EPISODE = {
  review_episode_id: EPISODE_ID,
  subject_id: SUBJECT_ID,
  project_id: PROJECT_ID,
  rule_set_id: "rules-e2e-phase-iii",
  study_phase: "phase_iii",
  study_phase_label: "Ⅲ期",
  stage: "screening",
  stage_label: "筛选期",
  protocol_version_id: "protocol-e2e-v1",
  rule_set_revision: 1,
  evidence_snapshot_id: "snapshot-e2e-initial",
  active_evidence_snapshot_id: "snapshot-e2e-active",
  active_evidence_processing_revision_id: "processing-e2e-active",
  anchor_dates: {},
  due_at: null,
  revision: 1,
};

export interface EvidenceRequestLog {
  url: string;
  method: string;
  /** multipart 表单字段（预览创建） */
  form: Record<string, string>;
  /** commit 请求体 */
  body: Record<string, unknown> | null;
}

export interface SyntheticPreviewOptions {
  mode: "incremental" | "full";
}

function syntheticMetadataHead(
  sourceDocumentVersionId: string,
  suffix: string,
  documentType: string,
) {
  return {
    metadata_revision_id: `metadata-e2e-${suffix}`,
    source_document_version_id: sourceDocumentVersionId,
    document_type: documentType,
    source_party: "研究中心",
    reason: "系统根据文件名提出建议。",
    is_auto_suggestion: true,
    supersedes_metadata_revision_id: null,
    revision: 1,
    created_at: "2026-08-19T08:00:00Z",
    created_by: "本地用户",
  };
}

const FILE_ITEMS = {
  addedReport: {
    item_id: "item-e2e-added-report",
    file_name: "检查报告.pdf",
    byte_size: 20480,
    media_type: "application/pdf",
    status: "added",
    status_label: "新增资料",
    processing_hint: "process_new",
    processing_hint_label: "需要处理",
    reason: "该文件内容与文件名均未出现在上一有效快照中，为本次新增资料。",
    next_action: "将首次处理该文件，请确认后提交。",
    logical_document_id: "logical-e2e-report",
    existing_version_id: null,
    error_detail: null,
  },
  addedBlood: {
    item_id: "item-e2e-added-blood",
    file_name: "血常规报告.png",
    byte_size: 512000,
    media_type: "image/png",
    status: "added",
    status_label: "新增资料",
    processing_hint: "process_new",
    processing_hint_label: "需要处理",
    reason: "该文件内容与文件名均未出现在上一有效快照中，为本次新增资料。",
    next_action: "将首次处理该文件，请确认后提交。",
    logical_document_id: "logical-e2e-blood",
    existing_version_id: null,
    error_detail: null,
  },
  duplicateIc: {
    item_id: "item-e2e-dup-ic",
    file_name: "知情同意书.pdf",
    byte_size: 40960,
    media_type: "application/pdf",
    status: "duplicate",
    status_label: "内容重复",
    processing_hint: "reuse_existing",
    processing_hint_label: "复用已有处理结果",
    reason: "该文件内容与上一有效快照中已存在的资料完全相同。",
    next_action: "系统将复用已有处理结果，不会重复保存或重复识别。",
    logical_document_id: "logical-e2e-ic",
    existing_version_id: null,
    error_detail: null,
  },
  reprocessIc: {
    item_id: "item-e2e-reprocess-ic",
    file_name: "知情同意书.pdf",
    byte_size: 40960,
    media_type: "application/pdf",
    status: "expected_reprocessing",
    status_label: "需要重新识别",
    processing_hint: "reprocess",
    processing_hint_label: "需要重新识别",
    reason: "完整资料快照重新纳入了与基准内容相同的文件。",
    next_action: "系统将按本次快照重新处理该文件。",
    logical_document_id: "logical-e2e-ic",
    existing_version_id: "version-e2e-ic",
    error_detail: null,
  },
  conflictAdmission: {
    item_id: "item-e2e-conflict-admission",
    file_name: "入院记录.docx",
    byte_size: 65536,
    media_type:
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    status: "conflict",
    status_label: "名称相同但内容不同",
    processing_hint: "require_resolution",
    processing_hint_label: "需要选择处置方式",
    reason: "存在同名文件但内容不同，系统不会自动覆盖。",
    next_action: "请选择“作为原资料的新版本”或“作为另一份资料并列保留”。",
    logical_document_id: "logical-e2e-admission",
    existing_version_id: "version-e2e-admission",
    error_detail: null,
  },
  unsupportedZip: {
    item_id: "item-e2e-unsupported-zip",
    file_name: "出院小结.zip",
    byte_size: 102400,
    media_type: "application/zip",
    status: "unsupported",
    status_label: "格式不支持",
    processing_hint: "rejected",
    processing_hint_label: "不纳入处理",
    reason: "该文件格式当前不受支持。",
    next_action: "请解压或转换为受支持的格式（PDF、Word、TXT、常用图片）后重新选择。",
    logical_document_id: null,
    existing_version_id: null,
    error_detail: null,
  },
  omissionHistory: {
    item_id: "item-e2e-omission-history",
    file_name: "既往病历.pdf",
    byte_size: 81920,
    media_type: "application/pdf",
    status: "full_snapshot_omission",
    status_label: "完整资料中未选择",
    processing_hint: "omitted",
    processing_hint_label: "不纳入本次快照",
    reason: "该资料存在于上一有效快照，但本次未选择。",
    next_action: "如确认遗漏，请重新选择该文件；完整资料快照只包含本次选择。",
    logical_document_id: "logical-e2e-history",
    existing_version_id: "version-e2e-history",
    error_detail: null,
  },
} as const;

export function syntheticPreview(
  options: SyntheticPreviewOptions,
): Record<string, unknown> {
  const items =
    options.mode === "incremental"
      ? [
          FILE_ITEMS.addedReport,
          FILE_ITEMS.addedBlood,
          FILE_ITEMS.duplicateIc,
          FILE_ITEMS.conflictAdmission,
          FILE_ITEMS.unsupportedZip,
        ]
      : [
          FILE_ITEMS.addedReport,
          FILE_ITEMS.addedBlood,
          FILE_ITEMS.reprocessIc,
          FILE_ITEMS.conflictAdmission,
          FILE_ITEMS.unsupportedZip,
          FILE_ITEMS.omissionHistory,
        ];
  return {
    preview_id: PREVIEW_ID,
    project_id: "project-synthetic-phase-iii",
    subject_id: SUBJECT_ID,
    review_episode_id: EPISODE_ID,
    upload_mode: options.mode,
    upload_mode_label:
      options.mode === "incremental" ? "补充资料" : "建立完整资料快照",
    base_revision: 1,
    base_snapshot_id: "snap-e2e-base",
    status: "staged",
    status_label: "等待确认",
    items,
    matching_snapshot_id: null,
    matching_snapshot_status: null,
    matching_snapshot_status_label: null,
    preview_sha256: PREVIEW_SHA,
    created_at: "2026-08-19T08:00:00Z",
    created_by: "本地用户",
  };
}

export function syntheticCommit(mode: "incremental" | "full") {
  return {
    commit_id: "commit-e2e-0001",
    preview_id: PREVIEW_ID,
    evidence_snapshot_id: SNAPSHOT_ID,
    project_id: "project-synthetic-phase-iii",
    subject_id: SUBJECT_ID,
    review_episode_id: EPISODE_ID,
    upload_mode: mode,
    upload_mode_label: mode === "incremental" ? "补充资料" : "建立完整资料快照",
    idempotency_key: "idem-e2e-0001",
    job_id: JOB_ID,
    created: true,
    replayed: false,
    duplicate: false,
    resolutions: [
      {
        item_id: FILE_ITEMS.conflictAdmission.item_id,
        logical_document_id: "logical-e2e-admission",
        resolution: "new_version",
        resolution_label: "作为原资料的新版本",
        source_document_version_id: "version-e2e-admission-v2",
        supersedes_version_id: "version-e2e-admission",
      },
    ],
    snapshot: {
      evidence_snapshot_id: SNAPSHOT_ID,
      project_id: "project-synthetic-phase-iii",
      subject_id: SUBJECT_ID,
      review_episode_id: EPISODE_ID,
      upload_mode: mode,
      upload_mode_label: mode === "incremental" ? "补充资料" : "建立完整资料快照",
      prior_snapshot_id: "snap-e2e-base",
      comparison_snapshot_id: null,
      status: "processing",
      status_label: "处理中",
      is_current: false,
      base_processing_revision_id: null,
      upload_job_id: JOB_ID,
      members: [
        {
          member_id: "member-e2e-report",
          snapshot_id: SNAPSHOT_ID,
          logical_document_id: "logical-e2e-report",
          source_document_version_id: "version-e2e-report",
          file_name: "检查报告.pdf",
          media_type: "application/pdf",
          version_number: 1,
          origin: "added",
          origin_label: "本次新增",
          metadata_head: syntheticMetadataHead(
            "version-e2e-report",
            "report",
            "检查报告",
          ),
        },
        {
          member_id: "member-e2e-ic",
          snapshot_id: SNAPSHOT_ID,
          logical_document_id: "logical-e2e-ic",
          source_document_version_id: "version-e2e-ic",
          file_name: "知情同意书.pdf",
          media_type: "application/pdf",
          version_number: 1,
          origin: "inherited",
          origin_label: "继承自上一快照",
          metadata_head: syntheticMetadataHead(
            "version-e2e-ic",
            "ic",
            "知情同意书",
          ),
        },
      ],
      collection_sha256: "c".repeat(64),
      created_at: "2026-08-19T08:00:00Z",
      created_by: "本地用户",
    },
    created_at: "2026-08-19T08:00:00Z",
    created_by: "本地用户",
  };
}

export function syntheticSnapshotList(activeReview = false) {
  const activeSnapshot = {
    evidence_snapshot_id: "snapshot-e2e-active",
    project_id: "project-synthetic-phase-iii",
    subject_id: SUBJECT_ID,
    review_episode_id: EPISODE_ID,
    upload_mode: "full",
    upload_mode_label: "建立完整资料快照",
    prior_snapshot_id: null,
    comparison_snapshot_id: null,
    status: "active",
    status_label: "当前有效",
    is_current: true,
    base_processing_revision_id: "processing-e2e-active",
    upload_job_id: null,
    members: [{
      member_id: "member-e2e-active",
      snapshot_id: "snapshot-e2e-active",
      logical_document_id: "logical-e2e-active",
      source_document_version_id: "version-e2e-active",
      file_name: "筛选期病历.pdf",
      media_type: "application/pdf",
      version_number: 1,
      origin: "added",
      origin_label: "本次新增",
      metadata_head: syntheticMetadataHead(
        "version-e2e-active",
        "active",
        "筛选期病历",
      ),
    }],
    collection_sha256: "d".repeat(64),
    created_at: "2026-08-21T08:00:00Z",
    created_by: "本地用户",
  };
  return {
    subject_id: SUBJECT_ID,
    review_episode_id: EPISODE_ID,
    active_evidence_snapshot_id: activeReview ? activeSnapshot.evidence_snapshot_id : null,
    active_evidence_processing_revision_id: activeReview ? "processing-e2e-active" : null,
    items: activeReview ? [activeSnapshot] : [],
  };
}

export function syntheticProcessingRevision() {
  return {
    evidence_processing_revision_id: "processing-e2e-active",
    revision_kind: "complete",
    revision_kind_label: "完整处理版本",
    evidence_snapshot_id: "snapshot-e2e-active",
    base_processing_revision_id: "processing-e2e-base",
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
        entry_id: "entry-e2e-1",
        position: 1,
        source_document_version_id: "version-e2e-active",
        page_number: 1,
        original_frame: "frame-e2e-1",
        page_artifact_id: "artifact-e2e-1",
        ocr_page_id: "ocr-e2e-1",
        status: "succeeded",
        status_label: "页面已就绪",
        failure_reason: null,
        image_available: true,
        page_width: 1240,
        page_height: 1754,
      },
      {
        entry_id: "entry-e2e-2",
        position: 2,
        source_document_version_id: "version-e2e-active",
        page_number: 2,
        original_frame: null,
        page_artifact_id: "artifact-e2e-2",
        ocr_page_id: null,
        status: "failed",
        status_label: "页面处理失败",
        failure_reason: "原始页面读取失败，请在后续恢复处理中重试。",
        image_available: false,
        page_width: null,
        page_height: null,
      },
    ],
    locator_ids: ["locator-e2e-1", "locator-e2e-degraded"],
    risk_scan_ids: ["scan-e2e-1"],
    risk_review_ids: [],
    risk_flag_count: 1,
    pending_risk_flag_count: 1,
    correction_ids: [],
    metadata_revision_ids: [],
    referenced_document_revision_ids: ["ref-revision-e2e-1"],
    resolution_revision_ids: [],
    gates: [],
    created_at: "2026-08-21T08:00:00Z",
    created_by: "本地用户",
  };
}

export function syntheticOcrPage() {
  return {
    ocr_page_id: "ocr-e2e-1",
    page_artifact_id: "artifact-e2e-1",
    source_document_version_id: "version-e2e-active",
    page_number: 1,
    source_sha256: "c".repeat(64),
    raw_text: "患者否认近期发热，ALT 39 U/L。",
    raw_text_sha256: "e".repeat(64),
    status: "succeeded",
    status_label: "已识别",
    processing_revision_id: "processing-e2e-active",
    is_current_revision: true,
    effective_text: "患者否认近期发热，ALT 39 U/L。",
    effective_text_sha256: "f".repeat(64),
    selected_corrections: [],
    risk_scans: [{
      scan_id: "scan-e2e-1",
      ocr_page_id: "ocr-e2e-1",
      raw_text_sha256: "e".repeat(64),
      scanner_rule_version: "识别核对规则-1",
      flags_sha256: "1".repeat(64),
      coverage_status: "complete",
      created_at: "2026-08-21T08:00:00Z",
      flags: [{
        risk_id: "risk-negation",
        kind: "negation_polarity",
        kind_label: "肯定/否定关系",
        level: "blocking",
        level_label: "需核对",
        text: "否认",
        text_start: 2,
        text_end: 4,
        detail: "请对照原始资料确认是否为否定表述。",
        rule_version: "识别核对规则-1",
      }],
    }],
    risk_reviews: [],
    locators: [{
      locator_id: "locator-e2e-1",
      page_artifact_id: "artifact-e2e-1",
      ocr_page_id: "ocr-e2e-1",
      source_document_version_id: "version-e2e-active",
      page_number: 1,
      source_layer: "native_text",
      source_layer_label: "原始资料文字层",
      source_text_sha256: "e".repeat(64),
      target_id: "target-e2e-1",
      precision: "bbox",
      precision_label: "原文区域",
      degradation_reason: null,
      text_start: 2,
      text_end: 4,
      excerpt: "否认",
      disambiguation: "unique_match",
      locator_algorithm_version: "定位规则-1",
      authenticity: "authenticated",
      match_confidence: 1,
      bbox: { x0: 120, y0: 440, x1: 430, y1: 525 },
      coordinate_frame: {
        space: "page_image_pixels",
        page_width: 1240,
        page_height: 1754,
        rotation: 0,
        transform_version: "页图坐标换算-1",
      },
      coordinate_transform_version: "页图坐标换算-1",
    }, {
      locator_id: "locator-e2e-degraded",
      page_artifact_id: "artifact-e2e-1",
      ocr_page_id: "ocr-e2e-1",
      source_document_version_id: "version-e2e-active",
      page_number: 1,
      source_layer: "raw_ocr",
      source_layer_label: "原始识别文字",
      source_text_sha256: "e".repeat(64),
      target_id: "target-e2e-degraded",
      precision: "page_excerpt",
      precision_label: "页内摘录",
      degradation_reason: "当前资料无法稳定框出具体区域，仅保留页内摘录。",
      text_start: 0,
      text_end: 8,
      excerpt: "患者否认近期发热",
      disambiguation: "unique_match",
      locator_algorithm_version: "定位规则-1",
      authenticity: "degraded",
      match_confidence: 0.95,
      bbox: null,
      coordinate_frame: null,
      coordinate_transform_version: null,
    }],
  };
}

function syntheticReferencedDocument(status = "proposed"): Record<string, unknown> {
  return {
    revision_id: "ref-revision-e2e-1",
    referenced_document_id: "refdoc-e2e-1",
    project_id: "project-synthetic-phase-iii",
    subject_id: SUBJECT_ID,
    review_episode_id: EPISODE_ID,
    description: "既往过敏原检测报告",
    document_type: "检验报告",
    source_party: "研究中心",
    origin: "deterministic_candidate",
    origin_label: "系统识别候选",
    pattern_version: "提及识别规则-1",
    status,
    status_label: status === "confirmed" ? "已确认" : "待确认",
    user_reviewed: status === "confirmed",
    reason: status === "confirmed" ? "已对照原文确认确有提及。" : null,
    revision: status === "confirmed" ? 2 : 1,
    supersedes_revision_id: status === "confirmed" ? "ref-revision-e2e-1" : null,
    trigger_locator_id: status === "confirmed" ? "locator-e2e-1" : null,
    resolution: null,
    created_at: "2026-08-21T08:00:00Z",
    created_by: "本地用户",
  };
}

export function syntheticReferencedDocumentList(activeReview = false) {
  return {
    subject_id: SUBJECT_ID,
    review_episode_id: EPISODE_ID,
    items: activeReview ? [syntheticReferencedDocument()] : [],
  };
}

/** 从 multipart 请求体提取指定表单字段（Playwright 未暴露 formData()）。 */
function multipartField(buffer: Buffer | null, name: string): string | null {
  if (buffer === null) return null;
  const text = buffer.toString("latin1");
  const re = new RegExp(`name="${name}"\\r?\\n\\r?\\n([\\s\\S]*?)\\r?\\n--`);
  const match = re.exec(text);
  if (match === null) return null;
  return match[1].replace(/\r?\n$/, "");
}

export interface RegisterEvidenceRoutesOptions {
  /** 让 DELETE /evidence-upload-previews/{id} 返回 500（模拟取消清理失败） */
  failCancel?: boolean;
  /** 返回已启用的页、识别风险、定位和被提及资料，供核对闭环 E2E。 */
  activeReview?: boolean;
  /** 校对提交返回结构化修订冲突，验证草稿和差异保留。 */
  correctionConflict?: boolean;
  /** 显示页面视觉核验任务；默认不显示，避免影响其他证据工作台场景。 */
  selectiveVisionTask?: "failed_final";
}

/** 注册 /api/v2/** 路由拦截并返回请求日志。 */
export async function registerEvidenceRoutes(
  page: Page,
  options: RegisterEvidenceRoutesOptions = {},
): Promise<EvidenceRequestLog[]> {
  const log: EvidenceRequestLog[] = [];
  let createdMode: "incremental" | "full" | null = null;
  let referencedStatus = "proposed";
  let referencedProvided = false;
  let selectiveVisionState = options.selectiveVisionTask ?? null;

  await page.route("**/api/v2/**", async (route) => {
    const request = route.request();
    const url = request.url();
    const method = request.method();
    let form: Record<string, string> = {};
    let body: Record<string, unknown> | null = null;

    if (method === "POST" && url.endsWith("/evidence-upload-previews")) {
      const buffer = request.postDataBuffer();
      const uploadMode = multipartField(buffer, "upload_mode");
      const reviewEpisodeId = multipartField(buffer, "review_episode_id");
      const mode = uploadMode === "full" ? "full" : "incremental";
      form = {
        upload_mode: mode,
        review_episode_id: reviewEpisodeId ?? "",
        base_revision: multipartField(buffer, "base_revision") ?? "",
      };
      log.push({ url, method, form, body: null });
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify(syntheticPreview({ mode })),
      });
      return;
    }

    if (method === "GET" && url.endsWith("/protocol/projects")) {
      log.push({ url, method, form, body: null });
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ projects: [CATALOG_PROJECT] }),
      });
      return;
    }

    if (method === "GET" && url.endsWith(`/protocol/projects/${PROJECT_ID}`)) {
      log.push({ url, method, form, body: null });
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          project: CATALOG_PROJECT,
          versions: [],
          publication_count: 1,
        }),
      });
      return;
    }

    if (method === "GET" && url.endsWith(`/projects/${PROJECT_ID}/subjects`)) {
      log.push({ url, method, form, body: null });
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ project_id: PROJECT_ID, items: [CATALOG_SUBJECT] }),
      });
      return;
    }

    if (method === "GET" && url.endsWith(`/subjects/${SUBJECT_ID}/review-episodes`)) {
      log.push({ url, method, form, body: null });
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ subject_id: SUBJECT_ID, items: [CATALOG_EPISODE] }),
      });
      return;
    }

    const commitMatch = url.match(/\/evidence-upload-previews\/([^/]+)\/commit$/);
    if (method === "POST" && commitMatch !== null) {
      const raw = request.postData();
      if (raw !== null && raw.length > 0) {
        try {
          body = JSON.parse(raw) as Record<string, unknown>;
        } catch {
          body = null;
        }
      }
      createdMode = body?.upload_mode === "full" ? "full" : "incremental";
      log.push({ url, method, form, body });
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify(syntheticCommit(createdMode)),
      });
      return;
    }

    const cancelMatch = url.match(/\/evidence-upload-previews\/([^/]+)$/);
    if (method === "DELETE" && cancelMatch !== null) {
      if (options.failCancel === true) {
        log.push({ url, method, form, body: null });
        await route.fulfill({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({
            error: {
              code: "PREVIEW_CLEANUP_FAILED",
              title: "取消清理未完成",
              detail: "预览已记录取消，但临时文件清理尚未完成。",
              recovery_action:
                "请重试取消以完成清理；系统不会使用该预览进行确认。",
            },
          }),
        });
        return;
      }
      const preview = syntheticPreview({ mode: "incremental" });
      preview.status = "cancelled";
      preview.status_label = "已取消";
      log.push({ url, method, form, body: null });
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(preview),
      });
      return;
    }

    if (method === "GET" && url.includes("/evidence-snapshots")) {
      log.push({ url, method, form, body: null });
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(syntheticSnapshotList(options.activeReview === true)),
      });
      return;
    }

    if (method === "GET" && url.endsWith(`/jobs/${JOB_ID}/evidence-progress`)) {
      log.push({ url, method, form, body: null });
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          job_id: JOB_ID,
          job_state: "failed_final",
          job_state_label: "未完成，需要处理",
          total_pages: 5,
          completed_pages: 4,
          failed_pages: 1,
          pending_pages: 0,
          scope_note: "当前进度仅覆盖需要文字识别的页面；无需识别的文本资料页在此阶段不单独枚举。",
          files: [{
            source_document_version_id: "version-e2e-report",
            file_name: "检查报告.pdf",
            page_total: 5,
            page_succeeded: 4,
            page_failed: 1,
            status: "partial",
            status_label: "部分完成",
          }],
        }),
      });
      return;
    }

    if (method === "GET" && url.endsWith(`/jobs/${JOB_ID}`)) {
      log.push({ url, method, form, body: null });
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          job_id: JOB_ID,
          job_type: "evidence_processing",
          state: "failed_final",
          state_label: "未完成，需要处理",
          cancel_requested: false,
          progress_completed: 1,
          progress_total: 1,
          error_code: null,
          error_classification: null,
          retryable_scope: [],
          recovery_action: "可以点击“重新处理失败部分”；已完成内容不会重复处理。",
          created_at: "2026-08-21T08:00:00Z",
          updated_at: "2026-08-21T08:05:00Z",
          last_event_seq: 2,
          steps: [{
            step_id: "evidence_processing",
            name: "evidence_processing",
            state: "failed_final",
            state_label: "未完成，需要处理",
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
            job_event_id: "event-e2e-completed",
            event_type: "failed",
            event_type_label: "本次处理未完成",
            step_id: null,
            occurred_at: "2026-08-21T08:05:00Z",
            attempt: 1,
            checkpoint_id: null,
            retryable: false,
            progress_completed: 1,
            progress_total: 1,
            payload: {},
          }],
        }),
      });
      return;
    }

    if (
      method === "GET" &&
      /\/evidence-processing-revisions\/[^/]+\/pages\/entry-e2e-1\/image$/.test(url)
    ) {
      log.push({ url, method, form, body: null });
      await route.fulfill({
        status: 200,
        contentType: "image/svg+xml",
        body: `
          <svg xmlns="http://www.w3.org/2000/svg" width="1240" height="1754" viewBox="0 0 1240 1754">
            <rect width="1240" height="1754" fill="#fff"/>
            <text x="620" y="120" text-anchor="middle" font-size="42" font-weight="700" fill="#1f2933">筛选期病历记录</text>
            <line x1="100" y1="170" x2="1140" y2="170" stroke="#aeb5bb" stroke-width="2"/>
            <text x="110" y="250" font-size="28" fill="#58636d">受试者编号：UAT-01</text>
            <text x="700" y="250" font-size="28" fill="#58636d">访视：筛选期</text>
            <text x="110" y="365" font-size="32" font-weight="700" fill="#1f2933">现病史</text>
            <text x="130" y="495" font-size="36" fill="#1f2933">患者否认近期发热，ALT 39 U/L。</text>
            <text x="110" y="660" font-size="32" font-weight="700" fill="#1f2933">既往史与用药</text>
            <text x="130" y="750" font-size="30" fill="#1f2933">近期未使用方案限制的全身治疗药物。</text>
            <text x="130" y="830" font-size="30" fill="#1f2933">相关时间窗仍需结合基线日期继续核对。</text>
            <line x1="100" y1="1510" x2="1140" y2="1510" stroke="#d7dbde"/>
            <text x="110" y="1580" font-size="24" fill="#737d85">合成测试资料，仅用于验证原件定位与界面联动</text>
          </svg>`,
      });
      return;
    }

    const selectiveVisionMatch = url.match(
      /\/evidence-processing-revisions\/([^/]+)\/selective-vision-task(?:\/(retry|cancel))?$/,
    );
    if (selectiveVisionMatch !== null) {
      const revisionId = decodeURIComponent(selectiveVisionMatch[1] ?? "");
      const action = selectiveVisionMatch[2] ?? null;
      log.push({ url, method, form, body: null });

      if (method === "POST" && action !== null) {
        selectiveVisionState = action === "retry" ? "queued" : "cancelled";
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            job_id: "job-selective-vision-e2e",
            state: selectiveVisionState,
            state_label: action === "retry" ? "等待处理" : "已停止",
            changed: true,
          }),
        });
        return;
      }

      if (method === "GET") {
        const found = selectiveVisionState !== null;
        const waiting = selectiveVisionState === "queued";
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            evidence_processing_revision_id: revisionId,
            found,
            job_id: found ? "job-selective-vision-e2e" : null,
            state: selectiveVisionState,
            state_label: !found
              ? "尚无页面视觉核验任务"
              : waiting
                ? "等待处理"
                : selectiveVisionState === "cancelled"
                  ? "已停止"
                  : "未完成，需要处理",
            cancel_requested: false,
            progress_completed: found && !waiting ? 1 : 0,
            progress_total: found ? 3 : 0,
            recovery_action: !found
              ? "重新处理资料后会自动建立。"
              : waiting
                ? "系统只会核验存在识别风险的页面，已确认的识别结果不会重复处理。"
                : "请重新开始未完成的页面核验，已保存的识别结果不受影响。",
            can_retry: selectiveVisionState === "failed_final",
            can_cancel: waiting,
            eligible_page_count: found ? 3 : null,
            skipped_page_count: found ? 7 : null,
            observation_page_count: found ? 1 : null,
            closed_page_count: selectiveVisionState === "failed_final" ? 2 : 0,
            closed_reason_label:
              selectiveVisionState === "failed_final" ? "部分页面暂时无法核验" : null,
            failed_scope_label:
              selectiveVisionState === "failed_final" ? "筛选期病历第 1页、检查报告第 2 页" : null,
            created_at: found ? "2026-09-01T01:00:00Z" : null,
            updated_at: found ? "2026-09-01T01:01:00Z" : null,
          }),
        });
        return;
      }
    }

    if (method === "GET" && url.includes("/evidence-processing-revisions/")) {
      log.push({ url, method, form, body: null });
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(syntheticProcessingRevision()),
      });
      return;
    }

    if (method === "GET" && url.includes("/ocr-pages/")) {
      log.push({ url, method, form, body: null });
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(syntheticOcrPage()),
      });
      return;
    }

    if (method === "POST" && /\/ocr-pages\/[^/]+\/corrections$/.test(url)) {
      const raw = request.postData();
      body = raw === null ? null : JSON.parse(raw) as Record<string, unknown>;
      log.push({ url, method, form, body });
      if (options.correctionConflict === true) {
        await route.fulfill({
          status: 409,
          contentType: "application/json",
          body: JSON.stringify({
            error: {
              code: "STALE_REVISION",
              title: "资料已发生变化",
              detail: "当前审核节点已有更新，请核对差异。",
              recovery_action: "请确认系统当前记录后再决定是否提交。",
              context: {
                submitted: body ?? {},
                current_record: { revision: 2, corrected_text: "患者否认近期发热" },
                field_diff: {
                  corrected_text: {
                    submitted: body?.corrected_text ?? null,
                    current: "患者否认近期发热",
                  },
                },
              },
            },
          }),
        });
        return;
      }
    }

    if (method === "POST" && /\/referenced-documents\/[^/]+\/confirm$/.test(url)) {
      const raw = request.postData();
      body = raw === null ? null : JSON.parse(raw) as Record<string, unknown>;
      referencedStatus = "confirmed";
      log.push({ url, method, form, body });
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(syntheticReferencedDocument("confirmed")),
      });
      return;
    }

    if (method === "POST" && /\/referenced-documents\/[^/]+\/resolve$/.test(url)) {
      const raw = request.postData();
      body = raw === null ? null : JSON.parse(raw) as Record<string, unknown>;
      referencedProvided = true;
      log.push({ url, method, form, body });
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          resolution_revision_id: "resolution-e2e-1",
          status: "provided",
          status_label: "已提供",
          source_document_version_id: "version-e2e-active",
          revision: 1,
          created_by: "本地用户",
          created_at: "2026-08-21T08:10:00Z",
        }),
      });
      return;
    }

    if (method === "DELETE" && /\/referenced-documents\/[^/]+\/resolution/.test(url)) {
      referencedProvided = false;
      log.push({ url, method, form, body: null });
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          resolution_revision_id: "resolution-e2e-2",
          status: "unresolved",
          status_label: "未提供",
          source_document_version_id: null,
          revision: 2,
          created_by: "本地用户",
          created_at: "2026-08-21T08:12:00Z",
        }),
      });
      return;
    }

    if (method === "GET" && url.includes("/referenced-documents")) {
      log.push({ url, method, form, body: null });
      const list = syntheticReferencedDocumentList(options.activeReview === true);
      if (options.activeReview === true) {
        const item = syntheticReferencedDocument(referencedStatus);
        item.resolution = referencedProvided ? {
          resolution_revision_id: "resolution-e2e-1",
          status: "provided",
          status_label: "已提供",
          source_document_version_id: "version-e2e-active",
          revision: 1,
          created_by: "本地用户",
          created_at: "2026-08-21T08:10:00Z",
        } : null;
        list.items = [item];
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(list),
      });
      return;
    }

    await route.fulfill({
      status: 404,
      contentType: "application/json",
      body: JSON.stringify({
        error: {
          code: "NOT_FOUND",
          title: "记录不存在",
          detail: `e2e 未覆盖的接口路径：${method} ${new URL(url).pathname}`,
          recovery_action: "请检查地址。",
        },
      }),
    });
  });

  return log;
}

/** e2e 合成文件载荷（干净 V2 数据）。 */
export const E2E_FILES = [
  { name: "检查报告.pdf", mimeType: "application/pdf", buffer: Buffer.from("pdf") },
  { name: "血常规报告.png", mimeType: "image/png", buffer: Buffer.from("png") },
  {
    name: "知情同意书.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("icf"),
  },
  {
    name: "入院记录.docx",
    mimeType:
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    buffer: Buffer.from("docx"),
  },
  { name: "出院小结.zip", mimeType: "application/zip", buffer: Buffer.from("zip") },
  { name: "既往病历.pdf", mimeType: "application/pdf", buffer: Buffer.from("history") },
] as const;

export const SELECTED_FILES = E2E_FILES.slice(0, 5);
