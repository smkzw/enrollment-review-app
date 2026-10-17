import { protocolDeconstructionsUrl } from "./protocolApiConfig";
import { decodeProtocolWorkbenchError } from "./protocolWorkbenchNormalize";
import type { TimeConstraintWire } from "./wire";

export const medicationStages = { pre_screening: "预筛", screening: "筛选", run_in: "导入／洗脱", baseline: "基线" } as const;
export type MedicationStage = keyof typeof medicationStages;
export interface MedicationQuote { source_span_id: string; excerpt: string }
export interface MedicationRestriction {
  item_id?: string; drug_text: string; drug_class_id: string | null;
  class_scope?: "all_members" | "qualified" | null;
  window: (TimeConstraintWire & Record<string, unknown>) | null;
  window_interpretation?: "prohibited_interval" | "minimum_washout" | null;
  period: "study_period" | "treatment_period" | null; applicable_stages: MedicationStage[];
  exception_excerpt: string | null; unresolved_reason: string | null;
  exception_period?: "study_period" | "treatment_period" | null;
  source_quotes: MedicationQuote[]; applies_to_rule: string | null;
}
export interface MedicationDisposition {
  source_span_id: string; disposition: "heading" | "permission" | "other_phase" | "background" | "unresolved"; reason: string;
}
export interface ScopeSupplement {
  medications: MedicationRestriction[]; source_dispositions: MedicationDisposition[]; sources: MedicationQuote[];
  selection_sha256: string; input_sha256: string; structure_sha256: string;
  drug_classes?: Record<string, string[]>;
}
function row(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("用药要求的内容不完整。");
  return value as Record<string, unknown>;
}
function quotes(value: unknown): void {
  if (!Array.isArray(value) || value.some(item => typeof row(item).source_span_id !== "string" || typeof row(item).excerpt !== "string"))
    throw new Error("用药要求的原文不完整。");
}
export function decodeScopeSupplement(value: unknown): ScopeSupplement {
  const result = row(value);
  for (const key of ["selection_sha256", "input_sha256", "structure_sha256"])
    if (typeof result[key] !== "string" || !/^[0-9a-f]{64}$/.test(result[key] as string)) throw new Error("用药要求与方案来源不一致。");
  quotes(result.sources);
  if (result.drug_classes != null && Object.values(row(result.drug_classes)).some(value => !Array.isArray(value) || value.some(member => typeof member !== "string")))
    throw new Error("本版用药类别内容不完整。");
  if (!Array.isArray(result.medications) || !Array.isArray(result.source_dispositions)) throw new Error("用药要求清单不完整。");
  for (const value of result.medications) {
    const item = row(value);
    if (typeof item.drug_text !== "string" || !item.drug_text || !Array.isArray(item.applicable_stages) ||
        item.applicable_stages.some(value => !Object.hasOwn(medicationStages, String(value))) ||
        !(item.drug_class_id === null || typeof item.drug_class_id === "string") ||
        ![null, "study_period", "treatment_period"].includes(item.period as null) ||
        !["exception_excerpt", "unresolved_reason", "applies_to_rule"].every(key => item[key] === null || typeof item[key] === "string"))
      throw new Error("用药限制的阶段或范围不完整。");
    quotes(item.source_quotes);
    if (item.exception_period != null && (!["study_period", "treatment_period"].includes(String(item.exception_period)) || !item.exception_excerpt))
      throw new Error("用药例外的适用期间不完整。");
    if (item.class_scope != null && (!["all_members", "qualified"].includes(String(item.class_scope)) || item.drug_class_id == null))
      throw new Error("药物类别的适用范围尚不能读取。");
    if (item.window_interpretation != null && !["prohibited_interval", "minimum_washout"].includes(String(item.window_interpretation)))
      throw new Error("用药时间要求的含义尚不能读取。");
    if (item.window_interpretation != null && item.window === null) throw new Error("用药时间要求缺少对应日期窗口。");
    if (item.window !== null) {
      const window = row(item.window);
      if (typeof window.anchor_type !== "string" || !["before", "after", "on"].includes(String(window.direction))) throw new Error("用药时间窗不完整。");
      for (const key of ["lower_bound", "upper_bound"]) if (window[key] != null) {
        const bound = row(window[key]);
        if (!Number.isInteger(bound.value) || Number(bound.value) <= 0 || !["day", "week", "month", "year"].includes(String(bound.unit))) throw new Error("洗脱时间的数量或单位不完整。");
      }
    }
  }
  for (const value of result.source_dispositions) {
    const item = row(value);
    if (typeof item.source_span_id !== "string" || typeof item.reason !== "string" ||
        !["heading", "permission", "other_phase", "background", "unresolved"].includes(String(item.disposition))) throw new Error("用药原文处置不完整。");
  }
  return result as unknown as ScopeSupplement;
}
export async function medicationRequest(jobId: string, revisionId: string, proposal?: ScopeSupplement, proposalRef?: string | null) {
  const response = await fetch(protocolDeconstructionsUrl(`/${encodeURIComponent(jobId)}/draft/medications${proposal ? "" : "/suggest"}`), {
    method: proposal ? "PUT" : "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ expected_revision_id: revisionId, ...(proposal ? {
      proposal: { medications: proposal.medications.map(({ item_id: _id, ...item }) => item), source_dispositions: proposal.source_dispositions },
      ...(proposal.drug_classes == null ? {} : { drug_classes: Object.fromEntries(Object.entries(proposal.drug_classes)
        .map(([id, members]) => [id, members.map(name => name.trim()).filter(Boolean)])) }),
      proposal_ref: proposalRef ?? null } : {}) }),
  });
  const data: unknown = await response.json();
  if (!response.ok) throw decodeProtocolWorkbenchError(data);
  const result = row(data);
  if (!proposal && (result.job_id !== jobId || result.draft_revision_id !== revisionId)) throw new Error("用药建议属于另一版草稿。");
  return result;
}
