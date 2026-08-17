/**
 * 方案解构工作台数据访问：stub 模拟各阶段；真实 API 通过 HTTP 客户端替换。
 */

import type {
  ConfirmIdentityInput,
  DraftRevisionView,
  IdentityReviewView,
  IntegrityView,
  ProtocolSessionView,
  PublishResultView,
  SourcesView,
  StartDeconstructionResult,
} from "./protocolWorkbenchTypes";
import {
  draftRevisionFixture,
  identityReviewFixture,
  integrityFixture,
  protocolSessionFixtures,
  PROTOCOL_DEMO_JOB_ID,
  PROTOCOL_IDENTITY_JOB_ID,
  PROTOCOL_RECOVERY_JOB_ID,
  sourcesFixture,
} from "../fixtures/protocol-deconstruction-workbench";

export class ProtocolWorkbenchApiError extends Error {
  readonly code: string;
  readonly title: string;
  readonly recoveryAction: string;

  constructor(code: string, title: string, message: string, recoveryAction: string) {
    super(message);
    this.name = "ProtocolWorkbenchApiError";
    this.code = code;
    this.title = title;
    this.recoveryAction = recoveryAction;
  }
}

export interface ProtocolWorkbenchRepository {
  readonly kind: "stub" | "http";
  startDeconstruction(file: File, idempotencyKey: string): Promise<StartDeconstructionResult>;
  getSession(jobId: string): Promise<ProtocolSessionView>;
  getIdentityReview(jobId: string): Promise<IdentityReviewView>;
  confirmIdentity(jobId: string, input: ConfirmIdentityInput): Promise<ProtocolSessionView>;
  getDraft(jobId: string): Promise<DraftRevisionView>;
  getIntegrity(jobId: string): Promise<IntegrityView>;
  getSources(jobId: string): Promise<SourcesView>;
  saveDraft(jobId: string, expectedRevisionId: string): Promise<DraftRevisionView>;
  publish(jobId: string, idempotencyKey: string): Promise<PublishResultView>;
}

const LATENCY_MS = 40;

function delay(ms: number = LATENCY_MS): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function nextJobId(): string {
  return `job-${Date.now().toString(36)}`;
}

export function createProtocolWorkbenchStub(): ProtocolWorkbenchRepository {
  const sessions = new Map<string, ProtocolSessionView>(
    Object.entries(protocolSessionFixtures),
  );

  return {
    kind: "stub",

    async startDeconstruction(file: File, _idempotencyKey: string): Promise<StartDeconstructionResult> {
      await delay();
      const jobId = nextJobId();
      sessions.set(
        jobId,
        protocolSessionFixtures[PROTOCOL_IDENTITY_JOB_ID]!.jobId === PROTOCOL_IDENTITY_JOB_ID
          ? {
              ...protocolSessionFixtures[PROTOCOL_IDENTITY_JOB_ID]!,
              jobId,
              fileName: file.name,
            }
          : {
              ...protocolSessionFixtures[PROTOCOL_IDENTITY_JOB_ID]!,
              jobId,
              fileName: file.name,
            },
      );
      return {
        jobId,
        state: "await_identity",
        stateLabel: "等待身份确认",
        created: true,
        sourceArtifactId: `artifact-${jobId}`,
        fileName: file.name,
      };
    },

    async getSession(jobId: string): Promise<ProtocolSessionView> {
      await delay();
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

    async getIdentityReview(jobId: string): Promise<IdentityReviewView> {
      await delay();
      if (jobId === PROTOCOL_IDENTITY_JOB_ID || sessions.has(jobId)) {
        return { ...identityReviewFixture, jobId };
      }
      throw new ProtocolWorkbenchApiError(
        "IDENTITY_NOT_READY",
        "身份信息尚未就绪",
        "方案结构仍在提取中，暂时无法核对身份与期别。",
        "请稍候刷新，或从恢复入口继续任务。",
      );
    },

    async confirmIdentity(jobId: string, input: ConfirmIdentityInput): Promise<ProtocolSessionView> {
      await delay();
      const confirmed = baseSession({
        jobId,
        state: "await_review",
        stateLabel: "等待审阅",
        progressCompleted: 7,
        awaitingUser: "review",
        awaitingUserLabel: "等待审阅草稿",
        selectedPhase: input.studyPhase,
        selectedPhaseLabel: input.studyPhase === "phase_ii" ? "II 期" : input.studyPhase,
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

    async getDraft(jobId: string): Promise<DraftRevisionView> {
      await delay();
      if (jobId === PROTOCOL_DEMO_JOB_ID || sessions.get(jobId)?.awaitingUser === "review") {
        return { ...draftRevisionFixture, jobId };
      }
      throw new ProtocolWorkbenchApiError(
        "DRAFT_NOT_READY",
        "草稿尚未生成",
        "当前任务尚未进入草稿审阅阶段。",
        "先完成身份与期别确认，或等待后台任务完成。",
      );
    },

    async getIntegrity(jobId: string): Promise<IntegrityView> {
      await delay();
      return { ...integrityFixture, jobId };
    },

    async getSources(jobId: string): Promise<SourcesView> {
      await delay();
      return { ...sourcesFixture, jobId };
    },

    async saveDraft(jobId: string, expectedRevisionId: string): Promise<DraftRevisionView> {
      await delay();
      if (expectedRevisionId !== draftRevisionFixture.revisionId) {
        throw new ProtocolWorkbenchApiError(
          "REVISION_CONFLICT",
          "草稿版本已更新",
          "其他窗口已保存较新的草稿，当前编辑基于过期版本。",
          "刷新页面加载最新草稿第 N 稿后再继续编辑。",
        );
      }
      return { ...draftRevisionFixture, jobId, statusLabel: "已保存" };
    },

    async publish(jobId: string): Promise<PublishResultView> {
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

function baseSession(overrides: Partial<ProtocolSessionView>): ProtocolSessionView {
  return {
    jobType: "protocol_deconstruction",
    progressTotal: 9,
    sessionKind: "first_deconstruction",
    sourceArtifactId: "artifact-demo-1",
    snapshotId: "snapshot-demo-1",
    recoveryCheckpointId: null,
    recoveryStepId: null,
    ...overrides,
  } as ProtocolSessionView;
}

let defaultRepo: ProtocolWorkbenchRepository | null = null;

export function getProtocolWorkbenchRepository(): ProtocolWorkbenchRepository {
  if (defaultRepo === null) {
    defaultRepo = createProtocolWorkbenchStub();
  }
  return defaultRepo;
}

/** 测试注入 */
export function setProtocolWorkbenchRepository(
  repo: ProtocolWorkbenchRepository | null,
): void {
  defaultRepo = repo;
}

export {
  PROTOCOL_DEMO_JOB_ID,
  PROTOCOL_IDENTITY_JOB_ID,
  PROTOCOL_RECOVERY_JOB_ID,
};