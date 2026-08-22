"""V2 证据上传预览/确认/快照 API（design.md §5.2/§5.3，Slice 4.2，薄路由）。

路由只做协议转换，不做领域判断：调用 ``EvidenceUploadService`` 与证据读取服务，
把领域合同投影为带中文标签的 DTO。本模块不导入 SQLAlchemy 或 ``app.storage``
（薄 API 边界验收由 AST 测试强制）：

- ``POST /api/v2/subjects/{subject_id}/evidence-upload-previews``（multipart）；
- ``GET/DELETE /api/v2/evidence-upload-previews/{preview_id}``；
- ``POST /api/v2/evidence-upload-previews/{preview_id}/commit``（JSON，
  ``preview_id`` 由路径唯一确定）；
- ``GET /api/v2/subjects/{subject_id}/evidence-snapshots?review_episode_id=...``；
- ``GET /api/v2/evidence-snapshots/{snapshot_id}``。

快照 ``is_current`` 与列表当前指针只来自审核节点成对活动指针（读取服务投影），
绝不按创建时间/列表顺序/状态/legacy 字段推断（§5.5）。
"""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import (
    APIRouter,
    File,
    Form,
    Query,
    Request,
    Response,
    UploadFile,
)
from fastapi import (
    status as http_status,
)

from app.api.v2.evidence_schemas import (
    EvidenceCommitRequest,
    EvidenceCommitResponse,
    EvidenceFileProgressDTO,
    EvidenceMetadataRevisionDTO,
    EvidenceMetadataRevisionRequest,
    EvidenceMetadataRevisionResponse,
    EvidenceProgressDTO,
    EvidenceResolutionDecisionDTO,
    EvidenceSnapshotCandidateDTO,
    EvidenceSnapshotDTO,
    EvidenceSnapshotListDTO,
    EvidenceSnapshotMemberDTO,
    EvidenceUploadItemDTO,
    EvidenceUploadPreviewDTO,
)
from app.api.v2.vocabulary import (
    conflict_resolution_label,
    item_next_action,
    item_status_label,
    item_status_reason,
    preview_status_label,
    processing_hint_label,
    snapshot_member_origin_label,
    snapshot_status_label,
    upload_mode_label,
)
from app.domain.contracts.enums import UploadMode
from app.domain.contracts.evidence_ingestion import (
    EvidenceSnapshot,
    EvidenceSnapshotMember,
)
from app.domain.contracts.evidence_upload import (
    EvidenceUploadCommit,
    EvidenceUploadConfirmInput,
    EvidenceUploadConfirmResult,
    EvidenceUploadItem,
    EvidenceUploadPreview,
)
from app.services.evidence_api_read_service import EvidenceApiReadService
from app.services.evidence_app_errors import AppEvidenceUploadError
from app.services.evidence_upload_service import (
    EvidenceUploadService,
    UploadedFileInput,
)

router = APIRouter(tags=["v2-evidence"])

#: 单机单用户应用的默认操作人；调用方可显式传入 actor 以便审计。
DEFAULT_ACTOR = "本地用户"


def _as_utc(value: datetime) -> datetime:
    """恢复存储层 UTC 约定（数据库存 UTC naive，API 边界补回时区）。"""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _service(request: Request) -> EvidenceUploadService:
    return request.app.state.evidence_upload_service


def _read(request: Request) -> EvidenceApiReadService:
    return request.app.state.evidence_api_read_service


def _command(request: Request):
    return request.app.state.evidence_api_command_service


def _require_subject_episode(request, subject_id: str, review_episode_id: str) -> None:
    """派生并重验作用域：审核节点必须属于路径受试者（跨项目/跨对象一律 404）。"""
    _read(request).require_subject_episode(subject_id, review_episode_id)


# --------------------------------------------------------------------- DTO


def _item_dto(item: EvidenceUploadItem) -> EvidenceUploadItemDTO:
    status = item.status.value
    return EvidenceUploadItemDTO(
        item_id=item.item_id,
        file_name=item.file_name,
        byte_size=item.byte_size,
        media_type=item.media_type,
        status=status,
        status_label=item_status_label(status),
        processing_hint=item.processing_hint,
        processing_hint_label=processing_hint_label(item.processing_hint),
        reason=item_status_reason(status, item.error_detail),
        next_action=item_next_action(status),
        logical_document_id=item.logical_document_id,
        existing_version_id=item.existing_version_id,
        error_detail=item.error_detail,
    )


