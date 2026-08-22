"""Slice 4.4 稳定应用错误类型（WP-44C 应用层错误所有权）。

应用错误由应用层（``evidence_api_*`` 服务）拥有：存储/服务层失败在服务边界翻译为
稳定的 ``EvidenceAppError`` 子类，API 错误映射器（``app/api/v2/errors.py``）只
导入本模块，不再导入存储层异常类（含经命令服务再导出的路径）。

约定：
- 每个错误携带 HTTP 状态、稳定机器 ``code``、中文 ``title``/``recovery`` 与安全的
  ``detail``；写侧 409 额外携带结构化 ``context()``（``submitted`` /
  ``current_record`` / ``field_diff``，待核对/门禁失败列出实际门禁）；
- 不得在 detail/context 中暴露 ORM 对象、内部枚举对象、绝对路径、payload/hash、
  堆栈或存储异常原文；
- ``app_error_boundary`` 装饰器把服务公共方法边界上未翻译的存储/服务异常转换为
  稳定应用错误（未知异常归入 ``AppInternalError``）。

本模块不导入任何存储异常类到模块顶层，仅在 ``translate`` 内部延迟导入，避免循环
依赖。
"""

from __future__ import annotations

import functools
from typing import Any

__all__ = [
    "AppActivationGateError",
    "AppAlreadyCurrentVersionError",
    "AppBuildConfigurationError",
    "AppBuildFailedError",
    "AppCandidateStateConflictError",
    "AppCorrectionConfirmationRequiredError",
    "AppCorrectionRangeError",
    "AppDatabaseBusyError",
    "AppDuplicateRecordError",
    "AppEvidenceReviewIncompleteError",
    "AppEvidenceUploadError",
    "AppIdempotencyConflictError",
    "AppInternalError",
    "AppInvalidReferenceError",
    "AppMetadataUnchangedError",
    "AppNonCompleteRevisionError",
    "AppNotFoundError",
    "AppReferencedDocumentError",
    "AppReviewPendingError",
    "AppRiskReviewError",
    "AppRollbackTargetError",
    "AppScopeMismatchError",
    "AppStaleRevisionError",
    "AppSubjectInUseError",
    "EvidenceAppError",
    "app_error_boundary",
    "is_database_busy_error",
    "is_operational_error",
    "translate_storage_error",
]


class EvidenceAppError(Exception):
    """稳定应用错误基类。"""

    status_code = 500
    code = "INTERNAL_ERROR"
    title = "系统内部错误"
    recovery = "请稍后重试；若问题持续出现，请记录请求时间并联系维护人员。"

    def __init__(self, detail: str | None = None) -> None:
        self._safe_detail = detail
        super().__init__(detail or self.title)

    def detail(self) -> str:
        return self._safe_detail or self.title

    def context(self) -> dict[str, Any] | None:
        return None


# --------------------------------------------------------------------------- 4xx/5xx


class AppNotFoundError(EvidenceAppError):
    status_code = 404
    code = "NOT_FOUND"
    title = "记录不存在"
    recovery = "请检查编号，或返回列表重新选择。"


class AppInvalidReferenceError(EvidenceAppError):
    status_code = 404
    code = "NOT_FOUND"
    title = "关联记录不存在"
    recovery = "请检查引用的项目、受试者或审核节点是否存在后再试。"


class AppWriteConflictError(EvidenceAppError):
    """写操作 409 的统一上下文形状。"""

    def __init__(
        self,
        detail: str | None = None,
        *,
        submitted: dict[str, Any] | None = None,
        current_record: dict[str, Any] | None = None,
        field_diff: dict[str, Any] | None = None,
    ) -> None:
        self.submitted = submitted or {}
        self.current_record = current_record or {}
        self.field_diff = field_diff or {}
        super().__init__(detail)

    def context(self) -> dict[str, Any]:
        return {
            "submitted": self.submitted,
            "current_record": self.current_record,
            "field_diff": self.field_diff,
        }


class AppScopeMismatchError(AppWriteConflictError):
    status_code = 409
    code = "SCOPE_MISMATCH"
    title = "作用域不一致"
    recovery = "请确认当前操作的项目、受试者与审核节点一致后重试；本次操作没有生效。"


