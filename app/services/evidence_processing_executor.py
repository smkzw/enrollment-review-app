"""证据处理 Job 的持久页级执行器（Slice 4.3，worker_03）。

把确认后创建的 ``evidence_processing`` 持久 Job 接入页级持久工作项、共享 oMLX
门禁、租约代次/晚到拒绝、渲染背压、文件页检查点、限定重试取消恢复与只读进度。
本模块是**持久执行器**，不是 ``process_source`` 便捷路径：

- 页工作租约（``PageWorkLeaseRepository``）只防止同一页被重复 worker 执行，
  不是并发额度；先取页租约，再在每次真实外部推理前取共享 oMLX 门禁租约；
- 固定顺序：页工作租约 -> 共享门禁租约 -> 推理；两租约在 ``finally`` 释放，
  长推理期间心跳续租；本地渲染/解码使用独立有界并发，不占门禁额度；
- 分阶段提交：先在事务内落 prepare（识别配置/原始请求/PROCESSING 页行），
  再在事务外经门禁推理，最后 ``commit_guard`` + OCRPage + 终态尝试在同一事务
  提交；晚到被拒尝试在独立审计事务追加，绝不进入成功缓存或处理清单；
- 提交核对页工作 owner/代次/过期与冻结输入/识别身份（缓存键重算），晚到结果
  拒绝；``PageArtifactOutcome.technical_detail``/``OcrRecognition.technical_detail``
  只写尝试/检查点技术记录，用户可见文字恒为稳定中文；
- 重试只处理失败/受影响页（成功页经不可变缓存去重跳过）；取消在页边界检查；
  崩溃由租约过期 + 启动恢复处理，不留永久处理中状态；
- 全部页达到终态后冻结不可变基础证据处理修订（明确不可激活，不触碰活动指针）；
- 每个文件完成写入 ``page_progress`` JobEvent，SSE 只读回放持久事件；
- 基础修订冻结后立即生成风险提示与诚实定位，增量复用页以追加记录
  沿用上一有效版本的核对/校对，使用户首次打开工作台即可看到真实门禁。

本模块不实现 Slice 4.4 的校正/风险门禁/定位器/激活，也不建立任何活动指针。
"""
from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Iterator
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, as_completed, wait
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.domain.contracts.enums import (
    ExtractionRoute,
    JobEventType,
    OcrAttemptStatus,
    OcrFailureCategory,
    OCRPageStatus,
    OcrRunStatus,
    PageArtifactStatus,
    ProcessingRevisionStatus,
    SnapshotStatus,
)
from app.domain.contracts.evidence_ingestion import (
    EvidenceSnapshot,
    SourceDocumentVersion,
)
from app.domain.contracts.evidence_processing import (
    EvidenceProcessingRevision,
    EvidenceProcessingRevisionPage,
    OCRAttempt,
    OCRRun,
)
from app.domain.contracts.evidence_upload import EVIDENCE_PROCESSING_JOB_TYPE
from app.domain.contracts.ocr import (
    OCRPage,
    OCRProfile,
    PageArtifact,
    PageQualityMetrics,
)
from app.domain.publication import evidence_processing_manifest_hash
from app.evidence.artifacts import ArtifactStore
from app.evidence.coordinates import COORDINATE_TRANSFORM_VERSION
from app.evidence.fingerprint import build_ocr_cache_key, build_profile_fingerprint
from app.evidence.locator_proof import NATIVE_COORDINATES_SCHEMA
from app.evidence.ocr_adapter import (
    INFERENCE_FAILURE_REASON,
    OcrFailure,
    PreparedOcrRequest,
    SegmentInferenceError,
    TextOnlyOcrAdapter,
    combine_segment_results,
    composite_segment_failure_response,
)
from app.evidence.page_processor import (
    DECODER_VERSION_BY_KIND,
    _build_page_artifact_detailed,
    decide_route_detailed,
)
from app.evidence.paging import PageInput, PagePlan, PagingError, page_source_document
from app.services.omlx_gate import (
    GATE_OWNER,
    OmlxGateCapacityError,
    OmlxGateClient,
    OmlxGateError,
    OmlxGateUnavailableError,
    OmlxLeaseLostError,
)
from app.storage.codecs import utc_now, verify_payload_sha256
from app.storage.config import DataPaths
from app.storage.evidence_repositories import (
    BlobRepository,
    EvidenceSnapshotRepository,
    SourceDocumentRepository,
)
from app.storage.models import JobRecord
from app.storage.ocr_models import EvidenceProcessingRevisionRecord
from app.storage.ocr_repositories import (
    EvidenceProcessingRevisionRepository,
    OcrAttemptRepository,
    OcrPageRepository,
    OCRProfileRepository,
    OcrRunRepository,
    PageArtifactRepository,
    PageLeaseBusyError,
    PageLeaseLostError,
    PageWorkLeaseRepository,
)
from app.workflow.errors import ProcessDeath, StepFailure
from app.workflow.jobstore import JobStore
from app.workflow.runner import StepContext, StepExecutor

logger = logging.getLogger(__name__)

#: 证据处理步骤的自动重试预算（可重试失败按退避自动重试；超预算进入终败需人工重试）。
EVIDENCE_PROCESSING_MAX_ATTEMPTS = 3

#: 渲染/解码独立有界并发（不占共享门禁额度）。
DEFAULT_RENDER_CONCURRENCY = 2

#: 单个执行器内跨文件共享的页处理并发；真实 OCR 仍必须逐请求领取共享 oMLX
#: 门禁，因而跨任务、跨进程的全局峰值继续由门禁限制为 8。
DEFAULT_PAGE_PROCESSING_CONCURRENCY = 8

#: 页工作租约 TTL（长推理期间由心跳续租）。
DEFAULT_PAGE_LEASE_TTL = timedelta(seconds=120)

_SNAPSHOT_MISSING_CODE = "SNAPSHOT_MISSING"
_SOURCE_BLOB_MISSING_CODE = "SOURCE_BLOB_MISSING"
_CANCEL_CODE = "CANCEL_REQUESTED"

_EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

_SOURCE_TEXT_PROVIDER = "local-deterministic"
_SOURCE_TEXT_MODEL_ID = "source-text-artifact"
_SOURCE_TEXT_PARSER_VERSION = "source-text-page/v1"


@dataclass(frozen=True)
class PageOutcome:
    """一页的持久处理结果（供执行器汇总与清单构建）。"""

    page_number: int
    original_frame: str | None
    artifact: Any  # PageArtifact
    route: ExtractionRoute | None
    ocr_page: OCRPage | None = None
    retryable: bool = False
    deferred: bool = False
    technical_detail: str | None = None


@dataclass
class FileProcessingResult:
    """一份来源文件处理结果（页清单 + 运行汇总）。"""

    source_document_version_id: str
    file_name: str
    media_kind: str
    page_total: int = 0
    page_succeeded: int = 0
    page_failed: int = 0
    retryable_failures: int = 0
    ocr_run_id: str | None = None
    outcomes: list[PageOutcome] = field(default_factory=list)


@dataclass
class _PreparedFileProcessing:
    """已完成分页/渲染、等待进入执行器级共享页队列的一份资料。"""

    version: SourceDocumentVersion
    source_sha256: str
    result: FileProcessingResult
    page_items: list[tuple[PageInput, tuple[Any, ExtractionRoute | None, str | None]]]
    ocr_run_id: str | None = None


@dataclass
class EvidenceProcessingExecutorConfig:
    """执行器配置：会话工厂、数据根、门禁、适配器、推理与并发边界。"""

    session_factory: sessionmaker[Session]
    data_paths: DataPaths
    now: Callable[[], datetime] = utc_now
    worker_id: str = "v2-evidence-worker"
    adapter: TextOnlyOcrAdapter | None = None
    gate: OmlxGateClient | None = None
    #: 真实推理函数 ``(request_payload, page_image_bytes) -> InferenceResult``；
    #: 由调用方注入，执行器用共享门禁租约包住它（绝不绕过门禁直连模型）。
    inference: Callable[[dict[str, Any], bytes], Any] | None = None
    doc_converter: Any | None = None
    render_concurrency: int = DEFAULT_RENDER_CONCURRENCY
    page_processing_concurrency: int = DEFAULT_PAGE_PROCESSING_CONCURRENCY
    page_lease_ttl: timedelta = DEFAULT_PAGE_LEASE_TTL
    #: 每处理多少页检查一次持久取消请求（页边界安全取消）。
    cancel_check_every: int = 1
    #: 门禁脚本缺失是否视为可重试失败（测试可注入覆盖）。
    gate_unavailable_retryable: bool = True


class _CancelBoundary(Exception):
    """内部信号：在页边界检测到持久取消请求。"""


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _media_kind(media_type: str, file_name: str) -> str | None:
    mt = (media_type or "").lower()
    if mt == "application/pdf":
        return "pdf"
    if "wordprocessingml" in mt:
        return "docx"
    if mt in {"application/msword", "application/vnd.ms-word"}:
        return "doc"
    if mt in {"text/plain", "text/plain; charset=utf-8"}:
        return "text"
    # TIFF 走 paging 的 image 分发：内部按魔数检测多帧并产出 tiff 页。
    if mt == "image/tiff":
        return "image"
    if mt.startswith("image/"):
        return "image"
    suffix = Path(file_name).suffix.lower()
    if suffix == ".pdf":
        return "pdf"
    if suffix == ".docx":
        return "docx"
    if suffix == ".doc":
        return "doc"
    if suffix == ".txt":
        return "text"
    if suffix in {".tif", ".tiff"}:
        return "image"
    if suffix in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}:
        return "image"
    return None


