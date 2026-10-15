/**
 * 个例档案整理（事实规范化）API 出口。
 * 正式默认路径只走 HTTP；fixture 不得进入本 barrel。
 */

export {
  factNormalizationCommandPath,
  factNormalizationJobPath,
  factNormalizationJobRetryPath,
  factNormalizationJobStorageKey,
} from "./endpoints";
export {
  getFactNormalizationRepository,
  setFactNormalizationRepository,
  createFactNormalizationHttp,
  FactNormalizationApiError,
  FactNormalizationDecodeError,
  type FactNormalizationRepository,
  type FactNormalizationRequestOptions,
  type FactNormalizationStartInput,
} from "./factNormalizationRepository";
export {
  decodeFactNormalizationCommand,
  decodeFactNormalizationJobStatus,
  decodeFactNormalizationJobAction,
  decodeFactNormalizationError,
  factNormalizationDisplayPhase,
  factNormalizationPhaseTitle,
  factNormalizationRecoveryHint,
  isTerminalFactNormalizationState,
  isFailureFactNormalizationState,
  type FactNormalizationCommandView,
  type FactNormalizationJobStatusView,
  type FactNormalizationJobActionView,
  type FactNormalizationJobState,
  type FactNormalizationDisplayPhase,
} from "./factNormalizationViewModels";
