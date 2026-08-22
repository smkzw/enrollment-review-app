// @vitest-environment jsdom

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  CatalogApiError,
  setCatalogRepository,
  type CatalogEpisodeView,
  type CatalogRepository,
  type CatalogSubjectView,
  type SubjectCreateInput,
} from "../api/catalog";
import { SubjectsCatalogPage } from "./SubjectsCatalogPage";

const project = {
  projectId: "project-1",
  projectCode: "PROJECT-1",
  projectName: "合成试用项目",
  studyPhase: "phase_iii" as const,
  studyPhaseLabel: "Ⅲ期",
  protocolCode: "PROTOCOL-1",
  officialVersion: "V1.0",
  officialDateValue: "2026-08-21",
  officialDatePrecision: "day" as const,
  ruleSetId: "rules-1",
  ruleSetRevision: 1,
};

const subject = {
  subjectId: "subject-1",
  subjectCode: "S-001",
  projectId: project.projectId,
  centerCode: "01",
  centerName: "合成研究中心",
  sex: null,
  ageYears: null,
  revision: 1,
};

const episode = {
  reviewEpisodeId: "episode-1",
  subjectId: subject.subjectId,
  projectId: project.projectId,
  ruleSetId: project.ruleSetId,
  studyPhase: "phase_iii",
  studyPhaseLabel: "Ⅲ期",
  stage: "screening",
  stageLabel: "筛选期",
  protocolVersionId: "protocol-version-1",
  ruleSetRevision: 1,
  evidenceSnapshotId: "snapshot-legacy",
  workflowStageId: "rules-1:1:stage-screening",
  workflowStageLabel: "筛选期审核",
  visitWindow: "第1天",
  latestEvidenceSnapshotId: "snapshot-active",
  activeEvidenceSnapshotId: "snapshot-active",
  activeEvidenceProcessingRevisionId: "processing-active",
  anchorDates: {},
  dueAt: null,
  revision: 1,
};

type CreateSubjectFn = (
  projectId: string,
  input: SubjectCreateInput,
  signal?: AbortSignal,
) => Promise<CatalogSubjectView>;
type DeleteSubjectFn = (
  projectId: string,
  subjectId: string,
  signal?: AbortSignal,
) => Promise<CatalogSubjectView>;

