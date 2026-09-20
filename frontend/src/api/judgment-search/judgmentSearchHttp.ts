import { getProtocolApiBase } from "../protocolApiConfig";
import {
  JUDGMENT_SEARCH_CHANNELS,
  JUDGMENT_SEARCH_JOB_STATES,
  JUDGMENT_SEARCH_LANES,
  JUDGMENT_SEARCH_RESULT_STATUSES,
  type JudgmentSearchBoundingBoxView,
  type JudgmentSearchCandidateView,
  type JudgmentSearchChannel,
  type JudgmentSearchExcerptView,
  type JudgmentSearchIncompletePageView,
  type JudgmentSearchJobState,
  type JudgmentSearchLane,
  type JudgmentSearchRequirementResultView,
  type JudgmentSearchRequirementStatusView,
  type JudgmentSearchResultsView,
  type JudgmentSearchResumeView,
  type JudgmentSearchStartInput,
  type JudgmentSearchStartView,
  type JudgmentSearchStatusView,
  type JudgmentSearchResultStatus,
} from "./judgmentSearchTypes";

export interface JudgmentSearchHttpOptions {
  fetchImpl?: typeof fetch;
}

export interface JudgmentSearchRequestOptions {
  signal?: AbortSignal;
}

export interface JudgmentSearchHttp {
  start(
    subjectId: string,
    reviewEpisodeId: string,
    input?: JudgmentSearchStartInput,
    options?: JudgmentSearchRequestOptions,
  ): Promise<JudgmentSearchStartView>;
  status(
    subjectId: string,
    reviewEpisodeId: string,
    jobId: string,
    options?: JudgmentSearchRequestOptions,
  ): Promise<JudgmentSearchStatusView>;
  results(
    subjectId: string,
    reviewEpisodeId: string,
    jobId: string,
    options?: JudgmentSearchRequestOptions,
  ): Promise<JudgmentSearchResultsView>;
  resume(
    subjectId: string,
    reviewEpisodeId: string,
    jobId: string,
    options?: JudgmentSearchRequestOptions,
  ): Promise<JudgmentSearchResumeView>;
}

export class JudgmentSearchDecodeError extends Error {
  readonly name = "JudgmentSearchDecodeError";

  constructor(message: string) {
    super(message);
  }
}

export class JudgmentSearchApiError extends Error {
  readonly name = "JudgmentSearchApiError";

  constructor(message: string) {
    super(message);
  }
}

const JOB_STATE_VALUES = JUDGMENT_SEARCH_JOB_STATES as readonly string[];
const RESULT_STATUS_VALUES = JUDGMENT_SEARCH_RESULT_STATUSES as readonly string[];
const LANE_VALUES = JUDGMENT_SEARCH_LANES as readonly string[];
const CHANNEL_VALUES = JUDGMENT_SEARCH_CHANNELS as readonly string[];

type RecordValue = Record<string, unknown>;

function record(value: unknown, path: string): RecordValue {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new JudgmentSearchDecodeError(`${path} 应为对象`);
  }
  return value as RecordValue;
}

function exactKeys(value: RecordValue, allowed: readonly string[], path: string): void {
  const unknown = Object.keys(value).filter((key) => !allowed.includes(key));
  if (unknown.length > 0) {
    throw new JudgmentSearchDecodeError(`${path} 含未知字段：${unknown.join("、")}`);
  }
}

function field(value: RecordValue, key: string, path: string): unknown {
  if (!Object.prototype.hasOwnProperty.call(value, key)) {
    throw new JudgmentSearchDecodeError(`${path}.${key} 缺少字段`);
  }
  return value[key];
}

function nonBlankString(value: unknown, path: string): string {
  if (typeof value !== "string" || value.trim().length === 0) {
    throw new JudgmentSearchDecodeError(`${path} 应为非空字符串`);
  }
  return value;
}

function nullableString(value: unknown, path: string): string | null {
  if (value === null) return null;
  return nonBlankString(value, path);
}

function nonNegativeInteger(value: unknown, path: string): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 0) {
    throw new JudgmentSearchDecodeError(`${path} 应为非负整数`);
  }
  return value;
}

function positiveInteger(value: unknown, path: string): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 1) {
    throw new JudgmentSearchDecodeError(`${path} 应为正整数`);
  }
  return value;
}

function finiteNumber(value: unknown, path: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new JudgmentSearchDecodeError(`${path} 应为有限数值`);
  }
  return value;
}

function booleanValue(value: unknown, path: string): boolean {
  if (typeof value !== "boolean") {
    throw new JudgmentSearchDecodeError(`${path} 应为布尔值`);
  }
  return value;
}

