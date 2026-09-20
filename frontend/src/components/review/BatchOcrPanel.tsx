import { useEffect, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, RefreshCw, ScanText, Square } from "lucide-react";
import { changeOcrBatch, ocrBatchLabels as labels, readOcrBatch, recentOcrBatches, startOcrBatch, type OcrBatch, type OcrBatchMember } from "../../api/evidence/reprocessingBatches";
import { useLoad } from "../../app/useLoad";
import { RouteLink, updateParams, useHashRoute } from "../../app/router";
import { ErrorState, LoadingState } from "../shell/Feedback";
import { reviewTime } from "./FrozenReviewReport";
import { BatchProcessingEstimate } from "./BatchProcessingEstimate";

const terminal = new Set(["completed", "cancelled", "failed_final"]);
const message = (cause: unknown) => cause instanceof Error ? cause.message : "暂时无法处理，请刷新后重试。原资料未改变。";
function Progress({ projectId, batchId }: { projectId: string; batchId: string }) {
  const [data, setData] = useState<OcrBatch | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [busy, setBusy] = useState(false);
  const operation = useRef<AbortController | null>(null);
  useEffect(() => () => operation.current?.abort(), []);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    let failures = 0;
    async function read() {
      try {
        const next = await readOcrBatch(projectId, batchId, controller.signal);
        if (controller.signal.aborted) return;
        setData(next); setError(null); failures = 0;
        if (!terminal.has(next.state) || next.items.some(item => item.jobId && !terminal.has(item.state))) timer = setTimeout(read, 4000);
      } catch (cause) {
        if (controller.signal.aborted) return;
        setError(message(cause)); if (++failures < 4) timer = setTimeout(read, failures * 4000);
      }
    }
    void read(); return () => { controller.abort(); clearTimeout(timer); };
  }, [projectId, batchId, refresh]);
  async function change(action: "cancel" | "retry") {
    if (busy) return;
    const controller = new AbortController(); operation.current = controller; setBusy(true);
    try { await changeOcrBatch(projectId, batchId, action, controller.signal); if (!controller.signal.aborted) setRefresh(value => value + 1); }
    catch (cause) { if (!controller.signal.aborted) setError(message(cause)); }
    finally { if (!controller.signal.aborted) setBusy(false); }
  }
  return <section className="prepared-review" aria-label="本批原件识别">
    <header className="prepared-review__head"><h2>本批原件识别</h2><div className="prepared-review__actions">
      <button className="icon-button" aria-label="刷新本批识别" title="刷新本批识别" onClick={() => setRefresh(value => value + 1)}><RefreshCw size={16} /></button>
      {(!data || !terminal.has(data.state)) && <button className="button" disabled={busy || data?.state === "cancel_requested"} onClick={() => void change("cancel")}><Square size={16} />停止本批</button>}
      {data?.state === "failed_final" && <button className="button" disabled={busy} onClick={() => void change("retry")}>重试未处理部分</button>}
    </div></header>
    {error && <p role="alert">{error}</p>}
    {!data ? <LoadingState /> : <><p>{data.state === "completed" ? "本批识别已结束，原报告未改变。"
      : data.state === "queued" && data.items.some(item => item.jobId && !terminal.has(item.state)) ? "正在识别所选资料" : labels[data.state]}</p>
      {data.failureDetail && <p role="alert">{data.failureDetail}</p>}
      <table className="reports-print__table"><thead><tr><th>受试者与节点</th><th>当前识别情况</th><th>本批结束记录</th><th>原件与结果</th></tr></thead>
        <tbody>{data.items.map(item => <tr key={item.episodeId}><th scope="row">{item.subjectCode}<p>{item.nodeLabel}</p></th><td>{labels[item.state]}</td><td>{item.recordedState ? labels[item.recordedState] : "尚未结束"}</td>
          <td><div className="prepared-review__actions">{item.jobId && <RouteLink to="/tasks" params={{ job: item.jobId, subject: item.subjectId, episode: item.episodeId }}>处理详情</RouteLink>}
            {item.newRevision && item.revisionId && <RouteLink to={`/subjects/${encodeURIComponent(item.subjectId)}/evidence`} params={{ episode: item.episodeId, ocrSnapshot: item.snapshotId, ocrRevision: item.revisionId }}>核对新识别结果</RouteLink>}
            {item.revisionId && !item.newRevision && <span>文字未变化</span>}</div></td></tr>)}</tbody>
      </table></>}
  </section>;
}

