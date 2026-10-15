import { getProtocolApiBase } from "../protocolApiConfig";
import { decodeUploadPreviewError } from "./evidenceViewModels";

export interface ReprocessingScope {
  projectId: string; subjectId: string; episodeId: string; snapshotId: string; completeId: string;
}
export interface ReprocessingView { jobId: string; state: string; revisionId: string | null; newRevision: boolean }
export const reprocessingTerminal = new Set(["completed", "cancelled", "failed_final"]);
const states = new Set(["queued", "running", "recovering", "cancel_requested", "failed_retryable", ...reprocessingTerminal]);
function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("识别记录不完整，请刷新后再试。");
  return value as Record<string, unknown>;
}
function text(value: unknown): string {
  if (typeof value !== "string" || !value.trim()) throw new Error("识别记录不完整，请刷新后再试。");
  return value;
}
async function request(scope: ReprocessingScope, suffix: string, options?: RequestInit) {
  const response = await fetch(`${getProtocolApiBase()}/api/v2/projects/${encodeURIComponent(scope.projectId)}/evidence-reprocessing${suffix}`, options);
  const payload: unknown = await response.json();
  if (!response.ok) throw decodeUploadPreviewError(payload, response.status);
  return record(payload);
}
export async function startReprocessing(scope: ReprocessingScope, key: string, signal?: AbortSignal): Promise<string> {
  const result = await request(scope, "", { method: "POST", signal, headers: { "Content-Type": "application/json" }, body: JSON.stringify({
    subject_id: scope.subjectId, review_episode_id: scope.episodeId, snapshot_id: scope.snapshotId,
    complete_id: scope.completeId, request_key: key,
  }) });
  if (!states.has(text(result.state)) || typeof result.created !== "boolean") throw new Error("未能核对识别任务，请重试同一次操作。");
  return text(result.job_id);
}
export async function readReprocessing(scope: ReprocessingScope, jobId: string, signal?: AbortSignal): Promise<ReprocessingView> {
  const result = await request(scope, `/${encodeURIComponent(jobId)}`, { signal });
  if (result.project_id !== scope.projectId || result.subject_id !== scope.subjectId || result.review_episode_id !== scope.episodeId
      || result.snapshot_id !== scope.snapshotId || result.previous_complete_revision_id !== scope.completeId || result.job_id !== jobId
      || !states.has(text(result.state)) || typeof result.new_revision !== "boolean") throw new Error("识别记录与当前资料不一致，未显示其他资料的结果。");
  const revisionId = result.revision_id === null ? null : text(result.revision_id);
  if ((result.state === "completed") !== (revisionId !== null) || (result.new_revision && revisionId === null)) throw new Error("识别完成记录不完整，请保留原资料并刷新。");
  return { jobId, state: text(result.state), revisionId, newRevision: result.new_revision };
}
