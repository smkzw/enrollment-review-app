import { ArrowLeft, ArrowRight, FileSearch, RefreshCw } from "lucide-react";
import { getCatalogRepository } from "../api";
import { listReviewActionWorklist, type WorklistMode } from "../api/review-history/reviewActionWorklistHttp";
import { useLoad } from "../app/useLoad";
import { updateParams, useHashRoute } from "../app/router";
import { EmptyState, ErrorState, LoadingState } from "../components/shell/Feedback";
import { reviewTime } from "../components/review/FrozenReviewReport";
import { actionStateLabel, actionTargetLabel, stageLabel, stageOrder } from "../domain/labels";

function ProjectWorklist({ projectId }: { projectId: string }) {
  const { params } = useHashRoute();
  const mode: WorklistMode = params.get("mode") === "all" ? "all" : "open";
  const dueStage = stageOrder.find((stage) => stage === params.get("dueStage")) ?? null;
  let previousCursors: string[] = [];
  try {
    const parsed: unknown = JSON.parse(params.get("cursors") ?? "[]");
    if (Array.isArray(parsed) && parsed.every((value) => typeof value === "string" && value.trim())) {
      previousCursors = parsed;
    }
  } catch { /* Invalid navigation state starts at the first page. */ }
  const cursors: Array<string | null> = [null, ...previousCursors];
  const setCursors = (values: Array<string | null>) => updateParams({
    project: projectId, cursors: values.length > 1 ? JSON.stringify(values.slice(1)) : null,
  });
  const cursor = cursors.at(-1) ?? null;
  const result = useLoad((signal) => listReviewActionWorklist(projectId, mode, cursor, signal, dueStage), [projectId, mode, cursor, dueStage]);
  const page = result.state.status === "success" ? result.state.data : null;
  return <>
    <section className="reports-controls kz-worklist-controls" aria-label="筛选办理事项">
      <label><span>办理情况</span><select value={mode} onChange={(event) => {
        updateParams({ project: projectId, mode: event.target.value, cursors: null });
      }}><option value="open">待办理</option><option value="all">全部记录</option></select></label>
      <label><span>应完成阶段</span><select value={dueStage ?? ""} onChange={(event) => {
        updateParams({ project: projectId, dueStage: event.target.value || null, cursors: null });
      }}><option value="">全部阶段</option>
        {stageOrder.map((stage) => <option key={stage} value={stage}>{stageLabel[stage]}</option>)}
      </select></label>
      <button type="button" className="button" onClick={result.retry} disabled={result.state.status === "loading"}>
        <RefreshCw size={16} aria-hidden="true" />刷新
      </button>
    </section>
    {result.state.status === "loading" ? <LoadingState />
      : result.state.status === "error" ? <ErrorState message={result.state.message} onRetry={result.retry} />
      : page && <>
        {page.items.length === 0 ? <EmptyState message="本页暂无办理事项"
          hint={mode === "open" ? "已保存的审核记录中，本页没有待办理事项。" : "本页尚无已保存的办理记录。"} />
          : <table className="reports-print__table kz-worklist-table" aria-label="项目办理事项">
            <colgroup><col /><col /><col /><col /><col /></colgroup>
            <thead><tr><th scope="col">受试者及节点</th><th scope="col">需要办理的事项</th>
              <th scope="col">负责方</th><th scope="col">办理情况</th><th scope="col">原审核记录</th></tr></thead>
            <tbody>{page.items.map((item) => {
              const source = item.action.clause?.ruleDisplayCode ?? item.action.control?.displayLabel;
              const params = new URLSearchParams({ project: projectId, subject: item.subjectId,
                episode: item.reviewEpisodeId, run: item.reviewRunId, action: item.action.actionId });
              const worklist = new URLSearchParams({ project: projectId, mode });
              if (dueStage) worklist.set("dueStage", dueStage);
              if (previousCursors.length) worklist.set("cursors", JSON.stringify(previousCursors));
              params.set("worklist", worklist.toString());
              return <tr key={item.action.actionId}>
                <th scope="row">{item.subjectCode}<small>{item.workflowStageLabel}</small></th>
                <td><strong>{source}</strong><p>{item.action.requestedAction}</p>
                  <small>所需资料：{item.action.acceptableEvidence}</small></td>
                <td>{actionTargetLabel[item.action.targetParty]}<small>应完成阶段：{stageLabel[item.action.dueStage]}</small></td>
                <td>{actionStateLabel[item.action.state]}</td>
                <td><p>{reviewTime(item.completedAt ?? item.startedAt)}</p>
                  {item.completedAt === null && <small>该次审核尚未完成</small>}
                  <a className="button" href={`#/reports?${params}`}><FileSearch size={16} aria-hidden="true" />查看并办理</a></td>
              </tr>;
            })}</tbody>
          </table>}
        <nav className="reports-controls kz-worklist-pagination" aria-label="办理事项翻页">
          <button type="button" className="button" disabled={cursors.length === 1}
            onClick={() => setCursors(cursors.slice(0, -1))}><ArrowLeft size={16} aria-hidden="true" />上一页</button>
          <span>第 {cursors.length} 页 · 本页 {page.items.length} 项</span>
          <button type="button" className="button" disabled={page.nextAfterActionId === null}
            onClick={() => { if (page.nextAfterActionId !== null) setCursors([...cursors, page.nextAfterActionId]); }}>
            下一页<ArrowRight size={16} aria-hidden="true" /></button>
        </nav>
      </>}
  </>;
}

export default function ReviewActionsPage() {
  const { params } = useHashRoute();
  const projects = useLoad((signal) => getCatalogRepository().listProjects(signal), []);
  if (projects.state.status === "loading") return <LoadingState />;
  if (projects.state.status === "error") return <ErrorState message={projects.state.message} onRetry={projects.retry} />;
  const choices = projects.state.data;
  if (!choices.length) return <EmptyState message="尚无研究项目" hint="请先导入研究方案并建立项目。" />;
  const projectId = params.get("project") ?? choices[0].projectId;
  const selected = choices.find((item) => item.projectId === projectId);
  return <div className="reports kz-worklist">
    <header className="page-head"><h1 className="page-head__title">待办事项</h1></header>
    <section className="reports-controls reports-controls--run" aria-label="选择研究项目"><label><span>研究项目</span>
      <select value={selected?.projectId ?? ""} onChange={(event) => updateParams({ project: event.target.value, cursors: null })}>
        {!selected && <option value="" disabled>请重新选择项目</option>}
        {choices.map((item) => <option key={item.projectId} value={item.projectId}>{item.projectName}</option>)}
      </select></label></section>
    {selected ? <ProjectWorklist key={projectId} projectId={projectId} />
      : <EmptyState message="未找到所选项目" hint="请从项目列表重新选择。" />}
  </div>;
}
