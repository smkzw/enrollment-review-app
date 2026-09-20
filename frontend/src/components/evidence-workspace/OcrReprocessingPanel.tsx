import { useEffect, useRef, useState } from "react";
import { RefreshCw, ScanText } from "lucide-react";
import { readReprocessing, reprocessingTerminal, startReprocessing, type ReprocessingScope, type ReprocessingView } from "../../api/evidence/reprocessing";
import { RouteLink } from "../../app/router";
import { retryEvidenceJob } from "../../api/evidence/evidenceJobHttp";

const labels: Record<string, string> = { queued: "等待识别", running: "正在识别", recovering: "正在恢复识别", cancel_requested: "正在停止", failed_retryable: "正在等待重试", failed_final: "识别未完成", cancelled: "已停止识别", completed: "识别已完成，原报告未改变" };
interface Saved { key: string; jobId: string | null }
export function OcrReprocessingPanel({ scope, onView, blocked = false }: { scope: ReprocessingScope; onView: (revisionId: string) => void; blocked?: boolean }) {
  const storageKey = `ocr-reprocessing:${JSON.stringify(scope)}`;
  const [saved, setSaved] = useState<Saved | null>(() => {
    try {
      const item = JSON.parse(localStorage.getItem(storageKey) ?? "null") as Saved | null;
      return item && typeof item.key === "string" && item.key && (item.jobId === null || typeof item.jobId === "string") ? item : null;
    } catch { return null; }
  });
  const [view, setView] = useState<ReprocessingView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => request.current?.abort(), []);
  useEffect(() => {
    if (!saved?.jobId) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    let failures = 0;
    async function poll() {
      try {
        const result = await readReprocessing(scope, saved!.jobId!, controller.signal);
        if (controller.signal.aborted) return;
        setView(result); setError(null); failures = 0;
        if (!reprocessingTerminal.has(result.state)) timer = setTimeout(poll, 3000);
      } catch (cause) {
        if (controller.signal.aborted) return;
        setError(cause instanceof Error ? cause.message : "暂时无法读取识别进度，原资料未改变。");
        if (++failures < 4) timer = setTimeout(poll, 5000);
      }
    }
    void poll();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [saved?.jobId, refresh, storageKey]);
  async function start() {
    if (busy || blocked) return;
    setBusy(true); setError(null);
    const controller = new AbortController(); request.current = controller;
    try {
      const next: Saved = saved && saved.jobId === null ? saved : { key: crypto.randomUUID(), jobId: null };
      localStorage.setItem(storageKey, JSON.stringify(next)); setSaved(next); setView(null);
      const jobId = await startReprocessing(scope, next.key, controller.signal);
      if (controller.signal.aborted) return;
      const accepted = { ...next, jobId };
      localStorage.setItem(storageKey, JSON.stringify(accepted)); setSaved(accepted);
    } catch (cause) {
      if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "未能确认是否已开始，请重试同一次操作。");
    } finally { if (!controller.signal.aborted) setBusy(false); }
  }
  async function retry() {
    if (busy || !saved?.jobId) return;
    setBusy(true); setError(null);
    const controller = new AbortController(); request.current = controller;
    try {
      await retryEvidenceJob(saved.jobId, (input, init) => fetch(input, { ...init, signal: controller.signal }));
      if (!controller.signal.aborted) { setView(null); setRefresh(value => value + 1); }
    } catch (cause) {
      if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "暂未恢复识别，请刷新处理详情。");
    } finally { if (!controller.signal.aborted) setBusy(false); }
  }
  return <section className="tasks-section persistent-task" aria-label="重新识别原件">
    <div className="tasks-section__head"><h2 className="tasks-section__title">原件识别</h2>
      {view && <span role="status">{labels[view.state]}</span>}
    </div>
    {error && <p className="evidence-notice evidence-notice--error" role="alert">{error}</p>}
    <div className="job-detail__actions">
      {view?.state === "failed_final" && <button type="button" className="button button--primary" disabled={busy} onClick={() => void retry()}>重试未完成的识别</button>}
      {(!saved?.jobId || (view && reprocessingTerminal.has(view.state))) && <button type="button" className="button" disabled={busy || blocked} title={blocked ? "请先完成当前资料核对" : undefined} onClick={() => void start()}>
        <ScanText size={16} aria-hidden="true" />{busy ? "正在提交…" : saved?.jobId === null ? "确认本次识别" : "重新识别原件"}
      </button>}
      {saved?.jobId && <><button type="button" className="button" title="刷新识别进度" aria-label="刷新识别进度" onClick={() => setRefresh(value => value + 1)}><RefreshCw size={16} /></button>
        <RouteLink to="/tasks" params={{ job: saved.jobId, subject: scope.subjectId, episode: scope.episodeId }}>查看处理详情</RouteLink></>}
      {view?.revisionId && view.newRevision && <button type="button" className="button button--primary" onClick={() => onView(view.revisionId!)}>核对新识别结果</button>}
      {view?.revisionId && !view.newRevision && <span>原件文字未变化，无需启用新版本。</span>}
    </div>
  </section>;
}
