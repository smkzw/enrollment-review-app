/**
 * 个例档案整理任务状态条：排队/进行中/成功/失败/陈旧。
 * 只展示中文临床措辞与明确恢复动作；不暴露内部技术标签。
 */

import type { FactNormalizationUiState } from "../../features/fact-normalization/useFactNormalizationJob";
import { RouteLink } from "../../app/router";

export interface ProfileNormalizationStatusProps {
  state: FactNormalizationUiState;
  onRetry?: () => void;
  onOpenProfile?: () => void;
}

export function ProfileNormalizationStatus({
  state,
  onRetry,
  onOpenProfile,
}: ProfileNormalizationStatusProps) {
  if (state.status === "idle") return null;

  if (state.status === "page_review") {
    return (
      <div className={`profile-normalization profile-normalization--${state.needsAttention ? "failed" : "progress"}`} role="status" aria-label="资料判读进度">
        <div className="profile-normalization__body">
          <p className="profile-normalization__title">{state.title}</p>
          <p className="profile-normalization__hint">{state.message}</p>
          {state.totalPages > 0 && <p className="profile-normalization__progress">已读完 {state.completedPages} / {state.totalPages} 页</p>}
        </div>
        {state.canRetry && onRetry && <button type="button" className="button" onClick={onRetry}>{state.retryLabel ?? "重读未完成资料"}</button>}
        {state.jobId && <RouteLink to="/tasks" params={{ job: state.jobId, subject: state.subjectId, episode: state.reviewEpisodeId }} className="button">查看处理进度</RouteLink>}
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <div className="profile-normalization profile-normalization--failed" role="alert">
        <div className="profile-normalization__body">
          <p className="profile-normalization__title">个例档案整理未完成</p>
          <p className="profile-normalization__hint">{state.message}</p>
          <p className="profile-normalization__hint">{state.recoveryHint}</p>
        </div>
        {state.canRetry && onRetry !== undefined && (
          <button type="button" className="button" onClick={onRetry}>
            重新整理个例档案
          </button>
        )}
      </div>
    );
  }

  const tone =
    state.phase === "failed"
      ? "failed"
      : state.phase === "stale"
        ? "stale"
        : state.phase === "succeeded"
          ? "succeeded"
          : "progress";

  return (
    <div
      className={`profile-normalization profile-normalization--${tone}`}
      role={state.phase === "failed" ? "alert" : "status"}
      aria-label="个例档案整理状态"
    >
      {(state.phase === "queued" || state.phase === "running") && (
        <span className="feedback__spinner" aria-hidden="true" />
      )}
      <div className="profile-normalization__body">
        <p className="profile-normalization__title">{state.title}</p>
        <p className="profile-normalization__hint">{state.recoveryHint}</p>
        {state.job !== null && state.job.progressTotal > 0 && (
          <p className="profile-normalization__progress">
            已完成 {state.job.progressCompleted} / {state.job.progressTotal} 项
          </p>
        )}
      </div>
      {state.canRetry && onRetry !== undefined && (
        <button type="button" className="button" onClick={() => void onRetry()}>
          重新整理个例档案
        </button>
      )}
      {state.phase === "succeeded" && onOpenProfile !== undefined && (
        <button type="button" className="button" onClick={onOpenProfile}>
          查看受试者档案
        </button>
      )}
    </div>
  );
}
