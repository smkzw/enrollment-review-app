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
    DraftComparisonResponse,
    DraftComparisonSideResponse,
    FeedbackRequest,
    IdentityDecisionDTO,
    IdentityReviewResponse,
    MetadataCandidateDTO,
    MetadataConflictCandidateDTO,
    MetadataConflictDTO,
    OfficialProjectDTO,
    OfficialProjectListResponse,
    PhaseCandidateDTO,
    IntegrityCheckDTO,
    IntegrityIssueDTO,
    IntegrityResponse,
    ManualEditRequest,
    ProjectOfficialVersionResponse,
    ProjectVersionDTO,
    ProtocolSessionResponse,
    PublishRequest,
    PublishResponse,
    SourcesResponse,
    StartDeconstructionResponse,
    StartFeedbackRevisionRequest,
)
from app.api.v2.vocabulary import (
    DRAFT_REASON_LABELS,
    DRAFT_STATUS_LABELS,
    METADATA_FIELD_LABELS,
    METADATA_SOURCE_LABELS,
    METADATA_STATUS_LABELS,
    study_phase_label,
)
from app.domain.contracts.common import DateValue
from app.domain.contracts.protocol_metadata import ProtocolIdentityDecision
from app.services.protocol_workbench_service import ProtocolWorkbenchService

router = APIRouter(prefix="/api/v2/protocol/deconstructions", tags=["v2-protocol"])
projects_router = APIRouter(prefix="/api/v2/protocol", tags=["v2-protocol"])


def _official_project_dto(view) -> OfficialProjectDTO:
    return OfficialProjectDTO(
        project_id=view.project_id,
        project_code=view.project_code,
        project_name=view.project_name,
        study_phase=view.study_phase,
        study_phase_label=view.study_phase_label,
        protocol_code=view.protocol_code,
        official_version=view.official_version,
        official_date_value=view.official_date_value,
        official_date_precision=view.official_date_precision,
        rule_set_id=view.rule_set_id,
        rule_set_revision=view.rule_set_revision,
    )


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
        target_project_id=view.target_project_id,
        target_project_name=view.target_project_name,
        target_project_code=view.target_project_code,
        target_protocol_code=view.target_protocol_code,
        target_study_phase=view.target_study_phase,
        target_study_phase_label=view.target_study_phase_label,
        target_official_version=view.target_official_version,
        target_rule_set_revision=view.target_rule_set_revision,
    )


def _identity_dto(decision: ProtocolIdentityDecision) -> IdentityDecisionDTO:
    official_date = decision.official_date
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
        official_date_value=_official_date_text(official_date),
        official_date_precision=official_date.precision if official_date else None,
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


def _official_date_text(value: DateValue | None) -> str | None:
    """Project normalized dates without losing the confirmed precision."""
    if value is None or value.value is None:
        return None
    if value.precision.value == "year":
        return f"{value.value.year:04d}"
    if value.precision.value == "month":
        return f"{value.value.year:04d}-{value.value.month:02d}"
    return value.value.isoformat()


def _metadata_source_label(candidate: dict) -> str:
    source_kind = str(candidate.get("source_kind") or "")
    return METADATA_SOURCE_LABELS.get(source_kind, "方案原文")


def _phase_candidate_dtos(candidates: list[dict]) -> list[PhaseCandidateDTO]:
    grouped: dict[str, list[dict]] = {}
    for candidate in candidates:
        phase = str(candidate.get("phase") or "")
        if phase:
            grouped.setdefault(phase, []).append(candidate)
    output = []
    for phase, items in grouped.items():
        excerpts = list(
            dict.fromkeys(
                str(item.get("excerpt") or "").strip()
                for item in items
                if str(item.get("excerpt") or "").strip()
            )
        )
        source_excerpt = "；".join(excerpts)
        output.append(
            PhaseCandidateDTO(
                candidate_id=str(items[0].get("candidate_id") or ""),
                phase=phase,
                phase_label=study_phase_label(phase),
                rationale=(
                    f"方案原文在 {len(excerpts)} 处明确提及该期别：{source_excerpt}"
                    if len(excerpts) > 1
                    else f"方案原文出现“{source_excerpt}”"
                ),
                source_excerpt=source_excerpt,
            )
        )
    return output


def _metadata_candidate_dto(candidate: dict) -> MetadataCandidateDTO:
    field = str(candidate.get("field_category") or "")
    return MetadataCandidateDTO(
        candidate_id=str(candidate.get("candidate_id") or ""),
        field=field,
        field_label=METADATA_FIELD_LABELS.get(field, "方案信息"),
        value=_metadata_candidate_value(candidate, field),
        source_label=_metadata_source_label(candidate),
        source_excerpt=str(candidate.get("excerpt") or ""),
        is_fallback=bool(candidate.get("is_fallback", False)),
    )


def _metadata_candidate_value(candidate: dict, field: str | None = None) -> str:
    """Use a form-ready value while keeping the exact source excerpt separate."""
    field_name = field or str(candidate.get("field_category") or "")
    if field_name == "protocol_date":
        normalized = candidate.get("normalized_value")
        if normalized:
            return str(normalized)
    return str(candidate.get("candidate_value") or "")