describe("受试者资料目录", () => {
  let episodeList: CatalogEpisodeView[];
  let subjectList: CatalogSubjectView[];
  let createSubject: ReturnType<typeof vi.fn<CreateSubjectFn>>;
  let deleteSubject: ReturnType<typeof vi.fn<DeleteSubjectFn>>;

  beforeEach(() => {
    window.location.hash = "#/subjects";
    episodeList = [episode];
    subjectList = [subject];
    createSubject = vi.fn<CreateSubjectFn>(async (projectId, input) => {
      const created: CatalogSubjectView = {
        subjectId: `subject-${input.subjectCode}`,
        subjectCode: input.subjectCode,
        projectId,
        centerCode: null,
        centerName: null,
        sex: null,
        ageYears: null,
        revision: 1,
      };
      subjectList = [...subjectList, created];
      return created;
    });
    deleteSubject = vi.fn<DeleteSubjectFn>(async (_projectId, subjectId) => {
      const target = subjectList.find((item) => item.subjectId === subjectId);
      if (target === undefined) {
        throw new CatalogApiError("未找到这个受试者。", "请刷新列表后重试。");
      }
      subjectList = subjectList.filter((item) => item.subjectId !== subjectId);
      return target;
    });
    const repository: CatalogRepository = {
      kind: "http",
      listProjects: vi.fn(async () => [project]),
      getProject: vi.fn(async () => project),
      listSubjects: vi.fn(async () => subjectList),
      getSubject: vi.fn(async () => subject),
      createSubject,
      deleteSubject,
      listEpisodes: vi.fn(async () => episodeList),
      getEvidenceContext: vi.fn(async () => ({ project, subject, episode })),
    };
    setCatalogRepository(repository);
  });

  it("项目选项以项目代号开头，长项目名仍保留完整身份", async () => {
    render(<SubjectsCatalogPage />);

    const projectSelect = await screen.findByRole("combobox", { name: "选择项目" });
    expect(
      within(projectSelect).getByRole("option", {
        name: /PROJECT-1 · 合成试用项目 · Ⅲ期 · 方案 V1\.0/,
      }),
    ).toBeInTheDocument();
  });

  it("已启用的资料在目录中明确标为当前有效", async () => {
    render(<SubjectsCatalogPage />);

    expect(await screen.findByText("筛选期资料当前有效")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "打开筛选期证据工作台" }),
    ).toHaveTextContent("查看筛选期资料");
    expect(screen.queryByText(/可继续核对/)).not.toBeInTheDocument();
  });

  it("展示流程节点原生中文名与访视窗口", async () => {
    render(<SubjectsCatalogPage />);

    // 工作台标题使用命名空间化流程节点的原生中文 display_name。
    expect(await screen.findByText("筛选期审核")).toBeInTheDocument();
    expect(screen.getByText("访视窗口：第1天")).toBeInTheDocument();
  });

  it("保留服务端流程顺序，不按中文标签将基线排到筛选前", async () => {
    episodeList = [
      episode,
      {
        ...episode,
        reviewEpisodeId: "episode-2",
        stage: "baseline",
        stageLabel: "基线期",
        workflowStageId: "rules-1:1:stage-baseline",
        workflowStageLabel: "基线期审核",
        visitWindow: "第2天",
      },
    ];

    render(<SubjectsCatalogPage />);

    await screen.findByText("基线期审核");
    expect(screen.getAllByRole("heading", { level: 3 }).map((heading) => heading.textContent))
      .toEqual(["筛选期审核", "基线期审核"]);
  });

  it("新增受试者：填写代号保存后列表出现新受试者并被选中", async () => {
    const user = userEvent.setup();
    render(<SubjectsCatalogPage />);
    await screen.findByText("筛选期资料当前有效");

    await user.click(screen.getByRole("button", { name: "新增受试者" }));
    await screen.findByRole("dialog", { name: "新增受试者" });
    await user.type(screen.getByLabelText(/受试者代号/), "S-002");
    await user.click(screen.getByRole("button", { name: "确认新增" }));

    await waitFor(() => expect(createSubject).toHaveBeenCalledTimes(1));
    expect(createSubject).toHaveBeenCalledWith(
      project.projectId,
      expect.objectContaining({ subjectCode: "S-002" }),
    );
    expect(screen.queryByRole("dialog", { name: "新增受试者" })).not.toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getAllByText("S-002").length).toBeGreaterThanOrEqual(1);
    });
    expect(window.location.hash).toContain("subject=subject-S-002");
  });

  it("新增受试者：代号为空时提示必填且不提交", async () => {
    const user = userEvent.setup();
    render(<SubjectsCatalogPage />);
    await screen.findByText("筛选期资料当前有效");

    await user.click(screen.getByRole("button", { name: "新增受试者" }));
    await screen.findByRole("dialog", { name: "新增受试者" });
    await user.click(screen.getByRole("button", { name: "确认新增" }));

    expect(await screen.findByText("请填写受试者代号。")).toBeInTheDocument();
    expect(createSubject).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog", { name: "新增受试者" })).toBeInTheDocument();
  });

  it("新增受试者：保存失败保留输入并展示中文恢复动作", async () => {
    createSubject.mockRejectedValueOnce(
      new CatalogApiError(
        "该项目已存在受试者代号 S-001。",
        "请更换受试者代号后重试；本次新增没有生效。",
      ),
    );
    const user = userEvent.setup();
    render(<SubjectsCatalogPage />);
    await screen.findByText("筛选期资料当前有效");

    await user.click(screen.getByRole("button", { name: "新增受试者" }));
    await screen.findByRole("dialog", { name: "新增受试者" });
    await user.type(screen.getByLabelText(/受试者代号/), "S-001");
    await user.click(screen.getByRole("button", { name: "确认新增" }));

    expect(
      await screen.findByText(/已存在受试者代号 S-001/),
    ).toBeInTheDocument();
    expect(screen.getByText(/请更换受试者代号后重试/)).toBeInTheDocument();
    // 弹窗未关闭、输入保留，可直接修改后重试。
    expect(screen.getByRole("dialog", { name: "新增受试者" })).toBeInTheDocument();
    expect(screen.getByLabelText(/受试者代号/)).toHaveValue("S-001");
  });

  it("删除受试者：确认后从列表移除并清空选中", async () => {
    const user = userEvent.setup();
    render(<SubjectsCatalogPage />);
    await screen.findByText("筛选期资料当前有效");

    await user.click(screen.getByRole("button", { name: "删除受试者 S-001" }));
    const deleteDialog = await screen.findByRole("dialog", { name: "确认删除受试者" });
    expect(within(deleteDialog).getByText("S-001")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "确认删除" }));

    await waitFor(() => expect(deleteSubject).toHaveBeenCalledTimes(1));
    expect(deleteSubject).toHaveBeenCalledWith(project.projectId, subject.subjectId);
    expect(screen.queryByRole("dialog", { name: "确认删除受试者" })).not.toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByText("S-001")).not.toBeInTheDocument();
    });
    expect(window.location.hash).not.toContain("subject=");
  });

  it("删除受试者：已纳入审核安排时保留弹窗并展示恢复动作", async () => {
    deleteSubject.mockRejectedValueOnce(
      new CatalogApiError(
        "该受试者已纳入审核安排。",
        "已建立审核节点或资料的受试者不能删除。",
      ),
    );
    const user = userEvent.setup();
    render(<SubjectsCatalogPage />);
    await screen.findByText("筛选期资料当前有效");

    await user.click(screen.getByRole("button", { name: "删除受试者 S-001" }));
    await screen.findByRole("dialog", { name: "确认删除受试者" });
    await user.click(screen.getByRole("button", { name: "确认删除" }));

    expect(await screen.findByText(/已纳入审核安排/)).toBeInTheDocument();
    expect(screen.getByText(/不能删除/)).toBeInTheDocument();
    const dialog = screen.getByRole("dialog", { name: "确认删除受试者" });
    expect(dialog).toBeInTheDocument();
    expect(within(dialog).getByText("S-001")).toBeInTheDocument();
  });
});
