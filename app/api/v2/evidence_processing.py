"""Slice 4.4 证据处理 / 校对 / 激活 / 被提及资料 API（WP-44C 薄路由）。

路由只做协议转换：把请求解析为命令/查询参数，调用应用服务（读取服务 + 命令
服务），并把领域合同投影为带中文标签的 DTO。本模块**不导入** SQLAlchemy、存储
模型、存储仓储或幂等表（薄 API 边界验收由 AST 测试强制）：

- 页读取分别暴露 ``raw_text``（原始识别）、``effective_text``（校对后文本，绝不
  叫“原始识别”）、所选校对、风险扫描/核对与定位精度/降级；指定处理修订时只返回
  该修订冻结的旁路工件（精确历史回放）；
- 所有写命令携带稳定幂等键与预期修订号：同键同请求回放原结果，同键异请求 409，
  新请求检查预期修订号；409 上下文保留提交值、当前记录与字段差异，待核对/门禁
  失败列出实际门禁；
- 被提及资料 create/patch/confirm/dismiss/resolve/delete 全部追加新的不可变修订，
  绝不原地 UPDATE/DELETE；``DELETE resolution`` 追加 unresolved 满足修订；
- current 只来自 ``ReviewEpisode`` 成对活动指针，绝不按创建时间/列表顺序/状态/
  legacy 字段推断。

不在本层实现临床判断、规则影响或持久化算法。
"""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Query, Request, Response
from fastapi import status as http_status

from app.api.v2.evidence_processing_schemas import (
    ActivateRequest,
    ActivationEventDTO,
    BoundingBoxDTO,
    BuildRevisionRequest,
    BuildRevisionResponse,
    CoordinateFrameDTO,
    CorrectionCreateRequest,
    CorrectionCreateResponse,
    CorrectionDTO,
    GateResultDTO,
    LocatorDTO,
    OcrPageDTO,
    OcrRiskFlagDTO,
    OcrRiskReviewDTO,
    OcrRiskScanDTO,
    OCRRiskPageReviewDTO,
    PageRiskReviewCreateRequest,
    PageRiskReviewCreateResponse,
    ProcessingCandidateDTO,
    ProcessingRevisionDTO,
    ProcessingRevisionPageDTO,
    ReferencedDocumentConfirmRequest,
    ReferencedDocumentCreateRequest,
    ReferencedDocumentDismissRequest,
    ReferencedDocumentDTO,
    ReferencedDocumentListDTO,
    ReferencedDocumentResolutionDTO,
    ReferencedDocumentResolveRequest,
    ReferencedDocumentReviseRequest,
    RiskReviewCreateRequest,
    RiskReviewCreateResponse,
)
from app.api.v2.vocabulary import (
    activation_event_kind_label,
    correction_change_kind_label,
    gate_status_label,
    locator_precision_label,
    locator_source_layer_label,
    ocr_page_status_label,
    ocr_risk_kind_label,
    ocr_risk_level_label,
    ocr_risk_review_decision_label,
    page_artifact_status_label,
    referenced_document_origin_label,
    referenced_document_resolution_label,
    referenced_document_status_label,
    revision_kind_label,
    snapshot_status_label,
)
from app.services.evidence_api_command_service import EvidenceApiCommandService
from app.services.evidence_api_read_service import (
    EvidenceApiReadService,
    GateSummary,
    OcrPageView,
    ReferencedHeadView,
    RevisionView,
)

router = APIRouter(tags=["v2-evidence-processing"])

#: 单机单用户应用的默认操作人；调用方可显式传入 actor 以便审计。
DEFAULT_ACTOR = "本地用户"


def _read(request: Request) -> EvidenceApiReadService:
    return request.app.state.evidence_api_read_service


def _command(request: Request) -> EvidenceApiCommandService:
    return request.app.state.evidence_api_command_service


