"""事实规范化命令 HTTP API：从活动证据派生权威并幂等创建持久任务。"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from fastapi import status as http_status

from app.api.v2.fact_normalization_schemas import (
    FactNormalizationRequest,
    FactNormalizationSubmitDTO,
)
from app.api.v2.vocabulary import JOB_STATE_LABELS, job_recovery_action
from app.services.evidence_app_errors import EvidenceAppError, translate_storage_error
from app.services.evidence_api_read_service import EvidenceApiReadService
from app.services.fact_normalization_command_service import (
    FactNormalizationCommandService,
)

router = APIRouter(prefix="/api/v2", tags=["v2-fact-normalization"])

_UNKNOWN_STATE_LABEL = "状态待更新"


def _read(request: Request) -> EvidenceApiReadService:
    return request.app.state.evidence_api_read_service


def _commands(request: Request) -> FactNormalizationCommandService:
    return request.app.state.fact_normalization_command_service


def _raise_translated(exc: Exception) -> None:
    if isinstance(exc, EvidenceAppError):
        raise exc
    translated = translate_storage_error(exc)
    if translated is not None:
        raise translated from exc
    raise exc


@router.post(
    "/subjects/{subject_id}/review-episodes/{review_episode_id}/fact-normalization-jobs",
    response_model=FactNormalizationSubmitDTO,
    status_code=http_status.HTTP_201_CREATED,
)
def create_fact_normalization_job(
    subject_id: str,
    review_episode_id: str,
    body: FactNormalizationRequest,
    request: Request,
    response: Response,
) -> FactNormalizationSubmitDTO:
    """只接受受试者/审核节点与可选意图；权威与配置由服务端派生。"""
    _read(request).require_subject_episode(subject_id, review_episode_id)
    try:
        result = _commands(request).create_or_reuse(
            subject_id=subject_id,
            review_episode_id=review_episode_id,
            idempotency_intent=body.idempotency_intent,
        )
    except Exception as exc:  # noqa: BLE001 - 边界统一翻译
        _raise_translated(exc)
        raise
    if not result.created:
        response.status_code = http_status.HTTP_200_OK
    return FactNormalizationSubmitDTO(
        job_id=result.job_id,
        run_id=result.run_id,
        created=result.created,
        state=result.status,
        state_label=JOB_STATE_LABELS.get(result.status, _UNKNOWN_STATE_LABEL),
        recovery_action=job_recovery_action(result.status),
    )
