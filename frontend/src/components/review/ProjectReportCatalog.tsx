import { useEffect, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, Download, Search, X } from "lucide-react";
import { loadProjectReports, type ProjectReportEntry, type ReportCursor } from "../../api/review-history/projectReportCatalog";
import { createReviewHistoryHttp } from "../../api/review-history/reviewHistoryHttp";
import type { ReviewHistoryRunDetailView } from "../../api/review-history/reviewHistoryTypes";
import { useLoad } from "../../app/useLoad";
import { frozenReviewCollectionExport } from "../../domain/frozenReviewExport";
import { EmptyState, ErrorState, LoadingState } from "../shell/Feedback";
import { reviewTime } from "./FrozenReviewReport";

const history = createReviewHistoryHttp();

function CatalogPage({ projectId, center, before, selected, busy, onSelect, onNext, onPrevious }: {
  projectId: string; center: string; before: ReportCursor | null; selected: Map<string, ProjectReportEntry>;
  busy: boolean; onSelect: (entry: ProjectReportEntry, checked: boolean) => void;
  onNext: (cursor: ReportCursor) => void; onPrevious?: () => void;
}) {
  const data = useLoad((signal) => loadProjectReports(projectId, center, before, signal), [projectId, center, before]);
  if (data.state.status === "loading") return <LoadingState />;
  if (data.state.status === "error") return <ErrorState message={data.state.message} onRetry={data.retry} />;
  const page = data.state.data;
  return <>
    {!page.items.length ? <EmptyState message="此范围内暂无已保存报告" /> : <table className="reports-print__table" aria-label="已保存报告目录">
      <thead><tr><th scope="col">选择</th><th scope="col">受试者</th><th scope="col">中心</th><th scope="col">审核节点</th><th scope="col">审核完成时间</th><th scope="col">方案版本</th><th scope="col">报告</th></tr></thead>
      <tbody>{page.items.map((entry) => <tr key={entry.runId}>
        <td><input type="checkbox" aria-label={`选择${entry.subjectCode}的${entry.nodeLabel}、${reviewTime(entry.completedAt)}报告`}
          checked={selected.has(entry.runId)} disabled={busy || (!selected.has(entry.runId) && selected.size >= 50)}
          onChange={(event) => onSelect(entry, event.target.checked)} /></td>
        <th scope="row">{entry.subjectCode}</th><td>{[entry.centerCode, entry.centerName].filter(Boolean).join(" · ") || "未登记"}</td>
        <td>{entry.nodeLabel}</td><td>{reviewTime(entry.completedAt)}</td><td>{entry.protocolVersion}</td>
        <td><a href={`#/reports?${new URLSearchParams({ project: projectId, subject: entry.subjectId, episode: entry.episodeId, run: entry.runId })}`}>查看报告</a></td>
      </tr>)}</tbody>
    </table>}
    <nav className="reports-controls" aria-label="报告目录翻页">
      <button className="button" type="button" title="上一页" aria-label="上一页" disabled={!onPrevious || busy} onClick={onPrevious}><ArrowLeft size={16} /></button>
      <button className="button" type="button" title="下一页" aria-label="下一页" disabled={!page.nextCursor || busy} onClick={() => { if (page.nextCursor) onNext(page.nextCursor); }}><ArrowRight size={16} /></button>
    </nav>
  </>;
}