def _as_utc(value: datetime) -> datetime:
    """恢复存储层 UTC 约定（数据库存 UTC naive，API 边界补回时区）。"""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _as_utc_opt(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return _as_utc(value)


# -------------------------------------------------------------- DTO 投影


def _flag_dto(flag) -> OcrRiskFlagDTO:
    kind = flag.kind.value if hasattr(flag.kind, "value") else flag.kind
    level = flag.level.value if hasattr(flag.level, "value") else flag.level
    return OcrRiskFlagDTO(
        risk_id=flag.risk_id,
        kind=kind,
        kind_label=ocr_risk_kind_label(kind),
        level=level,
        level_label=ocr_risk_level_label(level),
        text=flag.text,
        text_start=flag.text_start,
        text_end=flag.text_end,
        detail=flag.detail,
        rule_version=flag.rule_version,
    )


def _scan_dto(scan) -> OcrRiskScanDTO:
    return OcrRiskScanDTO(
        scan_id=scan.scan_id,
        ocr_page_id=scan.ocr_page_id,
        raw_text_sha256=scan.raw_text_sha256,
        scanner_rule_version=scan.scanner_rule_version,
        flags_sha256=scan.flags_sha256,
        coverage_status=scan.coverage_status,
        created_at=_as_utc(scan.created_at),
        flags=[_flag_dto(flag) for flag in scan.flags],
    )


def _review_dto(review) -> OcrRiskReviewDTO:
    decision = (
        review.decision.value if hasattr(review.decision, "value") else review.decision
    )
    return OcrRiskReviewDTO(
        review_id=review.review_id,
        risk_flag_id=review.risk_flag_id,
        decision=decision,
        decision_label=ocr_risk_review_decision_label(decision),
        reason=review.reason,
        actor=review.actor,
        base_processing_revision_id=review.base_processing_revision_id,
        expected_revision=review.expected_revision,
        created_at=_as_utc(review.created_at),
    )


def _page_review_dto(page_review) -> OCRRiskPageReviewDTO:
    decision = (
        page_review.decision.value
        if hasattr(page_review.decision, "value")
        else page_review.decision
    )
    return OCRRiskPageReviewDTO(
        page_review_id=page_review.page_review_id,
        ocr_page_id=page_review.ocr_page_id,
        scan_id=page_review.scan_id,
        raw_text_sha256=page_review.raw_text_sha256,
        scanner_rule_version=page_review.scanner_rule_version,
        decision=decision,
        decision_label=ocr_risk_review_decision_label(decision),
        reason=page_review.reason,
        actor=page_review.actor,
        base_processing_revision_id=page_review.base_processing_revision_id,
        expected_revision=page_review.expected_revision,
        covered_flag_ids=list(page_review.covered_flag_ids),
        created_review_ids=list(page_review.created_review_ids),
        covered_flag_sha256=page_review.covered_flag_sha256,
        created_at=_as_utc(page_review.created_at),
    )


def _correction_dto(correction) -> CorrectionDTO:
    kind = (
        correction.change_kind.value
        if hasattr(correction.change_kind, "value")
        else correction.change_kind
    )
    return CorrectionDTO(
        correction_id=correction.correction_id,
        ocr_page_id=correction.ocr_page_id,
        raw_text_sha256=correction.raw_text_sha256,
        text_start=correction.text_start,
        text_end=correction.text_end,
        original_text=correction.original_text,
        corrected_text=correction.corrected_text,
        change_kind=kind,
        change_kind_label=correction_change_kind_label(kind),
        requires_confirmation=correction.requires_confirmation,
        confirmation_actor=correction.confirmation_actor,
        confirmation_at=_as_utc_opt(correction.confirmation_at),
        reason=correction.reason,
        actor=correction.actor,
        base_processing_revision_id=correction.base_processing_revision_id,
        supersedes_correction_id=correction.supersedes_correction_id,
        affected_scope=list(correction.affected_scope),
        created_at=_as_utc(correction.created_at),
    )


def _locator_dto(locator) -> LocatorDTO:
    layer = (
        locator.source_layer.value
        if hasattr(locator.source_layer, "value")
        else locator.source_layer
    )
    precision = (
        locator.precision.value
        if hasattr(locator.precision, "value")
        else locator.precision
    )
    authenticity = (
        locator.authenticity.value
        if hasattr(locator.authenticity, "value")
        else locator.authenticity
    )
    disambiguation = (
        locator.disambiguation.value
        if hasattr(locator.disambiguation, "value")
        else locator.disambiguation
    )
    return LocatorDTO(
        locator_id=locator.locator_id,
        page_artifact_id=locator.page_artifact_id,
        ocr_page_id=locator.ocr_page_id,
        source_document_version_id=locator.source_document_version_id,
        page_number=locator.page_number,
        source_layer=layer,
        source_layer_label=locator_source_layer_label(layer),
        source_text_sha256=locator.source_text_sha256,
        target_id=locator.target_id,
        precision=precision,
        precision_label=locator_precision_label(precision),
        degradation_reason=locator.degradation_reason,
        text_start=locator.text_start,
        text_end=locator.text_end,
        excerpt=locator.excerpt,
        disambiguation=disambiguation,
        locator_algorithm_version=locator.locator_algorithm_version,
        authenticity=authenticity,
        match_confidence=locator.match_confidence,
        bbox=(
            BoundingBoxDTO(
                x0=locator.bbox.x0,
                y0=locator.bbox.y0,
                x1=locator.bbox.x1,
                y1=locator.bbox.y1,
            )
            if locator.bbox is not None
            else None
        ),
        coordinate_frame=(
            CoordinateFrameDTO(
                space=locator.coordinate_frame.space.value,
                page_width=locator.coordinate_frame.page_width,
                page_height=locator.coordinate_frame.page_height,
                rotation=locator.coordinate_frame.rotation,
                transform_version=locator.coordinate_frame.transform_version,
            )
            if locator.coordinate_frame is not None
            else None
        ),
        coordinate_transform_version=locator.coordinate_transform_version,
    )


def _gate_dto(gate: GateSummary) -> GateResultDTO:
    return GateResultDTO(
        gate=gate.gate,
        gate_label=gate.gate,
        status=gate.status,
        status_label=gate_status_label(gate.status),
        detail=gate.detail,
    )


def _page_dto(view: OcrPageView) -> OcrPageDTO:
    status = (
        view.ocr.status.value
        if hasattr(view.ocr.status, "value")
        else view.ocr.status
    )
    return OcrPageDTO(
        ocr_page_id=view.ocr.ocr_page_id,
        page_artifact_id=view.ocr.page_artifact_id,
        source_document_version_id=(
            view.source_document_version_id or view.ocr.page_artifact_id
        ),
        page_number=view.ocr.page_number,
        source_sha256=view.ocr.source_sha256,
        raw_text=view.ocr.raw_text,
        raw_text_sha256=view.ocr.raw_text_sha256,
        status=status,
        status_label=ocr_page_status_label(status),
        processing_revision_id=view.revision_id,
        is_current_revision=view.is_current_revision,
        effective_text=view.effective.effective_text if view.effective else None,
        effective_text_sha256=(
            view.effective.effective_text_sha256 if view.effective else None
        ),
        selected_corrections=[_correction_dto(c) for c in view.selected_corrections],
        risk_scans=[_scan_dto(s) for s in view.risk_scans],
        risk_reviews=[_review_dto(r) for r in view.risk_reviews],
        locators=[_locator_dto(l) for l in view.locators],
    )


def _revision_dto(view: RevisionView) -> ProcessingRevisionDTO:
    if view.kind == "base" and view.base is not None:
        base = view.base
        status = base.status.value if hasattr(base.status, "value") else base.status
        return ProcessingRevisionDTO(
            evidence_processing_revision_id=view.revision_id,
            revision_kind="base",
            revision_kind_label=revision_kind_label("base"),
            evidence_snapshot_id=base.evidence_snapshot_id,
            base_processing_revision_id=None,
            project_id=base.project_id,
            subject_id=base.subject_id,
            review_episode_id=base.review_episode_id,
            status=status,
            status_label=snapshot_status_label(status),
            is_activatable=False,
            is_current=view.is_current,
            manifest_sha256=base.manifest_sha256,
            completion_manifest_sha256=None,
            pages=[
                _revision_page_dto(page, view.page_dimensions.get(page.entry_id))
                for page in base.manifest
            ],
            risk_flag_count=view.risk_flag_count,
            pending_risk_flag_count=view.pending_risk_flag_count,
            gates=[_gate_dto(g) for g in view.gates],
            created_at=_as_utc(base.created_at),
            created_by=base.created_by,
        )
    complete = view.complete
    assert complete is not None  # 读取服务保证 complete 视图携带完整修订
    status = (
        complete.status.value if hasattr(complete.status, "value") else complete.status
    )
    return ProcessingRevisionDTO(
        evidence_processing_revision_id=view.revision_id,
        revision_kind="complete",
        revision_kind_label=revision_kind_label("complete"),
        evidence_snapshot_id=complete.evidence_snapshot_id,
        base_processing_revision_id=complete.base_processing_revision_id,
        project_id=complete.project_id,
        subject_id=complete.subject_id,
        review_episode_id=complete.review_episode_id,
        status=status,
        status_label=snapshot_status_label(status),
        is_activatable=complete.is_activatable,
        is_current=view.is_current,
        manifest_sha256=complete.manifest_sha256,
        completion_manifest_sha256=complete.completion_manifest_sha256,
        pages=[
            _revision_page_dto(page, view.page_dimensions.get(page.entry_id))
            for page in complete.manifest
        ],
        risk_flag_count=view.risk_flag_count,
        pending_risk_flag_count=view.pending_risk_flag_count,
        locator_ids=list(complete.locator_ids),
        risk_scan_ids=list(complete.risk_scan_ids),
        risk_review_ids=list(complete.risk_review_ids),
        correction_ids=list(complete.correction_ids),
        metadata_revision_ids=list(complete.metadata_revision_ids),
        referenced_document_revision_ids=list(
            complete.referenced_document_revision_ids
        ),
        resolution_revision_ids=list(complete.resolution_revision_ids),
        gates=[_gate_dto(g) for g in view.gates],
        created_at=_as_utc(complete.created_at),
        created_by=complete.created_by,
    )


def _revision_page_dto(
    page, dimensions: tuple[float, float] | None
) -> ProcessingRevisionPageDTO:
    status = page.status.value if hasattr(page.status, "value") else page.status
    return ProcessingRevisionPageDTO(
        entry_id=page.entry_id,
        position=page.position,
        source_document_version_id=page.source_document_version_id,
        page_number=page.page_number,
        original_frame=page.original_frame,
        page_artifact_id=page.page_artifact_id,
        ocr_page_id=page.ocr_page_id,
        status=status,
        status_label=page_artifact_status_label(status),
        failure_reason=page.failure_reason,
        image_available=dimensions is not None,
        page_width=dimensions[0] if dimensions is not None else None,
        page_height=dimensions[1] if dimensions is not None else None,
    )


def _activation_dto(event) -> ActivationEventDTO:
    kind = event.event_kind.value if hasattr(event.event_kind, "value") else event.event_kind
    return ActivationEventDTO(
        event_id=event.event_id,
        review_episode_id=event.review_episode_id,
        activation_seq=event.activation_seq,
        event_kind=kind,
        event_kind_label=activation_event_kind_label(kind),
        from_snapshot_id=event.from_snapshot_id,
        from_revision_id=event.from_revision_id,
        to_snapshot_id=event.to_snapshot_id,
        to_revision_id=event.to_revision_id,
        reason=event.reason,
        actor=event.actor,
        candidate_id=event.candidate_id,
        expected_revision=event.expected_revision,
        resulting_episode_revision=event.resulting_episode_revision,
        snapshot_status_transitioned=event.snapshot_status_transitioned,
        created_at=_as_utc(event.created_at),
    )


def _resolution_dto(resolution) -> ReferencedDocumentResolutionDTO | None:
    if resolution is None:
        return None
    status = (
        resolution.status.value
        if hasattr(resolution.status, "value")
        else resolution.status
    )
    return ReferencedDocumentResolutionDTO(
        resolution_revision_id=resolution.resolution_revision_id,
        status=status,
        status_label=referenced_document_resolution_label(status),
        source_document_version_id=resolution.source_document_version_id,
        revision=resolution.revision,
        created_by=resolution.created_by,
        created_at=_as_utc(resolution.created_at),
    )


def _referenced_dto(view: ReferencedHeadView) -> ReferencedDocumentDTO:
    revision = view.revision
    origin = (
        revision.origin.value if hasattr(revision.origin, "value") else revision.origin
    )
    status = (
        revision.status.value if hasattr(revision.status, "value") else revision.status
    )
    return ReferencedDocumentDTO(
        revision_id=revision.revision_id,
        referenced_document_id=revision.referenced_document_id,
        project_id=revision.project_id,
        subject_id=revision.subject_id,
        review_episode_id=revision.review_episode_id,
        description=revision.description,
        document_type=revision.document_type,
        source_party=revision.source_party,
        origin=origin,
        origin_label=referenced_document_origin_label(origin),
        pattern_version=revision.pattern_version,
        status=status,
        status_label=referenced_document_status_label(status),
        user_reviewed=revision.user_reviewed,
        reason=revision.reason,
        revision=revision.revision,
        supersedes_revision_id=revision.supersedes_revision_id,
        trigger_locator_id=revision.trigger_locator_id,
        resolution=_resolution_dto(view.resolution),
        created_at=_as_utc(revision.created_at),
        created_by=revision.created_by,
    )


# ------------------------------------------------------------------ 页读取


@router.get(
    "/api/v2/ocr-pages/{ocr_page_id}",
    response_model=OcrPageDTO,
)
def get_ocr_page(
    ocr_page_id: str,
    request: Request,
    processing_revision_id: str | None = Query(default=None),
) -> OcrPageDTO:
    """页分层读取：原始识别 / 校对后文本 / 所选校对 / 风险核对 / 定位精度并列。

    ``processing_revision_id`` 指定投影校对层的完整处理修订；缺省时取当前活动处理
    修订（没有则无校对层）。指定修订时只返回该修订冻结的旁路工件。
    """
    view = _read(request).page_view(ocr_page_id, processing_revision_id)
    return _page_dto(view)


@router.get(
    "/api/v2/evidence-processing-revisions/{revision_id}/pages/{entry_id}/image",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}},
)
def get_processing_revision_page_image(
    revision_id: str,
    entry_id: str,
    request: Request,
) -> Response:
    """返回该处理版本冻结的原始页图；失败页不伪造空白图片。"""
    page = _read(request).page_image(revision_id, entry_id)
    return Response(
        content=page.content,
        media_type="image/png",
        headers={
            "Cache-Control": "private, max-age=31536000, immutable",
            "ETag": f'"{page.content_sha256}"',
            "X-Page-Width": str(page.page_width),
            "X-Page-Height": str(page.page_height),
        },
    )


