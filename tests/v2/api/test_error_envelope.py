"""V2 API 错误信封映射：错误租约、revision 冲突、数据库繁忙等。

API 层只把领域异常转成自然中文问题/影响/恢复动作，不泄露 SQL、堆栈、
枚举或日志词（design.md §8）。Job API 本身不暴露可变实体编辑端点，
revision 冲突与租约丢失在本层以 ``map_exception`` 单元测试覆盖。
"""
from __future__ import annotations

from sqlalchemy.exc import OperationalError

from app.api.v2.errors import map_exception
from app.storage.concurrency import FieldChange, StaleRevisionError
from app.storage.idempotency import IdempotencyConflict
from app.workflow.errors import (
    JobNotFoundError,
    JobStateConflictError,
    LeaseLostError,
    WorkflowError,
)


def _envelope(exc: Exception):
    status, body = map_exception(exc)
    return status, body["error"]


def test_lease_lost_maps_to_chinese_envelope() -> None:
    status, error = _envelope(LeaseLostError("任务 x 租约失效"))
    assert status == 409
    assert error["code"] == "LEASE_LOST"
    assert error["title"] == "任务执行权已失效"
    assert error["recovery_action"]
    assert error["correlation_id"]
    # 不泄露内部租约/代号的实现细节
    assert "generation" not in error["detail"]
    assert "owner" not in error["detail"]


def test_stale_revision_carries_diff_and_current_revision() -> None:
    exc = StaleRevisionError(
        entity_type="project",
        entity_id="p1",
        expected_revision=1,
        current_revision=2,
        field_diff={"name": FieldChange(current="新名", submitted="旧名")},
    )
    status, error = _envelope(exc)
    assert status == 409
    assert error["code"] == "STALE_REVISION"
    assert error["title"] == "记录内容已经更新"
    context = error["context"]
    assert context["entity_type"] == "project"
    assert context["expected_revision"] == 1
    assert context["current_revision"] == 2
    assert context["field_diff"]["name"] == {"current": "新名", "submitted": "旧名"}
    assert "code" not in context  # code 已提升到信封顶层


def test_idempotency_conflict_maps_to_409() -> None:
    exc = IdempotencyConflict(
        scope="jobs", idempotency_key="k", existing_sha256="a", submitted_sha256="b"
    )
    status, error = _envelope(exc)
    assert status == 409
    assert error["code"] == "IDEMPOTENCY_CONFLICT"
    assert error["title"] == "重复提交内容不一致"
    # 哈希是内部细节，不应出现在面向用户的中文文案里
    assert "sha256" not in error["detail"]
    assert "sha256" not in error["title"]


def test_database_busy_maps_to_503() -> None:
    exc = OperationalError("INSERT INTO x", {}, Exception("database is locked"))
    status, error = _envelope(exc)
    assert status == 503
    assert error["code"] == "DATABASE_BUSY"
    assert error["title"] == "数据库暂时繁忙"
    assert "locked" not in error["detail"]  # 不泄露底层错误词


def test_other_database_failure_is_not_mislabeled_as_busy() -> None:
    exc = OperationalError("SELECT x", {}, Exception("no such table: x"))
    status, error = _envelope(exc)
    assert status == 500
    assert error["code"] == "LOCAL_DATA_ERROR"
    assert error["title"] == "本地数据读取失败"
    assert "no such table" not in error["detail"]


def test_not_found_and_state_conflict() -> None:
    assert _envelope(JobNotFoundError("不存在"))[0] == 404
    assert _envelope(JobNotFoundError("不存在"))[1]["code"] == "NOT_FOUND"
    status, error = _envelope(JobStateConflictError("不允许", current_state="queued"))
    assert status == 409
    assert error["code"] == "JOB_STATE_CONFLICT"
    assert error["context"] == {"current_state": "queued"}


def test_unknown_error_falls_back_to_internal_without_leak() -> None:
    status, error = _envelope(RuntimeError("secret traceback token"))
    assert status == 500
    assert error["code"] == "INTERNAL_ERROR"
    assert "secret traceback token" not in error["detail"]
    assert "secret traceback token" not in error["title"]


def test_generic_workflow_error_uses_stable_code() -> None:
    status, error = _envelope(WorkflowError("内部工作流错误"))
    assert status == 409
    assert error["code"] == "JOB_ERROR"
    assert error["correlation_id"]
