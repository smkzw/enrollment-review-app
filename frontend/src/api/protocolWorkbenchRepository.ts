/**
 * 方案解构工作台数据访问：默认 HTTP；stub 仅通过显式注入或构建时测试模式启用。
 */

import { isProtocolWorkbenchStubMode } from "./protocolApiConfig";
import { createProtocolWorkbenchHttp } from "./protocolWorkbenchHttp";
import { createProtocolWorkbenchStub } from "./protocolWorkbenchStub";
import type {
  ConfirmIdentityInput,
  DraftComparisonView,
  DraftRevisionView,
  FeedbackInput,
  GenerationPreviewView,
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

export { ProtocolWorkbenchApiError } from "./protocolWorkbenchTypes";
export {
  PROTOCOL_DEMO_JOB_ID,
  PROTOCOL_IDENTITY_JOB_ID,
  PROTOCOL_RECOVERY_JOB_ID,
  PROTOCOL_REDO_JOB_ID,
} from "./protocolWorkbenchStub";

export interface ProtocolWorkbenchRequestOptions {
  signal?: AbortSignal;
  /** 重新解构：上传目标正式项目编号（非空时进入重新解构路径）。 */
  projectId?: string;
  /** 用户正在审阅的补充要求版本；仅用于发布，不能用最新结果替代。 */
  controlPublication?: { jobId: string; checkpointId: string };
}

export interface ProtocolWorkbenchRepository {
  readonly kind: "stub" | "http";
  startDeconstruction(
    file: File,
    idempotencyKey: string,
    options?: ProtocolWorkbenchRequestOptions,
  ): Promise<StartDeconstructionResult>;
  startFeedbackRevision(
    projectId: string,
    idempotencyKey: string,
    options?: ProtocolWorkbenchRequestOptions,
  ): Promise<StartDeconstructionResult>;
  listOfficialProjects(
    options?: ProtocolWorkbenchRequestOptions,
  ): Promise<OfficialProjectView[]>;
  getProjectOfficialVersion(
    projectId: string,
    options?: ProtocolWorkbenchRequestOptions,
  ): Promise<ProjectOfficialVersionView>;
  getSession(
    jobId: string,
    options?: ProtocolWorkbenchRequestOptions,
  ): Promise<ProtocolSessionView>;
  retryFailedStep(
    jobId: string,
    options?: ProtocolWorkbenchRequestOptions,
  ): Promise<void>;
  getIdentityReview(
    jobId: string,
    options?: ProtocolWorkbenchRequestOptions,
  ): Promise<IdentityReviewView>;
  confirmIdentity(
    jobId: string,
    input: ConfirmIdentityInput,
    options?: ProtocolWorkbenchRequestOptions,
  ): Promise<ProtocolSessionView>;
  getDraft(
    jobId: string,
    options?: ProtocolWorkbenchRequestOptions,
  ): Promise<DraftRevisionView>;
  getDraftComparison(
    jobId: string,
    options?: ProtocolWorkbenchRequestOptions,
  ): Promise<DraftComparisonView>;
  getIntegrity(
    jobId: string,
    options?: ProtocolWorkbenchRequestOptions,
  ): Promise<IntegrityView>;
  getSources(
    jobId: string,
    options?: ProtocolWorkbenchRequestOptions,
  ): Promise<SourcesView>;
  /** 生成期间逐批只读预览（不可发布；正式草稿仍以 getDraft 为准）。 */
  getGenerationPreview(
    jobId: string,
    options?: ProtocolWorkbenchRequestOptions,
  ): Promise<GenerationPreviewView>;
  saveDraft(
    jobId: string,
    expectedRevisionId: string,
    options?: ProtocolWorkbenchRequestOptions,
  ): Promise<DraftRevisionView>;
  submitFeedback(
    jobId: string,
    input: FeedbackInput,
    options?: ProtocolWorkbenchRequestOptions,
  ): Promise<DraftRevisionView>;
  /** 手工修订草稿（继续编辑）：PUT /draft，乐观并发校验链头。 */
  editDraft(
    jobId: string,
    input: ManualEditInput,
    options?: ProtocolWorkbenchRequestOptions,
  ): Promise<DraftRevisionView>;
  cancelDraft(
    jobId: string,
    expectedRevisionId: string,
    options?: ProtocolWorkbenchRequestOptions,
  ): Promise<DraftRevisionView>;
  publish(
    jobId: string,
    idempotencyKey: string,
    options?: ProtocolWorkbenchRequestOptions,
  ): Promise<PublishResultView>;
}

let defaultRepo: ProtocolWorkbenchRepository | null = null;

function createDefaultRepository(): ProtocolWorkbenchRepository {
  if (isProtocolWorkbenchStubMode()) {
    return createProtocolWorkbenchStub();
  }
  return createProtocolWorkbenchHttp();
}

export function getProtocolWorkbenchRepository(): ProtocolWorkbenchRepository {
  if (defaultRepo === null) {
    defaultRepo = createDefaultRepository();
  }
  return defaultRepo;
}

/** 测试或 UAT 显式注入 stub / HTTP 实现。 */
export function setProtocolWorkbenchRepository(
  repo: ProtocolWorkbenchRepository | null,
): void {
  defaultRepo = repo;
}

export { createProtocolWorkbenchStub, createProtocolWorkbenchHttp };
