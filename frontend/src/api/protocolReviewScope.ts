import { protocolDeconstructionsUrl } from "./protocolApiConfig";
import { decodeProtocolWorkbenchError } from "./protocolWorkbenchNormalize";

export const scopeLabels = {
  official_rule_text: "入选与排除标准",
  referenced_source: "条款引用的说明",
  required_procedure: "必做检验、检查与评估",
  medication_section: "用药与伴随治疗章节",
} as const;
export type ScopeKind = keyof typeof scopeLabels;
export interface ScopeCandidate {
  candidate_key: string; scope_kind: ScopeKind; label: string;
  source_span_ids: string[]; official_codes: string[]; visit_instance: string | null;
  clinically_confirmed: false;
}
export interface ScopeRecord {
  source_span_id: string; raw_text: string | null; render_page: number | null;
  identity_status: "ok" | "unknown_span" | "cross_snapshot" | "source_mismatch" | "excerpt_mismatch";
}
export interface ScopeDiagnostic {
  kind: string; identifiers: string[]; related_official_codes: string[];
}
export interface ReviewScopeView {
  job_id: string; draft_revision_id: string; scope_content_hash: string;
  clinical_adoption_applied: false;
  candidates: ScopeCandidate[]; source_records: ScopeRecord[]; diagnostics: ScopeDiagnostic[];
}
function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("审核范围格式不完整。");
  return value as Record<string, unknown>;
}
function strings(value: unknown): value is string[] {
  return Array.isArray(value) && value.every(item => typeof item === "string");
}
export function decodeReviewScope(value: unknown, jobId: string, revisionId: string): ReviewScopeView {
  const view = record(value);
  if (view.job_id !== jobId || view.draft_revision_id !== revisionId ||
      typeof view.scope_content_hash !== "string" || !/^[0-9a-f]{64}$/.test(view.scope_content_hash) ||
      view.clinical_adoption_applied !== false || !Array.isArray(view.candidates) ||
      !Array.isArray(view.source_records) || !Array.isArray(view.diagnostics)) throw new Error("审核范围与当前方案版本不一致，请刷新。");
  for (const value of view.candidates) {
    const row = record(value);
    if (typeof row.candidate_key !== "string" || typeof row.label !== "string" ||
        !Object.hasOwn(scopeLabels, String(row.scope_kind)) || row.clinically_confirmed !== false ||
        !strings(row.source_span_ids) || !strings(row.official_codes) ||
        !(row.visit_instance === null || typeof row.visit_instance === "string")) throw new Error("审核范围条目不完整。");
  }
  for (const value of view.source_records) {
    const row = record(value);
    if (typeof row.source_span_id !== "string" || !(row.raw_text === null || typeof row.raw_text === "string") ||
        !(row.render_page === null || (Number.isInteger(row.render_page) && Number(row.render_page) > 0)) ||
        !["ok", "unknown_span", "cross_snapshot", "source_mismatch", "excerpt_mismatch"].includes(String(row.identity_status))) throw new Error("范围原文定位不完整。");
  }
  for (const value of view.diagnostics) {
    const row = record(value);
    if (typeof row.kind !== "string" || !strings(row.identifiers) || !strings(row.related_official_codes)) throw new Error("范围核对提示不完整。");
  }
  if (new Set(view.candidates.map(v => record(v).candidate_key)).size !== view.candidates.length ||
      new Set(view.source_records.map(v => record(v).source_span_id)).size !== view.source_records.length) throw new Error("范围来源身份重复，请刷新。");
  return view as unknown as ReviewScopeView;
}
export async function requestReviewScope(jobId: string, revisionId: string, signal: AbortSignal): Promise<ReviewScopeView> {
  const response = await fetch(protocolDeconstructionsUrl(`/${encodeURIComponent(jobId)}/draft/review-scope`), { signal });
  const value: unknown = await response.json();
  if (!response.ok) throw decodeProtocolWorkbenchError(value);
  return decodeReviewScope(value, jobId, revisionId);
}