function stringArray(value: unknown, path: string): ReadonlyArray<string> {
  if (!Array.isArray(value)) {
    throw new JudgmentSearchDecodeError(`${path} 应为字符串数组`);
  }
  return value.map((item, index) => nonBlankString(item, `${path}[${index}]`));
}

function enumValue<T extends string>(
  value: unknown,
  values: readonly string[],
  path: string,
): T {
  if (typeof value !== "string" || !values.includes(value)) {
    throw new JudgmentSearchDecodeError(`${path} 含未知值：${String(value)}`);
  }
  return value as T;
}

function decodeBoundingBox(value: unknown, path: string): JudgmentSearchBoundingBoxView | null {
  if (value === null) return null;
  const raw = record(value, path);
  exactKeys(raw, ["x0", "y0", "x1", "y1"], path);
  const x0 = finiteNumber(field(raw, "x0", path), `${path}.x0`);
  const y0 = finiteNumber(field(raw, "y0", path), `${path}.y0`);
  const x1 = finiteNumber(field(raw, "x1", path), `${path}.x1`);
  const y1 = finiteNumber(field(raw, "y1", path), `${path}.y1`);
  if (x0 < 0 || y0 < 0 || x1 <= x0 || y1 <= y0) {
    throw new JudgmentSearchDecodeError(`${path} 坐标范围无效`);
  }
  return { x0, y0, x1, y1 };
}

function decodeExcerpt(value: unknown, path: string): JudgmentSearchExcerptView {
  const raw = record(value, path);
  exactKeys(raw, ["text", "bbox", "coordinate_convention", "uncertainty_note"], path);
  const coordinateConvention = field(raw, "coordinate_convention", path);
  if (coordinateConvention !== "unverified") {
    throw new JudgmentSearchDecodeError(`${path}.coordinate_convention 含未知值`);
  }
  return {
    text: nonBlankString(field(raw, "text", path), `${path}.text`),
    bbox: decodeBoundingBox(field(raw, "bbox", path), `${path}.bbox`),
    coordinateConvention: "unverified",
    uncertaintyNote: nullableString(
      field(raw, "uncertainty_note", path),
      `${path}.uncertainty_note`,
    ),
  };
}

function decodeCandidate(value: unknown, path: string): JudgmentSearchCandidateView {
  const raw = record(value, path);
  exactKeys(
    raw,
    [
      "lane",
      "lane_label",
      "channel",
      "channel_label",
      "source_document_version_id",
      "page_artifact_id",
      "page_number",
      "excerpts",
    ],
    path,
  );
  const rawExcerpts = field(raw, "excerpts", path);
  if (!Array.isArray(rawExcerpts) || rawExcerpts.length === 0) {
    throw new JudgmentSearchDecodeError(`${path}.excerpts 应为非空数组`);
  }
  return {
    lane: enumValue<JudgmentSearchLane>(field(raw, "lane", path), LANE_VALUES, `${path}.lane`),
    laneLabel: nonBlankString(field(raw, "lane_label", path), `${path}.lane_label`),
    channel: enumValue<JudgmentSearchChannel>(
      field(raw, "channel", path),
      CHANNEL_VALUES,
      `${path}.channel`,
    ),
    channelLabel: nonBlankString(field(raw, "channel_label", path), `${path}.channel_label`),
    sourceDocumentVersionId: nonBlankString(
      field(raw, "source_document_version_id", path),
      `${path}.source_document_version_id`,
    ),
    pageArtifactId: nonBlankString(
      field(raw, "page_artifact_id", path),
      `${path}.page_artifact_id`,
    ),
    pageNumber: positiveInteger(field(raw, "page_number", path), `${path}.page_number`),
    excerpts: rawExcerpts.map((item, index) => decodeExcerpt(item, `${path}.excerpts[${index}]`)),
  };
}

function decodeRequirementStatus(
  value: unknown,
  path: string,
): JudgmentSearchRequirementStatusView {
  const raw = record(value, path);
  exactKeys(raw, ["requirement_id", "status", "status_label", "found_candidate_count"], path);
  return {
    requirementId: nonBlankString(field(raw, "requirement_id", path), `${path}.requirement_id`),
    status: enumValue<JudgmentSearchResultStatus>(
      field(raw, "status", path),
      RESULT_STATUS_VALUES,
      `${path}.status`,
    ),
    statusLabel: nonBlankString(field(raw, "status_label", path), `${path}.status_label`),
    foundCandidateCount: nonNegativeInteger(
      field(raw, "found_candidate_count", path),
      `${path}.found_candidate_count`,
    ),
  };
}

