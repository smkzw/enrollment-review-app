/**
 * 证据工作台 HTTP 仓储：multipart 预览创建、错误信封解码、wire 读取。
 * 与 protocolWorkbenchHttp.ts 同构（shared/api 适配层唯一出口）。
 */

import { getProtocolApiBase } from "../protocolApiConfig";
import {
  decodeCommitResponse,
  decodeMetadataRevisionResponse,
  decodeSnapshot,
  decodeSnapshotList,
  decodeUploadPreview,
  decodeUploadPreviewError,
  EvidenceApiError,
  EvidenceDecodeError,
} from "./evidenceViewModels";
import {
  decodeCorrectionResponse,
  decodeActivationEvent,
  decodeBuildRevisionResponse,
  decodeOcrPage,
  decodeProcessingCandidateStatus,
  decodeProcessingRevision,
  decodeReferencedDocumentList,
  decodeReferencedDocument as decodeReferencedDocumentView,
  decodeRiskReviewResponse,
  decodeRiskPageReviewResponse,
  decodeReferencedDocumentResolution,
} from "./evidenceProcessingViewModels";
import type {
  CreateUploadPreviewInput,
  EvidenceCommitRequestWire,
  EvidenceMetadataRevisionRequestWire,
} from "./evidenceTypes";
import type {
  EvidenceCommitView,
  EvidenceMetadataRevisionResponseView,
  EvidenceSnapshotListView,
  EvidenceSnapshotView,
  EvidenceUploadPreviewView,
} from "./evidenceViewModels";
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
import type { EvidenceRepository } from "./evidenceRepository";

export interface EvidenceHttpOptions {
  fetchImpl?: typeof fetch;
}

/** 证据接口基址：同源相对路径（空字符串），开发环境由 Vite 代理至本机 V2 服务。 */
export function evidenceApiBase(): string {
  return getProtocolApiBase();
}

function evidenceUrl(path: string): string {
  const base = evidenceApiBase();
  return base.length > 0 ? `${base}${path}` : path;
}

