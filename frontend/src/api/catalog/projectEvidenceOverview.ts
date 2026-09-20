import { getProtocolApiBase } from "../protocolApiConfig";
import { CatalogApiError } from "./catalogTypes";

export interface ProjectEvidenceNode {
  episodeId: string;
  label: string;
  snapshotId: string | null;
  processingId: string | null;
}
export interface ProjectEvidenceSubject {
  subjectId: string;
  subjectCode: string;
  centerCode: string | null;
  centerName: string | null;
  nodes: ProjectEvidenceNode[];
}

function invalid(): never {
  throw new CatalogApiError("未能完整读取项目资料情况。", "请刷新重试。");
}
function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return invalid();
  return value as Record<string, unknown>;
}
function text(value: unknown): string {
  if (typeof value !== "string" || !value.trim()) return invalid();
  return value;
}
function optional(value: unknown): string | null {
  return value === null ? null : text(value);
}

export async function loadProjectEvidenceOverview(projectId: string, signal?: AbortSignal): Promise<ProjectEvidenceSubject[]> {
  const response = await fetch(`${getProtocolApiBase()}/api/v2/projects/${encodeURIComponent(projectId)}/evidence-overview`, { signal });
  if (!response.ok) return invalid();
  const payload = object(await response.json());
  if (payload.project_id !== projectId || !Array.isArray(payload.items)) return invalid();
  const subjects = new Set<string>();
  const episodes = new Set<string>();
  return payload.items.map((value) => {
    const item = object(value);
    const subjectId = text(item.subject_id);
    if (subjects.has(subjectId) || !Array.isArray(item.nodes)) return invalid();
    subjects.add(subjectId);
    return {
      subjectId, subjectCode: text(item.subject_code),
      centerCode: optional(item.center_code), centerName: optional(item.center_name),
      nodes: item.nodes.map((value) => {
        const node = object(value);
        const episodeId = text(node.review_episode_id);
        if (episodes.has(episodeId)) return invalid();
        episodes.add(episodeId);
        const snapshotId = optional(node.active_evidence_snapshot_id);
        const processingId = optional(node.active_evidence_processing_revision_id);
        if (processingId !== null && snapshotId === null) return invalid();
        return { episodeId, label: text(node.display_name), snapshotId, processingId };
      }),
    };
  });
}
