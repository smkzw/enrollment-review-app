/**
 * 前端唯一数据访问出口：组件与页面只从此处获取数据。
 * Phase 1 为 stub 实现；真实 API 就绪后在同一接口下替换实现。
 */

export {
  createStubRepository,
  getDefaultRepository,
  StubApiError,
  type EnrollmentRepository,
} from "./stubRepository";
export {
  getProtocolWorkbenchRepository,
  setProtocolWorkbenchRepository,
  createProtocolWorkbenchStub,
  createProtocolWorkbenchHttp,
  ProtocolWorkbenchApiError,
  PROTOCOL_DEMO_JOB_ID,
  PROTOCOL_IDENTITY_JOB_ID,
  PROTOCOL_RECOVERY_JOB_ID,
  type ProtocolWorkbenchRepository,
} from "./protocolWorkbenchRepository";
export type {
  ProtocolSessionView,
  DraftRevisionView,
  IdentityReviewView,
  IntegrityView,
  SourcesView,
} from "./protocolWorkbenchTypes";
export { FIXTURE_SCHEMA_VERSION } from "./fixtureAssets";
export {
  getEvidenceRepository,
  setEvidenceRepository,
  createEvidenceHttp,
  EvidenceApiError,
  EvidenceDecodeError,
  type EvidenceRepository,
  type EvidenceUploadPreviewView,
  type EvidenceSnapshotView,
  type EvidenceCommitView,
  type EvidenceItemView,
  type EvidenceUploadMode,
  type EvidenceItemStatus,
  type EvidenceConflictResolution,
} from "./evidence";
export {
  subscribeJobEvents,
  type JobEventSubscription,
  type PersistentJobDone,
  type PersistentJobEvent,
  type SubscribeJobEventsOptions,
} from "./jobEvents";
export {
  getCatalogRepository,
  setCatalogRepository,
  createCatalogHttp,
  createCatalogTrial,
  CatalogApiError,
  type CatalogRepository,
  type CatalogProjectView,
  type CatalogSubjectView,
  type CatalogEpisodeView,
  type EvidenceContextView,
  type SubjectCreateInput,
} from "./catalog";
export {
  getPatientProfileRepository,
  setPatientProfileRepository,
  createPatientProfileHttp,
  PatientProfileApiError,
  PatientProfileDecodeError,
  type PatientProfileRepository,
  type PatientProfileRevisionView,
  type PatientProfileHistoryView,
} from "./patient-profile";
export {
  getEligibilityReviewRepository,
  setEligibilityReviewRepository,
  createEligibilityReviewHttp,
  EligibilityReviewApiError,
  EligibilityReviewDecodeError,
  type EligibilityReviewRepository,
  type EligibilityReviewHttpOptions,
  type EligibilityReviewRequestOptions,
  type EligibilityReviewView,
  type EligibilityClauseView,
  type EligibilityFactRefView,
  type EligibilityDecision,
  type EligibilityDeterminationMode,
  type EligibilityRuleKind,
} from "./eligibility-review";
