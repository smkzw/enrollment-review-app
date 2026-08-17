"""工作流错误类型：稳定错误码 + 恢复语义。

API 层只做协议转换；这里的 ``code`` 供程序和测试使用，
中文问题/影响/恢复动作由 API 错误词汇表提供（设计 §8）。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any


class WorkflowError(RuntimeError):
    code = "JOB_ERROR"

    def __init__(self, message: str, **context: Any) -> None:
        super().__init__(message)
        self.context = context


class JobNotFoundError(WorkflowError):
    code = "NOT_FOUND"


class JobStateConflictError(WorkflowError):
    """任务当前状态不允许该操作（如取消已完成任务、重试未失败任务）。"""

    code = "JOB_STATE_CONFLICT"

    def __init__(self, message: str, *, current_state: str) -> None:
        super().__init__(message, current_state=current_state)
        self.current_state = current_state


class InvalidJobDefinitionError(WorkflowError):
    """步骤编号、依赖或依赖图不完整，任务不得入队。"""

    code = "INVALID_JOB_DEFINITION"


class LeaseLostError(WorkflowError):
    """租约校验失败：提交被丢弃，不写入任何步骤结果（设计 §8）。"""

    code = "LEASE_LOST"


class StepDeferredError(WorkflowError):
    """步骤仍在退避等待期内，不可启动。"""

    code = "STEP_DEFERRED"

    def __init__(self, step_id: str, retry_not_before: datetime) -> None:
        super().__init__(
            f"步骤 {step_id} 的退避等待期未结束（不早于 {retry_not_before.isoformat()}）",
            step_id=step_id,
            retry_not_before=retry_not_before,
        )


class StepMismatchError(WorkflowError):
    """步骤不属于当前任务或状态不允许该操作（内部一致性护栏）。"""

    code = "STEP_MISMATCH"


class StepFailure(WorkflowError):
    """执行器声明的步骤失败：分类明确，决定重试范围与任务状态。"""

    code = "STEP_FAILED"

    def __init__(
        self,
        *,
        retryable: bool,
        error_code: str,
        detail: str | None = None,
    ) -> None:
        super().__init__(detail or error_code, retryable=retryable, error_code=error_code)
        self.retryable = retryable
        self.error_code = error_code
        self.detail = detail


class StepWaitForUser(Exception):
    """执行器声明的用户等待边界：持久 ``waiting_user``，不占用租约，不进入重试。"""

    def __init__(
        self,
        *,
        awaiting_user: str,
        checkpoint_payload: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(awaiting_user)
        self.awaiting_user = awaiting_user
        self.checkpoint_payload = checkpoint_payload


class ProcessDeath(BaseException):
    """模拟进程被强制终止（提交前/提交后故障注入）。

    继承 :class:`BaseException`：runner 不捕获、不清理、不写状态，
    等价于真实进程死亡 —— 恢复只能由租约过期 + 恢复器完成。
    """
