/**
 * 任务与系统：查看已保存的资料处理记录和具体任务进度。
 * - 记录列表沿用当前可用的资料处理仓储；正式模式由具体任务链接进入详情。
 * - URL 契约：/tasks?job=<JobId>。
 */

import { getDefaultRepository } from "../api";
import { RouteLink, updateParams, useHashRoute } from "../app/router";
import { isInterfaceTrialMode } from "../app/runtimeMode";
import { useLoad } from "../app/useLoad";
import { EmptyState, ErrorState, LoadingState } from "../components/shell/Feedback";
import { PersistentEvidenceTaskDetail } from "../components/evidence-workspace/PersistentEvidenceTaskDetail";
import { TaskStateBadge } from "../components/shell/StatusBadge";
import { OpenIcon, ResumeIcon } from "../components/shell/icons";
import type { JobView } from "../domain/viewModels";

function formatTime(iso: string): string {
  return iso.length >= 16 ? `${iso.slice(0, 10)} ${iso.slice(11, 16)}` : iso;
}

function PersistentTaskRoute({
  jobId,
  subjectId,
  reviewEpisodeId,
}: {
  jobId: string;
  subjectId: string | null;
  reviewEpisodeId: string | null;
}) {
  return (
    <div className="tasks">
      <header className="page-head">
        <h1 className="page-head__title">资料处理详情</h1>
        <p className="page-head__note">查看已确认资料的处理进度、需要处理的页面和恢复方式。</p>
      </header>
      <PersistentEvidenceTaskDetail
        jobId={jobId}
        subjectId={subjectId}
        reviewEpisodeId={reviewEpisodeId}
      />
      <section className="tasks-section" aria-labelledby="persistent-task-help-title">
        <h2 id="persistent-task-help-title" className="tasks-section__title">
          遇到问题怎么办
        </h2>
        <p className="tasks-section__note">
          单页处理失败不会删除已完成内容。请先核对失败文件和页数，再重新处理失败部分；
          若原文件无法打开，请返回受试者资料页补充可读取的原文件。
        </p>
      </section>
    </div>
  );
}

function FormalTaskEmptyState() {
  return (
    <div className="tasks">
      <header className="page-head">
        <h1 className="page-head__title">任务与系统</h1>
        <p className="page-head__note">从受试者资料页打开具体任务后，可查看处理进度。</p>
      </header>
      <section className="tasks-section">
        <p className="tasks-section__note">当前没有选中需要查看的资料处理任务。</p>
        <RouteLink to="/subjects" className="button button--primary">
          返回受试者与资料
        </RouteLink>
      </section>
    </div>
  );
}

