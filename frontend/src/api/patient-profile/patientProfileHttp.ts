/**
 * Patient Profile HTTP 仓储：Slice 5.5 档案读取、错误信封解码、wire 读取。
 * 与 evidenceHttp.ts 同构（shared/api 适配层唯一出口）；所有响应经严格运行时解码。
 */

import { getProtocolApiBase } from "../protocolApiConfig";
import {
  decodePatientProfileError,
  decodePatientProfileHistory,
  decodePatientProfileRevision,
  PatientProfileApiError,
} from "./patientProfileViewModels";
import type { PatientProfileRepository } from "./patientProfileRepository";
import { encodeFactCorrectionRequest } from "./factCorrectionTypes";
import {
  decodeFactCorrectionHistory,
  decodeFactCorrectionJobAction,
  decodeFactCorrectionJobStatus,
  decodeFactCorrectionPreview,
  decodeFactCorrectionSubmit,
} from "./factCorrectionViewModels";
import type {
  PatientProfileHistoryView,
  PatientProfileRevisionView,
} from "./patientProfileViewModels";
import type { FactCorrectionRequestInput } from "./factCorrectionTypes";
import type {
  FactCorrectionHistoryView,
  FactCorrectionJobActionView,
  FactCorrectionJobStatusView,
  FactCorrectionPreviewView,
  FactCorrectionSubmitView,
} from "./factCorrectionViewModels";

export interface PatientProfileHttpOptions {
  fetchImpl?: typeof fetch;
}

/** 档案接口基址：同源相对路径（空字符串），开发环境由 Vite 代理至本机 V2 服务。 */
export function patientProfileApiBase(): string {
  return getProtocolApiBase();
}

function patientProfileUrl(path: string): string {
  const base = patientProfileApiBase();
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

export function createPatientProfileHttp(
  options: PatientProfileHttpOptions = {},
): PatientProfileRepository {
  const fetchImpl = options.fetchImpl ?? fetch.bind(globalThis);

  async function request<T>(
    path: string,
    init: RequestInit,
    decode: (payload: unknown) => T,
  ): Promise<T> {
    const response = await fetchImpl(patientProfileUrl(path), init);
    const payload = await readJson(response);
    if (!response.ok) {
      throw decodePatientProfileError(payload, response.status);
    }
    if (payload === null || typeof payload !== "object") {
      throw new PatientProfileApiError(
        "INVALID_RESPONSE",
        "服务响应异常",
        "病历档案服务返回了无法识别的响应格式。",
        "请稍后重试；若问题持续出现，请联系维护人员。",
      );
    }
    return decode(payload);
  }

  return {
    kind: "http",

    async getLatestPatientProfile(
      subjectId: string,
      reviewEpisodeId: string,
      options?: { signal?: AbortSignal },
    ): Promise<PatientProfileRevisionView> {
      return request(
        `/api/v2/subjects/${encodeURIComponent(subjectId)}/review-episodes/${encodeURIComponent(reviewEpisodeId)}/patient-profile`,
        { method: "GET", signal: options?.signal },
        decodePatientProfileRevision,
      );
    },

    async listPatientProfileHistory(
      subjectId: string,
      reviewEpisodeId: string,
      options?: { signal?: AbortSignal },
    ): Promise<PatientProfileHistoryView> {
      return request(
        `/api/v2/subjects/${encodeURIComponent(subjectId)}/review-episodes/${encodeURIComponent(reviewEpisodeId)}/patient-profile/history`,
        { method: "GET", signal: options?.signal },
        decodePatientProfileHistory,
      );
    },

    async getPatientProfileRevision(
      subjectId: string,
      patientProfileRevisionId: string,
      options?: { signal?: AbortSignal },
    ): Promise<PatientProfileRevisionView> {
      return request(
        `/api/v2/subjects/${encodeURIComponent(subjectId)}/patient-profile-revisions/${encodeURIComponent(patientProfileRevisionId)}`,
        { method: "GET", signal: options?.signal },
        decodePatientProfileRevision,
      );
    },

    async previewFactCorrection(
      subjectId: string,
      reviewEpisodeId: string,
      input: FactCorrectionRequestInput,
      options?: { signal?: AbortSignal },
    ): Promise<FactCorrectionPreviewView> {
      return request(
        `/api/v2/subjects/${encodeURIComponent(subjectId)}/review-episodes/${encodeURIComponent(reviewEpisodeId)}/fact-corrections/preview`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(encodeFactCorrectionRequest(input)),
          signal: options?.signal,
        },
        decodeFactCorrectionPreview,
      );
    },

    async submitFactCorrection(
      subjectId: string,
      reviewEpisodeId: string,
      input: FactCorrectionRequestInput,
      options?: { signal?: AbortSignal },
    ): Promise<FactCorrectionSubmitView> {
      return request(
        `/api/v2/subjects/${encodeURIComponent(subjectId)}/review-episodes/${encodeURIComponent(reviewEpisodeId)}/fact-corrections`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(encodeFactCorrectionRequest(input)),
          signal: options?.signal,
        },
        decodeFactCorrectionSubmit,
      );
    },

    async listFactCorrectionHistory(
      subjectId: string,
      reviewEpisodeId: string,
      options?: { signal?: AbortSignal },
    ): Promise<FactCorrectionHistoryView> {
      return request(
        `/api/v2/subjects/${encodeURIComponent(subjectId)}/review-episodes/${encodeURIComponent(reviewEpisodeId)}/fact-corrections`,
        { method: "GET", signal: options?.signal },
        decodeFactCorrectionHistory,
      );
    },

    async getFactCorrectionJobStatus(
      jobId: string,
      options?: { signal?: AbortSignal },
    ): Promise<FactCorrectionJobStatusView> {
      return request(
        `/api/v2/jobs/${encodeURIComponent(jobId)}`,
        { method: "GET", signal: options?.signal },
        decodeFactCorrectionJobStatus,
      );
    },

    async cancelFactCorrectionJob(
      jobId: string,
      options?: { signal?: AbortSignal },
    ): Promise<FactCorrectionJobActionView> {
      return request(
        `/api/v2/jobs/${encodeURIComponent(jobId)}/cancel`,
        { method: "POST", signal: options?.signal },
        decodeFactCorrectionJobAction,
      );
    },

    async retryFactCorrectionJob(
      jobId: string,
      options?: { signal?: AbortSignal },
    ): Promise<FactCorrectionJobActionView> {
      return request(
        `/api/v2/jobs/${encodeURIComponent(jobId)}/retry`,
        { method: "POST", signal: options?.signal },
        decodeFactCorrectionJobAction,
      );
    },
  };
}
