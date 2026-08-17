"""V2 方案解构工作台 API：上传、身份确认、草稿 revision 与首次发布。

路由只做协议转换与中文投影，领域判断委托
:class:`app.services.protocol_workbench_service.ProtocolWorkbenchService`。
"""
from __future__ import annotations

import tempfile
from datetime import timezone
from pathlib import Path

from fastapi import APIRouter, File, Form, Request, Response, UploadFile, status as http_status

from app.api.v2.protocol_schemas import (
    ConfirmIdentityRequest,
    DraftActionRequest,
    DraftRevisionResponse,
    FeedbackRequest,
    IdentityDecisionDTO,
    IdentityReviewResponse,
    IntegrityCheckDTO,
    IntegrityIssueDTO,
    IntegrityResponse,
    ManualEditRequest,
    ProtocolSessionResponse,
    PublishRequest,
    PublishResponse,
    SourcesResponse,
    StartDeconstructionResponse,
)
from app.api.v2.vocabulary import (
    DRAFT_REASON_LABELS,
    DRAFT_STATUS_LABELS,
    METADATA_STATUS_LABELS,
    study_phase_label,
)
from app.domain.contracts.protocol_metadata import ProtocolIdentityDecision
from app.services.protocol_workbench_service import ProtocolWorkbenchService

router = APIRouter(prefix="/api/v2/protocol/deconstructions", tags=["v2-protocol"])


def _service(request: Request) -> ProtocolWorkbenchService:
    return request.app.state.protocol_workbench_service