function decodeIncompletePage(
  value: unknown,
  path: string,
): JudgmentSearchIncompletePageView {
  const raw = record(value, path);
  exactKeys(raw, ["source_document_version_id", "page_artifact_id", "page_number", "reasons"], path);
  return {
    sourceDocumentVersionId: nonBlankString(field(raw, "source_document_version_id", path), `${path}.source_document_version_id`),
    pageArtifactId: nonBlankString(field(raw, "page_artifact_id", path), `${path}.page_artifact_id`),
    pageNumber: positiveInteger(field(raw, "page_number", path), `${path}.page_number`),
    reasons: stringArray(field(raw, "reasons", path), `${path}.reasons`),
  };
}

function decodeRequirementResult(
  value: unknown,
  path: string,
): JudgmentSearchRequirementResultView {
  const raw = record(value, path);
  exactKeys(raw, ["requirement_id", "requirement_label", "status", "status_label", "found_candidates", "incomplete_pages"], path);
  const rawCandidates = field(raw, "found_candidates", path);
  if (!Array.isArray(rawCandidates)) {
    throw new JudgmentSearchDecodeError(`${path}.found_candidates 应为数组`);
  }
  const rawIncomplete = field(raw, "incomplete_pages", path);
  if (!Array.isArray(rawIncomplete)) {
    throw new JudgmentSearchDecodeError(`${path}.incomplete_pages 应为数组`);
  }
  const rawStatus = field(raw, "status", path);
  return {
    requirementId: nonBlankString(field(raw, "requirement_id", path), `${path}.requirement_id`),
    requirementLabel: nonBlankString(field(raw, "requirement_label", path), `${path}.requirement_label`),
    status:
      rawStatus === null
        ? null
        : enumValue<JudgmentSearchResultStatus>(rawStatus, RESULT_STATUS_VALUES, `${path}.status`),
    statusLabel: nonBlankString(field(raw, "status_label", path), `${path}.status_label`),
    foundCandidates: rawCandidates.map((item, index) => decodeCandidate(item, `${path}.found_candidates[${index}]`)),
    incompletePages: rawIncomplete.map((item, index) => decodeIncompletePage(item, `${path}.incomplete_pages[${index}]`)),
  };
}

export function decodeJudgmentSearchStart(value: unknown): JudgmentSearchStartView {
  const raw = record(value, "start");
  exactKeys(raw, ["job_id", "state", "state_label", "created"], "start");
  return {
    jobId: nonBlankString(field(raw, "job_id", "start"), "start.job_id"),
    state: enumValue<JudgmentSearchJobState>(field(raw, "state", "start"), JOB_STATE_VALUES, "start.state"),
    stateLabel: nonBlankString(field(raw, "state_label", "start"), "start.state_label"),
    created: booleanValue(field(raw, "created", "start"), "start.created"),
  };
}

export function decodeJudgmentSearchStatus(value: unknown): JudgmentSearchStatusView {
  const raw = record(value, "status");
  exactKeys(
    raw,
    [
      "job_id",
      "state",
      "state_label",
      "total_pages",
      "completed_reads",
      "total_reads",
      "requirement_results",
      "can_resume",
    ],
    "status",
  );
  const rawRequirements = field(raw, "requirement_results", "status");
  if (!Array.isArray(rawRequirements)) {
    throw new JudgmentSearchDecodeError("status.requirement_results 应为数组");
  }
  return {
    jobId: nonBlankString(field(raw, "job_id", "status"), "status.job_id"),
    state: enumValue<JudgmentSearchJobState>(field(raw, "state", "status"), JOB_STATE_VALUES, "status.state"),
    stateLabel: nonBlankString(field(raw, "state_label", "status"), "status.state_label"),
    totalPages: nonNegativeInteger(field(raw, "total_pages", "status"), "status.total_pages"),
    completedReads: nonNegativeInteger(field(raw, "completed_reads", "status"), "status.completed_reads"),
    totalReads: nonNegativeInteger(field(raw, "total_reads", "status"), "status.total_reads"),
    requirementResults: rawRequirements.map((item, index) => decodeRequirementStatus(item, `status.requirement_results[${index}]`)),
    canResume: booleanValue(field(raw, "can_resume", "status"), "status.can_resume"),
  };
}

export function decodeJudgmentSearchResults(value: unknown): JudgmentSearchResultsView {
  const raw = record(value, "results");
  exactKeys(raw, ["job_id", "state", "searched_page_count", "results"], "results");
  const rawResults = field(raw, "results", "results");
  if (!Array.isArray(rawResults)) {
    throw new JudgmentSearchDecodeError("results.results 应为数组");
  }
  return {
    jobId: nonBlankString(field(raw, "job_id", "results"), "results.job_id"),
    state: enumValue<JudgmentSearchJobState>(field(raw, "state", "results"), JOB_STATE_VALUES, "results.state"),
    searchedPageCount: nonNegativeInteger(
      field(raw, "searched_page_count", "results"),
      "results.searched_page_count",
    ),
    results: rawResults.map((item, index) => decodeRequirementResult(item, `results.results[${index}]`)),
  };
}

