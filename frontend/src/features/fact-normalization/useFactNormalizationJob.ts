/**
 * 个例档案整理任务生命周期：命令启动、本机 job id 持久化、标准 Job API 恢复轮询。
 * 服务端当前资料范围决定恢复的任务；本机缓存不能替代来源核对。
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { usePageReviewJob, type PageReviewUiState } from "./usePageReviewJob";
import {
  factNormalizationDisplayPhase,
  factNormalizationJobStorageKey,
  factNormalizationPhaseTitle,
  factNormalizationRecoveryHint,
  FactNormalizationApiError,
  getFactNormalizationRepository,
  isFailureFactNormalizationState,
  isTerminalFactNormalizationState,
  type FactNormalizationDisplayPhase,
  type FactNormalizationJobStatusView,
} from "../../api/fact-normalization";

const POLL_MS = 2_000;

export type FactNormalizationUiState =
  | PageReviewUiState
  | { status: "idle" }
  | {
      status: "active";
      jobId: string;
      phase: FactNormalizationDisplayPhase;
      title: string;
      recoveryHint: string;
      job: FactNormalizationJobStatusView | null;
      canRetry: boolean;
    }
  | { status: "error"; message: string; recoveryHint: string; canRetry: boolean };

function writeStoredJobId(reviewEpisodeId: string, jobId: string): void {
  try {
    window.localStorage.setItem(factNormalizationJobStorageKey(reviewEpisodeId), jobId);
  } catch {
    // 本机存储不可用时仍可继续当前会话轮询。
  }
}

function clearStoredJobId(reviewEpisodeId: string): void {
  try {
    window.localStorage.removeItem(factNormalizationJobStorageKey(reviewEpisodeId));
  } catch {
    // ignore
  }
}

function newIdempotencyKey(prefix: string): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `${prefix}:${crypto.randomUUID()}`;
  }
  return `${prefix}:${Date.now()}:${Math.random().toString(36).slice(2)}`;
}

function toUiError(error: unknown): { message: string; recoveryHint: string } {
  if (error instanceof FactNormalizationApiError) {
    return {
      message: error.message,
      recoveryHint:
        error.recoveryAction.length > 0
          ? error.recoveryAction
          : "请稍后重试；若问题持续出现，请联系维护人员。",
    };
  }
  return {
    message: "暂时无法整理个例档案。",
    recoveryHint: "请稍后重试；若问题持续出现，请联系维护人员。",
  };
}

function activeFromJob(
  job: FactNormalizationJobStatusView,
  profileStale: boolean,
): Extract<FactNormalizationUiState, { status: "active" }> {
  const phase =
    factNormalizationDisplayPhase(job.state, { profileStale }) ??
    (isFailureFactNormalizationState(job.state) ? "failed" : "running");
  return {
    status: "active",
    jobId: job.jobId,
    phase,
    title: factNormalizationPhaseTitle(phase),
    recoveryHint: factNormalizationRecoveryHint(phase, job.recoveryAction),
    job,
    canRetry: isFailureFactNormalizationState(job.state) || phase === "stale",
  };
}

export interface UseFactNormalizationJobOptions {
  subjectId: string | null;
  reviewEpisodeId: string | null;
  sourceRevisionId?: string | null;
  /** 档案侧已判定陈旧时展示 stale 相位与恢复动作。 */
  profileStale?: boolean;
  /** 任务成功终态时回调（用于刷新档案）。 */
  onSucceeded?: (jobId: string) => void;
  /** 轮询间隔（测试可缩短）。 */
  pollIntervalMs?: number;
}

export interface UseFactNormalizationJobResult {
  state: FactNormalizationUiState;
  restoring: boolean;
  completedReview: { jobId: string; subjectId: string; reviewEpisodeId: string } | null;
  /** 发起或幂等复用整理任务。 */
  start: (idempotencyKey?: string) => Promise<string | null>;
  retryFailedPages: (runId: string) => Promise<string | null>;
  revalidateSaved: (runId: string) => Promise<string | null>;
  /** 失败后重试失败范围，或陈旧时重新下发命令。 */
  retry: () => Promise<void>;
  /** 恢复服务端当前范围的已持久任务，不启动读取。 */
  resumeFromStorage: () => Promise<void>;
}

