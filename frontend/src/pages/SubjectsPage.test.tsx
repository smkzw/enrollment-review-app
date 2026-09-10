// @vitest-environment jsdom
/**
 * 受试者与 Patient Profile 页面测试（Phase 5.6）：
 * - 正式项目目录（catalog）选择项目/受试者/审核节点；
 * - 读取真实 Profile（严格解码后的视图），首屏只展示后端 highlights；
 * - "全部历时信息"展开 13 条泳道；
 * - 生成中/失败/陈旧/空态显式区分；
 * - 去除旧总体结论与旧 fixture 文案，不显示 Phase 6/7 结论或行动。
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, beforeEach, afterEach, vi } from "vitest";
import { setPatientProfileRepository, type PatientProfileRepository } from "../api/patient-profile";
import { decodePatientProfileRevision, PatientProfileApiError } from "../api/patient-profile/patientProfileViewModels";
import {
  makeFactItem,
  makeLaneSection,
  makeLocator,
  makeRevision,
  PROFILE_LANE_ORDER,
} from "../api/patient-profile/patientProfileFixtures";
import { setFactNormalizationRepository } from "../api/fact-normalization";
import { SubjectsPage } from "./SubjectsPage";

const PROJECT_ID = "project-synthetic-phase-iii";
const SUBJECT_UAT03 = "subject-uat-03-gap_conflict";
const EP_UAT01_BASELINE = "episode-uat-01-baseline-clear";
const GENERATED_TITLE = "血压 130/85 mmHg";
const GENERATED_EXCERPT = "基线血压 130/85 mmHg";
const PRE_CORRECTION_TITLE = "血压 120/80 mmHg";
const PRE_CORRECTION_EXCERPT = "基线血压 120/80 mmHg";
const CITED_LOCATOR_ID = "loc-bp-1";
const PRE_CORRECTION_LOCATOR_ID = "loc-bp-pre";

function factSnapshot(value: string) {
  return {
    kind: "fact",
    fact_type: "vital_sign",
    profile_lane: "demographics",
    polarity: "affirmed",
    asserted_object: "血压",
    value,
    unit: "mmHg",
    date_range: null,
    source_strength: "current_study_chart_direct_record",
    assertion_object: "血压",
    assertion_text: `基线血压 ${value} mmHg`,
    supported_requirement_ids: ["req-1"],
  };
}

function lanesWithFact(
  title: string,
  value: string,
  locatorIds: string[],
  sourceId = "fact-source-1",
) {
  return PROFILE_LANE_ORDER.map((lane) => {
    if (lane === "demographics") {
      return makeLaneSection(lane, [
        makeFactItem({ title, value, locator_ids: locatorIds, source_id: sourceId }),
      ]);
    }
    return makeLaneSection(lane, []);
  });
}

function makeProfileRepo(
  resolve: (subjectId: string, reviewEpisodeId: string) => ReturnType<typeof makeRevision> | Error,
  options: {
    listHistory?: PatientProfileRepository["listFactCorrectionHistory"];
    getRevision?: PatientProfileRepository["getPatientProfileRevision"];
  } = {},
): PatientProfileRepository {
  return {
    kind: "http",
    async getLatestPatientProfile(subjectId, reviewEpisodeId) {
      const result = resolve(subjectId, reviewEpisodeId);
      if (result instanceof Error) throw result;
      return decodePatientProfileRevision(result);
    },
    async listPatientProfileHistory() {
      throw new Error("not used");
    },
    async getPatientProfileRevision(subjectId, revisionId, requestOptions) {
      if (options.getRevision !== undefined) {
        return options.getRevision(subjectId, revisionId, requestOptions);
      }
      throw new Error("not used");
    },
    async previewFactCorrection() {
      throw new Error("not used");
    },
    async submitFactCorrection() {
      throw new Error("not used");
    },
    async listFactCorrectionHistory(subjectId, reviewEpisodeId, requestOptions) {
      if (options.listHistory !== undefined) {
        return options.listHistory(subjectId, reviewEpisodeId, requestOptions);
      }
      return {
        subjectId,
        reviewEpisodeId,
        items: [],
      };
    },
    async getFactCorrectionJobStatus() {
      throw new Error("not used");
    },
    async cancelFactCorrectionJob() {
      throw new Error("not used");
    },
    async retryFactCorrectionJob() {
      throw new Error("not used");
    },
  };
}

/** 默认成功档案：人口学事实条目 + 原报告异常 highlight。 */
function defaultRevision(subjectId: string, episodeId: string) {
  return makeRevision({
    patient_profile_revision_id: `rev-${episodeId}`,
    evidence_navigation: {
      project_id: PROJECT_ID,
      subject_id: subjectId,
      review_episode_id: episodeId,
      evidence_snapshot_v2_id: "snapshot-1",
      complete_processing_revision_id: "complete-1",
    },
  });
}

