/**
 * 方案解构工作台数据访问：默认 HTTP；stub 仅通过显式注入或构建时测试模式启用。
 */

import { isProtocolWorkbenchStubMode } from "./protocolApiConfig";
import { createProtocolWorkbenchHttp } from "./protocolWorkbenchHttp";
import { createProtocolWorkbenchStub } from "./protocolWorkbenchStub";
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

export { ProtocolWorkbenchApiError } from "./protocolWorkbenchTypes";
export {
  PROTOCOL_DEMO_JOB_ID,
  PROTOCOL_IDENTITY_JOB_ID,
  PROTOCOL_RECOVERY_JOB_ID,
} from "./protocolWorkbenchStub";

export interface ProtocolWorkbenchRequestOptions {
  signal?: AbortSignal;
}

export interface ProtocolWorkbenchRepository {
  readonly kind: "stub" | "http";
  startDeconstruction(
    file: File,
    idempotencyKey: string,
    options?: ProtocolWorkbenchRequestOptions,
  ): Promise<StartDeconstructionResult>;
  getSession(
    jobId: string,
    options?: ProtocolWorkbenchRequestOptions,
  ): Promise<ProtocolSessionView>;
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
  getIntegrity(
    jobId: string,
    options?: ProtocolWorkbenchRequestOptions,
  ): Promise<IntegrityView>;
  getSources(
    jobId: string,
    options?: ProtocolWorkbenchRequestOptions,
  ): Promise<SourcesView>;
  saveDraft(
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
