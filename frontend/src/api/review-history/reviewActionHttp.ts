import { decodeEligibilityReviewError } from "../eligibility-review";
import { getProtocolApiBase } from "../protocolApiConfig";

export interface ActionResponseInput {
  expected_revision: number;
  operation: "close_manual" | "reopen";
  reason: string;
  locator_ids: string[];
  response_snapshot_id: string | null;
  response_processing_revision_id: string | null;
  expected_episode_revision: number | null;
  idempotency_key: string;
}

export function createReviewActionHttp(fetchImpl: typeof fetch = fetch.bind(globalThis)) {
  return {
    async recordResponse(subjectId: string, episodeId: string, actionId: string, input: ActionResponseInput, signal?: AbortSignal) {
      const path = `/api/v2/subjects/${encodeURIComponent(subjectId)}/review-episodes/${encodeURIComponent(episodeId)}/actions/${encodeURIComponent(actionId)}/responses`;
      const response = await fetchImpl(`${getProtocolApiBase()}${path}`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(input), signal,
      });
      const text = await response.text();
      let payload: unknown;
      try { payload = JSON.parse(text) as unknown; } catch { payload = null; }
      if (!response.ok) throw decodeEligibilityReviewError(payload, response.status);
      if (payload === null || typeof payload !== "object" || Array.isArray(payload)) {
        throw new Error("办理结果暂不能确认，请保留当前说明后重试。");
      }
      const result = payload as Record<string, unknown>;
      if (Object.keys(result).sort().join(",") !== "action_id,record_revision,transition_id"
          || result.action_id !== actionId || result.record_revision !== input.expected_revision + 1
          || typeof result.transition_id !== "string" || !result.transition_id.trim()) {
        throw new Error("办理结果与本次提交不一致，请刷新办理记录核对。");
      }
      return { actionId, transitionId: result.transition_id, recordRevision: result.record_revision as number };
    },
  };
}
