/**
 * 证据工作台数据访问：唯一出口（与 protocolWorkbenchRepository 同构）。
 * 默认 HTTP 实现访问 V2 证据接口；测试经 setEvidenceRepository 注入假实现。
 */

import { createEvidenceHttp } from "./evidenceHttp";
import type {
  EvidenceCommitRequestWire,
  CreateUploadPreviewInput,
  EvidenceMetadataRevisionRequestWire,
} from "./evidenceTypes";
import type {
  BuildRevisionRequestWire,
  ActivateRevisionRequestWire,
  CorrectionCreateRequestWire,
  ReferencedDocumentConfirmRequestWire,
  ReferencedDocumentCreateRequestWire,
  ReferencedDocumentDismissRequestWire,
  ReferencedDocumentResolveRequestWire,
  ReferencedDocumentReviseRequestWire,
  RiskReviewCreateRequestWire,
  RiskPageReviewCreateRequestWire,
} from "./evidenceProcessingTypes";
import type {
  EvidenceCommitView,
  EvidenceMetadataRevisionResponseView,
  EvidenceSnapshotListView,
  EvidenceSnapshotView,
  EvidenceUploadPreviewView,
} from "./evidenceViewModels";
import type {
  BuildRevisionResponseView,
  ActivationEventView,
  CorrectionCreateResponseView,
  OcrPageView,
  ProcessingCandidateView,
  ProcessingRevisionView,
  ReferencedDocumentListView,
  ReferencedDocumentResolutionView,
  ReferencedDocumentView,
  RiskReviewCreateResponseView,
  RiskPageReviewCreateResponseView,
} from "./evidenceProcessingViewModels";

export { EvidenceApiError, EvidenceDecodeError } from "./evidenceViewModels";

export interface EvidenceRequestOptions {
  signal?: AbortSignal;
}

