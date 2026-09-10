// @vitest-environment jsdom

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  setEvidenceRepository,
  type EvidenceRepository,
  type EvidenceSnapshotView,
} from "../../api/evidence";
import {
  decodePatientProfileRevision,
  setPatientProfileRepository,
  type FactCorrectionJobStatusView,
  type FactCorrectionPreviewView,
  type PatientProfileRepository,
} from "../../api/patient-profile";
import { makeRevision } from "../../api/patient-profile/patientProfileFixtures";
import { adaptPatientProfile } from "../../features/patient-profile/model";
import {
  ProfileFactCorrectionDialog,
  type ProfileFactCorrectionCompleted,
} from "./ProfileFactCorrectionDialog";

const SUBJECT = "subject-1";
const EPISODE = "episode-1";

const evidenceSnapshot: EvidenceSnapshotView = {
  evidenceSnapshotId: "snapshot-1",
  projectId: "project-1",
  subjectId: SUBJECT,
  reviewEpisodeId: EPISODE,
  uploadMode: "full",
  uploadModeLabel: "建立完整资料版本",
  priorSnapshotId: null,
  comparisonSnapshotId: null,
  status: "active",
  statusLabel: "当前有效",
  isCurrent: true,
  baseProcessingRevisionId: null,
  uploadJobId: null,
  latestProcessingCandidate: null,
  members: [],
  collectionSha256: "a".repeat(64),
  createdAt: "2026-08-23T08:00:00Z",
};

function makeEvidenceRepo(): EvidenceRepository {
  return {
    kind: "http",
    createUploadPreview: vi.fn<EvidenceRepository["createUploadPreview"]>(),
    getUploadPreview: vi.fn<EvidenceRepository["getUploadPreview"]>(),
    cancelUploadPreview: vi.fn<EvidenceRepository["cancelUploadPreview"]>(),
    confirmUpload: vi.fn<EvidenceRepository["confirmUpload"]>(),
    listEvidenceSnapshots: vi.fn<EvidenceRepository["listEvidenceSnapshots"]>(),
    getEvidenceSnapshot: vi.fn<EvidenceRepository["getEvidenceSnapshot"]>(() =>
      Promise.resolve(evidenceSnapshot),
    ),
    reviseSourceDocumentMetadata: vi.fn<EvidenceRepository["reviseSourceDocumentMetadata"]>(),
    getProcessingRevision: vi.fn<EvidenceRepository["getProcessingRevision"]>(),
    getProcessingCandidate: vi.fn<EvidenceRepository["getProcessingCandidate"]>(),
    getOcrPage: vi.fn<EvidenceRepository["getOcrPage"]>(),
    createCorrection: vi.fn<EvidenceRepository["createCorrection"]>(),
    createRiskReview: vi.fn<EvidenceRepository["createRiskReview"]>(),
    createRiskPageReview: vi.fn<EvidenceRepository["createRiskPageReview"]>(),
    buildProcessingRevision: vi.fn<EvidenceRepository["buildProcessingRevision"]>(),
    activateProcessingRevision: vi.fn<EvidenceRepository["activateProcessingRevision"]>(),
    listReferencedDocuments: vi.fn<EvidenceRepository["listReferencedDocuments"]>(),
    createReferencedDocument: vi.fn<EvidenceRepository["createReferencedDocument"]>(),
    reviseReferencedDocument: vi.fn<EvidenceRepository["reviseReferencedDocument"]>(),
    confirmReferencedDocument: vi.fn<EvidenceRepository["confirmReferencedDocument"]>(),
    dismissReferencedDocument: vi.fn<EvidenceRepository["dismissReferencedDocument"]>(),
    resolveReferencedDocument: vi.fn<EvidenceRepository["resolveReferencedDocument"]>(),
    unresolveReferencedDocument: vi.fn<EvidenceRepository["unresolveReferencedDocument"]>(),
  };
}

function makePreview(): FactCorrectionPreviewView {
  return {
    targetKind: "fact",
    targetKindLabel: "事实",
    targetId: "fact-demographics-1",
    locatorIds: ["loc-bp-1"],
    oldSnapshot: {
      kind: "fact",
      asserted_object: "血压",
      value: "120/80",
      unit: "mmHg",
    },
    newSnapshot: {
      kind: "fact",
      asserted_object: "血压",
      value: "130/85",
      unit: "mmHg",
    },
    impact: {
      scopeKind: "node",
      scopeKindLabel: "审核节点全部事实",
      fallbackReason: "将重新整理本审核节点全部事实",
      affectedLocatorIds: ["loc-bp-1"],
      affectedDocumentIds: ["doc-1"],
      affectedFactIds: ["fact-demographics-1"],
      affectedEventIds: [],
      affectedExposureIds: [],
      affectedConflictGroupIds: ["conflict-1"],
      affectedRuleLinkIds: ["rule-1"],
      affectedExpectationIds: [],
      affectedProfileRevisionIds: ["profile-revision-1"],
    },
  };
}

