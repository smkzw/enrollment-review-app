import { protocolDeconstructionsUrl } from "./protocolApiConfig";
import { decodeProtocolWorkbenchError } from "./protocolWorkbenchNormalize";

export interface VariableDef {
  variable_id: string; label_zh: string;
  value_type: "number" | "category" | "boolean" | "date" | "exposure" | "procedure";
  canonical_unit: string | null; unit_conversions: Record<string, number>;
  plausible_range: [number, number] | null; aliases_zh: string[];
  domain: "demographic" | "lab" | "vital" | "score" | "history" | "medication" | "procedure";
}
export interface VariableBinding {
  component_id: string; predicate_id: string; requirement_id: string; variable_id: string;
}
export interface BindingView {
  job_id: string; draft_revision_id: string; variables: VariableDef[];
  source_context?: Record<string, { parent_source_text: string; component_source_text: string }>;
  predicates: { component_id: string; predicate_id: string; official_code: string; label: string;
    variable_id: string | null; requirements: { requirement_id: string; description: string }[] }[];
}
export async function variableRequest(jobId: string, suffix = "", body?: unknown, signal?: AbortSignal, method?: string): Promise<unknown> {
  const response = await fetch(protocolDeconstructionsUrl(`/${encodeURIComponent(jobId)}/draft/variables${suffix}`), {
    method: method ?? (body === undefined ? "GET" : suffix ? "POST" : "PUT"), signal,
    ...(body === undefined ? {} : { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  });
  const value: unknown = await response.json();
  if (!response.ok) throw decodeProtocolWorkbenchError(value);
  return value;
}
export function decodeBindingView(value: unknown, jobId: string, revisionId: string): BindingView {
  if (!value || typeof value !== "object") throw new Error("数据项目清单无法读取。");
  const view = value as BindingView;
  if (view.job_id !== jobId || view.draft_revision_id !== revisionId || !Array.isArray(view.variables) || !Array.isArray(view.predicates) ||
      view.variables.some(v => typeof v.variable_id !== "string" || typeof v.label_zh !== "string") ||
      view.predicates.some(p => typeof p.component_id !== "string" || typeof p.predicate_id !== "string" || typeof p.label !== "string" || !Array.isArray(p.requirements))) throw new Error("数据项目与草稿版本不一致，请刷新。");
  if (view.source_context !== undefined && (!view.source_context || typeof view.source_context !== "object" || Array.isArray(view.source_context) ||
      Object.entries(view.source_context).some(([id, context]) => !view.predicates.some(p => p.component_id === id) ||
        !context || typeof context.parent_source_text !== "string" || typeof context.component_source_text !== "string"))) {
    throw new Error("判断背景与当前条目不一致，请刷新。");
  }
  return view;
}
