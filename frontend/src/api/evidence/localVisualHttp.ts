import { getProtocolApiBase } from "../protocolApiConfig";
import { decodeUploadPreviewError, EvidenceDecodeError } from "./evidenceViewModels";

export interface LocalVisualRegion {
  x0: number; y0: number; x1: number; y1: number;
  clockwise_degrees: 0 | 90 | 180 | 270;
}
export interface LocalVisualTask {
  found: boolean; jobId: string | null; state: string | null;
  text: string | null; region: LocalVisualRegion | null;
  configurationCurrent: boolean; canRetry: boolean;
}
const states = new Set(["queued", "running", "recovering", "cancel_requested", "cancelled", "completed", "failed_final", "failed_retryable", "waiting_user", "needs_attention"]);

function object(value: unknown): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) throw new EvidenceDecodeError("局部核实信息格式无法确认。");
  return value as Record<string, unknown>;
}
export function decodeLocalVisualTask(value: unknown): LocalVisualTask {
  const data = object(value);
  if (typeof data.found !== "boolean" || data.candidate_only !== true || data.coverage_scope !== "region_only") throw new EvidenceDecodeError("局部阅读不能作为整页核对或已采用的病史。");
  if (!data.found) return { found: false, jobId: null, state: null, text: null, region: null, configurationCurrent: true, canRetry: false };
  if (typeof data.job_id !== "string" || !data.job_id || typeof data.state !== "string" || !states.has(data.state)) throw new EvidenceDecodeError("局部核实任务状态无法确认。");
  const box = object(data.region);
  if (["x0", "y0", "x1", "y1"].some((key) => typeof box[key] !== "number" || !Number.isInteger(box[key]) || (box[key] as number) < 0)
      || (box.x1 as number) <= (box.x0 as number) || (box.y1 as number) <= (box.y0 as number)
      || ![0, 90, 180, 270].includes(box.clockwise_degrees as number)) throw new EvidenceDecodeError("局部核实范围无法定位。");
  if (data.observation_text !== null && typeof data.observation_text !== "string") throw new EvidenceDecodeError("局部阅读结果无法确认。");
  if (data.state !== "completed" && data.observation_text !== null) throw new EvidenceDecodeError("未完成的阅读不应显示为核实结果。");
  if (data.state === "completed" && (typeof data.observation_text !== "string" || !data.observation_text.trim())) throw new EvidenceDecodeError("本次读取缺少完整内容，请重新读取或核对原件。");
  if (typeof data.configuration_current !== "boolean" || typeof data.can_retry !== "boolean"
      || (data.can_retry && (!data.configuration_current || !["failed_final", "failed_retryable"].includes(data.state)))) throw new EvidenceDecodeError("本次读取的恢复范围无法确认。");
  return { found: true, jobId: data.job_id, state: data.state, text: data.observation_text as string | null, region: box as unknown as LocalVisualRegion,
    configurationCurrent: data.configuration_current, canRetry: data.can_retry };
}

async function request(path: string, init: RequestInit): Promise<unknown> {
  const response = await fetch(`${getProtocolApiBase()}${path}`, init);
  const data: unknown = await response.json();
  if (!response.ok) throw decodeUploadPreviewError(data, response.status);
  return data;
}
function path(revisionId: string, pageId: string): string {
  return `/api/v2/evidence-processing-revisions/${encodeURIComponent(revisionId)}/pages/${encodeURIComponent(pageId)}/local-verification`;
}
export async function getLocalVisualTask(revisionId: string, pageId: string, signal?: AbortSignal, jobId?: string | null): Promise<LocalVisualTask> {
  return decodeLocalVisualTask(await request(path(revisionId, pageId) + (jobId ? `?job_id=${encodeURIComponent(jobId)}` : ""), { method: "GET", signal }));
}
export async function startLocalVisualTask(revisionId: string, pageId: string, region: LocalVisualRegion): Promise<string> {
  const data = object(await request(path(revisionId, pageId), {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(region),
  }));
  if (typeof data.job_id !== "string" || !data.job_id || typeof data.state !== "string" || !states.has(data.state)) throw new EvidenceDecodeError("局部核实任务未能确认创建。");
  return data.job_id;
}
export async function actOnLocalVisualTask(jobId: string, action: "retry" | "cancel"): Promise<void> {
  await request(`/api/v2/jobs/${encodeURIComponent(jobId)}/${action}`, { method: "POST" });
}
