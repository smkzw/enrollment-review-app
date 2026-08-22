"""证据处理只读进度投影。

只读读取持久化的 OCR 运行/页状态，把文件级处理进度投影为稳定中文业务状态；
不修改任何状态、不持有取消权、不读取运行日志或内部字段。主进度使用持久
``page_progress`` 事件覆盖本次全部资料页；需要图像识别的页再用 OCR 运行
补充文件级细节。原生文字 PDF/TXT 不再被误显示为“已完成 0/0”。
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.domain.contracts.enums import (
    JobEventType,
    OCRPageStatus,
    OcrRunStatus,
    PageArtifactStatus,
)
from app.domain.contracts.evidence_ingestion import EvidenceSnapshot
from app.storage.codecs import PersistedContractInvalid, verify_payload_sha256
from app.storage.evidence_repositories import (
    EvidenceSnapshotRepository,
    SourceDocumentRepository,
)
from app.storage.ocr_repositories import (
    OcrPageRepository,
    OcrRunRepository,
    PageArtifactRepository,
)
from app.storage.repositories import RepositoryError
from app.workflow.jobstore import JobStore

#: 页面状态的稳定中文业务标签（P4-R09：等待处理/正在处理/部分完成/需要处理/已完成）。
RUN_STATE_LABELS: dict[str, str] = {
    "running": "正在处理",
    "succeeded": "已完成",
    "partial": "部分完成",
    "failed": "需要处理",
    "cancelled": "已取消",
}

_PENDING = "等待处理"
_UNKNOWN = "状态待更新"


@dataclass(frozen=True)
class FileProgressView:
    """单文件处理进度（业务语义，不暴露内部列名/日志）。"""

    source_document_version_id: str
    file_name: str
    page_total: int
    page_succeeded: int
    page_failed: int
    status: str
    status_label: str


@dataclass(frozen=True)
class EvidenceProgressView:
    """一次证据处理任务的只读进度。

    ``total_pages`` / ``completed_pages`` 覆盖本次全部资料页；``files``
    只补充需要图像识别的文件细节，每个资料版本仅投影最新权威运行。
    """

    job_id: str
    job_state: str
    job_state_label: str
    total_pages: int
    completed_pages: int
    failed_pages: int
    pending_pages: int
    scope_note: str
    files: list[FileProgressView] = field(default_factory=list)


#: 只读进度投影的聚合语义（稳定中文；不暴露内部列名/运行日志）。
PROGRESS_SCOPE_NOTE = "页面进度覆盖本次全部资料；需要图像识别的页面会按文件显示细节。"
DIRECT_TEXT_SCOPE_NOTE = "本次资料页已直接读取，无需额外图像识别。"
PENDING_SCOPE_NOTE = "页面清单正在建立；需要图像识别的页面稍后会按文件显示。"


@dataclass(frozen=True)
class _EventFileProgress:
    source_document_version_id: str | None
    file_name: str
    page_total: int
    page_succeeded: int
    page_failed: int
    status: str | None


@dataclass(frozen=True)
class _PageRollup:
    succeeded: int = 0
    failed: int = 0
    processing: int = 0


def _payload_dict(event: Any) -> dict[str, Any]:
    payload = event.payload
    return payload if isinstance(payload, dict) else {}


def _event_file(payload: dict[str, Any]) -> _EventFileProgress | None:
    """读取当前事件的单文件快照，并兼容早期只有文件名的事件。"""
    value = payload.get("资料")
    if not isinstance(value, dict):
        if not isinstance(payload.get("文件"), str):
            return None
        value = {
            "资料名称": payload["文件"],
            "页面总数": payload.get("本文件页数", 0),
            "已完成": payload.get("本文件已完成", 0),
            "失败页数": payload.get("本文件失败", 0),
        }
    try:
        raw_status = value.get("状态") or value.get("状态说明")
        status = {
            "等待处理": "pending",
            "正在处理": "running",
            "部分完成": "partial",
            "需要处理": "failed",
            "已完成": "succeeded",
            "已取消": "cancelled",
        }.get(str(raw_status), str(raw_status) if raw_status else None)
        return _EventFileProgress(
            source_document_version_id=(
                str(value["资料标识"]) if value.get("资料标识") else None
            ),
            file_name=str(value.get("资料名称") or payload.get("文件") or ""),
            page_total=max(0, int(value.get("页面总数", 0))),
            page_succeeded=max(0, int(value.get("已完成", 0))),
            page_failed=max(0, int(value.get("失败页数", 0))),
            status=status,
        )
    except (TypeError, ValueError):
        return None


def _event_file_snapshots(
    events: Iterable[Any],
) -> tuple[dict[str, _EventFileProgress], dict[str, _EventFileProgress], Any | None]:
    """按事件序号保留每份资料最新快照，另保留无标识的旧事件。"""
    identified: dict[str, _EventFileProgress] = {}
    by_name: dict[str, _EventFileProgress] = {}
    latest: Any | None = None
    for event in events:
        if event.event_type != JobEventType.PAGE_PROGRESS:
            continue
        latest = event
        payload = _payload_dict(event)
        initial = payload.get("资料进度")
        if isinstance(initial, list):
            for item in initial:
                if not isinstance(item, dict):
                    continue
                parsed = _event_file({"资料": item})
                if parsed is None:
                    continue
                if parsed.source_document_version_id:
                    identified[parsed.source_document_version_id] = parsed
                elif parsed.file_name:
                    by_name[parsed.file_name] = parsed
        parsed = _event_file(payload)
        if parsed is None:
            continue
        if parsed.source_document_version_id:
            identified[parsed.source_document_version_id] = parsed
        elif parsed.file_name:
            by_name[parsed.file_name] = parsed
    return identified, by_name, latest


def _candidate_snapshot(session: Session, job_id: str) -> EvidenceSnapshot | None:
    """从持久任务载荷恢复冻结快照；旧/测试任务缺失时保持兼容。"""
    job = JobStore(session).get_job(job_id)
    try:
        payload = verify_payload_sha256(job.payload_json, job.payload_sha256)
    except (TypeError, ValueError):
        return None
    snapshot_id = payload.get("snapshot_id")
    if not isinstance(snapshot_id, str) or not snapshot_id:
        return None
    try:
        return EvidenceSnapshotRepository(session).get(snapshot_id)
    except (RepositoryError, PersistedContractInvalid):
        return None


def _effective_page_rollup(session: Session, version_id: str) -> _PageRollup:
    """按缓存键选一页的有效状态，旧失败/处理中行不与成功重试重复计数。"""
    pages = OcrPageRepository(session).list_by_source_document_version(version_id)
    by_cache_key: dict[str, list[Any]] = {}
    for page in pages:
        by_cache_key.setdefault(page.cache_key, []).append(page)

    succeeded = failed = processing = 0
    for history in by_cache_key.values():
        if any(page.status == OCRPageStatus.SUCCEEDED for page in history):
            succeeded += 1
            continue
        current = max(
            history,
            key=lambda page: (page.completed_at or page.started_at, page.ocr_page_id),
        )
        if current.status == OCRPageStatus.PROCESSING:
            processing += 1
        elif current.status in {OCRPageStatus.FAILED, OCRPageStatus.CANCELLED}:
            failed += 1

    artifacts = PageArtifactRepository(session).list_by_source_document_version(version_id)
    failed_artifacts = {
        artifact.page_artifact_id
        for artifact in artifacts
        if artifact.status == PageArtifactStatus.FAILED
    }
    page_artifact_ids = {page.page_artifact_id for page in pages}
    failed += sum(
        1 for artifact_id in failed_artifacts if artifact_id not in page_artifact_ids
    )
    return _PageRollup(succeeded=succeeded, failed=failed, processing=processing)


def _status_for_file(
    *,
    page_total: int,
    page_succeeded: int,
    page_failed: int,
    processing: bool,
    cancelled: bool,
    fallback: str | None = None,
) -> str:
    terminal = page_succeeded + page_failed
    if cancelled and terminal < page_total:
        return "cancelled"
    if page_total <= 0:
        return fallback or "pending"
    if page_succeeded >= page_total and page_failed == 0:
        return "succeeded"
    if processing and terminal < page_total:
        return "running"
    if page_failed and terminal >= page_total:
        return "failed"
    if page_succeeded or page_failed:
        return "partial"
    return fallback or "pending"


def build_progress(
    session: Session,
    job_id: str,
    *,
    job_state_labels: dict[str, str] | None = None,
) -> EvidenceProgressView:
    """按候选快照、不可变页行和持久事件投影证据处理进度。"""
    store = JobStore(session)
    status = store.job_status(job_id)
    progress_events: list[Any] = [
        row.event
        for row in store.list_event_rows(job_id)
        if row.event.event_type == JobEventType.PAGE_PROGRESS
    ]
    event_by_id, event_by_name, latest_event = _event_file_snapshots(progress_events)
    labels = job_state_labels or {}
    runs = OcrRunRepository(session).list_by_job(job_id)

    latest_run_by_doc: dict[str, Any] = {}
    for run in runs:
        key = run.source_document_version_id
        previous = latest_run_by_doc.get(key)
        if previous is None or (run.created_at, run.ocr_run_id) > (
            previous.created_at,
            previous.ocr_run_id,
        ):
            latest_run_by_doc[key] = run

    snapshot = _candidate_snapshot(session, job_id)
    # 快照成员顺序是用户确认的原始资料顺序；投影不得按 hash/逻辑标识重排。
    members = list(snapshot.members) if snapshot is not None else []
    files: list[FileProgressView] = []
    total = 0
    completed = 0
    failed = 0
    all_direct_text = True
    for member in members:
        version = SourceDocumentRepository(session).get(member.source_document_version_id)
        run = latest_run_by_doc.get(version.source_document_version_id)
        rollup = _effective_page_rollup(session, version.source_document_version_id)
        event = event_by_id.get(version.source_document_version_id)
        if event is None:
            event = event_by_name.get(version.file_name)
        artifacts = PageArtifactRepository(session).list_by_source_document_version(
            version.source_document_version_id
        )
        page_total = max(
            int(version.page_count or 0),
            len(artifacts),
            event.page_total if event is not None else 0,
            run.page_total if run is not None else 0,
            rollup.succeeded + rollup.failed + rollup.processing,
        )
        page_succeeded = rollup.succeeded
        page_failed = rollup.failed
        processing = rollup.processing > 0
        if not (page_succeeded or page_failed or processing) and event is not None:
            page_succeeded = min(page_total, event.page_succeeded)
            page_failed = min(max(0, page_total - page_succeeded), event.page_failed)
            processing = event.status == "running"
        if not (page_succeeded or page_failed or processing) and run is not None:
            page_succeeded = min(page_total, run.page_succeeded)
            page_failed = min(max(0, page_total - page_succeeded), run.page_failed)
            processing = run.status == OcrRunStatus.RUNNING
        if run is not None:
            processing = processing or run.status == OcrRunStatus.RUNNING
        page_rows = OcrPageRepository(session).list_by_source_document_version(
            version.source_document_version_id
        )
        # 只有每份候选资料都已有原生文字页且没有视觉运行，才能使用“直接读取”
        # 说明。视觉运行、尚未开始的资料或混合路线都必须保留全资料说明。
        all_direct_text = all_direct_text and bool(page_rows) and run is None
        file_status = _status_for_file(
            page_total=page_total,
            page_succeeded=page_succeeded,
            page_failed=page_failed,
            processing=processing,
            cancelled=status.state == "cancelled",
            fallback=event.status if event is not None else None,
        )
        total += page_total
        completed += page_succeeded
        failed += page_failed
        files.append(
            FileProgressView(
                source_document_version_id=version.source_document_version_id,
                file_name=version.file_name,
                page_total=page_total,
                page_succeeded=page_succeeded,
                page_failed=page_failed,
                status=file_status,
                status_label=RUN_STATE_LABELS.get(file_status, _PENDING),
            )
        )

    if latest_event is not None:
        total = max(total, int(latest_event.progress_total or 0))
        # 在第一页持久页行落库前，事件是唯一可观察的完成数来源。
        if not files or not any(file.page_succeeded or file.page_failed for file in files):
            completed = max(completed, int(latest_event.progress_completed or 0))
    if not files:
        total = max(total, status.progress_total)
        completed = max(completed, status.progress_completed)

    if files and all_direct_text and not any(file.status == "running" for file in files):
        scope_note = DIRECT_TEXT_SCOPE_NOTE
    elif files:
        scope_note = PROGRESS_SCOPE_NOTE
    elif latest_event is not None and not runs:
        scope_note = DIRECT_TEXT_SCOPE_NOTE
    else:
        scope_note = PENDING_SCOPE_NOTE

    return EvidenceProgressView(
        job_id=job_id,
        job_state=status.state,
        job_state_label=labels.get(status.state, _UNKNOWN),
        total_pages=total,
        completed_pages=completed,
        failed_pages=failed,
        pending_pages=max(0, total - completed - failed),
        scope_note=scope_note,
        files=files,
    )
