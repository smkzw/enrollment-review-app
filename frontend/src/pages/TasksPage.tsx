/**
 * 任务与系统（合同 §3.1/§8）：资料整理任务的进度、事件时间线与恢复路径。
 * - 真实任务来自 fixture（已完成/有失败重试历史）；状态词全部为合同固定中文。
 * - 准备、运行、部分失败、暂停、可继续、结果需复核、取消等边界由处理状态试用区展示，
 *   明确说明不会实际运行文字识别或审核（UAT-P1-12 语义）。
 * - URL 契约：/tasks?job=<JobId>。
 */

import { getDefaultRepository } from "../api";
import { RouteLink, updateParams, useHashRoute } from "../app/router";
import { useLoad } from "../app/useLoad";
import { useSessionState } from "../app/useSessionState";
import { EmptyState, ErrorState, LoadingState } from "../components/shell/Feedback";
import { TaskStateBadge } from "../components/shell/StatusBadge";
import { OpenIcon, ResumeIcon, RunningIcon, StaleIcon } from "../components/shell/icons";
import { UI_PHRASES } from "../domain/labels";
import type { TaskState } from "../domain/enums";
import type { JobView } from "../domain/viewModels";

function formatTime(iso: string): string {
  // fixture 时间为 UTC 示例时间；只做机械格式化，不解析为临床日期
  return iso.length >= 16 ? `${iso.slice(0, 10)} ${iso.slice(11, 16)}` : iso;
}

/** 处理状态试用区的整理总数 */
export const DEMO_TOTAL = 3;

interface DemoTaskProgress {
  state: TaskState;
  fileStates: Record<DemoFileId, DemoFileState>;
}

type DemoFileId = "screening" | "laboratory" | "medication";
type DemoFileState = "completed" | "pending" | "failed";

const DEMO_FILES: ReadonlyArray<{ id: DemoFileId; name: string }> = [
  { id: "screening", name: "筛选病历.pdf" },
  { id: "laboratory", name: "实验室检查.pdf" },
  { id: "medication", name: "既往用药记录.pdf" },
];

const INITIAL_DEMO_PROGRESS: DemoTaskProgress = {
  state: "partial",
  fileStates: {
    screening: "completed",
    laboratory: "pending",
    medication: "failed",
  },
};

const TASK_STATES: ReadonlyArray<TaskState> = [
  "queued", "running", "partial", "failed", "resumable", "cancelled", "stale", "completed",
];

function parseDemoTaskProgress(value: unknown): DemoTaskProgress | null {
  if (typeof value !== "object" || value === null) return null;
  const candidate = value as Record<string, unknown>;
  const files = candidate.fileStates;
  if (!TASK_STATES.includes(candidate.state as TaskState) || typeof files !== "object" || files === null) {
    return null;
  }
  const states = files as Record<string, unknown>;
  const valid = (item: unknown): item is DemoFileState =>
    item === "completed" || item === "pending" || item === "failed";
  if (!valid(states.screening) || !valid(states.laboratory) || !valid(states.medication)) {
    return null;
  }
  const progress: DemoTaskProgress = {
    state: candidate.state as TaskState,
    fileStates: {
      screening: states.screening,
      laboratory: states.laboratory,
      medication: states.medication,
    },
  };
  return isDemoTaskProgressConsistent(progress) ? progress : null;
}

function completedCount(fileStates: DemoTaskProgress["fileStates"]): number {
  return Object.values(fileStates).filter((state) => state === "completed").length;
}

function isDemoTaskProgressConsistent(progress: DemoTaskProgress): boolean {
  const states = Object.values(progress.fileStates);
  const allCompleted = states.every((state) => state === "completed");
  const allPending = states.every((state) => state === "pending");
  const hasFailed = states.some((state) => state === "failed");

  switch (progress.state) {
    case "queued":
      return allPending;
    case "running":
      return !allCompleted;
    case "partial":
    case "failed":
      return !allCompleted && hasFailed;
    case "resumable":
    case "cancelled":
      return !allCompleted;
    case "stale":
      return !allPending;
    case "completed":
      return allCompleted;
  }
}

function withCompletedCount(
  current: DemoTaskProgress["fileStates"],
  target: number,
): DemoTaskProgress["fileStates"] {
  const next = { ...current };
  if (target <= 0) {
    for (const file of DEMO_FILES) next[file.id] = "pending";
    return next;
  }
  let completed = completedCount(next);
  for (const file of DEMO_FILES) {
    if (completed >= target) break;
    if (next[file.id] !== "completed") {
      next[file.id] = "completed";
      completed += 1;
    }
  }
  return next;
}