class AppRollbackTargetError(AppWriteConflictError):
    status_code = 409
    code = "ROLLBACK_TARGET_INVALID"
    title = "回滚目标不可用"
    recovery = "请选择曾在启用事件中出现且可完整回放的历史版本。"


class AppCandidateStateConflictError(AppWriteConflictError):
    status_code = 409
    code = "CANDIDATE_STATE_CONFLICT"
    title = "处理候选状态不允许该操作"
    recovery = "请刷新候选状态后按最新状态操作。"


class AppAlreadyCurrentVersionError(AppWriteConflictError):
    status_code = 409
    code = "CURRENT_VERSION_UNCHANGED"
    title = "目标已是当前资料版本"
    recovery = "请刷新当前资料版本；如需变更，请选择另一组已完成处理的资料版本。"


class AppCorrectionRangeError(EvidenceAppError):
    status_code = 422
    code = "CORRECTION_RANGE_MISMATCH"
    title = "校对范围与原识别不一致"
    recovery = "请核对原始识别文本的范围与内容后重新提交。"


class AppCorrectionConfirmationRequiredError(EvidenceAppError):
    status_code = 422
    code = "CORRECTION_CONFIRMATION_REQUIRED"
    title = "关键校对需要二次确认"
    recovery = "请提供确认人与确认时间后重新提交。"


class AppReferencedDocumentError(EvidenceAppError):
    status_code = 422
    code = "REFERENCED_DOCUMENT_REJECTED"
    title = "被提及资料操作无法完成"
    recovery = "请修正提交内容后重试。"


class AppRiskReviewError(EvidenceAppError):
    status_code = 422
    code = "RISK_REVIEW_REJECTED"
    title = "识别核对无法保存"
    recovery = "请修正提交内容后重试。"


class AppDatabaseBusyError(EvidenceAppError):
    status_code = 503
    code = "DATABASE_BUSY"
    title = "数据库暂时繁忙"
    recovery = "请稍后重试；系统不会丢失已完成步骤的记录。"


class AppDuplicateRecordError(AppWriteConflictError):
    """记录已存在（非幂等语义的重复）：409。"""

    status_code = 409
    code = "DUPLICATE_RECORD"
    title = "记录已存在"
    recovery = "请使用现有记录，或更换唯一标识后重试。"


class AppSubjectInUseError(EvidenceAppError):
    """受试者已建立审核节点/资料，不允许删除（P4-R04 不可变证据边界）。"""

    status_code = 409
    code = "SUBJECT_IN_USE"
    title = "受试者已纳入审核安排"
    recovery = "已建立审核节点或资料的受试者不能删除；如确属误建，请核对后保留，或在新项目中使用新的受试者代号。"


class AppInternalError(EvidenceAppError):
    status_code = 500
    code = "INTERNAL_ERROR"
    title = "系统内部错误"
    recovery = "请稍后重试；若问题持续出现，请记录请求时间并联系维护人员。"


class AppMetadataUnchangedError(EvidenceAppError):
    status_code = 422
    code = "METADATA_UNCHANGED"
    title = "分类信息没有变化"
    recovery = "请修改资料类型或来源方后再保存。"


class AppEvidenceUploadError(EvidenceAppError):
    """上传工作流的稳定应用错误；API 不识别上传服务或存储异常。"""

    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        title: str,
        recovery: str,
        detail: str,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.title = title
        self.recovery = recovery
        super().__init__(detail)


# --------------------------------------------------------------------------- 带上下文的 409


class AppStaleRevisionError(EvidenceAppError):
    """预期修订号不匹配：保留提交值、当前记录与服务端差异。"""

    status_code = 409
    code = "STALE_REVISION"
    title = "记录内容已经更新"
    recovery = (
        "请先查看系统列出的差异，再基于最新内容重新编辑；本次提交没有覆盖现有记录。"
    )

    def __init__(
        self,
        *,
        entity_type: str,
        entity_id: str,
        expected_revision: int,
        current_revision: int | None,
        submitted: dict[str, Any],
        current_record: dict[str, Any],
        field_diff: dict[str, Any],
        detail: str | None = None,
    ) -> None:
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.expected_revision = expected_revision
        self.current_revision = current_revision
        self.submitted = submitted
        self.current_record = current_record
        self.field_diff = field_diff
        super().__init__(detail)

    def context(self) -> dict[str, Any]:
        return {
            "submitted": self.submitted,
            "current_record": self.current_record,
            "field_diff": self.field_diff,
            "expected_revision": self.expected_revision,
            "current_revision": self.current_revision,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
        }


