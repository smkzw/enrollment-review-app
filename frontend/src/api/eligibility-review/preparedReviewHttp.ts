import { decodeEligibilityReviewError } from "./eligibilityReviewViewModels";
import { getProtocolApiBase } from "../protocolApiConfig";

const kinds = ["predicate_candidates", "control_candidates", "qualification", "judgment_content", "proposition_evidence", "observation_relation", "frequency_evidence"] as const;
const states = ["queued", "running", "completed", "failed_retryable", "failed_final",
  "cancel_requested", "cancelled", "recovering", "waiting_user"] as const;
export type PreparedReviewKind = typeof kinds[number];
export type PreparedReviewState = typeof states[number];
export interface ReviewAuthorityInput {
  project_id: string;
  subject_id: string;
  review_episode_id: string;
  episode_revision: number;
  protocol_version_id: string;
  rule_set_id: string;
  rule_set_revision: number;
  evidence_snapshot_v2_id: string;
  complete_processing_revision_id: string;
}
export interface PreparedReviewTask {
  jobId: string;
  kind: PreparedReviewKind;
  candidateJobId: string | null;
  state: PreparedReviewState;
  stateLabel: string;
  progressCompleted: number;
  progressTotal: number;
}
export interface PreparedReviewWorkflow {
  reportSaved: boolean;
  jobId: string;
  contextId: string;
  contextSha256: string;
  reviewRunId: string;
  state: PreparedReviewState;
  stateLabel: string;
  stageLabel: string;
  progressCompleted: number;
  progressTotal: number;
  items: PreparedReviewTask[];
}

function invalid(): never {
  throw new Error("审核进度暂不能确认，请刷新后重试。原有记录不会因此改变。");
}
function object(value: unknown, keys: string[]): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return invalid();
  const row = value as Record<string, unknown>;
  if (Object.keys(row).length !== keys.length || keys.some((key) => !(key in row))) return invalid();
  return row;
}
function text(value: unknown): string {
  return typeof value === "string" && value.trim() ? value : invalid();
}
function nullableText(value: unknown): string | null {
  return value === null ? null : text(value);
}
function count(value: unknown): number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0 ? value : invalid();
}
function choice<T extends string>(value: unknown, options: readonly T[]): T {
  return typeof value === "string" && options.includes(value as T) ? value as T : invalid();
}

function taskItems(value: unknown): PreparedReviewTask[] {
  if (!Array.isArray(value)) return invalid();
  const seen = new Set<string>();
  return value.map((value: unknown) => {
    const item = object(value, ["job_id", "kind", "candidate_job_id", "state", "state_label",
      "progress_completed", "progress_total"]);
    const jobId = text(item.job_id);
    if (seen.has(jobId)) return invalid();
    seen.add(jobId);
    const kind = choice(item.kind, kinds);
    const candidateJobId = nullableText(item.candidate_job_id);
    if ((kind === "qualification" || kind === "judgment_content" || kind === "proposition_evidence" || kind === "observation_relation" || kind === "frequency_evidence") !== (candidateJobId !== null)) return invalid();
    return { jobId, kind, candidateJobId, state: choice(item.state, states), stateLabel: text(item.state_label),
      progressCompleted: count(item.progress_completed), progressTotal: count(item.progress_total) };
  });
}

function command(value: unknown) {
  const row = object(value, ["job_id", "state", "state_label", "created"]);
  if (typeof row.created !== "boolean") return invalid();
  return { jobId: text(row.job_id), state: choice(row.state, states), stateLabel: text(row.state_label), created: row.created };
}

