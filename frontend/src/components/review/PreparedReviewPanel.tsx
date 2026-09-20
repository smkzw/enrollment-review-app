import { CheckCircle2, Circle, FileText, Play, RefreshCw, Square, TriangleAlert } from "lucide-react";
import type { CatalogEpisodeView } from "../../api/catalog/catalogTypes";
import type { PreparedReviewTask } from "../../api/eligibility-review/preparedReviewHttp";
import { usePreparedReview } from "../../features/eligibility-review/usePreparedReview";

interface Props {
  episode: CatalogEpisodeView;
  workflowId: string | null;
  requestKey: string | null;
  onRequestKey: (key: string) => void;
  onStarted: (workflowId: string) => void;
  onNewReview: () => void;
  onPublished: (runId: string) => void;
}

function taskName(task: PreparedReviewTask, tasks: PreparedReviewTask[]): string {
  if (task.kind === "predicate_candidates") return "核对入排条款";
  if (task.kind === "control_candidates") return "核对方案补充要求";
  if (task.kind === "observation_relation") return "核实初查、复查与重复记录";
  if (task.kind === "frequency_evidence") return "核实发生次数、天数与统计期间";
  if (task.kind === "proposition_evidence") return tasks.find((item) => item.jobId === task.candidateJobId)?.kind === "control_candidates"
    ? "核实原文对补充要求的说明" : "核实原文对入排条款的说明";
  if (task.kind === "judgment_content") return tasks.find((item) => item.jobId === task.candidateJobId)?.kind === "control_candidates"
    ? "核实补充要求的书面判断" : "核实入排条款的书面判断";
  return tasks.find((item) => item.jobId === task.candidateJobId)?.kind === "control_candidates"
    ? "复核补充要求的原文依据" : "复核入排条款的原文依据";
}

export function PreparedReviewPanel(props: Props) {
  const review = usePreparedReview(props);
  const state = review.data?.state;
  const ended = state !== undefined && ["completed", "cancelled", "failed_final"].includes(state);
  const failed = state === "failed_final" || state === "failed_retryable";
  return <section className="prepared-review" aria-label="本次审核">
    <header className="prepared-review__head">
      <div>
        <h2>本次审核</h2>
        <p aria-live="polite">{review.busy ? "正在提交" : review.data?.stateLabel
          ?? (props.workflowId ? "正在读取审核进度" : "尚未开始")}</p>
      </div>
      <div className="prepared-review__actions">
        {props.workflowId === null ? <button className="button button--primary" type="button"
          disabled={review.busy || !review.canStart} onClick={() => void review.start()}>
          <Play size={16} aria-hidden="true" />开始审核
        </button> : <>
          {state === "completed" && !review.data?.reportSaved && <button className="button button--primary" type="button" disabled={review.busy}
            onClick={() => void review.publish()}><FileText size={16} aria-hidden="true" />生成审核报告</button>}
          <button className="icon-button" type="button" title="刷新审核进度" aria-label="刷新审核进度"
            disabled={review.busy} onClick={review.refresh}><RefreshCw size={16} aria-hidden="true" /></button>
          {failed && <button className="button" type="button" disabled={review.busy}
            onClick={() => void review.change("retry")}><RefreshCw size={16} aria-hidden="true" />重试未完成部分</button>}
          {!ended && <button className="button" type="button" disabled={review.busy || state === "cancel_requested"}
            onClick={() => void review.change("cancel")}><Square size={16} aria-hidden="true" />停止核对</button>}
          {ended && <button className="button" type="button" disabled={review.busy} onClick={props.onNewReview}>
            <Play size={16} aria-hidden="true" />重新准备审核</button>}
        </>}
      </div>
    </header>
    {props.workflowId === null && !review.canStart && <p className="prepared-review__notice">
      当前节点的资料尚未整理完成，请先完成资料判读与病史整理。
    </p>}
    {review.errorMessage && <p className="prepared-review__notice" role="alert"><TriangleAlert size={16} aria-hidden="true" />{review.errorMessage}</p>}
    {review.data && <>
      <p className="prepared-review__stage">{review.data.stageLabel}</p>
      <ul className="prepared-review__steps">
        {review.data.items.map((task) => <li key={task.jobId}>
          {task.state === "completed" ? <CheckCircle2 size={18} aria-hidden="true" />
            : task.state.startsWith("failed") ? <TriangleAlert size={18} aria-hidden="true" />
            : <Circle size={18} aria-hidden="true" />}
          <span>{taskName(task, review.data!.items)}</span>
          <span>{task.stateLabel}</span>
          <progress aria-label={`${taskName(task, review.data!.items)}进度`}
            max={task.progressTotal || 1} value={task.progressTotal > 0 ? task.progressCompleted : undefined} />
        </li>)}
      </ul>
    </>}
  </section>;
}
