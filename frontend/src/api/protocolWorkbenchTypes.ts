/**
 * V2 方案解构工作台 API 契约（与 app/api/v2/protocol_schemas.py 对齐）。
 * 组件经 mappers 消费 ViewModel，不直接使用 wire 结构。
 */

export interface ProtocolWorkbenchErrorBody {
  code: string;
  title: string;
  detail: string;
  recovery_action: string;
  correlation_id?: string;
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
  selectedPhase: string | null;
  selectedPhaseLabel: string | null;
  protocolCode: string | null;
  officialVersion: string | null;
  recoveryCheckpointId: string | null;
  recoveryStepId: string | null;
  nextAction: string;
  publishable: boolean | null;
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
  officialDatePrecision: string | null;
  studyPhase: string | null;
  studyPhaseLabel: string | null;
  confirmationRequired: boolean;
  conflictIds: string[];
  selectedCandidateIds: string[];
}

export interface PhaseCandidateView {
  candidateId: string;
  phase: string;
  phaseLabel: string;
  rationale: string;
}

export interface MetadataConflictView {
  conflictId: string;
  field: string;
  fieldLabel: string;
  candidates: ReadonlyArray<{ candidateId: string; value: string; sourceLabel: string }>;
}

export interface IdentityReviewView {
  jobId: string;
  snapshotId: string;
  confirmationRequired: boolean;
  identity: IdentityDecisionView;
  phaseCandidates: PhaseCandidateView[];
  metadataCandidates: ReadonlyArray<Record<string, unknown>>;
  metadataConflicts: MetadataConflictView[];
}

export interface ConfirmIdentityInput {
  protocolCode: string;
  projectName: string;
  projectCode?: string | null;
  officialVersion: string;
  officialDateValue: string;
  officialDatePrecision: string;
  studyPhase: string;
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
  studyPhase: string;
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
  precision: string;
  precisionLabel: string;
  degradationReason: string | null;
}

export interface SourcesView {
  jobId: string;
  snapshotId: string;
  selectedPhase: string;
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
