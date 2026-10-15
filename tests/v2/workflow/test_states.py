"""状态机纯函数：机器值、终态判定、取消映射、退避与可重试范围。"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.workflow.states import (
    JobState,
    JobStepState,
    backoff_delay,
    is_job_terminal,
    is_step_terminal,
    job_state_after_step_failure,
    retryable_scope,
    step_is_deferred,
    step_state_after_cancel,
    step_state_after_failure,
)


def test_terminal_predicates() -> None:
    for state in (JobState.COMPLETED, JobState.FAILED_FINAL, JobState.CANCELLED):
        assert is_job_terminal(state.value) is True
    for state in (JobState.QUEUED, JobState.RUNNING, JobState.FAILED_RETRYABLE,
                  JobState.CANCEL_REQUESTED, JobState.RECOVERING, JobState.WAITING_USER):
        assert is_job_terminal(state.value) is False

    for state in (JobStepState.COMPLETED, JobStepState.FAILED_FINAL, JobStepState.CANCELLED):
        assert is_step_terminal(state.value) is True
    for state in (JobStepState.QUEUED, JobStepState.RUNNING, JobStepState.FAILED_RETRYABLE,
                  JobStepState.WAITING_USER):
        assert is_step_terminal(state.value) is False


def test_job_state_after_step_failure() -> None:
    assert job_state_after_step_failure(retryable=True, cancel_requested=False) == "failed_retryable"
    assert job_state_after_step_failure(retryable=False, cancel_requested=False) == "failed_final"
    # 取消请求在安全边界优先于任何失败分类
    assert job_state_after_step_failure(retryable=True, cancel_requested=True) == "cancelled"
    assert job_state_after_step_failure(retryable=False, cancel_requested=True) == "cancelled"


def test_step_state_after_failure() -> None:
    assert step_state_after_failure(retryable=True) == "failed_retryable"
    assert step_state_after_failure(retryable=False) == "failed_final"


def test_step_state_after_cancel_preserves_terminal_history() -> None:
    # 终态步骤保留历史；未完成步骤转 cancelled
    assert step_state_after_cancel("completed") == "completed"
    assert step_state_after_cancel("failed_final") == "failed_final"
    assert step_state_after_cancel("cancelled") == "cancelled"
    assert step_state_after_cancel("queued") == "cancelled"
    assert step_state_after_cancel("running") == "cancelled"
    assert step_state_after_cancel("failed_retryable") == "cancelled"


def test_backoff_is_monotonic_and_capped() -> None:
    first = backoff_delay(1, base=1.0, factor=2.0, cap=4.0)
    second = backoff_delay(2, base=1.0, factor=2.0, cap=4.0)
    third = backoff_delay(3, base=1.0, factor=2.0, cap=4.0)
    assert first == timedelta(seconds=1.0)
    assert second == timedelta(seconds=2.0)
    assert third == timedelta(seconds=4.0)
    assert backoff_delay(4, base=1.0, factor=2.0, cap=4.0) == timedelta(seconds=4.0)
    assert backoff_delay(10, base=1.0, factor=2.0, cap=4.0) == timedelta(seconds=4.0)
    with pytest.raises(ValueError):
        backoff_delay(0)


def test_retryable_scope_only_failed_steps() -> None:
    states = {
        "s1": "completed",
        "s2": "failed_retryable",
        "s3": "failed_final",
        "s4": "queued",
        "s5": "cancelled",
    }
    assert retryable_scope(states) == ["s2", "s3"]


def test_step_is_deferred_only_during_backoff() -> None:
    now = datetime(2026, 8, 14, 12, 0, 0)
    future = now + timedelta(seconds=5)
    past = now - timedelta(seconds=5)
    assert step_is_deferred("failed_retryable", future, now) is True
    assert step_is_deferred("failed_retryable", past, now) is False
    assert step_is_deferred("failed_retryable", None, now) is False
    assert step_is_deferred("queued", future, now) is False
