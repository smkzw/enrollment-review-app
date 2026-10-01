import { useEffect, useState } from "react";
import { Play, RefreshCw, ScanSearch, Square } from "lucide-react";
import { useLoad } from "../../app/useLoad";
import { actOnLocalVisualTask, getLocalVisualTask, startLocalVisualTask, type LocalVisualRegion } from "../../api/evidence/localVisualHttp";

const pending = new Set(["queued", "running", "recovering", "cancel_requested"]);
const labels: Record<string, string> = {
  queued: "等待读取", running: "正在读取所选区域", recovering: "正在恢复读取", cancel_requested: "正在停止读取",
  cancelled: "局部读取已停止", completed: "局部阅读已返回，尚未采用", failed_final: "局部读取未完成",
  failed_retryable: "局部读取未完成", waiting_user: "本次读取需要核对", needs_attention: "本次读取需要核对",
};

export function LocalVisualVerificationPanel({ revisionId, pageId, region, onLocateRegion }: {
  revisionId: string; pageId: string; region: LocalVisualRegion | null;
  onLocateRegion?: (region: LocalVisualRegion) => void;
}) {
  const [requestedJobId, setRequestedJobId] = useState<string | null>(null);
  const detail = useLoad((signal) => getLocalVisualTask(revisionId, pageId, signal, requestedJobId), [revisionId, pageId, requestedJobId]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (detail.state.status !== "success" || !pending.has(detail.state.data.state ?? "")) return;
    const timer = window.setTimeout(detail.retry, 2000);
    return () => window.clearTimeout(timer);
  }, [detail.state, detail.retry]);
  const task = detail.state.status === "success" ? detail.state.data : null;
  async function run(action: "start" | "retry" | "cancel" | "restart") {
    setBusy(true); setError(null);
    try {
      if (action === "start" && region) setRequestedJobId(await startLocalVisualTask(revisionId, pageId, region));
      else if (action === "restart" && task?.region) setRequestedJobId(await startLocalVisualTask(revisionId, pageId, task.region));
      else if ((action === "retry" || action === "cancel") && task?.jobId) await actOnLocalVisualTask(task.jobId, action);
      detail.retry();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "本次局部核实未完成。"); }
    finally { setBusy(false); }
  }
  return <section className="local-visual-verification" aria-label="原件局部核实">
    <div className="local-visual-verification__actions">
      <strong>原件局部核实</strong>
      {region && <button type="button" className="button" disabled={busy || pending.has(task?.state ?? "")}
        onClick={() => void run("start")}><Play aria-hidden="true" />核实所选区域</button>}
      {task?.found && <span role="status">{labels[task.state ?? ""]}</span>}
      {task?.region && onLocateRegion && <button type="button" className="button" onClick={() => onLocateRegion(task.region!)}>
        <ScanSearch aria-hidden="true" />定位本次核实区域</button>}
      {task?.jobId && task.canRetry && <button type="button" className="button" disabled={busy}
        onClick={() => void run("retry")}><RefreshCw aria-hidden="true" />重试本次读取</button>}
      {task?.region && (task.state === "cancelled" || (!task.configurationCurrent && !pending.has(task.state ?? ""))) && <button type="button" className="button" disabled={busy}
        onClick={() => void run("restart")}><Play aria-hidden="true" />{task.configurationCurrent ? "重新读取原区域" : "按当前配置读取原区域"}</button>}
      {task?.jobId && pending.has(task.state ?? "") && task.state !== "cancel_requested" && <button type="button" className="button" disabled={busy}
        onClick={() => void run("cancel")}><Square aria-hidden="true" />停止读取</button>}
    </div>
    {task?.text && <><p>仅核对圈选区域的可见文字，未改动病史或入排意见。{!task.configurationCurrent && "这份记录来自此前的读取配置。"}</p><pre>{task.text}</pre></>}
    {(error || detail.state.status === "error") && <div role="alert">{error ?? (detail.state.status === "error" ? detail.state.message : "")}
      <button type="button" className="button" onClick={detail.retry}><RefreshCw aria-hidden="true" />重新查看</button></div>}
  </section>;
}