function TrialTasksPage() {
  const { params } = useHashRoute();
  const jobParam = params.get("job");
  const jobs = useLoad(() => getDefaultRepository().getJobs(), []);

  if (jobs.state.status === "loading") return <LoadingState />;
  if (jobs.state.status === "error") {
    return <ErrorState message={jobs.state.message} onRetry={jobs.retry} />;
  }

  const allJobs = [...jobs.state.data].sort(
    (a, b) =>
      a.subjectCode.localeCompare(b.subjectCode, "zh") ||
      a.stage.localeCompare(b.stage, "zh"),
  );
  const selectedJob =
    jobParam === null
      ? null
      : allJobs.find((job) => job.jobId === jobParam) ?? null;
  const persistentJobId = jobParam !== null && selectedJob === null ? jobParam : null;
  const subjectId = params.get("subject");
  const reviewEpisodeId = params.get("episode");

  if (persistentJobId !== null) {
    return (
      <PersistentTaskRoute
        jobId={persistentJobId}
        subjectId={subjectId}
        reviewEpisodeId={reviewEpisodeId}
      />
    );
  }

  return (
    <div className="tasks">
      <header className="page-head">
        <h1 className="page-head__title">任务与系统</h1>
        <p className="page-head__note">查看已保存的资料处理记录和恢复入口。</p>
      </header>
      <section className="tasks-section" aria-labelledby="tasks-real-title">
        <div className="tasks-section__head">
          <h2 id="tasks-real-title" className="tasks-section__title">
            资料处理记录
          </h2>
          <span className="section-count">{allJobs.length}</span>
        </div>
        <p className="tasks-section__note">数据来源：当前已接入的资料处理记录。</p>
        {allJobs.length === 0 ? (
          <EmptyState message="当前没有资料处理记录。" />
        ) : (
          <ul className="today-list">
            {allJobs.map((job) => (
              <li key={job.jobId}>
                <button
                  type="button"
                  className={`today-row task-row${selectedJob?.jobId === job.jobId ? " task-row--selected" : ""}`}
                  aria-pressed={selectedJob?.jobId === job.jobId}
                  onClick={() => updateParams({ job: job.jobId })}
                >
                  <span className="today-row__codes">
                    <span className="today-row__subject">{job.subjectCode}</span>
                    <span className="today-row__stage">{job.stageLabel}</span>
                  </span>
                  <TaskStateBadge state={job.state} />
                  <span className="today-row__main">
                    <span className="today-row__meta">
                      已整理 {job.progressCompleted} / {job.progressTotal} 项资料
                    </span>
                  </span>
                  <span className="today-row__action">查看</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
      {selectedJob !== null && <JobDetail job={selectedJob} />}
      <section className="tasks-section" aria-labelledby="tasks-help-title">
        <h2 id="tasks-help-title" className="tasks-section__title">
          遇到问题怎么办
        </h2>
        <p className="tasks-section__note">
          资料暂时打不开时，已保存的进度不会丢失。请稍后再试；如果仍无法打开，
          请记录页面上的事项编号并联系系统支持人员。
        </p>
      </section>
    </div>
  );
}

export function TasksPage() {
  const { params } = useHashRoute();
  const jobId = params.get("job");
  if (jobId !== null && !isInterfaceTrialMode()) {
    return (
      <PersistentTaskRoute
        jobId={jobId}
        subjectId={params.get("subject")}
        reviewEpisodeId={params.get("episode")}
      />
    );
  }
  if (!isInterfaceTrialMode()) return <FormalTaskEmptyState />;
  return <TrialTasksPage />;
}

function JobDetail({ job }: { job: JobView }) {
  const completed = job.state === "completed" || job.state === "cancelled";
  return (
    <section className="tasks-section" aria-labelledby="job-detail-title">
      <div className="tasks-section__head">
        <h2 id="job-detail-title" className="tasks-section__title">
          任务详情：{job.subjectCode} {job.stageLabel}
        </h2>
        <TaskStateBadge state={job.state} />
      </div>
      <div className="job-detail">
        <p className="job-detail__progress">
          进度：已整理 {job.progressCompleted} / {job.progressTotal} 项资料
        </p>
        {job.checkpointId !== null && (
          <p className="job-detail__checkpoint">
            <ResumeIcon size={13} />
            已保存目前进度，可随时继续。
          </p>
        )}
        <h3 className="job-detail__subtitle">处理记录</h3>
        <ol className="job-timeline">
          {job.events.map((event) => (
            <li key={event.jobEventId} className="job-timeline__item">
              <span className="job-timeline__type">{event.eventTypeLabel}</span>
              <span className="job-timeline__time">{formatTime(event.occurredAt)}</span>
              <span className="job-timeline__meta">
                第 {event.attempt} 次尝试 · 已整理 {event.progressCompleted}/
                {event.progressTotal}
                {event.retryable ? " · 可重试" : ""}
              </span>
            </li>
          ))}
        </ol>
        <div className="job-detail__actions">
          {completed ? (
            <>
              <span className="job-detail__note">
                已完成部分保留在资料版本中；重新开始不会覆盖历史结果。
              </span>
              <RouteLink
                to="/workbench"
                params={{ episode: job.reviewEpisodeId }}
                className="button button--quiet"
                ariaLabel={`查看 ${job.subjectCode} 的审核结果`}
              >
                <OpenIcon size={13} />
                查看审核结果
              </RouteLink>
            </>
          ) : (
            <span className="job-detail__note">
              请从当前任务详情继续处理未完成的资料。
            </span>
          )}
        </div>
      </div>
    </section>
  );
}

export default TasksPage;
