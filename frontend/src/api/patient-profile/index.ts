/**
 * Patient Profile v2 API 出口：页面与组件只从此处获取档案数据。
 * 默认 HTTP 仓储访问 Slice 5.5 真实接口；测试经 setPatientProfileRepository
 * 注入假实现。fixture 只存在于测试专属模块，不在此导出（不进入正式默认路径）。
 */

export {
  getPatientProfileRepository,
  setPatientProfileRepository,
  createPatientProfileHttp,
  PatientProfileApiError,
  PatientProfileDecodeError,
  type PatientProfileRepository,
  type PatientProfileRequestOptions,
} from "./patientProfileRepository";
export {
  decodePatientProfileRevision,
  decodePatientProfileHistory,
  decodePatientProfileError,
  type PatientProfileRevisionView,
  type PatientProfileHistoryView,
  type ProfileItemView,
  type ProfileLaneSectionView,
  type ProfileHighlightView,
  type ProfileDateRangeView,
  type ProfileEvidenceNavigationView,
  type ProfileScalarValue,
  type ProfileStatus,
} from "./patientProfileViewModels";
export type {
  ProfileStatusWire,
  ProfileLaneWire,
  ProfileItemKindWire,
  ProfileDatePrecisionWire,
  ProfileFactPolarityWire,
  ProfileDurationStatusWire,
  ProfileSourceStrengthWire,
  ProfileExpectationStatusWire,
  ProfileGapTypeWire,
  ProfileHighlightReasonWire,
  ProfileConflictMemberKindWire,
  ProfileDateRangeWire,
  ProfileEvidenceNavigationWire,
  ProfileItemWire,
  ProfileLaneSectionWire,
  ProfileHighlightWire,
  PatientProfileRevisionWire,
  PatientProfileHistoryWire,
  PatientProfileErrorEnvelope,
} from "./patientProfileTypes";
export type {
  FactCorrectionDateRangeInput,
  FactCorrectionJsonValue,
  FactCorrectionRequestInput,
  FactCorrectionTargetKind,
  FactCorrectionUpdates,
} from "./factCorrectionTypes";
export {
  decodeFactCorrectionError,
  decodeFactCorrectionHistory,
  decodeFactCorrectionJobAction,
  decodeFactCorrectionJobStatus,
  decodeFactCorrectionPreview,
  decodeFactCorrectionSubmit,
  type FactCorrectionHistoryView,
  type FactCorrectionImpactView,
  type FactCorrectionJobActionView,
  type FactCorrectionJobState,
  type FactCorrectionJobStatusView,
  type FactCorrectionJsonRecord,
  type FactCorrectionPreviewView,
  type FactCorrectionRecordView,
  type FactCorrectionSubmitView,
} from "./factCorrectionViewModels";
export type { LocatorView } from "../evidence/evidenceProcessingViewModels";
