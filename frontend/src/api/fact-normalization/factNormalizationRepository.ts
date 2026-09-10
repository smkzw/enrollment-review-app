/**
 * 个例档案整理数据访问：唯一出口。
 * 默认 HTTP；测试经 setFactNormalizationRepository 注入。
 */

import { createFactNormalizationHttp } from "./factNormalizationHttp";
import type {
  FactNormalizationCommandView,
  FactNormalizationJobActionView,
  FactNormalizationJobStatusView,
} from "./factNormalizationViewModels";

export {
  FactNormalizationApiError,
  FactNormalizationDecodeError,
} from "./factNormalizationViewModels";

export interface FactNormalizationRequestOptions {
  signal?: AbortSignal;
}

export interface FactNormalizationStartInput {
  /** 客户端幂等意图；服务端仍从活动权威派生真实幂等键。 */
  idempotencyKey: string;
}

export interface FactNormalizationRepository {
  readonly kind: "http";
  /** POST …/fact-normalization-jobs：创建或幂等复用持久整理任务。 */
  startFactNormalization(
    subjectId: string,
    reviewEpisodeId: string,
    input: FactNormalizationStartInput,
    options?: FactNormalizationRequestOptions,
  ): Promise<FactNormalizationCommandView>;
  /** GET /api/v2/jobs/{job_id}：读取持久任务状态。 */
  getFactNormalizationJobStatus(
    jobId: string,
    options?: FactNormalizationRequestOptions,
  ): Promise<FactNormalizationJobStatusView>;
  /** POST /api/v2/jobs/{job_id}/retry：只重试失败范围。 */
  retryFactNormalizationJob(
    jobId: string,
    options?: FactNormalizationRequestOptions,
  ): Promise<FactNormalizationJobActionView>;
}

let defaultRepo: FactNormalizationRepository | null = null;

export function getFactNormalizationRepository(): FactNormalizationRepository {
  if (defaultRepo === null) {
    defaultRepo = createFactNormalizationHttp();
  }
  return defaultRepo;
}

/** 测试显式注入假实现。 */
export function setFactNormalizationRepository(
  repo: FactNormalizationRepository | null,
): void {
  defaultRepo = repo;
}

export { createFactNormalizationHttp };