def _snapshot_from_payload(session: Session, payload: dict[str, Any]) -> EvidenceSnapshot:
    snapshot_id = payload.get("snapshot_id")
    if not snapshot_id:
        raise StepFailure(
            retryable=False,
            error_code=_SNAPSHOT_MISSING_CODE,
            detail="任务缺少快照标识，无法开始资料处理。",
        )
    return EvidenceSnapshotRepository(session).get(snapshot_id)


def create_evidence_processing_executor(
    config: EvidenceProcessingExecutorConfig,
) -> StepExecutor:
    """构建 ``evidence_processing`` 步骤的持久页级执行器。"""
    adapter = config.adapter or TextOnlyOcrAdapter()
    gate = config.gate or OmlxGateClient(owner=GATE_OWNER)

    def execute(context: StepContext) -> dict[str, Any]:
        if context.last_checkpoint is not None:
            return dict(context.last_checkpoint)
        snapshot_id = str(context.job_payload.get("snapshot_id") or "")
        try:
            return _execute(
                config=config,
                context=context,
                adapter=adapter,
                gate=gate,
            )
        except ProcessDeath:
            # 强制中断不伪造失败事件；候选保持处理中，由租约恢复后继续。
            raise
        except StepFailure as failure:
            _record_snapshot_failure(
                config,
                snapshot_id,
                failure,
                final_attempt=context.attempt >= context.max_attempts,
            )
            raise
        except Exception:
            _transition_snapshot_if_processing(
                config,
                snapshot_id,
                event="terminal_error",
                new_status=SnapshotStatus.TERMINAL_FAILURE,
                reason="资料处理遇到无法继续的异常，本次候选已停止。",
            )
            raise

    return execute


# ---------------------------------------------------------------------------
# 执行主流程
# ---------------------------------------------------------------------------


def _execute(
    *,
    config: EvidenceProcessingExecutorConfig,
    context: StepContext,
    adapter: TextOnlyOcrAdapter,
    gate: OmlxGateClient,
) -> dict[str, Any]:
    job_id = context.job_id
    payload = context.job_payload

    with config.session_factory() as session:
        snapshot = _snapshot_from_payload(session, payload)
        member_versions: list[tuple[Any, SourceDocumentVersion]] = []
        for member in snapshot.members:
            version = SourceDocumentRepository(session).get(member.source_document_version_id)
            member_versions.append((member, version))

    _start_or_resume_snapshot(config, snapshot.evidence_snapshot_id)

    artifact_store = ArtifactStore(config.data_paths)
    plans: list[tuple[Any, SourceDocumentVersion, PagePlan | None]] = []
    for member, version in member_versions:
        content = _read_blob(config, version)
        kind = _media_kind(version.media_type, version.file_name)
        if kind is None:
            # 不应进入快照的不支持格式：整文件一个永久失败页（显式失败）。
            plans.append((member, version, None))
            continue
        try:
            plan = page_source_document(
                content=content,
                media_kind=kind,
                source_sha256=version.source_blob_sha256,
                doc_converter=config.doc_converter,
            )
        except PagingError:
            plans.append((member, version, None))
            continue
        plans.append((member, version, plan))

    total_pages = sum(plan.page_total if plan is not None else 1 for _m, _v, plan in plans)
    progress_state = {
        version.source_document_version_id: FileProcessingResult(
            source_document_version_id=version.source_document_version_id,
            file_name=version.file_name,
            media_kind=_media_kind(version.media_type, version.file_name) or "unsupported",
            page_total=plan.page_total if plan is not None else 1,
        )
        for _member, version, plan in plans
    }

    def observe_page(result: FileProcessingResult) -> None:
        progress_state[result.source_document_version_id] = result
        _emit_progress(
            config,
            job_id,
            file_result=result,
            file_results=progress_state.values(),
            total_pages=total_pages,
        )

    # 页面清单落地后先持久化一次全资料快照，使尚未开始的候选资料立即可见。
    with config.session_factory() as session:
        has_progress = any(
            row.event.event_type == JobEventType.PAGE_PROGRESS
            for row in JobStore(session).list_event_rows(job_id)
        )
    if not has_progress:
        _emit_progress(
            config,
            job_id,
            file_result=None,
            file_results=progress_state.values(),
            total_pages=total_pages,
        )

    try:
        file_results = _process_files(
            config=config,
            job_id=job_id,
            plans=plans,
            adapter=adapter,
            gate=gate,
            artifact_store=artifact_store,
            on_page_progress=observe_page,
        )
        # 最后一页之后也属于安全边界；否则单页/末页取消只能在 JobRunner
        # 下一轮看到，执行器可能已经冻结不可激活修订。
        _maybe_cancel(config, job_id)
    except _CancelBoundary:
        raise StepFailure(
            retryable=False,
            error_code=_CANCEL_CODE,
            detail="任务已按取消请求在安全边界停止。",
        ) from None

    if any(result.retryable_failures for result in file_results):
        raise StepFailure(
            retryable=True,
            error_code="PAGE_OCR_RETRYABLE",
            detail="部分页面识别尚未完成，将仅重试未完成页面。",
        )

    # 永久失败（文件无法分页/渲染/解码失败等不可重试页）：任一失败页都阻止冻结
    # 基础处理修订并阻止任务完成——成功兄弟页产物保持不可变，但不得以 READY 修订
    # 或 completed 任务伪装“完整”（Slice 4.3 停止点：部分失败不得呈现为完整）。
    if any(result.page_failed > 0 for result in file_results):
        raise StepFailure(
            retryable=False,
            error_code="PAGE_PROCESSING_FAILED",
            detail="部分页面因文件或页面处理失败未能完成，未发布本次处理结果，请检查后重试。",
        )

    revision_id = _freeze_revision(config, snapshot, file_results)
    try:
        from app.services.evidence_sidecar_preparation import (
            EvidenceSidecarPreparationService,
        )

        EvidenceSidecarPreparationService(
            config.session_factory, artifact_store
        ).prepare(revision_id)
    except Exception as exc:
        raise StepFailure(
            retryable=True,
            error_code="EVIDENCE_SIDECAR_PREPARATION_FAILED",
            detail="识别结果已保存，但风险提示与原文定位尚未准备完成，系统将继续处理。",
        ) from exc
    _transition_snapshot_if_processing(
        config,
        snapshot.evidence_snapshot_id,
        event="checkpoint_success",
        new_status=SnapshotStatus.PROCESSING,
        reason="页面与文字识别基础处理已完成，等待后续定位、风险核对与校对。",
    )
    return _build_checkpoint(snapshot, revision_id, file_results)


def _start_or_resume_snapshot(
    config: EvidenceProcessingExecutorConfig, snapshot_id: str
) -> None:
    """把候选快照推进到本次执行允许的处理中状态。"""
    with config.session_factory() as session, session.begin():
        repo = EvidenceSnapshotRepository(session)
        current = repo.current_status(snapshot_id)
        if current == SnapshotStatus.STAGED:
            repo.transition_status(
                snapshot_id,
                event="worker_start",
                new_status=SnapshotStatus.PROCESSING,
                actor=config.worker_id,
                reason="已开始处理本次资料。",
            )
        elif current == SnapshotStatus.RETRYABLE_FAILURE:
            repo.transition_status(
                snapshot_id,
                event="retry",
                new_status=SnapshotStatus.PROCESSING,
                actor=config.worker_id,
                reason="正在继续处理上次未完成的页面。",
            )
        elif current != SnapshotStatus.PROCESSING:
            raise StepFailure(
                retryable=False,
                error_code="SNAPSHOT_STATE_INVALID",
                detail="本次资料当前状态不允许继续处理，请重新建立资料候选。",
            )


def _transition_snapshot_if_processing(
    config: EvidenceProcessingExecutorConfig,
    snapshot_id: str,
    *,
    event: str,
    new_status: SnapshotStatus,
    reason: str,
) -> None:
    """只从处理中追加一次状态事件；重复故障提交不覆盖既有历史。"""
    if not snapshot_id:
        return
    with config.session_factory() as session, session.begin():
        repo = EvidenceSnapshotRepository(session)
        if repo.current_status(snapshot_id) != SnapshotStatus.PROCESSING:
            return
        repo.transition_status(
            snapshot_id,
            event=event,
            new_status=new_status,
            actor=config.worker_id,
            reason=reason,
        )


def _record_snapshot_failure(
    config: EvidenceProcessingExecutorConfig,
    snapshot_id: str,
    failure: StepFailure,
    *,
    final_attempt: bool = False,
) -> None:
    if failure.error_code == _CANCEL_CODE:
        event = "cancel_at_safe_boundary"
        status = SnapshotStatus.CANCELLED
        reason = "已按取消请求在安全边界停止处理。"
    elif failure.retryable and not final_attempt:
        event = "retryable_error"
        status = SnapshotStatus.RETRYABLE_FAILURE
        reason = "部分页面暂未完成，系统将仅继续处理未完成部分。"
    else:
        event = "terminal_error"
        status = SnapshotStatus.TERMINAL_FAILURE
        reason = "资料或页面无法继续处理，本次候选已停止。"
    _transition_snapshot_if_processing(
        config,
        snapshot_id,
        event=event,
        new_status=status,
        reason=reason,
    )


