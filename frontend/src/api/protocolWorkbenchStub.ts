/**
 * 方案解构工作台 stub 仓储：仅用于组件测试、Playwright 与显式 UAT 注入。
 */

import {
  draftComparisonFixture,
  draftRevisionFixture,
  identityReviewFixture,
  integrityFixture,
  officialProjectsFixture,
  projectOfficialVersionFixture,
  protocolRedoSessionFixture,
  protocolSessionFixtures,
  PROTOCOL_DEMO_JOB_ID,
  PROTOCOL_IDENTITY_JOB_ID,
  PROTOCOL_RECOVERY_JOB_ID,
  PROTOCOL_REDO_JOB_ID,
  sourcesFixture,
} from "../fixtures/protocol-deconstruction-workbench";
import type {
  ProtocolWorkbenchRepository,
  ProtocolWorkbenchRequestOptions,
} from "./protocolWorkbenchRepository";
import type {
  ConfirmIdentityInput,
  DraftComparisonView,
  DraftRevisionView,
  FeedbackInput,
  IdentityReviewView,
  IntegrityView,
  ManualEditInput,
  OfficialProjectView,
  ProjectOfficialVersionView,
  ProtocolSessionView,
  PublishResultView,
  SourcesView,
  StartDeconstructionResult,
} from "./protocolWorkbenchTypes";
import { ProtocolWorkbenchApiError } from "./protocolWorkbenchTypes";
import { studyPhaseLabel } from "../domain/labels";

const LATENCY_MS = 40;

function delay(ms: number = LATENCY_MS): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function rejectIfAborted(signal?: AbortSignal): void {
  if (signal?.aborted === true) {
    throw new DOMException("Aborted", "AbortError");
  }
}

function nextJobId(): string {
  return `job-${Date.now().toString(36)}`;
}

function baseSession(overrides: Partial<ProtocolSessionView>): ProtocolSessionView {
  return {
    jobType: "protocol_deconstruction",
    progressTotal: 10,
    sessionKind: "first_deconstruction",
    sourceArtifactId: "artifact-demo-1",
    snapshotId: "snapshot-demo-1",
    recoveryCheckpointId: null,
    recoveryStepId: null,
    ...overrides,
  } as ProtocolSessionView;
}