def _preview_dto(preview: EvidenceUploadPreview) -> EvidenceUploadPreviewDTO:
    return EvidenceUploadPreviewDTO(
        preview_id=preview.preview_id,
        project_id=preview.project_id,
        subject_id=preview.subject_id,
        review_episode_id=preview.review_episode_id,
        upload_mode=preview.upload_mode.value,
        upload_mode_label=upload_mode_label(preview.upload_mode.value),
        base_revision=preview.base_revision,
        base_snapshot_id=preview.base_snapshot_id,
        status=preview.status.value,
        status_label=preview_status_label(preview.status.value),
        items=[_item_dto(item) for item in preview.items],
        matching_snapshot_id=preview.matching_snapshot_id,
        matching_snapshot_status=(
            preview.matching_snapshot_status.value
            if preview.matching_snapshot_status is not None
            else None
        ),
        matching_snapshot_status_label=(
            snapshot_status_label(preview.matching_snapshot_status.value)
            if preview.matching_snapshot_status is not None
            else None
        ),
        preview_sha256=preview.preview_sha256,
        created_at=_as_utc(preview.created_at),
        created_by=preview.created_by,
    )


def _metadata_dto(metadata) -> EvidenceMetadataRevisionDTO:
    return EvidenceMetadataRevisionDTO(
        metadata_revision_id=metadata.metadata_revision_id,
        source_document_version_id=metadata.source_document_version_id,
        revision=metadata.revision,
        document_type=metadata.document_type,
        source_party=metadata.source_party,
        reason=metadata.reason,
        is_auto_suggestion=metadata.is_auto_suggestion,
        supersedes_metadata_revision_id=metadata.supersedes_metadata_revision_id,
        created_at=_as_utc(metadata.created_at),
        created_by=metadata.created_by,
    )


def _snapshot_member_dto(member: EvidenceSnapshotMember, summary) -> EvidenceSnapshotMemberDTO:
    version = summary.version
    origin = member.origin.value
    return EvidenceSnapshotMemberDTO(
        member_id=member.member_id,
        snapshot_id=member.snapshot_id,
        logical_document_id=member.logical_document_id,
        source_document_version_id=member.source_document_version_id,
        file_name=version.file_name,
        media_type=version.media_type,
        version_number=version.version_number,
        origin=origin,
        origin_label=snapshot_member_origin_label(origin),
        metadata_head=_metadata_dto(summary.metadata),
    )


def _snapshot_dto(
    request, snapshot: EvidenceSnapshot, *, is_current: bool
) -> EvidenceSnapshotDTO:
    summaries = _read(request).source_document_summaries(
        [member.source_document_version_id for member in snapshot.members]
    )
    candidate_view = _read(request).latest_processing_candidate_for_snapshot(
        snapshot.evidence_snapshot_id
    )
    candidate_dto = None
    if candidate_view is not None:
        candidate = candidate_view.candidate
        candidate_status = (
            candidate.status.value
            if hasattr(candidate.status, "value")
            else candidate.status
        )
        candidate_dto = EvidenceSnapshotCandidateDTO(
            candidate_id=candidate.candidate_id,
            job_id=candidate.job_id,
            candidate_status=candidate_status,
            candidate_status_label=snapshot_status_label(candidate_status),
            candidate_event_seq=candidate_view.event_seq,
            complete_revision_id=candidate.complete_revision_id,
        )
    return EvidenceSnapshotDTO(
        evidence_snapshot_id=snapshot.evidence_snapshot_id,
        project_id=snapshot.project_id,
        subject_id=snapshot.subject_id,
        review_episode_id=snapshot.review_episode_id,
        upload_mode=snapshot.upload_mode.value,
        upload_mode_label=upload_mode_label(snapshot.upload_mode.value),
        prior_snapshot_id=snapshot.prior_snapshot_id,
        comparison_snapshot_id=snapshot.comparison_snapshot_id,
        status=snapshot.status.value,
        status_label=snapshot_status_label(snapshot.status.value),
        is_current=is_current,
        base_processing_revision_id=_read(
            request
        ).base_processing_revision_id_for_snapshot(snapshot.evidence_snapshot_id),
        upload_job_id=_read(request).upload_processing_job_id_for_snapshot(
            snapshot.evidence_snapshot_id
        ),
        latest_processing_candidate=candidate_dto,
        members=[
            _snapshot_member_dto(
                member, summaries[member.source_document_version_id]
            )
            for member in snapshot.members
        ],
        collection_sha256=snapshot.collection_sha256,
        created_at=_as_utc(snapshot.created_at),
        created_by=snapshot.created_by,
    )


def _episode_pointer(
    request, review_episode_id: str
) -> tuple[str | None, str | None]:
    """当前版本唯一权威：审核节点成对活动指针（绝不按时间/状态/顺序回退）。"""
    return _read(request).episode_pointer(review_episode_id)