function markNextIncompleteFailed(
  current: DemoTaskProgress["fileStates"],
): DemoTaskProgress["fileStates"] {
  const next = { ...current };
  const target = DEMO_FILES.find((file) => next[file.id] === "pending");
  if (target !== undefined) next[target.id] = "failed";
  return next;
}

function demoFileStateLabel(state: DemoFileState): string {
  if (state === "completed") return "已完成，继续时不会重复";
  if (state === "failed") return "上次处理失败，可稍后再试";
  return "尚未处理";
}

export function TasksPage() {
  const { params } = useHashRoute();
  const jobParam = params.get("job");

  const jobs = useLoad(() => getDefaultRepository().getJobs(), []);

  // ---- 处理状态试用：本地状态机覆盖 8 个任务状态边界 ----
  const [demoProgressState, setDemoProgressState, resetDemoProgress] =
    useSessionState<DemoTaskProgress>(
      "eligibility-review:uat:task-progress",
      INITIAL_DEMO_PROGRESS,
      parseDemoTaskProgress,
    );
  const demoState = demoProgressState.state;
  const demoProgress = completedCount(demoProgressState.fileStates);

  const advanceDemo = (next: TaskState, progress?: number) => {
    setDemoProgressState((current) => ({
      state: next,
      fileStates:
        next === "failed" || next === "partial"
          ? markNextIncompleteFailed(current.fileStates)
          : progress === undefined
            ? current.fileStates
            : withCompletedCount(current.fileStates, progress),
    }));
  };

  if (jobs.state.status === "loading") {
    return <LoadingState />;
  }
  if (jobs.state.status === "error") {
    return <ErrorState message={jobs.state.message} onRetry={jobs.retry} />;
  }

  const allJobs = [...jobs.state.data].sort(
    (a, b) =>
      a.subjectCode.localeCompare(b.subjectCode, "zh") ||
      a.stage.localeCompare(b.stage, "zh"),
  );
  const selectedJob =
    jobParam !== null
      ? allJobs.find((job) => job.jobId === jobParam) ?? null
      : null;

  return (
    <div className="tasks">
      <header className="page-head">
        <h1 className="page-head__title">任务与系统</h1>
        <p className="page-head__note">
          {UI_PHRASES.prototypeOnly}：下方可体验不同处理状态；这些操作不会实际整理资料或启动审核。
        </p>
      </header>

      <section className="tasks-section" aria-labelledby="tasks-demo-title">
        <div className="tasks-section__head">
          <h2 id="tasks-demo-title" className="tasks-section__title">
            继续未完成事项
          </h2>
          <span className="section-count">8 种状态</span>
        </div>
        <p className="tasks-section__note">
          以下演示覆盖准备中、正在整理、部分资料尚未处理、处理失败可重试、已保存进度可继续、
          已取消、资料发生变化需重新核对与已完成八种状态；仅用于查看操作反馈，
          <strong>不会实际运行文字识别或审核</strong>。
        </p>
        <div className="demo-job">
          <div className="demo-job__head">
            <span className="demo-job__subject">试用受试者</span>
            <span className="demo-job__stage">筛选期</span>
            <TaskStateBadge state={demoState} />
            <span className="demo-job__progress">
              已整理 {demoProgress} / {DEMO_TOTAL} 项资料
            </span>
          </div>
          <p className="demo-job__desc">{demoStateDescription(demoState)}</p>
          <ul className="demo-job__files" aria-label="资料处理范围">
            {DEMO_FILES.map((file) => (
              <li key={file.id}>
                <span>{file.name}</span>
                <strong>{demoFileStateLabel(demoProgressState.fileStates[file.id])}</strong>
              </li>
            ))}
          </ul>
          <div className="demo-job__actions">
            {demoActions(
              demoState,
              demoProgress,
              DEMO_TOTAL,
              advanceDemo,
              <RouteLink
                to="/workbench"
                params={{ episode: "episode-uat-03-screening-gap_conflict" }}
                className="button button--quiet"
                ariaLabel="查看差异对应的审核节点"
              >
                <OpenIcon size={13} />
                查看差异
              </RouteLink>,
            )}
          </div>
          <button type="button" className="button button--quiet" onClick={resetDemoProgress}>
            恢复试用初始状态
          </button>
        </div>
      </section>

      <section className="tasks-section" aria-labelledby="tasks-real-title">
        <div className="tasks-section__head">
          <h2 id="tasks-real-title" className="tasks-section__title">
            资料整理记录
          </h2>
          <span className="section-count">{allJobs.length}</span>
        </div>
        {allJobs.length === 0 ? (
          <EmptyState message={UI_PHRASES.noTodos} />
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
          资料暂时打不开时：已保存的进度不会丢失。请稍后再试；如果仍无法打开，
          请记录页面上的事项编号并联系系统支持人员。
        </p>
      </section>
    </div>
  );
}

/** 任务详情：进度、状态、事件时间线；恢复操作为本次界面试用。 */
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
                已完成部分保留在资料快照中；重新开始不会覆盖历史结果。
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
              本次恢复操作只用于查看界面反馈，不会实际继续处理资料。
            </span>
          )}
        </div>
      </div>
    </section>
  );
}

