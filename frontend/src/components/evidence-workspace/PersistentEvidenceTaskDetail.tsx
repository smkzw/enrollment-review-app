import { useEffect, useState } from "react";
import { getCatalogRepository } from "../../api";
import {
  getEvidenceJobDetail,
  retryEvidenceJob,
} from "../../api/evidence";
import { RouteLink } from "../../app/router";
import { useLoad } from "../../app/useLoad";
import { ErrorState, LoadingState } from "../shell/Feedback";
import { OpenIcon, ResumeIcon } from "../shell/icons";
import { StatusBadge, type Tone } from "../shell/StatusBadge";

interface PersistentEvidenceTaskDetailProps {
  jobId: string;
  subjectId: string | null;
  reviewEpisodeId: string | null;
}

function stateTone(state: string): Tone {
  if (state === "completed") return "ok";
  if (state === "failed_final") return "danger";
  if (state === "failed_retryable" || state === "waiting_user") return "info";
  return "neutral";
}

function isActive(state: string): boolean {
  return ["queued", "running", "recovering", "cancel_requested", "user_resumed"].includes(state);
}

function activeTaskFeedback(state: string): string {
  if (state === "queued") return "本次资料整理正在等待开始。";
  if (state === "recovering") return "系统正在恢复本次资料整理。";
  if (state === "cancel_requested") return "系统正在按安全节点停止本次整理。";
  if (state === "user_resumed") return "系统已收到继续处理请求，正在恢复。";
  return "系统仍在持续处理。复杂页面可能需要较长时间。";
}

function canRetry(state: string): boolean {
  return state === "failed_retryable" || state === "failed_final";
}

function displayStepName(name: string): string {
  if (name === "evidence_processing") return "整理原始资料";
  if (/^[A-Za-z0-9_./-]+$/.test(name)) return "整理资料";
  return name;
}

function formatTime(iso: string): string {
  const value = new Date(iso);
  if (Number.isNaN(value.getTime())) return iso;
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(value);
}