function completedStatus(): FactCorrectionJobStatusView {
  return {
    jobId: "job-1",
    state: "completed",
    stateLabel: "已完成",
    cancelRequested: false,
    progressCompleted: 2,
    progressTotal: 2,
    errorCode: null,
    errorClassification: null,
    retryableScope: [],
    recoveryAction: "",
    createdAt: "2026-08-23T08:00:00Z",
    updatedAt: "2026-08-23T08:01:00Z",
    lastEventSeq: 2,
  };
}

function queuedStatus(): FactCorrectionJobStatusView {
  return {
    ...completedStatus(),
    state: "queued",
    stateLabel: "等待处理",
    progressCompleted: 0,
    progressTotal: 2,
    updatedAt: "2026-08-23T08:00:00Z",
    lastEventSeq: 1,
  };
}

function makeRepo(
  status: FactCorrectionJobStatusView = completedStatus(),
): {
  repo: PatientProfileRepository;
  preview: ReturnType<typeof vi.fn>;
  submit: ReturnType<typeof vi.fn>;
} {
  const preview = vi.fn(() => Promise.resolve(makePreview()));
  const submit = vi.fn(() =>
    Promise.resolve({
      jobId: "job-1",
      correctionId: "correction-1",
      created: true,
      state: "queued" as const,
      stateLabel: "等待处理",
      recoveryAction: "请等待处理完成。",
    }),
  );
  const repo: PatientProfileRepository = {
    kind: "http",
    getLatestPatientProfile: vi.fn(() =>
      Promise.resolve(
        decodePatientProfileRevision(
          makeRevision({ patient_profile_revision_id: "profile-revision-2" }),
        ),
      ),
    ),
    listPatientProfileHistory: vi.fn(),
    getPatientProfileRevision: vi.fn(),
    previewFactCorrection: preview,
    submitFactCorrection: submit,
    listFactCorrectionHistory: vi.fn(() =>
      Promise.resolve({ subjectId: SUBJECT, reviewEpisodeId: EPISODE, items: [] }),
    ),
    getFactCorrectionJobStatus: vi.fn(() => Promise.resolve(status)),
    cancelFactCorrectionJob: vi.fn(),
    retryFactCorrectionJob: vi.fn(),
  };
  return { repo, preview, submit };
}

function renderDialog(
  repo: PatientProfileRepository,
  onCompleted = vi.fn(),
  onClose = vi.fn(),
) {
  const model = adaptPatientProfile(decodePatientProfileRevision(makeRevision()));
  const lane = model.lanes.find((candidate) => candidate.lane === "demographics");
  const item = lane?.items[0];
  if (item === undefined) throw new Error("测试数据缺少事实条目");
  setPatientProfileRepository(repo);
  render(
    <ProfileFactCorrectionDialog
      model={model}
      item={item}
      targetKind="fact"
      subjectId={SUBJECT}
      reviewEpisodeId={EPISODE}
      onClose={onClose}
      onCompleted={onCompleted}
    />,
  );
  return { item, model };
}

