import { getProtocolApiBase } from "../protocolApiConfig";
import { decodeUploadPreviewError, EvidenceDecodeError } from "./evidenceViewModels";

export interface LocalVisualRegion {
  x0: number; y0: number; x1: number; y1: number;
  clockwise_degrees: 0 | 90 | 180 | 270;
  include_context?: boolean;
  read_format?: "transcript" | "structured_candidate" | "localized_candidate";
}
export interface LocalVisualTask {
  found: boolean; jobId: string | null; state: string | null;
  text: string | null; region: LocalVisualRegion | null;
  configurationCurrent: boolean; canRetry: boolean;
  structuredRead?: { items: LocalVisualReadItem[]; unresolved: string[] };
  readingRegion?: LocalVisualRegion;
  failureMessage?: string;
}
export interface LocalVisualReadItem {
  label: string | null; raw_value: string | null; raw_unit: string | null;
  reference_text: string | null; time_label: string | null; annotation_target: string | null;
  excerpt: string; position: string;
  script: "printed" | "handwritten" | "mixed";
  legibility: "clear" | "partial" | "unclear";
  proposed_bbox?: { x0: number; y0: number; x1: number; y1: number } | null;
}
const states = new Set(["queued", "running", "recovering", "cancel_requested", "cancelled", "completed", "failed_final", "failed_retryable", "waiting_user", "needs_attention"]);

function object(value: unknown): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) throw new EvidenceDecodeError("局部核实信息格式无法确认。");
  return value as Record<string, unknown>;
}
function decodeRegion(value: unknown): LocalVisualRegion {
  const box = object(value);
  if (["x0", "y0", "x1", "y1"].some((key) => typeof box[key] !== "number" || !Number.isSafeInteger(box[key]) || (box[key] as number) < 0)
      || (box.x1 as number) <= (box.x0 as number) || (box.y1 as number) <= (box.y0 as number)
      || ![0, 90, 180, 270].includes(box.clockwise_degrees as number)) throw new EvidenceDecodeError("局部核实范围无法定位。");
  if ((box.include_context !== undefined && typeof box.include_context !== "boolean")
      || (box.read_format !== undefined && !["transcript", "structured_candidate", "localized_candidate"].includes(box.read_format as string))) throw new EvidenceDecodeError("本次读取范围无法确认。");
  return box as unknown as LocalVisualRegion;
}
function decodeStructuredRead(value: unknown, localized: boolean): LocalVisualTask["structuredRead"] {
  const read = object(value);
  if (Object.keys(read).some((key) => !["items", "unresolved"].includes(key))
      || !Array.isArray(read.items) || !Array.isArray(read.unresolved)
      || read.unresolved.some((item) => typeof item !== "string")
      || (!read.items.length && !read.unresolved.some((item) => item.trim()))) throw new EvidenceDecodeError("逐项读取内容不完整。");
  const items = read.items.map((value): LocalVisualReadItem => {
    const item = object(value);
    const nullable = ["label", "raw_value", "raw_unit", "reference_text", "time_label", "annotation_target"];
    const required = [...nullable, "excerpt", "position", "script", "legibility", ...(localized ? ["proposed_bbox"] : [])];
    if (Object.keys(item).some((key) => !required.includes(key)) || required.some((key) => !(key in item))
        || nullable.some((key) => item[key] !== null && typeof item[key] !== "string")
        || ["excerpt", "position"].some((key) => typeof item[key] !== "string" || !(item[key] as string).trim())
        || !["printed", "handwritten", "mixed"].includes(item.script as string)
        || !["clear", "partial", "unclear"].includes(item.legibility as string)) throw new EvidenceDecodeError("逐项读取的归属或字迹信息无法确认。");
    if (localized && item.proposed_bbox !== null) {
      const box = object(item.proposed_bbox);
      if (Object.keys(box).some((key) => !["x0", "y0", "x1", "y1"].includes(key))
          || ["x0", "y0", "x1", "y1"].some((key) => !Number.isInteger(box[key]) || (box[key] as number) < 0 || (box[key] as number) > 1000)
          || (box.x1 as number) <= (box.x0 as number) || (box.y1 as number) <= (box.y0 as number)) throw new EvidenceDecodeError("读取项目的位置尚不能确认。");
    }
    return item as unknown as LocalVisualReadItem;
  });
  return { items, unresolved: read.unresolved as string[] };
}

