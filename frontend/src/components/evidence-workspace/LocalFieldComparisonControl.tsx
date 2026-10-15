import { useEffect, useState } from "react";
import { ListChecks, RefreshCw, Square } from "lucide-react";
import { useLoad } from "../../app/useLoad";
import { actOnLocalVisualTask, getLocalFieldComparison, startLocalFieldComparison } from "../../api/evidence/localVisualHttp";

const pending = new Set(["queued", "running", "recovering", "cancel_requested"]);

export function LocalFieldComparisonControl({ revisionId, pageId, visualJobId, itemIndex }: {
  revisionId: string; pageId: string; visualJobId: string; itemIndex: number;
}) {
  const [jobId, setJobId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const detail = useLoad((signal) => getLocalFieldComparison(revisionId, pageId, visualJobId, itemIndex, signal, jobId),
    [revisionId, pageId, visualJobId, itemIndex, jobId]);
  const task = detail.state.status === "success" ? detail.state.data : null;
  const isPending = pending.has(task?.state ?? "");
  useEffect(() => {
    if (!isPending) return;
    const timer = window.setTimeout(detail.retry, 2000);
    return () => window.clearTimeout(timer);
  }, [isPending, detail.state, detail.retry]);
  async function act(action: "start" | "retry" | "cancel") {
    setBusy(true); setError(null);
    try {
      if (action === "start") setJobId(await startLocalFieldComparison(revisionId, pageId, visualJobId, itemIndex));
      else if (task?.jobId) await actOnLocalVisualTask(task.jobId, action);
      detail.retry();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "本次项目核对未完成。"); }
    finally { setBusy(false); }
  }
  return <div aria-label={`第${itemIndex + 1}项原文核对`}>
    {!task?.found || task.state === "cancelled" || (task.state === "failed_final" && !task.canRetry)
      ? <button type="button" className="button" disabled={busy || detail.state.status === "loading"}
      title="仅核对这一项的原文，不自动采用" onClick={() => void act("start")}><ListChecks aria-hidden="true" />
        {task?.state === "failed_final" ? "重新发起项目核对" : "核对这一项"}</button> : null}
    {isPending && <><span role="status">{task?.state === "cancel_requested" ? "正在停止核对" : "正在核对这一项"}</span>
      {task?.state !== "cancel_requested" && <button type="button" className="button" disabled={busy} title="停止项目核对"
        aria-label="停止项目核对" onClick={() => void act("cancel")}><Square aria-hidden="true" /></button>}</>}
    {task?.outcome && <details><summary>{task.outcome.agreement ? "原文核对一致，尚未采用" : "原文仍待核对，尚未采用"}</summary>
      <ul>{task.outcome.reasons.map((reason, index) => <li key={index}>{reason}</li>)}</ul></details>}
    {task?.failureMessage && <span role="alert">{task.failureMessage}</span>}
    {task?.canRetry && <button type="button" className="button" disabled={busy} title="仅重试未完成的区域"
      onClick={() => void act("retry")}><RefreshCw aria-hidden="true" />重试未完成的核对</button>}
    {(error || detail.state.status === "error") && <span role="alert">{error ?? (detail.state.status === "error" ? detail.state.message : "")}
      <button type="button" className="button" aria-label="重新查看项目核对" onClick={detail.retry}><RefreshCw aria-hidden="true" /></button></span>}
  </div>;
}
