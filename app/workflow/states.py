"""持久 Job 状态机：稳定机器值与纯状态转换函数。

设计（.trellis/tasks/08-14-phase2-sqlite-domain-jobs/design.md §5）：

::

    queued -> running -> completed
                      -> failed_retryable -> queued
                      -> failed_final
                      -> cancel_requested -> cancelled
    running --lease expired/startup recovery--> recovering -> queued

- Job/Step 状态使用稳定英文机器值，中文标签由 API 投影词汇表提供；
- 本模块不导入 SQLAlchemy/FastAPI，全部为纯函数，可直接单测；
- 取消是持久请求：worker 只在安全步骤边界检查并提交 cancelled；
- 可重试失败只重跑失败范围；已完成步骤与已提交检查点永不回退。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from app.domain.contracts.enums import StableEnum


class JobState(StableEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_FINAL = "failed_final"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
    RECOVERING = "recovering"


class JobStepState(StableEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_FINAL = "failed_final"
    CANCELLED = "cancelled"


class ErrorClassification(StableEnum):
    """步骤失败分类：retryable 由系统按退避自动重试；fatal 需要人工重试。"""

    RETRYABLE = "retryable"
    FATAL = "fatal"


TERMINAL_JOB_STATES: tuple[str, ...] = (
    JobState.COMPLETED.value,
    JobState.FAILED_FINAL.value,
    JobState.CANCELLED.value,
)
TERMINAL_STEP_STATES: tuple[str, ...] = (
    JobStepState.COMPLETED.value,
    JobStepState.FAILED_FINAL.value,
    JobStepState.CANCELLED.value,
)
CLAIMABLE_JOB_STATES: tuple[str, ...] = (
    JobState.QUEUED.value,
    JobState.RECOVERING.value,
)
RUNNABLE_STEP_STATES: tuple[str, ...] = (
    JobStepState.QUEUED.value,
    JobStepState.FAILED_RETRYABLE.value,
)
FAILED_STEP_STATES: tuple[str, ...] = (
    JobStepState.FAILED_RETRYABLE.value,
    JobStepState.FAILED_FINAL.value,
)
ACTIVE_LEASE_STATES: tuple[str, ...] = ("running", "cancel_requested")
# 无租约时可直接取消的 Job 状态（安全边界：没有正在执行的步骤）
DIRECT_CANCELABLE_JOB_STATES: tuple[str, ...] = (
    JobState.QUEUED.value,
    JobState.FAILED_RETRYABLE.value,
    JobState.RECOVERING.value,
)

DEPENDENCY_FAILED_CODE = "DEPENDENCY_FAILED"
EXECUTOR_MISSING_CODE = "EXECUTOR_MISSING"
EXECUTOR_ERROR_CODE = "EXECUTOR_ERROR"
RECOVERY_RESET_CODE = "RECOVERY_RESET"


def is_job_terminal(state: str) -> bool:
    return state in TERMINAL_JOB_STATES


def is_step_terminal(state: str) -> bool:
    return state in TERMINAL_STEP_STATES


def job_state_after_step_failure(retryable: bool, cancel_requested: bool) -> str:
    """步骤失败后任务的目标状态（取消请求在安全边界优先）。"""
    if cancel_requested:
        return JobState.CANCELLED.value
    if retryable:
        return JobState.FAILED_RETRYABLE.value
    return JobState.FAILED_FINAL.value


def step_state_after_failure(retryable: bool) -> str:
    return (
        JobStepState.FAILED_RETRYABLE.value
        if retryable
        else JobStepState.FAILED_FINAL.value
    )


def step_state_after_cancel(state: str) -> str:
    """取消时步骤的目标状态：终态步骤保留历史，其余转为 cancelled。"""
    if state in TERMINAL_STEP_STATES:
        return state
    return JobStepState.CANCELLED.value


def backoff_delay(
    attempt: int,
    *,
    base: float = 0.5,
    factor: float = 2.0,
    cap: float = 8.0,
) -> timedelta:
    """指数退避：``base * factor**(attempt-1)``，封顶 ``cap`` 秒。

    纯函数：attempt 为已执行次数（>=1）。
    """
    if attempt < 1:
        raise ValueError(f"attempt 必须 >= 1，收到 {attempt}")
    seconds = min(base * (factor ** (attempt - 1)), cap)
    return timedelta(seconds=seconds)


def retryable_scope(states: dict[str, str]) -> list[str]:
    """可重试范围 = 失败步骤（failed_retryable / failed_final），保持稳定顺序。"""
    return [step_id for step_id, state in states.items() if state in FAILED_STEP_STATES]


def step_is_deferred(state: str, retry_not_before: datetime | None, now: datetime) -> bool:
    """退避未到期的可重试步骤：不可启动，但任务本身保持持久状态。"""
    return (
        state == JobStepState.FAILED_RETRYABLE.value
        and retry_not_before is not None
        and retry_not_before > now
    )
