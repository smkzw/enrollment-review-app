/**
 * 状态徽标：中文词 + 图标同时显示，颜色只作辅助（合同 §2.1/§1.1）。
 * 覆盖审核节点主状态、阻断程度、资料整理任务状态三类。
 */

import {
  AttentionIcon,
  BarrierIcon,
  CancelledIcon,
  CheckIcon,
  ClearIcon,
  ConflictIcon,
  GapIcon,
  JudgmentIcon,
  ResumeIcon,
  RunningIcon,
  StaleIcon,
} from "./icons";
import {
  blockingLevelBadge,
  blockingLevelLabel,
  mainStatusLabel,
  taskStateLabel,
} from "../../domain/labels";
import type {
  BlockingLevel,
  EpisodeMainStatus,
  TaskState,
} from "../../domain/enums";

/** 色调只作辅助：危险（红）、提醒（琥珀）、中性（灰）、可继续（绿） */
export type Tone = "danger" | "info" | "neutral" | "ok";

interface StatusBadgeProps {
  tone: Tone;
  /** 中文词 */
  text: string;
  /** 悬停/无障碍完整说明 */
  hint?: string;
  icon?: React.ReactNode;
}

export function StatusBadge({ tone, text, hint, icon }: StatusBadgeProps) {
  return (
    <span className={`status-badge status-badge--${tone}`} title={hint ?? text}>
      {icon}
      <span>{text}</span>
    </span>
  );
}

const MAIN_STATUS_TONE: Record<EpisodeMainStatus, Tone> = {
  clear_barrier: "danger",
  current_gap: "info",
  conflict: "danger",
  professional_judgment: "info",
  future_attention: "neutral",
  no_clear_barrier: "ok",
};

const MAIN_STATUS_ICON: Record<EpisodeMainStatus, React.ReactNode> = {
  clear_barrier: <BarrierIcon size={13} />,
  current_gap: <GapIcon size={13} />,
  conflict: <ConflictIcon size={13} />,
  professional_judgment: <JudgmentIcon size={13} />,
  future_attention: <AttentionIcon size={13} />,
  no_clear_barrier: <ClearIcon size={13} />,
};

export function MainStatusBadge({ status }: { status: EpisodeMainStatus }) {
  return (
    <StatusBadge
      tone={MAIN_STATUS_TONE[status]}
      text={mainStatusLabel[status]}
      icon={MAIN_STATUS_ICON[status]}
    />
  );
}

export function BlockingBadge({ level }: { level: BlockingLevel }) {
  const tone: Tone =
    level === "blocking" ? "danger" : level === "attention" ? "info" : "neutral";
  const icon =
    level === "blocking" ? (
      <BarrierIcon size={13} />
    ) : level === "attention" ? (
      <AttentionIcon size={13} />
    ) : (
      <ClearIcon size={13} />
    );
  return (
    <StatusBadge
      tone={tone}
      text={blockingLevelBadge[level]}
      hint={blockingLevelLabel[level]}
      icon={icon}
    />
  );
}

const TASK_STATE_TONE: Record<TaskState, Tone> = {
  queued: "neutral",
  running: "info",
  completed: "ok",
  partial: "info",
  failed: "danger",
  resumable: "info",
  cancelled: "neutral",
  stale: "danger",
};

const TASK_STATE_ICON: Record<TaskState, React.ReactNode> = {
  queued: <RunningIcon size={13} />,
  running: <RunningIcon size={13} />,
  completed: <CheckIcon size={13} />,
  partial: <GapIcon size={13} />,
  failed: <BarrierIcon size={13} />,
  resumable: <ResumeIcon size={13} />,
  cancelled: <CancelledIcon size={13} />,
  stale: <StaleIcon size={13} />,
};

export function TaskStateBadge({ state }: { state: TaskState }) {
  return (
    <StatusBadge
      tone={TASK_STATE_TONE[state]}
      text={taskStateLabel[state]}
      icon={TASK_STATE_ICON[state]}
    />
  );
}