# ------------------------------------------------------------------ 校对


@router.post(
    "/api/v2/ocr-pages/{ocr_page_id}/corrections",
    response_model=CorrectionCreateResponse,
    status_code=http_status.HTTP_201_CREATED,
)
def create_correction(
    ocr_page_id: str,
    body: CorrectionCreateRequest,
    request: Request,
    response: Response,
) -> CorrectionCreateResponse:
    """追加校对：必须带原识别哈希/原始范围/base 修订/预期修订号/幂等键。

    关键语义变化缺二次确认 -> 422；预期修订号不匹配 -> 409 保留提交值 + 服务端
    差异；同幂等键同请求回放（200），同幂等键异请求 409 冲突。
    """
    actor = body.actor or DEFAULT_ACTOR
    result = _command(request).create_correction(
        ocr_page_id=ocr_page_id,
        raw_text_sha256=body.raw_text_sha256,
        text_start=body.text_start,
        text_end=body.text_end,
        original_text=body.original_text,
        corrected_text=body.corrected_text,
        change_kind=body.change_kind,
        reason=body.reason,
        base_processing_revision_id=body.base_processing_revision_id,
        expected_revision=body.expected_revision,
        idempotency_key=body.idempotency_key,
        actor=actor,
        supersedes_correction_id=body.supersedes_correction_id,
        confirmation_actor=(
            body.confirmation.actor if body.confirmation is not None else None
        ),
        confirmation_at=(
            body.confirmation.at if body.confirmation is not None else None
        ),
        affected_scope=body.affected_scope,
        target_candidate_id=body.target_candidate_id,
        expected_candidate_event_seq=body.expected_candidate_event_seq,
    )
    if not result.created:
        response.status_code = http_status.HTTP_200_OK
    candidate_view = _read(request).processing_candidate(result.candidate_id)
    return CorrectionCreateResponse(
        correction=_correction_dto(result.correction),
        created=result.created,
        candidate_id=result.candidate_id,
        job_id=result.job_id,
        candidate_status=result.candidate_status,
        candidate_status_label=snapshot_status_label(result.candidate_status),
        candidate_event_seq=candidate_view.event_seq,
        complete_revision_id=candidate_view.candidate.complete_revision_id,
    )