def _commit_dto(
    request,
    commit: EvidenceUploadCommit,
    snapshot: EvidenceSnapshot,
    *,
    result: EvidenceUploadConfirmResult,
) -> EvidenceCommitResponse:
    active_snapshot, _active_revision = _episode_pointer(
        request, commit.review_episode_id
    )
    return EvidenceCommitResponse(
        commit_id=commit.commit_id,
        preview_id=commit.preview_id,
        evidence_snapshot_id=commit.evidence_snapshot_id,
        project_id=commit.project_id,
        subject_id=commit.subject_id,
        review_episode_id=commit.review_episode_id,
        upload_mode=commit.upload_mode.value,
        upload_mode_label=upload_mode_label(commit.upload_mode.value),
        idempotency_key=commit.idempotency_key,
        job_id=commit.job_id,
        created=result.created,
        replayed=result.replayed,
        duplicate=result.duplicate,
        resolutions=[
            EvidenceResolutionDecisionDTO(
                item_id=decision.item_id,
                logical_document_id=decision.logical_document_id,
                resolution=decision.resolution.value,
                resolution_label=conflict_resolution_label(
                    decision.resolution.value
                ),
                source_document_version_id=decision.source_document_version_id,
                supersedes_version_id=decision.supersedes_version_id,
            )
            for decision in commit.resolutions
        ],
        snapshot=_snapshot_dto(
            request,
            snapshot,
            is_current=(snapshot.evidence_snapshot_id == active_snapshot),
        ),
        created_at=_as_utc(commit.created_at),
        created_by=commit.created_by,
    )


# ------------------------------------------------------------- 上传预览


@router.post(
    "/api/v2/subjects/{subject_id}/evidence-upload-previews",
    response_model=EvidenceUploadPreviewDTO,
    status_code=http_status.HTTP_201_CREATED,
)
def create_upload_preview(
    subject_id: str,
    request: Request,
    review_episode_id: str = Form(...),
    upload_mode: UploadMode = Form(...),  # noqa: B008 - FastAPI 依赖注入标记
    base_revision: int = Form(..., ge=1),
    actor: str | None = Form(default=None, max_length=128),
    files: list[UploadFile] = File(...),  # noqa: B008 - FastAPI 依赖注入标记
) -> EvidenceUploadPreviewDTO:
    if not files:
        raise AppEvidenceUploadError(
            status_code=422,
            code="EMPTY_UPLOAD",
            title="未选择任何文件",
            recovery="请至少选择一个文件后重新提交。",
            detail="本次上传没有收到任何文件。",
        )
    _require_subject_episode(request, subject_id, review_episode_id)
    project_id = _read(request).episode(review_episode_id).project_id
    inputs = [
        UploadedFileInput(file_name=file.filename or "", content=file.file.read())
        for file in files
    ]
    preview = _service(request).create_preview(
        project_id=project_id,
        subject_id=subject_id,
        review_episode_id=review_episode_id,
        upload_mode=upload_mode,
        base_revision=base_revision,
        files=inputs,
        created_by=actor or DEFAULT_ACTOR,
    )
    return _preview_dto(preview)


@router.get(
    "/api/v2/evidence-upload-previews/{preview_id}",
    response_model=EvidenceUploadPreviewDTO,
)
def get_upload_preview(preview_id: str, request: Request) -> EvidenceUploadPreviewDTO:
    """读取预览：作用域从预览记录推导，仓储读取时重验 episode↔subject↔project。"""
    preview = _service(request).get_preview(preview_id)
    return _preview_dto(preview)


@router.delete(
    "/api/v2/evidence-upload-previews/{preview_id}",
    response_model=EvidenceUploadPreviewDTO,
)
def cancel_upload_preview(
    preview_id: str, request: Request
) -> EvidenceUploadPreviewDTO:
    """取消预览：幂等，只清理预览自有暂存，不触碰共享 blob/快照/历史。"""
    cancelled = _service(request).cancel(
        preview_id, actor=DEFAULT_ACTOR
    )
    return _preview_dto(cancelled)


# ----------------------------------------------------------------- 确认


@router.post(
    "/api/v2/evidence-upload-previews/{preview_id}/commit",
    response_model=EvidenceCommitResponse,
    status_code=http_status.HTTP_201_CREATED,
)
def confirm_upload(
    preview_id: str,
    body: EvidenceCommitRequest,
    request: Request,
    response: Response,
) -> EvidenceCommitResponse:
    """确认预览：同一事务创建/复用候选快照、持久任务与幂等记录。

    ``preview_id`` 由路径唯一确定，作用域从预览记录派生并重验，不信任客户端
    摘要或文件名。新建快照/任务返回 201；同幂等键回放与跨预览同集合 no-op 复用
    既有结果并返回 200，``created``/``replayed``/``duplicate`` 如实区分两者。
    """
    actor = body.actor or DEFAULT_ACTOR
    service = _service(request)
    preview = service.get_preview(preview_id)
    command = EvidenceUploadConfirmInput(
        preview_id=preview.preview_id,
        project_id=preview.project_id,
        subject_id=preview.subject_id,
        review_episode_id=preview.review_episode_id,
        upload_mode=body.upload_mode,
        base_revision=body.base_revision,
        preview_sha256=body.preview_sha256,
        idempotency_key=body.idempotency_key,
        resolutions=body.resolutions,
    )
    result = service.confirm(command, created_by=actor)
    if not result.created:
        response.status_code = http_status.HTTP_200_OK
    commit = _read(request).commit(result.commit_id)
    return _commit_dto(
        request,
        commit,
        result.snapshot,
        result=result,
    )