class AppIdempotencyConflictError(EvidenceAppError):
    """同幂等键已绑定不同命令：409 且不产生新历史。"""

    status_code = 409
    code = "IDEMPOTENCY_CONFLICT"
    title = "重复提交内容不一致"
    recovery = "请更换幂等键重新提交，或保持与上次提交完全一致后重试。"

    def __init__(
        self,
        *,
        submitted: dict[str, Any],
        existing_result: dict[str, Any],
        detail: str | None = None,
        scope: str | None = None,
        idempotency_key: str | None = None,
        current_record: dict[str, Any] | None = None,
        field_diff: dict[str, Any] | None = None,
    ) -> None:
        self.submitted = submitted
        self.existing_result = existing_result
        self.scope = scope
        self.idempotency_key = idempotency_key
        self.current_record = (
            current_record if current_record is not None else existing_result
        )
        self.field_diff = (
            field_diff
            if field_diff is not None
            else _field_diff(submitted, self.current_record)
        )
        super().__init__(detail)

    def context(self) -> dict[str, Any]:
        return {
            "submitted": self.submitted,
            "current_record": self.current_record,
            "field_diff": self.field_diff,
            "existing_result": self.existing_result,
        }


class AppReviewPendingError(EvidenceAppError):
    """构建存在未解除的阻断性识别风险：列出实际未解除风险。"""

    status_code = 409
    code = "REVIEW_PENDING"
    title = "存在未核对的识别风险"
    recovery = "请在页面上核对所列识别风险或提交覆盖校对后重新构建。"

    def __init__(
        self,
        *,
        candidate_id: str,
        candidate_status: str,
        unresolved_gates: list[dict[str, Any]],
        submitted: dict[str, Any],
        detail: str | None = None,
    ) -> None:
        self.candidate_id = candidate_id
        self.candidate_status = candidate_status
        self.unresolved_gates = unresolved_gates
        self.submitted = submitted
        super().__init__(detail)

    def context(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "candidate_status": self.candidate_status,
            "unresolved_gates": self.unresolved_gates,
            "submitted": self.submitted,
            "current_record": {
                "candidate_id": self.candidate_id,
                "candidate_status": self.candidate_status,
            },
            "field_diff": {
                "unresolved_gates": {
                    "current": self.unresolved_gates,
                    "submitted": [],
                }
            },
            "detail": self.detail(),
        }


class AppEvidenceReviewIncompleteError(AppWriteConflictError):
    """资料核对仍有明确待办，后台任务尚不应建立。"""

    status_code = 409
    code = "EVIDENCE_REVIEW_INCOMPLETE"
    title = "资料核对尚未完成"
    recovery = "请按页面列出的待办完成确认、解除或资料关联，再重新生成资料版本。"

    def __init__(
        self,
        *,
        pending_items: list[dict[str, Any]],
        submitted: dict[str, Any],
        detail: str | None = None,
    ) -> None:
        self.pending_items = pending_items
        super().__init__(
            detail,
            submitted=submitted,
            current_record={"pending_items": pending_items},
            field_diff={
                "pending_items": {
                    "current": pending_items,
                    "submitted": [],
                }
            },
        )

    def context(self) -> dict[str, Any]:
        result = super().context()
        result["pending_items"] = self.pending_items
        return result


class AppBuildFailedError(EvidenceAppError):
    """完整处理修订构建失败：列出未通过门禁。"""

    status_code = 409
    code = "REVISION_BUILD_FAILED"
    title = "完整处理修订构建失败"
    recovery = "请按提示补齐缺失内容后重新构建。"

    def __init__(
        self,
        *,
        candidate_id: str,
        candidate_status: str,
        failed_gates: list[dict[str, Any]],
        submitted: dict[str, Any],
        detail: str | None = None,
    ) -> None:
        self.candidate_id = candidate_id
        self.candidate_status = candidate_status
        self.failed_gates = failed_gates
        self.submitted = submitted
        super().__init__(detail)

    def context(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "candidate_status": self.candidate_status,
            "failed_gates": self.failed_gates,
            "submitted": self.submitted,
            "current_record": {
                "candidate_id": self.candidate_id,
                "candidate_status": self.candidate_status,
            },
            "field_diff": {
                "failed_gates": {
                    "current": self.failed_gates,
                    "submitted": [],
                }
            },
            "detail": self.detail(),
        }


