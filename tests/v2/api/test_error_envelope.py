"""V2 API 错误信封映射：错误租约、revision 冲突、数据库繁忙等。

API 层只把领域异常转成自然中文问题/影响/恢复动作，不泄露 SQL、堆栈、
枚举或日志词（design.md §8）。Job API 本身不暴露可变实体编辑端点，
revision 冲突与租约丢失在本层以 ``map_exception`` 单元测试覆盖。
"""

from __future__ import annotations

import pytest

from app.api.v2.errors import map_exception
from app.services.evidence_app_errors import (
    AppDatabaseBusyError,
    AppIdempotencyConflictError,
    AppStaleRevisionError,
    translate_storage_error,
)
from app.services.evidence_upload_service import (
    CorruptedStagingError,
    EmptySelectionError,
    EmptyUploadError,
    EvidenceUploadServiceError,
    MissingResolutionError,
    NoEffectiveSnapshotError,
    PreviewCleanupFailedError,
    PreviewDigestMismatchError,
    StaleBaseRevisionError,
    UnknownResolutionError,
)
from app.storage.evidence_upload_repositories import (
    EvidenceUploadCommitNotFoundError,
    PreviewNotFoundError,
    PreviewStatusTransitionError,
)
from app.workflow.errors import (
    JobNotFoundError,
    JobStateConflictError,
    LeaseLostError,
    WorkflowError,
)


def _envelope(exc: Exception):
    status, body = map_exception(exc)
    return status, body["error"]


def _service_boundary_envelope(exc: Exception):
    """模拟服务公开边界翻译；API 映射器永远只接收应用错误。"""
    translated = translate_storage_error(exc)
    assert translated is not None
    return _envelope(translated)


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
    exc = AppStaleRevisionError(
        entity_type="project",
        entity_id="p1",
        expected_revision=1,
        current_revision=2,
        submitted={"name": "旧名"},
        current_record={"name": "新名", "revision": 2},
        field_diff={"name": {"current": "新名", "submitted": "旧名"}},
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
    exc = AppIdempotencyConflictError(
        scope="jobs",
        idempotency_key="k",
        submitted={"reason": "本次"},
        current_record={"reason": "首次"},
        existing_result={"job_id": "j1"},
    )
    status, error = _envelope(exc)
    assert status == 409
    assert error["code"] == "IDEMPOTENCY_CONFLICT"
    assert error["title"] == "重复提交内容不一致"
    # 哈希是内部细节，不应出现在面向用户的中文文案里
    assert "sha256" not in error["detail"]
    assert "sha256" not in error["title"]


def test_database_busy_maps_to_503() -> None:
    exc = AppDatabaseBusyError("本机数据库当前正忙，本次操作没有完成。")
    status, error = _envelope(exc)
    assert status == 503
    assert error["code"] == "DATABASE_BUSY"
    assert error["title"] == "数据库暂时繁忙"
    assert "locked" not in error["detail"]  # 不泄露底层错误词


def test_storage_failure_not_translated_inside_api_mapper() -> None:
    from app.storage.idempotency import IdempotencyConflict

    exc = IdempotencyConflict(
        scope="jobs", idempotency_key="k", existing_sha256="a", submitted_sha256="b"
    )
    status, error = _envelope(exc)
    assert status == 500
    assert error["code"] == "INTERNAL_ERROR"
    assert "sha256" not in error["detail"]


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


# ---------------------------------------------------------------- Phase 4 证据上传


@pytest.mark.parametrize(
    "exc,status,code",
    [
        (EmptyUploadError("无文件"), 422, "EMPTY_UPLOAD"),
        (NoEffectiveSnapshotError("无前序快照"), 409, "NO_EFFECTIVE_SNAPSHOT"),
        (StaleBaseRevisionError("预览过期"), 409, "STALE_BASE_REVISION"),
        (PreviewDigestMismatchError("摘要不一致"), 409, "PREVIEW_DIGEST_MISMATCH"),
        (MissingResolutionError("缺少处置"), 422, "MISSING_RESOLUTION"),
        (UnknownResolutionError("未知文件"), 422, "UNKNOWN_RESOLUTION"),
        (CorruptedStagingError("暂存损坏"), 409, "STAGING_CORRUPTED"),
        (EmptySelectionError("无可确认"), 422, "EMPTY_SELECTION"),
        (PreviewStatusTransitionError("状态不允许"), 409, "PREVIEW_STATE_CONFLICT"),
        (PreviewNotFoundError("预览不存在"), 404, "PREVIEW_NOT_FOUND"),
        (EvidenceUploadCommitNotFoundError("确认不存在"), 404, "NOT_FOUND"),
    ],
)
def test_evidence_upload_errors_map_to_chinese_envelope(exc, status, code) -> None:
    mapped_status, error = _service_boundary_envelope(exc)
    assert mapped_status == status
    assert error["code"] == code
    assert error["title"]
    assert error["detail"]
    assert error["recovery_action"]
    assert error["correlation_id"]


def test_cleanup_failure_is_500_with_retry_recovery() -> None:
    status, error = _service_boundary_envelope(PreviewCleanupFailedError("清理失败"))
    assert status == 500
    assert error["code"] == "PREVIEW_CLEANUP_FAILED"
    assert "重试" in error["recovery_action"]
    # 不泄露暂存目录/内部细节。
    assert "staging/" not in error["detail"]


def test_generic_upload_error_maps_with_chinese_shell() -> None:
    exc = EvidenceUploadServiceError("补充资料预览缺少前序快照引用，拒绝确认")
    status, error = _service_boundary_envelope(exc)
    assert status == 422
    assert error["code"] == "EVIDENCE_UPLOAD_REJECTED"
    # 标题/恢复动作是固定中文，不携带具体内部内容；服务中文原因进入 detail。
    assert "sha256" not in error["title"].lower()
    assert error["detail"]
    assert error["recovery_action"]
