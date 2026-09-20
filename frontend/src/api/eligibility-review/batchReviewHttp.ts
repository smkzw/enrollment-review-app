import { getProtocolApiBase } from "../protocolApiConfig";
import { decodeEligibilityReviewError } from "./eligibilityReviewViewModels";

export interface ReviewBatchMember {
  subjectId: string;
  subjectCode: string;
  stageLabel: string;
  episodeId: string;
  workflowId: string | null;
  state: string;
  recordedState: string | null;
}
export interface ReviewBatch {
  jobId: string;
  state: string;
  items: ReviewBatchMember[];
  failureDetail: string | null;
}
function invalid(): never { throw new Error("批量审核进度暂不能确认，请刷新重试。"); }
function object(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : invalid();
}
function text(value: unknown): string { return typeof value === "string" && value.trim() ? value : invalid(); }
const states = ["queued", "running", "completed", "failed_retryable", "failed_final", "cancel_requested", "cancelled", "recovering", "waiting_user"];
function state(value: unknown, extra: string[] = []): string { return [...states, ...extra].includes(text(value)) ? text(value) : invalid(); }
function parse(value: unknown, projectId: string): ReviewBatch {
  const row = object(value);
  if (row.project_id !== projectId || row.clinical_adoption !== false || !Array.isArray(row.items) || !row.items.length || row.items.length > 50) return invalid();
  const seen = new Set<string>();
  return { jobId: text(row.job_id), state: state(row.state), failureDetail: row.failure_detail === null ? null : text(row.failure_detail), items: row.items.map((value) => {
    const item = object(value);
    const episodeId = text(item.review_episode_id);
    if (seen.has(episodeId)) return invalid();
    seen.add(episodeId);
    const workflowId = item.workflow_job_id === null ? null : text(item.workflow_job_id);
    const memberState = state(item.state, ["not_started"]);
    if ((workflowId === null) !== (memberState === "not_started")) return invalid();
    const recordedState = item.recorded_state === null ? null : text(item.recorded_state);
    if (recordedState !== null && !["completed", "failed_final", "cancelled"].includes(recordedState)) return invalid();
    return { subjectId: text(item.subject_id), subjectCode: text(item.subject_code), stageLabel: text(item.workflow_stage_label), episodeId,
      workflowId, state: memberState, recordedState };
  }) };
}
async function request(projectId: string, suffix: string, init: RequestInit): Promise<unknown> {
  const response = await fetch(`${getProtocolApiBase()}/api/v2/projects/${encodeURIComponent(projectId)}/review-batches${suffix}`, init);
  let payload: unknown;
  try { payload = await response.json(); } catch { payload = null; }
  if (!response.ok) throw decodeEligibilityReviewError(payload, response.status);
  return payload;
}
export async function recentReviewBatches(projectId: string, signal?: AbortSignal, offset = 0) {
  const payload = object(await request(projectId, `?offset=${offset}`, { signal }));
  if (payload.project_id !== projectId || payload.offset !== offset || typeof payload.has_more !== "boolean" || !Array.isArray(payload.items) || payload.items.length > 20) return invalid();
  const unavailableCount = payload.unavailable_count;
  if (typeof unavailableCount !== "number" || !Number.isInteger(unavailableCount) || unavailableCount < 0 || unavailableCount + payload.items.length > 20) return invalid();
  const items = payload.items.map((value) => {
    const item = object(value);
    const memberCount = item.member_count;
    if (typeof memberCount !== "number" || !Number.isInteger(memberCount) || memberCount < 1 || memberCount > 50) return invalid();
    const createdAt = text(item.created_at);
    if (!Number.isFinite(Date.parse(createdAt))) return invalid();
    return { jobId: text(item.job_id), state: state(item.state), memberCount, createdAt };
  });
  if (new Set(items.map((item) => item.jobId)).size !== items.length) return invalid();
  return { items, hasMore: payload.has_more, unavailableCount, offset };
}
export async function readReviewBatch(projectId: string, batchId: string, signal?: AbortSignal) {
  const result = parse(await request(projectId, `/${encodeURIComponent(batchId)}`, { signal }), projectId);
  if (result.jobId !== batchId) return invalid();
  return result;
}
export async function startReviewBatch(projectId: string, requestKey: string,
  members: { subject_id: string; review_episode_id: string; context_id: string }[], signal?: AbortSignal) {
  const row = object(await request(projectId, "", { method: "POST", signal,
    headers: { "Content-Type": "application/json" }, body: JSON.stringify({ request_key: requestKey, members }) }));
  if (typeof row.created !== "boolean") return invalid();
  state(row.state);
  return text(row.job_id);
}
export async function changeReviewBatch(projectId: string, batchId: string, operation: "cancel" | "retry", signal?: AbortSignal) {
  const row = object(await request(projectId, `/${encodeURIComponent(batchId)}/${operation}`, { method: "POST", signal }));
  if (row.job_id !== batchId || typeof row.changed !== "boolean") return invalid();
  state(row.state);
}
