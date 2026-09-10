import { useCallback, useEffect, useRef, useState } from "react";
import { createPageReviewHttp, PageReviewApiError, type PageReviewStatus } from "../../api/page-review/pageReviewHttp";

export type PageReviewUiState = { status: "idle" } | {
  status: "page_review";
  title: string;
  message: string;
  canRetry: boolean;
  totalPages: number;
  completedPages: number;
  jobId?: string;
  subjectId?: string;
  reviewEpisodeId?: string;
  retryLabel?: string;
  needsAttention?: boolean;
};

export function pageReviewStorageKey(subjectId: string, episodeId: string) {
  return `enrollment:page-review:${encodeURIComponent(subjectId)}:${encodeURIComponent(episodeId)}`;
}

function stored(key: string): string | null {
  try { return window.localStorage.getItem(key); } catch { return null; }
}
function save(key: string, jobId: string | null) {
  try {
    if (jobId === null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, jobId);
  } catch { /* The durable server job remains authoritative. */ }
}

function display(job: PageReviewStatus): PageReviewUiState {
  const failed = job.reviewStatus === "needs_reread" || job.reviewStatus === "stopped";
  return { status: "page_review", title: failed ? "资料识别尚未完成" : "正在识别资料",
    message: job.reviewStatus === "needs_reread" && !job.canReread ? "补读后仍有资料未能读清，请核对原件。已完成的结果会保留。"
      : job.failedPages > 0 ? `${job.failedPages} 页暂未读完，已完成的结果会保留。`
      : failed ? "请查看原任务并恢复处理，已完成的结果会保留。" : "读页完成后将继续整理个例档案。",
    canRetry: job.canReread || job.state === "cancelled", totalPages: job.totalPages,
    completedPages: job.acceptedPages + job.unrelatedPages, jobId: job.jobId,
    retryLabel: job.state === "cancelled" ? "继续识别" : "重读未完成资料", needsAttention: failed };
}

export function usePageReviewJob({ subjectId, reviewEpisodeId, onReady, pollIntervalMs = 2000 }: {
  subjectId: string | null; reviewEpisodeId: string | null;
  onReady: () => void; pollIntervalMs?: number;
}) {
  const [state, setState] = useState<PageReviewUiState>({ status: "idle" });
  const [completed, setCompleted] = useState<{ key: string; jobId: string } | null>(null);
  const api = useRef<ReturnType<typeof createPageReviewHttp> | null>(null);
  if (api.current === null) api.current = createPageReviewHttp();
  const ready = useRef(onReady);
  ready.current = onReady;
  const current = useRef<{ controller: AbortController; job: PageReviewStatus | null; jobId: string | null } | null>(null);
  const starting = useRef(false);
  const key = subjectId && reviewEpisodeId ? pageReviewStorageKey(subjectId, reviewEpisodeId) : null;

  const observe = useCallback(async (jobId: string, owner: NonNullable<typeof current.current>, notifyReady = true) => {
    if (subjectId === null || reviewEpisodeId === null || key === null) return;
    const { signal } = owner.controller;
    try {
      while (!signal.aborted && current.current === owner) {
        const job = await api.current!.status(subjectId, reviewEpisodeId, jobId, signal);
        if (signal.aborted || current.current !== owner) return;
        if (job.jobId !== jobId) throw new PageReviewApiError();
        owner.job = job;
        if (!notifyReady && job.reviewStatus !== "ready") return;
        if (job.reviewStatus === "ready") {
          save(key, null);
          save(`${key}:completed`, jobId);
          setCompleted({ key, jobId });
          current.current = null;
          setState({ status: "idle" });
          if (notifyReady) ready.current();
          return;
        }
        setState(display(job));
        if (job.reviewStatus !== "processing") return;
        await new Promise<void>((resolve) => {
          const finish = () => { clearTimeout(timer); signal.removeEventListener("abort", finish); resolve(); };
          const timer = setTimeout(finish, pollIntervalMs);
          signal.addEventListener("abort", finish, { once: true });
        });
      }
    } catch (error) {
      if (signal.aborted || current.current !== owner) return;
      if (!notifyReady) return;
      setState({ status: "page_review", title: "暂时无法查看资料进度",
        message: error instanceof PageReviewApiError ? error.message : "请重新查询进度，已完成的识别结果会保留。",
        canRetry: true, totalPages: 0, completedPages: 0, jobId, retryLabel: "重新查询进度", needsAttention: true });
    }
  }, [subjectId, reviewEpisodeId, key, pollIntervalMs]);

  useEffect(() => {
    current.current?.controller.abort();
    current.current = null;
    starting.current = false;
    setState({ status: "idle" });
    setCompleted(null);
    const activeJobId = key ? stored(key) : null;
    const jobId = activeJobId ?? (key ? stored(`${key}:completed`) : null);
    if (jobId) {
      const owner = { controller: new AbortController(), job: null, jobId };
      current.current = owner;
      void observe(jobId, owner, activeJobId !== null);
    }
    return () => { current.current?.controller.abort(); current.current = null; };
  }, [key, observe]);

  const start = useCallback(async () => {
    if (!subjectId || !reviewEpisodeId || !key || starting.current) return;
    const previous = current.current;
    if (previous?.jobId && !previous.job?.canReread && previous.job?.state !== "cancelled") {
      previous.controller.abort();
      const owner = { ...previous, controller: new AbortController() };
      current.current = owner;
      void observe(previous.jobId, owner);
      return;
    }
    previous?.controller.abort();
    const owner = { controller: new AbortController(), job: null, jobId: null as string | null };
    current.current = owner;
    starting.current = true;
    setState({ status: "page_review", title: "正在准备资料识别", message: "已完成的结果会保留。",
      canRetry: false, totalPages: 0, completedPages: 0 });
    try {
      const jobId = previous?.job?.state === "cancelled" && previous.jobId
        ? await api.current!.resume(subjectId, reviewEpisodeId, previous.jobId, owner.controller.signal)
        : await api.current!.start(subjectId, reviewEpisodeId,
          previous?.job?.canReread ? previous.jobId ?? undefined : undefined, owner.controller.signal);
      if (owner.controller.signal.aborted || current.current !== owner) return;
      owner.jobId = jobId;
      save(key, jobId);
      void observe(jobId, owner);
    } catch (error) {
      if (owner.controller.signal.aborted || current.current !== owner) return;
      // Keep the predecessor on submission failure so retry cannot silently start a root.
      current.current = previous ?? owner;
      setState({ status: "page_review", title: "资料识别未能开始",
        message: error instanceof PageReviewApiError ? error.message : "请稍后重试。",
        canRetry: true, totalPages: 0, completedPages: 0,
        jobId: previous?.jobId ?? undefined,
        retryLabel: previous?.job?.state === "cancelled" ? "重试继续识别" : "重新开始识别", needsAttention: true });
    } finally {
      if (current.current === owner || current.current === previous) starting.current = false;
    }
  }, [subjectId, reviewEpisodeId, key, observe]);
  const scopedState: PageReviewUiState = state.status === "page_review"
    ? { ...state, subjectId: subjectId ?? undefined, reviewEpisodeId: reviewEpisodeId ?? undefined } : state;
  const completedReview = completed?.key === key && subjectId && reviewEpisodeId
    ? { jobId: completed.jobId, subjectId, reviewEpisodeId } : null;
  return { state: scopedState, completedReview, start, retry: start };
}
