import { useEffect, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, Play, RefreshCw, Square } from "lucide-react";
import { getCatalogRepository } from "../../api";
import { createPreparedReviewHttp } from "../../api/eligibility-review/preparedReviewHttp";
import { changeReviewBatch, readReviewBatch, recentReviewBatches, startReviewBatch, type ReviewBatch } from "../../api/eligibility-review/batchReviewHttp";
import { EligibilityReviewApiError } from "../../api/eligibility-review";
import { useLoad } from "../../app/useLoad";
import { updateParams, useHashRoute } from "../../app/router";
import { ErrorState, LoadingState } from "../shell/Feedback";
import { reviewTime } from "./FrozenReviewReport";
import { BatchProcessingEstimate } from "./BatchProcessingEstimate";

export interface BatchChoice { subjectId: string; episodeId: string; snapshotId: string; processingId: string }
const labels: Record<string, string> = { not_started: "尚未开始", queued: "等待处理", running: "正在核对", completed: "核对已结束",
  failed_retryable: "等待重试", failed_final: "未完成", cancel_requested: "正在停止", cancelled: "已停止", recovering: "正在恢复", waiting_user: "等待处理" };
function message(error: unknown): string {
  return error instanceof EligibilityReviewApiError ? error.message
    : error instanceof Error ? error.message : "暂时无法提交，请重试。已保存的资料仍会保留。";
}

function BatchProgress({ projectId, batchId }: { projectId: string; batchId: string }) {
  const [data, setData] = useState<ReviewBatch | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    let failures = 0;
    async function read() {
      try {
        const result = await readReviewBatch(projectId, batchId, controller.signal);
        if (controller.signal.aborted) return;
        setData(result); setError(null); failures = 0;
        if (!["completed", "failed_final", "cancelled"].includes(result.state)
          || result.items.some((item) => !["not_started", "completed", "failed_final", "cancelled"].includes(item.state))) {
          timer = setTimeout(() => void read(), 4000);
        }
      } catch (error) {
        if (controller.signal.aborted) return;
        failures++; setError(`${message(error)}${failures >= 4 ? " 自动刷新暂已停止，请手动刷新。" : ""}`);
        if (failures < 4) timer = setTimeout(() => void read(), failures * 4000);
      }
    }
    void read();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [projectId, batchId, refresh]);
  async function change(operation: "cancel" | "retry") {
    if (busy) return;
    setBusy(true);
    try { await changeReviewBatch(projectId, batchId, operation); setRefresh((value) => value + 1); }
    catch (error) { setError(message(error)); }
    finally { setBusy(false); }
  }
  return <section className="prepared-review" aria-label="本批审核进度">
    <header className="prepared-review__head"><h2>本批审核</h2>
      <div className="prepared-review__actions">
        <button className="icon-button" title="刷新本批进度" aria-label="刷新本批进度" onClick={() => setRefresh((value) => value + 1)}><RefreshCw size={16} /></button>
        {(!data || !["completed", "cancelled", "failed_final"].includes(data.state)) && <button className="button" disabled={busy || data?.state === "cancel_requested"} onClick={() => void change("cancel")}><Square size={16} />停止本批</button>}
        {data && ["failed_final", "failed_retryable"].includes(data.state) && <button className="button" disabled={busy} onClick={() => void change("retry")}><RefreshCw size={16} />重试未处理部分</button>}
      </div>
    </header>
    {error && <p role="alert">{error}</p>}
    {!data ? <LoadingState /> : <>
      <p>{data.items.some((item) => ["queued", "running", "recovering", "failed_retryable"].includes(item.state))
        ? "正在处理所选资料，请查看逐项进度。"
        : data.state === "completed" ? "本批处理已结束，请查看逐项结果。" : labels[data.state]}</p>
      {data.failureDetail && <p role="alert">{data.failureDetail}</p>}
      <table className="reports-print__table"><thead><tr><th>受试者</th><th>当前核对情况</th><th>本批记录</th><th>详细记录</th></tr></thead>
        <tbody>{data.items.map((item) => <tr key={item.episodeId}><th scope="row">{item.subjectCode}<p>{item.stageLabel}</p></th><td>{labels[item.state]}</td>
          <td>{item.recordedState ? labels[item.recordedState] : "尚未结束"}</td><td>{item.workflowId && <a className="button" href={`#/reports?${new URLSearchParams({ project: projectId, subject: item.subjectId, episode: item.episodeId, workflow: item.workflowId })}`}>查看并处理</a>}</td></tr>)}</tbody>
      </table>
    </>}
  </section>;
}