# ------------------------------------------------------------------ 风险核对


@router.post(
    "/api/v2/ocr-pages/{ocr_page_id}/risk-reviews",
    response_model=RiskReviewCreateResponse,
    status_code=http_status.HTTP_201_CREATED,
)
def create_risk_review(
    ocr_page_id: str,
    body: RiskReviewCreateRequest,
    request: Request,
    response: Response,
) -> RiskReviewCreateResponse:
    """对单个风险条目追加核对决议；预期修订号不匹配 -> 409 保留提交值 + 差异。"""
    actor = body.actor or DEFAULT_ACTOR
    result = _command(request).create_risk_review(
        ocr_page_id=ocr_page_id,
        risk_flag_id=body.risk_flag_id,
        decision=body.decision,
        reason=body.reason,
        base_processing_revision_id=body.base_processing_revision_id,
        expected_revision=body.expected_revision,
        idempotency_key=body.idempotency_key,
        actor=actor,
        target_candidate_id=body.target_candidate_id,
        expected_candidate_event_seq=body.expected_candidate_event_seq,
    )
    if not result.created:
        response.status_code = http_status.HTTP_200_OK
    candidate_view = _read(request).processing_candidate(result.candidate_id)
    return RiskReviewCreateResponse(
        review=_review_dto(result.review),
        created=result.created,
        candidate_id=result.candidate_id,
        job_id=result.job_id,
        candidate_status=result.candidate_status,
        candidate_status_label=snapshot_status_label(result.candidate_status),
        candidate_event_seq=candidate_view.event_seq,
        complete_revision_id=candidate_view.candidate.complete_revision_id,
    )