export function localVisualItemRegion(task: LocalVisualTask, item: LocalVisualReadItem): LocalVisualRegion | null {
  const parent = task.readingRegion;
  const focus = task.region;
  const box = item.proposed_bbox;
  if (!parent || !focus || !box) return null;
  const width = parent.x1 - parent.x0, height = parent.y1 - parent.y0;
  const region = { x0: parent.x0 + Math.floor(width * box.x0 / 1000),
    y0: parent.y0 + Math.floor(height * box.y0 / 1000),
    x1: parent.x0 + Math.ceil(width * box.x1 / 1000),
    y1: parent.y0 + Math.ceil(height * box.y1 / 1000), clockwise_degrees: parent.clockwise_degrees };
  // A partially overlapping proposal stays unresolved; never clip it into
  // the focus and present the resulting pixels as the model's original box.
  if (region.x0 < focus.x0 || region.y0 < focus.y0 || region.x1 > focus.x1 || region.y1 > focus.y1) return null;
  return region;
}
export function decodeLocalVisualTask(value: unknown): LocalVisualTask {
  const data = object(value);
  if (typeof data.found !== "boolean" || data.candidate_only !== true || data.coverage_scope !== "region_only") throw new EvidenceDecodeError("局部阅读不能作为整页核对或已采用的病史。");
  if (!data.found) return { found: false, jobId: null, state: null, text: null, region: null, configurationCurrent: true, canRetry: false };
  if (typeof data.job_id !== "string" || !data.job_id || typeof data.state !== "string" || !states.has(data.state)) throw new EvidenceDecodeError("局部核实任务状态无法确认。");
  const box = decodeRegion(data.region);
  if (data.failure_message !== undefined && (typeof data.failure_message !== "string"
      || !data.failure_message.trim() || !["failed_final", "failed_retryable"].includes(data.state))) throw new EvidenceDecodeError("读取失败的说明无法确认。");
  if (data.observation_text !== null && typeof data.observation_text !== "string") throw new EvidenceDecodeError("局部阅读结果无法确认。");
  if (data.state !== "completed" && data.observation_text !== null) throw new EvidenceDecodeError("未完成的阅读不应显示为核实结果。");
  if (data.state === "completed" && (typeof data.observation_text !== "string" || !data.observation_text.trim())) throw new EvidenceDecodeError("本次读取缺少完整内容，请重新读取或核对原件。");
  if (typeof data.configuration_current !== "boolean" || typeof data.can_retry !== "boolean"
      || (data.can_retry && (!data.configuration_current || !["failed_final", "failed_retryable"].includes(data.state)))) throw new EvidenceDecodeError("本次读取的恢复范围无法确认。");
  let structuredRead: LocalVisualTask["structuredRead"];
  let readingRegion: LocalVisualRegion | undefined;
  if (data.structured_read !== undefined) {
    if (data.state !== "completed" || !["structured_candidate", "localized_candidate"].includes(box.read_format ?? "")) throw new EvidenceDecodeError("本次逐项读取尚未完成。");
    readingRegion = decodeRegion(data.reading_region);
    if (readingRegion.clockwise_degrees !== box.clockwise_degrees || readingRegion.read_format !== box.read_format
        || readingRegion.x0 > box.x0 || readingRegion.y0 > box.y0 || readingRegion.x1 < box.x1 || readingRegion.y1 < box.y1) throw new EvidenceDecodeError("读取项目与圈选来源无法对应。");
    structuredRead = decodeStructuredRead(data.structured_read, box.read_format === "localized_candidate");
  }
  return { found: true, jobId: data.job_id, state: data.state, text: data.observation_text as string | null, region: box,
    configurationCurrent: data.configuration_current, canRetry: data.can_retry,
    ...(data.failure_message !== undefined ? { failureMessage: data.failure_message as string } : {}),
    ...(structuredRead ? { structuredRead, readingRegion } : {}) };
}