export function PersistentEvidenceTaskDetail({
  jobId,
  subjectId,
  reviewEpisodeId,
}: PersistentEvidenceTaskDetailProps) {
  const detail = useLoad((signal) => getEvidenceJobDetail(jobId, signal), [jobId]);
  const contextReady = subjectId !== null && reviewEpisodeId !== null;
  const context = useLoad(
    (signal) =>
      getCatalogRepository().getEvidenceContext(
        subjectId as string,
        reviewEpisodeId as string,
        signal,
      ),
    [subjectId, reviewEpisodeId],
    { enabled: contextReady },
  );
  const [retrying, setRetrying] = useState(false);
  const [retryError, setRetryError] = useState<string | null>(null);

  useEffect(() => {
    if (detail.state.status !== "success" || !isActive(detail.state.data.status.state)) return;
    const timer = window.setTimeout(detail.retry, 1500);
    return () => window.clearTimeout(timer);
  }, [detail.retry, detail.state]);

  if (detail.state.status === "loading") return <LoadingState />;
  if (detail.state.status === "error") {
    return <ErrorState message={detail.state.message} onRetry={detail.retry} />;
  }

  const { status, progress } = detail.state.data;
  const taskContext = context.state.status === "success" ? context.state.data : null;
  const centerLabel =
    taskContext === null
      ? ""
      : [taskContext.subject.centerCode, taskContext.subject.centerName]
          .filter((item): item is string => item !== null && item.length > 0)
          .join("｜");

  async function retryFailedScope(): Promise<void> {
    setRetrying(true);
    setRetryError(null);
    try {
      await retryEvidenceJob(jobId);
      detail.retry();
    } catch {
      setRetryError("未能重新开始失败部分。已完成的资料不会丢失，请稍后再试。");
    } finally {
      setRetrying(false);
    }
  }

  return (
    <>
      {taskContext !== null && (
        <section className="persistent-task__context" aria-label="本次资料整理所属对象">
          <dl>
            <div className="persistent-task__context-project">
              <dt>项目</dt>
              <dd>
                {taskContext.project.projectName}
                <span> · {taskContext.project.studyPhaseLabel}</span>
              </dd>
            </div>
            <div>
              <dt>受试者</dt>
              <dd>
                {taskContext.subject.subjectCode}
                {centerLabel.length > 0 && <span> · {centerLabel}</span>}
              </dd>
            </div>
            <div>
              <dt>审核节点</dt>
              <dd>{taskContext.episode.stageLabel}</dd>
            </div>
            <div>
              <dt>方案版本</dt>
              <dd>{taskContext.project.officialVersion}</dd>
            </div>
          </dl>
        </section>
      )}
      <section className="tasks-section persistent-task" aria-labelledby="persistent-task-title">
      <div className="tasks-section__head">
        <div>
          <p className="persistent-task__eyebrow">本次资料整理</p>
          <h2 id="persistent-task-title" className="tasks-section__title">本次处理概况</h2>
        </div>
        <StatusBadge tone={stateTone(status.state)} text={status.stateLabel} />
      </div>

      <div className="persistent-task__summary">
        <div>
          <span>页面进度</span>
          <strong>{progress.completedPages} / {progress.totalPages}</strong>
        </div>
        <div>
          <span>等待处理</span>
          <strong>{progress.pendingPages}</strong>
        </div>
        <div className={progress.failedPages > 0 ? "persistent-task__metric--risk" : undefined}>
          <span>需要处理</span>
          <strong>{progress.failedPages}</strong>
        </div>
        <div>
          <span>最近更新</span>
          <strong>{formatTime(status.updatedAt)}</strong>
        </div>
      </div>

      <p className="persistent-task__recovery">
        <ResumeIcon size={14} />
        {status.recoveryAction}
      </p>
      {isActive(status.state) && (
        <p className="persistent-task__heartbeat" role="status" aria-live="polite">
          <span>{activeTaskFeedback(status.state)}最近状态更新：</span>
          <strong>{formatTime(status.updatedAt)}</strong>
        </p>
      )}

      <div className="persistent-task__grid">
        <section aria-labelledby="persistent-files-title">
          <h3 id="persistent-files-title" className="job-detail__subtitle">文件与页面</h3>
          {progress.files.length === 0 ? (
            <p className="tasks-section__note">{progress.scopeNote}</p>
          ) : (
            <ul className="persistent-task__files">
              {progress.files.map((file) => (
                <li key={file.sourceDocumentVersionId}>
                  <div>
                    <strong>{file.fileName}</strong>
                    <span>
                      已完成 {file.pageSucceeded} 页
                      {file.pageFailed > 0 ? ` · 需要处理 ${file.pageFailed} 页` : ""}
                      {file.pageTotal > file.pageSucceeded + file.pageFailed
                        ? ` · 等待 ${file.pageTotal - file.pageSucceeded - file.pageFailed} 页`
                        : ""}
                    </span>
                  </div>
                  <StatusBadge tone={file.pageFailed > 0 ? "danger" : stateTone(file.status)} text={file.statusLabel} />
                </li>
              ))}
            </ul>
          )}
          {progress.files.length > 0 && (
            <p className="persistent-task__scope">{progress.scopeNote}</p>
          )}
        </section>

        <section aria-labelledby="persistent-steps-title">
          <h3 id="persistent-steps-title" className="job-detail__subtitle">整理阶段</h3>
          <ol className="persistent-task__steps">
            {status.steps.map((step) => (
              <li key={step.stepId}>
                <span>{displayStepName(step.name)}</span>
                <StatusBadge tone={stateTone(step.state)} text={step.stateLabel} />
              </li>
            ))}
          </ol>
        </section>
      </div>

      <details className="persistent-task__history">
        <summary>查看处理记录（{status.events.length} 条）</summary>
        <ol className="job-timeline">
          {status.events.map((event) => (
            <li key={event.eventId} className="job-timeline__item">
              <span className="job-timeline__type">{event.eventTypeLabel}</span>
              <span className="job-timeline__time">{formatTime(event.occurredAt)}</span>
              {event.progressTotal > 0 && (
                <span className="job-timeline__meta">
                  已完成 {event.progressCompleted}/{event.progressTotal}
                </span>
              )}
            </li>
          ))}
        </ol>
      </details>

      {retryError !== null && <p className="evidence-notice evidence-notice--error" role="alert">{retryError}</p>}
      <div className="job-detail__actions">
        <button type="button" className="button" onClick={detail.retry}>刷新进度</button>
        {canRetry(status.state) && (
          <button
            type="button"
            className="button button--primary"
            disabled={retrying}
            onClick={() => void retryFailedScope()}
          >
            {retrying ? "正在重新开始…" : "重新处理失败部分"}
          </button>
        )}
        {subjectId !== null && reviewEpisodeId !== null && (
          <RouteLink
            to={`/subjects/${subjectId}/evidence`}
            params={{ episode: reviewEpisodeId }}
            className="button button--quiet"
            ariaLabel="返回该受试者资料"
          >
            <OpenIcon size={13} />
            返回该受试者资料
          </RouteLink>
        )}
      </div>
      </section>
    </>
  );
}