def _read_blob(config: EvidenceProcessingExecutorConfig, version: SourceDocumentVersion) -> bytes:
    with config.session_factory() as session:
        blob = BlobRepository(session).get(version.source_blob_sha256)
        path = config.data_paths.boundary.require_v2_target(
            config.data_paths.root / blob.storage_ref
        )
    if not path.is_file():
        raise StepFailure(
            retryable=True,
            error_code=_SOURCE_BLOB_MISSING_CODE,
            detail="资料副本暂时不可用，请稍后重试。",
        )
    return path.read_bytes()


def _maybe_cancel(config: EvidenceProcessingExecutorConfig, job_id: str) -> None:
    """页/文件边界检查持久取消请求：已请求则在安全边界抛取消信号。"""
    with config.session_factory() as session:
        status = JobStore(session, now=config.now).job_status(job_id)
        if status.cancel_requested or status.state == "cancel_requested":
            raise _CancelBoundary()


# ---------------------------------------------------------------------------
# 单文件处理
# ---------------------------------------------------------------------------


def _process_files(
    *,
    config: EvidenceProcessingExecutorConfig,
    job_id: str,
    plans: list[tuple[Any, SourceDocumentVersion, PagePlan | None]],
    adapter: TextOnlyOcrAdapter,
    gate: OmlxGateClient,
    artifact_store: ArtifactStore,
    on_page_progress: Callable[[FileProcessingResult], None] | None = None,
) -> list[FileProcessingResult]:
    """以单个全局页池处理全部资料，避免文件之间的队头阻塞。"""
    prepared_files: list[_PreparedFileProcessing] = []
    try:
        for _member, version, plan in plans:
            _maybe_cancel(config, job_id)
            prepared = _prepare_file(
                config=config,
                job_id=job_id,
                version=version,
                plan=plan,
                adapter=adapter,
                artifact_store=artifact_store,
            )
            prepared_files.append(prepared)
            if not prepared.page_items and on_page_progress is not None:
                on_page_progress(prepared.result)
        _run_prepared_files(
            config=config,
            job_id=job_id,
            prepared_files=prepared_files,
            adapter=adapter,
            gate=gate,
            artifact_store=artifact_store,
            on_page_progress=on_page_progress,
        )
    except _CancelBoundary:
        _finalize_prepared_files(config, prepared_files, status=OcrRunStatus.CANCELLED)
        raise
    except ProcessDeath:
        # 保留持久 RUNNING/页租约，由租约过期与启动恢复接管。
        raise
    except Exception:
        _finalize_prepared_files(config, prepared_files, status=OcrRunStatus.FAILED)
        raise
    return [prepared.result for prepared in prepared_files]


def _process_file(
    *,
    config: EvidenceProcessingExecutorConfig,
    job_id: str,
    member_id: str,
    version: SourceDocumentVersion,
    plan: PagePlan | None,
    adapter: TextOnlyOcrAdapter,
    gate: OmlxGateClient,
    artifact_store: ArtifactStore,
    on_page_progress: Callable[[FileProcessingResult], None] | None = None,
) -> FileProcessingResult:
    """兼容单文件调用；页并发仍由同一个共享调度器统一限制。"""
    del member_id
    prepared = _prepare_file(
        config=config,
        job_id=job_id,
        version=version,
        plan=plan,
        adapter=adapter,
        artifact_store=artifact_store,
    )
    if not prepared.page_items and on_page_progress is not None:
        on_page_progress(prepared.result)
    try:
        _run_prepared_files(
            config=config,
            job_id=job_id,
            prepared_files=[prepared],
            adapter=adapter,
            gate=gate,
            artifact_store=artifact_store,
            on_page_progress=on_page_progress,
        )
    except _CancelBoundary:
        _finalize_prepared_files(config, [prepared], status=OcrRunStatus.CANCELLED)
        raise
    except ProcessDeath:
        raise
    except Exception:
        _finalize_prepared_files(config, [prepared], status=OcrRunStatus.FAILED)
        raise
    return prepared.result


def _prepare_file(
    *,
    config: EvidenceProcessingExecutorConfig,
    job_id: str,
    version: SourceDocumentVersion,
    plan: PagePlan | None,
    adapter: TextOnlyOcrAdapter,
    artifact_store: ArtifactStore,
) -> _PreparedFileProcessing:
    source_sha256 = version.source_blob_sha256
    kind = _media_kind(version.media_type, version.file_name)
    result = FileProcessingResult(
        source_document_version_id=version.source_document_version_id,
        file_name=version.file_name,
        media_kind=kind or "unsupported",
    )

    if plan is None:
        outcome = _failed_whole_file(config, version, source_sha256)
        result.outcomes = [outcome]
        result.page_total = 1
        result.page_failed = 1
        return _PreparedFileProcessing(
            version=version,
            source_sha256=source_sha256,
            result=result,
            page_items=[],
        )

    result.page_total = plan.page_total
    page_inputs = list(plan.pages)

    # ---- Pass A：渲染/解码（独立有界并发，不占共享门禁） ----
    rendered = _render_all_pages(
        config=config,
        page_inputs=page_inputs,
        version=version,
        source_sha256=source_sha256,
        artifact_store=artifact_store,
    )

    visual_pages = [
        (page_input, artifact)
        for page_input, (artifact, route, _detail) in zip(page_inputs, rendered)
        if (not page_input.expects_failure)
        and route == ExtractionRoute.VISION_OCR
        and artifact.status != PageArtifactStatus.FAILED
    ]

    ocr_run_id: str | None = None
    if visual_pages:
        ocr_run_id = _create_ocr_run(
            config=config,
            job_id=job_id,
            version=version,
            adapter=adapter,
            page_total=result.page_total,
        )
    result.ocr_run_id = ocr_run_id
    return _PreparedFileProcessing(
        version=version,
        source_sha256=source_sha256,
        result=result,
        page_items=list(zip(page_inputs, rendered)),
        ocr_run_id=ocr_run_id,
    )


def _process_prepared_page(
    *,
    config: EvidenceProcessingExecutorConfig,
    prepared: _PreparedFileProcessing,
    page_input: PageInput,
    rendered_page: tuple[Any, ExtractionRoute | None, str | None],
    adapter: TextOnlyOcrAdapter,
    gate: OmlxGateClient,
    artifact_store: ArtifactStore,
) -> PageOutcome:
    artifact, route, detail = rendered_page
    ocr_page: OCRPage | None = None
    retryable = False
    deferred = False
    if (
        not page_input.expects_failure
        and route == ExtractionRoute.VISION_OCR
        and prepared.ocr_run_id is not None
    ):
        ocr_outcome = _process_visual_page(
            config=config,
            ocr_run_id=prepared.ocr_run_id,
            page_number=artifact.page_number,
            artifact=artifact,
            source_sha256=prepared.source_sha256,
            adapter=adapter,
            gate=gate,
            artifact_store=artifact_store,
        )
        ocr_page = ocr_outcome.ocr_page
        retryable = ocr_outcome.retryable
        deferred = ocr_outcome.deferred
        detail = ocr_outcome.technical_detail or detail
    elif (
        not page_input.expects_failure
        and artifact.status != PageArtifactStatus.FAILED
        and route != ExtractionRoute.VISION_OCR
        and artifact.native_text_sha256 is not None
    ):
        ocr_page = _get_or_create_source_text_page(
            config=config,
            artifact=artifact,
            route=route,
            artifact_store=artifact_store,
        )
    return PageOutcome(
        page_number=artifact.page_number,
        original_frame=artifact.original_frame,
        artifact=artifact,
        route=route,
        ocr_page=ocr_page,
        retryable=retryable,
        deferred=deferred,
        technical_detail=detail,
    )


def _run_prepared_files(
    *,
    config: EvidenceProcessingExecutorConfig,
    job_id: str,
    prepared_files: list[_PreparedFileProcessing],
    adapter: TextOnlyOcrAdapter,
    gate: OmlxGateClient,
    artifact_store: ArtifactStore,
    on_page_progress: Callable[[FileProcessingResult], None] | None,
) -> None:
    """跨文件轮转提交页任务，且任意时刻最多只有配置数量的页在执行。"""
    pending: list[
        tuple[
            _PreparedFileProcessing,
            PageInput,
            tuple[Any, ExtractionRoute | None, str | None],
        ]
    ] = []
    max_pages = max((len(prepared.page_items) for prepared in prepared_files), default=0)
    for page_index in range(max_pages):
        for prepared in prepared_files:
            if page_index < len(prepared.page_items):
                page_input, rendered_page = prepared.page_items[page_index]
                pending.append((prepared, page_input, rendered_page))
    if not pending:
        return

    worker_count = min(max(1, config.page_processing_concurrency), len(pending))
    _maybe_cancel(config, job_id)
    next_item = 0
    active: dict[Any, tuple[_PreparedFileProcessing, int]] = {}
    completed_since_cancel_check = 0
    cancel_requested = False

    def submit_next(pool: ThreadPoolExecutor) -> None:
        nonlocal next_item
        prepared, page_input, rendered_page = pending[next_item]
        next_item += 1
        future = pool.submit(
            _process_prepared_page,
            config=config,
            prepared=prepared,
            page_input=page_input,
            rendered_page=rendered_page,
            adapter=adapter,
            gate=gate,
            artifact_store=artifact_store,
        )
        active[future] = (prepared, page_input.page_number)

    with ThreadPoolExecutor(max_workers=worker_count) as pool:
        while len(active) < worker_count and next_item < len(pending):
            submit_next(pool)

        while active:
            done, _not_done = wait(active, return_when=FIRST_COMPLETED)
            for future in sorted(done, key=lambda item: active[item][1]):
                prepared, _page_number = active.pop(future)
                outcome = future.result()
                prepared.result.outcomes.append(outcome)
                prepared.result.outcomes.sort(key=lambda item: item.page_number)
                _count_file_outcomes(prepared.result)
                if on_page_progress is not None:
                    on_page_progress(prepared.result)
                completed_since_cancel_check += 1

            if (
                not cancel_requested
                and completed_since_cancel_check >= max(1, config.cancel_check_every)
                and (worker_count > 1 or next_item < len(pending))
            ):
                try:
                    _maybe_cancel(config, job_id)
                except _CancelBoundary:
                    cancel_requested = True
                completed_since_cancel_check = 0

            while (
                not cancel_requested
                and len(active) < worker_count
                and next_item < len(pending)
            ):
                submit_next(pool)

    if cancel_requested:
        raise _CancelBoundary()

    for prepared in prepared_files:
        _count_file_outcomes(prepared.result)
    _finalize_prepared_files(config, prepared_files)