class AppBuildConfigurationError(EvidenceAppError):
    """页面与服务的资料处理配置不一致。"""

    status_code = 422
    code = "BUILD_CONFIGURATION_UNAVAILABLE"
    title = "当前资料处理方式已更新"
    recovery = "请刷新页面后重试；系统将自动使用当前的识别核对方式。"


class AppNonCompleteRevisionError(EvidenceAppError):
    """目标不是完整处理修订（base 修订永不可激活/投影校对层）。"""

    status_code = 409
    code = "NON_COMPLETE_REVISION"
    title = "目标不是完整处理修订"
    recovery = "请改用完整处理修订后再操作。"

    def __init__(
        self, *, revision_id: str, submitted: dict[str, Any], detail: str | None = None
    ) -> None:
        self.revision_id = revision_id
        self.submitted = submitted
        super().__init__(detail)

    def context(self) -> dict[str, Any]:
        return {
            "revision_id": self.revision_id,
            "submitted": self.submitted,
            "current_record": {
                "revision_id": self.revision_id,
                "revision_kind": "base",
                "is_activatable": False,
            },
            "field_diff": {
                "revision_kind": {
                    "current": "base",
                    "submitted": "complete",
                }
            },
        }


class AppActivationGateError(EvidenceAppError):
    """激活门禁失败：列出实际未通过门禁。"""

    status_code = 409
    code = "ACTIVATION_GATE_FAILED"
    title = "资料版本未通过启用门禁"
    recovery = "请先补齐启用门禁要求后重试。"

    def __init__(
        self,
        *,
        revision_id: str,
        failed_gates: list[dict[str, Any]],
        submitted: dict[str, Any],
        detail: str | None = None,
    ) -> None:
        self.revision_id = revision_id
        self.failed_gates = failed_gates
        self.submitted = submitted
        super().__init__(detail)

    def context(self) -> dict[str, Any]:
        return {
            "revision_id": self.revision_id,
            "failed_gates": self.failed_gates,
            "submitted": self.submitted,
            "current_record": {
                "revision_id": self.revision_id,
            },
            "field_diff": {
                "failed_gates": {
                    "current": self.failed_gates,
                    "submitted": [],
                }
            },
            "detail": self.detail(),
        }


def _field_diff(submitted: dict[str, Any], existing: dict[str, Any]) -> dict[str, Any]:
    """对两份完整命令计算真实的顶层字段差异。"""
    diff: dict[str, Any] = {}
    for key in sorted(set(submitted) | set(existing)):
        current_value = existing.get(key)
        submitted_value = submitted.get(key)
        if submitted_value != current_value:
            diff[key] = {"current": current_value, "submitted": submitted_value}
    return diff


# --------------------------------------------------------------------------- 翻译


def is_operational_error(exc: Exception) -> bool:
    """SQLAlchemy OperationalError 识别（API 层不直接导入 sqlalchemy）。"""
    from sqlalchemy.exc import OperationalError

    return isinstance(exc, OperationalError)


def is_database_busy_error(exc: Exception) -> bool:
    """SQLite 忙/锁错误识别。"""
    if not is_operational_error(exc):
        return False
    orig = getattr(exc, "orig", None)
    message = str(orig or exc).lower()
    return "database is locked" in message or "database is busy" in message


