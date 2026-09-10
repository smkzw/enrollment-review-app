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

from app.services.evidence_app_errors import (
    EvidenceAppError,
)
from app.services.protocol_draft_service import DraftEditBoundaryError
from app.services.protocol_workbench_service import ProtocolWorkbenchError
from app.workflow.errors import (
    InvalidJobDefinitionError,
    JobNotFoundError,
    JobStateConflictError,
    LeaseLostError,
    StepDeferredError,
    StepMismatchError,
    WorkflowError,
)

logger = logging.getLogger(__name__)


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
    "file": "方案文件",
    "actor": "操作人",
    "protocol_code": "方案编号",
    "project_name": "项目名称",
    "project_code": "项目代号",
    "official_version": "正式版本",
    "official_date_value": "版本日期",
    "official_date_precision": "版本日期精度",
    "study_phase": "研究期别",
    "selected_candidate_ids": "来源候选",
    "subject_id": "受试者编号",
    "subject_code": "受试者代号",
    "project_id": "项目编号",
    "center_code": "中心编号",
    "center_name": "中心名称",
    "sex": "性别",
    "age_years": "年龄",
    "review_episode_id": "审核节点编号",
    "rule_set_id": "规则集编号",
    "rule_set_revision": "规则集修订号",
    "protocol_version_id": "方案版本",
    "evidence_snapshot_id": "证据快照编号",
    "stage": "审核阶段",
    "anchor_dates": "锚定日期",
    "due_at": "截止时间",
    "revision": "修订号",
    "target_kind": "修订对象类型",
    "target_id": "修订对象编号",
    "locator_ids": "原文定位",
    "reason": "修订理由",
    "operator_id": "操作者",
    "asserted_object": "被断言对象",
    "value": "记录值",
    "unit": "单位",
    "date_range": "日期范围",
    "polarity": "肯定或否定",
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
    """异常 -> (HTTP 状态, 信封 dict)；未知异常归入内部错误，绝不泄露技术细节。

    应用错误由应用服务拥有；本映射器不识别或翻译任何存储实现
    异常。存储失败若逃逸服务边界，只能作为未处理的内部错误，避免 API
    层反向依赖存储类型。
    """
    if isinstance(exc, EvidenceAppError):
        spec = ErrorSpec(
            exc.status_code,
            exc.code,
            exc.title,
            exc.detail(),
            exc.recovery,
        )
        context = exc.context()
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

    async def _validation_handler(request: Request, exc: Exception) -> JSONResponse:
        del request
        if not isinstance(exc, RequestValidationError):
            raise exc
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
        EvidenceAppError,
        LeaseLostError,
        JobStateConflictError,
        InvalidJobDefinitionError,
        JobNotFoundError,
        ProtocolWorkbenchError,
        DraftEditBoundaryError,
        StepDeferredError,
        StepMismatchError,
        WorkflowError,
    ):
        app.add_exception_handler(exc_type, _typed_handler)
    app.add_exception_handler(RequestValidationError, _validation_handler)
    app.add_exception_handler(Exception, _fallback_handler)