export function decodeJudgmentSearchResume(value: unknown): JudgmentSearchResumeView {
  const raw = record(value, "resume");
  exactKeys(raw, ["job_id", "state", "changed", "state_label"], "resume");
  return {
    jobId: nonBlankString(field(raw, "job_id", "resume"), "resume.job_id"),
    state: enumValue<JudgmentSearchJobState>(field(raw, "state", "resume"), JOB_STATE_VALUES, "resume.state"),
    changed: booleanValue(field(raw, "changed", "resume"), "resume.changed"),
    stateLabel: nonBlankString(field(raw, "state_label", "resume"), "resume.state_label"),
  };
}

function apiPath(subjectId: string, reviewEpisodeId: string): string {
  const path = `/api/v2/subjects/${encodeURIComponent(subjectId)}/review-episodes/${encodeURIComponent(reviewEpisodeId)}/judgment-search-jobs`;
  const base = getProtocolApiBase();
  return base.length > 0 ? `${base}${path}` : path;
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

function errorMessage(payload: unknown): string {
  if (payload !== null && typeof payload === "object" && !Array.isArray(payload)) {
    const error = (payload as Record<string, unknown>).error;
    if (error !== null && typeof error === "object" && !Array.isArray(error)) {
      const data = error as Record<string, unknown>;
      const parts = [data.title, data.detail, data.recovery_action].filter(
        (part): part is string => typeof part === "string" && part.trim().length > 0,
      );
      if (parts.length > 0) return [...new Set(parts)].join(" ");
    }
  }
  return "书面判断检索服务暂时不可用，请稍后重试。";
}

async function request<T>(
  fetchImpl: typeof fetch,
  url: string,
  init: RequestInit,
  decode: (payload: unknown) => T,
): Promise<T> {
  const response = await fetchImpl(url, init);
  const payload = await readJson(response);
  if (!response.ok) throw new JudgmentSearchApiError(errorMessage(payload));
  if (payload === null) {
    throw new JudgmentSearchApiError("书面判断检索服务返回了空响应，请稍后重试。");
  }
  try {
    return decode(payload);
  } catch (error) {
    if (error instanceof JudgmentSearchDecodeError) throw error;
    throw new JudgmentSearchDecodeError("书面判断检索响应无法识别。");
  }
}

export function createJudgmentSearchHttp(
  options: JudgmentSearchHttpOptions | typeof fetch = {},
): JudgmentSearchHttp {
  const fetchImpl =
    typeof options === "function"
      ? options
      : options.fetchImpl ?? fetch.bind(globalThis);
  return {
    async start(subjectId, reviewEpisodeId, input = {}, requestOptions = {}) {
      const requirementIds = input.requirementIds;
      if (
        requirementIds !== undefined &&
        requirementIds.some((id) => typeof id !== "string" || id.trim().length === 0)
      ) {
        throw new Error("requirementIds 必须为非空字符串数组");
      }
      const body =
        requirementIds === undefined ? {} : { requirement_ids: [...requirementIds] };
      return request(
        fetchImpl,
        apiPath(subjectId, reviewEpisodeId),
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          signal: requestOptions.signal,
        },
        decodeJudgmentSearchStart,
      );
    },
    async status(subjectId, reviewEpisodeId, jobId, requestOptions = {}) {
      const result = await request(
        fetchImpl,
        `${apiPath(subjectId, reviewEpisodeId)}/${encodeURIComponent(jobId)}`,
        { method: "GET", signal: requestOptions.signal },
        decodeJudgmentSearchStatus,
      );
      if (result.jobId !== jobId) {
        throw new JudgmentSearchDecodeError("status.job_id 与请求任务不一致");
      }
      return result;
    },
    async results(subjectId, reviewEpisodeId, jobId, requestOptions = {}) {
      const result = await request(
        fetchImpl,
        `${apiPath(subjectId, reviewEpisodeId)}/${encodeURIComponent(jobId)}/results`,
        { method: "GET", signal: requestOptions.signal },
        decodeJudgmentSearchResults,
      );
      if (result.jobId !== jobId) {
        throw new JudgmentSearchDecodeError("results.job_id 与请求任务不一致");
      }
      return result;
    },
    async resume(subjectId, reviewEpisodeId, jobId, requestOptions = {}) {
      const result = await request(
        fetchImpl,
        `${apiPath(subjectId, reviewEpisodeId)}/${encodeURIComponent(jobId)}/resume`,
        { method: "POST", signal: requestOptions.signal },
        decodeJudgmentSearchResume,
      );
      if (result.jobId !== jobId) {
        throw new JudgmentSearchDecodeError("resume.job_id 与请求任务不一致");
      }
      return result;
    },
  };
}
