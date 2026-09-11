import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ProfileEvidenceNavigationView } from "../../api/patient-profile";
import {
  createJudgmentSearchHttp,
  JudgmentSearchApiError,
  JudgmentSearchDecodeError,
  type JudgmentSearchHttp,
} from "../../api/judgment-search/judgmentSearchHttp";
import type {
  JudgmentSearchCandidateView,
  JudgmentSearchResultsView,
  JudgmentSearchStatusView,
} from "../../api/judgment-search/judgmentSearchTypes";

const POLL_MS = 2_500;

export interface JudgmentSearchCandidateSelection {
  page_artifact_id: string;
  page_number: number;
}

export interface JudgmentSearchCardProps {
  subjectId: string;
  reviewEpisodeId: string;
  evidenceNavigation: ProfileEvidenceNavigationView;
  onSelectCandidate: (selection: JudgmentSearchCandidateSelection) => void;
  /** 测试与页面装配可注入同一类型的请求客户端。 */
  http?: JudgmentSearchHttp;
}

type CardState =
  | { kind: "idle" }
  | { kind: "loading"; jobId: string }
  | { kind: "running"; jobId: string; status: JudgmentSearchStatusView }
  | {
      kind: "completed";
      jobId: string;
      status: JudgmentSearchStatusView;
      results: JudgmentSearchResultsView;
    }
  | {
      kind: "cancelled";
      jobId: string;
      status: JudgmentSearchStatusView;
      results: JudgmentSearchResultsView | null;
    }
  | { kind: "error"; jobId: string | null; message: string };

function storageKey(subjectId: string, reviewEpisodeId: string): string {
  return `judgment-search-job:${subjectId}:${reviewEpisodeId}`;
}

function readStoredJob(key: string): string | null {
  try {
    const value = window.localStorage.getItem(key);
    return value !== null && value.trim().length > 0 ? value : null;
  } catch {
    return null;
  }
}

function writeStoredJob(key: string, jobId: string): void {
  try {
    window.localStorage.setItem(key, jobId);
  } catch {
    // 本机存储不可用时仍允许当前页面继续使用任务。
  }
}

function clearStoredJob(key: string): void {
  try {
    window.localStorage.removeItem(key);
  } catch {
    // 本机存储不可用不应阻断任务结果展示。
  }
}

function errorMessage(error: unknown): string {
  const message =
    error instanceof JudgmentSearchApiError ||
    error instanceof JudgmentSearchDecodeError ||
    error instanceof Error
      ? error.message
      : "";
  if (message.trim().length > 0 && /[\u4e00-\u9fff]/u.test(message)) {
    return message;
  }
  return "书面判断检索暂时无法读取，请稍后重试。";
}

function isRetryableFailure(state: JudgmentSearchStatusView["state"]): boolean {
  return state === "failed_retryable" || state === "failed_final";
}

function candidateCount(results: JudgmentSearchResultsView): number {
  return results.results.reduce((count, item) => count + item.foundCandidates.length, 0);
}

