import { getProtocolApiBase } from "../protocolApiConfig";
import {
  decodeEligibilityReview,
  decodeEligibilityReviewError,
  type EligibilityReviewView,
} from "./eligibilityReviewViewModels";

export interface EligibilityReviewRequestOptions {
  signal?: AbortSignal;
}

export interface EligibilityReviewRepository {
  readonly kind: "http";
  getEligibilityReview(
    subjectId: string,
    reviewEpisodeId: string,
    options?: EligibilityReviewRequestOptions,
  ): Promise<EligibilityReviewView>;
}

export interface EligibilityReviewHttpOptions {
  fetchImpl?: typeof fetch;
}

function eligibilityReviewUrl(path: string): string {
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

export function createEligibilityReviewHttp(
  options: EligibilityReviewHttpOptions = {},
): EligibilityReviewRepository {
  const fetchImpl = options.fetchImpl ?? fetch.bind(globalThis);
  return {
    kind: "http",
    async getEligibilityReview(subjectId, reviewEpisodeId, requestOptions) {
      const response = await fetchImpl(
        eligibilityReviewUrl(
          `/api/v2/subjects/${encodeURIComponent(subjectId)}/review-episodes/${encodeURIComponent(reviewEpisodeId)}/eligibility-review`,
        ),
        { method: "GET", signal: requestOptions?.signal },
      );
      const payload = await readJson(response);
      if (!response.ok) {
        throw decodeEligibilityReviewError(payload, response.status);
      }
      if (payload === null || typeof payload !== "object" || Array.isArray(payload)) {
        throw decodeEligibilityReviewError(payload, response.status);
      }
      return decodeEligibilityReview(payload);
    },
  };
}

let defaultRepository: EligibilityReviewRepository | null = null;

export function getEligibilityReviewRepository(): EligibilityReviewRepository {
  if (defaultRepository === null) defaultRepository = createEligibilityReviewHttp();
  return defaultRepository;
}

/** 测试或本地浏览器验收可显式注入仓储。 */
export function setEligibilityReviewRepository(
  repository: EligibilityReviewRepository | null,
): void {
  defaultRepository = repository;
}

export { EligibilityReviewApiError, EligibilityReviewDecodeError } from "./eligibilityReviewViewModels";
