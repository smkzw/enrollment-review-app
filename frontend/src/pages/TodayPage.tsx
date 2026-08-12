/**
 * 今日工作（合同 §3.1 首屏候选之一）：到期行动、明确障碍、存在冲突、
 * 资料整理任务与近期变化；每项提供直达审核节点入口。
 * 所有状态词来自 domain/labels.ts 固定映射，不展示实现词。
 */

import { getDefaultRepository } from "../api";
import { RouteLink } from "../app/router";
import { useLoad } from "../app/useLoad";
import { EmptyState, ErrorState, LoadingState } from "../components/shell/Feedback";
import { BlockingBadge, MainStatusBadge, TaskStateBadge } from "../components/shell/StatusBadge";
import { OpenIcon } from "../components/shell/icons";
import { stageOrder, UI_PHRASES } from "../domain/labels";
import type { ActionView, EpisodeSummaryView, JobView, TodayChangeView } from "../domain/viewModels";
import type { EpisodeCountsView } from "../domain/viewModels";

/** 待处理事项预览行数上限：优先展示阻断事项，其余引导至行动中心（视觉缺陷 4） */
const DUE_ACTIONS_PREVIEW = 6;

/** 六类分类计数的紧凑展示（只显示非零项） */
function CountsLine({ counts }: { counts: EpisodeCountsView }) {
  const items = [
    [counts.barrier, "明确障碍"],
    [counts.currentGap, "当前节点缺口"],
    [counts.conflict, "存在冲突"],
    [counts.professionalJudgment, "需专业判断"],
    [counts.provenanceFollowup, "溯源待办"],
    [counts.futureAttention, "后续节点关注"],
  ] as const;
  const visible = items.filter(([count]) => count > 0);
  if (visible.length === 0) {
    return <span className="today-row__meta">无缺口</span>;
  }
  return (
    <span className="today-row__meta">
      {visible.map(([count, label]) => (
        <span key={label} className="count-chip" title={label}>
          {label} {count}
        </span>
      ))}
    </span>
  );
}

function DueActionRow({ action }: { action: ActionView }) {
  return (
    <li className="today-row">
      <div className="today-row__codes">
        <span className="today-row__subject">{action.subjectCode}</span>
        <span className="today-row__stage">{action.dueStageLabel}</span>
      </div>
      <BlockingBadge level={action.blockingLevel} />
      <div className="today-row__main">
        <p className="today-row__text">{action.requestedAction}</p>
        <p className="today-row__meta">
          关联规则：{action.displayCode} · 缺口：{action.gapLabel} · 责任方：
          {action.targetPartyLabel}
        </p>
      </div>
      <RouteLink
        to="/workbench"
        params={{ episode: action.episodeId, component: action.ruleComponentId }}
        className="button button--quiet today-row__action"
        ariaLabel={`打开 ${action.subjectCode} ${action.dueStageLabel}审核`}
        title={`打开 ${action.subjectCode} ${action.dueStageLabel}审核`}
      >
        <OpenIcon size={14} />
        打开审核
      </RouteLink>
    </li>
  );
}

function EpisodeRow({ episode }: { episode: EpisodeSummaryView }) {
  return (
    <li className="today-row">
      <div className="today-row__codes">
        <span className="today-row__subject">{episode.subjectCode}</span>
        <span className="today-row__stage">{episode.stageLabel}</span>
      </div>
      <MainStatusBadge status={episode.mainStatus} />
      <div className="today-row__main">
        <CountsLine counts={episode.counts} />
      </div>
      <RouteLink
        to="/workbench"
        params={{
          episode: episode.episodeId,
          component: episode.focusComponentId,
        }}
        className="button button--quiet today-row__action"
        ariaLabel={`打开 ${episode.subjectCode} ${episode.stageLabel}审核`}
        title={`打开 ${episode.subjectCode} ${episode.stageLabel}审核`}
      >
        <OpenIcon size={14} />
        打开审核
      </RouteLink>
    </li>
  );
}

function JobRow({ job }: { job: JobView }) {
  const active =
    job.state === "queued" ||
    job.state === "running" ||
    job.state === "failed" ||
    job.state === "resumable" ||
    job.state === "partial";
  return (
    <li className="today-row">
      <div className="today-row__codes">
        <span className="today-row__subject">{job.subjectCode}</span>
        <span className="today-row__stage">{job.stageLabel}</span>
      </div>
      <TaskStateBadge state={job.state} />
      <div className="today-row__main">
        <p className="today-row__meta">
          已整理 {job.progressCompleted} / {job.progressTotal} 项资料
        </p>
      </div>
      {active ? (
        <RouteLink
          to="/tasks"
          params={{ job: job.jobId }}
          className="button button--quiet today-row__action"
          ariaLabel={`继续 ${job.subjectCode} ${job.stageLabel}资料整理`}
        >
          继续
        </RouteLink>
      ) : (
        <span className="today-row__action-placeholder" />
      )}
    </li>
  );
}

function ChangeRow({ change }: { change: TodayChangeView }) {
  const protocol = change.kind === "protocol_change";
  return (
    <li className="today-row">
      <div className="today-row__codes">
        <span className="today-row__stage">
          {protocol ? "方案变化" : "资料变化"}
        </span>
      </div>
      <div className="today-row__main">
        <p className="today-row__text">{change.title}</p>
        <p className="today-row__meta">{change.detail}</p>
      </div>
      {protocol ? (
        <RouteLink
          to="/protocols"
          className="button button--quiet today-row__action"
          ariaLabel="打开方案工作台查看差异"
        >
          查看方案
        </RouteLink>
      ) : (
        <span className="today-row__action-placeholder" />
      )}
    </li>
  );
}

