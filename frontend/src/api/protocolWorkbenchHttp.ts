/**
 * 方案解构工作台 HTTP 仓储：multipart 上传、错误信封解码、wire 归一化。
 */

import type { StudyPhase } from "../domain/enums";
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
  WorkbenchEntryJobView,
  WorkbenchEntryProjectView,
  WorkbenchProjectEntryState,
  WorkbenchProjectEntryView,
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
      if (
        options?.workbenchOrigin !== undefined &&
        options.workbenchOrigin.length > 0
      ) {
        // 共享工作台来源只作为任务元数据随上传持久保存；方案身份、
        // 身份确认与联合发布仍由既有流程裁定。
        body.append("workbench_origin", options.workbenchOrigin);
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
            ...(options?.workbenchOrigin !== undefined
              ? { workbench_origin: options.workbenchOrigin } : {}),
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

// ---------------------------------------------------------------------------
// 共享工作台来源（workbench:<shared_project_id>）：只读入口解析
//
// 来源是元数据，不是方案身份；已绑定的任务/项目由服务端按持久身份解析，
// 不使用 localStorage 作为权威映射。共享侧目前尚未产出命名空间来源
// （共享 manifest 的 eligibility 路由绑定缺口在 WORKBENCH_ADAPTATION_20261007
// 单独记录），因此这里只提供真实 HTTP 查询，stub 仓储不伪造来源数据。
// ---------------------------------------------------------------------------

const WORKBENCH_ENTRY_STATES: ReadonlyArray<WorkbenchProjectEntryState> = [
  "unbound",
  "job_in_progress",
  "project_published",
];

function entryRecord(value: unknown): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw decodeProtocolWorkbenchError(null);
  }
  return value as Record<string, unknown>;
}

function entryRequiredString(value: unknown): string {
  if (typeof value !== "string" || value.length === 0) {
    throw decodeProtocolWorkbenchError(null);
  }
  return value;
}

function entryOptionalString(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function entryOptionalBoolean(value: unknown): boolean | null {
  return typeof value === "boolean" ? value : null;
}

function entryRequiredNumber(value: unknown): number {
  if (typeof value !== "number" || !Number.isInteger(value) || value < 1) {
    throw decodeProtocolWorkbenchError(null);
  }
  return value;
}

function entryStudyPhase(value: unknown): StudyPhase {
  const candidate = entryRequiredString(value);
  if (
    candidate !== "phase_ii" &&
    candidate !== "phase_iii" &&
    candidate !== "seamless_phase_ii_iii" &&
    candidate !== "other"
  ) {
    throw decodeProtocolWorkbenchError(null);
  }
  return candidate;
}

function normalizeEntryProject(raw: unknown): WorkbenchEntryProjectView {
  const row = entryRecord(raw);
  return {
    projectId: entryRequiredString(row.project_id),
    projectCode: entryRequiredString(row.project_code),
    projectName: entryRequiredString(row.project_name),
    studyPhase: entryStudyPhase(row.study_phase),
    studyPhaseLabel: entryRequiredString(row.study_phase_label),
    protocolCode: entryRequiredString(row.protocol_code),
    officialVersion: entryRequiredString(row.official_version),
    ruleSetId: entryRequiredString(row.rule_set_id),
    ruleSetRevision: entryRequiredNumber(row.rule_set_revision),
  };
}

function normalizeEntryJob(raw: unknown): WorkbenchEntryJobView {
  const job = entryRecord(raw);
  return {
    jobId: entryRequiredString(job.job_id),
    state: entryOptionalString(job.state),
    stateLabel: entryOptionalString(job.state_label),
    sessionKind: entryOptionalString(job.session_kind),
    awaitingUser: entryOptionalString(job.awaiting_user),
    awaitingUserLabel: entryOptionalString(job.awaiting_user_label),
    publishable: entryOptionalBoolean(job.publishable),
    fileName: entryOptionalString(job.file_name),
  };
}

export function normalizeWorkbenchProjectEntry(
  payload: unknown,
): WorkbenchProjectEntryView {
  const row = entryRecord(payload);
  const rawState = entryRequiredString(row.entry_state);
  if (!WORKBENCH_ENTRY_STATES.includes(rawState as WorkbenchProjectEntryState)) {
    throw decodeProtocolWorkbenchError(null);
  }
  const rawJob = row.job;
  const rawProject = row.project;
  const entry: WorkbenchProjectEntryView = {
    origin: entryRequiredString(row.origin),
    entryState: rawState as WorkbenchProjectEntryState,
    job:
      rawJob === null || rawJob === undefined ? null : normalizeEntryJob(rawJob),
    project:
      rawProject === null || rawProject === undefined
        ? null
        : normalizeEntryProject(rawProject),
  };
  if ((entry.entryState === "unbound" && (entry.job !== null || entry.project !== null)) ||
      (entry.entryState === "job_in_progress" && entry.job === null) ||
      (entry.entryState === "project_published" && entry.project === null)) {
    throw decodeProtocolWorkbenchError(null);
  }
  return entry;
}

/** 按持久身份解析共享工作台来源；未绑定时返回 entry_state="unbound"。 */
export async function fetchWorkbenchProjectEntry(
  origin: string,
  options: { signal?: AbortSignal; fetchImpl?: typeof fetch } = {},
): Promise<WorkbenchProjectEntryView> {
  const fetchImpl = options.fetchImpl ?? fetch.bind(globalThis);
  const response = await fetchImpl(
    protocolProjectsUrl(`/workbench-origins/${encodeURIComponent(origin)}`),
    { method: "GET", signal: options.signal },
  );
  const payload = await readJson(response);
  if (!response.ok) {
    throw decodeProtocolWorkbenchError(payload);
  }
  const entry = normalizeWorkbenchProjectEntry(payload);
  if (entry.origin !== origin) throw decodeProtocolWorkbenchError(null);
  return entry;
}