@router.post(
    "/api/v2/ocr-pages/{ocr_page_id}/risk-page-reviews",
    response_model=PageRiskReviewCreateResponse,
    status_code=http_status.HTTP_201_CREATED,
)
def create_page_risk_review(
    ocr_page_id: str,
    body: PageRiskReviewCreateRequest,
    request: Request,
    response: Response,
) -> PageRiskReviewCreateResponse:
    """对页上全部待核对风险做一次原子核对，逐条不可变记录同事务物化。

    预期修订号不匹配 -> 409 保留提交值 + 差异；同幂等键回放 -> 200。
    """
    actor = body.actor or DEFAULT_ACTOR
    result = _command(request).create_page_risk_review(
        ocr_page_id=ocr_page_id,
        scan_id=body.scan_id,
        decision=body.decision,
        reason=body.reason,
        base_processing_revision_id=body.base_processing_revision_id,
        expected_revision=body.expected_revision,
        idempotency_key=body.idempotency_key,
        actor=actor,
        target_candidate_id=body.target_candidate_id,
        expected_candidate_event_seq=body.expected_candidate_event_seq,
    )
    if not result.created:
        response.status_code = http_status.HTTP_200_OK
    candidate_view = _read(request).processing_candidate(result.candidate_id)
    return PageRiskReviewCreateResponse(
        page_review=_page_review_dto(result.page_review),
        reviews=[_review_dto(r) for r in result.reviews],
        created=result.created,
        candidate_id=result.candidate_id,
        job_id=result.job_id,
        candidate_status=result.candidate_status,
        candidate_status_label=snapshot_status_label(result.candidate_status),
        candidate_event_seq=candidate_view.event_seq,
        complete_revision_id=candidate_view.candidate.complete_revision_id,
    )