describe("ProfileFactCorrectionDialog", () => {
  beforeEach(() => {
    setEvidenceRepository(makeEvidenceRepo());
  });

  afterEach(() => {
    setEvidenceRepository(null);
    setPatientProfileRepository(null);
  });

  it("requires a reason and keeps preview read-only until explicit confirmation", async () => {
    const user = userEvent.setup();
    const { repo, preview, submit } = makeRepo();
    renderDialog(repo);

    await user.click(screen.getByRole("button", { name: "预览影响范围" }));
    expect(screen.getByText("请先填写本次修订理由，再预览影响范围。")).toBeInTheDocument();
    expect(preview).not.toHaveBeenCalled();

    await user.type(screen.getByRole("textbox", { name: "修订理由（必填）" }), "原始报告与当前记录不一致。");
    await user.click(screen.getByRole("button", { name: "预览影响范围" }));
    expect(await screen.findByText("修改前")).toBeInTheDocument();
    expect(screen.getByText("拟修改")).toBeInTheDocument();
    expect(screen.getByText("将重新整理本审核节点全部事实。既有档案版本保持不变，完成后只会生成新的当前档案版本。", { exact: true })).toBeInTheDocument();
    expect(screen.getByText("受影响历史档案")).toBeInTheDocument();
    expect(screen.getByText("冲突组")).toBeInTheDocument();
    expect(screen.getByText("冲突组").closest("div")).toHaveTextContent("1");
    expect(submit).not.toHaveBeenCalled();

    await user.click(screen.getByRole("checkbox", { name: /我已核对/ }));
    expect(screen.getByRole("button", { name: "提交修订" })).toBeEnabled();
  });

  it("reports completion only after the persistent status is completed", async () => {
    const user = userEvent.setup();
    const completed = vi.fn<(result: ProfileFactCorrectionCompleted) => void>();
    const { repo } = makeRepo();
    renderDialog(repo, completed);

    await user.type(screen.getByRole("textbox", { name: "修订理由（必填）" }), "原始报告与当前记录不一致。");
    await user.click(screen.getByRole("button", { name: "预览影响范围" }));
    await screen.findByText("拟修改");
    await user.click(screen.getByRole("checkbox", { name: /我已核对/ }));
    await user.click(screen.getByRole("button", { name: "提交修订" }));

    await waitFor(() => expect(completed).toHaveBeenCalledTimes(1));
    expect(completed).toHaveBeenCalledWith({
      correctionId: "correction-1",
      jobId: "job-1",
    });
    expect(repo.getLatestPatientProfile).not.toHaveBeenCalled();
    expect(screen.getByText("修订已完成，档案和修订记录正在刷新。")).toBeInTheDocument();
  });

  it("keeps the workspace mounted while the persistent task is active", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const { repo } = makeRepo(queuedStatus());
    renderDialog(repo, vi.fn(), onClose);

    await user.type(screen.getByRole("textbox", { name: "修订理由（必填）" }), "原始报告与当前记录不一致。");
    await user.click(screen.getByRole("button", { name: "预览影响范围" }));
    await screen.findByText("拟修改");
    await user.click(screen.getByRole("checkbox", { name: /我已核对/ }));
    await user.click(screen.getByRole("button", { name: "提交修订" }));

    const keepOpen = await screen.findByRole("button", { name: "处理中请保持窗口打开" });
    expect(keepOpen).toBeDisabled();
    expect(screen.getByRole("button", { name: "关闭事实修订" })).toBeDisabled();
    expect(screen.getByText("请保持当前窗口打开。处理结束后系统会自动刷新病历档案和修订记录。")).toBeInTheDocument();

    await user.keyboard("{Escape}");
    expect(onClose).not.toHaveBeenCalled();
  });

  it("keeps the draft visible when the persistent task needs retry", async () => {
    const user = userEvent.setup();
    const failed: FactCorrectionJobStatusView = {
      ...completedStatus(),
      state: "failed_retryable",
      stateLabel: "未完成，稍后重试",
      errorCode: "TEMPORARY_FAILURE",
      errorClassification: "暂时无法完成",
      recoveryAction: "请稍后重新处理。",
    };
    const { repo } = makeRepo(failed);
    renderDialog(repo);

    const reason = "原始报告与当前记录不一致。";
    await user.type(screen.getByRole("textbox", { name: "修订理由（必填）" }), reason);
    await user.click(screen.getByRole("button", { name: "预览影响范围" }));
    await screen.findByText("拟修改");
    await user.click(screen.getByRole("checkbox", { name: /我已核对/ }));
    await user.click(screen.getByRole("button", { name: "提交修订" }));

    expect(await screen.findByText("修改内容仍保留在当前窗口，可以重新处理失败部分。")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "修订理由（必填）" })).toHaveValue(reason);
    expect(screen.getByRole("button", { name: "重新处理失败部分" })).toBeInTheDocument();
  });

  it("keeps draft and preview when evidenceOpen parks the workspace", async () => {
    const user = userEvent.setup();
    const { repo } = makeRepo();
    const model = adaptPatientProfile(decodePatientProfileRevision(makeRevision()));
    const lane = model.lanes.find((candidate) => candidate.lane === "demographics");
    const item = lane?.items[0];
    if (item === undefined) throw new Error("测试数据缺少事实条目");
    setPatientProfileRepository(repo);

    const reason = "原始报告与当前记录不一致。";
    const { rerender } = render(
      <ProfileFactCorrectionDialog
        model={model}
        item={item}
        targetKind="fact"
        subjectId={SUBJECT}
        reviewEpisodeId={EPISODE}
        onClose={vi.fn()}
        onOpenEvidence={vi.fn()}
        evidenceOpen={false}
        onCompleted={vi.fn()}
      />,
    );

    await user.type(screen.getByRole("textbox", { name: "修订理由（必填）" }), reason);
    await user.click(screen.getByRole("button", { name: "预览影响范围" }));
    await screen.findByText("拟修改");
    await user.click(screen.getByRole("checkbox", { name: /我已核对/ }));

    rerender(
      <ProfileFactCorrectionDialog
        model={model}
        item={item}
        targetKind="fact"
        subjectId={SUBJECT}
        reviewEpisodeId={EPISODE}
        onClose={vi.fn()}
        onOpenEvidence={vi.fn()}
        evidenceOpen
        onCompleted={vi.fn()}
      />,
    );
    expect(screen.getByRole("dialog", { hidden: true })).toHaveAttribute("aria-modal", "false");

    rerender(
      <ProfileFactCorrectionDialog
        model={model}
        item={item}
        targetKind="fact"
        subjectId={SUBJECT}
        reviewEpisodeId={EPISODE}
        onClose={vi.fn()}
        onOpenEvidence={vi.fn()}
        evidenceOpen={false}
        onCompleted={vi.fn()}
      />,
    );

    expect(screen.getByRole("textbox", { name: "修订理由（必填）" })).toHaveValue(reason);
    expect(screen.getByText("拟修改")).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /我已核对/ })).toBeChecked();
  });
});
