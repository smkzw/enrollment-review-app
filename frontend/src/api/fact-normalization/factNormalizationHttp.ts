/**
 * 个例档案整理 HTTP 仓储：命令入口 + 标准 /api/v2/jobs 恢复。
 * 路径命名只经 endpoints.ts，便于与后端 worker_01 对齐。
 */

import { getProtocolApiBase } from "../protocolApiConfig";
import {
  factNormalizationCommandPath,
  factNormalizationJobPath,
  factNormalizationJobRetryPath,
} from "./endpoints";
import {
  decodeFactNormalizationCommand,
  decodeFactNormalizationError,
  decodeFactNormalizationJobAction,
  decodeFactNormalizationJobStatus,
  FactNormalizationApiError,
  type FactNormalizationCommandView,
  type FactNormalizationJobActionView,
  type FactNormalizationJobStatusView,
} from "./factNormalizationViewModels";
import type { FactNormalizationRepository } from "./factNormalizationRepository";

export interface FactNormalizationHttpOptions {
  fetchImpl?: typeof fetch;
}

function apiUrl(path: string): string {
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

export function createFactNormalizationHttp(
  options: FactNormalizationHttpOptions = {},
): FactNormalizationRepository {
  const fetchImpl = options.fetchImpl ?? fetch.bind(globalThis);

  async function request<T>(
    path: string,
    init: RequestInit,
    decode: (payload: unknown) => T,
  ): Promise<T> {
    const response = await fetchImpl(apiUrl(path), init);
    const payload = await readJson(response);
    if (!response.ok) {
      throw decodeFactNormalizationError(payload, response.status);
    }
    if (payload === null || typeof payload !== "object") {
      throw new FactNormalizationApiError(
        "INVALID_RESPONSE",
        "服务响应异常",
        "个例档案整理服务返回了无法识别的内容。",
        "请稍后重试；若问题持续出现，请联系维护人员。",
      );
    }
    return decode(payload);
  }

  return {
    kind: "http",

    async startFactNormalization(
      subjectId: string,
      reviewEpisodeId: string,
      input: { idempotencyKey: string },
      options?: { signal?: AbortSignal },
    ): Promise<FactNormalizationCommandView> {
      return request(
        factNormalizationCommandPath(subjectId, reviewEpisodeId),
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ idempotency_intent: input.idempotencyKey }),
          signal: options?.signal,
        },
        decodeFactNormalizationCommand,
      );
    },

    async getFactNormalizationJobStatus(
      jobId: string,
      options?: { signal?: AbortSignal },
    ): Promise<FactNormalizationJobStatusView> {
      return request(
        factNormalizationJobPath(jobId),
        { method: "GET", signal: options?.signal },
        decodeFactNormalizationJobStatus,
      );
    },

    async retryFactNormalizationJob(
      jobId: string,
      options?: { signal?: AbortSignal },
    ): Promise<FactNormalizationJobActionView> {
      return request(
        factNormalizationJobRetryPath(jobId),
        { method: "POST", signal: options?.signal },
        decodeFactNormalizationJobAction,
      );
    },
  };
}