function demoStateDescription(state: TaskState): string {
  switch (state) {
    case "queued":
      return "任务已建立，等待开始整理资料。";
    case "running":
      return "正在逐项整理资料；进度会实时显示。";
    case "partial":
      return "有资料处理失败或尚未处理；可继续未完成部分。";
    case "failed":
      return "一项资料整理失败；可以稍后再试，已保存的进度不丢失。";
    case "resumable":
      return "已保存目前进度；可继续处理或取消未完成部分。";
    case "cancelled":
      return "已停止这次处理，已完成部分仍保留。";
    case "stale":
      return "资料发生变化，当前结果需要重新核对。";
    case "completed":
      return "全部资料整理完成。";
  }
}

function demoActions(
  state: TaskState,
  progress: number,
  total: number,
  advance: (next: TaskState, progress?: number) => void,
  diffLink: React.ReactNode,
): React.ReactNode {
  switch (state) {
    case "queued":
      return (
        <button
          type="button"
          className="button button--primary"
          onClick={() => advance("running", 0)}
        >
          <RunningIcon size={14} />
          开始整理
        </button>
      );
    case "running":
      return (
        <>
          {progress < total ? (
            <button
              type="button"
              className="button"
              onClick={() =>
                progress === total - 1
                  ? advance("completed", total)
                  : advance("running", progress + 1)
              }
            >
              完成一项资料
            </button>
          ) : (
            <button
              type="button"
              className="button"
              onClick={() => advance("completed", total)}
            >
              完成全部
            </button>
          )}
          <button
            type="button"
            className="button"
            onClick={() => advance("partial", progress)}
          >
            部分资料失败
          </button>
          <button
            type="button"
            className="button"
            onClick={() => advance("failed", progress)}
          >
            一项资料失败
          </button>
          <button
            type="button"
            className="button"
            onClick={() => advance("resumable", progress)}
          >
            <ResumeIcon size={14} />
            暂停
          </button>
        </>
      );
    case "partial":
      return (
        <>
          <button
            type="button"
            className="button button--primary"
            onClick={() => advance("running", progress)}
          >
            继续
          </button>
          <button
            type="button"
            className="button"
            onClick={() => advance("cancelled", progress)}
          >
            取消本次操作
          </button>
        </>
      );
    case "failed":
      return (
        <>
          <button
            type="button"
            className="button button--primary"
            onClick={() => advance("running", progress)}
          >
            稍后再试
          </button>
          <button
            type="button"
            className="button"
            onClick={() => advance("stale", progress)}
          >
            <StaleIcon size={14} />
            资料发生变化
          </button>
        </>
      );
    case "resumable":
      return (
        <>
          <button
            type="button"
            className="button button--primary"
            onClick={() => advance("running", progress)}
          >
            继续
          </button>
          <button
            type="button"
            className="button"
            onClick={() => advance("cancelled", progress)}
          >
            取消
          </button>
        </>
      );
    case "cancelled":
      return (
        <>
          <span className="job-detail__note">
            已完成部分仍保留在资料快照中，不会被删除。
          </span>
          <button
            type="button"
            className="button"
            onClick={() => advance("queued", 0)}
          >
            重新开始
          </button>
        </>
      );
    case "stale":
      return (
        <>
          {diffLink}
          <button
            type="button"
            className="button button--primary"
            onClick={() => advance("running", 0)}
          >
            开始新的整理
          </button>
        </>
      );
    case "completed":
      return (
        <span className="job-detail__note">
          全部整理完成；重新开始会建立新的整理记录，历史结果保留。
        </span>
      );
  }
}

export default TasksPage;
