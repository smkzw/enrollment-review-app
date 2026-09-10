/**
 * 页面视觉核验任务面板：已冻结证据修订的视觉核验状态、失败范围与人工重试/取消。
 * 只消费修订级投影的中文业务字段与稳定机器状态；不显示模型、日志或工程字段。
 */

import { useEffect, useState } from "react";
import {
  cancelSelectiveVisionTask,
  getSelectiveVisionTask,
  retrySelectiveVisionTask,
} from "../../api/evidence";
import { useLoad } from "../../app/useLoad";
import { ResumeIcon } from "../shell/icons";
import { StatusBadge, type Tone } from "../shell/StatusBadge";

interface SelectiveVisionTaskPanelProps {
  revisionId: string;
}

/** 停止请求受理后任务尚未落定，仍需轮询直到终态。 */
const POLLING_STATES = new Set([
  "queued",
  "running",
  "recovering",
  "cancel_requested",
]);

function toneFor(state: string | null): Tone {
  if (state === "completed") return "ok";
  if (state === "failed_final") return "danger";
  if (state === "failed_retryable") return "info";
  return "neutral";
}

function formatTime(iso: string): string {
  const value = new Date(iso);
  if (Number.isNaN(value.getTime())) return iso;
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(value);
}

export function SelectiveVisionTaskPanel({
  revisionId,
}: SelectiveVisionTaskPanelProps) {
  const detail = useLoad(
    (signal) => getSelectiveVisionTask(revisionId, signal),
    [revisionId],
  );
  const [busyAction, setBusyAction] = useState<"retry" | "cancel" | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    if (detail.state.status !== "success") return;
    if (!POLLING_STATES.has(detail.state.data.state ?? "")) return;
    const timer = window.setTimeout(detail.retry, 2000);
    return () => window.clearTimeout(timer);
  }, [detail.retry, detail.state]);

  if (detail.state.status === "loading") return null;
  if (detail.state.status === "error") {
    return (
      <div className="evidence-notice evidence-notice--error" role="status">
        页面视觉核验状态暂时打不开：{detail.state.message}
        <button type="button" className="button" onClick={detail.retry}>
          重试
        </button>
      </div>
    );
  }
  const task = detail.state.data;
  if (!task.found) return null;

  const summaryEntries: Array<{ label: string; value: number }> = [];
  if (task.eligiblePageCount !== null) {
    summaryEntries.push({ label: "需要核验的页面", value: task.eligiblePageCount });
  }
  if (task.skippedPageCount !== null) {
    summaryEntries.push({ label: "无需核验的页面", value: task.skippedPageCount });
  }
  if (task.observationPageCount !== null) {
    summaryEntries.push({ label: "已形成核对观察", value: task.observationPageCount });
  }
  if (task.closedPageCount !== null && task.closedPageCount > 0) {
    summaryEntries.push({ label: "未能核验而关闭", value: task.closedPageCount });
  }

  async function runAction(action: "retry" | "cancel"): Promise<void> {
    setBusyAction(action);
    setActionError(null);
    try {
      if (action === "retry") {
        await retrySelectiveVisionTask(revisionId);
      } else {
        await cancelSelectiveVisionTask(revisionId);
      }
      detail.retry();
    } catch {
      setActionError(
        action === "retry"
          ? "未能重新开始页面视觉核验。已保存的识别结果不受影响，请稍后再试。"
          : "未能停止页面视觉核验。请刷新状态后重试。",
      );
    } finally {
      setBusyAction(null);
    }
  }

  return (
    <section
      className="tasks-section persistent-task"
      aria-labelledby="selective-vision-task-title"
    >
      <div className="tasks-section__head">
        <div>
          <p className="persistent-task__eyebrow">已冻结证据修订</p>
          <h2 id="selective-vision-task-title" className="tasks-section__title">
            页面视觉核验
          </h2>
        </div>
        <StatusBadge tone={toneFor(task.state)} text={task.stateLabel} />
      </div>

      <p className="persistent-task__recovery">
        <ResumeIcon size={14} />
        {task.recoveryAction}
      </p>

      {summaryEntries.length > 0 && (
        <div className="persistent-task__summary">
          {summaryEntries.map((entry) => (
            <div key={entry.label}>
              <span>{entry.label}</span>
              <strong>{entry.value}</strong>
            </div>
          ))}
          {task.updatedAt !== null && (
            <div>
              <span>最近更新</span>
              <strong>{formatTime(task.updatedAt)}</strong>
            </div>
          )}
        </div>
      )}

      {task.failedScopeLabel !== null && (
        <p className="evidence-notice evidence-notice--error" role="status">
          <strong>未完成范围：{task.failedScopeLabel}</strong>
          {task.closedReasonLabel !== null && <span>{task.closedReasonLabel}。</span>}
        </p>
      )}

      {actionError !== null && (
        <p className="evidence-notice evidence-notice--error" role="alert">
          {actionError}
        </p>
      )}

      <div className="job-detail__actions">
        <button type="button" className="button" onClick={detail.retry}>
          刷新状态
        </button>
        {task.canRetry && (
          <button
            type="button"
            className="button button--primary"
            disabled={busyAction !== null}
            onClick={() => void runAction("retry")}
          >
            {busyAction === "retry" ? "正在重新开始…" : "重新开始核验"}
          </button>
        )}
        {task.canCancel && (
          <button
            type="button"
            className="button"
            disabled={busyAction !== null}
            onClick={() => void runAction("cancel")}
          >
            {busyAction === "cancel" ? "正在停止…" : "停止核验"}
          </button>
        )}
      </div>
    </section>
  );
}