export interface EvidenceRepository {
  readonly kind: "http";
  /** POST /subjects/{subject_id}/evidence-upload-previews（multipart） */
  createUploadPreview(
    input: CreateUploadPreviewInput,
    options?: EvidenceRequestOptions,
  ): Promise<EvidenceUploadPreviewView>;
  /** GET /evidence-upload-previews/{preview_id} */
  getUploadPreview(
    previewId: string,
    options?: EvidenceRequestOptions,
  ): Promise<EvidenceUploadPreviewView>;
  /** DELETE /evidence-upload-previews/{preview_id}（幂等取消） */
  cancelUploadPreview(
    previewId: string,
    options?: EvidenceRequestOptions,
  ): Promise<EvidenceUploadPreviewView>;
  /** POST /evidence-upload-previews/{preview_id}/commit */
  confirmUpload(
    previewId: string,
    body: EvidenceCommitRequestWire,
    options?: EvidenceRequestOptions,
  ): Promise<EvidenceCommitView>;
  /** GET /subjects/{subject_id}/evidence-snapshots?review_episode_id=... */
  listEvidenceSnapshots(
    subjectId: string,
    reviewEpisodeId: string,
    options?: EvidenceRequestOptions,
  ): Promise<EvidenceSnapshotListView>;
  /** GET /evidence-snapshots/{snapshot_id} */
  getEvidenceSnapshot(
    snapshotId: string,
    options?: EvidenceRequestOptions,
  ): Promise<EvidenceSnapshotView>;
  /** PATCH /source-document-versions/{id}/metadata（追加资料元数据修订） */
  reviseSourceDocumentMetadata(
    sourceDocumentVersionId: string,
    body: EvidenceMetadataRevisionRequestWire,
    options?: EvidenceRequestOptions,
  ): Promise<EvidenceMetadataRevisionResponseView>;
  /** GET /evidence-processing-revisions/{revision_id} */
  getProcessingRevision(
    revisionId: string,
    options?: EvidenceRequestOptions,
  ): Promise<ProcessingRevisionView>;
  /** GET /evidence-processing-candidates/{candidate_id} */
  getProcessingCandidate(
    candidateId: string,
    options?: EvidenceRequestOptions,
  ): Promise<ProcessingCandidateView>;
  /** GET /ocr-pages/{ocr_page_id}?processing_revision_id=... */
  getOcrPage(
    ocrPageId: string,
    processingRevisionId: string,
    options?: EvidenceRequestOptions,
  ): Promise<OcrPageView>;
  /** POST /ocr-pages/{ocr_page_id}/corrections */
  createCorrection(
    ocrPageId: string,
    body: CorrectionCreateRequestWire,
    options?: EvidenceRequestOptions,
  ): Promise<CorrectionCreateResponseView>;
  /** POST /ocr-pages/{ocr_page_id}/risk-reviews */
  createRiskReview(
    ocrPageId: string,
    body: RiskReviewCreateRequestWire,
    options?: EvidenceRequestOptions,
  ): Promise<RiskReviewCreateResponseView>;
  /** POST /ocr-pages/{ocr_page_id}/risk-page-reviews */
  createRiskPageReview(
    ocrPageId: string,
    body: RiskPageReviewCreateRequestWire,
    options?: EvidenceRequestOptions,
  ): Promise<RiskPageReviewCreateResponseView>;
  /** POST /evidence-processing-revisions/build */
  buildProcessingRevision(
    body: BuildRevisionRequestWire,
    options?: EvidenceRequestOptions,
  ): Promise<BuildRevisionResponseView>;
  /** POST /evidence-processing-revisions/{revision_id}/activate */
  activateProcessingRevision(
    revisionId: string,
    body: ActivateRevisionRequestWire,
    options?: EvidenceRequestOptions,
  ): Promise<ActivationEventView>;
  /** GET /subjects/{subject_id}/referenced-documents?review_episode_id=... */
  listReferencedDocuments(
    subjectId: string,
    reviewEpisodeId: string,
    options?: EvidenceRequestOptions,
  ): Promise<ReferencedDocumentListView>;
  /** POST /subjects/{subject_id}/referenced-documents */
  createReferencedDocument(
    subjectId: string,
    body: ReferencedDocumentCreateRequestWire,
    options?: EvidenceRequestOptions,
  ): Promise<ReferencedDocumentView>;
  /** PATCH /referenced-documents/{referenced_document_id} */
  reviseReferencedDocument(
    referencedDocumentId: string,
    body: ReferencedDocumentReviseRequestWire,
    options?: EvidenceRequestOptions,
  ): Promise<ReferencedDocumentView>;
  /** POST /referenced-documents/{referenced_document_id}/confirm */
  confirmReferencedDocument(
    referencedDocumentId: string,
    body: ReferencedDocumentConfirmRequestWire,
    options?: EvidenceRequestOptions,
  ): Promise<ReferencedDocumentView>;
  /** POST /referenced-documents/{referenced_document_id}/dismiss */
  dismissReferencedDocument(
    referencedDocumentId: string,
    body: ReferencedDocumentDismissRequestWire,
    options?: EvidenceRequestOptions,
  ): Promise<ReferencedDocumentView>;
  /** POST /referenced-documents/{referenced_document_id}/resolve */
  resolveReferencedDocument(
    referencedDocumentId: string,
    body: ReferencedDocumentResolveRequestWire,
    options?: EvidenceRequestOptions,
  ): Promise<ReferencedDocumentResolutionView>;
  /** DELETE /referenced-documents/{referenced_document_id}/resolution */
  unresolveReferencedDocument(
    referencedDocumentId: string,
    expectedRevision: number,
    idempotencyKey: string,
    options?: EvidenceRequestOptions,
  ): Promise<ReferencedDocumentResolutionView>;
}

let defaultRepo: EvidenceRepository | null = null;

export function getEvidenceRepository(): EvidenceRepository {
  if (defaultRepo === null) {
    defaultRepo = createEvidenceHttp();
  }
  return defaultRepo;
}

/** 测试或 UAT 显式注入假实现。 */
export function setEvidenceRepository(repo: EvidenceRepository | null): void {
  defaultRepo = repo;
}

export { createEvidenceHttp };
