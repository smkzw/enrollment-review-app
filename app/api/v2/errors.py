"""V2 API 错误信封：异常 -> 自然中文问题/影响/恢复动作。

规范（.trellis/spec/backend/error-handling.md、design.md §8）：

- ``code`` 供程序和测试使用，用户界面不默认显示；
- ``title``/``detail``/``recovery_action`` 为自然中文，不泄露 SQL、堆栈、
  枚举或日志词；
- 所有信封携带 ``correlation_id`` 便于本机日志关联。
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from app.services.protocol_draft_service import DraftEditBoundaryError
from app.services.protocol_workbench_service import ProtocolWorkbenchError
from app.storage.codecs import PersistedContractInvalid
from app.storage.concurrency import StaleRevisionError
from app.storage.idempotency import IdempotencyConflict
from app.workflow.errors import (
    JobNotFoundError,
    JobStateConflictError,
    InvalidJobDefinitionError,
    LeaseLostError,
    StepDeferredError,
    StepMismatchError,
    WorkflowError,
)

logger = logging.getLogger(__name__)


def _is_sqlite_busy(exc: OperationalError) -> bool:
    message = str(exc.orig or exc).lower()
    return "database is locked" in message or "database is busy" in message


class ErrorSpec:
    def __init__(
        self,
        status: int,
        code: str,
        title: str,
        detail: str,
        recovery: str,
    ) -> None:
        self.status = status
        self.code = code
        self.title = title
        self.detail = detail
        self.recovery = recovery


_INTERNAL = ErrorSpec(
    500,
    "INTERNAL_ERROR",
    "系统内部错误",
    "发生了未预期的系统错误。",
    "请稍后重试；若问题持续出现，请记录请求时间并联系维护人员。",
)

_FIELD_LABELS = {
    "idempotency_key": "重复提交标识",
    "job_type": "任务类型",
    "payload": "任务内容",
    "steps": "任务步骤",
    "step_id": "步骤编号",
    "name": "步骤名称",
    "max_attempts": "最多尝试次数",
    "retryable": "是否允许重试",
    "depends_on": "前置步骤",
}


def _validation_context(exc: RequestValidationError) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    reason_labels = {
        "missing": "尚未填写",
        "extra_forbidden": "包含系统不识别的内容",
        "string_too_short": "内容过短",
        "string_too_long": "内容过长",
        "greater_than_equal": "数值小于允许范围",
        "less_than_equal": "数值超过允许范围",
        "int_parsing": "应填写整数",
        "bool_parsing": "应选择是或否",
    }
    for error in exc.errors():
        loc = [part for part in error.get("loc", ()) if part != "body"]
        labels: list[str] = []
        for part in loc:
            if isinstance(part, int):
                labels.append(f"第{part + 1}项")
            else:
                labels.append(_FIELD_LABELS.get(str(part), "相关内容"))
        issues.append(
            {
                "field": " · ".join(labels) or "请求内容",
                "issue": reason_labels.get(
                    str(error.get("type", "")), "内容不符合填写要求"
                ),
            }
        )
    return {"fields": issues}


def map_exception(exc: Exception) -> tuple[int, dict[str, Any]]:
    """异常 -> (HTTP 状态, 信封 dict)；未知异常归入内部错误，绝不泄露技术细节。"""
    if isinstance(exc, IdempotencyConflict):
        spec = ErrorSpec(
            409,
            "IDEMPOTENCY_CONFLICT",
            "重复提交内容不一致",
            "同一个幂等键之前已绑定不同的请求内容，系统不会静默复用旧结果。",
            "请更换幂等键重新提交，或保持与上次提交完全一致后重试。",
        )
        context: dict[str, Any] | None = None
    elif isinstance(exc, StaleRevisionError):
        spec = ErrorSpec(
            409,
            "STALE_REVISION",
            "记录内容已经更新",
            "这条记录在您打开之后发生了变化，当前内容与您准备提交的内容不一致。",
            "请先查看系统列出的差异，再基于最新内容重新编辑；本次提交没有覆盖现有记录。",
        )
        context = exc.as_dict()
        context.pop("code", None)
    elif isinstance(exc, LeaseLostError):
        spec = ErrorSpec(
            409,
            "LEASE_LOST",
            "任务执行权已失效",
            "该任务的执行权已被其他执行者接管或服务已重启，本次提交的结果未被采用。",
            "无需手动处理；系统会从最后成功的检查点自动恢复，请稍后刷新任务状态。",
        )
        context = None
    elif isinstance(exc, JobStateConflictError):
        spec = ErrorSpec(
            409,
            "JOB_STATE_CONFLICT",
            "任务状态不允许该操作",
            "任务当前状态不支持您请求的操作。",
            "请刷新任务状态后，根据最新状态选择合适操作。",
        )
        context = {"current_state": exc.current_state}
    elif isinstance(exc, InvalidJobDefinitionError):
        spec = ErrorSpec(
            422,
            "INVALID_JOB_DEFINITION",
            "任务步骤设置不完整",
            "任务步骤存在重复、缺失或循环依赖，系统没有创建任务。",
            "请检查每个步骤的前置条件后重新提交。",
        )
        context = None
    elif isinstance(exc, JobNotFoundError):
        spec = ErrorSpec(
            404,
            "NOT_FOUND",
            "任务不存在",
            "找不到对应的任务，可能已被清理或任务编号有误。",
            "请检查任务编号，或返回任务列表重新选择。",
        )
        context = None
    elif isinstance(exc, ProtocolWorkbenchError):
        status = 404 if exc.code.endswith("_NOT_FOUND") else 409
        if exc.code in {"IDENTITY_CONFIRM_INVALID", "SOURCE_INGESTION_FAILED"}:
            status = 422
        spec = ErrorSpec(
            status,
            exc.code,
            exc.title,
            exc.detail,
            exc.recovery,
        )
        context = exc.context
    elif isinstance(exc, DraftEditBoundaryError):
        spec = ErrorSpec(
            422,
            getattr(exc, "code", "DRAFT_EDIT_BOUNDARY"),
            "草稿编辑超出允许范围",
            str(exc),
            "请只修正与当前方案来源一致的语义内容，不要增删冻结目录或改写流程结构。",
        )
        context = None
    elif isinstance(exc, PersistedContractInvalid):
        spec = ErrorSpec(
            500,
            "PERSISTED_CONTRACT_INVALID",
            "持久化内容校验失败",
            "任务相关的持久化记录未能通过完整性校验，系统拒绝继续发布不完整结果。",
            "请稍后重试；若问题持续出现，请使用已验证的备份恢复或联系维护人员。",
        )
        context = None
    elif isinstance(exc, OperationalError) and _is_sqlite_busy(exc):
        spec = ErrorSpec(
            503,
            "DATABASE_BUSY",
            "数据库暂时繁忙",
            "本机数据库当前正忙，本次操作没有完成，已完成的步骤记录不受影响。",
            "请稍后重试；系统不会丢失已完成步骤的记录。",
        )
        context = None
    elif isinstance(exc, OperationalError):
        spec = ErrorSpec(
            500,
            "LOCAL_DATA_ERROR",
            "本地数据读取失败",
            "系统未能完成本次本地数据操作，本次操作没有生效。",
            "请重新打开系统后再试；若仍然失败，请联系维护人员检查本地数据文件。",
        )
        context = None
    elif isinstance(exc, (StepDeferredError, StepMismatchError, WorkflowError)):
        spec = ErrorSpec(
            409,
            getattr(exc, "code", "JOB_STATE_CONFLICT"),
            "任务状态不允许该操作",
            "任务当前状态不支持您请求的操作。",
            "请刷新任务状态后，根据最新状态选择合适操作。",
        )
        context = None
    else:
        spec = _INTERNAL
        context = None
    return spec.status, {
        "error": {
            "code": spec.code,
            "title": spec.title,
            "detail": spec.detail,
            "recovery_action": spec.recovery,
            "correlation_id": uuid4().hex,
            "context": context,
        }
    }


def register_error_handlers(app: FastAPI) -> None:
    async def _typed_handler(request: Request, exc: Exception) -> JSONResponse:
        status, content = map_exception(exc)
        return JSONResponse(status_code=status, content=content)

    async def _validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "INVALID_REQUEST",
                    "title": "请求参数不合法",
                    "detail": "请求内容不符合接口要求，系统没有执行任何写入。",
                    "recovery_action": "请按提示修改对应内容后重新提交。",
                    "correlation_id": uuid4().hex,
                    "context": _validation_context(exc),
                }
            },
        )

    async def _fallback_handler(request: Request, exc: Exception) -> JSONResponse:
        del request
        if not isinstance(exc, (RequestValidationError,)):
            logger.exception("V2 API 未处理异常（关联号见响应）: %r", exc)
        status, content = map_exception(exc)
        return JSONResponse(status_code=status, content=content)

    for exc_type in (
        IdempotencyConflict,
        StaleRevisionError,
        LeaseLostError,
        JobStateConflictError,
        InvalidJobDefinitionError,
        JobNotFoundError,
        ProtocolWorkbenchError,
        DraftEditBoundaryError,
        PersistedContractInvalid,
        OperationalError,
        StepDeferredError,
        StepMismatchError,
        WorkflowError,
    ):
        app.add_exception_handler(exc_type, _typed_handler)
    app.add_exception_handler(RequestValidationError, _validation_handler)
    app.add_exception_handler(Exception, _fallback_handler)