function ReportSelection({ projectId, center }: { projectId: string; center: string }) {
  const [cursors, setCursors] = useState<(ReportCursor | null)[]>([null]);
  const [selected, setSelected] = useState<Map<string, ProjectReportEntry>>(new Map());
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  const before = cursors[cursors.length - 1];
  const busy = progress !== null;
  async function exportSelection(format: "html" | "md") {
    if (controller.current || !selected.size) return;
    const request = new AbortController(); controller.current = request;
    setProgress(0); setError(null);
    try {
      const reports: ReviewHistoryRunDetailView[] = [];
      for (const entry of selected.values()) {
        const report = await history.getRun(entry.subjectId, entry.episodeId, entry.runId, { signal: request.signal });
        if (request.signal.aborted) return;
        if (report.context.projectId !== projectId || report.context.centerCode !== entry.centerCode ||
          report.context.subjectCode !== entry.subjectCode || report.context.officialProtocolVersion !== entry.protocolVersion ||
          report.run.completedAt !== entry.completedAt || report.context.workflowStageLabel !== entry.nodeLabel) {
          throw new Error("所选报告与目录不一致");
        }
        reports.push(report); setProgress(reports.length);
      }
      const content = frozenReviewCollectionExport(reports, format);
      if (request.signal.aborted) return;
      const url = URL.createObjectURL(new Blob([content], { type: format === "html" ? "text/html;charset=utf-8" : "text/markdown;charset=utf-8" }));
      const link = document.createElement("a");
      try {
        link.href = url; link.download = `入排审核报告汇集-${new Date().toISOString().slice(0, 10)}.${format}`;
        document.body.append(link); link.click();
      } finally { link.remove(); window.setTimeout(() => URL.revokeObjectURL(url), 1000); }
    } catch {
      if (!request.signal.aborted) setError("部分报告未能完整读取，本次未生成汇集文件。请重新查看所选报告后再试。");
    } finally {
      if (!request.signal.aborted) setProgress(null);
      if (controller.current === request) controller.current = null;
    }
  }
  return <>
    <div className="reports-controls">
      <span aria-live="polite">{busy ? `正在读取所选报告：${progress}/${selected.size}` : `已选 ${selected.size} 份报告（最多五十份）`}</span>
      <button type="button" className="button" disabled={!selected.size || busy} onClick={() => void exportSelection("html")}><Download size={16} />导出网页报告</button>
      <button type="button" className="button" disabled={!selected.size || busy} onClick={() => void exportSelection("md")}><Download size={16} />导出文字报告</button>
      <button type="button" className="button" title="清空选择" aria-label="清空选择" disabled={!selected.size || busy} onClick={() => setSelected(new Map())}><X size={16} /></button>
    </div>
    {error && <p role="alert">{error}</p>}
    {selected.size > 0 && <details><summary>已选报告</summary><ul>{[...selected.values()].map((entry) => <li key={entry.runId}>
      {entry.subjectCode} · {entry.nodeLabel} · {reviewTime(entry.completedAt)}{" "}
      <button type="button" className="button" title="移除此报告" aria-label={`移除${entry.subjectCode}的所选报告`} disabled={busy} onClick={() => setSelected((previous) => { const next = new Map(previous); next.delete(entry.runId); return next; })}><X size={14} /></button>
    </li>)}</ul></details>}
    <CatalogPage key={before ? `${before.completedAt}:${before.runId}` : "first"}
      projectId={projectId} center={center} before={before} selected={selected} busy={busy}
      onSelect={(entry, checked) => setSelected((previous) => { const next = new Map(previous); if (checked) next.set(entry.runId, entry); else next.delete(entry.runId); return next; })}
      onNext={(cursor) => setCursors((previous) => [...previous, cursor])}
      onPrevious={cursors.length > 1 ? () => setCursors((previous) => previous.slice(0, -1)) : undefined} />
  </>;
}

export function ProjectReportCatalog({ projectId }: { projectId: string }) {
  const [draft, setDraft] = useState("");
  const [center, setCenter] = useState("");
  return <section aria-label="报告汇集">
    <h2>报告汇集</h2>
    <form className="reports-controls" onSubmit={(event) => { event.preventDefault(); setCenter(draft.trim()); }}>
      <label><span>中心编号</span><input value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="全部中心" /></label>
      <button className="button" type="submit" title="筛选报告" aria-label="筛选报告"><Search size={16} /></button>
    </form>
    <ReportSelection key={`${projectId}:${center}`} projectId={projectId} center={center} />
  </section>;
}
