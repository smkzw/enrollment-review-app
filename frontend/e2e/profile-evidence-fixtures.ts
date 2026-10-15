/**
 * Phase 5.6 Profile 证据面板 e2e 共享合成 V2 数据与路由拦截（worker_03）。
 * 只使用干净合成 V2 数据；拦截 /api/v2/** 使构建产物在真实浏览器中
 * 走完整解码/渲染路径，不依赖本机 V2 服务或真实临床资料。
 */

import type { Page } from "@playwright/test";
import { makeRevision } from "../src/api/patient-profile/patientProfileFixtures.ts";

export const PROJECT_ID = "project-synthetic-phase-iii";
export const SUBJECT_ID = "subject-uat-01-clear";
export const EPISODE_ID = "episode-uat-01-screening-clear";

export const PROFILE_HASH = `#/subjects?project=${PROJECT_ID}&subject=${SUBJECT_ID}&episode=${EPISODE_ID}`;

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

const PROCESSING_PAGES = [
  {
    entry_id: "entry-page-1",
    position: 1,
    source_document_version_id: "version-1",
    page_number: 1,
    original_frame: "frame-1",
    page_artifact_id: "page-artifact-1",
    ocr_page_id: "ocr-page-1",
    status: "succeeded",
    status_label: "页面已就绪",
    failure_reason: null,
    image_available: true,
    page_width: 1240,
    page_height: 1754,
  },
  {
    entry_id: "entry-page-2",
    position: 2,
    source_document_version_id: "version-2",
    page_number: 2,
    original_frame: null,
    page_artifact_id: "page-artifact-2",
    ocr_page_id: null,
    status: "failed",
    status_label: "页面处理失败",
    failure_reason: "原始页面读取失败，请在后续恢复处理中重试。",
    image_available: false,
    page_width: null,
    page_height: null,
  },
];

/** 注册 /api/v2/** 路由拦截：目录、Profile、处理修订、快照、页图。 */
export async function registerProfileRoutes(page: Page): Promise<void> {
  await page.route("**/api/v2/**", async (route) => {
    const request = route.request();
    const url = request.url();
    const method = request.method();

    if (method === "GET" && url.endsWith("/protocol/projects")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ projects: [CATALOG_PROJECT] }),
      });
      return;
    }
    if (method === "GET" && url.endsWith(`/projects/${PROJECT_ID}/subjects`)) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ project_id: PROJECT_ID, items: [CATALOG_SUBJECT] }),
      });
      return;
    }
    if (method === "GET" && url.endsWith(`/subjects/${SUBJECT_ID}/review-episodes`)) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ subject_id: SUBJECT_ID, items: [CATALOG_EPISODE] }),
      });
      return;
    }
    // 受试者 Patient Profile：用契约测试专属 fixture 构建可通过严格解码的 wire。
    if (
      method === "GET" &&
      url.includes(
        `/subjects/${SUBJECT_ID}/review-episodes/${EPISODE_ID}/patient-profile`,
      )
    ) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(makeRevision()),
      });
      return;
    }
    if (
      method === "GET" &&
      url.endsWith(
        `/subjects/${SUBJECT_ID}/review-episodes/${EPISODE_ID}/fact-corrections`,
      )
    ) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          subject_id: SUBJECT_ID,
          review_episode_id: EPISODE_ID,
          items: [],
        }),
      });
      return;
    }
    if (
      method === "GET" &&
      /\/evidence-processing-revisions\/[^/]+$/.test(new URL(url).pathname)
    ) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          evidence_processing_revision_id: "processing-e2e-active",
          revision_kind: "complete",
          revision_kind_label: "完整处理版本",
          evidence_snapshot_id: "snapshot-e2e-active",
          base_processing_revision_id: null,
          project_id: PROJECT_ID,
          subject_id: SUBJECT_ID,
          review_episode_id: EPISODE_ID,
          status: "active",
          status_label: "当前有效",
          is_activatable: false,
          is_current: true,
          manifest_sha256: "a".repeat(64),
          completion_manifest_sha256: "b".repeat(64),
          pages: PROCESSING_PAGES,
          locator_ids: ["loc-bp-1", "loc-page-1"],
          risk_scan_ids: [],
          risk_review_ids: [],
          risk_flag_count: 0,
          pending_risk_flag_count: 0,
          correction_ids: [],
          metadata_revision_ids: [],
          referenced_document_revision_ids: [],
          resolution_revision_ids: [],
          gates: [],
          created_at: "2026-08-22T08:00:00Z",
          created_by: "本地用户",
        }),
      });
      return;
    }
    if (method === "GET" && url.includes("/evidence-snapshots")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          evidence_snapshot_id: "snapshot-e2e-active",
          project_id: PROJECT_ID,
          subject_id: SUBJECT_ID,
          review_episode_id: EPISODE_ID,
          upload_mode: "full",
          upload_mode_label: "建立完整资料快照",
          prior_snapshot_id: null,
          comparison_snapshot_id: null,
          status: "active",
          status_label: "当前有效",
          is_current: true,
          base_processing_revision_id: null,
          upload_job_id: null,
          members: [
            {
              member_id: "member-1",
              snapshot_id: "snapshot-e2e-active",
              logical_document_id: "logical-1",
              source_document_version_id: "version-1",
              file_name: "筛选病历.pdf",
              media_type: "application/pdf",
              version_number: 1,
              origin: "added",
              origin_label: "本次新增",
              metadata_head: {
                metadata_revision_id: "metadata-1",
                source_document_version_id: "version-1",
                document_type: "筛选病历",
                source_party: "研究中心",
                reason: "系统根据文件名提出建议。",
                is_auto_suggestion: true,
                supersedes_metadata_revision_id: null,
                revision: 1,
                created_at: "2026-08-22T08:00:00Z",
                created_by: "本地用户",
              },
            },
          ],
          collection_sha256: "c".repeat(64),
          created_at: "2026-08-22T08:00:00Z",
          created_by: "本地用户",
        }),
      });
      return;
    }
    if (
      method === "GET" &&
      /\/evidence-processing-revisions\/[^/]+\/pages\/entry-page-1\/image$/.test(url)
    ) {
      await route.fulfill({
        status: 200,
        contentType: "image/svg+xml",
        body: `
          <svg xmlns="http://www.w3.org/2000/svg" width="1240" height="1754" viewBox="0 0 1240 1754">
            <rect width="1240" height="1754" fill="#fff"/>
            <text x="620" y="120" text-anchor="middle" font-size="42" font-weight="700" fill="#1f2933">筛选期病历记录</text>
            <text x="110" y="365" font-size="32" font-weight="700" fill="#1f2933">现病史</text>
            <text x="130" y="495" font-size="36" fill="#1f2933">基线血压 120/80 mmHg</text>
            <text x="130" y="690" font-size="36" fill="#1f2933">体温 38.2°C，伴发热</text>
            <line x1="100" y1="1510" x2="1140" y2="1510" stroke="#d7dbde"/>
            <text x="110" y="1580" font-size="24" fill="#737d85">合成测试资料，仅用于验证原件定位与界面联动</text>
          </svg>`,
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
          detail: `profile-evidence e2e 未覆盖的接口路径：${method} ${new URL(url).pathname}`,
          recovery_action: "请检查地址。",
        },
      }),
    });
  });
}
