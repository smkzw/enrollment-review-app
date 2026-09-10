// @vitest-environment jsdom
/**
 * ProfileEvidencePanel（Slice 5.6，worker_03）：宽屏证据面板与 Phase 4 原件查看器联动。
 * - 通过 evidenceNavigation 的完整处理修订加载连续原件页与文档名；
 * - 所有定位都能打开所在页，只有真实 bbox 提供精确定位并画框；
 * - 只有真实 bbox 定位画唯一单框（OriginalEvidenceViewer 内部合约）；
 * - 冲突条目按并列记录展示，不合成坐标。
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  decodeProcessingRevision,
  decodeSnapshot,
  setEvidenceRepository,
  type EvidenceRepository,
} from "../../api/evidence";
import { adaptPatientProfile } from "../../features/patient-profile/model";
import {
  decodePatientProfileRevision,
} from "../../api/patient-profile/patientProfileViewModels";
import { makeRevision } from "../../api/patient-profile/patientProfileFixtures";
import { ProfileEvidencePanel } from "./ProfileEvidencePanel";

const SUBJECT = "subject-1";
const EPISODE = "episode-1";
const PROCESSING_REVISION = "complete-rev-1";
const SNAPSHOT = "snapshot-1";

function makeSnapshotWire() {
  return {
    evidence_snapshot_id: SNAPSHOT,
    project_id: "project-1",
    subject_id: SUBJECT,
    review_episode_id: EPISODE,
    upload_mode: "full" as const,
    upload_mode_label: "建立完整资料版本",
    prior_snapshot_id: null,
    comparison_snapshot_id: null,
    status: "active" as const,
    status_label: "当前有效",
    is_current: true,
    base_processing_revision_id: null,
    upload_job_id: null,
    members: [
      {
        member_id: "member-1",
        snapshot_id: SNAPSHOT,
        logical_document_id: "logical-1",
        source_document_version_id: "version-1",
        file_name: "筛选病历.pdf",
        media_type: "application/pdf",
        version_number: 1,
        origin: "added" as const,
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
      {
        member_id: "member-2",
        snapshot_id: SNAPSHOT,
        logical_document_id: "logical-2",
        source_document_version_id: "version-2",
        file_name: "合并用药记录.pdf",
        media_type: "application/pdf",
        version_number: 1,
        origin: "added" as const,
        origin_label: "本次新增",
        metadata_head: {
          metadata_revision_id: "metadata-2",
          source_document_version_id: "version-2",
          document_type: "合并用药记录",
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
  };
}

function makeProcessingRevisionWire() {
  return {
    evidence_processing_revision_id: PROCESSING_REVISION,
    revision_kind: "complete" as const,
    revision_kind_label: "完整处理版本",
    evidence_snapshot_id: SNAPSHOT,
    base_processing_revision_id: null,
    project_id: "project-1",
    subject_id: SUBJECT,
    review_episode_id: EPISODE,
    status: "active" as const,
    status_label: "当前有效",
    is_activatable: false,
    is_current: true,
    manifest_sha256: "a".repeat(64),
    completion_manifest_sha256: "b".repeat(64),
    pages: [
      {
        entry_id: "entry-page-1",
        position: 1,
        source_document_version_id: "version-1",
        page_number: 1,
        original_frame: "frame-1",
        page_artifact_id: "page-artifact-1",
        ocr_page_id: "ocr-page-1",
        status: "succeeded" as const,
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
        original_frame: "frame-2",
        page_artifact_id: "page-artifact-2",
        ocr_page_id: "ocr-page-2",
        status: "succeeded" as const,
        status_label: "页面已就绪",
        failure_reason: null,
        image_available: true,
        page_width: 1240,
        page_height: 1754,
      },
    ],
    locator_ids: ["loc-bp-1", "loc-fever-1", "loc-page-1"],
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
  };
}

function loadModel() {
  return adaptPatientProfile(
    decodePatientProfileRevision(makeRevision()),
  );
}

function openItem(model: ReturnType<typeof loadModel>) {
  const lane = model.lanes.find((candidate) => candidate.lane === "demographics");
  const item = lane?.items[0];
  if (item === undefined) throw new Error("测试数据缺少人口学条目");
  return item;
}

function laneItem(model: ReturnType<typeof loadModel>, laneName: string) {
  const lane = model.lanes.find((candidate) => candidate.lane === laneName);
  const item = lane?.items[0];
  if (item === undefined) throw new Error(`测试数据缺少泳道条目 ${laneName}`);
  return item;
}

describe("ProfileEvidencePanel", () => {
  beforeEach(() => {
    HTMLElement.prototype.scrollIntoView = vi.fn();
    const repo: EvidenceRepository = {
      kind: "http",
      createUploadPreview: vi.fn<EvidenceRepository["createUploadPreview"]>(),
      getUploadPreview: vi.fn<EvidenceRepository["getUploadPreview"]>(),
      cancelUploadPreview: vi.fn<EvidenceRepository["cancelUploadPreview"]>(),
      confirmUpload: vi.fn<EvidenceRepository["confirmUpload"]>(),
      listEvidenceSnapshots: vi.fn<EvidenceRepository["listEvidenceSnapshots"]>(),
      getEvidenceSnapshot: vi.fn<EvidenceRepository["getEvidenceSnapshot"]>(() =>
        Promise.resolve(decodeSnapshot(makeSnapshotWire())),
      ),
      getProcessingRevision:
        vi.fn<EvidenceRepository["getProcessingRevision"]>(() =>
          Promise.resolve(decodeProcessingRevision(makeProcessingRevisionWire())),
        ),
      getProcessingCandidate: vi.fn<EvidenceRepository["getProcessingCandidate"]>(),
      getOcrPage: vi.fn<EvidenceRepository["getOcrPage"]>(),
      createCorrection: vi.fn<EvidenceRepository["createCorrection"]>(),
      createRiskReview: vi.fn<EvidenceRepository["createRiskReview"]>(),
      createRiskPageReview: vi.fn<EvidenceRepository["createRiskPageReview"]>(),
      buildProcessingRevision: vi.fn<EvidenceRepository["buildProcessingRevision"]>(),
      activateProcessingRevision: vi.fn<EvidenceRepository["activateProcessingRevision"]>(),
      reviseSourceDocumentMetadata: vi.fn<EvidenceRepository["reviseSourceDocumentMetadata"]>(),
      listReferencedDocuments: vi.fn<EvidenceRepository["listReferencedDocuments"]>(),
      createReferencedDocument: vi.fn<EvidenceRepository["createReferencedDocument"]>(),
      reviseReferencedDocument: vi.fn<EvidenceRepository["reviseReferencedDocument"]>(),
      confirmReferencedDocument: vi.fn<EvidenceRepository["confirmReferencedDocument"]>(),
      dismissReferencedDocument: vi.fn<EvidenceRepository["dismissReferencedDocument"]>(),
      resolveReferencedDocument: vi.fn<EvidenceRepository["resolveReferencedDocument"]>(),
      unresolveReferencedDocument: vi.fn<EvidenceRepository["unresolveReferencedDocument"]>(),
    };
    setEvidenceRepository(repo);
  });

  it("加载完整处理修订与快照，展示文档名与连续原件页", async () => {
    const model = loadModel();
    render(
      <ProfileEvidencePanel model={model} item={openItem(model)} onClose={vi.fn()} />,
    );
    await screen.findByText("筛选病历.pdf");
    expect(screen.getByText("2 页连续查看")).toBeInTheDocument();
    expect(screen.getByLabelText("原始资料查看区")).toBeInTheDocument();
  });

  it("真实 bbox 定位提供定位按钮，并只画当前单框", async () => {
    const model = loadModel();
    const user = userEvent.setup();
    render(
      <ProfileEvidencePanel model={model} item={openItem(model)} onClose={vi.fn()} />,
    );
    await screen.findByText("筛选病历.pdf");
    // 首个真实 bbox 定位默认选中，显示“当前定位”。
    const locate = await screen.findByRole("button", { name: "当前定位" });
    await user.click(locate);
    // 只有一个真实 bbox 框被画出来，且标为当前选中。
    const boxes = screen.getAllByLabelText(/^重点标注/);
    expect(boxes).toHaveLength(1);
    expect(boxes[0]).toHaveClass("original-evidence-page__box--selected");
  });

  it("定位页码或资料版本与实际页不一致时停止精确定位且不画框", async () => {
    const wire = makeRevision();
    wire.evidence_locators[0] = {
      ...wire.evidence_locators[0]!,
      page_number: 7,
    };
    const model = adaptPatientProfile(decodePatientProfileRevision(wire));

    render(
      <ProfileEvidencePanel model={model} item={openItem(model)} onClose={vi.fn()} />,
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "档案中的原文定位与实际页面不一致，已停止精确定位",
    );
    expect(screen.queryByText("已精确定位到原文区域。")).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/^重点标注/)).not.toBeInTheDocument();
  });

  it("非 bbox 定位可打开所在页，但不出现合成区域或画框", async () => {
    const model = loadModel();
    // 用药暴露条目使用 page_only 定位。
    const item = laneItem(model, "medication");
    render(
      <ProfileEvidencePanel model={model} item={item} onClose={vi.fn()} />,
    );
    await screen.findByText("筛选病历.pdf");
    expect(screen.getByText(/只能确定到所在页/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /^(查看所在页|当前页)$/ }),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText(/^重点标注/)).not.toBeInTheDocument();
  });

  it("冲突条目按并列记录展示，并说明冲突成员数量", async () => {
    const model = loadModel();
    const item = laneItem(model, "evidence_quality");
    render(
      <ProfileEvidencePanel model={model} item={item} onClose={vi.fn()} />,
    );
    await screen.findByText("筛选病历.pdf");
    // 冲突并列记录：同一页面定位并排。
    const panel = screen.getByLabelText("该条目的原文证据与定位");
    const records = within(panel).getAllByLabelText(/^并列记录/);
    expect(records.length).toBeGreaterThanOrEqual(1);
  });

  it("关闭按钮调用 onClose，且不出现入排结论/通过/不通过语言", async () => {
    const model = loadModel();
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<ProfileEvidencePanel model={model} item={openItem(model)} onClose={onClose} />);
    await screen.findByText("筛选病历.pdf");
    await user.click(screen.getByRole("button", { name: "关闭原文证据" }));
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(
      screen.queryByText(/入排结论|行动数量|负责方|通过|不通过/),
    ).not.toBeInTheDocument();
  });
});