export function BatchReviewPanel({ projectId, choices, onBusy, disabled = false }: { projectId: string; choices: BatchChoice[]; onBusy: (busy: boolean) => void; disabled?: boolean }) {
  const { params } = useHashRoute();
  const batchId = params.get("batch");
  const [offset, setOffset] = useState(0);
  const recent = useLoad((signal) => recentReviewBatches(projectId, signal, offset), [projectId, batchId, offset]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const request = useRef<{ signature: string; key: string } | null>(null);
  const operation = useRef<AbortController | null>(null);
  useEffect(() => () => operation.current?.abort(), []);
  async function start() {
    if (operation.current || disabled || !choices.length || choices.length > 50) return;
    const controller = new AbortController(); operation.current = controller;
    setBusy(true); onBusy(true); setError(null);
    const ordered = [...choices].sort((left, right) => left.episodeId.localeCompare(right.episodeId));
    const signature = JSON.stringify(ordered);
    try {
      const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(signature));
      const fingerprint = Array.from(new Uint8Array(digest), (value) => value.toString(16).padStart(2, "0")).join("");
      const storageKey = `enrollment-review:pending-batch:${projectId}:${fingerprint}`;
      if (request.current?.signature !== signature) {
        try {
          const pending = localStorage.getItem(storageKey);
          const candidate = { signature, key: pending && /^[0-9a-f-]{36}$/.test(pending) ? pending : crypto.randomUUID() };
          localStorage.setItem(storageKey, candidate.key);
          request.current = candidate;
        } catch {
          throw new Error("暂时无法保存本次提交记录。为避免重复审核，尚未提交，请检查浏览器存储后重试。");
        }
      }
      const key = request.current.key;
      const prepared = createPreparedReviewHttp();
      const members = [];
      for (const choice of ordered) {
        const episodes = await getCatalogRepository().listEpisodes(choice.subjectId, controller.signal);
        const episode = episodes.find((item) => item.reviewEpisodeId === choice.episodeId);
        if (!episode || episode.projectId !== projectId || episode.activeEvidenceSnapshotId !== choice.snapshotId || episode.activeEvidenceProcessingRevisionId !== choice.processingId) {
          throw new Error("所选资料已变化，请刷新项目资料后重新选择。");
        }
        const context = await prepared.prepare(choice.subjectId, choice.episodeId, {
          project_id: projectId, subject_id: choice.subjectId, review_episode_id: choice.episodeId,
          episode_revision: episode.revision, protocol_version_id: episode.protocolVersionId,
          rule_set_id: episode.ruleSetId, rule_set_revision: episode.ruleSetRevision,
          evidence_snapshot_v2_id: choice.snapshotId, complete_processing_revision_id: choice.processingId,
        }, `${key}:${choice.episodeId}`, controller.signal);
        members.push({ subject_id: choice.subjectId, review_episode_id: choice.episodeId, context_id: context.contextId });
      }
      const id = await startReviewBatch(projectId, key, members, controller.signal);
      if (!controller.signal.aborted) {
        updateParams({ batch: id });
        setOffset(0);
        localStorage.removeItem(storageKey);
        request.current = null;
      }
    } catch (error) { if (!controller.signal.aborted) setError(message(error)); }
    finally { operation.current = null; if (!controller.signal.aborted) { setBusy(false); onBusy(false); } }
  }
  return <>
    <div className="prepared-review__actions"><button className="button button--primary" type="button" disabled={busy || disabled || !choices.length || choices.length > 50} onClick={() => void start()}>
      <Play size={16} aria-hidden="true" />{busy ? "正在准备所选资料" : `批量审核${choices.length ? `（${choices.length}个节点）` : ""}`}
    </button>{error && <p role="alert">{error}</p>}</div>
    <BatchProcessingEstimate projectId={projectId} kind="review" choices={choices} />
    {recent.state.status === "error" && <ErrorState message={recent.state.message} onRetry={recent.retry} />}
    {recent.state.status === "success" && recent.state.data.offset === offset && recent.state.data.items.length > 0 && <label>批量审核记录
      <select value={batchId ?? ""} onChange={(event) => updateParams({ batch: event.target.value || null })}>
        <option value="">请选择</option>{batchId && !recent.state.data.items.some((item) => item.jobId === batchId) && <option value={batchId}>当前查看的批次</option>}
        {recent.state.data.items.map((item) => <option value={item.jobId} key={item.jobId}>{reviewTime(item.createdAt)} · {item.memberCount}个节点 · {labels[item.state]}</option>)}
      </select>
    </label>}
    <div className="prepared-review__actions">
      <button className="icon-button" type="button" aria-label="上一页批量记录" title="上一页批量记录" disabled={offset === 0 || recent.state.status === "loading"} onClick={() => setOffset((value) => Math.max(0, value - 20))}><ArrowLeft size={16} /></button>
      <button className="icon-button" type="button" aria-label="下一页批量记录" title="下一页批量记录" disabled={recent.state.status !== "success" || recent.state.data.offset !== offset || !recent.state.data.hasMore || offset >= 100000} onClick={() => setOffset((value) => value + 20)}><ArrowRight size={16} /></button>
    </div>
    {recent.state.status === "success" && recent.state.data.unavailableCount > 0 && <p role="status">近期有{recent.state.data.unavailableCount}批记录暂时无法核实，其他批次仍可查看。</p>}
    {batchId && <BatchProgress key={batchId} projectId={projectId} batchId={batchId} />}
  </>;
}
