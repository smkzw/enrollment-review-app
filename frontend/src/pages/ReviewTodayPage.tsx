import { FileSearch, RefreshCw } from "lucide-react";
import { getCatalogRepository } from "../api";
import { listRecentProjectReviews, listReviewActionWorklist } from "../api/review-history/reviewActionWorklistHttp";
import { updateParams, useHashRoute } from "../app/router";
import { useLoad } from "../app/useLoad";
import { EmptyState, ErrorState, LoadingState } from "../components/shell/Feedback";
import { reviewTime } from "../components/review/FrozenReviewReport";
import { actionTargetLabel, stageLabel } from "../domain/labels";

function reportLink(project: string, subject: string, episode: string, run: string, action?: string) {
  const params = new URLSearchParams({ project, subject, episode, run });
  if (action) params.set("action", action);
  return `#/reports?${params}`;
}

function ProjectPreview({ projectId }: { projectId: string }) {
  const actions = useLoad((signal) => listReviewActionWorklist(projectId, "open", null, signal, null, 6), [projectId]);
  const reviews = useLoad((signal) => listRecentProjectReviews(projectId, signal), [projectId]);
  const projectParams = new URLSearchParams({ project: projectId });
  return <>
    <section className="today-section" aria-labelledby="review-today-actions">
      <div className="today-section__head"><h2 id="review-today-actions" className="today-section__title">待办理事项</h2>
        <a className="button" href={`#/actions?${projectParams}`}>查看全部待办</a>
        <button type="button" className="button" aria-label="刷新待办理事项" title="刷新待办理事项"
          disabled={actions.state.status === "loading"} onClick={actions.retry}><RefreshCw size={16} aria-hidden="true" /></button>
      </div>
      {actions.state.status === "loading" ? <LoadingState />
        : actions.state.status === "error" ? <ErrorState message={actions.state.message} onRetry={actions.retry} />
          : actions.state.data.items.length === 0 ? <EmptyState message="已保存的审核记录中暂无待办理事项" />
            : <>
              <table className="reports-print__table review-today__actions" aria-label="待办理事项预览">
                <colgroup><col /><col /><col /><col /></colgroup>
                <thead><tr><th scope="col">受试者及节点</th><th scope="col">办理事项</th><th scope="col">负责方及阶段</th><th scope="col">原审核记录</th></tr></thead>
                <tbody>{actions.state.data.items.map((item) => <tr key={item.action.actionId}>
                  <th scope="row">{item.subjectCode}<p>{item.workflowStageLabel}</p></th>
                  <td><strong>{item.action.clause?.ruleDisplayCode ?? item.action.control?.displayLabel}</strong><p>{item.action.requestedAction}</p></td>
                  <td>{actionTargetLabel[item.action.targetParty]}<p>{stageLabel[item.action.dueStage]}</p></td>
                  <td><a className="button" href={reportLink(projectId, item.subjectId, item.reviewEpisodeId, item.reviewRunId, item.action.actionId)}>
                    <FileSearch size={16} aria-hidden="true" />查看并办理</a></td>
                </tr>)}</tbody>
              </table>
              {actions.state.data.nextAfterActionId !== null && <p className="today-section__more">还有待办理事项，请查看全部待办。</p>}
            </>}
    </section>
    <section className="today-section" aria-labelledby="review-today-recent">
      <div className="today-section__head"><h2 id="review-today-recent" className="today-section__title">近期审核记录</h2>
        <a className="button" href={`#/reports?${projectParams}`}>查看审核记录</a>
        <button type="button" className="button" aria-label="刷新近期审核记录" title="刷新近期审核记录"
          disabled={reviews.state.status === "loading"} onClick={reviews.retry}><RefreshCw size={16} aria-hidden="true" /></button>
      </div>
      {reviews.state.status === "loading" ? <LoadingState />
        : reviews.state.status === "error" ? <ErrorState message={reviews.state.message} onRetry={reviews.retry} />
          : reviews.state.data.items.length === 0 ? <EmptyState message="尚无已保存的审核记录" />
            : <table className="reports-print__table review-today__recent" aria-label="近期审核记录">
              <colgroup><col /><col /><col /><col /><col /></colgroup>
              <thead><tr><th scope="col">受试者</th><th scope="col">审核节点</th><th scope="col">开始时间</th><th scope="col">保存情况</th><th scope="col">原审核记录</th></tr></thead>
              <tbody>{reviews.state.data.items.map((item) => <tr key={item.reviewRunId}>
                <th scope="row">{item.subjectCode}</th><td>{item.workflowStageLabel}</td><td>{reviewTime(item.startedAt)}</td>
                <td>{item.completedAt === null ? "尚未完成保存" : "审核记录已保存"}</td>
                <td><a className="button" href={reportLink(projectId, item.subjectId, item.reviewEpisodeId, item.reviewRunId)}>
                  <FileSearch size={16} aria-hidden="true" />查看记录</a></td>
              </tr>)}</tbody>
            </table>}
    </section>
  </>;
}

export default function ReviewTodayPage() {
  const { params } = useHashRoute();
  const projects = useLoad((signal) => getCatalogRepository().listProjects(signal), []);
  if (projects.state.status === "loading") return <LoadingState />;
  if (projects.state.status === "error") return <ErrorState message={projects.state.message} onRetry={projects.retry} />;
  const choices = projects.state.data;
  const projectId = params.get("project") ?? choices[0]?.projectId;
  const selected = choices.find((item) => item.projectId === projectId);
  return <div className="today review-today">
    <header className="page-head"><h1 className="page-head__title">今日工作</h1></header>
    {!choices.length ? <><EmptyState message="尚无研究项目" />
      <a className="button button--primary" href="#/protocols">导入研究方案</a></>
      : <>
        <section className="reports-controls" aria-label="选择研究项目"><label><span>研究项目</span>
          <select value={selected?.projectId ?? ""} onChange={(event) => updateParams({ project: event.target.value })}>
            {!selected && <option value="" disabled>请重新选择项目</option>}
            {choices.map((item) => <option key={item.projectId} value={item.projectId}>{item.projectName}</option>)}
          </select></label>
          {selected && <a className="button" href={`#/subjects?${new URLSearchParams({ project: selected.projectId })}`}>受试者与资料</a>}
        </section>
        {selected ? <ProjectPreview key={selected.projectId} projectId={selected.projectId} />
          : <EmptyState message="未找到所选项目，请重新选择。" />}
      </>}
  </div>;
}
