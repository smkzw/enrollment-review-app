import { useEffect, useState } from "react";
import { Play, RefreshCw, TriangleAlert } from "lucide-react";
import type { CatalogEpisodeView } from "../../api/catalog/catalogTypes";

interface Props {
  episode: CatalogEpisodeView;
  onCompleted?: (runId: string) => void;
}
interface Job { job_id: string; state: string; review_run_id: string | null }

export function WorkDraftPanel({ episode, onCompleted }: Props) {
  const [job, setJob] = useState<Job | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const anchorKey = episode.stage === "baseline" ? "baseline_date" : "screening_date";
  const storedAnchor = episode.anchorDates[anchorKey] as { value?: string } | undefined;
  const [nodeDate, setNodeDate] = useState(storedAnchor?.value ?? "");
  const [nodeRevision, setNodeRevision] = useState(episode.revision);
  const [dateSaved, setDateSaved] = useState(false);
  useEffect(() => {
    setNodeRevision(current => Math.max(current, episode.revision));
    setNodeDate(storedAnchor?.value ?? "");
  }, [episode.reviewEpisodeId, episode.revision, storedAnchor?.value]);
  const prefix = `/api/v2/subjects/${encodeURIComponent(episode.subjectId)}/review-episodes/${encodeURIComponent(episode.reviewEpisodeId)}/work-draft-jobs`;
  const storageKey = `work-draft-job:${episode.reviewEpisodeId}`;
  const read = async (url: string, method = "GET"): Promise<Job> => {
    const response = await fetch(url, { method });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error?.detail ?? "暂时无法生成工作稿，原资料与旧结果未改变。");
    if (typeof data.job_id !== "string" || !["queued", "running", "recovering", "failed_retryable", "waiting_user", "completed", "failed_final", "cancel_requested", "cancelled"].includes(data.state)
      || !(data.review_run_id === null || typeof data.review_run_id === "string")) throw new Error("工作稿处理记录不完整，请刷新查看。");
    return data;
  };
  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const saved = localStorage.getItem(storageKey);
    async function refresh() {
      const id = job?.job_id ?? saved;
      if (!id) return;
      try {
        const result = await read(`${prefix}/${encodeURIComponent(id)}`);
        if (cancelled) return;
        setJob(result);
        if (result.state === "completed" && result.review_run_id) {
          // The surrounding view already reads saved results on mount. Only a
          // running job's transition needs a refresh; otherwise remount loops.
          if (job && job.state !== "completed") onCompleted?.(result.review_run_id);
        }
        else if (["queued", "running", "recovering", "failed_retryable", "cancel_requested"].includes(result.state)) timer = setTimeout(() => void refresh(), 2000);
      } catch (e) { if (!cancelled) setError(e instanceof Error ? e.message : "暂时无法读取进度。"); }
    }
    void refresh();
    return () => { cancelled = true; clearTimeout(timer); };
  }, [prefix, storageKey, job?.job_id]);
  async function start() {
    setBusy(true); setError(null);
    try {
      const result = await read(prefix, "POST");
      localStorage.setItem(storageKey, result.job_id);
      setJob(result);
      if (result.state === "completed" && result.review_run_id) onCompleted?.(result.review_run_id);
    } catch (e) { setError(e instanceof Error ? e.message : "暂时无法开始审核。"); }
    finally { setBusy(false); }
  }
  async function saveDate() {
    setBusy(true); setError(null); setDateSaved(false);
    try {
      const response = await fetch(prefix.replace("work-draft-jobs", "node-date"), {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ node_date: nodeDate, expected_revision: nodeRevision }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error?.detail ?? "日期未保存，请核对当前资料处理状态。");
      if (!Number.isInteger(data.revision)) throw new Error("日期保存回执不完整，请刷新查看。");
      setNodeRevision(data.revision); setDateSaved(true);
    } catch (e) { setError(e instanceof Error ? e.message : "暂时无法保存日期。"); }
    finally { setBusy(false); }
  }
  const pending = job !== null && !["completed", "failed_final", "cancelled"].includes(job.state);
  return <section className="eligibility-context-bar" aria-label="生成工作稿">
    <label>本节点日期 <input type="date" value={nodeDate} disabled={busy || pending}
      onChange={event => { setNodeDate(event.target.value); setDateSaved(false); }} /></label>
    <button type="button" className="button button--quiet" disabled={!nodeDate || busy || pending} onClick={() => void saveDate()}>保存日期</button>
    {dateSaved && <span role="status">日期已保存，请按此日期更新工作稿。</span>}
    <p role="status">{job?.state === "completed" ? "工作稿已保存，未签发。" : job?.state === "cancel_requested" ? "正在停止本次处理，原件与已有结果保留。" : job?.state === "cancelled" ? "本次处理已停止，原件与已有结果保留。" : job?.state === "waiting_user" ? "本次处理需要人工核对，请查看任务详情。" : pending ? "正在核对已有记录并生成工作稿。" : "根据当前方案和已提供资料生成工作稿。"}</p>
    <button type="button" className="button button--primary" disabled={busy || pending || !episode.activeEvidenceProcessingRevisionId} onClick={() => void start()}>
      {job?.state === "completed" ? <RefreshCw size={16} aria-hidden="true" /> : <Play size={16} aria-hidden="true" />}
      {busy ? "正在提交" : job?.state === "completed" ? "更新工作稿" : "开始审核"}
    </button>
    {job?.state === "failed_final" && <p role="alert">本次工作稿未能生成，请核查资料与方案记录；旧结果未改变。</p>}
    {error && <p role="alert"><TriangleAlert size={16} aria-hidden="true" />{error}</p>}
  </section>;
}