export function createProtocolWorkbenchStub(): ProtocolWorkbenchRepository {
  const sessions = new Map<string, ProtocolSessionView>([
    ...Object.entries(protocolSessionFixtures),
    [PROTOCOL_REDO_JOB_ID, protocolRedoSessionFixture],
  ]);

  return {
    kind: "stub",

    async startDeconstruction(
      file: File,
      _idempotencyKey: string,
      options?: ProtocolWorkbenchRequestOptions,
    ): Promise<StartDeconstructionResult> {
      rejectIfAborted(options?.signal);
      await delay();
      rejectIfAborted(options?.signal);
      const jobId = nextJobId();
      if (options?.projectId !== undefined && options.projectId.length > 0) {
        // 重新解构：目标项目持久保存于任务，任务进入身份确认等待。
        sessions.set(jobId, {
          ...protocolRedoSessionFixture,
          jobId,
          fileName: file.name,
          state: "await_identity",
          stateLabel: "等待方案信息确认",
          awaitingUser: "identity",
          awaitingUserLabel: "等待核对方案信息与研究期别",
          targetProjectId: options.projectId,
          nextAction: "核对方案编号、版本与研究期别；新版方案需与目标项目一致。",
        });
      } else {
        sessions.set(jobId, {
          ...protocolSessionFixtures[PROTOCOL_IDENTITY_JOB_ID]!,
          jobId,
          fileName: file.name,
        });
      }
      return {
        jobId,
        state: "await_identity",
        stateLabel: "等待方案信息确认",
        created: true,
        sourceArtifactId: `artifact-${jobId}`,
        fileName: file.name,
      };
    },

    async startFeedbackRevision(
      projectId: string,
      _idempotencyKey: string,
      options?: ProtocolWorkbenchRequestOptions,
    ): Promise<StartDeconstructionResult> {
      rejectIfAborted(options?.signal);
      await delay();
      const project = officialProjectsFixture.find((item) => item.projectId === projectId);
      if (project === undefined) {
        throw new ProtocolWorkbenchApiError(
          "PROJECT_NOT_FOUND",
          "找不到正式项目",
          "该项目编号不存在正式发布记录，无法建立反馈修订稿。",
          "请返回项目列表重新选择。",
        );
      }
      const jobId = nextJobId();
      sessions.set(jobId, {
        ...protocolRedoSessionFixture,
        jobId,
        targetProjectId: project.projectId,
        targetProjectName: project.projectName,
        targetProjectCode: project.projectCode,
        targetProtocolCode: project.protocolCode,
        targetStudyPhase: project.studyPhase,
        targetStudyPhaseLabel: project.studyPhaseLabel,
        targetOfficialVersion: project.officialVersion,
      });
      return {
        jobId,
        state: "waiting_user",
        stateLabel: "等待审阅",
        created: true,
        sourceArtifactId: "artifact-formal-source",
        fileName: "当前正式方案",
      };
    },

    async listOfficialProjects(
      options?: ProtocolWorkbenchRequestOptions,
    ): Promise<OfficialProjectView[]> {
      rejectIfAborted(options?.signal);
      await delay();
      return structuredClone(officialProjectsFixture);
    },

    async getProjectOfficialVersion(
      projectId: string,
      options?: ProtocolWorkbenchRequestOptions,
    ): Promise<ProjectOfficialVersionView> {
      rejectIfAborted(options?.signal);
      await delay();
      const project = officialProjectsFixture.find(
        (item) => item.projectId === projectId,
      );
      if (project === undefined) {
        throw new ProtocolWorkbenchApiError(
          "PROJECT_NOT_FOUND",
          "找不到正式项目",
          "该项目编号不存在正式发布记录，无法读取其正式版本。",
          "请返回项目列表重新选择，或先完成首次解构与发布。",
        );
      }
      return {
        ...projectOfficialVersionFixture,
        project: structuredClone(project),
      };
    },

    async getDraftComparison(
      jobId: string,
      options?: ProtocolWorkbenchRequestOptions,
    ): Promise<DraftComparisonView> {
      rejectIfAborted(options?.signal);
      await delay();
      if (jobId === PROTOCOL_REDO_JOB_ID || sessions.get(jobId)?.sessionKind === "re_deconstruction") {
        return { ...draftComparisonFixture, jobId };
      }
      throw new ProtocolWorkbenchApiError(
        "NOT_RE_DECONSTRUCTION_JOB",
        "不是重新解构任务",
        "只有重新解构任务提供“当前正式版本与新草稿”并列比较。",
        "请返回重新解构工作台选择项目后再比较。",
      );
    },

    async submitFeedback(
      jobId: string,
      input: FeedbackInput,
      options?: ProtocolWorkbenchRequestOptions,
    ): Promise<DraftRevisionView> {
      rejectIfAborted(options?.signal);
      await delay();
      if (
        input.expectedRevisionId !== draftRevisionFixture.revisionId &&
        input.expectedRevisionId !== draftComparisonFixture.candidate.revisionId
      ) {
        throw new ProtocolWorkbenchApiError(
          "REVISION_CONFLICT",
          "草稿版本已更新",
          "其他窗口已保存较新的草稿，当前编辑基于过期版本。",
          "刷新页面加载最新草稿后再继续编辑。",
        );
      }
      return {
        ...draftRevisionFixture,
        jobId,
        revisionNumber: 2,
        statusLabel: input.feedbackKind === "clarification" ? "已记录补充解释" : "已记录原文纠错",
        reasonLabel: input.feedbackKind === "clarification" ? "补充解释" : "原文理解纠错",
      };
    },

    async editDraft(
      jobId: string,
      input: ManualEditInput,
      options?: ProtocolWorkbenchRequestOptions,
    ): Promise<DraftRevisionView> {
      rejectIfAborted(options?.signal);
      await delay();
      if (
        input.expectedRevisionId !== draftRevisionFixture.revisionId &&
        input.expectedRevisionId !== draftComparisonFixture.candidate.revisionId
      ) {
        throw new ProtocolWorkbenchApiError(
          "REVISION_CONFLICT",
          "草稿版本已更新",
          "其他窗口已保存较新的草稿，当前编辑基于过期版本。",
          "刷新页面加载最新草稿后再继续编辑。",
        );
      }
      return {
        ...draftRevisionFixture,
        jobId,
        revisionNumber: 2,
        statusLabel: "已保存草稿（手工修订）",
        reasonLabel: "手工修订",
      };
    },

    async cancelDraft(
      jobId: string,
      expectedRevisionId: string,
      options?: ProtocolWorkbenchRequestOptions,
    ): Promise<DraftRevisionView> {
      rejectIfAborted(options?.signal);
      await delay();
      if (
        expectedRevisionId !== draftRevisionFixture.revisionId &&
        expectedRevisionId !== draftComparisonFixture.candidate.revisionId
      ) {
        throw new ProtocolWorkbenchApiError(
          "REVISION_CONFLICT",
          "草稿版本已更新",
          "其他窗口已保存较新的草稿，当前编辑基于过期版本。",
          "刷新页面加载最新草稿后再继续编辑。",
        );
      }
      return {
        ...draftRevisionFixture,
        jobId,
        status: "cancelled",
        statusLabel: "已取消",
      };
    },

    async getSession(
      jobId: string,
      options?: ProtocolWorkbenchRequestOptions,
    ): Promise<ProtocolSessionView> {
      rejectIfAborted(options?.signal);
      await delay();
      rejectIfAborted(options?.signal);
      const session = sessions.get(jobId);
      if (session === undefined) {
        throw new ProtocolWorkbenchApiError(
          "NOT_FOUND",
          "任务不存在",
          "未找到该方案解构任务，可能已过期或被删除。",
          "返回方案工作台首页，重新上传方案文件。",
        );
      }
      return session;
    },

    async retryFailedStep(
      jobId: string,
      options?: ProtocolWorkbenchRequestOptions,
    ): Promise<void> {
      rejectIfAborted(options?.signal);
      await delay();
      rejectIfAborted(options?.signal);
      const session = sessions.get(jobId);
      if (session === undefined) {
        throw new ProtocolWorkbenchApiError(
          "NOT_FOUND",
          "任务不存在",
          "未找到该方案解构任务。",
          "返回方案工作台首页。",
        );
      }
      sessions.set(jobId, {
        ...session,
        state: "queued",
        stateLabel: "等待执行",
        nextAction: "将从上次失败的步骤继续，已完成内容不会重复处理。",
      });
    },

    async getIdentityReview(
      jobId: string,
      options?: ProtocolWorkbenchRequestOptions,
    ): Promise<IdentityReviewView> {
      rejectIfAborted(options?.signal);
      await delay();
      rejectIfAborted(options?.signal);
      if (jobId === PROTOCOL_IDENTITY_JOB_ID || sessions.has(jobId)) {
        return { ...identityReviewFixture, jobId };
      }
      throw new ProtocolWorkbenchApiError(
        "IDENTITY_NOT_READY",
        "方案信息尚未就绪",
        "方案结构仍在提取中，暂时无法核对方案信息与研究期别。",
        "请稍候刷新，或从恢复入口继续任务。",
      );
    },

    async confirmIdentity(
      jobId: string,
      input: ConfirmIdentityInput,
      options?: ProtocolWorkbenchRequestOptions,
    ): Promise<ProtocolSessionView> {
      rejectIfAborted(options?.signal);
      await delay();
      rejectIfAborted(options?.signal);
      const confirmed = baseSession({
        jobId,
        state: "await_review",
        stateLabel: "等待审阅",
        progressCompleted: 7,
        awaitingUser: "review",
        awaitingUserLabel: "等待审阅草稿",
        selectedPhase: input.studyPhase,
        selectedPhaseLabel: studyPhaseLabel[input.studyPhase],
        protocolCode: input.protocolCode,
        officialVersion: input.officialVersion,
        draftId: draftRevisionFixture.draftId,
        draftRevisionId: draftRevisionFixture.revisionId,
        draftRevisionNumber: draftRevisionFixture.revisionNumber,
        draftStatus: draftRevisionFixture.status,
        draftStatusLabel: draftRevisionFixture.statusLabel,
        nextAction: "审阅草稿第 1 稿并核对来源定位",
        publishable: true,
        fileName: sessions.get(jobId)?.fileName ?? "方案.docx",
      });
      sessions.set(jobId, confirmed);
      return confirmed;
    },

    async getDraft(
      jobId: string,
      options?: ProtocolWorkbenchRequestOptions,
    ): Promise<DraftRevisionView> {
      rejectIfAborted(options?.signal);
      await delay();
      rejectIfAborted(options?.signal);
      if (jobId === PROTOCOL_DEMO_JOB_ID || sessions.get(jobId)?.awaitingUser === "review") {
        return { ...draftRevisionFixture, jobId };
      }
      throw new ProtocolWorkbenchApiError(
        "DRAFT_NOT_READY",
        "草稿尚未生成",
        "当前任务尚未进入草稿审阅阶段。",
        "先完成方案信息与研究期别核对，或等待后台任务完成。",
      );
    },

    async getIntegrity(
      jobId: string,
      options?: ProtocolWorkbenchRequestOptions,
    ): Promise<IntegrityView> {
      rejectIfAborted(options?.signal);
      await delay();
      return { ...integrityFixture, jobId };
    },

    async getSources(
      jobId: string,
      options?: ProtocolWorkbenchRequestOptions,
    ): Promise<SourcesView> {
      rejectIfAborted(options?.signal);
      await delay();
      return { ...sourcesFixture, jobId };
    },

    async saveDraft(
      jobId: string,
      expectedRevisionId: string,
      options?: ProtocolWorkbenchRequestOptions,
    ): Promise<DraftRevisionView> {
      rejectIfAborted(options?.signal);
      await delay();
      if (expectedRevisionId !== draftRevisionFixture.revisionId) {
        throw new ProtocolWorkbenchApiError(
          "REVISION_CONFLICT",
          "草稿版本已更新",
          "其他窗口已保存较新的草稿，当前编辑基于过期版本。",
          "刷新页面加载最新草稿后再继续编辑。",
        );
      }
      return { ...draftRevisionFixture, jobId, statusLabel: "已保存" };
    },

    async publish(
      jobId: string,
      _idempotencyKey: string,
      options?: ProtocolWorkbenchRequestOptions,
    ): Promise<PublishResultView> {
      rejectIfAborted(options?.signal);
      await delay();
      return {
        jobId,
        projectId: "project-published-1",
        protocolVersionId: "protocol-version-published-1",
        ruleSetId: "ruleset-published-1",
        ruleSetRevision: 1,
        replay: false,
      };
    },
  };
}

export {
  PROTOCOL_DEMO_JOB_ID,
  PROTOCOL_IDENTITY_JOB_ID,
  PROTOCOL_RECOVERY_JOB_ID,
  PROTOCOL_REDO_JOB_ID,
};
