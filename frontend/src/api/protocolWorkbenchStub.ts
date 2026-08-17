/**
 * 方案解构工作台 stub 仓储：仅用于组件测试、Playwright 与显式 UAT 注入。
 */

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
import type {
  ProtocolWorkbenchRepository,
  ProtocolWorkbenchRequestOptions,
} from "./protocolWorkbenchRepository";
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
    progressTotal: 9,
    sessionKind: "first_deconstruction",
    sourceArtifactId: "artifact-demo-1",
    snapshotId: "snapshot-demo-1",
    recoveryCheckpointId: null,
    recoveryStepId: null,
    ...overrides,
  } as ProtocolSessionView;
}

export function createProtocolWorkbenchStub(): ProtocolWorkbenchRepository {
  const sessions = new Map<string, ProtocolSessionView>(
    Object.entries(protocolSessionFixtures),
  );

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
      sessions.set(jobId, {
        ...protocolSessionFixtures[PROTOCOL_IDENTITY_JOB_ID]!,
        jobId,
        fileName: file.name,
      });
      return {
        jobId,
        state: "await_identity",
        stateLabel: "等待方案信息确认",
        created: true,
        sourceArtifactId: `artifact-${jobId}`,
        fileName: file.name,
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
};
