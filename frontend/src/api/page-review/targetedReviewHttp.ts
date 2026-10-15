import { getProtocolApiBase } from "../protocolApiConfig";
import { PageReviewApiError } from "./pageReviewHttp";

export interface TargetedExcerpt {
  round: number;
  reader: number;
  field: string;
  value: string;
  excerpt: string;
  context: string[];
}

export interface TargetedReviewDetail {
  state: string;
  label: string;
  rounds: number;
  fileName: string;
  pageNumber: number;
  imageUrl: string;
  excerpts: TargetedExcerpt[];
}

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new PageReviewApiError();
  return value as Record<string, unknown>;
}
function text(value: unknown): string {
  if (typeof value !== "string" || !value.trim()) throw new PageReviewApiError();
  return value;
}
function integer(value: unknown, min: number, max: number): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < min || value > max) throw new PageReviewApiError();
  return value;
}

export function decodeTargetedReviewDetail(status: unknown, evidence: unknown, jobId: string): TargetedReviewDetail {
  const s = record(status), e = record(evidence);
  if (s.job_id !== jobId || e.job_id !== jobId || s.round_budget !== 2
      || e.candidate_auto_accept !== false || !Array.isArray(e.excerpts)) throw new PageReviewApiError();
  if (s.outcome !== null) {
    const outcome = record(s.outcome);
    if (outcome.candidate_auto_accept !== false || outcome.clinical_findings_allowed !== false) throw new PageReviewApiError();
  }
  const imagePath = text(e.image_path);
  if (!/^\/api\/v2\/evidence-processing-revisions\/[^/]+\/pages\/[^/]+\/image$/.test(imagePath)) throw new PageReviewApiError();
  return {
    state: text(s.state), label: text(s.status_label), rounds: integer(s.rounds_with_receipts, 0, 2),
    fileName: text(e.file_name), pageNumber: integer(e.page_number, 1, Number.MAX_SAFE_INTEGER),
    imageUrl: `${getProtocolApiBase()}${imagePath}`,
    excerpts: e.excerpts.map((value) => {
      const row = record(value);
      const context = [row.target_text, row.time_text, row.location_text].flatMap((item) => {
        if (item === null) return [];
        if (typeof item !== "string") throw new PageReviewApiError();
        return item.trim() ? [item] : [];
      });
      return { round: integer(row.round_number, 0, 2), reader: integer(row.read_number, 1, 2),
        field: text(row.field_name), value: text(row.raw_value), excerpt: text(row.excerpt), context };
    }),
  };
}

export async function getTargetedReviewDetail(subjectId: string, episodeId: string, jobId: string,
  signal?: AbortSignal, fetchImpl: typeof fetch = fetch.bind(globalThis)): Promise<TargetedReviewDetail> {
  const path = `${getProtocolApiBase()}/api/v2/subjects/${encodeURIComponent(subjectId)}/review-episodes/${encodeURIComponent(episodeId)}/targeted-review-jobs/${encodeURIComponent(jobId)}`;
  const read = async (suffix: string) => {
    const response = await fetchImpl(`${path}${suffix}`, { signal });
    if (!response.ok) throw new PageReviewApiError();
    try { return await response.json() as unknown; } catch { throw new PageReviewApiError(); }
  };
  const [status, evidence] = await Promise.all([read(""), read("/evidence")]);
  return decodeTargetedReviewDetail(status, evidence, jobId);
}

export interface ReviewConflictPage { pageIndex: number; fileName: string; pageNumber: number; fieldCount: number }
export async function getReviewConflicts(subjectId: string, episodeId: string, jobId: string, signal?: AbortSignal): Promise<ReviewConflictPage[]> {
  const path = `${getProtocolApiBase()}/api/v2/subjects/${encodeURIComponent(subjectId)}/review-episodes/${encodeURIComponent(episodeId)}/page-review-jobs/${encodeURIComponent(jobId)}/conflicts`;
  const response = await fetch(path, { signal });
  if (!response.ok) throw new PageReviewApiError();
  const raw = record(await response.json());
  if (raw.job_id !== jobId || !Array.isArray(raw.pages)) throw new PageReviewApiError();
  return raw.pages.map((value) => {
    const row = record(value);
    return { pageIndex: integer(row.page_index, 0, Number.MAX_SAFE_INTEGER), fileName: text(row.file_name),
      pageNumber: integer(row.page_number, 1, Number.MAX_SAFE_INTEGER), fieldCount: integer(row.field_count, 1, Number.MAX_SAFE_INTEGER) };
  });
}

export async function startTargetedReview(subjectId: string, episodeId: string, originalJobId: string, pageIndex: number): Promise<string> {
  const response = await fetch(`${getProtocolApiBase()}/api/v2/subjects/${encodeURIComponent(subjectId)}/review-episodes/${encodeURIComponent(episodeId)}/targeted-review-jobs`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ original_job_id: originalJobId, page_index: pageIndex }),
  });
  if (!response.ok) throw new PageReviewApiError();
  return text(record(await response.json()).job_id);
}