def _as_utc(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _session_dto(view) -> ProtocolSessionResponse:
    return ProtocolSessionResponse(
        job_id=view.job_id,
        job_type=view.job_type,
        state=view.state,
        state_label=view.state_label,
        progress_completed=view.progress_completed,
        progress_total=view.progress_total,
        session_kind=view.session_kind,
        awaiting_user=view.awaiting_user,
        awaiting_user_label=view.awaiting_user_label,
        source_artifact_id=view.source_artifact_id,
        file_name=view.file_name,
        snapshot_id=view.snapshot_id,
        draft_id=view.draft_id,
        draft_revision_id=view.draft_revision_id,
        draft_revision_number=view.draft_revision_number,
        draft_status=view.draft_status,
        draft_status_label=(
            DRAFT_STATUS_LABELS.get(view.draft_status, view.draft_status)
            if view.draft_status
            else None
        ),
        selected_phase=view.selected_phase,
        selected_phase_label=view.selected_phase_label,
        protocol_code=view.protocol_code,
        official_version=view.official_version,
        recovery_checkpoint_id=view.recovery_checkpoint_id,
        recovery_step_id=view.recovery_step_id,
        next_action=view.next_action,
        publishable=view.publishable,
    )


def _identity_dto(decision: ProtocolIdentityDecision) -> IdentityDecisionDTO:
    return IdentityDecisionDTO(
        identity_decision_id=decision.identity_decision_id,
        snapshot_id=decision.snapshot_id,
        status=decision.status.value,
        status_label=METADATA_STATUS_LABELS.get(
            decision.status.value, decision.status.value
        ),
        project_name=decision.project_name,
        project_code=decision.project_code,
        protocol_code=decision.protocol_code,
        official_version=decision.official_version,
        official_date_value=(
            decision.official_date.value if decision.official_date else None
        ),
        official_date_precision=(
            decision.official_date.precision.value if decision.official_date else None
        ),
        study_phase=decision.study_phase.value if decision.study_phase else None,
        study_phase_label=(
            study_phase_label(decision.study_phase.value)
            if decision.study_phase
            else None
        ),
        confirmation_required=decision.confirmation_required,
        conflict_ids=list(decision.conflict_ids),
        selected_candidate_ids=list(decision.selected_candidate_ids),
    )


def _draft_dto(view) -> DraftRevisionResponse:
    revision = view.revision
    content = revision.content
    return DraftRevisionResponse(
        job_id=view.job_id,
        revision_id=revision.revision_id,
        draft_id=revision.draft_id,
        revision_number=revision.revision_number,
        status=revision.status.value,
        status_label=DRAFT_STATUS_LABELS.get(
            revision.status.value, revision.status.value
        ),
        reason=revision.reason.value,
        reason_label=DRAFT_REASON_LABELS.get(
            revision.reason.value, revision.reason.value
        ),
        actor=revision.actor,
        created_at=_as_utc(revision.created_at),
        study_phase=revision.study_phase.value,
        study_phase_label=study_phase_label(revision.study_phase.value),
        protocol_code=content.protocol_metadata.protocol_code_candidate,
        official_version=content.protocol_metadata.version_candidate,
        rule_count=len(content.proposed_rules),
        workflow_stage_count=len(content.proposed_workflow_stages),
        content=content.model_dump(mode="json"),
        diff=view.diff,
    )


def _integrity_dto(view) -> IntegrityResponse:
    if view.publishable:
        summary = "完整性检查已通过，可以进入发布确认。"
    elif view.blocking_count:
        summary = f"有 {view.blocking_count} 项问题阻止发布，请先修正后再发布。"
    elif view.review_count:
        summary = f"有 {view.review_count} 项需要核对，建议修正后再发布。"
    else:
        summary = "完整性检查已完成，请继续审阅草稿。"
    return IntegrityResponse(
        job_id=view.job_id,
        publishable=view.publishable,
        blocking_count=view.blocking_count,
        review_count=view.review_count,
        reminder_count=view.reminder_count,
        summary=summary,
        checks=[IntegrityCheckDTO(**item) for item in view.checks],
        issues=[IntegrityIssueDTO(**item) for item in view.issues],
    )


@router.post(
    "",
    response_model=StartDeconstructionResponse,
    status_code=http_status.HTTP_201_CREATED,
)
async def start_deconstruction(
    request: Request,
    response: Response,
    idempotency_key: str = Form(min_length=1, max_length=256),
    file: UploadFile = File(...),
    actor: str = Form(default="用户", min_length=1, max_length=128),
) -> StartDeconstructionResponse:
    suffix = Path(file.filename or "protocol.docx").suffix or ".docx"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
        temp_path = Path(handle.name)
        content = await file.read()
        handle.write(content)
    try:
        result = _service(request).start_first_deconstruction(
            upload_path=temp_path,
            original_name=file.filename or "protocol.docx",
            idempotency_key=idempotency_key,
            actor=actor,
        )
    finally:
        temp_path.unlink(missing_ok=True)
    from app.api.v2.vocabulary import JOB_STATE_LABELS

    if not result.created:
        response.status_code = http_status.HTTP_200_OK
    return StartDeconstructionResponse(
        job_id=result.job_id,
        state=result.state,
        state_label=JOB_STATE_LABELS.get(result.state, result.state),
        created=result.created,
        source_artifact_id=result.source_artifact_id,
        file_name=result.file_name,
    )


@router.get("/{job_id}", response_model=ProtocolSessionResponse)
def get_deconstruction_session(job_id: str, request: Request) -> ProtocolSessionResponse:
    return _session_dto(_service(request).get_session(job_id))


@router.get("/{job_id}/identity", response_model=IdentityReviewResponse)
def get_identity_review(job_id: str, request: Request) -> IdentityReviewResponse:
    view = _service(request).get_identity_review(job_id)
    return IdentityReviewResponse(
        job_id=view.job_id,
        snapshot_id=view.snapshot_id,
        confirmation_required=view.confirmation_required,
        identity=_identity_dto(view.identity_decision),
        phase_candidates=view.phase_candidates,
        metadata_candidates=view.metadata_candidates,
        metadata_conflicts=view.metadata_conflicts,
    )


@router.post("/{job_id}/identity/confirm", response_model=ProtocolSessionResponse)
def confirm_identity(
    job_id: str,
    body: ConfirmIdentityRequest,
    request: Request,
) -> ProtocolSessionResponse:
    view = _service(request).confirm_identity(
        job_id,
        protocol_code=body.protocol_code,
        project_name=body.project_name,
        project_code=body.project_code,
        official_version=body.official_version,
        official_date_value=body.official_date_value,
        official_date_precision=body.official_date_precision,
        study_phase=body.study_phase,
        actor=body.actor,
        selected_candidate_ids=body.selected_candidate_ids,
    )
    return _session_dto(view)


@router.get("/{job_id}/draft", response_model=DraftRevisionResponse)
def get_draft(job_id: str, request: Request) -> DraftRevisionResponse:
    return _draft_dto(_service(request).get_draft_detail(job_id))


@router.put("/{job_id}/draft", response_model=DraftRevisionResponse)
def edit_draft(
    job_id: str,
    body: ManualEditRequest,
    request: Request,
) -> DraftRevisionResponse:
    view = _service(request).apply_manual_edit(
        job_id,
        draft=body.draft,
        expected_revision_id=body.expected_revision_id,
        actor=body.actor,
    )
    return _draft_dto(view)


@router.post("/{job_id}/draft/feedback", response_model=DraftRevisionResponse)
def submit_feedback(
    job_id: str,
    body: FeedbackRequest,
    request: Request,
) -> DraftRevisionResponse:
    view = _service(request).apply_feedback(
        job_id,
        draft=body.draft,
        expected_revision_id=body.expected_revision_id,
        feedback_kind=body.feedback_kind,
        feedback_note=body.feedback_note,
        actor=body.actor,
    )
    return _draft_dto(view)


@router.post("/{job_id}/draft/save", response_model=DraftRevisionResponse)
def save_draft(
    job_id: str,
    body: DraftActionRequest,
    request: Request,
) -> DraftRevisionResponse:
    view = _service(request).save_draft(
        job_id,
        expected_revision_id=body.expected_revision_id,
    )
    return _draft_dto(view)


@router.post("/{job_id}/draft/cancel", response_model=DraftRevisionResponse)
def cancel_draft(
    job_id: str,
    body: DraftActionRequest,
    request: Request,
) -> DraftRevisionResponse:
    view = _service(request).cancel_draft(
        job_id,
        expected_revision_id=body.expected_revision_id,
    )
    return _draft_dto(view)


@router.get("/{job_id}/sources", response_model=SourcesResponse)
def get_sources(job_id: str, request: Request) -> SourcesResponse:
    payload = _service(request).get_sources(job_id)
    return SourcesResponse(**payload)


@router.get("/{job_id}/integrity", response_model=IntegrityResponse)
def get_integrity(job_id: str, request: Request) -> IntegrityResponse:
    return _integrity_dto(_service(request).get_integrity(job_id))


@router.post("/{job_id}/publish", response_model=PublishResponse)
def publish_first_project(
    job_id: str,
    body: PublishRequest,
    request: Request,
) -> PublishResponse:
    result = _service(request).publish_first_project(
        job_id,
        idempotency_key=body.idempotency_key,
        actor=body.actor,
    )
    return PublishResponse(
        job_id=result.job_id,
        project_id=result.project_id,
        protocol_version_id=result.protocol_version_id,
        rule_set_id=result.rule_set_id,
        rule_set_revision=result.rule_set_revision,
        replay=result.replay,
    )