def _finalize_prepared_files(
    config: EvidenceProcessingExecutorConfig,
    prepared_files: list[_PreparedFileProcessing],
    *,
    status: OcrRunStatus | None = None,
) -> None:
    for prepared in prepared_files:
        if prepared.ocr_run_id is None:
            continue
        _finalize_ocr_run(
            config=config,
            ocr_run_id=prepared.ocr_run_id,
            page_total=prepared.result.page_total,
            page_succeeded=prepared.result.page_succeeded,
            page_failed=prepared.result.page_failed,
            retryable_failures=prepared.result.retryable_failures,
            status_override=status,
        )


def _count_file_outcomes(result: FileProcessingResult) -> None:
    """从持久页结果重新计算文件汇总，避免取消/异常路径重复累计。"""
    result.page_succeeded = 0
    result.page_failed = 0
    result.retryable_failures = 0
    for outcome in result.outcomes:
        if outcome.artifact.status == PageArtifactStatus.FAILED:
            result.page_failed += 1
        elif outcome.retryable or outcome.deferred:
            result.retryable_failures += 1
        elif outcome.ocr_page is not None and outcome.ocr_page.status in {
            OCRPageStatus.FAILED,
            OCRPageStatus.CANCELLED,
        }:
            result.page_failed += 1
        elif (
            outcome.ocr_page is None
            or outcome.ocr_page.status == OCRPageStatus.SUCCEEDED
        ):
            result.page_succeeded += 1


def _finalize_interrupted_ocr_run(
    *,
    config: EvidenceProcessingExecutorConfig,
    ocr_run_id: str | None,
    result: FileProcessingResult,
    status: OcrRunStatus,
) -> None:
    """尽力收敛取消/普通异常留下的文件级 RUNNING 运行。

    ``ProcessDeath`` 不会进入此函数；其 RUNNING 记录由启动/租约恢复收敛。
    若当前数据库短暂不可写，原始异常仍由上层按既定恢复路径处理。
    """
    if ocr_run_id is None:
        return
    try:
        _finalize_ocr_run(
            config=config,
            ocr_run_id=ocr_run_id,
            page_total=result.page_total,
            page_succeeded=result.page_succeeded,
            page_failed=result.page_failed,
            retryable_failures=result.retryable_failures,
            status_override=status,
        )
    except Exception as exc:
        logger.exception("OCR 运行 %s 的异常收敛暂未完成", ocr_run_id)
        raise StepFailure(
            retryable=True,
            error_code="OCR_RUN_FINALIZE_RETRYABLE",
            detail="页面处理状态暂未完成保存，请稍后重试。",
        ) from exc


def _failed_whole_file(
    config: EvidenceProcessingExecutorConfig,
    version: SourceDocumentVersion,
    source_sha256: str,
) -> PageOutcome:
    """整文件不可分页/不支持：单个永久失败页（无页图、无 OCR，显式失败）。"""
    reason = "文件格式不受支持，无法生成可处理页面"
    page_input = PageInput(
        page_number=1,
        media_kind="unsupported",
        original_frame=None,
        render_source=None,
        input_sha256=None,
        status=PageArtifactStatus.FAILED,
        failure_reason=reason,
    )
    artifact, _route, detail = _build_page_artifact_detailed(
        page_input=page_input,
        source_document_version_id=version.source_document_version_id,
        source_sha256=source_sha256,
        artifact_store=ArtifactStore(config.data_paths),
        transform_version=COORDINATE_TRANSFORM_VERSION,
    )
    return PageOutcome(
        page_number=1,
        original_frame=None,
        artifact=artifact,
        route=None,
        technical_detail=detail,
    )


# ---------------------------------------------------------------------------
# Pass A：渲染/解码（有界并发）
# ---------------------------------------------------------------------------


def _render_all_pages(
    *,
    config: EvidenceProcessingExecutorConfig,
    page_inputs: list[PageInput],
    version: SourceDocumentVersion,
    source_sha256: str,
    artifact_store: ArtifactStore,
) -> list[tuple[Any, ExtractionRoute | None, str | None]]:
    """有界并发渲染/解码全部页面并持久化页产物（不占门禁额度）。"""
    results: dict[int, tuple[Any, ExtractionRoute | None, str | None]] = {}

    def render_one(page_input: PageInput) -> tuple[int, Any, ExtractionRoute | None, str | None]:
        return (
            page_input.page_number,
            *_render_one_page(
                config=config,
                page_input=page_input,
                version=version,
                source_sha256=source_sha256,
                artifact_store=artifact_store,
            ),
        )

    if config.render_concurrency <= 1 or len(page_inputs) <= 1:
        for page_input in page_inputs:
            page_number, artifact, route, detail = render_one(page_input)
            results[page_number] = (artifact, route, detail)
        return [results[pi.page_number] for pi in page_inputs]

    with ThreadPoolExecutor(max_workers=config.render_concurrency) as pool:
        future_map = {
            pool.submit(render_one, page_input): page_input.page_number
            for page_input in page_inputs
        }
        for future in as_completed(future_map):
            page_number, artifact, route, detail = future.result()
            results[page_number] = (artifact, route, detail)
    return [results[pi.page_number] for pi in page_inputs]


def _render_one_page(
    *,
    config: EvidenceProcessingExecutorConfig,
    page_input: PageInput,
    version: SourceDocumentVersion,
    source_sha256: str,
    artifact_store: ArtifactStore,
) -> tuple[Any, ExtractionRoute | None, str | None]:
    probe_route, probe_detail = decide_route_detailed(page_input)
    decoder_version = DECODER_VERSION_BY_KIND.get(page_input.media_kind)
    with config.session_factory() as session, session.begin():
        repo = PageArtifactRepository(session)
        artifact, route, detail = _build_page_artifact_detailed(
            page_input=page_input,
            source_document_version_id=version.source_document_version_id,
            source_sha256=source_sha256,
            artifact_store=artifact_store,
            decoder_version=decoder_version,
            route=probe_route,
            persist=repo.get_or_create,
        )
    return artifact, route, detail or probe_detail


# ---------------------------------------------------------------------------
# OCR 运行 / 页处理
# ---------------------------------------------------------------------------