export function createPreparedReviewHttp(fetchImpl: typeof fetch = fetch.bind(globalThis)) {
  async function request(subjectId: string, episodeId: string, suffix: string, init: RequestInit,
    resource = "prepared-review-jobs") {
    const path = `/api/v2/subjects/${encodeURIComponent(subjectId)}/review-episodes/${encodeURIComponent(episodeId)}/${resource}${suffix}`;
    const response = await fetchImpl(`${getProtocolApiBase()}${path}`, init);
    let payload: unknown;
    try { payload = await response.json() as unknown; } catch { payload = null; }
    if (!response.ok) throw decodeEligibilityReviewError(payload, response.status);
    return payload;
  }
  return {
    async publishWorkflow(subjectId: string, episodeId: string, workflowId: string, signal?: AbortSignal) {
      const payload = await request(subjectId, episodeId, `/${encodeURIComponent(workflowId)}/publish`,
        { method: "POST", signal }, "prepared-review-workflows");
      return text(object(payload, ["review_run_id"]).review_run_id);
    },
    async startWorkflow(subjectId: string, episodeId: string, contextId: string, signal?: AbortSignal) {
      return command(await request(subjectId, episodeId, "", {
        method: "POST", headers: { "Content-Type": "application/json" }, signal,
        body: JSON.stringify({ context_id: contextId }),
      }, "prepared-review-workflows"));
    },
    async workflow(subjectId: string, episodeId: string, workflowId: string, signal?: AbortSignal): Promise<PreparedReviewWorkflow> {
      const payload = await request(subjectId, episodeId, `/${encodeURIComponent(workflowId)}`, { method: "GET", signal },
        "prepared-review-workflows");
      const row = object(payload, ["job_id", "context_id", "context_sha256", "review_run_id", "state", "state_label",
        "stage_label", "progress_completed", "progress_total", "items", "report_saved"]);
      if (typeof row.report_saved !== "boolean") return invalid();
      const contextSha256 = text(row.context_sha256);
      if (row.job_id !== workflowId || !/^[0-9a-f]{64}$/.test(contextSha256)) return invalid();
      return { reportSaved: row.report_saved, jobId: workflowId, contextId: text(row.context_id), contextSha256, reviewRunId: text(row.review_run_id),
        state: choice(row.state, states), stateLabel: text(row.state_label), stageLabel: text(row.stage_label),
        progressCompleted: count(row.progress_completed), progressTotal: count(row.progress_total), items: taskItems(row.items) };
    },
    async changeWorkflow(subjectId: string, episodeId: string, workflowId: string, operation: "cancel" | "retry", signal?: AbortSignal) {
      const payload = await request(subjectId, episodeId, `/${encodeURIComponent(workflowId)}/${operation}`,
        { method: "POST", signal }, "prepared-review-workflows");
      const row = object(payload, ["state", "state_label", "changed"]);
      if (typeof row.changed !== "boolean") return invalid();
      return { state: choice(row.state, states), stateLabel: text(row.state_label), changed: row.changed };
    },
    async prepare(subjectId: string, episodeId: string, authority: ReviewAuthorityInput,
      idempotencyKey: string, signal?: AbortSignal) {
      if (authority.subject_id !== subjectId || authority.review_episode_id !== episodeId) return invalid();
      const payload = await request(subjectId, episodeId, "", {
        method: "POST", headers: { "Content-Type": "application/json" }, signal,
        body: JSON.stringify({ expected_authority: authority, idempotency_key: idempotencyKey }),
      }, "review-preparations");
      const row = object(payload, ["context_id", "context_sha256", "review_run_id"]);
      const contextSha256 = text(row.context_sha256);
      if (!/^[0-9a-f]{64}$/.test(contextSha256)) return invalid();
      return { contextId: text(row.context_id), contextSha256, reviewRunId: text(row.review_run_id) };
    },
    async start(subjectId: string, episodeId: string, contextId: string, kind: PreparedReviewKind,
      candidateJobId: string | null = null, signal?: AbortSignal) {
      const followsCandidate = kind === "qualification" || kind === "judgment_content" || kind === "proposition_evidence" || kind === "observation_relation" || kind === "frequency_evidence";
      if (followsCandidate !== (candidateJobId !== null)) return invalid();
      const payload = await request(subjectId, episodeId, "", {
        method: "POST", headers: { "Content-Type": "application/json" }, signal,
        body: JSON.stringify({ context_id: contextId, kind, candidate_job_id: candidateJobId }),
      });
      return command(payload);
    },
    async progress(subjectId: string, episodeId: string, contextId: string, contextSha256: string,
      afterJobId: string | null = null, signal?: AbortSignal) {
      const query = new URLSearchParams({ context_id: contextId });
      if (afterJobId !== null) query.set("after_job_id", afterJobId);
      const payload = await request(subjectId, episodeId, `?${query}`, { method: "GET", signal });
      const row = object(payload, ["context_id", "context_sha256", "items", "next_cursor"]);
      if (row.context_id !== contextId || row.context_sha256 !== contextSha256 || !Array.isArray(row.items)) return invalid();
      const items = taskItems(row.items);
      const nextCursor = nullableText(row.next_cursor);
      if (nextCursor !== null && (items.length === 0 || nextCursor !== items[items.length - 1].jobId)) return invalid();
      return { contextId, contextSha256, items, nextCursor };
    },
  };
}
