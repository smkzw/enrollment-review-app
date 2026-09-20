/**
 * 方案解构工作台 HTTP 仓储：multipart 上传、错误信封解码、wire 归一化。
 */

import {
  protocolDeconstructionsUrl,
  protocolJobsUrl,
  protocolProjectsUrl,
} from "./protocolApiConfig";
import {
  decodeProtocolWorkbenchError,
  encodeConfirmIdentity,
  encodeFeedback,
  encodeManualEdit,
  normalizeDraftComparison,
  normalizeDraftRevision,
  normalizeGenerationPreview,
  normalizeIdentityReview,
  normalizeIntegrity,
  normalizeOfficialProjectList,
  normalizeProjectOfficialVersion,
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

  async function projectsRequest<T>(
    pathSuffix: string,
    init: RequestInit,
    normalize: (payload: unknown) => T,
  ): Promise<T> {
    const response = await fetchImpl(protocolProjectsUrl(pathSuffix), init);
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
      options?: ProtocolWorkbenchRequestOptions & { projectId?: string },
    ): Promise<StartDeconstructionResult> {
      const body = new FormData();
      body.append("file", file);
      body.append("idempotency_key", idempotencyKey);
      body.append("actor", "用户");
      if (options?.projectId !== undefined && options.projectId.length > 0) {
        body.append("project_id", options.projectId);
      }
      const result = await request(
        "",
        { method: "POST", body, signal: options?.signal },
        normalizeStartDeconstruction,
      );
      return result;
    },

    async startFeedbackRevision(
      projectId: string,
      idempotencyKey: string,
      options?: ProtocolWorkbenchRequestOptions,
    ): Promise<StartDeconstructionResult> {
      return request(
        "/from-formal",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            project_id: projectId,
            idempotency_key: idempotencyKey,
            actor: "用户",
          }),
          signal: options?.signal,
        },
        normalizeStartDeconstruction,
      );
    },

    async listOfficialProjects(
      options?: ProtocolWorkbenchRequestOptions,
    ): Promise<OfficialProjectView[]> {
      return projectsRequest(
        "",
        { method: "GET", signal: options?.signal },
        normalizeOfficialProjectList,
      );
    },

    async getProjectOfficialVersion(
      projectId: string,
      options?: ProtocolWorkbenchRequestOptions,
    ): Promise<ProjectOfficialVersionView> {
      return projectsRequest(
        `/${encodeURIComponent(projectId)}`,
        { method: "GET", signal: options?.signal },
        normalizeProjectOfficialVersion,
      );
    },

    async getDraftComparison(
      jobId: string,
      options?: ProtocolWorkbenchRequestOptions,
    ): Promise<DraftComparisonView> {
      return request(
        `/${encodeURIComponent(jobId)}/draft/comparison`,
        { method: "GET", signal: options?.signal },
        normalizeDraftComparison,
      );
    },

    async submitFeedback(
      jobId: string,
      input: FeedbackInput,
      options?: ProtocolWorkbenchRequestOptions,
    ): Promise<DraftRevisionView> {
      return request(
        `/${encodeURIComponent(jobId)}/draft/feedback`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(encodeFeedback(input)),
          signal: options?.signal,
        },
        normalizeDraftRevision,
      );
    },

    editDraft(
      jobId: string,
      input: ManualEditInput,
      options?: ProtocolWorkbenchRequestOptions,
    ): Promise<DraftRevisionView> {
      return request(
        `/${encodeURIComponent(jobId)}/draft`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(encodeManualEdit(input)),
          signal: options?.signal,
        },
        normalizeDraftRevision,
      );
    },

    async cancelDraft(
      jobId: string,
      expectedRevisionId: string,
      options?: ProtocolWorkbenchRequestOptions,
    ): Promise<DraftRevisionView> {
      return request(
        `/${encodeURIComponent(jobId)}/draft/cancel`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ expected_revision_id: expectedRevisionId }),
          signal: options?.signal,
        },
        normalizeDraftRevision,
      );
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

    async retryFailedStep(
      jobId: string,
      options?: ProtocolWorkbenchRequestOptions,
    ): Promise<void> {
      const response = await fetchImpl(
        protocolJobsUrl(`/${encodeURIComponent(jobId)}/retry`),
        { method: "POST", signal: options?.signal },
      );
      const payload = await readJson(response);
      if (!response.ok) throw decodeProtocolWorkbenchError(payload);
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

    getGenerationPreview(
      jobId: string,
      options?: ProtocolWorkbenchRequestOptions,
    ): Promise<GenerationPreviewView> {
      return request(
        `/${encodeURIComponent(jobId)}/draft/generation-preview`,
        { method: "GET", signal: options?.signal },
        normalizeGenerationPreview,
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
          body: JSON.stringify({ idempotency_key: idempotencyKey, actor: "用户",
            ...(options?.controlPublication ? {
              control_job_id: options.controlPublication.jobId,
              control_checkpoint_id: options.controlPublication.checkpointId,
            } : {}),
          }),
          signal: options?.signal,
        },
        normalizePublishResult,
      );
    },
  };
}
