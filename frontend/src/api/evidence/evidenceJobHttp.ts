/** 任务详情读取与失败范围重试。 */

import { getProtocolApiBase } from "../protocolApiConfig";
import { decodeUploadPreviewError, EvidenceApiError } from "./evidenceViewModels";
import {
  decodeEvidenceJobProgress,
  decodeEvidenceJobStatus,
  type EvidenceJobDetailView,
  type EvidenceJobStatusView,
} from "./evidenceJobViewModels";

function url(path: string): string {
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

async function request<T>(
  path: string,
  init: RequestInit,
  decode: (payload: unknown) => T,
  fetchImpl: typeof fetch,
): Promise<T> {
  const response = await fetchImpl(url(path), init);
  const payload = await readJson(response);
  if (!response.ok) throw decodeUploadPreviewError(payload, response.status);
  if (payload === null || typeof payload !== "object") {
    throw new EvidenceApiError(
      "INVALID_RESPONSE",
      "服务响应异常",
      "资料整理服务返回了无法识别的内容。",
      "请稍后重试；若问题持续出现，请联系维护人员。",
    );
  }
  return decode(payload);
}

export async function getEvidenceJobDetail(
  jobId: string,
  signal?: AbortSignal,
  fetchImpl: typeof fetch = fetch.bind(globalThis),
): Promise<EvidenceJobDetailView> {
  const encoded = encodeURIComponent(jobId);
  const [status, progress] = await Promise.all([
    request(`/api/v2/jobs/${encoded}`, { method: "GET", signal }, decodeEvidenceJobStatus, fetchImpl),
    request(`/api/v2/jobs/${encoded}/evidence-progress`, { method: "GET", signal }, decodeEvidenceJobProgress, fetchImpl),
  ]);
  if (status.jobId !== progress.jobId) {
    throw new EvidenceApiError(
      "MISMATCHED_RESPONSE",
      "任务信息不一致",
      "任务状态与资料页进度不属于同一次处理。",
      "请刷新后重试；若问题持续出现，请联系维护人员。",
    );
  }
  if (
    status.state === "completed" &&
    (progress.failedPages > 0 || progress.pendingPages > 0)
  ) {
    throw new EvidenceApiError(
      "INCONSISTENT_PROGRESS",
      "处理状态需要重新核对",
      "总体状态显示已完成，但仍有页面未完成处理。",
      "请刷新后重试；系统不会把这次处理显示为完整结果。",
    );
  }
  return { status, progress };
}

export async function retryEvidenceJob(
  jobId: string,
  fetchImpl: typeof fetch = fetch.bind(globalThis),
): Promise<EvidenceJobStatusView> {
  const encoded = encodeURIComponent(jobId);
  await request(
    `/api/v2/jobs/${encoded}/retry`,
    { method: "POST" },
    (payload) => payload,
    fetchImpl,
  );
  return request(`/api/v2/jobs/${encoded}`, { method: "GET" }, decodeEvidenceJobStatus, fetchImpl);
}
