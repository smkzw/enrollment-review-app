import { getProtocolApiBase } from "./protocolApiConfig";
import { decodeUploadPreviewError } from "./evidence/evidenceViewModels";
import type { OcrBatchMember } from "./evidence/reprocessingBatches";

export type BatchProcessingKind = "review" | "ocr";
export interface BatchProcessingEstimate {
  samples: number; medianSeconds: number | null; lowerSeconds: number | null; upperSeconds: number | null;
  historyTruncated: boolean;
}
function invalid(): never { throw new Error("历史耗时暂时无法核实，请稍后刷新。未开始处理资料。"); }
function object(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : invalid();
}
function duration(value: unknown): number | null {
  return value === null ? null : typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : invalid();
}
export async function readBatchProcessingEstimate(projectId: string, kind: BatchProcessingKind, members: OcrBatchMember[], signal: AbortSignal): Promise<BatchProcessingEstimate> {
  const endpoint = kind === "review" ? "review-batches" : "reprocessing-batches";
  const response = await fetch(`${getProtocolApiBase()}/api/v2/projects/${encodeURIComponent(projectId)}/${endpoint}/estimate`, {
    method: "POST", signal, headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ members: members.map(item => ({ subject_id: item.subjectId, review_episode_id: item.episodeId,
      snapshot_id: item.snapshotId, complete_id: item.processingId })) }),
  });
  const raw: unknown = await response.json();
  if (!response.ok) throw decodeUploadPreviewError(raw, response.status);
  const value = object(raw), cost = object(value.cost);
  if (value.project_id !== projectId || value.kind !== kind || value.member_count !== members.length
    || value.method !== "same-source-batch-history/v1" || !Number.isInteger(value.sample_count)
    || Number(value.sample_count) < 0 || Number(value.sample_count) > 100
    || !Number.isInteger(value.excluded_count) || Number(value.excluded_count) < 0
    || typeof value.history_truncated !== "boolean" || !Array.isArray(value.source_batch_ids)
    || value.source_batch_ids.length !== value.sample_count
    || value.source_batch_ids.some(id => typeof id !== "string" || !id.trim())
    || new Set(value.source_batch_ids).size !== value.source_batch_ids.length
    || cost.amount !== null || cost.currency !== null || cost.reason !== "no_verified_billing_basis") return invalid();
  const samples = Number(value.sample_count), medianSeconds = duration(value.median_seconds);
  const lowerSeconds = duration(value.lower_seconds), upperSeconds = duration(value.upper_seconds);
  if ((samples === 0) !== (medianSeconds === null)
    || (samples < 3 ? lowerSeconds !== null || upperSeconds !== null
      : lowerSeconds === null || upperSeconds === null || medianSeconds === null || lowerSeconds > medianSeconds || medianSeconds > upperSeconds)) return invalid();
  return { samples, medianSeconds, lowerSeconds, upperSeconds, historyTruncated: value.history_truncated };
}
