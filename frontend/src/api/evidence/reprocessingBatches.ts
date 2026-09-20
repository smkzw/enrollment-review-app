import { getProtocolApiBase } from "../protocolApiConfig";
import { decodeUploadPreviewError } from "./evidenceViewModels";

export interface OcrBatchMember { subjectId: string; episodeId: string; snapshotId: string; processingId: string }
export interface OcrBatchItem extends OcrBatchMember {
  subjectCode: string; nodeLabel: string; jobId: string | null; state: string; recordedState: string | null;
  revisionId: string | null; newRevision: boolean;
}
export interface OcrBatch { jobId: string; state: string; failureDetail: string | null; items: OcrBatchItem[] }
export const ocrBatchLabels: Record<string, string> = { not_started: "尚未开始", queued: "等待识别", running: "正在识别", completed: "识别已结束",
  failed_retryable: "等待重试", failed_final: "未完成", cancel_requested: "正在停止", cancelled: "已停止", recovering: "正在恢复", waiting_user: "等待处理" };
const invalid = (): never => { throw new Error("识别记录不完整，未显示无法核实的结果。请刷新后重试。"); };
const text = (value: unknown): string => typeof value === "string" && value.trim() ? value : invalid();
const optional = (value: unknown): string | null => value === null ? null : text(value);
function object(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : invalid();
}
function state(value: unknown): string { const result = text(value); return Object.hasOwn(ocrBatchLabels, result) ? result : invalid(); }
async function request(projectId: string, suffix: string, init?: RequestInit) {
  const response = await fetch(`${getProtocolApiBase()}/api/v2/projects/${encodeURIComponent(projectId)}/reprocessing-batches${suffix}`, init);
  const result: unknown = await response.json();
  if (!response.ok) throw decodeUploadPreviewError(result, response.status);
  return object(result);
}
export async function startOcrBatch(projectId: string, key: string, members: OcrBatchMember[], signal?: AbortSignal) {
  const result = await request(projectId, "", { method: "POST", signal, headers: { "Content-Type": "application/json" }, body: JSON.stringify({ request_key: key,
    members: members.map(item => ({ subject_id: item.subjectId, review_episode_id: item.episodeId, snapshot_id: item.snapshotId, complete_id: item.processingId })) }) });
  state(result.state); if (typeof result.created !== "boolean") return invalid();
  return text(result.job_id);
}
export async function readOcrBatch(projectId: string, batchId: string, signal?: AbortSignal): Promise<OcrBatch> {
  const result = await request(projectId, `/${encodeURIComponent(batchId)}`, { signal });
  if (result.job_id !== batchId || result.project_id !== projectId || result.activated !== false || !Array.isArray(result.items) || !result.items.length || result.items.length > 50) return invalid();
  const seen = new Set<string>();
  return { jobId: batchId, state: state(result.state), failureDetail: optional(result.failure_detail), items: result.items.map(value => {
    const item = object(value), episodeId = text(item.review_episode_id);
    if (seen.has(episodeId) || typeof item.new_revision !== "boolean") return invalid();
    seen.add(episodeId);
    const jobId = optional(item.reprocess_job_id), revisionId = optional(item.revision_id), current = state(item.state);
    if ((jobId === null) !== (current === "not_started") || (revisionId !== null) !== (current === "completed") || (item.new_revision && !revisionId)) return invalid();
    const recordedState = item.recorded_state === null ? null : state(item.recorded_state);
    if (recordedState && !["completed", "cancelled", "failed_final"].includes(recordedState)) return invalid();
    return { subjectId: text(item.subject_id), subjectCode: text(item.subject_code), nodeLabel: text(item.node_label), episodeId,
      snapshotId: text(item.snapshot_id), processingId: text(item.complete_id), jobId, revisionId, newRevision: item.new_revision, state: current, recordedState };
  }) };
}
export async function changeOcrBatch(projectId: string, batchId: string, operation: "retry" | "cancel", signal?: AbortSignal) {
  const result = await request(projectId, `/${encodeURIComponent(batchId)}/${operation}`, { method: "POST", signal });
  if (result.job_id !== batchId || typeof result.changed !== "boolean") return invalid();
  state(result.state);
}
export async function recentOcrBatches(projectId: string, offset: number, signal?: AbortSignal) {
  const result = await request(projectId, `?offset=${offset}`, { signal });
  if (result.project_id !== projectId || result.offset !== offset || typeof result.has_more !== "boolean" || !Array.isArray(result.items)
      || !Number.isInteger(result.unavailable_count) || Number(result.unavailable_count) < 0) return invalid();
  const ids = new Set<string>();
  return { offset, hasMore: result.has_more, unavailableCount: Number(result.unavailable_count), items: result.items.map(value => {
    const item = object(value), jobId = text(item.job_id), createdAt = text(item.created_at);
    if (ids.has(jobId) || !Number.isFinite(Date.parse(createdAt)) || !Number.isInteger(item.member_count) || Number(item.member_count) < 1 || Number(item.member_count) > 50) return invalid();
    ids.add(jobId);
    return { jobId, state: state(item.state), createdAt, memberCount: Number(item.member_count) };
  }) };
}
