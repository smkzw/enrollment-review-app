import { getProtocolApiBase, protocolJobsUrl } from "./protocolApiConfig";
import { decodeProtocolWorkbenchError } from "./protocolWorkbenchNormalize";
import { ProtocolWorkbenchApiError } from "./protocolWorkbenchTypes";
import { normalizeProtocolControlRequirements, type ProtocolControlRequirements } from "./protocolControlView";

export interface ProtocolControlStatus {
  jobId: string;
  sourceJobId: string;
  state: string;
  status: "candidate_ready" | "processing" | "stopped";
  statusLabel: string;
  checkpointId: string | null;
  candidateCount: number | null;
}

function invalidResponse(): never {
  throw new ProtocolWorkbenchApiError(
    "INVALID_RESPONSE", "补充审核要求暂不可用",
    "保存的整理结果不完整，暂不能随方案发布。",
    "请刷新查看；原方案和已保存的整理结果不会被覆盖。",
  );
}

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return invalidResponse();
  return value as Record<string, unknown>;
}

function text(value: unknown): string {
  if (typeof value !== "string" || !value.trim()) return invalidResponse();
  return value;
}

async function request(suffix: string, init: RequestInit): Promise<Record<string, unknown>> {
  const response = await fetch(`${getProtocolApiBase()}/api/v2/protocol/control-executions${suffix}`, init);
  let payload: unknown;
  try { payload = await response.json(); } catch { payload = null; }
  if (!response.ok) throw decodeProtocolWorkbenchError(payload);
  return record(payload);
}

export async function startProtocolControls(sourceJobId: string, signal: AbortSignal): Promise<string> {
  const payload = await request("", {
    method: "POST", signal, headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      source_job_id: sourceJobId,
      idempotency_key: `control-publication-v3:${sourceJobId}`,
    }),
  });
  if (payload.source_job_id !== sourceJobId) return invalidResponse();
  return text(payload.job_id);
}

export async function getProtocolControlStatus(jobId: string, signal: AbortSignal): Promise<ProtocolControlStatus> {
  const payload = await request(`/${encodeURIComponent(jobId)}`, { signal });
  if (payload.job_id !== jobId) return invalidResponse();
  const status = payload.status;
  if (status !== "candidate_ready" && status !== "processing" && status !== "stopped") return invalidResponse();
  const checkpointId = payload.publishable_checkpoint_id;
  const candidateCount = payload.candidate_count;
  if (status === "candidate_ready") {
    text(checkpointId);
    if (typeof candidateCount !== "number" || !Number.isSafeInteger(candidateCount) || candidateCount < 0) return invalidResponse();
  } else if (checkpointId !== null || candidateCount !== null) {
    return invalidResponse();
  }
  return {
    jobId, sourceJobId: text(payload.source_job_id), state: text(payload.state),
    status, statusLabel: text(payload.status_label),
    checkpointId: checkpointId as string | null,
    candidateCount: candidateCount as number | null,
  };
}

export async function getProtocolControlRequirements(
  status: ProtocolControlStatus, signal: AbortSignal,
): Promise<ProtocolControlRequirements> {
  if (status.status !== "candidate_ready") return invalidResponse();
  const result = normalizeProtocolControlRequirements(await request(
    `/${encodeURIComponent(status.jobId)}/requirements`, { signal },
  ));
  if (result.jobId !== status.jobId || result.sourceJobId !== status.sourceJobId ||
      result.checkpointId !== status.checkpointId || result.requirements.length !== status.candidateCount) {
    return invalidResponse();
  }
  return result;
}

export async function retryProtocolControls(jobId: string, signal: AbortSignal): Promise<void> {
  const response = await fetch(protocolJobsUrl(`/${encodeURIComponent(jobId)}/retry`), { method: "POST", signal });
  let payload: unknown;
  try { payload = await response.json(); } catch { payload = null; }
  if (!response.ok) throw decodeProtocolWorkbenchError(payload);
  const result = record(payload);
  if (result.job_id !== jobId || result.state !== "queued" || result.changed !== true) invalidResponse();
}