def _metadata_conflict_dto(
    conflict: dict,
    candidates_by_id: dict[str, dict],
) -> MetadataConflictDTO:
    field = str(conflict.get("field_category") or "")
    candidates = []
    for candidate_id in conflict.get("candidate_ids") or []:
        candidate = candidates_by_id.get(str(candidate_id), {})
        candidates.append(
            MetadataConflictCandidateDTO(
                candidate_id=str(candidate_id),
                value=_metadata_candidate_value(candidate, field),
                source_label=_metadata_source_label(candidate),
            )
        )
    return MetadataConflictDTO(
        conflict_id=str(conflict.get("conflict_id") or ""),
        field=field,
        field_label=METADATA_FIELD_LABELS.get(field, "方案信息"),
        reason=str(conflict.get("reason") or "检测到多个不一致的候选值"),
        candidates=candidates,
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


def _comparison_side_dto(side) -> DraftComparisonSideResponse:
    return DraftComparisonSideResponse(
        revision_id=side.revision_id,
        draft_id=side.draft_id,
        protocol_version_id=side.protocol_version_id,
        official_version=side.official_version,
        revision_number=side.revision_number,
        status=side.status,
        rule_count=side.rule_count,
        workflow_stage_count=side.workflow_stage_count,
        is_formal_baseline=side.is_formal_baseline,
        content=side.content,
        source_refs=list(side.source_refs),
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
    project_id: str = Form(default="", max_length=128),
) -> StartDeconstructionResponse:
    suffix = Path(file.filename or "protocol.docx").suffix or ".docx"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
        temp_path = Path(handle.name)
        content = await file.read()
        handle.write(content)
    try:
        # 携带 project_id 时进入“重新解构已有项目”路径：目标项目持久保存于任务，
        # 上传的新版方案在同一项目生成新的不可变规则版本。
        if project_id.strip():
            result = _service(request).start_re_deconstruction(
                upload_path=temp_path,
                original_name=file.filename or "protocol.docx",
                project_id=project_id.strip(),
                idempotency_key=idempotency_key,
                actor=actor,
            )
        else:
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


@router.post(
    "/from-formal",
    response_model=StartDeconstructionResponse,
    status_code=http_status.HTTP_201_CREATED,
)
def start_feedback_re_deconstruction(
    payload: StartFeedbackRevisionRequest,
    request: Request,
    response: Response,
) -> StartDeconstructionResponse:
    """不上传新文件，基于当前正式草稿建立反馈修订任务。"""
    result = _service(request).start_feedback_re_deconstruction(
        project_id=payload.project_id,
        idempotency_key=payload.idempotency_key,
        actor=payload.actor,
    )
    if not result.created:
        response.status_code = http_status.HTTP_200_OK
    from app.api.v2.vocabulary import JOB_STATE_LABELS

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
    candidates_by_id = {
        str(item.get("candidate_id")): item for item in view.metadata_candidates
    }
    return IdentityReviewResponse(
        job_id=view.job_id,
        snapshot_id=view.snapshot_id,
        confirmation_required=view.confirmation_required,
        identity=_identity_dto(view.identity_decision),
        phase_candidates=_phase_candidate_dtos(view.phase_candidates),
        metadata_candidates=[
            _metadata_candidate_dto(item) for item in view.metadata_candidates
        ],
        metadata_conflicts=[
            _metadata_conflict_dto(item, candidates_by_id)
            for item in view.metadata_conflicts
        ],
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


@router.get("/{job_id}/draft/comparison", response_model=DraftComparisonResponse)
def get_draft_comparison(job_id: str, request: Request) -> DraftComparisonResponse:
    view = _service(request).get_draft_comparison(job_id)
    return DraftComparisonResponse(
        job_id=view.job_id,
        baseline=_comparison_side_dto(view.baseline),
        candidate=_comparison_side_dto(view.candidate),
        diff=view.diff,
        source_bound=view.source_bound,
    )


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
        expected_revision_id=body.expected_revision_id,
        feedback_kind=body.feedback_kind,
        feedback_note=body.feedback_note,
        target_rule_code=body.target_rule_code,
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
def publish_deconstruction(
    job_id: str,
    body: PublishRequest,
    request: Request,
) -> PublishResponse:
    service = _service(request)
    if service.is_re_deconstruction(job_id):
        result = service.publish_re_deconstruction(
            job_id,
            idempotency_key=body.idempotency_key,
            actor=body.actor,
        )
    else:
        result = service.publish_first_project(
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


# ---------------------------------------------------------------------------
# 正式项目读取（重新解构选择与当前正式版本投影）
# ---------------------------------------------------------------------------


@projects_router.get("/projects", response_model=OfficialProjectListResponse)
def list_official_projects(request: Request) -> OfficialProjectListResponse:
    return OfficialProjectListResponse(
        projects=[_official_project_dto(view) for view in _service(request).list_official_projects()]
    )


@projects_router.get(
    "/projects/{project_id}", response_model=ProjectOfficialVersionResponse
)
def get_project_official_version(
    project_id: str, request: Request
) -> ProjectOfficialVersionResponse:
    view = _service(request).get_project_official_version(project_id)
    return ProjectOfficialVersionResponse(
        project=_official_project_dto(view.project),
        versions=[
            ProjectVersionDTO(
                rule_set_revision=item.rule_set_revision,
                protocol_version_id=item.protocol_version_id,
                official_version=item.official_version,
                official_date_value=item.official_date_value,
                official_date_precision=item.official_date_precision,
                sha256=item.sha256,
                rule_count=item.rule_count,
                published_at=item.published_at,
            )
            for item in view.versions
        ],
        publication_count=view.publication_count,
    )