# ------------------------------------------------------------------ 处理修订


@router.get(
    "/api/v2/evidence-processing-candidates/{candidate_id}",
    response_model=ProcessingCandidateDTO,
)
def get_processing_candidate(
    candidate_id: str, request: Request
) -> ProcessingCandidateDTO:
    """读取后台候选的持久状态，浏览器刷新不影响任务。"""
    view = _read(request).processing_candidate(candidate_id)
    candidate = view.candidate
    status = candidate.status.value if hasattr(candidate.status, "value") else candidate.status
    if candidate.job_id is None:
        from app.services.evidence_app_errors import AppInternalError

        raise AppInternalError("资料版本候选缺少持久任务")
    return ProcessingCandidateDTO(
        candidate_id=candidate.candidate_id,
        job_id=candidate.job_id,
        candidate_status=status,
        candidate_status_label=snapshot_status_label(status),
        candidate_event_seq=view.event_seq,
        complete_revision_id=candidate.complete_revision_id,
    )


@router.get(
    "/api/v2/evidence-processing-revisions/{revision_id}",
    response_model=ProcessingRevisionDTO,
)
def get_processing_revision(revision_id: str, request: Request) -> ProcessingRevisionDTO:
    """读取处理修订：kind/base ID/快照 ID/清单 hashes/可激活/逐门禁结果。

    ``is_current`` 只来自审核节点成对活动指针，绝不按创建时间/ID/状态推断。
    """
    return _revision_dto(_read(request).revision_view(revision_id))


@router.post(
    "/api/v2/evidence-processing-revisions/build",
    response_model=BuildRevisionResponse,
    status_code=http_status.HTTP_201_CREATED,
)
def build_processing_revision(
    body: BuildRevisionRequest,
    request: Request,
    response: Response,
) -> BuildRevisionResponse:
    """排队生成完整处理修订；请求只冻结输入并创建持久任务。

    后台取得任务执行权后才开始构建。同幂等键同输入回放同一候选；是否存在待核对
    风险由后台构建结果持久化，页面随后按任务状态引导用户继续核对。
    """
    actor = body.actor or DEFAULT_ACTOR
    result = _command(request).build_revision(
        evidence_snapshot_id=body.evidence_snapshot_id,
        base_processing_revision_id=body.base_processing_revision_id,
        expected_revision=body.expected_revision,
        idempotency_key=body.idempotency_key,
        actor=actor,
        scanner_rule_version=body.scanner_rule_version,
        selected_locator_ids=body.selected_locator_ids,
    )
    if not result.created:
        response.status_code = http_status.HTTP_200_OK
    revision_dto = None
    if result.complete_revision_id is not None:
        revision_dto = _revision_dto(
            _read(request).revision_view(result.complete_revision_id)
        )
    candidate_view = _read(request).processing_candidate(result.candidate_id)
    return BuildRevisionResponse(
        candidate_id=result.candidate_id,
        job_id=result.job_id,
        candidate_status=result.candidate_status,
        candidate_status_label=snapshot_status_label(result.candidate_status),
        candidate_event_seq=candidate_view.event_seq,
        complete_revision_id=candidate_view.candidate.complete_revision_id,
        created=result.created,
        revision=revision_dto,
    )


