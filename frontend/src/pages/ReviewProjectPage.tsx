import { useState } from "react";
import { RefreshCw, Search } from "lucide-react";
import { getCatalogRepository } from "../api";
import { loadProjectEvidenceOverview } from "../api/catalog/projectEvidenceOverview";
import { updateParams, useHashRoute } from "../app/router";
import { useLoad } from "../app/useLoad";
import { EmptyState, ErrorState, LoadingState } from "../components/shell/Feedback";
import { BatchReviewPanel, type BatchChoice } from "../components/review/BatchReviewPanel";
import { ProjectReportCatalog } from "../components/review/ProjectReportCatalog";
import { BatchOcrPanel } from "../components/review/BatchOcrPanel";

function ProjectDirectory({ projectId }: { projectId: string }) {
  const data = useLoad((signal) => loadProjectEvidenceOverview(projectId, signal), [projectId]);
  const [query, setQuery] = useState("");
  const [nodeLabel, setNodeLabel] = useState("");
  const [readyOnly, setReadyOnly] = useState(false);
  const [selectedNodes, setSelectedNodes] = useState<Set<string>>(new Set());
  const [reviewSubmitting, setReviewSubmitting] = useState(false);
  const [ocrSubmitting, setOcrSubmitting] = useState(false);
  const submitting = reviewSubmitting || ocrSubmitting;
  if (data.state.status === "loading") return <LoadingState />;
  if (data.state.status === "error") return <ErrorState message={data.state.message} onRetry={data.retry} />;
  const all = data.state.data;
  const choices: BatchChoice[] = all.flatMap((subject) => subject.nodes.flatMap((node) =>
    selectedNodes.has(node.episodeId) && node.snapshotId !== null && node.processingId !== null
      ? [{ subjectId: subject.subjectId, episodeId: node.episodeId, snapshotId: node.snapshotId, processingId: node.processingId }] : []));
  const labels = [...new Set(all.flatMap((subject) => subject.nodes.map((node) => node.label)))];
  const needle = query.trim().toLocaleLowerCase();
  const visible = all.filter((subject) =>
    [subject.subjectCode, subject.centerCode ?? "", subject.centerName ?? ""].join(" ").toLocaleLowerCase().includes(needle),
  ).map((subject) => ({ ...subject, nodes: subject.nodes.filter((node) =>
    (!nodeLabel || node.label === nodeLabel) && (!readyOnly || node.processingId !== null),
  ) })).filter((subject) => subject.nodes.length > 0 || (!nodeLabel && !readyOnly));
  return <>
    <section className="reports-controls" aria-label="筛选项目资料">
      <label><span><Search size={16} aria-hidden="true" /> 受试者或中心</span>
        <input value={query} onChange={(event) => setQuery(event.target.value)} type="search" /></label>
      <label><span>审核节点</span><select value={nodeLabel} onChange={(event) => setNodeLabel(event.target.value)}>
        <option value="">全部节点</option>{labels.map((label) => <option key={label}>{label}</option>)}
      </select></label>
      <label><input type="checkbox" checked={readyOnly} onChange={(event) => setReadyOnly(event.target.checked)} />仅看已有整理资料</label>
      <button className="button" type="button" title="刷新项目资料" aria-label="刷新项目资料" disabled={submitting} onClick={() => { setSelectedNodes(new Set()); data.retry(); }}><RefreshCw size={16} aria-hidden="true" /></button>
    </section>
    <p>已登记 {all.length} 位受试者；当前显示 {visible.length} 位。</p>
    {!visible.length ? <EmptyState message={all.length ? "没有符合筛选条件的受试者" : "尚未登记受试者"} />
      : <table className="reports-print__table" aria-label="项目资料总览">
        <thead><tr><th scope="col">受试者</th><th scope="col">中心</th><th scope="col">审核节点与资料</th><th scope="col">审核记录</th></tr></thead>
        <tbody>{visible.map((subject) => <tr key={subject.subjectId}>
          <th scope="row"><a href={`#/subjects?${new URLSearchParams({ project: projectId, subject: subject.subjectId })}`}>{subject.subjectCode}</a></th>
          <td>{[subject.centerCode, subject.centerName].filter(Boolean).join(" · ") || "尚未填写"}</td>
          <td>{subject.nodes.length ? <ul>{subject.nodes.map((node) => <li key={node.episodeId}>
            <input type="checkbox" aria-label={`选择${subject.subjectCode}的${node.label}资料`}
              checked={selectedNodes.has(node.episodeId)} disabled={submitting || node.processingId === null ||
                (!selectedNodes.has(node.episodeId) && selectedNodes.size >= 50)}
              onChange={(event) => { const checked = event.target.checked; setSelectedNodes((previous) => {
                const next = new Set(previous); if (checked) next.add(node.episodeId); else next.delete(node.episodeId); return next;
              }); }} />{" "}
            <a href={`#/subjects/${encodeURIComponent(subject.subjectId)}/evidence?${new URLSearchParams({ episode: node.episodeId })}`}>{node.label}</a>
            {" · "}{node.processingId ? "已有整理资料" : "尚无已确认的整理资料"}
          </li>)}</ul> : "尚未建立节点"}</td>
          <td><a className="button" href={`#/reports?${new URLSearchParams({ project: projectId, subject: subject.subjectId })}`}>查看审核记录</a></td>
        </tr>)}</tbody>
      </table>}
    <BatchReviewPanel projectId={projectId} choices={choices} onBusy={setReviewSubmitting} disabled={ocrSubmitting} />
    <BatchOcrPanel projectId={projectId} choices={choices} onBusy={setOcrSubmitting} disabled={reviewSubmitting} />
    <ProjectReportCatalog projectId={projectId} />
  </>;
}

export default function ReviewProjectPage() {
  const { params } = useHashRoute();
  const projects = useLoad((signal) => getCatalogRepository().listProjects(signal), []);
  if (projects.state.status === "loading") return <LoadingState />;
  if (projects.state.status === "error") return <ErrorState message={projects.state.message} onRetry={projects.retry} />;
  const choices = projects.state.data;
  const selected = choices.find((project) => project.projectId === (params.get("project") ?? choices[0]?.projectId));
  return <div className="review-project catalog-page">
    <header className="page-head"><h1 className="page-head__title">项目看板</h1></header>
    {!choices.length ? <EmptyState message="尚无研究项目" /> : <>
      <section className="reports-controls"><label><span>研究项目</span>
        <select value={selected?.projectId ?? ""} onChange={(event) => updateParams({ project: event.target.value, subject: null, episode: null, batch: null, ocrBatch: null })}>
          {!selected && <option value="" disabled>请重新选择项目</option>}
          {choices.map((project) => <option key={project.projectId} value={project.projectId}>{project.projectName} · {project.studyPhaseLabel}</option>)}
        </select></label>
        {selected && <a className="button" href={`#/subjects?${new URLSearchParams({ project: selected.projectId })}`}>受试者与资料</a>}
      </section>
      {selected ? <ProjectDirectory key={selected.projectId} projectId={selected.projectId} /> : <EmptyState message="找不到所选项目，请重新选择。" />}
    </>}
  </div>;
}
