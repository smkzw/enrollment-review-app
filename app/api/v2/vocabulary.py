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
    "waiting_user": "等待确认",
}

STEP_STATE_LABELS: dict[str, str] = {
    "queued": "等待执行",
    "running": "执行中",
    "completed": "已完成",
    "failed_retryable": "失败（等待重试）",
    "failed_final": "失败",
    "cancelled": "已取消",
    "waiting_user": "等待确认",
}

EVENT_TYPE_LABELS: dict[str, str] = {
    "created": "任务已创建",
    "step_started": "步骤开始",
    "step_completed": "步骤完成",
    "step_failed": "步骤失败",
    "retry_scheduled": "已安排重试",
    "waiting_user": "等待确认",
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
    "waiting_user": "任务正在等待您的确认；提交后将继续执行后续步骤。",
}


def job_recovery_action(state: str) -> str:
    return _JOB_RECOVERY_ACTIONS.get(state, "请刷新任务状态获取最新进展。")


def is_terminal_label(state: str) -> bool:
    return state in TERMINAL_JOB_STATES


def study_phase_label(phase: str) -> str:
    labels = {
        "phase_ii": "II 期",
        "phase_iii": "III 期",
        "seamless_phase_ii_iii": "II/III 期无缝设计",
        "other": "其他",
    }
    return labels.get(phase, phase)


METADATA_STATUS_LABELS: dict[str, str] = {
    "pending": "待确认",
    "confirmed": "已确认",
    "conflict": "存在冲突",
}

DRAFT_STATUS_LABELS: dict[str, str] = {
    "draft": "草稿",
    "saved": "已保存",
    "cancelled": "已取消",
    "published": "已发布",
    "restored_from": "已恢复",
}

DRAFT_REASON_LABELS: dict[str, str] = {
    "initial_save": "首次保存",
    "manual_edit": "手工编辑",
    "source_error_feedback": "原文理解纠错",
    "clarification_feedback": "解释性澄清",
    "restore": "恢复历史版本",
}
