"""V2 中文投影词汇表：稳定机器值 -> 用户可读中文（design.md §5）。"""
from __future__ import annotations

from app.workflow.states import TERMINAL_JOB_STATES

JOB_STATE_LABELS: dict[str, str] = {
    "queued": "等待执行",
    "running": "执行中",
    "completed": "已完成",
    "failed_retryable": "失败（等待重试）",
    "failed_final": "失败",
    "cancel_requested": "正在取消",
    "cancelled": "已取消",
    "recovering": "恢复中",
}

STEP_STATE_LABELS: dict[str, str] = {
    "queued": "等待执行",
    "running": "执行中",
    "completed": "已完成",
    "failed_retryable": "失败（等待重试）",
    "failed_final": "失败",
    "cancelled": "已取消",
}

EVENT_TYPE_LABELS: dict[str, str] = {
    "created": "任务已创建",
    "step_started": "步骤开始",
    "step_completed": "步骤完成",
    "step_failed": "步骤失败",
    "retry_scheduled": "已安排重试",
    "cancel_requested": "取消已受理",
    "cancelled": "任务已取消",
    "completed": "任务已完成",
    "failed": "任务执行失败",
}

_JOB_RECOVERY_ACTIONS: dict[str, str] = {
    "queued": "无需操作，任务正在等待执行。",
    "running": "任务正在执行；关闭页面或断开连接不会中断任务。",
    "failed_retryable": "系统将按退避策略自动重试失败步骤；也可以手动重试仅重跑失败范围。",
    "failed_final": "可以点击“重试”仅重跑失败步骤；已完成步骤不会重复执行。",
    "cancel_requested": "取消请求已受理，任务将在安全步骤边界停止。",
    "cancelled": "任务已取消；已完成的步骤和检查点保留在历史记录中。",
    "completed": "任务已完成，全部步骤均已提交检查点。",
    "recovering": "服务重启后正在恢复任务，无需操作。",
}


def job_recovery_action(state: str) -> str:
    return _JOB_RECOVERY_ACTIONS.get(state, "请刷新任务状态获取最新进展。")


def is_terminal_label(state: str) -> bool:
    return state in TERMINAL_JOB_STATES