export function useFactNormalizationJob(
  options: UseFactNormalizationJobOptions,
): UseFactNormalizationJobResult {
  const {
    subjectId,
    reviewEpisodeId,
    sourceRevisionId = null,
    profileStale = false,
    onSucceeded,
    pollIntervalMs = POLL_MS,
  } = options;

  const [state, setState] = useState<FactNormalizationUiState>({ status: "idle" });
  const scopeKey = JSON.stringify([subjectId, reviewEpisodeId, sourceRevisionId]);
  const identityKey = JSON.stringify([subjectId, reviewEpisodeId]);
  const currentScope = useRef(scopeKey);
  currentScope.current = scopeKey;
  const currentIdentity = useRef(identityKey);
  currentIdentity.current = identityKey;
  const mounted = useRef(true);
  const resumeCurrentScope = useRef<() => Promise<void>>(async () => {});
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const [restoredScope, setRestoredScope] = useState<string | null>(null);
  const restoring = subjectId !== null && reviewEpisodeId !== null && restoredScope !== scopeKey;
  const jobIdRef = useRef<string | null>(null);
  const profileStaleRef = useRef(profileStale);
  const onSucceededRef = useRef(onSucceeded);
  const startInFlight = useRef<Promise<string | null> | null>(null);
  const idempotencyRef = useRef<string | null>(null);
  const revalidationRef = useRef<string | null>(null);
  const succeededNotified = useRef<string | null>(null);
  const afterPages = useRef<() => void>(() => {});
  const pageReview = usePageReviewJob({ subjectId, reviewEpisodeId,
    onReady: () => afterPages.current(), pollIntervalMs });

  useEffect(() => {
    profileStaleRef.current = profileStale;
  }, [profileStale]);

  useEffect(() => {
    onSucceededRef.current = onSucceeded;
  }, [onSucceeded]);

  const applyJob = useCallback(
    (job: FactNormalizationJobStatusView) => {
      jobIdRef.current = job.jobId;
      if (reviewEpisodeId !== null) {
        writeStoredJobId(reviewEpisodeId, job.jobId);
      }
      const next = activeFromJob(job, profileStaleRef.current);
      setState(next);
      if (job.state === "completed" && succeededNotified.current !== job.jobId) {
        succeededNotified.current = job.jobId;
        onSucceededRef.current?.(job.jobId);
      }
      return next;
    },
    [reviewEpisodeId],
  );

  const fetchStatus = useCallback(
    async (jobId: string, signal?: AbortSignal) => {
      const job = await getFactNormalizationRepository().getFactNormalizationJobStatus(
        jobId,
        { signal },
      );
      if (currentScope.current === scopeKey) applyJob(job);
      return job;
    },
    [applyJob, scopeKey],
  );

  const resumeFromStorage = useCallback(async () => {
    if (subjectId === null || reviewEpisodeId === null) return;
    try {
      const job = await getFactNormalizationRepository().getCurrentFactNormalizationJob(subjectId, reviewEpisodeId);
      if (currentScope.current !== scopeKey || startInFlight.current !== null) return;
      if (job !== null) applyJob(job);
      else { clearStoredJobId(reviewEpisodeId); setState({ status: "idle" }); }
    } catch (error) {
      if (currentScope.current !== scopeKey) return;
      const ui = toUiError(error);
      setState({
        status: "error",
        message: ui.message,
        recoveryHint: ui.recoveryHint,
        canRetry: true,
      });
    } finally {
      if (currentScope.current === scopeKey) setRestoredScope(scopeKey);
    }
  }, [applyJob, reviewEpisodeId, subjectId, scopeKey]);
  resumeCurrentScope.current = resumeFromStorage;

  // Scope discovery is read-only. Late responses cannot replace a new scope/start.
  useEffect(() => {
    jobIdRef.current = null;
    idempotencyRef.current = null;
    revalidationRef.current = null;
    startInFlight.current = null;
    succeededNotified.current = null;
    setState({ status: "idle" });
    if (subjectId === null || reviewEpisodeId === null) return;
    let cancelled = false;
    const controller = new AbortController();
    void (async () => {
      try {
        const job = await getFactNormalizationRepository().getCurrentFactNormalizationJob(
          subjectId, reviewEpisodeId, { signal: controller.signal });
        if (cancelled || currentScope.current !== scopeKey || startInFlight.current !== null || jobIdRef.current !== null) return;
        if (job !== null) applyJob(job);
        else clearStoredJobId(reviewEpisodeId);
      } catch (error) {
        if (cancelled || currentScope.current !== scopeKey || startInFlight.current !== null || jobIdRef.current !== null) return;
        const ui = toUiError(error);
        setState({
          status: "error",
          message: ui.message,
          recoveryHint: ui.recoveryHint,
          canRetry: true,
        });
      } finally {
        if (!cancelled && currentScope.current === scopeKey) setRestoredScope(scopeKey);
      }
    })();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [applyJob, reviewEpisodeId, subjectId, scopeKey]);

  // 非终态且非失败态轮询；失败/陈旧等待用户明确恢复动作。
  const pollJobId =
    state.status === "active" &&
    state.job !== null &&
    !isTerminalFactNormalizationState(state.job.state) &&
    !isFailureFactNormalizationState(state.job.state) &&
    state.phase !== "stale"
      ? state.jobId
      : null;

  useEffect(() => {
    if (pollJobId === null) return;
    const controller = new AbortController();
    const timer = window.setInterval(() => {
      void fetchStatus(pollJobId, controller.signal).catch(() => {
        // 瞬时失败保留上一状态；用户可点重试。
      });
    }, pollIntervalMs);
    return () => {
      controller.abort();
      window.clearInterval(timer);
    };
  }, [fetchStatus, pollIntervalMs, pollJobId]);

  // 档案变为陈旧时刷新相位文案（不重启任务）。
  useEffect(() => {
    setState((current) => {
      if (current.status !== "active" || current.job === null) return current;
      const next = activeFromJob(current.job, profileStale);
      if (
        next.phase === current.phase &&
        next.title === current.title &&
        next.recoveryHint === current.recoveryHint &&
        next.canRetry === current.canRetry
      ) {
        return current;
      }
      return next;
    });
  }, [profileStale]);

  const start = useCallback(
    async (idempotencyKey?: string, allowPageRead = true, retryFailedFromRunId?: string, revalidateFromRunId?: string): Promise<string | null> => {
      if (subjectId === null || reviewEpisodeId === null) return null;
      if (startInFlight.current !== null) return startInFlight.current;

      const key =
        idempotencyKey ??
        idempotencyRef.current ??
        newIdempotencyKey(`profile-organize:${reviewEpisodeId}`);
      idempotencyRef.current = key;
      revalidationRef.current = revalidateFromRunId ?? null;

      const pending = (async () => {
        try {
          const command = await getFactNormalizationRepository().startFactNormalization(
            subjectId,
            reviewEpisodeId,
            { idempotencyKey: key, ...(retryFailedFromRunId ? {retryFailedFromRunId} : {}),
              ...(revalidateFromRunId ? {revalidateFromRunId} : {}) },
          );
          writeStoredJobId(reviewEpisodeId, command.jobId);
          if (currentScope.current !== scopeKey) return command.jobId;
          jobIdRef.current = command.jobId;
          const job = await getFactNormalizationRepository().getFactNormalizationJobStatus(
            command.jobId,
          );
          if (currentScope.current === scopeKey) {
            applyJob(job);
            setRestoredScope(scopeKey);
          }
          return command.jobId;
        } catch (error) {
          if (currentScope.current !== scopeKey) return null;
          if (allowPageRead && error instanceof FactNormalizationApiError && error.code === "PAGE_COVERAGE_NOT_READY") {
            setState({ status: "idle" });
            void pageReview.start();
            return null;
          }
          const ui = toUiError(error);
          setState({
            status: "error",
            message: ui.message,
            recoveryHint: ui.recoveryHint,
            canRetry: !revalidateFromRunId,
          });
          return null;
        } finally {
          if (currentScope.current === scopeKey) startInFlight.current = null;
          // Activation can refresh the source before its POST returns. Discover
          // the current scope again; never adopt the old command by its ID.
          else if (mounted.current && currentIdentity.current === identityKey) await resumeCurrentScope.current();
        }
      })();

      startInFlight.current = pending;
      return pending;
    },
    [applyJob, reviewEpisodeId, subjectId, pageReview.start, scopeKey, identityKey],
  );
  afterPages.current = () => { void start(undefined, false); };

  const retry = useCallback(async () => {
    if (subjectId === null || reviewEpisodeId === null) return;
    if (revalidationRef.current && !(state.status === "active" && state.phase === "failed")) {
      await start(undefined, false, undefined, revalidationRef.current);
      return;
    }
    if (pageReview.state.status !== "idle") {
      await pageReview.retry();
      return;
    }

    if (profileStaleRef.current || state.status === "error" || jobIdRef.current === null) {
      idempotencyRef.current = newIdempotencyKey(`profile-organize-retry:${reviewEpisodeId}`);
      await start(idempotencyRef.current);
      return;
    }

    const jobId = jobIdRef.current;
    try {
      const read = getFactNormalizationRepository().getNormalizationUnresolved;
      if (read) {
        const source = await read(subjectId, reviewEpisodeId, jobId, 0);
        if (currentScope.current !== scopeKey) return;
        if (source.revalidationSourceRunId) {
          if (!source.canRevalidateSaved) {
            setState({status: "error", message: "本次核验仍有未解决问题。",
              recoveryHint: "原来的读取结果已保留；修复后可从资料页重新核验，不会重新调用模型。", canRetry: false});
            return;
          }
          await start(undefined, false, undefined, source.revalidationSourceRunId);
          return;
        }
      }
      const action = await getFactNormalizationRepository().retryFactNormalizationJob(jobId);
      if (currentScope.current !== scopeKey) return;
      const job = await getFactNormalizationRepository().getFactNormalizationJobStatus(
        action.jobId,
      );
      if (currentScope.current === scopeKey) applyJob(job);
    } catch (error) {
      if (currentScope.current !== scopeKey) return;
      const ui = toUiError(error);
      setState({status: "error", ...ui, canRetry: false});
    }
  }, [applyJob, reviewEpisodeId, start, state, subjectId, pageReview.state.status, pageReview.retry, scopeKey]);

  return { state: restoring ? { status: "idle" } : pageReview.state.status === "idle" ? state : pageReview.state,
    restoring,
    completedReview: pageReview.completedReview, start, retry,
    retryFailedPages: (runId: string) => start(undefined, false, runId),
    revalidateSaved: (runId: string) => start(undefined, false, undefined, runId), resumeFromStorage };
}

export function clearFactNormalizationJobStorage(reviewEpisodeId: string): void {
  clearStoredJobId(reviewEpisodeId);
}
