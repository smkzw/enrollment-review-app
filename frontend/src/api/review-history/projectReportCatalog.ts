import { getProtocolApiBase } from "../protocolApiConfig";
import { decodeEligibilityReviewError } from "../eligibility-review";

export interface ReportCursor { completedAt: string; runId: string }
export interface ProjectReportEntry extends ReportCursor {
  subjectId: string; subjectCode: string; episodeId: string; nodeLabel: string;
  centerCode: string | null; centerName: string | null; protocolVersion: string;
}
export interface ProjectReportPage { items: ProjectReportEntry[]; nextCursor: ReportCursor | null }
const invalid = (): never => { throw new Error("报告目录信息不完整，请刷新后重试。"); };
function object(value: unknown, keys: string[]): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return invalid();
  const item = value as Record<string, unknown>;
  if (Object.keys(item).length !== keys.length || keys.some((key) => !(key in item))) return invalid();
  return item;
}
const text = (value: unknown): string => typeof value === "string" && value.trim() ? value : invalid();
const optional = (value: unknown): string | null => value === null ? null : text(value);
function cursor(value: Record<string, unknown>): ReportCursor {
  const completedAt = text(value.completed_at);
  if (!/(?:Z|\+00:00)$/.test(completedAt) || !Number.isFinite(Date.parse(completedAt))) return invalid();
  return { completedAt, runId: text(value.review_run_id) };
}

export async function loadProjectReports(projectId: string, center: string, before: ReportCursor | null, signal?: AbortSignal): Promise<ProjectReportPage> {
  const params = new URLSearchParams();
  if (center) params.set("center_code", center);
  if (before) { params.set("before_completed_at", before.completedAt); params.set("before_run_id", before.runId); }
  const response = await fetch(`${getProtocolApiBase()}/api/v2/projects/${encodeURIComponent(projectId)}/saved-reports?${params}`, { signal });
  const payload: unknown = await response.json();
  if (!response.ok) throw decodeEligibilityReviewError(payload, response.status);
  const page = object(payload, ["project_id", "items", "next_cursor"]);
  if (page.project_id !== projectId || !Array.isArray(page.items)) return invalid();
  const ids = new Set<string>();
  const items = page.items.map((value) => {
    const item = object(value, ["subject_id", "subject_code", "review_episode_id", "review_run_id", "workflow_stage_label", "center_code", "center_name", "completed_at", "official_protocol_version"]);
    const position = cursor(item);
    if (ids.has(position.runId)) return invalid();
    ids.add(position.runId);
    const centerCode = optional(item.center_code);
    if (center && centerCode !== center) return invalid();
    return { ...position, subjectId: text(item.subject_id), subjectCode: text(item.subject_code),
      episodeId: text(item.review_episode_id), nodeLabel: text(item.workflow_stage_label),
      centerCode, centerName: optional(item.center_name), protocolVersion: text(item.official_protocol_version) };
  });
  const nextCursor = page.next_cursor === null ? null : cursor(object(page.next_cursor, ["completed_at", "review_run_id"]));
  const last = items.at(-1);
  if (nextCursor && (!last || nextCursor.runId !== last.runId || nextCursor.completedAt !== last.completedAt)) return invalid();
  if (before && items.some((item) => item.runId === before.runId)) return invalid();
  return { items, nextCursor };
}
