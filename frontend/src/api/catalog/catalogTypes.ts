import type { DatePrecision, StudyPhase } from "../../domain/enums";

export interface CatalogProjectView {
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

export interface CatalogSubjectView {
  subjectId: string;
  subjectCode: string;
  projectId: string;
  centerCode: string | null;
  centerName: string | null;
  sex: string | null;
  ageYears: number | null;
  revision: number;
}

/** 新增受试者的提交内容（与后端 SubjectCreateRequest 对应）。 */
export interface SubjectCreateInput {
  subjectCode: string;
  centerCode?: string | null;
  centerName?: string | null;
  sex?: string | null;
  ageYears?: number | null;
}

export interface CatalogEpisodeView {
  reviewEpisodeId: string;
  subjectId: string;
  projectId: string;
  ruleSetId: string;
  studyPhase: string;
  studyPhaseLabel: string;
  stage: string;
  stageLabel: string;
  protocolVersionId: string;
  ruleSetRevision: number;
  evidenceSnapshotId: string | null;
  workflowStageId: string | null;
  workflowStageLabel: string | null;
  visitWindow: string | null;
  latestEvidenceSnapshotId: string | null;
  activeEvidenceSnapshotId: string | null;
  activeEvidenceProcessingRevisionId: string | null;
  anchorDates: Readonly<Record<string, unknown>>;
  dueAt: string | null;
  revision: number;
}

export interface EvidenceContextView {
  project: CatalogProjectView;
  subject: CatalogSubjectView;
  episode: CatalogEpisodeView;
}

export class CatalogApiError extends Error {
  readonly recoveryAction: string;

  constructor(message: string, recoveryAction: string) {
    super(message);
    this.name = "CatalogApiError";
    this.recoveryAction = recoveryAction;
  }
}
