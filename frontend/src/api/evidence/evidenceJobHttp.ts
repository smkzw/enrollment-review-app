/** 任务详情读取与失败范围重试。 */

import { getProtocolApiBase } from "../protocolApiConfig";
import { decodeUploadPreviewError, EvidenceApiError } from "./evidenceViewModels";
import {
  decodeEvidenceJobProgress,
  decodeEvidenceJobStatus,
  decodeSelectiveVisionTask,
  decodeSelectiveVisionTaskAction,
  type EvidenceJobDetailView,
  type EvidenceJobStatusView,
  type SelectiveVisionTaskActionView,
  type SelectiveVisionTaskView,
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
  const status = await request(`/api/v2/jobs/${encoded}`, { method: "GET", signal }, decodeEvidenceJobStatus, fetchImpl);
  if (status.isTargetedReview || status.isPageReview) return { status, progress: null };
  const progress = await request(`/api/v2/jobs/${encoded}/evidence-progress`, { method: "GET", signal }, decodeEvidenceJobProgress, fetchImpl);
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

/** 修订 -> 页面视觉核验任务状态；刷新后凭修订编号即可恢复。 */
export async function getSelectiveVisionTask(
  revisionId: string,
  signal?: AbortSignal,
  fetchImpl: typeof fetch = fetch.bind(globalThis),
): Promise<SelectiveVisionTaskView> {
  const encoded = encodeURIComponent(revisionId);
  return request(
    `/api/v2/evidence-processing-revisions/${encoded}/selective-vision-task`,
    { method: "GET", signal },
    decodeSelectiveVisionTask,
    fetchImpl,
  );
}

/** 人工重新开始页面视觉核验的失败范围。 */
export async function retrySelectiveVisionTask(
  revisionId: string,
  fetchImpl: typeof fetch = fetch.bind(globalThis),
): Promise<SelectiveVisionTaskActionView> {
  const encoded = encodeURIComponent(revisionId);
  return request(
    `/api/v2/evidence-processing-revisions/${encoded}/selective-vision-task/retry`,
    { method: "POST" },
    decodeSelectiveVisionTaskAction,
    fetchImpl,
  );
}

/** 在安全边界停止页面视觉核验（终态任务为无副作用请求）。 */
export async function cancelSelectiveVisionTask(
  revisionId: string,
  fetchImpl: typeof fetch = fetch.bind(globalThis),
): Promise<SelectiveVisionTaskActionView> {
  const encoded = encodeURIComponent(revisionId);
  return request(
    `/api/v2/evidence-processing-revisions/${encoded}/selective-vision-task/cancel`,
    { method: "POST" },
    decodeSelectiveVisionTaskAction,
    fetchImpl,
  );
}
