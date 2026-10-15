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
  diagnostic_key?: string; resolved_by_manual_selection?: boolean;
}
export interface ScopeAddition {
  scope_kind: "referenced_source" | "medication_section"; source_span_ids: string[];
  official_codes: string[]; reason: string;
  resolves_references?: string[];
}
export interface ScopeProposal {
  scope_content_hash: string; included_candidate_keys: string[];
  exclusions: { candidate_key: string; reason: string }[]; additions: ScopeAddition[];
}
export interface ScopeSelection extends ScopeProposal { snapshot_id: string; saved_by: string; saved_at: string }
export interface ScopeSourceOption { label: string; text: string; page: number | null; source_span_ids: string[]; missing_positions: number }
export interface ScopeSourceOptions { items: ScopeSourceOption[]; total: number; next_offset: number | null }
export interface ReviewScopeView {
  job_id: string; draft_revision_id: string; scope_content_hash: string;
  clinical_adoption_applied: false;
  candidates: ScopeCandidate[]; source_records: ScopeRecord[]; diagnostics: ScopeDiagnostic[];
  additional_source_records: ScopeRecord[];
  editable: boolean; selection: ScopeSelection | null;
  drug_classes?: Record<string, string[]>;
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
  const additional = view.additional_source_records ?? [];
  if (view.drug_classes != null && Object.values(record(view.drug_classes)).some(value => !strings(value))) throw new Error("用药类别清单不完整。");
  if (!Array.isArray(additional)) throw new Error("手工选择的原文不完整。");
  for (const value of [...view.source_records, ...additional]) {
    const row = record(value);
    if (typeof row.source_span_id !== "string" || !(row.raw_text === null || typeof row.raw_text === "string") ||
        !(row.render_page === null || (Number.isInteger(row.render_page) && Number(row.render_page) > 0)) ||
        !["ok", "unknown_span", "cross_snapshot", "source_mismatch", "excerpt_mismatch"].includes(String(row.identity_status))) throw new Error("范围原文定位不完整。");
  }
  for (const value of view.diagnostics) {
    const row = record(value);
    if (typeof row.kind !== "string" || !strings(row.identifiers) || !strings(row.related_official_codes)) throw new Error("范围核对提示不完整。");
    if ((row.diagnostic_key !== undefined && typeof row.diagnostic_key !== "string") ||
        (row.resolved_by_manual_selection !== undefined && typeof row.resolved_by_manual_selection !== "boolean")) throw new Error("引用指定状态不完整。");
  }
  if (new Set(view.candidates.map(v => record(v).candidate_key)).size !== view.candidates.length ||
      new Set(view.source_records.map(v => record(v).source_span_id)).size !== view.source_records.length) throw new Error("范围来源身份重复，请刷新。");
  if (view.editable !== undefined && typeof view.editable !== "boolean") throw new Error("范围编辑状态不完整。");
  if (view.selection != null) {
    const selection = record(view.selection);
    if (typeof selection.scope_content_hash !== "string" || !strings(selection.included_candidate_keys) ||
        typeof selection.snapshot_id !== "string" || typeof selection.saved_by !== "string" || typeof selection.saved_at !== "string" ||
        !Array.isArray(selection.exclusions) || !Array.isArray(selection.additions)) throw new Error("保存的范围选择不完整。");
    for (const value of selection.exclusions) {
      const row = record(value);
      if (typeof row.candidate_key !== "string" || typeof row.reason !== "string") throw new Error("移除范围的理由不完整。");
    }
    for (const value of selection.additions) {
      const row = record(value);
      if (!["referenced_source", "medication_section"].includes(String(row.scope_kind)) || !strings(row.source_span_ids) ||
          !strings(row.official_codes) || typeof row.reason !== "string" ||
          (row.resolves_references !== undefined && !strings(row.resolves_references))) throw new Error("新增原文范围不完整。");
    }
  }
  return { ...view, additional_source_records: additional, editable: view.editable ?? false,
    selection: view.selection ?? null } as unknown as ReviewScopeView;
}

export async function saveReviewScope(jobId: string, revisionId: string, proposal: ScopeProposal): Promise<ReviewScopeView> {
  const response = await fetch(protocolDeconstructionsUrl(`/${encodeURIComponent(jobId)}/draft/review-scope`), {
    method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ expected_revision_id: revisionId, proposal }),
  });
  const value: unknown = await response.json();
  if (!response.ok) throw decodeProtocolWorkbenchError(value);
  const row = record(value);
  if (typeof row.draft_revision_id !== "string") throw new Error("保存后的草稿版本缺失，请刷新核对。");
  return decodeReviewScope(value, jobId, row.draft_revision_id);
}

export async function findScopeSources(jobId: string, revisionId: string, query: string, offset: number,
                                        signal: AbortSignal): Promise<ScopeSourceOptions> {
  const params = new URLSearchParams({ q: query, offset: String(offset) });
  const response = await fetch(protocolDeconstructionsUrl(`/${encodeURIComponent(jobId)}/draft/review-scope/sources?${params}`), { signal });
  const value: unknown = await response.json();
  if (!response.ok) throw decodeProtocolWorkbenchError(value);
  const row = record(value);
  if (row.job_id !== jobId || row.draft_revision_id !== revisionId || !Array.isArray(row.items) ||
      !Number.isInteger(row.total) || Number(row.total) < row.items.length ||
      !(row.next_offset === null || Number.isInteger(row.next_offset))) throw new Error("原文查找结果与草稿不一致。");
  for (const value of row.items) {
    const option = record(value);
    if (typeof option.label !== "string" || typeof option.text !== "string" || !strings(option.source_span_ids) ||
        !Number.isInteger(option.missing_positions) || !(option.page === null || Number.isInteger(option.page))) throw new Error("原文选项不完整。");
  }
  return row as unknown as ScopeSourceOptions;
}
export async function requestReviewScope(jobId: string, revisionId: string, signal: AbortSignal): Promise<ReviewScopeView> {
  const response = await fetch(protocolDeconstructionsUrl(`/${encodeURIComponent(jobId)}/draft/review-scope`), { signal });
  const value: unknown = await response.json();
  if (!response.ok) throw decodeProtocolWorkbenchError(value);
  return decodeReviewScope(value, jobId, revisionId);
}
