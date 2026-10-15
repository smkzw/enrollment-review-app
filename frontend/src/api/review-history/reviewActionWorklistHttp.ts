import { getProtocolApiBase } from "../protocolApiConfig";
import { decodeEligibilityReviewError } from "../eligibility-review";
import { decodeAction, ReviewHistoryDecodeError } from "./reviewHistoryHttp";
import type { ReviewHistoryActionView, ReviewHistoryStage } from "./reviewHistoryTypes";

export type WorklistMode = "open" | "all";
export interface ReviewActionWorklistItem {
  action: ReviewHistoryActionView;
  projectName: string;
  subjectId: string;
  subjectCode: string;
  reviewEpisodeId: string;
  reviewRunId: string;
  workflowStageLabel: string;
  startedAt: string;
  completedAt: string | null;
}
export interface ReviewActionWorklistPage {
  projectId: string;
  mode: WorklistMode;
  items: ReviewActionWorklistItem[];
  nextAfterActionId: string | null;
}

function invalid(): never {
  throw new ReviewHistoryDecodeError("办理清单与保存记录不一致，请重新读取。");
}
function object(value: unknown, keys: string[]): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return invalid();
  const row = value as Record<string, unknown>;
  if (Object.keys(row).length !== keys.length || keys.some((key) => !(key in row))) return invalid();
  return row;
}
function text(value: unknown): string {
  return typeof value === "string" && value.trim() ? value : invalid();
}
function date(value: unknown): string {
  const result = text(value);
  return Number.isFinite(Date.parse(result)) ? result : invalid();
}

export async function listReviewActionWorklist(projectId: string, mode: WorklistMode,
  afterActionId: string | null, signal?: AbortSignal,
  dueStage: ReviewHistoryStage | null = null, limit = 50): Promise<ReviewActionWorklistPage> {
  if (!Number.isInteger(limit) || limit < 1 || limit > 100) return invalid();
  const params = new URLSearchParams({ mode, limit: String(limit) });
  if (afterActionId !== null) params.set("after_action_id", afterActionId);
  if (dueStage !== null) params.set("due_stage", dueStage);
  const response = await fetch(`${getProtocolApiBase()}/api/v2/projects/${encodeURIComponent(projectId)}/review-actions?${params}`, { signal });
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) throw decodeEligibilityReviewError(payload, response.status);
  const row = object(payload, ["project_id", "mode", "items", "next_after_action_id"]);
  if (row.project_id !== projectId || row.mode !== mode || !Array.isArray(row.items)) return invalid();
  const items = row.items.map((value, index): ReviewActionWorklistItem => {
    const item = object(value, ["action", "project_name", "subject_id", "subject_code", "review_episode_id", "review_run_id", "workflow_stage_label", "started_at", "completed_at"]);
    const action = decodeAction(item.action, `worklist.items[${index}].action`);
    if (mode === "open" && action.state !== "open" && action.state !== "reopened") return invalid();
    if (dueStage !== null && action.dueStage !== dueStage) return invalid();
    const startedAt = date(item.started_at);
    const completedAt = item.completed_at === null ? null : date(item.completed_at);
    if (completedAt !== null && Date.parse(completedAt) < Date.parse(startedAt)) return invalid();
    const subjectId = text(item.subject_id);
    const reviewEpisodeId = text(item.review_episode_id);
    if (action.transitions.some((entry) => entry.responseEvidence !== null && (
      entry.responseEvidence.projectId !== projectId || entry.responseEvidence.subjectId !== subjectId
      || entry.responseEvidence.reviewEpisodeId !== reviewEpisodeId))) return invalid();
    return { action, projectName: text(item.project_name), subjectId, subjectCode: text(item.subject_code),
      reviewEpisodeId, reviewRunId: text(item.review_run_id), workflowStageLabel: text(item.workflow_stage_label), startedAt, completedAt };
  });
  const ids = items.map((item) => item.action.actionId);
  if (items.length > limit || new Set(ids).size !== ids.length
    || ids.some((id, index) => id <= (index ? ids[index - 1] : afterActionId ?? ""))) return invalid();
  const nextAfterActionId = row.next_after_action_id === null ? null : text(row.next_after_action_id);
  if (nextAfterActionId !== null && (items.length !== limit || nextAfterActionId !== ids.at(-1))) return invalid();
  return { projectId, mode, items, nextAfterActionId };
}

export type RecentProjectReview = Pick<ReviewActionWorklistItem,
  "subjectId" | "subjectCode" | "reviewEpisodeId" | "reviewRunId" | "workflowStageLabel" | "startedAt" | "completedAt">;

export async function listRecentProjectReviews(projectId: string, signal?: AbortSignal): Promise<{
  items: RecentProjectReview[]; hasMore: boolean;
}> {
  const response = await fetch(`${getProtocolApiBase()}/api/v2/projects/${encodeURIComponent(projectId)}/recent-reviews?limit=6`, { signal });
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) throw decodeEligibilityReviewError(payload, response.status);
  const row = object(payload, ["project_id", "items", "has_more"]);
  if (row.project_id !== projectId || !Array.isArray(row.items) || typeof row.has_more !== "boolean") return invalid();
  const items = row.items.map((value): RecentProjectReview => {
    const item = object(value, ["subject_id", "subject_code", "review_episode_id", "review_run_id", "workflow_stage_label", "started_at", "completed_at"]);
    const startedAt = date(item.started_at);
    const completedAt = item.completed_at === null ? null : date(item.completed_at);
    if (completedAt !== null && Date.parse(completedAt) < Date.parse(startedAt)) return invalid();
    return { subjectId: text(item.subject_id), subjectCode: text(item.subject_code),
      reviewEpisodeId: text(item.review_episode_id), reviewRunId: text(item.review_run_id),
      workflowStageLabel: text(item.workflow_stage_label), startedAt, completedAt };
  });
  if (items.length > 6 || (row.has_more && items.length !== 6)
      || new Set(items.map((item) => item.reviewRunId)).size !== items.length
      || items.some((item, index) => index > 0 && Date.parse(item.startedAt) > Date.parse(items[index - 1].startedAt))) return invalid();
  return { items, hasMore: row.has_more };
}
