/**
 * Patient Profile 领域模型出口：页面与组件只从这里消费适配后的 ViewModel。
 */

export {
  adaptPatientProfile,
  formatProfileDateTime,
  locatorsForItem,
  PROFILE_LANE_ORDER,
  type PatientProfileModel,
  type ProfileLaneModel,
  type ProfileHighlightModel,
} from "./patientProfileModel";