describe("受试者与 Patient Profile 页", () => {
  beforeEach(() => {
    window.location.hash = "";
    window.localStorage.clear();
    setPatientProfileRepository(
      makeProfileRepo((subjectId, episodeId) => defaultRevision(subjectId, episodeId)),
    );
    setFactNormalizationRepository({
      kind: "http",
      startFactNormalization: vi.fn(async () => ({
        jobId: "job-normalize-test",
        runId: "run-normalize-test",
        created: false,
        state: "queued" as const,
        stateLabel: "等待处理",
        recoveryAction: "无需操作，正在等待开始。",
      })),
      getFactNormalizationJobStatus: vi.fn(async () => ({
        jobId: "job-normalize-test",
        state: "queued" as const,
        stateLabel: "等待处理",
        cancelRequested: false,
        progressCompleted: 0,
        progressTotal: 1,
        recoveryAction: "无需操作，正在等待开始。",
        createdAt: "2026-08-23T10:00:00Z",
        updatedAt: "2026-08-23T10:00:00Z",
      })),
      retryFactNormalizationJob: vi.fn(async () => ({
        jobId: "job-normalize-test",
        state: "queued" as const,
        stateLabel: "等待处理",
        changed: false,
      })),
    });
  });
  afterEach(() => {
    setPatientProfileRepository(null);
    setFactNormalizationRepository(null);
  });

  it("默认选择首个项目/受试者/审核节点并读取真实档案，首屏只显示后端 highlights", async () => {
    render(<SubjectsPage />);
    // 正式目录：项目、受试者、审核节点
    expect(await screen.findByRole("heading", { name: "受试者" })).toBeInTheDocument();
    const projectSelect = screen.getByRole("combobox", { name: "选择项目" });
    expect(projectSelect).toHaveValue(PROJECT_ID);

    // 首屏标题与后端 highlight 原因（来自 makeRevision 默认 highlight：原报告异常）
    expect(await screen.findByRole("heading", { name: /首屏重点/ })).toBeInTheDocument();
    expect(screen.getByText("原报告异常")).toBeInTheDocument();
    // 突出条目标题来自档案
    expect(screen.getByText("基线血压 120/80 mmHg")).toBeInTheDocument();
    // 首屏不应直接展开 13 条泳道
    expect(screen.queryByRole("heading", { name: /生育/ })).not.toBeInTheDocument();
    // 审核节点选择存在
    expect(screen.getByRole("button", { name: "筛选期" })).toBeInTheDocument();
  });

  it("“全部历时信息”展开 13 条泳道，空泳道不判为资料缺口", async () => {
    const user = userEvent.setup();
    render(<SubjectsPage />);
    await screen.findByRole("heading", { name: /首屏重点/ });
    await user.click(screen.getByRole("button", { name: "全部历时信息" }));
    // 泳道标题（含空泳道）
    expect(await screen.findByRole("heading", { name: /人口学\/基线/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /生育/ })).toBeInTheDocument();
    expect(screen.getByText(/分区暂无记录不代表正常或否认/)).toBeInTheDocument();
    expect(screen.queryByText(/按资料缺口处理/)).not.toBeInTheDocument();
  });

  it("切换受试者后重新读取该受试者档案，URL 记录新 subject", async () => {
    const user = userEvent.setup();
    render(<SubjectsPage />);
    await screen.findByRole("heading", { name: /首屏重点/ });
    await user.click(screen.getByRole("button", { name: /UAT-03/ }));
    await screen.findByRole("heading", { name: /首屏重点/ });
    expect(window.location.hash).toContain(`subject=${SUBJECT_UAT03}`);
  });

  it("切换审核节点后重新读取档案，URL 记录新 episode", async () => {
    const user = userEvent.setup();
    render(<SubjectsPage />);
    await screen.findByRole("heading", { name: /首屏重点/ });
    await user.click(screen.getByRole("button", { name: "基线/随机前" }));
    await screen.findByRole("heading", { name: /首屏重点/ });
    expect(window.location.hash).toContain(`episode=${EP_UAT01_BASELINE}`);
  });

  it("生成中状态：提示生成中，不渲染泳道列表", async () => {
    setPatientProfileRepository(
      makeProfileRepo(() => makeRevision({ status: "generating", status_label: "生成中" })),
    );
    render(<SubjectsPage />);
    // 状态提示（role=status）只出现一次（横幅），正文不再重复
    expect(await screen.findByText(/档案正在生成中/)).toBeInTheDocument();
    expect(screen.getByText("生成中", { exact: true })).toBeInTheDocument();
    expect(screen.queryByText("基线血压 120/80 mmHg")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "全部历时信息" })).not.toBeInTheDocument();
  });

  it("失败状态：提示生成失败（role=alert）", async () => {
    setPatientProfileRepository(
      makeProfileRepo(() => makeRevision({ status: "failed", status_label: "生成失败" })),
    );
    render(<SubjectsPage />);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("生成失败");
  });

  it("陈旧状态：提示资料已更新且仍展示历史档案内容", async () => {
    setPatientProfileRepository(
      makeProfileRepo(() =>
        makeRevision({ status: "stale", status_label: "资料已更新，档案待重新生成" }),
      ),
    );
    render(<SubjectsPage />);
    // 状态提示（role=status）
    expect(await screen.findByText(/档案待重新生成/)).toBeInTheDocument();
    expect(screen.getByText(/资料已更新，档案待重新生成/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "重新整理个例档案" })).toBeInTheDocument();
    // 仍展示历史内容（首屏重点）
    expect(screen.getByText("基线血压 120/80 mmHg")).toBeInTheDocument();
  });

  it("已生成空态：区分于生成中/失败", async () => {
    setPatientProfileRepository(
      makeProfileRepo(() =>
        makeRevision({
          lanes: PROFILE_LANE_ORDER.map((lane) => ({
            lane,
            lane_label: lane,
            items: [],
          })),
          highlights: [],
          evidence_locators: [],
        }),
      ),
    );
    render(<SubjectsPage />);
    expect(
      await screen.findByText("该审核节点已生成档案，但当前没有已整理的资料条目。"),
    ).toBeInTheDocument();
    expect(screen.queryByText(/档案正在生成中/)).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("档案尚未生成（404）时自动发起整理并展示任务状态", async () => {
    setPatientProfileRepository(
      makeProfileRepo(() =>
        new PatientProfileApiError(
          "NOT_FOUND",
          "未找到",
          "该审核节点还没有生成病历档案。",
          "请先完成资料整理并生成档案，或从项目目录选择其他审核节点。",
          404,
        ),
      ),
    );
    render(<SubjectsPage />);
    expect(await screen.findByLabelText("个例档案整理状态")).toHaveTextContent(
      /个例档案整理排队中|正在整理个例档案/,
    );
    expect(screen.queryByText(/Agent|pipeline|schema/i)).not.toBeInTheDocument();
  });

  it("不显示旧 fixture 文案、旧总体结论或 Phase 6/7 结论/行动", async () => {
    render(<SubjectsPage />);
    await screen.findByRole("heading", { name: /首屏重点/ });
    expect(screen.queryByText(/界试用：展示合成示例数据/)).not.toBeInTheDocument();
    expect(screen.queryByText(/关键事件与风险/)).not.toBeInTheDocument();
    expect(screen.queryByText(/入排结论|行动数量|负责方|通过|不通过/)).not.toBeInTheDocument();
    expect(screen.queryByText(/后续节点关注/)).not.toBeInTheDocument();
  });

  it("资料页元信息使用中文项目展示名，不暴露原始项目代号", async () => {
    render(<SubjectsPage />);
    expect(await screen.findByText(/界面试用项目 · Ⅲ期/)).toBeInTheDocument();
    expect(screen.queryByText(/SYNTHETIC-001-III/)).not.toBeInTheDocument();
  });

  it("待核对数与生成时间来自真实档案模型", async () => {
    render(<SubjectsPage />);
    await screen.findByRole("heading", { name: /首屏重点/ });
    expect(screen.getByText(/待核对 0 项/)).toBeInTheDocument();
    expect(screen.getByText(/生成时间 2026年8月22日 20:00（北京时间）/)).toBeInTheDocument();
  });

  it("修订记录绑定本次修订生成的档案版本，原文入口不回退到修订前定位", async () => {
    const user = userEvent.setup();
    const getRevision = vi.fn(async (_subjectId: string, revisionId: string) => {
      expect(revisionId).toBe("profile-revision-3");
      return decodePatientProfileRevision(
        makeRevision({
          patient_profile_revision_id: "profile-revision-3",
          revision: 3,
          lanes: lanesWithFact(
            GENERATED_TITLE,
            "130/85",
            [CITED_LOCATOR_ID],
            "fact-source-2",
          ),
          evidence_locators: [
            makeLocator({
              locator_id: CITED_LOCATOR_ID,
              page_number: 1,
              excerpt: GENERATED_EXCERPT,
              precision_label: "原文区域",
            }),
          ],
        }),
      );
    });
    setPatientProfileRepository(
      makeProfileRepo(
        () =>
          makeRevision({
            patient_profile_revision_id: "profile-revision-3",
            revision: 3,
            lanes: lanesWithFact(
              GENERATED_TITLE,
              "130/85",
              [CITED_LOCATOR_ID],
              "fact-source-2",
            ),
            evidence_locators: [
              makeLocator({
                locator_id: CITED_LOCATOR_ID,
                page_number: 1,
                excerpt: GENERATED_EXCERPT,
                precision_label: "原文区域",
              }),
              // 修订前定位仅存在于旧档案；同 id 不得在此改页改摘录。
              makeLocator({
                locator_id: PRE_CORRECTION_LOCATOR_ID,
                page_number: 7,
                excerpt: PRE_CORRECTION_EXCERPT,
                precision_label: "原文区域",
              }),
            ],
          }),
        {
          getRevision,
          listHistory: async () => ({
            subjectId: "subject-uat-01-clear",
            reviewEpisodeId: "episode-uat-01-screening-clear",
            items: [
              {
                correctionId: "correction-1",
                targetKind: "fact",
                targetKindLabel: "事实",
                targetId: "fact-source-1",
                newEntityId: "fact-source-2",
                reason: "原始报告数值与当前记录不一致。",
                operatorId: "local-reviewer",
                locatorIds: [CITED_LOCATOR_ID],
                correctedAt: "2026-08-23T08:00:00Z",
                oldSnapshot: factSnapshot("120/80"),
                newSnapshot: factSnapshot("130/85"),
                impact: {
                  scopeKind: "local",
                  scopeKindLabel: "当前记录及相关内容",
                  fallbackReason: null,
                  affectedLocatorIds: [CITED_LOCATOR_ID],
                  affectedDocumentIds: ["document-1"],
                  affectedFactIds: ["fact-source-1"],
                  affectedEventIds: [],
                  affectedExposureIds: [],
                  affectedConflictGroupIds: [],
                  affectedRuleLinkIds: [],
                  affectedExpectationIds: [],
                  affectedProfileRevisionIds: ["profile-revision-1"],
                },
                profileRevisionId: "profile-revision-3",
                profileRevision: 3,
              },
            ],
          }),
        },
      ),
    );

    render(<SubjectsPage />);
    expect(await screen.findByText(GENERATED_TITLE)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /修订记录/ }));
    expect(await screen.findByText("本次修订形成档案第 3 版。")).toBeInTheDocument();
    expect(
      screen.getByText(`第 1 页 · 原文区域 · “${GENERATED_EXCERPT}”`),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(`第 7 页 · 原文区域 · “${PRE_CORRECTION_EXCERPT}”`),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(PRE_CORRECTION_TITLE)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "查看原文" }));
    const evidence = await screen.findByLabelText("该条目的原文证据与定位");
    expect(within(evidence).getByRole("heading", { name: GENERATED_TITLE })).toBeInTheDocument();
    expect(within(evidence).queryByText(PRE_CORRECTION_TITLE)).not.toBeInTheDocument();
    expect(getRevision).toHaveBeenCalled();
  });
});
