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
    siblingFactIds: [],
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
    getFactSourceReadings: vi.fn(() => Promise.resolve([])),
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

  it("空读数可明确选择数字，不把补回的读数保存成文字，提交仍须预览确认", async () => {
    const { repo, preview, submit } = makeRepo();
    preview.mockResolvedValue({ ...makePreview(),
      oldSnapshot: { ...makePreview().oldSnapshot, value: null },
      newSnapshot: { ...makePreview().oldSnapshot, value: 52 } });
    const raw = makeRevision();
    const selected = raw.lanes.flatMap(lane => lane.items).find(item => item.kind === "fact")!;
    selected.value = null;
    const model = adaptPatientProfile(decodePatientProfileRevision(raw));
    const item = model.lanes.flatMap(lane => lane.items).find(item => item.sourceId === selected.source_id)!;
    setPatientProfileRepository(repo);
    render(<ProfileFactCorrectionDialog model={model} item={item} targetKind="fact" subjectId={SUBJECT}
      reviewEpisodeId={EPISODE} onClose={vi.fn()} onCompleted={vi.fn()} />);
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "记录形式" }), "number");
    await userEvent.type(screen.getByRole("spinbutton", { name: "记录结果" }), "52");
    await userEvent.type(screen.getByRole("textbox", { name: "修订理由（必填）" }), "按原件补回未记录读数。");
    await userEvent.click(screen.getByRole("button", { name: "预览影响范围" }));
    await screen.findByText("拟修改");
    expect(preview.mock.calls[0]?.[2].updates.value).toBe(52);
    expect(submit).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("checkbox", { name: /我已核对/ }));
    await userEvent.click(screen.getByRole("button", { name: "提交修订" }));
    expect(submit.mock.calls[0]?.[2].updates.value).toBe(52);
  });

  it("用中文选择所属项目，修改关联进入预览和提交，不改写未动的原值", async () => {
    const { repo, preview, submit } = makeRepo();
    repo.getFactCorrectionOptions = vi.fn(async () => ({ subjectId: SUBJECT, reviewEpisodeId: EPISODE,
      targetId: "fact-demographics-1", targetRevision: 1, variableId: null,
      variables: [{ variableId: "pressure_record", label: "血压记录", valueType: "category" as const, unit: null }] }));
    preview.mockResolvedValue({ ...makePreview(), oldSnapshot: { ...makePreview().oldSnapshot, variable_id: null },
      newSnapshot: { ...makePreview().oldSnapshot, variable_id: "pressure_record" },
      variableLabels: new Map([["pressure_record", "血压记录"]]) });
    renderDialog(repo);
    const choices = await screen.findByRole("combobox", { name: "所属审核项目" });
    expect(choices).toHaveValue("");
    await userEvent.selectOptions(choices, "pressure_record");
    await userEvent.type(screen.getByRole("textbox", { name: "修订理由（必填）" }), "原读数对应血压记录。");
    await userEvent.click(screen.getByRole("button", { name: "预览影响范围" }));
    expect(await screen.findByText("拟修改")).toBeInTheDocument();
    expect(preview.mock.calls[0]?.[2].updates).toMatchObject({ variableId: "pressure_record", value: "120/80" });
    expect(screen.getAllByText("所属审核项目")).toHaveLength(3);
    expect(screen.queryByText("pressure_record")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("checkbox", { name: /我已核对/ }));
    await userEvent.click(screen.getByRole("button", { name: "提交修订" }));
    expect(submit.mock.calls[0]?.[2].updates.variableId).toBe("pressure_record");
  });

  it("项目清单版本失配时不让用户选错记录，原关联和旧修订输入保持", async () => {
    const { repo, preview } = makeRepo();
    repo.getFactCorrectionOptions = vi.fn(async () => ({ subjectId: SUBJECT, reviewEpisodeId: EPISODE,
      targetId: "fact-demographics-1", targetRevision: 99, variableId: null, variables: [] }));
    renderDialog(repo);
    expect(await screen.findByText("所属审核项目暂时无法读取，原关联保持不变。")).toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: "所属审核项目" })).not.toBeInTheDocument();
    await userEvent.type(screen.getByRole("textbox", { name: "修订理由（必填）" }), "保留原关联核对读数。");
    await userEvent.click(screen.getByRole("button", { name: "预览影响范围" }));
    await screen.findByText("拟修改");
    expect(preview.mock.calls[0]?.[2].updates).not.toHaveProperty("variableId");
  });

  it("选择是否项目不会自动清空原文字或改为是与否", async () => {
    const { repo, preview } = makeRepo();
    repo.getFactCorrectionOptions = vi.fn(async () => ({ subjectId: SUBJECT, reviewEpisodeId: EPISODE,
      targetId: "fact-demographics-1", targetRevision: 1, variableId: null,
      variables: [{ variableId: "procedure_record", label: "检查完成", valueType: "procedure" as const, unit: null }] }));
    renderDialog(repo);
    await userEvent.selectOptions(await screen.findByRole("combobox", { name: "所属审核项目" }), "procedure_record");
    await userEvent.type(screen.getByRole("textbox", { name: "修订理由（必填）" }), "核对关联。");
    await userEvent.click(screen.getByRole("button", { name: "预览影响范围" }));
    await screen.findByText("拟修改");
    expect(preview.mock.calls[0]?.[2].updates).toMatchObject({ variableId: "procedure_record", value: "120/80" });
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

  it("explains which other facts share the source without silently changing them", async () => {
    const user = userEvent.setup();
    const { repo, preview } = makeRepo();
    preview.mockResolvedValue({ ...makePreview(), siblingFactIds: ["fact-2"] });
    renderDialog(repo);

    await user.type(screen.getByRole("textbox", { name: "修订理由（必填）" }), "原始报告与当前记录不一致。");
    await user.click(screen.getByRole("button", { name: "预览影响范围" }));

    expect(await screen.findByText(/同一处原始资料还关联 1 条其他病史/)).toHaveTextContent(
      "本次只更正当前条目，请在提交后核对这些条目是否也需更正。",
    );
    expect(screen.queryByText("fact-2")).not.toBeInTheDocument();
  });

  it("范围未能逐项列清时保留整节点重算说明，不把未知范围显示成全为零", async () => {
    const { repo, preview } = makeRepo();
    preview.mockResolvedValue({ ...makePreview(), impact: { ...makePreview().impact,
      affectedLocatorIds: [], affectedDocumentIds: [], affectedFactIds: [], affectedEventIds: [],
      affectedExposureIds: [], affectedConflictGroupIds: [], affectedRuleLinkIds: [], affectedExpectationIds: [],
      affectedProfileRevisionIds: [], fallbackReason: "历史 Profile 未提供类型化条目反向索引" } });
    renderDialog(repo);
    await userEvent.type(screen.getByRole("textbox", { name: "修订理由（必填）" }), "核对记录。");
    await userEvent.click(screen.getByRole("button", { name: "预览影响范围" }));
    await screen.findByText("拟修改");
    expect(screen.getByText("将重新整理本审核节点全部事实。既有档案版本保持不变，完成后只会生成新的当前档案版本。")).toBeVisible();
    expect(screen.queryByText(/反向索引/)).not.toBeInTheDocument();
    expect(document.querySelector(".profile-correction-impact__counts")).toBeNull();
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

  it("更正已保存不冒充新版工作稿完成，后续核对完成才刷新", async () => {
    const user = userEvent.setup();
    const completed = vi.fn();
    const { repo } = makeRepo({ ...completedStatus(), progressTotal: 3, progressCompleted: 3 });
    let ready = false;
    repo.getFactCorrectionWorkDraftLink = vi.fn<NonNullable<PatientProfileRepository["getFactCorrectionWorkDraftLink"]>>(async () => ({
      jobId: "job-1", subjectId: SUBJECT, reviewEpisodeId: EPISODE, enabled: true, correctionApplied: true,
      workDraftJobId: "new-work-draft", workDraftState: ready ? "completed" : "running", reviewRunId: ready ? "new-review-run" : null,
    }));
    renderDialog(repo, completed);
    await user.type(screen.getByRole("textbox", { name: "修订理由（必填）" }), "核对合成原件，更正读数。");
    await user.click(screen.getByRole("button", { name: "预览影响范围" }));
    await screen.findByText("拟修改");
    await user.click(screen.getByRole("checkbox", { name: /我已核对/ }));
    await user.click(screen.getByRole("button", { name: "提交修订" }));
    await screen.findByText("更正已保存，正在更新工作稿");
    expect(completed).not.toHaveBeenCalled();
    expect(localStorage.getItem(`work-draft-job:${EPISODE}`)).toBe("new-work-draft");
    ready = true;
    await waitFor(() => expect(completed).toHaveBeenCalledTimes(1), { timeout: 2500 });
    expect(screen.getByText("更正与新工作稿均已保存，未签发")).toBeInTheDocument();
  });

  it("结果更新失败可只重试核对任务，不再次保存更正", async () => {
    const user = userEvent.setup();
    const completed = vi.fn();
    const { repo, submit } = makeRepo({ ...completedStatus(), progressTotal: 3, progressCompleted: 3 });
    let recovered = false;
    repo.getFactCorrectionWorkDraftLink = vi.fn<NonNullable<PatientProfileRepository["getFactCorrectionWorkDraftLink"]>>(async () => ({ jobId: "job-1", subjectId: SUBJECT, reviewEpisodeId: EPISODE,
      enabled: true, correctionApplied: true, workDraftJobId: "failed-working-job", workDraftState: recovered ? "completed" : "failed_final",
      reviewRunId: recovered ? "new-run" : null }));
    repo.retryFactCorrectionJob = vi.fn<PatientProfileRepository["retryFactCorrectionJob"]>(async () => { recovered = true; return { jobId: "failed-working-job", state: "queued", stateLabel: "等待处理", changed: true }; });
    renderDialog(repo, completed);
    await user.type(screen.getByRole("textbox", { name: "修订理由（必填）" }), "核对合成原件，更正读数。");
    await user.click(screen.getByRole("button", { name: "预览影响范围" }));
    await screen.findByText("拟修改");
    await user.click(screen.getByRole("checkbox", { name: /我已核对/ }));
    await user.click(screen.getByRole("button", { name: "提交修订" }));
    await screen.findByText("更正已经保存，新工作稿尚未生成；原结果保留，可重新更新工作稿。");
    expect(completed).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "重新处理失败部分" }));
    await waitFor(() => expect(completed).toHaveBeenCalledTimes(1));
    expect(repo.retryFactCorrectionJob).toHaveBeenCalledWith("failed-working-job");
    expect(submit).toHaveBeenCalledTimes(1);
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
