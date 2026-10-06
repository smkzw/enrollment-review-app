import { Fragment, useEffect, useState } from "react";
import { FilePenLine, Play, RefreshCw, ScanSearch, Square } from "lucide-react";
import { useLoad } from "../../app/useLoad";
import { LocalFieldComparisonControl } from "./LocalFieldComparisonControl";
import { actOnLocalVisualTask, getLocalVisualTask, localVisualItemRegion, startLocalVisualTask, type LocalVisualRegion } from "../../api/evidence/localVisualHttp";

const pending = new Set(["queued", "running", "recovering", "cancel_requested"]);
const labels: Record<string, string> = {
  queued: "等待读取", running: "正在读取所选区域", recovering: "正在恢复读取", cancel_requested: "正在停止读取",
  cancelled: "局部读取已停止", completed: "局部阅读已返回，尚未采用", failed_final: "局部读取未完成",
  failed_retryable: "局部读取未完成", waiting_user: "本次读取需要核对", needs_attention: "本次读取需要核对",
};

export interface LocalVisualExcerpt {
  revisionId: string;
  pageId: string;
  jobId: string;
  itemIndex: number;
  excerpt: string;
}

export function LocalVisualVerificationPanel({ revisionId, pageId, region, onLocateRegion, onPrepareCorrection }: {
  revisionId: string; pageId: string; region: LocalVisualRegion | null;
  onLocateRegion?: (region: LocalVisualRegion) => void;
  onPrepareCorrection?: (excerpt: LocalVisualExcerpt) => void;
}) {
  const [requestedJobId, setRequestedJobId] = useState<string | null>(null);
  const detail = useLoad((signal) => getLocalVisualTask(revisionId, pageId, signal, requestedJobId), [revisionId, pageId, requestedJobId]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [includeContext, setIncludeContext] = useState(false);
  const [readFormat, setReadFormat] = useState<NonNullable<LocalVisualRegion["read_format"]>>("transcript");
  const [resultOpen, setResultOpen] = useState(false);
  useEffect(() => setIncludeContext(region?.include_context ?? false), [region]);
  useEffect(() => setReadFormat(region?.read_format ?? "transcript"), [region]);
  useEffect(() => {
    if (detail.state.status !== "success" || !pending.has(detail.state.data.state ?? "")) return;
    const timer = window.setTimeout(detail.retry, 2000);
    return () => window.clearTimeout(timer);
  }, [detail.state, detail.retry]);
  const task = detail.state.status === "success" ? detail.state.data : null;
  useEffect(() => setResultOpen(false), [task?.jobId]);
  function locate(box: LocalVisualRegion) {
    setResultOpen(false);
    onLocateRegion?.(box);
  }
  const previousSelection = Boolean(region && task?.region && (
    region.x0 !== task.region.x0 || region.y0 !== task.region.y0
    || region.x1 !== task.region.x1 || region.y1 !== task.region.y1
    || region.clockwise_degrees !== task.region.clockwise_degrees
  ));
  async function run(action: "start" | "retry" | "cancel" | "restart") {
    setBusy(true); setError(null);
    try {
      if (action === "start" && region) {
        const { include_context: _previousContext, ...selected } = region;
        if (readFormat === "transcript") delete selected.read_format;
        else selected.read_format = readFormat;
        setRequestedJobId(await startLocalVisualTask(revisionId, pageId,
          includeContext ? { ...selected, include_context: true } : selected));
      }
      else if (action === "restart" && task?.region) setRequestedJobId(await startLocalVisualTask(revisionId, pageId, task.region));
      else if ((action === "retry" || action === "cancel") && task?.jobId) await actOnLocalVisualTask(task.jobId, action);
      detail.retry();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "本次局部核实未完成。"); }
    finally { setBusy(false); }
  }
  return <section className="local-visual-verification" aria-label="原件局部核实">
    <div className="local-visual-verification__actions">
      <strong>原件局部核实</strong>
      {region && <select aria-label="局部读取方式" value={readFormat} disabled={busy || pending.has(task?.state ?? "")}
        onChange={(event) => setReadFormat(event.target.value as NonNullable<LocalVisualRegion["read_format"]>)}>
        <option value="transcript">原文摘录</option><option value="structured_candidate">逐项摘录</option><option value="localized_candidate">逐项核对</option>
      </select>}
      {region && <label className="local-visual-verification__context"><input type="checkbox" checked={includeContext}
        disabled={busy || pending.has(task?.state ?? "")} onChange={(event) => setIncludeContext(event.target.checked)} />保留周边作参考</label>}
      {region && <button type="button" className="button" disabled={busy || pending.has(task?.state ?? "")}
        onClick={() => void run("start")}><Play aria-hidden="true" />核实所选区域</button>}
      {task?.found && <span role="status">{previousSelection && "此前区域："}{labels[task.state ?? ""]}</span>}
      {task?.region && onLocateRegion && <button type="button" className="button" onClick={() => locate(task.region!)}>
        <ScanSearch aria-hidden="true" />{previousSelection ? "定位此前核实区域" : "定位本次核实区域"}</button>}
      {task?.jobId && task.canRetry && <button type="button" className="button" disabled={busy}
        onClick={() => void run("retry")}><RefreshCw aria-hidden="true" />{previousSelection ? "重试此前区域" : "重试本次读取"}</button>}
      {task?.region && (task.state === "cancelled" || (!task.configurationCurrent && !pending.has(task.state ?? ""))) && <button type="button" className="button" disabled={busy}
        onClick={() => void run("restart")}><Play aria-hidden="true" />{task.configurationCurrent
          ? (previousSelection ? "重新读取此前区域" : "重新读取原区域")
          : (previousSelection ? "按当前配置读取此前区域" : "按当前配置读取原区域")}</button>}
      {task?.jobId && pending.has(task.state ?? "") && task.state !== "cancel_requested" && <button type="button" className="button" disabled={busy}
        onClick={() => void run("cancel")}><Square aria-hidden="true" />停止读取</button>}
    </div>
    {task?.failureMessage && <p role="alert">{task.failureMessage}</p>}
    {task?.text && <details className="local-visual-verification__result" open={resultOpen}
      onToggle={(event) => setResultOpen(event.currentTarget.open)}>
      <summary>{previousSelection ? "查看此前区域的读取结果（尚未采用）" : "查看本次读取结果（尚未采用）"}</summary>
      <p>局部读取内容尚未采用，未改动病史或入排意见。{!task.configurationCurrent && "这份记录来自此前的读取配置。"}</p>
      {task.structuredRead ? <>
        <div className="local-visual-verification__fields"><table aria-label="待核实的局部读取项目">
          <thead><tr><th>项目</th><th>原文摘录</th><th>待核事项</th><th>原件</th></tr></thead>
          <tbody>{task.structuredRead.items.map((item, index) => {
            const proposed = localVisualItemRegion(task, item);
            const notes = [
              item.legibility !== "clear" ? "有裁切或字迹不清" : null,
              item.script !== "printed" && !item.annotation_target ? "批注对应的项目不明" : null,
              item.proposed_bbox && !proposed ? "所指范围超出本次圈选，位置待核" : null,
            ].filter(Boolean);
            const canCompare = proposed && notes.length === 0 && task.jobId && task.configurationCurrent
              && task.region?.read_format === "localized_candidate";
            return <Fragment key={index}><tr>
              <th scope="row">{item.label || "未注明项目"}{item.time_label && <small>{item.time_label}</small>}</th>
              <td>{item.excerpt}<small>{item.position}</small></td>
              <td>{notes.length ? notes.join("；") : "尚未采用"}</td>
              <td>{proposed && onLocateRegion ? <button type="button" className="button"
                aria-label={`查看第${index + 1}项${item.label || "内容"}所指原件区域`}
                title="查看所指区域，位置仍需核对" onClick={() => locate(proposed)}>
                <ScanSearch aria-hidden="true" /></button> : "位置待核"}
                {onPrepareCorrection && task.jobId && proposed && notes.length === 0
                  && task.state === "completed" && task.configurationCurrent && (
                  <button type="button" className="button"
                    aria-label={`将第${index + 1}项${item.label || "内容"}转到文字校对`}
                    title="转到文字校对，尚未保存或采用"
                    onClick={() => {
                      onPrepareCorrection({ revisionId, pageId,
                        jobId: task.jobId!, itemIndex: index, excerpt: item.excerpt });
                      locate(proposed);
                    }}>
                    <FilePenLine aria-hidden="true" />
                  </button>
                )}
              </td>
            </tr>{canCompare && <tr><td colSpan={4}><LocalFieldComparisonControl
              key={`${revisionId}:${pageId}:${task.jobId}:${index}`} revisionId={revisionId} pageId={pageId}
              visualJobId={task.jobId!} itemIndex={index} /></td></tr>}</Fragment>;
          })}</tbody>
        </table></div>
        {task.structuredRead.unresolved.length > 0 && <ul>{task.structuredRead.unresolved.map((item, index) => <li key={index}>{item}</li>)}</ul>}
      </> : <pre>{task.text}</pre>}
    </details>}
    {(error || detail.state.status === "error") && <div role="alert">{error ?? (detail.state.status === "error" ? detail.state.message : "")}
      <button type="button" className="button" onClick={detail.retry}><RefreshCw aria-hidden="true" />重新查看</button></div>}
  </section>;
}