export function evidencePageImageUrl(
  revisionId: string,
  entryId: string,
): string {
  return evidenceUrl(
    `/api/v2/evidence-processing-revisions/${encodeURIComponent(revisionId)}/pages/${encodeURIComponent(entryId)}/image`,
  );
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

export function createEvidenceHttp(
  options: EvidenceHttpOptions = {},
): EvidenceRepository {
  const fetchImpl = options.fetchImpl ?? fetch.bind(globalThis);

  async function request<T>(
    path: string,
    init: RequestInit,
    decode: (payload: unknown) => T,
  ): Promise<T> {
    const response = await fetchImpl(evidenceUrl(path), init);
    const payload = await readJson(response);
    if (!response.ok) {
      throw decodeUploadPreviewError(payload, response.status);
    }
    if (payload === null || typeof payload !== "object") {
      throw new EvidenceApiError(
        "INVALID_RESPONSE",
        "服务响应异常",
        "证据服务返回了无法识别的响应格式。",
        "请稍后重试；若问题持续出现，请联系维护人员。",
      );
    }
    return decode(payload);
  }

  return {
    kind: "http",

    async createUploadPreview(
      input: CreateUploadPreviewInput,
      options?: { signal?: AbortSignal },
    ): Promise<EvidenceUploadPreviewView> {
      const body = new FormData();
      body.append("review_episode_id", input.reviewEpisodeId);
      body.append("upload_mode", input.uploadMode);
      body.append("base_revision", String(input.baseRevision));
      if (input.actor !== undefined) body.append("actor", input.actor);
      for (const file of input.files) body.append("files", file, file.name);
      return request<EvidenceUploadPreviewView>(
        `/api/v2/subjects/${encodeURIComponent(input.subjectId)}/evidence-upload-previews`,
        { method: "POST", body, signal: options?.signal },
        decodeUploadPreview,
      );
    },

    async getUploadPreview(
      previewId: string,
      options?: { signal?: AbortSignal },
    ): Promise<EvidenceUploadPreviewView> {
      return request<EvidenceUploadPreviewView>(
        `/api/v2/evidence-upload-previews/${encodeURIComponent(previewId)}`,
        { method: "GET", signal: options?.signal },
        decodeUploadPreview,
      );
    },

    async cancelUploadPreview(
      previewId: string,
      options?: { signal?: AbortSignal },
    ): Promise<EvidenceUploadPreviewView> {
      return request<EvidenceUploadPreviewView>(
        `/api/v2/evidence-upload-previews/${encodeURIComponent(previewId)}`,
        { method: "DELETE", signal: options?.signal },
        decodeUploadPreview,
      );
    },

    async confirmUpload(
      previewId: string,
      body: EvidenceCommitRequestWire,
      options?: { signal?: AbortSignal },
    ): Promise<EvidenceCommitView> {
      return request<EvidenceCommitView>(
        `/api/v2/evidence-upload-previews/${encodeURIComponent(previewId)}/commit`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            preview_sha256: body.preview_sha256,
            upload_mode: body.upload_mode,
            base_revision: body.base_revision,
            idempotency_key: body.idempotency_key,
            ...(body.actor !== undefined ? { actor: body.actor } : {}),
            resolutions: body.resolutions,
          }),
          signal: options?.signal,
        },
        decodeCommitResponse,
      );
    },

    async listEvidenceSnapshots(
      subjectId: string,
      reviewEpisodeId: string,
      options?: { signal?: AbortSignal },
    ): Promise<EvidenceSnapshotListView> {
      return request<EvidenceSnapshotListView>(
        `/api/v2/subjects/${encodeURIComponent(subjectId)}/evidence-snapshots?review_episode_id=${encodeURIComponent(reviewEpisodeId)}`,
        { method: "GET", signal: options?.signal },
        decodeSnapshotList,
      );
    },

    async getEvidenceSnapshot(
      snapshotId: string,
      options?: { signal?: AbortSignal },
    ): Promise<EvidenceSnapshotView> {
      return request<EvidenceSnapshotView>(
        `/api/v2/evidence-snapshots/${encodeURIComponent(snapshotId)}`,
        { method: "GET", signal: options?.signal },
        decodeSnapshot,
      );
    },

    async reviseSourceDocumentMetadata(
      sourceDocumentVersionId: string,
      body: EvidenceMetadataRevisionRequestWire,
      options?: { signal?: AbortSignal },
    ): Promise<EvidenceMetadataRevisionResponseView> {
      return request<EvidenceMetadataRevisionResponseView>(
        `/api/v2/source-document-versions/${encodeURIComponent(sourceDocumentVersionId)}/metadata`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            document_type: body.document_type,
            source_party: body.source_party,
            reason: body.reason,
            expected_metadata_revision: body.expected_metadata_revision,
            idempotency_key: body.idempotency_key,
            ...(body.actor !== undefined ? { actor: body.actor } : {}),
          }),
          signal: options?.signal,
        },
        (payload) => {
          const decoded = decodeMetadataRevisionResponse(payload);
          if (decoded.metadata.sourceDocumentVersionId !== sourceDocumentVersionId) {
            throw new EvidenceDecodeError("资料信息修订与本次核对的资料不一致");
          }
          return decoded;
        },
      );
    },

    async getProcessingRevision(
      revisionId: string,
      options?: { signal?: AbortSignal },
    ): Promise<ProcessingRevisionView> {
      return request<ProcessingRevisionView>(
        `/api/v2/evidence-processing-revisions/${encodeURIComponent(revisionId)}`,
        { method: "GET", signal: options?.signal },
        decodeProcessingRevision,
      );
    },

    async getProcessingCandidate(
      candidateId: string,
      options?: { signal?: AbortSignal },
    ): Promise<ProcessingCandidateView> {
      return request<ProcessingCandidateView>(
        `/api/v2/evidence-processing-candidates/${encodeURIComponent(candidateId)}`,
        { method: "GET", signal: options?.signal },
        decodeProcessingCandidateStatus,
      );
    },

    async getOcrPage(
      ocrPageId: string,
      processingRevisionId: string,
      options?: { signal?: AbortSignal },
    ): Promise<OcrPageView> {
      return request<OcrPageView>(
        `/api/v2/ocr-pages/${encodeURIComponent(ocrPageId)}?processing_revision_id=${encodeURIComponent(processingRevisionId)}`,
        { method: "GET", signal: options?.signal },
        decodeOcrPage,
      );
    },

    async createCorrection(
      ocrPageId: string,
      body: CorrectionCreateRequestWire,
      options?: { signal?: AbortSignal },
    ): Promise<CorrectionCreateResponseView> {
      return request<CorrectionCreateResponseView>(
        `/api/v2/ocr-pages/${encodeURIComponent(ocrPageId)}/corrections`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          signal: options?.signal,
        },
        decodeCorrectionResponse,
      );
    },

    async createRiskReview(
      ocrPageId: string,
      body: RiskReviewCreateRequestWire,
      options?: { signal?: AbortSignal },
    ): Promise<RiskReviewCreateResponseView> {
      return request<RiskReviewCreateResponseView>(
        `/api/v2/ocr-pages/${encodeURIComponent(ocrPageId)}/risk-reviews`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          signal: options?.signal,
        },
        decodeRiskReviewResponse,
      );
    },

    async createRiskPageReview(
      ocrPageId: string,
      body: RiskPageReviewCreateRequestWire,
      options?: { signal?: AbortSignal },
    ): Promise<RiskPageReviewCreateResponseView> {
      return request<RiskPageReviewCreateResponseView>(
        `/api/v2/ocr-pages/${encodeURIComponent(ocrPageId)}/risk-page-reviews`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          signal: options?.signal,
        },
        decodeRiskPageReviewResponse,
      );
    },

    async buildProcessingRevision(
      body: BuildRevisionRequestWire,
      options?: { signal?: AbortSignal },
    ): Promise<BuildRevisionResponseView> {
      return request<BuildRevisionResponseView>(
        "/api/v2/evidence-processing-revisions/build",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          signal: options?.signal,
        },
        decodeBuildRevisionResponse,
      );
    },

    async activateProcessingRevision(
      revisionId: string,
      body: ActivateRevisionRequestWire,
      options?: { signal?: AbortSignal },
    ): Promise<ActivationEventView> {
      return request<ActivationEventView>(
        `/api/v2/evidence-processing-revisions/${encodeURIComponent(revisionId)}/activate`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          signal: options?.signal,
        },
        decodeActivationEvent,
      );
    },

    async listReferencedDocuments(
      subjectId: string,
      reviewEpisodeId: string,
      options?: { signal?: AbortSignal },
    ): Promise<ReferencedDocumentListView> {
      return request<ReferencedDocumentListView>(
        `/api/v2/subjects/${encodeURIComponent(subjectId)}/referenced-documents?review_episode_id=${encodeURIComponent(reviewEpisodeId)}`,
        { method: "GET", signal: options?.signal },
        decodeReferencedDocumentList,
      );
    },

    async createReferencedDocument(
      subjectId: string,
      body: ReferencedDocumentCreateRequestWire,
      options?: { signal?: AbortSignal },
    ): Promise<ReferencedDocumentView> {
      return request<ReferencedDocumentView>(
        `/api/v2/subjects/${encodeURIComponent(subjectId)}/referenced-documents`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          signal: options?.signal,
        },
        decodeReferencedDocumentView,
      );
    },

    async reviseReferencedDocument(
      referencedDocumentId: string,
      body: ReferencedDocumentReviseRequestWire,
      options?: { signal?: AbortSignal },
    ): Promise<ReferencedDocumentView> {
      return request<ReferencedDocumentView>(
        `/api/v2/referenced-documents/${encodeURIComponent(referencedDocumentId)}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          signal: options?.signal,
        },
        decodeReferencedDocumentView,
      );
    },

    async confirmReferencedDocument(
      referencedDocumentId: string,
      body: ReferencedDocumentConfirmRequestWire,
      options?: { signal?: AbortSignal },
    ): Promise<ReferencedDocumentView> {
      return request<ReferencedDocumentView>(
        `/api/v2/referenced-documents/${encodeURIComponent(referencedDocumentId)}/confirm`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          signal: options?.signal,
        },
        decodeReferencedDocumentView,
      );
    },

    async dismissReferencedDocument(
      referencedDocumentId: string,
      body: ReferencedDocumentDismissRequestWire,
      options?: { signal?: AbortSignal },
    ): Promise<ReferencedDocumentView> {
      return request<ReferencedDocumentView>(
        `/api/v2/referenced-documents/${encodeURIComponent(referencedDocumentId)}/dismiss`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          signal: options?.signal,
        },
        decodeReferencedDocumentView,
      );
    },

    async resolveReferencedDocument(
      referencedDocumentId: string,
      body: ReferencedDocumentResolveRequestWire,
      options?: { signal?: AbortSignal },
    ): Promise<ReferencedDocumentResolutionView> {
      return request<ReferencedDocumentResolutionView>(
        `/api/v2/referenced-documents/${encodeURIComponent(referencedDocumentId)}/resolve`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          signal: options?.signal,
        },
        decodeReferencedDocumentResolution,
      );
    },

    async unresolveReferencedDocument(
      referencedDocumentId: string,
      expectedRevision: number,
      idempotencyKey: string,
      options?: { signal?: AbortSignal },
    ): Promise<ReferencedDocumentResolutionView> {
      const query = new URLSearchParams({
        expected_revision: String(expectedRevision),
        idempotency_key: idempotencyKey,
      });
      return request<ReferencedDocumentResolutionView>(
        `/api/v2/referenced-documents/${encodeURIComponent(referencedDocumentId)}/resolution?${query.toString()}`,
        { method: "DELETE", signal: options?.signal },
        decodeReferencedDocumentResolution,
      );
    },
  };
}