def _get_or_create_source_text_page(
    *,
    config: EvidenceProcessingExecutorConfig,
    artifact: PageArtifact,
    route: ExtractionRoute | None,
    artifact_store: ArtifactStore,
) -> OCRPage:
    """把确定性源文本投影为统一的成功 OCRPage，不建立外部 OCR 运行或尝试。"""
    if route not in {
        ExtractionRoute.SOURCE_TEXT,
        ExtractionRoute.NATIVE_PDF_TEXT,
        ExtractionRoute.RENDERED_PDF_TEXT,
    }:
        raise StepFailure(
            retryable=False,
            error_code="SOURCE_TEXT_ROUTE_INVALID",
            detail="页面文字来源与处理路线不一致，无法保存本次处理结果。",
        )
    assert route is not None
    if artifact.page_image_sha256 is None or artifact.native_text_sha256 is None:
        raise StepFailure(
            retryable=False,
            error_code="SOURCE_TEXT_ARTIFACT_INCOMPLETE",
            detail="页面缺少可核对的原文或页图，无法保存本次处理结果。",
        )

    raw_text_bytes = artifact_store.read_by_sha(
        "native_text", artifact.native_text_sha256
    )
    try:
        raw_text = raw_text_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise StepFailure(
            retryable=False,
            error_code="SOURCE_TEXT_ENCODING_INVALID",
            detail="页面原文无法按已记录的文字编码回读，无法保存本次处理结果。",
        ) from exc
    if sha256(raw_text.encode("utf-8")).hexdigest() != artifact.native_text_sha256:
        raise StepFailure(
            retryable=False,
            error_code="SOURCE_TEXT_HASH_MISMATCH",
            detail="页面原文与已记录内容不一致，无法保存本次处理结果。",
        )

    layout_parser_version = None
    if artifact.native_coordinates_sha256 is not None:
        artifact_store.read_by_sha(
            "native_coordinates", artifact.native_coordinates_sha256
        )
        layout_parser_version = NATIVE_COORDINATES_SCHEMA

    decoder_version = artifact.decoder_version or "unknown"
    profile_sha256 = build_profile_fingerprint(
        extraction_route=route.value,
        provider=_SOURCE_TEXT_PROVIDER,
        model_id=_SOURCE_TEXT_MODEL_ID,
        model_revision=decoder_version,
        prompt_sha256=None,
        parser_version=_SOURCE_TEXT_PARSER_VERSION,
        render_params_sha256=None,
        request_params_sha256=None,
        layout_parser_version=layout_parser_version,
        coordinate_transform_version=artifact.coordinate_transform_version,
    )
    created_at = _now_utc()
    profile = OCRProfile(
        ocr_profile_id=f"ocr-profile-{profile_sha256[:40]}",
        profile_sha256=profile_sha256,
        extraction_route=route,
        provider=_SOURCE_TEXT_PROVIDER,
        model_id=_SOURCE_TEXT_MODEL_ID,
        model_revision=decoder_version,
        prompt_sha256=None,
        parser_version=_SOURCE_TEXT_PARSER_VERSION,
        render_params_sha256=None,
        request_params_sha256=None,
        layout_parser_version=layout_parser_version,
        coordinate_transform_version=artifact.coordinate_transform_version,
        created_at=created_at,
    )
    cache_key = build_ocr_cache_key(
        source_sha256=artifact.source_sha256,
        page_number=artifact.page_number,
        ocr_profile_sha256=profile.profile_sha256,
        page_input_sha256=artifact.page_image_sha256,
        layout_parser_version=profile.layout_parser_version,
        coordinate_transform_version=profile.coordinate_transform_version,
    )

    with config.session_factory() as session, session.begin():
        persisted_profile = OCRProfileRepository(session).get_or_create(profile)
        page_repo = OcrPageRepository(session)
        cached = page_repo.get_successful_by_cache_key(cache_key)
        if cached is not None:
            if (
                cached.page_artifact_id != artifact.page_artifact_id
                or cached.raw_text_sha256 != artifact.native_text_sha256
                or cached.layout_sidecar_sha256 != artifact.native_coordinates_sha256
            ):
                raise StepFailure(
                    retryable=False,
                    error_code="SOURCE_TEXT_CACHE_CONFLICT",
                    detail="页面原文缓存与当前页产物不一致，无法复用。",
                )
            return cached

        page = OCRPage(
            ocr_page_id=f"ocr-page-source-{cache_key[:40]}",
            page_artifact_id=artifact.page_artifact_id,
            source_sha256=artifact.source_sha256,
            page_number=artifact.page_number,
            page_input_sha256=artifact.page_image_sha256,
            ocr_profile_sha256=persisted_profile.profile_sha256,
            cache_key=cache_key,
            layout_parser_version=persisted_profile.layout_parser_version,
            coordinate_transform_version=persisted_profile.coordinate_transform_version,
            raw_text=raw_text,
            raw_text_sha256=artifact.native_text_sha256,
            normalized_text=raw_text,
            layout_sidecar_sha256=artifact.native_coordinates_sha256,
            quality=PageQualityMetrics(
                char_count=len(raw_text),
                word_count=len(raw_text.split()),
            ),
            risk_items=[],
            status=OCRPageStatus.SUCCEEDED,
            failure_reason=None,
            started_at=created_at,
            completed_at=created_at,
        )
        return page_repo.create(page)


def _create_ocr_run(
    *,
    config: EvidenceProcessingExecutorConfig,
    job_id: str,
    version: SourceDocumentVersion,
    adapter: TextOnlyOcrAdapter,
    page_total: int,
) -> str:
    started = _now_utc()
    run_id = f"ocr-run-{job_id[:16]}-{version.source_document_version_id[:20]}-{uuid4().hex[:8]}"
    with config.session_factory() as session, session.begin():
        # JobRunner 的租约恢复与 OCRRun 是两套持久状态；进程可能在页提交后、
        # 文件汇总前退出。新一轮只接着已落盘缓存处理，并先把旧 RUNNING 运行
        # 收敛为明确失败，避免同一文件长期显示处理中。
        OcrRunRepository(session).recover_running_for_job(
            job_id,
            source_document_version_id=version.source_document_version_id,
            status=OcrRunStatus.FAILED,
            completed_at=started,
        )
        profile = OCRProfileRepository(session).get_or_create(adapter.profile(created_at=started))
        run = OCRRun(
            ocr_run_id=run_id,
            source_document_version_id=version.source_document_version_id,
            ocr_profile_id=profile.ocr_profile_id,
            ocr_profile_sha256=profile.profile_sha256,
            job_id=job_id,
            status=OcrRunStatus.RUNNING,
            page_total=page_total,
            page_succeeded=0,
            page_failed=0,
            started_at=started,
            completed_at=None,
            created_at=started,
        )
        OcrRunRepository(session).create(run)
    return run_id


class _PageLeaseHeartbeat(threading.Thread):
    """页工作租约心跳线程：整个外部调用期间续租；丢失时置位。

    页工作租约 TTL（默认 120 秒）必须覆盖真实推理时长：长请求由本线程按
    ``ttl/3`` 间隔续租，推理结束提交前停止。心跳失败（owner/代次/过期不匹配，
    即被恢复器或其他 worker 接管）置 ``lost``，调用方必须拒绝/审计本次结果，
    不得进入成功缓存。
    """

    def __init__(
        self,
        *,
        renew: Callable[[], bool],
        ttl_seconds: float,
    ) -> None:
        super().__init__(daemon=True)
        self._renew = renew
        self._ttl_seconds = ttl_seconds
        self._stop_event = threading.Event()
        self.lost = False

    def run(self) -> None:
        interval = min(30.0, max(1.0, self._ttl_seconds / 3.0))
        while not self._stop_event.wait(interval):
            if not self._renew():
                self.lost = True
                return

    def stop(self) -> None:
        self._stop_event.set()
        self.join(timeout=2.0)
        if self.is_alive():
            self.lost = True


def _renew_page_lease(
    config: EvidenceProcessingExecutorConfig,
    work_item_id: str,
    owner: str,
    generation: int,
) -> bool:
    """续租页工作租约；失败（被接管/过期）返回 False。"""
    try:
        with config.session_factory() as session, session.begin():
            PageWorkLeaseRepository(session).heartbeat(
                work_item_id, owner, generation, config.page_lease_ttl
            )
        return True
    except PageLeaseLostError:
        return False
    except Exception:  # noqa: BLE001 - 瞬时 DB 忙不立即判定丢失，下一次心跳再核对
        return True


@contextmanager
def _page_lease_heartbeat(
    config: EvidenceProcessingExecutorConfig,
    work_item_id: str,
    owner: str,
    generation: int,
) -> Iterator[_PageLeaseHeartbeat]:
    """页工作租约在整段外部调用期间的心跳上下文；退出即停止续租。"""
    heartbeat = _PageLeaseHeartbeat(
        renew=lambda: _renew_page_lease(config, work_item_id, owner, generation),
        ttl_seconds=config.page_lease_ttl.total_seconds(),
    )
    heartbeat.start()
    try:
        yield heartbeat
    finally:
        heartbeat.stop()


@dataclass
class _VisualOutcome:
    ocr_page: OCRPage | None = None
    retryable: bool = False
    deferred: bool = False
    technical_detail: str | None = None


def _run_prepared_segments(
    *,
    config: EvidenceProcessingExecutorConfig,
    gate: OmlxGateClient,
    prepared: PreparedOcrRequest,
):
    """在同一页工作租约内逐段推理；密集页任一段失败即整页失败。"""
    inference = config.inference
    if inference is None:
        raise RuntimeError("未配置文字识别服务")
    completed = []
    for segment in prepared.segments:
        try:
            result, gate_lease = gate.run_under_lease(
                inference,
                request_payload=segment.request_payload,
                image_bytes=segment.image_bytes,
            )
        except ProcessDeath:
            raise
        except Exception as exc:
            if len(prepared.segments) == 1:
                raise
            raw_response = composite_segment_failure_response(
                prepared,
                completed,
                failed_segment=segment,
                failed_raw_response=getattr(exc, "raw_response", None),
            )
            raise SegmentInferenceError(exc, raw_response) from exc
        completed.append((segment, result, gate_lease))
    return combine_segment_results(prepared, completed)