export function TodayPage() {
  const today = useLoad(() => getDefaultRepository().getTodayWork(), []);
  const jobs = useLoad(() => getDefaultRepository().getJobs(), []);

  if (today.state.status === "loading" || jobs.state.status === "loading") {
    return <LoadingState />;
  }
  if (today.state.status === "error") {
    return <ErrorState message={today.state.message} onRetry={today.retry} />;
  }
  if (jobs.state.status === "error") {
    return <ErrorState message={jobs.state.message} onRetry={jobs.retry} />;
  }

  const { dueActions, barriers, conflicts, recentChanges } = today.state.data;
  const allJobs = [...jobs.state.data].sort((a, b) => {
    const rank = (job: JobView) =>
      job.state === "completed" || job.state === "cancelled" ? 1 : 0;
    return (
      rank(a) - rank(b) ||
      a.subjectCode.localeCompare(b.subjectCode, "zh") ||
      a.stage.localeCompare(b.stage, "zh")
    );
  });
  // 预览按优先级排序（显示层）：阻断优先 → 受试者代号 → 到期节点顺序 → 行动编号。
  // 只改变展示顺序，不改动底层行动集合（视觉缺陷 4）。
  const stageRank = (action: ActionView) =>
    stageOrder.indexOf(action.dueStage);
  const preview = [...dueActions]
    .sort(
      (a, b) =>
        (a.blockingLevel === "blocking" ? 0 : 1) -
          (b.blockingLevel === "blocking" ? 0 : 1) ||
        a.subjectCode.localeCompare(b.subjectCode, "zh") ||
        stageRank(a) - stageRank(b) ||
        a.actionId.localeCompare(b.actionId, "zh"),
    )
    .slice(0, DUE_ACTIONS_PREVIEW);
  const hiddenCount = dueActions.length - preview.length;

  return (
    <div className="today">
      <header className="page-head">
        <h1 className="page-head__title">今日工作</h1>
        <p className="page-head__note">{UI_PHRASES.prototypeOnly}：展示合成示例数据，不代表真实审核已经完成。</p>
      </header>

      <section className="today-section" aria-labelledby="today-due-title">
        <div className="today-section__head">
          <h2 id="today-due-title" className="today-section__title">
            待处理事项
          </h2>
          <span className="section-count">{dueActions.length}</span>
        </div>
        {dueActions.length === 0 ? (
          <EmptyState message={UI_PHRASES.noTodos} hint="当前审核节点没有到期行动。" />
        ) : (
          <>
            <ul className="today-list">
              {preview.map((action) => (
                <DueActionRow key={action.actionId} action={action} />
              ))}
            </ul>
            {hiddenCount > 0 && (
              <p className="today-section__more">
                共 {dueActions.length} 项，其余请在
                <RouteLink to="/actions" ariaLabel="打开行动中心">
                  行动中心
                </RouteLink>
                查看。
              </p>
            )}
          </>
        )}
      </section>

      <div className="today-grid">
        <section className="today-section" aria-labelledby="today-barrier-title">
          <div className="today-section__head">
            <h2 id="today-barrier-title" className="today-section__title">
              明确障碍
            </h2>
            <span className="section-count">{barriers.length}</span>
          </div>
          {barriers.length === 0 ? (
            <EmptyState message="当前没有明确障碍的对象。" />
          ) : (
            <ul className="today-list">
              {barriers.map((episode) => (
                <EpisodeRow key={episode.episodeId} episode={episode} />
              ))}
            </ul>
          )}
        </section>

        <section className="today-section" aria-labelledby="today-conflict-title">
          <div className="today-section__head">
            <h2 id="today-conflict-title" className="today-section__title">
              存在冲突
            </h2>
            <span className="section-count">{conflicts.length}</span>
          </div>
          {conflicts.length === 0 ? (
            <EmptyState message="当前没有来源冲突的对象。" />
          ) : (
            <ul className="today-list">
              {conflicts.map((episode) => (
                <EpisodeRow key={episode.episodeId} episode={episode} />
              ))}
            </ul>
          )}
        </section>

        <section className="today-section" aria-labelledby="today-jobs-title">
          <div className="today-section__head">
            <h2 id="today-jobs-title" className="today-section__title">
              资料整理任务
            </h2>
            <span className="section-count">{allJobs.length}</span>
          </div>
          {allJobs.length === 0 ? (
            <EmptyState message={UI_PHRASES.noTodos} />
          ) : (
            <ul className="today-list">
              {allJobs.map((job) => (
                <JobRow key={job.jobId} job={job} />
              ))}
            </ul>
          )}
        </section>

        <section className="today-section" aria-labelledby="today-change-title">
          <div className="today-section__head">
            <h2 id="today-change-title" className="today-section__title">
              近期变化
            </h2>
            <span className="section-count">{recentChanges.length}</span>
          </div>
          {recentChanges.length === 0 ? (
            <EmptyState message="当前没有需要留意的变化。" />
          ) : (
            <ul className="today-list">
              {recentChanges.map((change, index) => (
                <ChangeRow
                  key={`${change.kind}-${change.title}-${index}`}
                  change={change}
                />
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}

export default TodayPage;