# ------------------------------------------------------------------ 激活 / 回滚


@router.post(
    "/api/v2/evidence-processing-revisions/{revision_id}/activate",
    response_model=ActivationEventDTO,
    status_code=http_status.HTTP_201_CREATED,
)
def activate_revision(
    revision_id: str,
    body: ActivateRequest,
    request: Request,
    response: Response,
) -> ActivationEventDTO:
    """启用完整处理修订：必须携带预期审核节点修订号与幂等键；返回事件/旧新指针
    对/新修订号。同键同命令幂等回放（200）；base 修订永不可激活。"""
    actor = body.actor or DEFAULT_ACTOR
    read = _read(request)
    view = read.revision_view(revision_id)
    if view.kind != "complete" or view.complete is None:
        from app.services.evidence_api_command_service import (
            NonCompleteRevision409Error,
        )

        raise NonCompleteRevision409Error(
            revision_id=revision_id,
            submitted=body.model_dump(mode="json"),
        )
    complete = view.complete
    result = _command(request).activate(
        target_snapshot_id=complete.evidence_snapshot_id,
        target_revision_id=revision_id,
        expected_revision=body.expected_revision,
        idempotency_key=body.idempotency_key,
        actor=actor,
        reason=body.reason,
        candidate_id=body.candidate_id,
        job_id=body.job_id,
    )
    if not result.created:
        response.status_code = http_status.HTTP_200_OK
    return _activation_dto(result.event)


@router.post(
    "/api/v2/evidence-processing-revisions/{revision_id}/rollback",
    response_model=ActivationEventDTO,
    status_code=http_status.HTTP_201_CREATED,
)
def rollback_revision(
    revision_id: str,
    body: ActivateRequest,
    request: Request,
    response: Response,
) -> ActivationEventDTO:
    """回滚到历史活动版本对：追加 rollback 事件并切换成对指针，不改写旧历史。"""
    actor = body.actor or DEFAULT_ACTOR
    read = _read(request)
    view = read.revision_view(revision_id)
    if view.kind != "complete" or view.complete is None:
        from app.services.evidence_api_command_service import (
            NonCompleteRevision409Error,
        )

        raise NonCompleteRevision409Error(
            revision_id=revision_id,
            submitted=body.model_dump(mode="json"),
        )
    complete = view.complete
    result = _command(request).rollback(
        target_snapshot_id=complete.evidence_snapshot_id,
        target_revision_id=revision_id,
        expected_revision=body.expected_revision,
        idempotency_key=body.idempotency_key,
        actor=actor,
        reason=body.reason,
    )
    if not result.created:
        response.status_code = http_status.HTTP_200_OK
    return _activation_dto(result.event)


def _require_referenced_head(request, referenced_document_id: str) -> ReferencedHeadView:
    head = _read(request).referenced_head(referenced_document_id)
    if head is None:
        from app.services.evidence_app_errors import AppNotFoundError

        raise AppNotFoundError(f"被提及资料 {referenced_document_id} 不存在")
    return head


# ------------------------------------------------------------------ 被提及资料


@router.post(
    "/api/v2/subjects/{subject_id}/referenced-documents",
    response_model=ReferencedDocumentDTO,
    status_code=http_status.HTTP_201_CREATED,
)
def create_referenced_document(
    subject_id: str,
    body: ReferencedDocumentCreateRequest,
    request: Request,
    response: Response,
) -> ReferencedDocumentDTO:
    """登记被提及资料（初始 proposed 修订）；确定性模式绝不自动 confirmed。"""
    actor = body.actor or DEFAULT_ACTOR
    result = _command(request).create_referenced_document(
        subject_id=subject_id,
        review_episode_id=body.review_episode_id,
        expected_revision=body.expected_revision,
        description=body.description,
        document_type=body.document_type,
        source_party=body.source_party,
        origin=body.origin,
        pattern_version=body.pattern_version,
        trigger_locator_id=body.trigger_locator_id,
        idempotency_key=body.idempotency_key,
        actor=actor,
    )
    if not result.created:
        response.status_code = http_status.HTTP_200_OK
    head = _require_referenced_head(request, result.revision.referenced_document_id)
    return _referenced_dto(head)


@router.get(
    "/api/v2/subjects/{subject_id}/referenced-documents",
    response_model=ReferencedDocumentListDTO,
)
def list_referenced_documents(
    subject_id: str,
    request: Request,
    review_episode_id: str = Query(...),
) -> ReferencedDocumentListDTO:
    """某审核节点下被提及资料的当前登记链头 + 当前满足状态（只读投影）。"""
    _read(request).require_subject_episode(subject_id, review_episode_id)
    heads = _read(request).referenced_heads(review_episode_id)
    return ReferencedDocumentListDTO(
        subject_id=subject_id,
        review_episode_id=review_episode_id,
        items=[_referenced_dto(view) for view in heads],
    )