def _process_visual_page(
    *,
    config: EvidenceProcessingExecutorConfig,
    ocr_run_id: str,
    page_number: int,
    artifact,
    source_sha256: str,
    adapter: TextOnlyOcrAdapter,
    gate: OmlxGateClient,
    artifact_store: ArtifactStore,
) -> _VisualOutcome:
    page_image_sha = artifact.page_image_sha256
    if page_image_sha is None:
        return _VisualOutcome(retryable=True, technical_detail="视觉页缺少页图哈希")
    page_image_bytes = artifact_store.read_by_sha("page_image", page_image_sha)
    started_at = _now_utc()
    owner = config.worker_id

    # ---- 阶段 (a)：prepare + 原子领取页租约 + 仅胜者写 PROCESSING 页行（同一事务） ----
    # 先落不可变原始请求工件（可重放的 prepared 请求检查点）；只有页租约领取成功
    # 的 worker 才写 PROCESSING 页行并调用模型。PageLeaseBusyError 竞争者不写
    # PROCESSING 页、不调用模型；prepare 工件本身可以作为共享的不可变检查点保留。
    with config.session_factory() as session, session.begin():
        prepared = adapter.prepare(
            session=session,
            artifact_store=artifact_store,
            source_sha256=source_sha256,
            page_number=page_number,
            page_artifact_id=artifact.page_artifact_id,
            page_input_sha256=page_image_sha,
            page_image_bytes=page_image_bytes,
            started_at=started_at,
        )
        if prepared.cached_page is not None:
            # 不可变成功缓存命中：复用，不发起真实推理，不占门禁。
            return _VisualOutcome(ocr_page=prepared.cached_page)
        try:
            lease = PageWorkLeaseRepository(session).claim(
                prepared.cache_key, owner, config.page_lease_ttl
            )
        except PageLeaseBusyError:
            return _VisualOutcome(deferred=True, technical_detail="页工作项由其他执行者持有")
        OcrPageRepository(session).create(_build_running_page(adapter, prepared))

    # ---- 阶段 (b)：整段外部调用期间页租约续租 + 门禁租约下推理（事务外） ----
    release_page_lease = True
    try:
        with _page_lease_heartbeat(
            config, prepared.cache_key, owner, lease.lease_generation
        ) as page_hb:
            if config.inference is None:
                raise StepFailure(
                    retryable=True,
                    error_code="GATE_UNAVAILABLE",
                    detail="识别通道尚未配置，本次识别未开始，请稍后重试。",
                )
            try:
                result, gate_lease = _run_prepared_segments(
                    config=config,
                    gate=gate,
                    prepared=prepared,
                )
            except SegmentInferenceError as exc:
                cause = exc.cause
                if isinstance(cause, OmlxLeaseLostError):
                    _append_rejected_late(
                        config,
                        prepared,
                        ocr_run_id,
                        lease,
                        started_at,
                        adapter=adapter,
                        artifact_store=artifact_store,
                        raw_response=exc.raw_response,
                        reason=str(cause),
                    )
                    return _VisualOutcome(retryable=True, technical_detail=str(cause))
                category = (
                    OcrFailureCategory.TIMEOUT
                    if isinstance(cause, OmlxGateCapacityError)
                    else OcrFailureCategory.PROVIDER
                )
                failed_page = _commit_ocr_failure(
                    config=config,
                    adapter=adapter,
                    prepared=prepared,
                    ocr_run_id=ocr_run_id,
                    lease=lease,
                    artifact_store=artifact_store,
                    failure=OcrFailure(
                        category=category,
                        reason=INFERENCE_FAILURE_REASON,
                        technical_detail=str(cause),
                        raw_response=exc.raw_response,
                    ),
                )
                unavailable = isinstance(cause, OmlxGateUnavailableError)
                return _VisualOutcome(
                    ocr_page=failed_page,
                    retryable=(
                        config.gate_unavailable_retryable or failed_page is None
                        if unavailable
                        else True
                    ),
                    deferred=failed_page is None,
                    technical_detail=str(cause),
                )
            except OmlxGateCapacityError as exc:
                failed_page = _commit_ocr_failure(
                    config=config,
                    adapter=adapter,
                    prepared=prepared,
                    ocr_run_id=ocr_run_id,
                    lease=lease,
                    artifact_store=artifact_store,
                    failure=OcrFailure(
                        category=OcrFailureCategory.TIMEOUT,
                        reason=INFERENCE_FAILURE_REASON,
                        technical_detail=str(exc),
                        raw_response=getattr(exc, "raw_response", None),
                    ),
                )
                return _VisualOutcome(
                    ocr_page=failed_page,
                    retryable=True,
                    deferred=failed_page is None,
                    technical_detail=str(exc),
                )
            except OmlxGateUnavailableError as exc:
                failed_page = _commit_ocr_failure(
                    config=config,
                    adapter=adapter,
                    prepared=prepared,
                    ocr_run_id=ocr_run_id,
                    lease=lease,
                    artifact_store=artifact_store,
                    failure=OcrFailure(
                        category=OcrFailureCategory.PROVIDER,
                        reason=INFERENCE_FAILURE_REASON,
                        technical_detail=str(exc),
                        raw_response=getattr(exc, "raw_response", None),
                    ),
                )
                return _VisualOutcome(
                    ocr_page=failed_page,
                    retryable=config.gate_unavailable_retryable or failed_page is None,
                    deferred=failed_page is None,
                    technical_detail=str(exc),
                )
            except OmlxLeaseLostError as exc:
                # 共享门禁租约在推理期间丢失：结果不得提交，按可重试处理。
                _append_rejected_late(
                    config,
                    prepared,
                    ocr_run_id,
                    lease,
                    started_at,
                    adapter=adapter,
                    artifact_store=artifact_store,
                    reason=str(exc),
                )
                return _VisualOutcome(retryable=True, technical_detail=str(exc))
            except OmlxGateError as exc:
                failed_page = _commit_ocr_failure(
                    config=config,
                    adapter=adapter,
                    prepared=prepared,
                    ocr_run_id=ocr_run_id,
                    lease=lease,
                    artifact_store=artifact_store,
                    failure=OcrFailure(
                        category=OcrFailureCategory.PROVIDER,
                        reason=INFERENCE_FAILURE_REASON,
                        technical_detail=str(exc),
                        raw_response=getattr(exc, "raw_response", None),
                    ),
                )
                return _VisualOutcome(
                    ocr_page=failed_page,
                    retryable=True,
                    deferred=failed_page is None,
                    technical_detail=str(exc),
                )
            except Exception as exc:  # noqa: BLE001 - provider 推理异常（非 ProcessDeath）按可重试处理
                failed_page = _commit_ocr_failure(
                    config=config,
                    adapter=adapter,
                    prepared=prepared,
                    ocr_run_id=ocr_run_id,
                    lease=lease,
                    artifact_store=artifact_store,
                    failure=OcrFailure(
                        category=OcrFailureCategory.PROVIDER,
                        reason=INFERENCE_FAILURE_REASON,
                        technical_detail=f"{type(exc).__name__}: {exc}",
                        raw_response=getattr(exc, "raw_response", None),
                    ),
                )
                return _VisualOutcome(
                    ocr_page=failed_page,
                    retryable=True,
                    deferred=failed_page is None,
                    technical_detail=f"{type(exc).__name__}: {exc}",
                )
            if page_hb.lost:
                # 页租约在推理期间被接管/过期：结果晚到，拒绝并审计，绝不提交。
                _append_rejected_late(
                    config,
                    prepared,
                    ocr_run_id,
                    lease,
                    started_at,
                    adapter=adapter,
                    artifact_store=artifact_store,
                    raw_response=result.raw_response,
                    reason="页工作租约在推理期间丢失，晚到结果被拒绝",
                )
                return _VisualOutcome(deferred=True, technical_detail="page lease lost during inference")
        if page_hb.lost:
            # ``stop()`` can discover a stalled heartbeat thread while the context
            # is unwinding. Treat that last-window loss exactly like an in-flight
            # loss; the commit transaction must never start after it.
            _append_rejected_late(
                config,
                prepared,
                ocr_run_id,
                lease,
                started_at,
                adapter=adapter,
                artifact_store=artifact_store,
                raw_response=result.raw_response,
                reason="页工作租约在推理完成时丢失，晚到结果被拒绝",
            )
            return _VisualOutcome(deferred=True, technical_detail="page lease lost during heartbeat shutdown")
        # 心跳已停止；页租约在 TTL 内仍有效。
        # ---- 阶段 (c)：commit_guard + OCRPage + 终态尝试同一事务 ----
        return _commit_ocr_success(
            config=config,
            adapter=adapter,
            prepared=prepared,
            result=result,
            ocr_run_id=ocr_run_id,
            lease=lease,
            gate_lease=gate_lease,
            artifact_store=artifact_store,
            started_at=started_at,
        )
    except ProcessDeath:
        # 真实进程死亡：不执行任何清理（页租约/PROCESSING 行保持原样），
        # 由租约 TTL 过期 + 启动恢复接管；不产生可被误认成功的晚到结果。
        release_page_lease = False
        raise
    finally:
        if release_page_lease:
            _release_page_lease(config, prepared.cache_key, owner, lease.lease_generation)


def _build_running_page(adapter: TextOnlyOcrAdapter, prepared) -> OCRPage:
    """构造 PROCESSING 页行（持久“处理中”尝试标记，追加写不可变）。"""
    return OCRPage(
        ocr_page_id=f"ocr-page-{uuid4().hex}",
        page_artifact_id=prepared.page_artifact_id,
        source_sha256=prepared.source_sha256,
        page_number=prepared.page_number,
        page_input_sha256=prepared.page_input_sha256,
        ocr_profile_sha256=prepared.profile.profile_sha256,
        cache_key=prepared.cache_key,
        layout_parser_version=prepared.profile.layout_parser_version,
        coordinate_transform_version=prepared.profile.coordinate_transform_version,
        raw_text="",
        raw_text_sha256=_EMPTY_SHA256,
        normalized_text=None,
        layout_sidecar_sha256=None,
        quality=PageQualityMetrics(char_count=0, word_count=0),
        risk_items=[],
        status=OCRPageStatus.PROCESSING,
        failure_reason=None,
        started_at=prepared.started_at,
        completed_at=None,
    )


