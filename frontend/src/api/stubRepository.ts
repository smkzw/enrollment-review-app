/**
 * 版本化异步 stub 仓储：Phase 1 的单一数据访问边界。
 * 实现从 `src/fixtures`（contracts/v1/fixtures 的 fixture/v1 副本）读取，
 * 经 mappers.ts 转换为只读 ViewModel；不写回、不模拟真实后台完成。
 * 后续真实 API 实现同一接口即可无缝替换（spec: hook-guidelines）。
 */

import { assertFixtureVersion, workspaceFixture } from "./fixtureAssets";
import {
  mapAction,
  mapBoard,
  mapEpisodeDetail,
  mapJob,
  mapPatientProfile,
  mapProtocolDiff,
  mapTodayWork,
  mapWorkspace,
} from "../domain/mappers";
import type { ReviewStage } from "../domain/enums";
import type { SubjectId } from "../domain/ids";
import type {
  ActionView,
  BoardView,
  EpisodeDetailView,
  EpisodeSummaryView,
  JobView,
  PatientProfileView,
  ProjectSummaryView,
  ProtocolDiffView,
  ReviewDiffView,
  StageInfoView,
  SubjectSummaryView,
  TodayWorkView,
  WorkspaceView,
} from "../domain/viewModels";

export interface EnrollmentRepository {
  readonly kind: "stub";
  getWorkspace(): Promise<WorkspaceView>;
  getBoard(): Promise<BoardView>;
  getProjectSummary(): Promise<ProjectSummaryView>;
  getTodayWork(): Promise<TodayWorkView>;
  getStages(): Promise<ReadonlyArray<StageInfoView>>;
  getSubjects(): Promise<ReadonlyArray<SubjectSummaryView>>;
  /** 某受试者的全部审核节点 */
  getSubjectEpisodes(subjectId: SubjectId): Promise<ReadonlyArray<EpisodeSummaryView>>;
  /** 受试者 × 独立审核节点详情（规则树、判断、行动、证据） */
  getEpisodeDetail(subjectId: SubjectId, stage: ReviewStage): Promise<EpisodeDetailView>;
  getPatientProfile(subjectId: SubjectId, stage: ReviewStage): Promise<PatientProfileView>;
  getProtocolDiff(): Promise<ProtocolDiffView>;
  getActions(): Promise<ReadonlyArray<ActionView>>;
  getJobs(): Promise<ReadonlyArray<JobView>>;
  getReviewDiffs(): Promise<ReadonlyArray<ReviewDiffView>>;
}

export class StubApiError extends Error {
  readonly code: "subject_not_found" | "episode_not_found" | "fixture_version_mismatch";
  readonly detail: string;

  constructor(
    code: StubApiError["code"],
    message: string,
    detail: string,
  ) {
    super(message);
    this.name = "StubApiError";
    this.code = code;
    this.detail = detail;
  }
}

const LATENCY_MS = 30;

function simulateLatency(ms: number = LATENCY_MS): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function findEpisode(subjectId: SubjectId, stage: ReviewStage) {
  const episode = workspaceFixture.episodes.find(
    (candidate) =>
      candidate.subject.subject_id === subjectId &&
      candidate.review_episode.stage === stage,
  );
  if (episode === undefined) {
    throw new StubApiError(
      "episode_not_found",
      "未找到该受试者在此审核节点的资料。",
      `subjectId=${subjectId}, stage=${stage}`,
    );
  }
  return episode;
}

export function createStubRepository(): EnrollmentRepository {
  assertFixtureVersion(workspaceFixture.schema_version);

  return {
    kind: "stub",

    async getWorkspace(): Promise<WorkspaceView> {
      await simulateLatency();
      return mapWorkspaceView();
    },

    async getBoard(): Promise<BoardView> {
      await simulateLatency();
      return mapBoard(workspaceFixture);
    },

    async getProjectSummary(): Promise<ProjectSummaryView> {
      await simulateLatency();
      return mapBoard(workspaceFixture).project;
    },

    async getTodayWork(): Promise<TodayWorkView> {
      await simulateLatency();
      return mapTodayWork(workspaceFixture);
    },

    async getStages(): Promise<ReadonlyArray<StageInfoView>> {
      await simulateLatency();
      return mapBoard(workspaceFixture).stages;
    },

    async getSubjects(): Promise<ReadonlyArray<SubjectSummaryView>> {
      await simulateLatency();
      return mapBoard(workspaceFixture).subjects;
    },

    async getSubjectEpisodes(
      subjectId: SubjectId,
    ): Promise<ReadonlyArray<EpisodeSummaryView>> {
      await simulateLatency();
      const board = mapBoard(workspaceFixture);
      const found = board.episodes.filter(
        (episode) => episode.subjectId === subjectId,
      );
      if (found.length === 0) {
        throw new StubApiError(
          "subject_not_found",
          "未找到这位受试者。",
          `subjectId=${subjectId}`,
        );
      }
      return found;
    },

    async getEpisodeDetail(
      subjectId: SubjectId,
      stage: ReviewStage,
    ): Promise<EpisodeDetailView> {
      await simulateLatency();
      return mapEpisodeDetail(findEpisode(subjectId, stage));
    },

    async getPatientProfile(
      subjectId: SubjectId,
      stage: ReviewStage,
    ): Promise<PatientProfileView> {
      await simulateLatency();
      const episode = findEpisode(subjectId, stage);
      return mapPatientProfile(episode.patient_profile, episode);
    },

    async getProtocolDiff(): Promise<ProtocolDiffView> {
      await simulateLatency();
      return mapProtocolDiff(workspaceFixture.protocol_diff);
    },

    async getActions(): Promise<ReadonlyArray<ActionView>> {
      await simulateLatency();
      // 行动中心需要全部行动（含溯源待办与后续节点行动）；今日工作另取到期子集
      return workspaceFixture.episodes.flatMap((episode) =>
        episode.actions.map((action) => mapAction(action, episode)),
      );
    },

    async getJobs(): Promise<ReadonlyArray<JobView>> {
      await simulateLatency();
      return workspaceFixture.episodes
        .map(mapJob)
        .filter((job): job is JobView => job !== null);
    },

    async getReviewDiffs(): Promise<ReadonlyArray<ReviewDiffView>> {
      await simulateLatency();
      return mapWorkspaceView().reviewDiffs;
    },
  };
}

let workspaceViewCache: WorkspaceView | null = null;

/** 惰性构建并缓存，避免每次调用重建 2.4MB 映射；结果确定不变。 */
function mapWorkspaceView(): WorkspaceView {
  if (workspaceViewCache === null) {
    workspaceViewCache = mapWorkspace(workspaceFixture);
  }
  return workspaceViewCache;
}

let defaultRepository: EnrollmentRepository | null = null;

export function getDefaultRepository(): EnrollmentRepository {
  if (defaultRepository === null) {
    defaultRepository = createStubRepository();
  }
  return defaultRepository;
}
