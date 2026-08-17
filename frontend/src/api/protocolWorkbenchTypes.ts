/**
 * V2 方案解构工作台 API 契约（与 app/api/v2/protocol_schemas.py 对齐）。
 * 组件经 mappers 消费 ViewModel，不直接使用 wire 结构。
 */

import type {
  DatePrecision,
  ProtocolSourcePrecision,
  StudyPhase,
} from "../domain/enums";

export type ConfirmableDatePrecision = Exclude<DatePrecision, "unknown">;

export interface ProtocolWorkbenchErrorBody {
  code: string;
  title: string;
  detail: string;
  recovery_action: string;
  correlation_id?: string;
}

export class ProtocolWorkbenchApiError extends Error {
  readonly code: string;
  readonly title: string;
  readonly recoveryAction: string;

  constructor(code: string, title: string, message: string, recoveryAction: string) {
    super(message);
    this.name = "ProtocolWorkbenchApiError";
    this.code = code;
    this.title = title;
    this.recoveryAction = recoveryAction;
  }
}

export interface StartDeconstructionResult {
  jobId: string;
  state: string;
  stateLabel: string;
  created: boolean;
  sourceArtifactId: string;
  fileName: string;
}

export interface ProtocolSessionView {
  jobId: string;
  jobType: string;
  state: string;
  stateLabel: string;
  progressCompleted: number;
  progressTotal: number;
  sessionKind: string;
  awaitingUser: string | null;
  awaitingUserLabel: string | null;
  sourceArtifactId: string | null;
  fileName: string | null;
  snapshotId: string | null;
  draftId: string | null;
  draftRevisionId: string | null;
  draftRevisionNumber: number | null;
  draftStatus: string | null;
  draftStatusLabel: string | null;
  selectedPhase: StudyPhase | null;
  selectedPhaseLabel: string | null;
  protocolCode: string | null;
  officialVersion: string | null;
  recoveryCheckpointId: string | null;
  recoveryStepId: string | null;
  nextAction: string;
  publishable: boolean | null;
  /** 重新解构：目标正式项目投影（sessionKind="re_deconstruction" 时有值）。 */
  targetProjectId: string | null;
  targetProjectName: string | null;
  targetProjectCode: string | null;
  targetProtocolCode: string | null;
  targetStudyPhase: StudyPhase | null;
  targetStudyPhaseLabel: string | null;
  targetOfficialVersion: string | null;
  targetRuleSetRevision: number | null;
}

export interface IdentityDecisionView {
  identityDecisionId: string;
  snapshotId: string;
  status: string;
  statusLabel: string;
  projectName: string | null;
  projectCode: string | null;
  protocolCode: string | null;
  officialVersion: string | null;
  officialDateValue: string | null;
  officialDatePrecision: DatePrecision | null;
  studyPhase: StudyPhase | null;
  studyPhaseLabel: string | null;
  confirmationRequired: boolean;
  conflictIds: string[];
  selectedCandidateIds: string[];
}

export interface PhaseCandidateView {
  candidateId: string;
  phase: StudyPhase;
  phaseLabel: string;
  rationale: string;
  sourceExcerpt: string;
}

export interface MetadataCandidateView {
  candidateId: string;
  field: string;
  fieldLabel: string;
  value: string;
  sourceLabel: string;
  sourceExcerpt: string;
  isFallback: boolean;
}

export interface MetadataConflictView {
  conflictId: string;
  field: string;
  fieldLabel: string;
  reason: string;
  candidates: ReadonlyArray<{ candidateId: string; value: string; sourceLabel: string }>;
}

export interface IdentityReviewView {
  jobId: string;
  snapshotId: string;
  confirmationRequired: boolean;
  identity: IdentityDecisionView;
  phaseCandidates: PhaseCandidateView[];
  metadataCandidates: MetadataCandidateView[];
  metadataConflicts: MetadataConflictView[];
}

export interface ConfirmIdentityInput {
  protocolCode: string;
  projectName: string;
  projectCode?: string | null;
  officialVersion: string;
  officialDateValue: string;
  officialDatePrecision: ConfirmableDatePrecision;
  studyPhase: StudyPhase;
  selectedCandidateIds?: string[];
  actor?: string;
}

export interface DraftRevisionView {
  jobId: string;
  revisionId: string;
  draftId: string;
  revisionNumber: number;
  status: string;
  statusLabel: string;
  reason: string;
  reasonLabel: string;
  actor: string;
  createdAt: string;
  studyPhase: StudyPhase;
  studyPhaseLabel: string;
  protocolCode: string | null;
  officialVersion: string | null;
  ruleCount: number;
  workflowStageCount: number;
  content: Record<string, unknown>;
  diff: Record<string, unknown> | null;
}

export interface IntegrityIssueView {
  issueCode: string;
  checkName: string;
  level: string;
  problem: string;
  impact: string;
  nextAction: string;
  affectedRefs: string[];
  repairScope: string[];
}

export interface IntegrityCheckView {
  checkName: string;
  passed: boolean;
  issueCount: number;
}

export interface IntegrityView {
  jobId: string;
  publishable: boolean;
  blockingCount: number;
  reviewCount: number;
  reminderCount: number;
  summary: string;
  checks: IntegrityCheckView[];
  issues: IntegrityIssueView[];
}

export interface SourceSpanView {
  sourceSpanId: string;
  sourceRef: string;
  pageLabel: string | null;
  excerpt: string;
  precision: ProtocolSourcePrecision;
  precisionLabel: string;
  degradationReason: string | null;
}

export interface SourcesView {
  jobId: string;
  snapshotId: string;
  selectedPhase: StudyPhase;
  selectedPhaseLabel: string;
  sourceSpans: Record<string, unknown>;
  sourceMaterials: Record<string, unknown>;
}

export interface PublishResultView {
  jobId: string;
  projectId: string;
  protocolVersionId: string;
  ruleSetId: string;
  ruleSetRevision: number;
  replay: boolean;
}

export interface OfficialProjectView {
  projectId: string;
  projectCode: string;
  projectName: string;
  studyPhase: StudyPhase;
  studyPhaseLabel: string;
  protocolCode: string;
  officialVersion: string;
  officialDateValue: string | null;
  officialDatePrecision: DatePrecision | null;
  ruleSetId: string;
  ruleSetRevision: number;
}

export interface ProjectVersionView {
  ruleSetRevision: number;
  protocolVersionId: string;
  officialVersion: string;
  officialDateValue: string | null;
  officialDatePrecision: DatePrecision | null;
  sha256: string;
  ruleCount: number;
  publishedAt: string;
}

export interface ProjectOfficialVersionView {
  project: OfficialProjectView;
  versions: ProjectVersionView[];
  publicationCount: number;
}

export interface DraftComparisonSideView {
  revisionId: string;
  draftId: string;
  protocolVersionId: string;
  officialVersion: string | null;
  revisionNumber: number | null;
  status: string | null;
  ruleCount: number;
  workflowStageCount: number;
  isFormalBaseline: boolean;
  content: Record<string, unknown>;
  sourceRefs: string[];
}

export interface DraftComparisonView {
  jobId: string;
  baseline: DraftComparisonSideView;
  candidate: DraftComparisonSideView;
  diff: Record<string, unknown>;
  sourceBound: boolean;
}

export type FeedbackKind = "source_error" | "clarification";

export interface FeedbackInput {
  expectedRevisionId: string;
  draft: Record<string, unknown>;
  feedbackKind: FeedbackKind;
  feedbackNote: string | null;
  actor?: string;
}