def _commit_ocr_success(
    *,
    config: EvidenceProcessingExecutorConfig,
    adapter: TextOnlyOcrAdapter,
    prepared,
    result,
    ocr_run_id: str,
    lease,
    gate_lease,
    artifact_store: ArtifactStore,
    started_at: datetime,
) -> _VisualOutcome:
    completed_at = _now_utc()
    try:
        with config.session_factory() as session, session.begin():
            PageWorkLeaseRepository(session).commit_guard(
                prepared.cache_key,
                lease.lease_owner,
                lease.lease_generation,
                source_sha256=prepared.source_sha256,
                page_number=prepared.page_number,
                ocr_profile_sha256=prepared.profile.profile_sha256,
                page_input_sha256=prepared.page_input_sha256,
                layout_parser_version=prepared.profile.layout_parser_version,
                coordinate_transform_version=prepared.profile.coordinate_transform_version,
            )
            recognition = adapter.finalize_success(
                session=session,
                artifact_store=artifact_store,
                prepared=prepared,
                result=result,
            )
            page = recognition.ocr_page
            OcrPageRepository(session).create(page)
            OcrAttemptRepository(session).append(
                OCRAttempt(
                    attempt_id=f"ocr-attempt-{uuid4().hex}",
                    ocr_run_id=ocr_run_id,
                    ocr_page_id=page.ocr_page_id,
                    cache_key=prepared.cache_key,
                    attempt_number=1,
                    status=OcrAttemptStatus.SUCCEEDED,
                    started_at=started_at,
                    completed_at=completed_at,
                    raw_request_artifact_id=prepared.request_artifact.raw_request_artifact_id,
                    raw_response_artifact_id=(
                        recognition.raw_response_artifact.raw_response_artifact_id
                        if recognition.raw_response_artifact is not None
                        else None
                    ),
                    work_lease_owner=lease.lease_owner,
                    work_lease_generation=lease.lease_generation,
                    omlx_lease_owner=gate_lease.get("lease_id"),
                    created_at=started_at,
                )
            )
        return _VisualOutcome(ocr_page=page)
    except PageLeaseLostError as exc:
        _append_rejected_late(
            config,
            prepared,
            ocr_run_id,
            lease,
            started_at,
            adapter=adapter,
            artifact_store=artifact_store,
            raw_response=result.raw_response,
            reason=str(exc),
        )
        return _VisualOutcome(deferred=True, technical_detail=str(exc))
    except Exception as exc:  # noqa: BLE001 - 成功缓存写冲突/漂移视为晚到拒绝，不污染缓存
        _append_rejected_late(
            config,
            prepared,
            ocr_run_id,
            lease,
            started_at,
            adapter=adapter,
            artifact_store=artifact_store,
            raw_response=result.raw_response,
            reason=f"{type(exc).__name__}: {exc}",
        )
        return _VisualOutcome(retryable=True, technical_detail=f"{type(exc).__name__}: {exc}")


def _commit_ocr_failure(
    *,
    config: EvidenceProcessingExecutorConfig,
    adapter: TextOnlyOcrAdapter,
    prepared,
    ocr_run_id: str,
    lease,
    artifact_store: ArtifactStore,
    failure: OcrFailure,
) -> OCRPage | None:
    """终态失败 OCRPage + FAILED 尝试（追加写审计；成功缓存不受影响）。"""
    completed_at = _now_utc()
    try:
        with config.session_factory() as session, session.begin():
            PageWorkLeaseRepository(session).commit_guard(
                prepared.cache_key,
                lease.lease_owner,
                lease.lease_generation,
                source_sha256=prepared.source_sha256,
                page_number=prepared.page_number,
                ocr_profile_sha256=prepared.profile.profile_sha256,
                page_input_sha256=prepared.page_input_sha256,
                layout_parser_version=prepared.profile.layout_parser_version,
                coordinate_transform_version=prepared.profile.coordinate_transform_version,
            )
            recognition = adapter.finalize_failure(
                session=session,
                prepared=prepared,
                failure=failure,
                artifact_store=artifact_store,
            )
            page = recognition.ocr_page
            OcrPageRepository(session).create(page)
            OcrAttemptRepository(session).append(
                OCRAttempt(
                    attempt_id=f"ocr-attempt-{uuid4().hex}",
                    ocr_run_id=ocr_run_id,
                    ocr_page_id=page.ocr_page_id,
                    cache_key=prepared.cache_key,
                    attempt_number=1,
                    status=OcrAttemptStatus.FAILED,
                    failure_category=failure.category,
                    started_at=prepared.started_at,
                    completed_at=completed_at,
                    raw_request_artifact_id=prepared.request_artifact.raw_request_artifact_id,
                    raw_response_artifact_id=(
                        recognition.raw_response_artifact.raw_response_artifact_id
                        if recognition.raw_response_artifact is not None
                        else None
                    ),
                    work_lease_owner=lease.lease_owner,
                    work_lease_generation=lease.lease_generation,
                    omlx_lease_owner=None,
                    created_at=prepared.started_at,
                )
            )
        return page
    except PageLeaseLostError as exc:
        _append_rejected_late(
            config,
            prepared,
            ocr_run_id,
            lease,
            prepared.started_at,
            adapter=adapter,
            artifact_store=artifact_store,
            raw_response=failure.raw_response,
            reason=str(exc),
        )
        return None
    except Exception as exc:
        raise StepFailure(
            retryable=True,
            error_code="OCR_FAILURE_RECORD_RETRYABLE",
            detail="识别失败结果暂未保存，请稍后重试。",
        ) from exc


def _append_rejected_late(
    config: EvidenceProcessingExecutorConfig,
    prepared,
    ocr_run_id: str,
    lease,
    started_at: datetime,
    *,
    adapter: TextOnlyOcrAdapter,
    artifact_store: ArtifactStore,
    raw_response: bytes | None = None,
    reason: str,
) -> None:
    """晚到/代次不匹配结果：独立审计事务追加 REJECTED_LATE 尝试，绝无成功缓存。"""
    try:
        with config.session_factory() as session, session.begin():
            raw_response_artifact_id = None
            if raw_response is not None:
                raw_response_artifact_id = adapter.persist_raw_response_artifact(
                    session=session,
                    artifact_store=artifact_store,
                    raw_response=raw_response,
                ).raw_response_artifact_id
            OcrAttemptRepository(session).append(
                OCRAttempt(
                    attempt_id=f"ocr-attempt-{uuid4().hex}",
                    ocr_run_id=ocr_run_id,
                    ocr_page_id=None,
                    cache_key=prepared.cache_key,
                    attempt_number=1,
                    status=OcrAttemptStatus.REJECTED_LATE,
                    rejection_reason=reason,
                    started_at=started_at,
                    completed_at=_now_utc(),
                    raw_request_artifact_id=prepared.request_artifact.raw_request_artifact_id,
                    raw_response_artifact_id=raw_response_artifact_id,
                    work_lease_owner=lease.lease_owner,
                    work_lease_generation=lease.lease_generation,
                    omlx_lease_owner=None,
                    created_at=started_at,
                )
            )
    except Exception as exc:
        raise StepFailure(
            retryable=True,
            error_code="OCR_ATTEMPT_AUDIT_RETRYABLE",
            detail="本次识别结果暂未完成审计记录，请稍后重试。",
        ) from exc


def _release_page_lease(
    config: EvidenceProcessingExecutorConfig, work_item_id: str, owner: str, generation: int
) -> None:
    try:
        with config.session_factory() as session, session.begin():
            PageWorkLeaseRepository(session).release(work_item_id, owner, generation)
    except PageLeaseLostError:
        pass  # 已被接管/过期：释放不是义务，代次核对已阻止重复提交
    except Exception:
        logger.warning("页工作租约释放暂未完成，将由过期恢复接管", exc_info=True)


def _finalize_ocr_run(
    *,
    config: EvidenceProcessingExecutorConfig,
    ocr_run_id: str,
    page_total: int,
    page_succeeded: int,
    page_failed: int,
    retryable_failures: int,
    status_override: OcrRunStatus | None = None,
) -> None:
    if status_override is not None:
        status = status_override
    elif retryable_failures:
        status = OcrRunStatus.FAILED
    elif page_failed > 0:
        status = OcrRunStatus.PARTIAL
    else:
        status = OcrRunStatus.SUCCEEDED
    with config.session_factory() as session, session.begin():
        OcrRunRepository(session).update_status(
            ocr_run_id,
            status=status,
            page_succeeded=page_succeeded,
            page_failed=page_failed,
            completed_at=_now_utc(),
        )