def translate_storage_error(exc: Exception) -> EvidenceAppError | None:
    """把存储/服务层失败翻译为稳定应用错误（服务边界调用）。

    只返回用户安全的 detail/context；存储异常原文绝不进入用户可见字段。
    未知异常返回 None（调用方归入内部错误）。
    """
    from app.services.evidence_correction_service import (
        CorrectionConfirmationRequiredError,
        CorrectionRangeError,
    )
    from app.services.evidence_referenced_document_service import (
        ReferencedDocumentServiceError,
    )
    from app.services.evidence_revision_builder import (
        MissingMetadataRevisionError,
        MissingRiskScanError,
        UnresolvedBlockingRiskError,
    )
    from app.services.evidence_risk_service import EvidenceRiskScanServiceError
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
    from app.storage.codecs import PersistedContractInvalid
    from app.storage.concurrency import StaleRevisionError
    from app.storage.evidence_locator_repositories import (
        CandidateStateTransitionError,
        LocatorIdentityError,
        OcrRevisionKindError,
        RevisionClosureError,
        Slice44RepositoryError,
    )
    from app.storage.evidence_upload_repositories import (
        EvidenceUploadCommitNotFoundError,
        PreviewNotFoundError,
        PreviewStatusTransitionError,
    )
    from app.storage.idempotency import IdempotencyConflict
    from app.storage.repositories import (
        DuplicateRecordError,
        InvalidReferenceError,
        NotFoundError,
        ScopeViolationError,
    )

    if isinstance(exc, EvidenceAppError):
        return exc
    upload_error_specs: tuple[
        tuple[type[Exception], int, str, str, str, str], ...
    ] = (
        (
            PreviewNotFoundError,
            404,
            "PREVIEW_NOT_FOUND",
            "上传预览不存在",
            "请检查预览编号，或重新选择文件生成预览。",
            "找不到对应的上传预览，可能预览编号有误或预览已被取消。",
        ),
        (
            EvidenceUploadCommitNotFoundError,
            404,
            "NOT_FOUND",
            "确认记录不存在",
            "请检查确认编号，或重新提交上传。",
            "找不到对应的上传确认记录，可能记录编号有误。",
        ),
        (
            PreviewStatusTransitionError,
            409,
            "PREVIEW_STATE_CONFLICT",
            "上传预览状态不允许该操作",
            "请刷新预览状态后重试；已确认的预览不能取消，已取消的预览不能确认。",
            "上传预览当前状态不支持您请求的操作，可能预览已经确认、已取消或正在取消。",
        ),
        (
            EmptyUploadError,
            422,
            "EMPTY_UPLOAD",
            "未选择任何文件",
            "请至少选择一个文件后重新提交。",
            "本次上传没有收到任何文件。",
        ),
        (
            NoEffectiveSnapshotError,
            409,
            "NO_EFFECTIVE_SNAPSHOT",
            "缺少可补充的上一快照",
            "请改用“建立完整资料快照”方式，或先确认一个完整快照后再补充。",
            "该审核节点还没有有效的前序资料快照，无法使用“补充资料”方式上传。",
        ),
        (
            StaleBaseRevisionError,
            409,
            "STALE_BASE_REVISION",
            "预览已过期",
            "请重新生成预览并再次确认。",
            "审核节点资料在预览生成之后发生了变化，当前预览不再有效，系统没有执行本次提交。",
        ),
        (
            PreviewDigestMismatchError,
            409,
            "PREVIEW_DIGEST_MISMATCH",
            "预览内容与确认请求不一致",
            "请刷新预览后重新确认。",
            "确认请求携带的摘要与系统实际保存的预览内容不一致，系统没有执行本次提交。",
        ),
        (
            MissingResolutionError,
            422,
            "MISSING_RESOLUTION",
            "缺少同名文件的处置选择",
            "请为每个冲突文件选择“作为原资料的新版本”或“作为另一份资料并列保留”。",
            "存在名称相同但内容不同的文件，必须明确选择处置方式后才能确认。",
        ),
        (
            UnknownResolutionError,
            422,
            "UNKNOWN_RESOLUTION",
            "处置选择包含未知文件",
            "请重新生成预览后，仅对预览列出的冲突文件选择处置方式。",
            "处置选择中引用了预览不存在的文件，系统没有执行本次提交。",
        ),
        (
            CorruptedStagingError,
            409,
            "STAGING_CORRUPTED",
            "暂存资料已失效",
            "请重新生成预览并再次确认；原预览已不可用。",
            "预览对应的暂存文件缺失或内容与预览记录不一致，不能确认。",
        ),
        (
            PreviewCleanupFailedError,
            500,
            "PREVIEW_CLEANUP_FAILED",
            "取消清理未完成",
            "请重试取消以完成清理；系统不会使用该预览进行确认。",
            "预览已记录取消，但临时文件清理尚未完成。",
        ),
        (
            EmptySelectionError,
            422,
            "EMPTY_SELECTION",
            "没有可确认的资料",
            "请重新选择文件并生成预览后确认。",
            "预览中没有可进入快照的文件（例如全部文件不受支持或无法读取）。",
        ),
    )
    for error_type, status_code, code, title, recovery, detail in upload_error_specs:
        if isinstance(exc, error_type):
            return AppEvidenceUploadError(
                status_code=status_code,
                code=code,
                title=title,
                recovery=recovery,
                detail=detail,
            )
    if isinstance(exc, EvidenceUploadServiceError):
        return AppEvidenceUploadError(
            status_code=422,
            code="EVIDENCE_UPLOAD_REJECTED",
            title="上传预览无法确认",
            recovery="请重新生成预览后重试；本次操作没有生效。",
            detail="上传预览未能通过完整性检查，系统没有执行本次提交。",
        )
    if is_database_busy_error(exc):
        return AppDatabaseBusyError("本机数据库当前正忙，本次操作没有完成。")
    if isinstance(exc, StaleRevisionError):
        return AppStaleRevisionError(
            entity_type=exc.entity_type,
            entity_id=exc.entity_id,
            expected_revision=exc.expected_revision,
            current_revision=exc.current_revision,
            submitted={},
            current_record={},
            field_diff={
                field: change.as_dict()
                for field, change in sorted(exc.field_diff.items())
            },
            detail="这条记录在您打开之后发生了变化，当前内容与您准备提交的内容不一致。",
        )
    if isinstance(exc, IdempotencyConflict):
        return AppIdempotencyConflictError(
            submitted={},
            existing_result={},
            detail="同一个幂等键之前已绑定不同的请求内容，系统不会静默复用旧结果。",
        )
    if isinstance(exc, NotFoundError):
        return AppNotFoundError("找不到对应的记录，可能编号有误或记录已被移除。")
    if isinstance(exc, InvalidReferenceError):
        return AppInvalidReferenceError(str(exc))
    if isinstance(exc, ScopeViolationError):
        return AppScopeMismatchError(str(exc))
    if isinstance(exc, DuplicateRecordError):
        return AppDuplicateRecordError(str(exc))
    if isinstance(exc, PersistedContractInvalid):
        return AppInternalError(
            "持久化内容未能通过完整性校验，系统拒绝继续发布不完整结果。"
        )
    if isinstance(exc, CorrectionRangeError):
        return AppCorrectionRangeError(str(exc))
    if isinstance(exc, CorrectionConfirmationRequiredError):
        return AppCorrectionConfirmationRequiredError(str(exc))
    if isinstance(exc, ReferencedDocumentServiceError):
        return AppReferencedDocumentError(str(exc))
    if isinstance(exc, EvidenceRiskScanServiceError):
        return AppRiskReviewError(str(exc))
    if isinstance(exc, CandidateStateTransitionError):
        return AppCandidateStateConflictError(str(exc))
    if isinstance(exc, OcrRevisionKindError):
        return AppNonCompleteRevisionError(
            revision_id=getattr(exc, "revision_id", "unknown"),
            submitted={},
            detail="基础处理修订只冻结页产物与识别结果，永不可激活。",
        )
    if isinstance(
        exc,
        (
            MissingMetadataRevisionError,
            MissingRiskScanError,
            UnresolvedBlockingRiskError,
            RevisionClosureError,
            LocatorIdentityError,
            Slice44RepositoryError,
        ),
    ):
        if isinstance(exc, MissingMetadataRevisionError):
            failed_gates = [{"gate": "metadata", "detail": "缺少当前资料的有效分类修订"}]
        elif isinstance(exc, MissingRiskScanError):
            failed_gates = [{"gate": "risk", "detail": "缺少当前识别版本的风险扫描结果"}]
        elif isinstance(exc, UnresolvedBlockingRiskError):
            failed_gates = [{"gate": "risk", "detail": "存在尚未完成核对的关键识别风险"}]
        else:
            failed_gates = [{"gate": "closure", "detail": "完整处理修订闭包不完整"}]
        return AppBuildFailedError(
            candidate_id="",
            candidate_status="retryable_failure",
            failed_gates=failed_gates,
            submitted={},
            detail="完整处理修订闭包不完整，请重新构建。",
        )
    return None


def app_error_boundary(method):
    """服务公共方法边界：未翻译的异常 -> 稳定应用错误。"""

    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except EvidenceAppError:
            raise
        except Exception as exc:
            translated = translate_storage_error(exc)
            if translated is not None:
                raise translated from exc
            # 不属于已知应用/存储异常的错误交给 API 统一内部错误兜底。
            raise

    return wrapper
