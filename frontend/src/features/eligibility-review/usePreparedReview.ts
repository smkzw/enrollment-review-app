import { useEffect, useRef, useState } from "react";
import type { CatalogEpisodeView } from "../../api/catalog/catalogTypes";
import { EligibilityReviewApiError } from "../../api/eligibility-review";
import { createPreparedReviewHttp, type PreparedReviewWorkflow } from "../../api/eligibility-review/preparedReviewHttp";

const repository = createPreparedReviewHttp();
const terminal = new Set(["completed", "cancelled", "failed_final"]);

interface Options {
  episode: CatalogEpisodeView;
  workflowId: string | null;
  requestKey: string | null;
  onRequestKey: (key: string) => void;
  onStarted: (workflowId: string) => void;
  onPublished: (runId: string) => void;
}

function message(error: unknown): string {
  return error instanceof EligibilityReviewApiError ? error.message
    : "暂时无法确认审核进度，请刷新后重试。已保存的核对记录仍会保留。";
}

export function usePreparedReview({ episode, workflowId, requestKey, onRequestKey, onStarted, onPublished }: Options) {
  const [data, setData] = useState<PreparedReviewWorkflow | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [refreshCount, setRefreshCount] = useState(0);
  const operation = useRef<AbortController | null>(null);
  const key = useRef(requestKey);
  useEffect(() => () => operation.current?.abort(), []);

  useEffect(() => {
    if (workflowId === null) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    let failures = 0;
    async function read() {
      try {
        const result = await repository.workflow(episode.subjectId, episode.reviewEpisodeId, workflowId!, controller.signal);
        if (controller.signal.aborted) return;
        setData(result);
        failures = 0;
        setErrorMessage(null);
        if (!terminal.has(result.state)) timer = setTimeout(() => void read(), 3000);
      } catch (error) {
        if (!controller.signal.aborted) {
          setErrorMessage(message(error));
          failures += 1;
          if (failures < 4) timer = setTimeout(() => void read(), 3000 * failures);
        }
      }
    }
    void read();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [episode.subjectId, episode.reviewEpisodeId, workflowId, refreshCount]);

  async function mutate(action: (signal: AbortSignal) => Promise<void>) {
    if (operation.current !== null) return;
    const controller = new AbortController();
    operation.current = controller;
    setBusy(true);
    setErrorMessage(null);
    try { await action(controller.signal); }
    catch (error) { if (!controller.signal.aborted) setErrorMessage(message(error)); }
    finally {
      if (operation.current === controller) operation.current = null;
      if (!controller.signal.aborted) setBusy(false);
    }
  }

  const canStart = episode.activeEvidenceSnapshotId !== null && episode.activeEvidenceProcessingRevisionId !== null;
  return {
    data: data?.jobId === workflowId ? data : null, errorMessage, busy, canStart,
    refresh: () => setRefreshCount((value) => value + 1),
    publish: () => mutate(async (signal) => {
      if (workflowId === null || data?.state !== "completed") return;
      const runId = await repository.publishWorkflow(episode.subjectId, episode.reviewEpisodeId, workflowId, signal);
      if (!signal.aborted) { onPublished(runId); setRefreshCount((value) => value + 1); }
    }),
    start: () => mutate(async (signal) => {
      if (!canStart) return;
      key.current ??= crypto.randomUUID();
      onRequestKey(key.current);
      const prepared = await repository.prepare(episode.subjectId, episode.reviewEpisodeId, {
        project_id: episode.projectId, subject_id: episode.subjectId, review_episode_id: episode.reviewEpisodeId,
        episode_revision: episode.revision, protocol_version_id: episode.protocolVersionId,
        rule_set_id: episode.ruleSetId, rule_set_revision: episode.ruleSetRevision,
        evidence_snapshot_v2_id: episode.activeEvidenceSnapshotId!,
        complete_processing_revision_id: episode.activeEvidenceProcessingRevisionId!,
      }, key.current, signal);
      if (signal.aborted) return;
      const started = await repository.startWorkflow(episode.subjectId, episode.reviewEpisodeId, prepared.contextId, signal);
      if (!signal.aborted) onStarted(started.jobId);
    }),
    change: (action: "cancel" | "retry") => mutate(async (signal) => {
      if (workflowId === null) return;
      await repository.changeWorkflow(episode.subjectId, episode.reviewEpisodeId, workflowId, action, signal);
      if (!signal.aborted) setRefreshCount((value) => value + 1);
    }),
  };
}