def recover_evidence_ocr_runs(
    session_factory: sessionmaker[Session],
    *,
    recovered_job_ids: list[str] | tuple[str, ...] = (),
    cancelled_job_ids: list[str] | tuple[str, ...] = (),
    failed_final_job_ids: list[str] | tuple[str, ...] = (),
    now: Callable[[], datetime] = utc_now,
) -> None:
    """在 JobRunner 启动/恢复后收敛遗留的 OCRRun。

    Job 租约恢复只负责任务状态；OCRRun 也必须从持久页尝试投影出明确终态。
    取消优先于普通恢复，避免用户已取消的候选被标成失败后继续显示可重试。
    新一轮执行还会在 ``_create_ocr_run`` 内再次兜底收敛，保证手动/延迟恢复
    不依赖启动钩子也不会留下永久 RUNNING。
    """
    recovered = set(recovered_job_ids)
    cancelled = set(cancelled_job_ids)
    failed_final = set(failed_final_job_ids)
    with session_factory() as session, session.begin():
        repo = OcrRunRepository(session)
        for job_id in sorted(cancelled):
            _recover_terminal_snapshot(
                session,
                job_id,
                status=SnapshotStatus.CANCELLED,
                reason="任务取消后，已在启动恢复中收敛候选快照状态。",
            )
            repo.recover_running_for_job(
                job_id,
                status=OcrRunStatus.CANCELLED,
                completed_at=now(),
            )
        for job_id in sorted(failed_final):
            _recover_terminal_snapshot(
                session,
                job_id,
                status=SnapshotStatus.TERMINAL_FAILURE,
                reason="任务重启恢复后已达到重试上限，本次候选已停止。",
            )
        for job_id in sorted(recovered - cancelled):
            repo.recover_running_for_job(
                job_id,
                status=OcrRunStatus.FAILED,
                completed_at=now(),
            )
        # 回调与 Job 事务不是同一事务：进程可能恰好死在 Job 已终态、领域投影
        # 尚未执行之间。每次启动都扫描证据任务终态，消除这个短窗口中的 PROCESSING。
        terminal_jobs = session.execute(
            select(JobRecord.job_id, JobRecord.state).where(
                JobRecord.job_type == EVIDENCE_PROCESSING_JOB_TYPE,
                JobRecord.state.in_(("cancelled", "failed_final")),
            )
        ).all()
        for job_id, state in terminal_jobs:
            if state == "cancelled":
                _recover_terminal_snapshot(
                    session,
                    job_id,
                    status=SnapshotStatus.CANCELLED,
                    reason="任务终态已持久化，启动恢复补齐候选快照取消状态。",
                )
            else:
                _recover_terminal_snapshot(
                    session,
                    job_id,
                    status=SnapshotStatus.TERMINAL_FAILURE,
                    reason="任务已达到终态，启动恢复补齐候选快照停止状态。",
                )
        repo.recover_orphaned_running(completed_at=now())


def _recover_terminal_snapshot(
    session: Session,
    job_id: str,
    *,
    status: SnapshotStatus,
    reason: str,
) -> None:
    """把 Job 终态投影到仍处于处理中/可重试的候选快照。"""
    job = session.get(JobRecord, job_id)
    if job is None or job.job_type != EVIDENCE_PROCESSING_JOB_TYPE:
        return
    payload = verify_payload_sha256(job.payload_json, job.payload_sha256)
    snapshot_id = payload.get("snapshot_id")
    if not isinstance(snapshot_id, str) or not snapshot_id:
        return
    repo = EvidenceSnapshotRepository(session)
    current = repo.current_status(snapshot_id)
    if status == SnapshotStatus.CANCELLED:
        if current == SnapshotStatus.STAGED:
            event = "cancel"
        elif current == SnapshotStatus.PROCESSING:
            event = "cancel_at_safe_boundary"
        elif current in {
            SnapshotStatus.RETRYABLE_FAILURE,
            SnapshotStatus.NEEDS_ATTENTION,
        }:
            event = "cancel"
        else:
            return
    elif status == SnapshotStatus.TERMINAL_FAILURE:
        if current == SnapshotStatus.PROCESSING:
            event = "terminal_error"
        elif current == SnapshotStatus.RETRYABLE_FAILURE:
            event = "recovery_attempts_exhausted"
        else:
            return
    else:
        return
    repo.transition_status(
        snapshot_id,
        event=event,
        new_status=status,
        actor="v2-startup-recovery",
        reason=reason,
    )


# ---------------------------------------------------------------------------
# 修订冻结 / 进度事件 / 检查点
# ---------------------------------------------------------------------------


def _freeze_revision(
    config: EvidenceProcessingExecutorConfig,
    snapshot: EvidenceSnapshot,
    file_results: list[FileProcessingResult],
) -> str:
    """按用户确认的资料顺序及各文件页码冻结不可变基础处理修订。"""
    member_order = [member.source_document_version_id for member in snapshot.members]
    results_by_version = {
        result.source_document_version_id: result for result in file_results
    }
    if len(results_by_version) != len(file_results) or set(results_by_version) != set(
        member_order
    ):
        raise ValueError("处理结果与本次确认的资料清单不一致，拒绝生成资料版本")
    raw_entries: list[tuple] = []
    for version_id in member_order:
        result = results_by_version[version_id]
        for outcome in sorted(result.outcomes, key=lambda o: o.page_number):
            artifact = outcome.artifact
            ocr_page_id = outcome.ocr_page.ocr_page_id if outcome.ocr_page is not None else None
            raw_entries.append(
                (
                    result.source_document_version_id,
                    outcome.page_number,
                    outcome.original_frame,
                    artifact.page_artifact_id,
                    ocr_page_id,
                    artifact.status.value,
                    artifact.failure_reason,
                )
            )

    manifest_sha256 = evidence_processing_manifest_hash(
        entries=[(e[0], e[1], e[2], e[3], e[4], e[5]) for e in raw_entries]
    )
    revision_id = f"epr-{snapshot.evidence_snapshot_id[:24]}-{manifest_sha256[:16]}"
    revision = EvidenceProcessingRevision(
        evidence_processing_revision_id=revision_id,
        evidence_snapshot_id=snapshot.evidence_snapshot_id,
        project_id=snapshot.project_id,
        subject_id=snapshot.subject_id,
        review_episode_id=snapshot.review_episode_id,
        manifest=[
            EvidenceProcessingRevisionPage(
                entry_id=f"eprp-{position}",
                position=position,
                source_document_version_id=e[0],
                page_number=e[1],
                original_frame=e[2],
                page_artifact_id=e[3],
                ocr_page_id=e[4],
                status=PageArtifactStatus(e[5]),
                failure_reason=e[6],
            )
            for position, e in enumerate(raw_entries, start=1)
        ],
        manifest_sha256=manifest_sha256,
        status=ProcessingRevisionStatus.READY,
        is_activatable=False,
        created_at=_now_utc(),
        created_by="evidence-processing",
    )
    with config.session_factory() as session, session.begin():
        if session.get(EvidenceProcessingRevisionRecord, revision_id) is None:
            EvidenceProcessingRevisionRepository(session).create(revision)
    return revision_id


def _emit_progress(
    config: EvidenceProcessingExecutorConfig,
    job_id: str,
    *,
    file_result: FileProcessingResult | None,
    file_results: Any,
    total_pages: int,
) -> None:
    """在每页持久结果之后追加一条可恢复的业务进度快照。"""
    results = list(file_results)
    completed_pages = sum(result.page_succeeded for result in results)
    failed_pages = sum(
        result.page_failed + result.retryable_failures for result in results
    )
    processed_pages = completed_pages + failed_pages
    current_failed = (
        file_result.page_failed + file_result.retryable_failures
        if file_result is not None
        else 0
    )

    def status_label(result: FileProcessingResult) -> str:
        processed = result.page_succeeded + result.page_failed + result.retryable_failures
        result_failed = result.page_failed + result.retryable_failures
        if result.page_total <= 0:
            return "等待处理"
        if result.page_succeeded >= result.page_total and result_failed == 0:
            return "已完成"
        if result_failed and processed >= result.page_total:
            return "需要处理"
        if processed:
            return "正在处理"
        return "等待处理"

    text = f"已处理第 {processed_pages} 页，共 {total_pages} 页"
    payload: dict[str, Any] = {"进度说明": text}
    if file_result is not None:
        payload.update(
            {
                "文件": file_result.file_name,
                "资料": {
                    "资料标识": file_result.source_document_version_id,
                    "资料名称": file_result.file_name,
                    "页面总数": file_result.page_total,
                    "已完成": file_result.page_succeeded,
                    "失败页数": current_failed,
                    "状态说明": status_label(file_result),
                },
            }
        )
    else:
        payload["资料进度"] = [
            {
                "资料标识": result.source_document_version_id,
                "资料名称": result.file_name,
                "页面总数": result.page_total,
                "已完成": result.page_succeeded,
                "失败页数": result.page_failed + result.retryable_failures,
                "状态说明": status_label(result),
            }
            for result in results
        ]
    with config.session_factory() as session, session.begin():
        store = JobStore(session, now=config.now)
        # 重试开始时沿用旧事件水位，避免 SSE/断线客户端看到总完成页回退。
        prior = [
            row.event
            for row in store.list_event_rows(job_id)
            if row.event.event_type == JobEventType.PAGE_PROGRESS
        ]
        if prior:
            completed_pages = max(completed_pages, prior[-1].progress_completed)
            text = f"已处理第 {completed_pages + failed_pages} 页，共 {total_pages} 页"
            payload["进度说明"] = text
        store.append_event(
            store.make_event(
                job_id=job_id,
                event_type=JobEventType.PAGE_PROGRESS,
                progress_completed=completed_pages,
                progress_total=total_pages,
                payload=payload,
            )
        )


def _build_checkpoint(
    snapshot: EvidenceSnapshot,
    revision_id: str,
    file_results: list[FileProcessingResult],
) -> dict[str, Any]:
    return {
        "snapshot_id": snapshot.evidence_snapshot_id,
        "revision_id": revision_id,
        "files": [
            {
                "source_document_version_id": r.source_document_version_id,
                "file_name": r.file_name,
                "page_total": r.page_total,
                "page_succeeded": r.page_succeeded,
                "page_failed": r.page_failed,
                "retryable_failures": r.retryable_failures,
            }
            for r in file_results
        ],
        "total_pages": sum(r.page_total for r in file_results),
        "total_succeeded": sum(r.page_succeeded for r in file_results),
        "total_failed": sum(r.page_failed for r in file_results),
    }