async function request(path: string, init: RequestInit): Promise<unknown> {
  const response = await fetch(`${getProtocolApiBase()}${path}`, init);
  const data: unknown = await response.json();
  if (!response.ok) throw decodeUploadPreviewError(data, response.status);
  return data;
}
function path(revisionId: string, pageId: string): string {
  return `/api/v2/evidence-processing-revisions/${encodeURIComponent(revisionId)}/pages/${encodeURIComponent(pageId)}/local-verification`;
}
export async function getLocalVisualTask(revisionId: string, pageId: string, signal?: AbortSignal, jobId?: string | null): Promise<LocalVisualTask> {
  return decodeLocalVisualTask(await request(path(revisionId, pageId) + (jobId ? `?job_id=${encodeURIComponent(jobId)}` : ""), { method: "GET", signal }));
}
export async function startLocalVisualTask(revisionId: string, pageId: string, region: LocalVisualRegion): Promise<string> {
  const data = object(await request(path(revisionId, pageId), {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(region),
  }));
  if (typeof data.job_id !== "string" || !data.job_id || typeof data.state !== "string" || !states.has(data.state)) throw new EvidenceDecodeError("局部核实任务未能确认创建。");
  return data.job_id;
}
export async function actOnLocalVisualTask(jobId: string, action: "retry" | "cancel"): Promise<void> {
  await request(`/api/v2/jobs/${encodeURIComponent(jobId)}/${action}`, { method: "POST" });
}

export interface LocalFieldComparisonTask {
  found: boolean; jobId: string | null; state: string | null; canRetry: boolean;
  failureMessage: string | null;
  outcome: { itemIndex: number; agreement: boolean; reasons: string[] } | null;
}
export function decodeLocalFieldComparison(value: unknown, itemIndex: number): LocalFieldComparisonTask {
  const data = object(value);
  if (typeof data.found !== "boolean" || data.candidate_only !== true || data.formal_adoption_authorized !== false)
    throw new EvidenceDecodeError("项目核对不能代替正式采用。");
  if (!data.found) return { found: false, jobId: null, state: null, canRetry: false, failureMessage: null, outcome: null };
  if (typeof data.job_id !== "string" || !data.job_id || typeof data.state !== "string" || !states.has(data.state)
      || typeof data.can_retry !== "boolean" || typeof data.configuration_current !== "boolean"
      || (data.can_retry && (!data.configuration_current || !["failed_final", "failed_retryable"].includes(data.state))))
    throw new EvidenceDecodeError("项目核对的状态或恢复范围无法确认。");
  if (data.failure_message !== undefined && (typeof data.failure_message !== "string"
      || !["failed_final", "failed_retryable"].includes(data.state))) throw new EvidenceDecodeError("核对失败的说明无法确认。");
  let outcome: LocalFieldComparisonTask["outcome"] = null;
  if (data.state === "completed") {
    const item = object(data.outcome);
    if (item.item_index !== itemIndex || item.candidate_only !== true || item.source_position_verified !== false
        || typeof item.single_field_transcription_agreement !== "boolean"
        || !Array.isArray(item.reasons) || item.reasons.some((reason) => typeof reason !== "string"))
      throw new EvidenceDecodeError("项目核对的实际依据无法确认。");
    outcome = { itemIndex, agreement: item.single_field_transcription_agreement, reasons: item.reasons as string[] };
  } else if (data.outcome !== null) throw new EvidenceDecodeError("未完成的核对不能显示为一致。");
  return { found: true, jobId: data.job_id, state: data.state, canRetry: data.can_retry,
    failureMessage: (data.failure_message as string | undefined) ?? null, outcome };
}
export async function getLocalFieldComparison(revisionId: string, pageId: string, visualJobId: string,
  itemIndex: number, signal?: AbortSignal, jobId?: string | null): Promise<LocalFieldComparisonTask> {
  const params = new URLSearchParams({ visual_job_id: visualJobId, item_index: String(itemIndex) });
  if (jobId) params.set("job_id", jobId);
  return decodeLocalFieldComparison(await request(path(revisionId, pageId) + `/comparison?${params}`,
    { method: "GET", signal }), itemIndex);
}
export async function startLocalFieldComparison(revisionId: string, pageId: string, visualJobId: string, itemIndex: number): Promise<string> {
  const data = object(await request(path(revisionId, pageId) + "/comparison", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ visual_job_id: visualJobId, item_index: itemIndex }),
  }));
  if (typeof data.job_id !== "string" || !data.job_id || typeof data.state !== "string" || !states.has(data.state))
    throw new EvidenceDecodeError("项目核对未能确认创建。");
  return data.job_id;
}