@router.patch(
    "/api/v2/referenced-documents/{referenced_document_id}",
    response_model=ReferencedDocumentDTO,
)
def revise_referenced_document(
    referenced_document_id: str,
    body: ReferencedDocumentReviseRequest,
    request: Request,
) -> ReferencedDocumentDTO:
    """修改候选描述/类型/来源方：追加新修订，保留触发定位与状态历史。"""
    actor = body.actor or DEFAULT_ACTOR
    _command(request).revise_referenced_document(
        referenced_document_id=referenced_document_id,
        description=body.description,
        document_type=body.document_type,
        source_party=body.source_party,
        reason=body.reason,
        expected_revision=body.expected_revision,
        idempotency_key=body.idempotency_key,
        actor=actor,
    )
    head = _require_referenced_head(request, referenced_document_id)
    return _referenced_dto(head)


@router.post(
    "/api/v2/referenced-documents/{referenced_document_id}/confirm",
    response_model=ReferencedDocumentDTO,
)
def confirm_referenced_document(
    referenced_document_id: str,
    body: ReferencedDocumentConfirmRequest,
    request: Request,
) -> ReferencedDocumentDTO:
    """确认候选：必须携带可回放触发定位（无法提供 trigger 时不能伪装成原文提及）。"""
    actor = body.actor or DEFAULT_ACTOR
    _command(request).confirm_referenced_document(
        referenced_document_id=referenced_document_id,
        trigger_locator_id=body.trigger_locator_id,
        reason=body.reason,
        expected_revision=body.expected_revision,
        idempotency_key=body.idempotency_key,
        actor=actor,
    )
    head = _require_referenced_head(request, referenced_document_id)
    return _referenced_dto(head)


@router.post(
    "/api/v2/referenced-documents/{referenced_document_id}/dismiss",
    response_model=ReferencedDocumentDTO,
)
def dismiss_referenced_document(
    referenced_document_id: str,
    body: ReferencedDocumentDismissRequest,
    request: Request,
) -> ReferencedDocumentDTO:
    """解除候选：只追加 dismissed 修订，不删除候选/触发原文/历史。"""
    actor = body.actor or DEFAULT_ACTOR
    _command(request).dismiss_referenced_document(
        referenced_document_id=referenced_document_id,
        reason=body.reason,
        expected_revision=body.expected_revision,
        idempotency_key=body.idempotency_key,
        actor=actor,
    )
    head = _require_referenced_head(request, referenced_document_id)
    return _referenced_dto(head)


@router.post(
    "/api/v2/referenced-documents/{referenced_document_id}/resolve",
    response_model=ReferencedDocumentResolutionDTO,
    status_code=http_status.HTTP_201_CREATED,
)
def resolve_referenced_document(
    referenced_document_id: str,
    body: ReferencedDocumentResolveRequest,
    request: Request,
    response: Response,
) -> ReferencedDocumentResolutionDTO:
    """追加满足修订：provided 必须绑定该快照成员资料版本；unresolved 无绑定。"""
    actor = body.actor or DEFAULT_ACTOR
    result = _command(request).resolve_referenced_document(
        referenced_document_id=referenced_document_id,
        status=body.status,
        source_document_version_id=body.source_document_version_id,
        expected_revision=body.expected_revision,
        idempotency_key=body.idempotency_key,
        actor=actor,
    )
    if not result.created:
        response.status_code = http_status.HTTP_200_OK
    dto = _resolution_dto(result.resolution)
    assert dto is not None  # 命令服务保证返回已创建的满足修订
    return dto


@router.delete(
    "/api/v2/referenced-documents/{referenced_document_id}/resolution",
    response_model=ReferencedDocumentResolutionDTO,
)
def delete_referenced_document_resolution(
    referenced_document_id: str,
    request: Request,
    expected_revision: int = Query(..., ge=0),
    idempotency_key: str = Query(..., min_length=1, max_length=256),
    actor: str | None = Query(default=None, max_length=128),
) -> ReferencedDocumentResolutionDTO:
    """解除关联：追加 unresolved 满足修订，不删除旧满足关系。"""
    result = _command(request).unresolve_referenced_document(
        referenced_document_id=referenced_document_id,
        expected_revision=expected_revision,
        idempotency_key=idempotency_key,
        actor=actor or DEFAULT_ACTOR,
    )
    dto = _resolution_dto(result.resolution)
    assert dto is not None  # 命令服务保证返回已创建的满足修订
    return dto