# ------------------------------------------------------------ 快照查询


@router.get(
    "/api/v2/subjects/{subject_id}/evidence-snapshots",
    response_model=EvidenceSnapshotListDTO,
)
def list_evidence_snapshots(
    subject_id: str,
    request: Request,
    review_episode_id: str = Query(...),
) -> EvidenceSnapshotListDTO:
    _require_subject_episode(request, subject_id, review_episode_id)
    active_snapshot, active_revision = _episode_pointer(request, review_episode_id)
    snapshots = _read(request).snapshot_list(review_episode_id)
    return EvidenceSnapshotListDTO(
        subject_id=subject_id,
        review_episode_id=review_episode_id,
        active_evidence_snapshot_id=active_snapshot,
        active_evidence_processing_revision_id=active_revision,
        items=[
            _snapshot_dto(
                request,
                snapshot,
                is_current=(snapshot.evidence_snapshot_id == active_snapshot),
            )
            for snapshot in snapshots
        ],
    )


@router.get(
    "/api/v2/evidence-snapshots/{snapshot_id}",
    response_model=EvidenceSnapshotDTO,
)
def get_evidence_snapshot(
    snapshot_id: str, request: Request
) -> EvidenceSnapshotDTO:
    """读取快照：作用域从快照记录推导，仓储读取时重验 episode↔subject↔project。

    ``is_current`` 只来自审核节点成对活动指针，绝不从快照状态/创建时间推断。
    """
    snapshot = _read(request).snapshot(snapshot_id)
    active_snapshot, _active_revision = _episode_pointer(
        request, snapshot.review_episode_id
    )
    return _snapshot_dto(
        request,
        snapshot,
        is_current=(snapshot.evidence_snapshot_id == active_snapshot),
    )


@router.patch(
    "/api/v2/source-document-versions/{source_document_version_id}/metadata",
    response_model=EvidenceMetadataRevisionResponse,
)
def revise_source_document_metadata(
    source_document_version_id: str,
    body: EvidenceMetadataRevisionRequest,
    request: Request,
    response: Response,
) -> EvidenceMetadataRevisionResponse:
    """核对资料类型与来源方；新内容追加修订，同命令可安全回放。"""
    result = _command(request).revise_source_document_metadata(
        source_document_version_id=source_document_version_id,
        document_type=body.document_type,
        source_party=body.source_party,
        reason=body.reason,
        expected_metadata_revision=body.expected_metadata_revision,
        idempotency_key=body.idempotency_key,
        actor=body.actor or DEFAULT_ACTOR,
    )
    if not result.created:
        response.status_code = http_status.HTTP_200_OK
    else:
        response.status_code = http_status.HTTP_201_CREATED
    return EvidenceMetadataRevisionResponse(
        created=result.created,
        metadata=_metadata_dto(result.revision),
    )


# ------------------------------------------------------------ 只读处理进度


@router.get(
    "/api/v2/jobs/{job_id}/evidence-progress",
    response_model=EvidenceProgressDTO,
)
def get_evidence_progress(job_id: str, request: Request) -> EvidenceProgressDTO:
    """只读投影证据处理进度：按持久 OCR 运行/页状态给出中文业务进度。

    只读读取，不修改任务、不持有取消权；任务不存在返回 404 信封。每页状态以
    「等待处理 / 正在处理 / 部分完成 / 需要处理 / 已完成」中文业务措辞呈现，
    不暴露内部列名、运行日志或本地路径。
    """
    from app.api.v2.vocabulary import JOB_STATE_LABELS as _JSL

    view = _read(request).progress(job_id, job_state_labels=_JSL)
    return EvidenceProgressDTO(
            job_id=view.job_id,
            job_state=view.job_state,
            job_state_label=view.job_state_label,
            total_pages=view.total_pages,
            completed_pages=view.completed_pages,
            failed_pages=view.failed_pages,
            pending_pages=view.pending_pages,
            scope_note=view.scope_note,
            files=[
                EvidenceFileProgressDTO(
                    source_document_version_id=file.source_document_version_id,
                    file_name=file.file_name,
                    page_total=file.page_total,
                    page_succeeded=file.page_succeeded,
                    page_failed=file.page_failed,
                    status=file.status,
                    status_label=file.status_label,
                )
                for file in view.files
            ],
        )
