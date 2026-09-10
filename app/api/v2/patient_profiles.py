"""Phase 5 Patient Profile HTTP API（Slice 5.5，worker_03，薄路由）。

路由只做协议转换与作用域核对，不做领域判断：调用
:class:`~app.services.patient_profile_service.PatientProfileService` 读取不可变
Profile revision（worker_02 已接受的 ``get/latest/history`` 契约），把领域合同映射
为中文原生 DTO。本模块不导入 SQLAlchemy 或 ``app.storage``（薄 API 边界验收由
AST 测试强制）：

- ``GET /api/v2/subjects/{subject_id}/review-episodes/{review_episode_id}/patient-profile``
  当前链头 Profile（对照审核节点活动指针派生 ``stale``；尚未生成时 404，不返回
  空成功 Profile）；
- ``GET /api/v2/subjects/{subject_id}/review-episodes/{review_episode_id}/patient-profile/history``
  全部历史 revision（按 revision 升序，逐条派生 stale；尚未生成时返回空列表）；
- ``GET /api/v2/subjects/{subject_id}/patient-profile-revisions/{patient_profile_revision_id}``
  按稳定 ID 读取冻结 revision（不派生 stale；跨受试者一律 404）。

作用域：审核节点必须属于路径受试者（跨项目/跨受试者 404）；按 ID 读取时以
revision 权威元组中的受试者与路径受试者核对。会话经应用会话工厂获取，错误统一经
``errors.py`` 信封返回（存储 NotFoundError 由应用错误翻译函数映射为 404 中文
信封，投影完整性失败保持大声内部错误，绝不静默降级）。
"""
from __future__ import annotations

from fastapi import APIRouter, Request

from app.api.v2.patient_profile_schemas import (
    PatientProfileHistoryDTO,
    PatientProfileRevisionDTO,
    profile_locator_ids,
    profile_revision_dto,
)
from app.domain.contracts.patient_profile_v2 import PatientProfileRevisionV2
from app.services.evidence_app_errors import (
    AppNotFoundError,
    translate_storage_error,
)
from app.services.evidence_api_read_service import EvidenceApiReadService
from app.services.patient_profile_service import PatientProfileService

router = APIRouter(prefix="/api/v2", tags=["v2-patient-profile"])


def _read(request: Request) -> EvidenceApiReadService:
    return request.app.state.evidence_api_read_service


def _profile(request: Request) -> PatientProfileService:
    return request.app.state.patient_profile_service


def _session(request: Request):
    """应用会话工厂：路由只调用工厂，不导入 SQLAlchemy/存储类型。"""
    return request.app.state.session_factory()


def _raise_translated(exc: Exception) -> None:
    """存储/服务层失败 -> 稳定应用错误信封；未知异常原样上抛（内部错误兜底）。

    仅做协议转换：Profile 服务未装饰应用错误边界，路由在此补回与 Phase 4 读取
    服务一致的错误翻译，避免 404 类存储异常变成 500。
    """
    translated = translate_storage_error(exc)
    if translated is not None:
        raise translated from exc
    raise exc


def _require_episode_scope(request: Request, subject_id: str, review_episode_id: str) -> None:
    """派生并重验作用域：审核节点必须属于路径受试者（跨对象一律 404）。"""
    _read(request).require_subject_episode(subject_id, review_episode_id)


def _revision_dto(
    request: Request, revision: PatientProfileRevisionV2
) -> PatientProfileRevisionDTO:
    """补齐 revision 引用的真实定位详情后做协议转换。"""
    locator_ids = profile_locator_ids(revision)
    locators = _read(request).locators_by_ids(
        locator_ids,
        complete_processing_revision_id=(
            revision.authority.complete_processing_revision_id
        ),
    )
    return profile_revision_dto(revision, locators=locators)


@router.get(
    "/subjects/{subject_id}/review-episodes/{review_episode_id}/patient-profile",
    response_model=PatientProfileRevisionDTO,
)
def get_latest_patient_profile(
    subject_id: str, review_episode_id: str, request: Request
) -> PatientProfileRevisionDTO:
    """当前链头 Patient Profile；冻结权威落后于活动指针时派生 ``stale``。

    尚未生成任何 revision 时返回 404（``generating``/``failed`` 是显式状态记录，
    不会伪装成空成功 Profile；读取派生缺上下文时大声失败）。
    """
    _require_episode_scope(request, subject_id, review_episode_id)
    with _session(request) as session:
        try:
            revision = _profile(request).latest(session, review_episode_id)
        except Exception as exc:  # noqa: BLE001 - 边界统一翻译
            _raise_translated(exc)
            raise
    if revision is None:
        raise AppNotFoundError("该审核节点还没有生成病历档案。")
    return _revision_dto(request, revision)


@router.get(
    "/subjects/{subject_id}/review-episodes/{review_episode_id}/patient-profile/history",
    response_model=PatientProfileHistoryDTO,
)
def list_patient_profile_history(
    subject_id: str, review_episode_id: str, request: Request
) -> PatientProfileHistoryDTO:
    """全部历史 revision（按 revision 升序，逐条对照当前权威派生 stale）。

    审核节点不存在或不属于路径受试者 -> 404；尚未生成时返回空列表。
    """
    _require_episode_scope(request, subject_id, review_episode_id)
    with _session(request) as session:
        try:
            revisions = _profile(request).history(session, review_episode_id)
        except Exception as exc:  # noqa: BLE001 - 边界统一翻译
            _raise_translated(exc)
            raise
    return PatientProfileHistoryDTO(
        subject_id=subject_id,
        review_episode_id=review_episode_id,
        items=[_revision_dto(request, item) for item in revisions],
    )


@router.get(
    "/subjects/{subject_id}/patient-profile-revisions/{patient_profile_revision_id}",
    response_model=PatientProfileRevisionDTO,
)
def get_patient_profile_revision(
    subject_id: str, patient_profile_revision_id: str, request: Request
) -> PatientProfileRevisionDTO:
    """按稳定 ID 读取一条冻结 revision（不派生 stale，历史回放原样返回）。

    revision 不存在或属于其他受试者 -> 404；读取永不静默改写历史行。
    """
    with _session(request) as session:
        try:
            revision = _profile(request).get(session, patient_profile_revision_id)
        except Exception as exc:  # noqa: BLE001 - 边界统一翻译
            _raise_translated(exc)
            raise
    if revision.authority.subject_id != subject_id:
        raise AppNotFoundError("找不到对应的病历档案。")
    return _revision_dto(request, revision)
