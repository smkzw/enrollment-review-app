"""人工事实修订 HTTP API：预览、提交持久任务与历史回看。"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from fastapi import status as http_status

from app.api.v2.fact_correction_schemas import (
    FactCorrectionHistoryDTO,
    FactCorrectionPreviewDTO,
    FactCorrectionRequest,
    FactCorrectionSubmitDTO,
    correction_dto,
    preview_dto,
    request_updates,
)
from app.api.v2.vocabulary import JOB_STATE_LABELS, job_recovery_action
from app.services.evidence_app_errors import translate_storage_error
from app.services.evidence_api_read_service import EvidenceApiReadService
from app.services.fact_correction_job_service import FactCorrectionJobService
from app.services.fact_correction_service import (
    FactCorrectionError,
    authority_from_episode,
    list_fact_correction_history,
    preview_fact_correction,
)

router = APIRouter(prefix="/api/v2", tags=["v2-fact-corrections"])

_UNKNOWN_STATE_LABEL = "状态待更新"


def _read(request: Request) -> EvidenceApiReadService:
    return request.app.state.evidence_api_read_service


def _jobs(request: Request) -> FactCorrectionJobService:
    return request.app.state.fact_correction_job_service


def _session(request: Request):
    return request.app.state.session_factory()


def _raise_translated(exc: Exception) -> None:
    translated = translate_storage_error(exc)
    if translated is not None:
        raise translated from exc
    if isinstance(exc, FactCorrectionError):
        raise exc
    raise exc


def _require_episode_scope(request: Request, subject_id: str, review_episode_id: str) -> None:
    _read(request).require_subject_episode(subject_id, review_episode_id)


@router.post(
    "/subjects/{subject_id}/review-episodes/{review_episode_id}/fact-corrections/preview",
    response_model=FactCorrectionPreviewDTO,
)
def preview_correction(
    subject_id: str,
    review_episode_id: str,
    body: FactCorrectionRequest,
    request: Request,
) -> FactCorrectionPreviewDTO:
    _require_episode_scope(request, subject_id, review_episode_id)
    with _session(request) as session:
        try:
            authority = authority_from_episode(session, review_episode_id)
            preview = preview_fact_correction(
                session,
                authority=authority,
                target_kind=body.target_kind,
                target_id=body.target_id,
                locator_ids=body.locator_ids,
                updates=request_updates(body),
            )
        except Exception as exc:  # noqa: BLE001 - 边界统一翻译
            _raise_translated(exc)
            raise
    return preview_dto(preview)


@router.post(
    "/subjects/{subject_id}/review-episodes/{review_episode_id}/fact-corrections",
    response_model=FactCorrectionSubmitDTO,
    status_code=http_status.HTTP_201_CREATED,
)
def submit_correction(
    subject_id: str,
    review_episode_id: str,
    body: FactCorrectionRequest,
    request: Request,
    response: Response,
) -> FactCorrectionSubmitDTO:
    _require_episode_scope(request, subject_id, review_episode_id)
    if body.reason is None or not body.reason.strip():
        from app.services.evidence_app_errors import AppFactCorrectionError

        raise AppFactCorrectionError("提交修订必须填写理由。")
    operator_id = body.operator_id or "local-reviewer"
    try:
        result = _jobs(request).create_or_reuse_job(
            authority=_authority(request, review_episode_id),
            target_kind=body.target_kind,
            target_id=body.target_id,
            locator_ids=body.locator_ids,
            reason=body.reason,
            operator_id=operator_id,
            updates=request_updates(body),
            created_by=operator_id,
        )
    except Exception as exc:  # noqa: BLE001 - 边界统一翻译
        _raise_translated(exc)
        raise
    if not result.created:
        response.status_code = http_status.HTTP_200_OK
    return FactCorrectionSubmitDTO(
        job_id=result.job_id,
        correction_id=result.correction_id,
        created=result.created,
        state=result.status,
        state_label=JOB_STATE_LABELS.get(result.status, _UNKNOWN_STATE_LABEL),
        recovery_action=job_recovery_action(result.status),
    )


def _authority(request: Request, review_episode_id: str):
    with _session(request) as session:
        return authority_from_episode(session, review_episode_id)


@router.get(
    "/subjects/{subject_id}/review-episodes/{review_episode_id}/fact-corrections",
    response_model=FactCorrectionHistoryDTO,
)
def list_corrections(
    subject_id: str, review_episode_id: str, request: Request
) -> FactCorrectionHistoryDTO:
    _require_episode_scope(request, subject_id, review_episode_id)
    with _session(request) as session:
        try:
            items = list_fact_correction_history(session, review_episode_id)
        except Exception as exc:  # noqa: BLE001 - 边界统一翻译
            _raise_translated(exc)
            raise
    return FactCorrectionHistoryDTO(
        subject_id=subject_id,
        review_episode_id=review_episode_id,
        items=[
            correction_dto(
                item.correction,
                patient_profile_revision_id=item.patient_profile_revision_id,
                patient_profile_revision=item.patient_profile_revision,
            )
            for item in items
        ],
    )
