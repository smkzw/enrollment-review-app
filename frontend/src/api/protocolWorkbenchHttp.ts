/**
 * 方案解构工作台 HTTP 仓储：multipart 上传、错误信封解码、wire 归一化。
 */

import { protocolDeconstructionsUrl } from "./protocolApiConfig";
import {
  decodeProtocolWorkbenchError,
  encodeConfirmIdentity,
  normalizeDraftRevision,
  normalizeIdentityReview,
  normalizeIntegrity,
  normalizePublishResult,
  normalizeSession,
  normalizeSources,
  normalizeStartDeconstruction,
} from "./protocolWorkbenchNormalize";
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
export interface ProtocolWorkbenchHttpOptions {
  fetchImpl?: typeof fetch;
}

async function readJson(response: Response): Promise<unknown> {
  const text = await response.text();
  if (text.length === 0) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return null;
  }
}

export function createProtocolWorkbenchHttp(
  options: ProtocolWorkbenchHttpOptions = {},
): ProtocolWorkbenchRepository {
  const fetchImpl = options.fetchImpl ?? fetch.bind(globalThis);

  async function request<T>(
    pathSuffix: string,
    init: RequestInit,
    normalize: (payload: unknown) => T,
  ): Promise<T> {
    const response = await fetchImpl(protocolDeconstructionsUrl(pathSuffix), init);
    const payload = await readJson(response);
    if (!response.ok) {
      throw decodeProtocolWorkbenchError(payload);
    }
    if (payload === null || typeof payload !== "object") {
      throw decodeProtocolWorkbenchError(null);
    }
    return normalize(payload);
  }

  return {
    kind: "http",

    async startDeconstruction(
      file: File,
      idempotencyKey: string,
      options?: ProtocolWorkbenchRequestOptions,
    ): Promise<StartDeconstructionResult> {
      const body = new FormData();
      body.append("file", file);
      body.append("idempotency_key", idempotencyKey);
      body.append("actor", "用户");
      const result = await request(
        "",
        { method: "POST", body, signal: options?.signal },
        normalizeStartDeconstruction,
      );
      return result;
    },

    getSession(
      jobId: string,
      options?: ProtocolWorkbenchRequestOptions,
    ): Promise<ProtocolSessionView> {
      return request(
        `/${encodeURIComponent(jobId)}`,
        { method: "GET", signal: options?.signal },
        normalizeSession,
      );
    },

    getIdentityReview(
      jobId: string,
      options?: ProtocolWorkbenchRequestOptions,
    ): Promise<IdentityReviewView> {
      return request(
        `/${encodeURIComponent(jobId)}/identity`,
        { method: "GET", signal: options?.signal },
        normalizeIdentityReview,
      );
    },

    confirmIdentity(
      jobId: string,
      input: ConfirmIdentityInput,
      options?: ProtocolWorkbenchRequestOptions,
    ): Promise<ProtocolSessionView> {
      return request(
        `/${encodeURIComponent(jobId)}/identity/confirm`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(encodeConfirmIdentity(input)),
          signal: options?.signal,
        },
        normalizeSession,
      );
    },

    getDraft(
      jobId: string,
      options?: ProtocolWorkbenchRequestOptions,
    ): Promise<DraftRevisionView> {
      return request(
        `/${encodeURIComponent(jobId)}/draft`,
        { method: "GET", signal: options?.signal },
        normalizeDraftRevision,
      );
    },

    getIntegrity(
      jobId: string,
      options?: ProtocolWorkbenchRequestOptions,
    ): Promise<IntegrityView> {
      return request(
        `/${encodeURIComponent(jobId)}/integrity`,
        { method: "GET", signal: options?.signal },
        normalizeIntegrity,
      );
    },

    getSources(
      jobId: string,
      options?: ProtocolWorkbenchRequestOptions,
    ): Promise<SourcesView> {
      return request(
        `/${encodeURIComponent(jobId)}/sources`,
        { method: "GET", signal: options?.signal },
        normalizeSources,
      );
    },

    saveDraft(
      jobId: string,
      expectedRevisionId: string,
      options?: ProtocolWorkbenchRequestOptions,
    ): Promise<DraftRevisionView> {
      return request(
        `/${encodeURIComponent(jobId)}/draft/save`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ expected_revision_id: expectedRevisionId }),
          signal: options?.signal,
        },
        normalizeDraftRevision,
      );
    },

    publish(
      jobId: string,
      idempotencyKey: string,
      options?: ProtocolWorkbenchRequestOptions,
    ): Promise<PublishResultView> {
      return request(
        `/${encodeURIComponent(jobId)}/publish`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ idempotency_key: idempotencyKey, actor: "用户" }),
          signal: options?.signal,
        },
        normalizePublishResult,
      );
    },
  };
}