export function BatchOcrPanel({ projectId, choices, onBusy, disabled }: { projectId: string; choices: OcrBatchMember[]; onBusy: (value: boolean) => void; disabled: boolean }) {
  const { params } = useHashRoute();
  const batchId = params.get("ocrBatch");
  const [offset, setOffset] = useState(0);
  const recent = useLoad(signal => recentOcrBatches(projectId, offset, signal), [projectId, offset, batchId]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const operation = useRef<AbortController | null>(null);
  useEffect(() => () => operation.current?.abort(), []);
  async function start() {
    if (operation.current || disabled || !choices.length || choices.length > 50) return;
    const controller = new AbortController(); operation.current = controller; setBusy(true); onBusy(true); setError(null);
    try {
      const ordered = [...choices].sort((a, b) => a.episodeId.localeCompare(b.episodeId));
      const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(JSON.stringify(ordered)));
      const fingerprint = Array.from(new Uint8Array(digest), value => value.toString(16).padStart(2, "0")).join("");
      const storageKey = `pending-ocr-batch:${projectId}:${fingerprint}`;
      const key = localStorage.getItem(storageKey) || crypto.randomUUID();
      localStorage.setItem(storageKey, key);
      if (controller.signal.aborted) return;
      const id = await startOcrBatch(projectId, key, ordered, controller.signal);
      if (controller.signal.aborted) return;
      updateParams({ ocrBatch: id }); setOffset(0); localStorage.removeItem(storageKey);
    } catch (cause) { if (!controller.signal.aborted) setError(message(cause)); }
    finally { operation.current = null; if (!controller.signal.aborted) { setBusy(false); onBusy(false); } }
  }
  return <>
    <div className="prepared-review__actions"><button className="button" disabled={busy || disabled || !choices.length || choices.length > 50} onClick={() => void start()}>
      <ScanText size={16} />{busy ? "正在提交识别" : `重新识别所选原件${choices.length ? `（${choices.length}个节点）` : ""}`}</button>
      {error && <p role="alert">{error}</p>}</div>
    <BatchProcessingEstimate projectId={projectId} kind="ocr" choices={choices} />
    {recent.state.status === "error" && <ErrorState message={recent.state.message} onRetry={recent.retry} />}
    {recent.state.status === "success" && recent.state.data.offset === offset && <>
      <label>批量识别记录 <select value={batchId ?? ""} onChange={event => updateParams({ ocrBatch: event.target.value || null })}>
        <option value="">请选择</option>{batchId && !recent.state.data.items.some(item => item.jobId === batchId) && <option value={batchId}>当前查看的批次</option>}
        {recent.state.data.items.map(item => <option key={item.jobId} value={item.jobId}>{reviewTime(item.createdAt)} · {item.memberCount}个节点 · {labels[item.state]}</option>)}
      </select></label>{recent.state.data.unavailableCount > 0 && <p role="status">有{recent.state.data.unavailableCount}批记录暂时无法核实。</p>}
    </>}
    <div className="prepared-review__actions"><button className="icon-button" aria-label="上一页识别记录" title="上一页识别记录" disabled={!offset || recent.state.status === "loading"} onClick={() => setOffset(value => Math.max(0, value - 20))}><ArrowLeft size={16} /></button>
      <button className="icon-button" aria-label="下一页识别记录" title="下一页识别记录" disabled={recent.state.status !== "success" || recent.state.data.offset !== offset || !recent.state.data.hasMore || offset >= 100000} onClick={() => setOffset(value => value + 20)}><ArrowRight size={16} /></button></div>
    {batchId && <Progress key={`${projectId}:${batchId}`} projectId={projectId} batchId={batchId} />}
  </>;
}
