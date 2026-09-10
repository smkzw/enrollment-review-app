import { getProtocolApiBase } from "../protocolApiConfig";

export class PageReviewApiError extends Error {
  constructor(message = "暂时无法读取资料识别进度。") { super(message); }
}

export interface PageReviewStatus {
  jobId: string;
  state: string;
  reviewStatus: "processing" | "stopped" | "needs_reread" | "ready";
  totalPages: number;
  acceptedPages: number;
  unrelatedPages: number;
  failedPages: number;
  pendingPages: number;
  canReread: boolean;
}

function object(value: unknown): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) throw new PageReviewApiError();
  return value as Record<string, unknown>;
}

function text(value: unknown): string {
  if (typeof value !== "string" || !value.trim()) throw new PageReviewApiError();
  return value;
}

function count(value: unknown): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 0) throw new PageReviewApiError();
  return value;
}

export function decodePageReviewStatus(value: unknown): PageReviewStatus {
  const raw = object(value);
  const status = raw.review_status;
  if (status !== "processing" && status !== "stopped" && status !== "needs_reread" && status !== "ready") {
    throw new PageReviewApiError();
  }
  const result: PageReviewStatus = {
    jobId: text(raw.job_id), state: text(raw.state), reviewStatus: status,
    totalPages: count(raw.total_pages), acceptedPages: count(raw.accepted_pages),
    unrelatedPages: count(raw.unrelated_pages), failedPages: count(raw.failed_pages),
    pendingPages: count(raw.pending_pages), canReread: raw.can_reread === true,
  };
  if (typeof raw.can_reread !== "boolean"
      || result.totalPages !== result.acceptedPages + result.unrelatedPages + result.failedPages + result.pendingPages
      || (status === "ready" && (result.failedPages > 0 || result.pendingPages > 0 || result.state !== "completed"))
      || (result.canReread && status !== "needs_reread")) throw new PageReviewApiError();
  return result;
}

export function createPageReviewHttp(fetchImpl: typeof fetch = fetch.bind(globalThis)) {
  function path(subjectId: string, episodeId: string) {
    return `${getProtocolApiBase()}/api/v2/subjects/${encodeURIComponent(subjectId)}/review-episodes/${encodeURIComponent(episodeId)}/page-review-jobs`;
  }
  async function request(url: string, init: RequestInit): Promise<unknown> {
    const response = await fetchImpl(url, init);
    let value: unknown;
    try { value = await response.json(); } catch { throw new PageReviewApiError(); }
    if (!response.ok) {
      const error = object(value).error;
      const title = error && typeof error === "object" ? (error as Record<string, unknown>).title : null;
      const recovery = error && typeof error === "object" ? (error as Record<string, unknown>).recovery_action : null;
      const message = [title, recovery].filter((part): part is string => typeof part === "string" && !!part.trim());
      throw new PageReviewApiError(message.length ? [...new Set(message)].join(" ") : undefined);
    }
    return value;
  }
  return {
    async resume(subjectId: string, episodeId: string, jobId: string, signal?: AbortSignal) {
      const raw = object(await request(`${path(subjectId, episodeId)}/${encodeURIComponent(jobId)}/resume`, {
        method: "POST", signal,
      }));
      if (text(raw.job_id) !== jobId || typeof raw.changed !== "boolean") throw new PageReviewApiError();
      return jobId;
    },
    async start(subjectId: string, episodeId: string, predecessorJobId?: string, signal?: AbortSignal) {
      const raw = object(await request(path(subjectId, episodeId), {
        method: "POST", headers: { "Content-Type": "application/json" }, signal,
        body: JSON.stringify(predecessorJobId ? { predecessor_job_id: predecessorJobId } : {}),
      }));
      return text(raw.job_id);
    },
    async status(subjectId: string, episodeId: string, jobId: string, signal?: AbortSignal) {
      return decodePageReviewStatus(await request(`${path(subjectId, episodeId)}/${encodeURIComponent(jobId)}`, {
        method: "GET", signal,
      }));
    },
  };
}