export function JudgmentSearchCard({
  subjectId,
  reviewEpisodeId,
  evidenceNavigation,
  onSelectCandidate,
  http,
}: JudgmentSearchCardProps) {
  const api = useMemo(() => http ?? createJudgmentSearchHttp(), [http]);
  const key = useMemo(() => storageKey(subjectId, reviewEpisodeId), [subjectId, reviewEpisodeId]);
  const [state, setState] = useState<CardState>({ kind: "idle" });
  const [expandedRequirements, setExpandedRequirements] = useState<Record<string, boolean>>({});
  const generationRef = useRef(0);
  const requestRef = useRef(0);
  const controllerRef = useRef<AbortController | null>(null);

  const refreshJob = useCallback(
    async (jobId: string, showLoading: boolean, generation: number) => {
      const requestId = ++requestRef.current;
      controllerRef.current?.abort();
      const controller = new AbortController();
      controllerRef.current = controller;
      if (showLoading) setState({ kind: "loading", jobId });
      try {
        const status = await api.status(subjectId, reviewEpisodeId, jobId, {
          signal: controller.signal,
        });
        if (generationRef.current !== generation || requestRef.current !== requestId) return;
        if (isRetryableFailure(status.state)) {
          setState({ kind: "error", jobId, message: status.stateLabel });
          return;
        }
        if (status.state === "completed" || status.state === "cancelled") {
          const results = await api.results(subjectId, reviewEpisodeId, jobId, {
            signal: controller.signal,
          });
          if (generationRef.current !== generation || requestRef.current !== requestId) return;
          if (status.state === "completed") {
            clearStoredJob(key);
            setState({ kind: "completed", jobId, status, results });
          } else {
            setState({ kind: "cancelled", jobId, status, results });
          }
          return;
        }
        setState({ kind: "running", jobId, status });
      } catch (error) {
        if (controller.signal.aborted || generationRef.current !== generation) return;
        setState({ kind: "error", jobId, message: errorMessage(error) });
      }
    },
    [api, key, reviewEpisodeId, subjectId],
  );

  useEffect(() => {
    const generation = ++generationRef.current;
    controllerRef.current?.abort();
    requestRef.current += 1;
    setExpandedRequirements({});
    const storedJobId = readStoredJob(key);
    if (storedJobId === null) {
      setState({ kind: "idle" });
    } else {
      void refreshJob(storedJobId, true, generation);
    }
    return () => {
      generationRef.current += 1;
      controllerRef.current?.abort();
      controllerRef.current = null;
    };
  }, [key, refreshJob]);

  useEffect(() => {
    if (state.kind !== "running") return;
    const timer = window.setTimeout(() => {
      void refreshJob(state.jobId, false, generationRef.current);
    }, POLL_MS);
    return () => window.clearTimeout(timer);
  }, [refreshJob, state]);

  const start = useCallback(async () => {
    const generation = ++generationRef.current;
    controllerRef.current?.abort();
    requestRef.current += 1;
    const controller = new AbortController();
    controllerRef.current = controller;
    setState({ kind: "loading", jobId: "" });
    try {
      const started = await api.start(subjectId, reviewEpisodeId, {}, { signal: controller.signal });
      if (generationRef.current !== generation) return;
      writeStoredJob(key, started.jobId);
      await refreshJob(started.jobId, false, generation);
    } catch (error) {
      if (controller.signal.aborted || generationRef.current !== generation) return;
      setState({ kind: "error", jobId: null, message: errorMessage(error) });
    }
  }, [api, key, refreshJob, reviewEpisodeId, subjectId]);

  const resume = useCallback(async (jobId: string) => {
    const generation = ++generationRef.current;
    controllerRef.current?.abort();
    requestRef.current += 1;
    const controller = new AbortController();
    controllerRef.current = controller;
    setState({ kind: "loading", jobId });
    try {
      await api.resume(subjectId, reviewEpisodeId, jobId, { signal: controller.signal });
      if (generationRef.current !== generation) return;
      await refreshJob(jobId, false, generation);
    } catch (error) {
      if (controller.signal.aborted || generationRef.current !== generation) return;
      setState({ kind: "error", jobId, message: errorMessage(error) });
    }
  }, [api, refreshJob, reviewEpisodeId, subjectId]);

  const retry = useCallback(() => {
    if (state.kind === "error" && state.jobId !== null) {
      void refreshJob(state.jobId, true, generationRef.current);
    } else {
      void start();
    }
  }, [refreshJob, start, state]);

  const toggleRequirement = useCallback((requirementId: string) => {
    setExpandedRequirements((current) => ({
      ...current,
      [requirementId]: !current[requirementId],
    }));
  }, []);

  const renderRequirements = (
    requirements: ReadonlyArray<{
      requirementId: string;
      requirementLabel?: string;
      statusLabel: string;
      foundCandidateCount: number;
      foundCandidates?: ReadonlyArray<JudgmentSearchCandidateView>;
      incompletePages?: ReadonlyArray<{
        pageNumber: number;
        reasons: ReadonlyArray<string>;
      }>;
    }>,
    canExpand: boolean,
  ) => (
    <ul className="judgment-search-card__requirements">
      {requirements.map((requirement) => {
        const candidates = requirement.foundCandidates ?? [];
        const expanded = expandedRequirements[requirement.requirementId] === true;
        return (
          <li key={requirement.requirementId} className="judgment-search-card__requirement">
            <div className="judgment-search-card__requirement-head">
              <strong title={requirement.requirementId}>{requirement.requirementLabel ?? "研究者书面判断"}</strong>
              <span>{requirement.statusLabel}</span>
              {canExpand && requirement.foundCandidateCount > 0 && (
                <button
                  type="button"
                  className="chip"
                  aria-expanded={expanded}
                  onClick={() => toggleRequirement(requirement.requirementId)}
                >
                  候选 {requirement.foundCandidateCount} 条
                </button>
              )}
              {!canExpand && (
                <span className="count-chip">候选 {requirement.foundCandidateCount} 条</span>
              )}
            </div>
            {canExpand && expanded && candidates.length > 0 && (
              <ul className="judgment-search-card__candidates">
                {candidates.map((candidate, index) => (
                  <li key={`${candidate.pageArtifactId}-${candidate.pageNumber}-${index}`}>
                    <button
                      type="button"
                      className="judgment-search-card__candidate"
                      onClick={() =>
                        onSelectCandidate({
                          page_artifact_id: candidate.pageArtifactId,
                          page_number: candidate.pageNumber,
                        })
                      }
                    >
                      <span>
                        第 {candidate.pageNumber} 页 · {candidate.laneLabel} · {candidate.channelLabel}
                      </span>
                      <span className="judgment-search-card__excerpt-list">
                        {candidate.excerpts.map((excerpt, excerptIndex) => (
                          <q key={`${candidate.pageArtifactId}-excerpt-${excerptIndex}`}>
                            {excerpt.text}
                          </q>
                        ))}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {canExpand && requirement.incompletePages !== undefined && requirement.incompletePages.length > 0 && (
              <ul className="judgment-search-card__incomplete">
                {requirement.incompletePages.map((page) => (
                  <li key={`${requirement.requirementId}-${page.pageNumber}`}>
                    第 {page.pageNumber} 页：{page.reasons.join("；")}
                  </li>
                ))}
              </ul>
            )}
          </li>
        );
      })}
    </ul>
  );

  const statusRequirements = state.kind === "running" ? state.status.requirementResults : [];
  const resultRequirements =
    state.kind === "completed"
      ? state.results.results.map((result) => ({
          requirementId: result.requirementId,
          requirementLabel: result.requirementLabel,
          statusLabel: result.statusLabel,
          foundCandidateCount: result.foundCandidates.length,
          foundCandidates: result.foundCandidates,
          incompletePages: result.incompletePages,
        }))
      : state.kind === "cancelled" && state.results !== null
        ? state.results.results.map((result) => ({
            requirementId: result.requirementId,
            requirementLabel: result.requirementLabel,
            statusLabel: result.statusLabel,
            foundCandidateCount: result.foundCandidates.length,
            foundCandidates: result.foundCandidates,
            incompletePages: result.incompletePages,
          }))
        : [];

  return (
    <section
      className="profile-section judgment-search-card"
      aria-labelledby="judgment-search-card-title"
      data-evidence-revision={evidenceNavigation.completeProcessingRevisionId}
    >
      <header className="profile-section__heading">
        <div>
          <h3 id="judgment-search-card-title" className="profile-section__title">
            书面判断检索
          </h3>
          <p className="profile-section__note">在本次提交的资料中查找研究者书写的判断文字。</p>
        </div>
      </header>

      {state.kind === "idle" && (
        <div className="judgment-search-card__empty">
          <p>尚未发起书面判断检索。</p>
          <button type="button" className="button button--primary" onClick={() => void start()}>
            开始查找书面判断
          </button>
        </div>
      )}
      {state.kind === "loading" && (
        <p role="status" className="judgment-search-card__status">
          正在读取书面判断检索进度…
        </p>
      )}
      {state.kind === "running" && (
        <div className="judgment-search-card__running">
          <p role="status">
            正在查找研究者书面判断…（已查 {state.status.completedReads}/{state.status.totalPages} 页）
          </p>
          {renderRequirements(statusRequirements, false)}
        </div>
      )}
      {state.kind === "completed" && (
        <div className="judgment-search-card__completed">
          <p className="judgment-search-card__summary">
            本次检索已完成，共发现 {candidateCount(state.results)} 条待人工核对的候选内容。
          </p>
          {renderRequirements(resultRequirements, true)}
        </div>
      )}
      {state.kind === "cancelled" && (
        <div className="judgment-search-card__cancelled">
          <p>本次检索已停止，已保存的结果仍可查看。</p>
          {state.results !== null && renderRequirements(resultRequirements, true)}
          {state.status.canResume && (
            <button type="button" className="button button--primary" onClick={() => void resume(state.jobId)}>
              继续查找
            </button>
          )}
        </div>
      )}
      {state.kind === "error" && (
        <div className="judgment-search-card__error" role="alert">
          <p>{state.message}</p>
          <button type="button" className="button" onClick={retry}>
            重试
          </button>
        </div>
      )}
    </section>
  );
}
