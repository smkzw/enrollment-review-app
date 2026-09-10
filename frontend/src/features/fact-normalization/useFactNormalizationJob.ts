/**
 * 个例档案整理任务生命周期：命令启动、本机 job id 持久化、标准 Job API 恢复轮询。
 * 进度不保存在组件内存 alone；刷新后从 localStorage + /api/v2/jobs/{id} 恢复。
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

function readStoredJobId(reviewEpisodeId: string): string | null {
  try {
    const value = window.localStorage.getItem(
      factNormalizationJobStorageKey(reviewEpisodeId),
    );
    return value !== null && value.trim().length > 0 ? value.trim() : null;
  } catch {
    return null;
  }
}

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
  /** 档案侧已判定陈旧时展示 stale 相位与恢复动作。 */
  profileStale?: boolean;
  /** 任务成功终态时回调（用于刷新档案）。 */
  onSucceeded?: (jobId: string) => void;
  /** 轮询间隔（测试可缩短）。 */
  pollIntervalMs?: number;
}

export interface UseFactNormalizationJobResult {
  state: FactNormalizationUiState;
  completedReview: { jobId: string; subjectId: string; reviewEpisodeId: string } | null;
  /** 发起或幂等复用整理任务。 */
  start: (idempotencyKey?: string) => Promise<string | null>;
  /** 失败后重试失败范围，或陈旧时重新下发命令。 */
  retry: () => Promise<void>;
  /** 仅从本机恢复已持久的 job id 并拉取状态。 */
  resumeFromStorage: () => Promise<void>;
}

export function useFactNormalizationJob(
  options: UseFactNormalizationJobOptions,
): UseFactNormalizationJobResult {
  const {
    subjectId,
    reviewEpisodeId,
    profileStale = false,
    onSucceeded,
    pollIntervalMs = POLL_MS,
  } = options;

  const [state, setState] = useState<FactNormalizationUiState>({ status: "idle" });
  const jobIdRef = useRef<string | null>(null);
  const profileStaleRef = useRef(profileStale);
  const onSucceededRef = useRef(onSucceeded);
  const startInFlight = useRef<Promise<string | null> | null>(null);
  const idempotencyRef = useRef<string | null>(null);
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
      applyJob(job);
      return job;
    },
    [applyJob],
  );

  const resumeFromStorage = useCallback(async () => {
    if (reviewEpisodeId === null) return;
    const stored = readStoredJobId(reviewEpisodeId);
    if (stored === null) return;
    jobIdRef.current = stored;
    try {
      await fetchStatus(stored);
    } catch (error) {
      const ui = toUiError(error);
      setState({
        status: "error",
        message: ui.message,
        recoveryHint: ui.recoveryHint,
        canRetry: true,
      });
    }
  }, [fetchStatus, reviewEpisodeId]);

  // 切换审核节点时清理内存态并从本机恢复。
  useEffect(() => {
    jobIdRef.current = null;
    idempotencyRef.current = null;
    startInFlight.current = null;
    succeededNotified.current = null;
    setState({ status: "idle" });
    if (reviewEpisodeId === null) return;
    let cancelled = false;
    void (async () => {
      const stored = readStoredJobId(reviewEpisodeId);
      if (stored === null || cancelled) return;
      jobIdRef.current = stored;
      try {
        const job = await getFactNormalizationRepository().getFactNormalizationJobStatus(
          stored,
        );
        if (!cancelled) applyJob(job);
      } catch (error) {
        if (cancelled) return;
        const ui = toUiError(error);
        setState({
          status: "error",
          message: ui.message,
          recoveryHint: ui.recoveryHint,
          canRetry: true,
        });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [applyJob, reviewEpisodeId]);

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
    async (idempotencyKey?: string, allowPageRead = true): Promise<string | null> => {
      if (subjectId === null || reviewEpisodeId === null) return null;
      if (startInFlight.current !== null) return startInFlight.current;

      const key =
        idempotencyKey ??
        idempotencyRef.current ??
        newIdempotencyKey(`profile-organize:${reviewEpisodeId}`);
      idempotencyRef.current = key;

      const pending = (async () => {
        try {
          const command = await getFactNormalizationRepository().startFactNormalization(
            subjectId,
            reviewEpisodeId,
            { idempotencyKey: key },
          );
          writeStoredJobId(reviewEpisodeId, command.jobId);
          jobIdRef.current = command.jobId;
          const job = await getFactNormalizationRepository().getFactNormalizationJobStatus(
            command.jobId,
          );
          applyJob(job);
          return command.jobId;
        } catch (error) {
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
            canRetry: true,
          });
          return null;
        } finally {
          startInFlight.current = null;
        }
      })();

      startInFlight.current = pending;
      return pending;
    },
    [applyJob, reviewEpisodeId, subjectId, pageReview.start],
  );
  afterPages.current = () => { void start(undefined, false); };

  const retry = useCallback(async () => {
    if (subjectId === null || reviewEpisodeId === null) return;
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
      const action = await getFactNormalizationRepository().retryFactNormalizationJob(jobId);
      const job = await getFactNormalizationRepository().getFactNormalizationJobStatus(
        action.jobId,
      );
      applyJob(job);
    } catch {
      idempotencyRef.current = newIdempotencyKey(`profile-organize-retry:${reviewEpisodeId}`);
      await start(idempotencyRef.current);
    }
  }, [applyJob, reviewEpisodeId, start, state.status, subjectId, pageReview.state.status, pageReview.retry]);

  return { state: pageReview.state.status === "idle" ? state : pageReview.state,
    completedReview: pageReview.completedReview, start, retry, resumeFromStorage };
}

export function clearFactNormalizationJobStorage(reviewEpisodeId: string): void {
  clearStoredJobId(reviewEpisodeId);
}
