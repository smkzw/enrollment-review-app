import { protocolDeconstructionsUrl } from "./protocolApiConfig";
import { decodeProtocolWorkbenchError } from "./protocolWorkbenchNormalize";

export type ReviewerKind = "medical_manager" | "builder_verification";
export interface RuleReviewRecord {
  record_id: string;
  official_code: string;
  rule_content_hash: string;
  reviewer_kind: ReviewerKind;
  reviewed_by: string;
  reviewed_at: string;
  action: "approved" | "revoked";
  note: string | null;
  result_variables: string[];
}
export interface RuleReviewEntry {
  official_code: string;
  kind: "rule" | "procedure" | "medication" | "scope";
  label: string;
  rule_content_hash: string;
  source_refs: string[];
  issue_refs: string[];
  review: RuleReviewRecord | null;
  reviewed_content_hash?: string | null;
}
export interface RuleReviews {
  job_id: string;
  draft_revision_id: string;
  operator_name: string;
  all_reviewed: boolean;
  entries: RuleReviewEntry[];
  history: RuleReviewRecord[];
}

function record(value: unknown): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) throw new Error("审定记录格式不完整，请刷新。");
  return value as Record<string, unknown>;
}
function readReview(value: unknown): RuleReviewRecord {
  const row = record(value);
  for (const key of ["record_id", "official_code", "rule_content_hash", "reviewed_by", "reviewed_at"]) {
    if (typeof row[key] !== "string" || row[key] === "") throw new Error("审定记录缺少信息，请刷新。");
  }
  if (!["medical_manager", "builder_verification"].includes(String(row.reviewer_kind)) ||
      !["approved", "revoked"].includes(String(row.action)) ||
      !(row.note === null || typeof row.note === "string") ||
      !Array.isArray(row.result_variables) || !row.result_variables.every(v => typeof v === "string")) throw new Error("审定记录格式不完整，请刷新。");
  // This endpoint inherits the SQLite UTC-naive storage convention. Do not
  // interpret an operation timestamp as the browser's local clinical date.
  const savedTime = String(row.reviewed_at);
  const reviewedAt = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/.test(savedTime) ? savedTime + "Z" : savedTime;
  if (!/(?:Z|[+-]\d{2}:\d{2})$/.test(reviewedAt) || Number.isNaN(Date.parse(reviewedAt)))
    throw new Error("审定时间不完整，请刷新。");
  return { ...row, reviewed_at: reviewedAt } as unknown as RuleReviewRecord;
}
export function decodeRuleReviews(value: unknown, jobId: string): RuleReviews {
  const row = record(value);
  if (row.job_id !== jobId || typeof row.draft_revision_id !== "string" || typeof row.operator_name !== "string" ||
      typeof row.all_reviewed !== "boolean" || !Array.isArray(row.entries) || !Array.isArray(row.history)) throw new Error("审定记录与当前任务不一致，请刷新。");
  const entries = row.entries.map(value => {
    const entry = record(value);
    if (typeof entry.official_code !== "string" || typeof entry.label !== "string" ||
        typeof entry.rule_content_hash !== "string" || !/^[a-f0-9]{64}$/.test(entry.rule_content_hash) ||
        !["rule", "procedure", "medication", "scope"].includes(String(entry.kind)) || !Array.isArray(entry.source_refs) ||
        !entry.source_refs.every(ref => typeof ref === "string") || !Array.isArray(entry.issue_refs) ||
        !entry.issue_refs.every(ref => typeof ref === "string")) throw new Error("条目审定信息不完整，请刷新。");
    const review = entry.review === null ? null : readReview(entry.review);
    if (entry.reviewed_content_hash != null && (!review || entry.reviewed_content_hash !== entry.rule_content_hash)) throw new Error("审定内容已经变化，请刷新。");
    if (review && (review.action !== "approved" || review.official_code !== entry.official_code ||
        (review.rule_content_hash !== entry.rule_content_hash && entry.reviewed_content_hash !== entry.rule_content_hash))) throw new Error("审定内容已经变化，请刷新。");
    return { ...entry, review } as unknown as RuleReviewEntry;
  });
  if (new Set(entries.map(entry => entry.official_code)).size !== entries.length ||
      row.all_reviewed !== (entries.length > 0 && entries.every(entry => entry.review !== null))) throw new Error("审定条目清单不一致，请刷新。");
  return { ...row, entries, history: row.history.map(readReview) } as unknown as RuleReviews;
}
export async function requestRuleReviews(jobId: string, options: {
  signal?: AbortSignal;
  entry?: RuleReviewEntry;
  draftRevisionId?: string;
  reviewerKind?: ReviewerKind;
  revoke?: boolean;
  excluded?: boolean;
  resultVariables?: string[];
  entries?: { official_code: string; rule_content_hash: string; note: string | null; result_variables: string[] }[];
} = {}): Promise<RuleReviews> {
  const path = options.entry
    ? `/draft/rules/${encodeURIComponent(options.entry.official_code)}/review` : "/draft/reviews";
  const response = await fetch(protocolDeconstructionsUrl(`/${encodeURIComponent(jobId)}${path}`), {
    method: options.entry ? options.revoke ? "DELETE" : "POST" : options.entries ? "POST" : "GET", signal: options.signal,
    ...(options.entry || options.entries ? {
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ expected_revision_id: options.draftRevisionId, reviewer_kind: options.reviewerKind,
        ...(options.entries ? { entries: options.entries } : {
          rule_content_hash: options.entry?.rule_content_hash,
          note: options.excluded ? "excluded" : null, result_variables: options.resultVariables ?? [],
        }) }),
    } : {}),
  });
  const value: unknown = await response.json();
  if (!response.ok) throw decodeProtocolWorkbenchError(value);
  return decodeRuleReviews(value, jobId);
}
