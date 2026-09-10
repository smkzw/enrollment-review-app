/**
 * Patient Profile 数据访问：唯一出口（与 evidenceRepository 同构）。
 * 默认 HTTP 实现访问 Slice 5.5 V2 档案接口；测试经 setPatientProfileRepository
 * 注入假实现。正式默认路径只消费解码后的领域视图，绝不读取旧 fixture。
 */

import { createPatientProfileHttp } from "./patientProfileHttp";
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

export {
  PatientProfileApiError,
  PatientProfileDecodeError,
} from "./patientProfileViewModels";

export interface PatientProfileRequestOptions {
  signal?: AbortSignal;
}

export interface PatientProfileRepository {
  readonly kind: "http";
  /** GET /subjects/{subject_id}/review-episodes/{review_episode_id}/patient-profile */
  getLatestPatientProfile(
    subjectId: string,
    reviewEpisodeId: string,
    options?: PatientProfileRequestOptions,
  ): Promise<PatientProfileRevisionView>;
  /** GET .../patient-profile/history（全部历史 revision，按 revision 升序） */
  listPatientProfileHistory(
    subjectId: string,
    reviewEpisodeId: string,
    options?: PatientProfileRequestOptions,
  ): Promise<PatientProfileHistoryView>;
  /** GET /subjects/{subject_id}/patient-profile-revisions/{patient_profile_revision_id} */
  getPatientProfileRevision(
    subjectId: string,
    patientProfileRevisionId: string,
    options?: PatientProfileRequestOptions,
  ): Promise<PatientProfileRevisionView>;
  /** POST .../fact-corrections/preview：只读预览，不创建修订或任务。 */
  previewFactCorrection(
    subjectId: string,
    reviewEpisodeId: string,
    input: FactCorrectionRequestInput,
    options?: PatientProfileRequestOptions,
  ): Promise<FactCorrectionPreviewView>;
  /** POST .../fact-corrections：创建或幂等复用持久修订任务。 */
  submitFactCorrection(
    subjectId: string,
    reviewEpisodeId: string,
    input: FactCorrectionRequestInput,
    options?: PatientProfileRequestOptions,
  ): Promise<FactCorrectionSubmitView>;
  /** GET .../fact-corrections：不可变人工修订历史。 */
  listFactCorrectionHistory(
    subjectId: string,
    reviewEpisodeId: string,
    options?: PatientProfileRequestOptions,
  ): Promise<FactCorrectionHistoryView>;
  /** GET /api/v2/jobs/{job_id}：读取持久任务状态。 */
  getFactCorrectionJobStatus(
    jobId: string,
    options?: PatientProfileRequestOptions,
  ): Promise<FactCorrectionJobStatusView>;
  /** POST /api/v2/jobs/{job_id}/cancel：持久停止请求。 */
  cancelFactCorrectionJob(
    jobId: string,
    options?: PatientProfileRequestOptions,
  ): Promise<FactCorrectionJobActionView>;
  /** POST /api/v2/jobs/{job_id}/retry：只重试失败范围。 */
  retryFactCorrectionJob(
    jobId: string,
    options?: PatientProfileRequestOptions,
  ): Promise<FactCorrectionJobActionView>;
}

let defaultRepo: PatientProfileRepository | null = null;

export function getPatientProfileRepository(): PatientProfileRepository {
  if (defaultRepo === null) {
    defaultRepo = createPatientProfileHttp();
  }
  return defaultRepo;
}

/** 测试或 UAT 显式注入假实现。 */
export function setPatientProfileRepository(
  repo: PatientProfileRepository | null,
): void {
  defaultRepo = repo;
}

export { createPatientProfileHttp };
