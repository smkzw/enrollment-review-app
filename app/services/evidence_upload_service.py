"""Phase 4 上传预览服务（Slice 4.2）：暂存、指纹/格式探测、差异分类、确认与取消。

设计书 §5.2 与 §6 覆盖：用户先选择补充资料/完整资料快照并生成逐文件差异预览；
取消只清理预览自有暂存并追加取消状态，不触碰共享 blob 或历史；确认在同一事务内
创建或复用候选快照、初始持久 Job、幂等记录与确认记录，不在 HTTP/服务调用内运行
OCR（初始 Job 由后台 worker 在 Slice 4.3 消费）。

本服务职责：

- ``create_preview``  暂存文件（V2 数据根内按内容 SHA-256 命名）、格式探测、
                      差异分类（新增/重复/同名异内容冲突/不支持/无法读取/
                      完整快照遗漏/预计重新识别）、确定性预览摘要与遗漏清单；
- ``get_preview``     读取预览（条目镜像三方交叉校验）；
- ``cancel``          追加取消状态并清理预览自有暂存，幂等可重复调用；
- ``confirm``         重新校验作用域/文件/摘要/基准修订号/处置后，在同一事务
                      创建或复用候选快照 + 确认记录 + 幂等记录 + 初始持久 Job；
                      重复集合确认返回既有候选/活动快照且不创建新 Job。

确定性身份：``logical_document_id`` / ``source_document_version_id`` 由作用域与
内容 SHA-256 导出，同一输入重复确认产生同一成员集合，支撑重复集合 no-op 与并发
收敛；文件名从不参与身份计算。
"""

from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session, sessionmaker

from app.domain.contracts.enums import (
    SnapshotMemberOrigin,
    SnapshotStatus,
    UploadConflictResolution,
    UploadItemStatus,
    UploadMode,
    UploadPreviewStatus,
)
from app.domain.contracts.evidence_ingestion import (
    EvidenceSnapshot,
    EvidenceSnapshotMember,
    SourceBlob,
    SourceDocumentMetadataRevision,
    SourceDocumentVersion,
)
from app.domain.contracts.evidence_upload import (
    EVIDENCE_PROCESSING_JOB_TYPE,
    PROCESSING_HINT_BY_STATUS,
    EvidenceUploadCommit,
    EvidenceUploadConfirmInput,
    EvidenceUploadConfirmResult,
    EvidenceUploadItem,
    EvidenceUploadPreview,
    ResolutionDecision,
    evidence_preview_digest,
    logical_document_id,
    source_document_version_id,
)
from app.domain.contracts.review import ReviewEpisode
from app.domain.publication import (
    canonical_hash,
    evidence_snapshot_collection_hash,
)
from app.services.evidence_activation_service import EvidenceActivationService
from app.services.evidence_app_errors import app_error_boundary
from app.services.evidence_processing_executor import EVIDENCE_PROCESSING_MAX_ATTEMPTS
from app.services.job_service import JobService, StepSpec
from app.storage.codecs import encode_contract, to_utc_naive
from app.storage.config import DataPaths
from app.storage.evidence_models import (
    SourceBlobRecord,
    SourceDocumentVersionV2Record,
)
from app.storage.evidence_repositories import (
    BlobRepository,
    EvidenceSnapshotRepository,
    SourceDocumentMetadataRevisionRepository,
    SourceDocumentRepository,
)
from app.storage.evidence_upload_repositories import (
    EvidenceUploadCommitNotFoundError,
    EvidenceUploadCommitRepository,
    EvidenceUploadPreviewRepository,
    PreviewNotFoundError,
    PreviewStatusTransitionError,
)
from app.storage.idempotency import IdempotencyRepository, request_hash
from app.storage.repositories import (
    EpisodeRepository,
    InvalidReferenceError,
    ScopeViolationError,
    _flush_guarded,
)

__all__ = [
    "COMMIT_IDEMPOTENCY_SCOPE",
    "CorruptedStagingError",
    "EmptySelectionError",
    "EmptyUploadError",
    "EvidenceUploadCommitNotFoundError",
    "EvidenceUploadService",
    "EvidenceUploadServiceError",
    "FileFormat",
    "MissingResolutionError",
    "NoEffectiveSnapshotError",
    "PreviewCleanupFailedError",
    "PreviewDigestMismatchError",
    "PreviewNotFoundError",
    "PreviewStatusTransitionError",
    "StaleBaseRevisionError",
    "UnknownResolutionError",
    "UploadedFileInput",
    "detect_file_format",
]

COMMIT_IDEMPOTENCY_SCOPE = "evidence_upload_commit/v1"

#: 参与确认成员计算的条目分类；其余（重复/不支持/无法读取/遗漏）不进入新快照。
_INCLUDABLE_STATUSES = frozenset(
    {
        UploadItemStatus.ADDED,
        UploadItemStatus.EXPECTED_REPROCESSING,
        UploadItemStatus.CONFLICT,
    }
)

_STAGED_STATUSES = frozenset(
    {
        UploadItemStatus.ADDED,
        UploadItemStatus.DUPLICATE,
        UploadItemStatus.CONFLICT,
        UploadItemStatus.UNSUPPORTED,
        UploadItemStatus.EXPECTED_REPROCESSING,
    }
)


# ---------------------------------------------------------------------------
# 领域错误
# ---------------------------------------------------------------------------


class EvidenceUploadServiceError(RuntimeError):
    """上传预览服务领域错误基类。"""


class EmptyUploadError(EvidenceUploadServiceError):
    """没有选择任何文件。"""


class NoEffectiveSnapshotError(EvidenceUploadServiceError):
    """补充资料需要唯一有效前序快照，但当前不存在。"""


class StaleBaseRevisionError(EvidenceUploadServiceError):
    """基准修订号或基准快照已变化，预览已过期，必须重新生成预览。"""


class PreviewDigestMismatchError(EvidenceUploadServiceError):
    """确认摘要与服务端重算摘要不一致，拒绝确认。"""


class MissingResolutionError(EvidenceUploadServiceError):
    """同名异内容文件缺少显式处置（新版本/并列保留）。"""


class UnknownResolutionError(EvidenceUploadServiceError):
    """处置条目引用了不存在的预览条目。"""


class CorruptedStagingError(EvidenceUploadServiceError):
    """暂存文件缺失或内容与预览指纹不一致。"""


class PreviewCleanupFailedError(EvidenceUploadServiceError):
    """取消预览后，预览自有暂存清理失败；预览保持取消待清理状态，可重试。"""


class EmptySelectionError(EvidenceUploadServiceError):
    """没有可确认进入快照的文件。"""


# ---------------------------------------------------------------------------
# 格式探测
# ---------------------------------------------------------------------------

_SUPPORTED_EXTENSIONS = frozenset(
    {
        ".pdf",
        ".docx",
        ".doc",
        ".txt",
        ".jpg",
        ".jpeg",
        ".png",
        ".bmp",
        ".tif",
        ".tiff",
        ".webp",
    }
)


@dataclass(frozen=True)
class FileFormat:
    """格式探测结果：媒体类型、是否受支持、类别与中文原因（不支持/无法读取时）。"""

    media_type: str
    supported: bool
    kind: str  # pdf | docx | doc | text | image | archive | unreadable
    reason: str | None = None


def _is_text(content: bytes) -> bool:
    if not content or b"\x00" in content:
        return False
    try:
        content.decode("utf-8")
        return True
    except UnicodeDecodeError:
        pass
    try:
        content.decode("gb18030")
        return True
    except UnicodeDecodeError:
        return False


def _sniff(content: bytes) -> tuple[str, str] | None:
    """按魔数识别内容格式，返回 (media_type, kind)；无法识别返回 None。

    内容签名优先于扩展名；DOCX 是带 OOXML 标记的 ZIP，与普通压缩包区分。
    """
    head = content[:16]
    if head.startswith(b"%PDF"):
        return "application/pdf", "pdf"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", "image"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", "image"
    if head.startswith(b"BM"):
        return "image/bmp", "image"
    if head.startswith((b"II*\x00", b"MM\x00*")):
        return "image/tiff", "image"
    if head.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "image/webp", "image"
    if head.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return "application/msword", "doc"
    if head.startswith((b"PK\x03\x04", b"PK\x05\x06")):
        # OOXML 文档包含 word/ 部件或 [Content_Types].xml 清单；普通 zip 是压缩包。
        marker_window = content[: 256 * 1024]
        if b"word/" in marker_window or b"[Content_Types].xml" in marker_window:
            return (
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "docx",
            )
        return "application/zip", "archive"
    if head.startswith(b"Rar!\x1a\x07"):
        return "application/vnd.rar", "archive"
    if head.startswith(b"7z\xbc\xaf\x27\x1c"):
        return "application/x-7z-compressed", "archive"
    if head.startswith(b"\x1f\x8b"):
        return "application/gzip", "archive"
    if content[257:262] == b"ustar":
        return "application/x-tar", "archive"
    return None


def detect_file_format(file_name: str, content: bytes) -> FileFormat:
    """探测上传文件格式；压缩包明确标记为不支持，无法识别/空文件标记为无法读取。

    内容签名优先；无签名时按扩展名兜底（仅 .txt 允许无签名文本），扩展名与内容
    冲突时以内容为准。
    """
    if not content:
        return FileFormat(
            media_type="application/octet-stream",
            supported=False,
            kind="unreadable",
            reason="文件内容为空，无法建立资料身份",
        )
    extension = Path(file_name).suffix.lower()
    signature = _sniff(content)
    if signature is not None:
        media_type, kind = signature
        if kind == "archive":
            return FileFormat(
                media_type=media_type,
                supported=False,
                kind="archive",
                reason="压缩包格式暂不支持，不静默展开",
            )
        return FileFormat(media_type=media_type, supported=True, kind=kind)
    if extension == ".txt":
        if _is_text(content):
            return FileFormat(media_type="text/plain", supported=True, kind="text")
        return FileFormat(
            media_type="application/octet-stream",
            supported=False,
            kind="unreadable",
            reason="文件无法解码为文本",
        )
    if extension in _SUPPORTED_EXTENSIONS:
        return FileFormat(
            media_type="application/octet-stream",
            supported=False,
            kind="unreadable",
            reason=f"文件内容与 {extension} 扩展名不符，无法识别文件格式",
        )
    return FileFormat(
        media_type="application/octet-stream",
        supported=False,
        kind="unreadable",
        reason="无法识别文件格式",
    )


@dataclass(frozen=True)
class UploadedFileInput:
    """上传文件输入：原始文件名 + 完整内容字节。"""

    file_name: str
    content: bytes


# ---------------------------------------------------------------------------
# 服务
# ---------------------------------------------------------------------------


class EvidenceUploadService:
    """上传预览用例编排与确认事务边界。"""

    def __init__(
        self, session_factory: sessionmaker[Session], data_paths: DataPaths
    ) -> None:
        self.session_factory = session_factory
        self.data_paths = data_paths
        self.job_service = JobService(session_factory)

    # ------------------------------------------------------------------ 路径

    def _staging_dir(self, preview_id: str) -> Path:
        return self.data_paths.boundary.require_v2_target(
            self.data_paths.root / "staging" / preview_id
        )

    # ------------------------------------------------------------------ 预览

    @app_error_boundary
    def create_preview(
        self,
        *,
        project_id: str,
        subject_id: str,
        review_episode_id: str,
        upload_mode: UploadMode,
        base_revision: int,
        files: list[UploadedFileInput],
        created_by: str,
    ) -> EvidenceUploadPreview:
        """暂存文件、指纹/格式探测、差异分类并持久化预览；不创建任何临床快照。"""
        if not files:
            raise EmptyUploadError("请至少选择一个文件")
        preview_id = uuid4().hex
        staging_dir = self._staging_dir(preview_id)
        written_paths: list[Path] = []
        try:
            with self.session_factory() as session, session.begin():
                _episode, baseline = self._read_baseline(
                    session,
                    project_id=project_id,
                    subject_id=subject_id,
                    review_episode_id=review_episode_id,
                    upload_mode=upload_mode,
                    base_revision=base_revision,
                )
                baseline_map = self._baseline_member_map(session, baseline)
                items = self._build_items(
                    preview_id=preview_id,
                    files=files,
                    upload_mode=upload_mode,
                    scope=(project_id, subject_id, review_episode_id),
                    baseline_map=baseline_map,
                    staging_dir=staging_dir,
                    written_paths=written_paths,
                )
                matching_snapshot = self._matching_snapshot_for_preview(
                    session,
                    project_id=project_id,
                    subject_id=subject_id,
                    review_episode_id=review_episode_id,
                    upload_mode=upload_mode,
                    baseline=baseline,
                    items=items,
                )
                preview = self._assemble_preview(
                    preview_id=preview_id,
                    project_id=project_id,
                    subject_id=subject_id,
                    review_episode_id=review_episode_id,
                    upload_mode=upload_mode,
                    base_revision=base_revision,
                    base_snapshot_id=baseline.evidence_snapshot_id
                    if baseline
                    else None,
                    items=items,
                    matching_snapshot=matching_snapshot,
                    created_by=created_by,
                )
                # 事务内重验作用域/修订号，防止读取基准与写入之间的漂移。
                current = EpisodeRepository(session).get(review_episode_id)
                if current.subject_id != subject_id or current.project_id != project_id:
                    raise ScopeViolationError("上传预览作用域超出审核节点/受试者")
                if current.revision != base_revision:
                    raise StaleBaseRevisionError(
                        "审核节点修订号已变化，请刷新后重新生成预览"
                    )
                EvidenceUploadPreviewRepository(session).create(preview)
            return preview
        except Exception:
            for path in written_paths:
                path.unlink(missing_ok=True)
            shutil.rmtree(staging_dir, ignore_errors=True)
            raise

    def _read_baseline(
        self,
        session: Session,
        *,
        project_id: str,
        subject_id: str,
        review_episode_id: str,
        upload_mode: UploadMode,
        base_revision: int,
    ) -> tuple[ReviewEpisode, EvidenceSnapshot | None]:
        episode = EpisodeRepository(session).get(review_episode_id)
        if episode.subject_id != subject_id or episode.project_id != project_id:
            raise ScopeViolationError("上传预览作用域超出审核节点/受试者")
        if episode.revision != base_revision:
            raise StaleBaseRevisionError("审核节点修订号与请求不一致，请刷新后重试")
        baseline = EvidenceActivationService.current_snapshot(
            session, review_episode_id
        )
        if upload_mode == UploadMode.INCREMENTAL and baseline is None:
            raise NoEffectiveSnapshotError(
                "补充资料需要上一有效资料快照作为前序；请先建立完整资料快照"
            )
        return episode, baseline

    def _baseline_member_map(
        self, session: Session, baseline: EvidenceSnapshot | None
    ) -> dict[str, dict[str, Any]]:
        """基准快照活动成员 -> {version_id, sha256, file_name, byte_size, media_type}。"""
        result: dict[str, dict[str, Any]] = {}
        if baseline is None:
            return result
        for member in baseline.members:
            record = session.get(
                SourceDocumentVersionV2Record, member.source_document_version_id
            )
            if record is None:
                raise InvalidReferenceError(
                    f"基准快照成员 {member.member_id} 引用的资料版本不存在"
                )
            version = SourceDocumentRepository._decode(record)
            blob_record = session.get(SourceBlobRecord, version.source_blob_sha256)
            if blob_record is None:
                raise InvalidReferenceError(
                    f"资料版本 {version.source_document_version_id} 引用的 SourceBlob 不存在"
                )
            blob = BlobRepository._decode(blob_record)
            result[member.logical_document_id] = {
                "version_id": member.source_document_version_id,
                "sha256": blob.sha256,
                "file_name": version.file_name,
                "byte_size": blob.byte_size,
                "media_type": version.media_type,
            }
        return result

    def _build_items(
        self,
        *,
        preview_id: str,
        files: list[UploadedFileInput],
        upload_mode: UploadMode,
        scope: tuple[str, str, str],
        baseline_map: dict[str, dict[str, Any]],
        staging_dir: Path,
        written_paths: list[Path],
    ) -> list[EvidenceUploadItem]:
        items: list[EvidenceUploadItem] = []
        for upload in files:
            file_name, content = upload.file_name, upload.content
            fmt = detect_file_format(file_name, content)
            if fmt.kind == "unreadable":
                items.append(
                    EvidenceUploadItem(
                        item_id=uuid4().hex,
                        preview_id=preview_id,
                        file_name=file_name,
                        sha256=None,
                        byte_size=len(content),
                        media_type=fmt.media_type,
                        storage_ref=None,
                        status=UploadItemStatus.UNREADABLE,
                        processing_hint="rejected",
                        error_detail=fmt.reason,
                    )
                )
                continue
            digest = hashlib.sha256(content).hexdigest()
            staged_path = staging_dir / digest
            if not staged_path.exists():
                self.data_paths.boundary.atomic_write_bytes(staged_path, content)
                written_paths.append(staged_path)
            status, logical_id, existing_version = self._classify(
                file_name=file_name,
                sha256=digest,
                upload_mode=upload_mode,
                baseline_map=baseline_map,
                supported=fmt.supported,
            )
            storage_ref = f"staging/{preview_id}/{digest}"
            items.append(
                EvidenceUploadItem(
                    item_id=uuid4().hex,
                    preview_id=preview_id,
                    file_name=file_name,
                    sha256=digest,
                    byte_size=len(content),
                    media_type=fmt.media_type,
                    storage_ref=storage_ref,
                    status=status,
                    processing_hint=PROCESSING_HINT_BY_STATUS[status],
                    logical_document_id=logical_id,
                    existing_version_id=existing_version,
                    error_detail=fmt.reason
                    if status == UploadItemStatus.UNSUPPORTED
                    else None,
                )
            )
        # 一次上传内的同内容去重：首个条目保留原分类，后续条目降为内容重复。
        by_sha: dict[str, list[int]] = {}
        for index, item in enumerate(items):
            if item.sha256 is not None:
                by_sha.setdefault(item.sha256, []).append(index)
        for digest, indexes in by_sha.items():
            if len(indexes) < 2:
                continue
            first = items[indexes[0]]
            content_logical = first.logical_document_id or logical_document_id(
                project_id=scope[0],
                subject_id=scope[1],
                review_episode_id=scope[2],
                sha256=digest,
            )
            for index in indexes[1:]:
                item = items[index]
                if item.status not in _INCLUDABLE_STATUSES:
                    continue
                items[index] = item.model_copy(
                    update={
                        "status": UploadItemStatus.DUPLICATE,
                        "processing_hint": "reuse_existing",
                        "logical_document_id": content_logical,
                        "existing_version_id": None,
                    }
                )
        # 完整资料模式：上一有效快照存在、本次未选择（内容与名称均未匹配）的遗漏。
        if upload_mode == UploadMode.FULL and baseline_map:
            selected_content = {
                item.sha256
                for item in items
                if item.sha256 is not None and item.status in _INCLUDABLE_STATUSES
            }
            selected_names = {
                item.file_name for item in items if item.status in _INCLUDABLE_STATUSES
            }
            for logical_id in sorted(baseline_map):
                entry = baseline_map[logical_id]
                if (
                    entry["sha256"] in selected_content
                    or entry["file_name"] in selected_names
                ):
                    continue
                items.append(
                    EvidenceUploadItem(
                        item_id=uuid4().hex,
                        preview_id=preview_id,
                        file_name=str(entry["file_name"]),
                        sha256=str(entry["sha256"]),
                        byte_size=int(entry["byte_size"]),
                        media_type=str(entry["media_type"]),
                        storage_ref=None,
                        status=UploadItemStatus.FULL_SNAPSHOT_OMISSION,
                        processing_hint="omitted",
                        logical_document_id=logical_id,
                        existing_version_id=str(entry["version_id"]),
                    )
                )
        return items

    @staticmethod
    def _classify(
        *,
        file_name: str,
        sha256: str,
        upload_mode: UploadMode,
        baseline_map: dict[str, dict[str, Any]],
        supported: bool,
    ) -> tuple[UploadItemStatus, str | None, str | None]:
        """差异分类：不支持 > 内容重复 > 同名异内容冲突 > 新增（补充/完整语义区分）。"""
        if not supported:
            return UploadItemStatus.UNSUPPORTED, None, None
        content_matches = [
            (logical_id, entry)
            for logical_id, entry in baseline_map.items()
            if entry["sha256"] == sha256
        ]
        if content_matches:
            content_matches.sort(key=lambda pair: pair[0])
            logical_id, entry = content_matches[0]
            if upload_mode == UploadMode.INCREMENTAL:
                return UploadItemStatus.DUPLICATE, logical_id, str(entry["version_id"])
            return (
                UploadItemStatus.EXPECTED_REPROCESSING,
                logical_id,
                str(entry["version_id"]),
            )
        name_matches = [
            (logical_id, entry)
            for logical_id, entry in baseline_map.items()
            if entry["file_name"] == file_name
        ]
        if name_matches:
            name_matches.sort(key=lambda pair: pair[0])
            logical_id, entry = name_matches[0]
            return UploadItemStatus.CONFLICT, logical_id, str(entry["version_id"])
        return UploadItemStatus.ADDED, None, None

    def _assemble_preview(
        self,
        *,
        preview_id: str,
        project_id: str,
        subject_id: str,
        review_episode_id: str,
        upload_mode: UploadMode,
        base_revision: int,
        base_snapshot_id: str | None,
        items: list[EvidenceUploadItem],
        matching_snapshot: EvidenceSnapshot | None,
        created_by: str,
    ) -> EvidenceUploadPreview:
        preview_like = EvidenceUploadPreview.model_construct(
            preview_id=preview_id,
            project_id=project_id,
            subject_id=subject_id,
            review_episode_id=review_episode_id,
            upload_mode=upload_mode,
            base_revision=base_revision,
            base_snapshot_id=base_snapshot_id,
            status=UploadPreviewStatus.STAGED,
            items=items,
            matching_snapshot_id=(
                matching_snapshot.evidence_snapshot_id
                if matching_snapshot is not None
                else None
            ),
            matching_snapshot_status=(
                matching_snapshot.status if matching_snapshot is not None else None
            ),
            preview_sha256="0" * 64,
            created_at=datetime.now(UTC),
            created_by=created_by,
        )
        digest = evidence_preview_digest(preview_like)
        return EvidenceUploadPreview.model_validate(
            {
                "preview_id": preview_id,
                "project_id": project_id,
                "subject_id": subject_id,
                "review_episode_id": review_episode_id,
                "upload_mode": upload_mode.value,
                "base_revision": base_revision,
                "base_snapshot_id": base_snapshot_id,
                "status": UploadPreviewStatus.STAGED.value,
                "items": [item.model_dump(mode="json") for item in items],
                "matching_snapshot_id": (
                    matching_snapshot.evidence_snapshot_id
                    if matching_snapshot is not None
                    else None
                ),
                "matching_snapshot_status": (
                    matching_snapshot.status.value
                    if matching_snapshot is not None
                    else None
                ),
                "preview_sha256": digest,
                "created_at": datetime.now(UTC),
                "created_by": created_by,
            }
        )

    def _matching_snapshot_for_preview(
        self,
        session: Session,
        *,
        project_id: str,
        subject_id: str,
        review_episode_id: str,
        upload_mode: UploadMode,
        baseline: EvidenceSnapshot | None,
        items: list[EvidenceUploadItem],
    ) -> EvidenceSnapshot | None:
        """在确认前识别整组资料是否已形成候选或有效版本。

        活动快照仍是差异分类和补充资料前序的唯一权威；这里仅给预览增加
        “整组内容已存在”的只读提示，避免待处理候选被逐文件误写成首次新增。
        只有同名冲突会在用户决策前改变目标集合。完整资料遗漏、不支持和
        无法读取条目均已明确不进入目标集合，不得因此漏掉既有整组版本。
        """
        if any(item.status == UploadItemStatus.CONFLICT for item in items):
            return None
        planned: dict[str, str] = {}
        if upload_mode == UploadMode.INCREMENTAL and baseline is not None:
            planned.update(
                (member.logical_document_id, member.source_document_version_id)
                for member in baseline.members
            )
        for item in items:
            if item.sha256 is None:
                continue
            if item.status == UploadItemStatus.ADDED:
                logical_id = logical_document_id(
                    project_id=project_id,
                    subject_id=subject_id,
                    review_episode_id=review_episode_id,
                    sha256=item.sha256,
                )
                planned[logical_id] = source_document_version_id(
                    logical_document_id=logical_id,
                    version_number=1,
                    sha256=item.sha256,
                )
            elif item.status == UploadItemStatus.EXPECTED_REPROCESSING:
                if item.logical_document_id is None or item.existing_version_id is None:
                    return None
                planned[item.logical_document_id] = item.existing_version_id
            elif item.status == UploadItemStatus.DUPLICATE:
                if item.logical_document_id is None:
                    return None
                if item.existing_version_id is not None:
                    planned[item.logical_document_id] = item.existing_version_id
        if not planned:
            return None
        collection_sha256 = evidence_snapshot_collection_hash(
            members=list(planned.items())
        )
        return EvidenceSnapshotRepository(session).find_by_collection(
            project_id=project_id,
            subject_id=subject_id,
            review_episode_id=review_episode_id,
            upload_mode=upload_mode,
            collection_sha256=collection_sha256,
        )

    @app_error_boundary
    def get_preview(self, preview_id: str) -> EvidenceUploadPreview:
        with self.session_factory() as session:
            return EvidenceUploadPreviewRepository(session).get(preview_id)

    @app_error_boundary
    def cancel(self, preview_id: str, *, actor: str) -> EvidenceUploadPreview:
        """取消预览：追加取消状态并核实预览自有暂存已清理；幂等，不触碰共享 blob/历史。

        取消流程分两步，保证诚实与可重试：

        1. 先在同一事务内把 staged 预览追加为 ``cancel_pending``（取消意图已持久化，
           已确认预览拒绝取消）；该状态不可被确认使用，避免残缺暂存进入确认；
        2. 随后删除并核实预览自有暂存目录；清理成功才把 ``cancel_pending`` 转终态
           ``cancelled``；清理失败保持 ``cancel_pending`` 并抛
           :class:`PreviewCleanupFailedError`，再次调用 cancel 会重试清理。

        已处于 ``cancelled`` 的预览再次取消只做清理核实（目录已不存在即视为已清理），
        不重复改状态。清理只作用于 ``staging/<preview_id>`` 目录，绝不影响共享
        ``blobs/`` 或快照/历史。
        """
        with self.session_factory() as session, session.begin():
            preview = EvidenceUploadPreviewRepository(session).get(preview_id)
            if preview.status == UploadPreviewStatus.COMMITTED:
                raise PreviewStatusTransitionError(
                    f"上传预览 {preview_id} 已确认，不能取消"
                )
            if preview.status == UploadPreviewStatus.STAGED:
                EvidenceUploadPreviewRepository(session).transition_status(
                    preview_id,
                    to_status=UploadPreviewStatus.CANCEL_PENDING,
                    actor=actor,
                    reason="用户取消预览",
                )
        cleaned = self._remove_staging_dir(preview_id)
        with self.session_factory() as session, session.begin():
            current = EvidenceUploadPreviewRepository(session).get(preview_id)
            if not cleaned:
                if current.status != UploadPreviewStatus.CANCEL_PENDING:
                    raise PreviewCleanupFailedError(
                        f"上传预览 {preview_id} 暂存清理失败且预览已处于终态 "
                        f"{current.status.value}，请人工检查 staging/{preview_id} 残留"
                    )
                raise PreviewCleanupFailedError(
                    f"上传预览 {preview_id} 已记录取消，但暂存清理失败；"
                    "请重试取消以完成清理"
                )
            if current.status == UploadPreviewStatus.CANCEL_PENDING:
                current = EvidenceUploadPreviewRepository(session).transition_status(
                    preview_id,
                    to_status=UploadPreviewStatus.CANCELLED,
                    actor=actor,
                    reason="取消暂存清理完成",
                )
            return current

    def _remove_staging_dir(self, preview_id: str) -> bool:
        """删除并核实预览自有暂存目录；失败返回 False，不抛出（由调用方诚实上报）。"""
        try:
            staging_dir = self._staging_dir(preview_id)
            if not staging_dir.exists():
                return True
            shutil.rmtree(staging_dir)
        except OSError:
            return False
        return not staging_dir.exists()

    # ------------------------------------------------------------------ 确认

    @app_error_boundary
    def confirm(
        self,
        command: EvidenceUploadConfirmInput,
        *,
        created_by: str,
    ) -> EvidenceUploadConfirmResult:
        """确认预览：同一事务创建或复用候选快照/确认记录/幂等记录/初始持久 Job。

        不在本调用内运行 OCR；重复集合确认是 no-op（返回既有候选/活动快照且不
        创建新 Job）。任何校验失败都会回滚整个事务，不留下孤立候选或任务。
        """
        with self.session_factory() as session, session.begin():
            return self._confirm_in_session(session, command, created_by)

    def _confirm_in_session(
        self,
        session: Session,
        command: EvidenceUploadConfirmInput,
        created_by: str,
    ) -> EvidenceUploadConfirmResult:
        preview_repo = EvidenceUploadPreviewRepository(session)
        commit_repo = EvidenceUploadCommitRepository(session)
        idempotency = IdempotencyRepository(session)
        snapshot_repo = EvidenceSnapshotRepository(session)

        submitted_hash = request_hash(
            {
                "preview_id": command.preview_id,
                "preview_sha256": command.preview_sha256,
                "base_revision": command.base_revision,
                "upload_mode": command.upload_mode.value,
                "scope": {
                    "project_id": command.project_id,
                    "subject_id": command.subject_id,
                    "review_episode_id": command.review_episode_id,
                },
                "resolutions": sorted(
                    (key, value.value) for key, value in command.resolutions.items()
                ),
            }
        )
        commit_id = uuid4().hex
        record, created = idempotency.resolve(
            scope=COMMIT_IDEMPOTENCY_SCOPE,
            idempotency_key=command.idempotency_key,
            submitted_hash=submitted_hash,
            result_type="evidence_upload_commit",
            result_id=commit_id,
        )
        if not created:
            existing_commit = commit_repo.get(record.result_id)
            snapshot = snapshot_repo.get(existing_commit.evidence_snapshot_id)
            return EvidenceUploadConfirmResult(
                commit_id=existing_commit.commit_id,
                evidence_snapshot_id=existing_commit.evidence_snapshot_id,
                snapshot=snapshot,
                job_id=existing_commit.job_id,
                created=False,
                replayed=True,
                duplicate=existing_commit.duplicate,
            )

        preview = preview_repo.get(command.preview_id)
        self._validate_confirm_preamble(session, command, preview)
        contents = self._verify_staged_files(preview)
        resolutions = self._validate_resolutions(preview, command.resolutions)

        # 任何新的确认请求（非同一幂等键回放）都必须先重验审核节点修订号与活动
        # 基准快照，再进入所有 no-op/并发收敛分支。这样预览生成后节点修订或活动
        # 基准已经变化的旧预览不能以重复集合 no-op 形式被确认。
        self._validate_stale_base(session, preview)

        planned, version_specs, resolution_decisions = self._plan_members(
            session,
            preview=preview,
            resolutions=resolutions,
            scope=(command.project_id, command.subject_id, command.review_episode_id),
        )
        if not planned:
            raise EmptySelectionError("没有可确认进入快照的文件")

        snapshot_id = uuid4().hex
        members = [
            EvidenceSnapshotMember(
                member_id=canonical_hash(
                    {
                        "member": "evidence_snapshot_member/v1",
                        "snapshot": snapshot_id,
                        "logical_document_id": logical_id,
                        "source_document_version_id": version_id,
                    }
                ),
                snapshot_id=snapshot_id,
                logical_document_id=logical_id,
                source_document_version_id=version_id,
                origin=origin,
            )
            for logical_id, (version_id, origin) in planned.items()
        ]
        collection_sha256 = evidence_snapshot_collection_hash(
            members=[
                (member.logical_document_id, member.source_document_version_id)
                for member in members
            ]
        )
        snapshot = EvidenceSnapshot(
            evidence_snapshot_id=snapshot_id,
            project_id=command.project_id,
            subject_id=command.subject_id,
            review_episode_id=command.review_episode_id,
            upload_mode=command.upload_mode,
            prior_snapshot_id=(
                preview.base_snapshot_id
                if command.upload_mode == UploadMode.INCREMENTAL
                else None
            ),
            comparison_snapshot_id=preview.base_snapshot_id,
            members=members,
            collection_sha256=collection_sha256,
            status=SnapshotStatus.STAGED,
            created_at=datetime.now(UTC),
            created_by=created_by,
        )

        existing = snapshot_repo.find_by_collection(
            project_id=command.project_id,
            subject_id=command.subject_id,
            review_episode_id=command.review_episode_id,
            upload_mode=command.upload_mode,
            collection_sha256=collection_sha256,
        )
        if existing is not None:
            commit = self._build_commit(
                preview=preview,
                command=command,
                snapshot_id=existing.evidence_snapshot_id,
                commit_id=commit_id,
                duplicate=True,
                job_id=None,
                resolutions=resolution_decisions,
                created_by=created_by,
            )
            commit_repo.create(commit)
            preview_repo.transition_status(
                preview.preview_id,
                to_status=UploadPreviewStatus.COMMITTED,
                actor=created_by,
                reason="确认命中重复集合 no-op",
            )
            return EvidenceUploadConfirmResult(
                commit_id=commit.commit_id,
                evidence_snapshot_id=existing.evidence_snapshot_id,
                snapshot=existing,
                job_id=None,
                created=False,
                duplicate=True,
            )

        # 新建候选：先落 blob，再落资料版本，最后落快照（成员外键依赖版本）。
        # 基准修订号/基准快照已在上方（所有 no-op 分支之前）统一重验。
        for spec in version_specs:
            blob = self._promote_blob(session, item=spec.item, contents=contents)
            version = self._resolve_version(
                session,
                version=SourceDocumentVersion(
                    source_document_version_id=spec.version_id,
                    logical_document_id=spec.logical_document_id,
                    source_blob_sha256=blob.sha256,
                    file_name=spec.item.file_name,
                    media_type=spec.item.media_type,
                    page_count=None,
                    project_id=command.project_id,
                    subject_id=command.subject_id,
                    review_episode_id=command.review_episode_id,
                    version_number=spec.version_number,
                    supersedes_version_id=spec.supersedes_version_id,
                    created_at=datetime.now(UTC),
                    created_by=created_by,
                ),
            )
            self._ensure_initial_metadata(
                session,
                version=version,
                created_by=created_by,
            )

        if command.upload_mode == UploadMode.INCREMENTAL:
            created_snapshot = snapshot_repo.create_incremental(snapshot)
        else:
            created_snapshot = snapshot_repo.create_full(snapshot)

        if created_snapshot.evidence_snapshot_id != snapshot.evidence_snapshot_id:
            # 并发竞争：另一事务已创建同集合快照，转入重复 no-op（不创建新 Job）。
            commit = self._build_commit(
                preview=preview,
                command=command,
                snapshot_id=created_snapshot.evidence_snapshot_id,
                commit_id=commit_id,
                duplicate=True,
                job_id=None,
                resolutions=resolution_decisions,
                created_by=created_by,
            )
            commit_repo.create(commit)
            preview_repo.transition_status(
                preview.preview_id,
                to_status=UploadPreviewStatus.COMMITTED,
                actor=created_by,
                reason="确认命中并发重复集合",
            )
            return EvidenceUploadConfirmResult(
                commit_id=commit.commit_id,
                evidence_snapshot_id=created_snapshot.evidence_snapshot_id,
                snapshot=created_snapshot,
                job_id=None,
                created=False,
                duplicate=True,
            )

        job_result = self.job_service.create_job_in_session(
            session,
            idempotency_key=f"evidence-upload:{commit_id}",
            job_type=EVIDENCE_PROCESSING_JOB_TYPE,
            payload={
                "preview_id": preview.preview_id,
                "commit_id": commit_id,
                "snapshot_id": snapshot_id,
                "project_id": command.project_id,
                "subject_id": command.subject_id,
                "review_episode_id": command.review_episode_id,
                "upload_mode": command.upload_mode.value,
            },
            steps=[
                StepSpec(
                    step_id="evidence_processing",
                    name="evidence_processing",
                    max_attempts=EVIDENCE_PROCESSING_MAX_ATTEMPTS,
                    retryable=True,
                )
            ],
        )
        commit = self._build_commit(
            preview=preview,
            command=command,
            snapshot_id=snapshot_id,
            commit_id=commit_id,
            duplicate=False,
            job_id=job_result.job_id,
            resolutions=resolution_decisions,
            created_by=created_by,
        )
        commit_repo.create(commit)
        preview_repo.transition_status(
            preview.preview_id,
            to_status=UploadPreviewStatus.COMMITTED,
            actor=created_by,
            reason="用户确认上传",
        )
        return EvidenceUploadConfirmResult(
            commit_id=commit.commit_id,
            evidence_snapshot_id=snapshot_id,
            snapshot=created_snapshot,
            job_id=job_result.job_id,
            created=True,
            duplicate=False,
        )

    def _validate_confirm_preamble(
        self,
        session: Session,
        command: EvidenceUploadConfirmInput,
        preview: EvidenceUploadPreview,
    ) -> None:
        """确认前的基础校验：作用域、上传方式、预览状态与摘要一致（不涉基准过期）。"""
        if (
            command.project_id != preview.project_id
            or command.subject_id != preview.subject_id
            or command.review_episode_id != preview.review_episode_id
        ):
            raise ScopeViolationError("确认请求作用域与预览不一致，拒绝跨对象确认")
        if command.upload_mode != preview.upload_mode:
            raise ScopeViolationError(
                f"确认请求上传方式与预览不一致：{preview.upload_mode.value}"
            )
        if preview.status != UploadPreviewStatus.STAGED:
            raise PreviewStatusTransitionError(
                f"上传预览 {preview.preview_id} 处于 {preview.status.value}，不可确认"
            )
        if command.preview_sha256 != preview.preview_sha256:
            raise PreviewDigestMismatchError("确认摘要与预览摘要不一致")
        recomputed = evidence_preview_digest(preview)
        if recomputed != preview.preview_sha256:
            raise PreviewDigestMismatchError(
                "预览摘要与存储的逐文件内容不一致，拒绝确认"
            )

    def _validate_stale_base(
        self,
        session: Session,
        preview: EvidenceUploadPreview,
    ) -> None:
        """任何新确认请求（非同一幂等键回放）在进入 no-op/并发收敛分支前重验基准。

        校验审核节点修订号未变化，且当前活动基准快照仍是预览创建时的基准。
        预览生成后节点修订推进或活动快照变化都会让旧预览过期，必须拒绝而不是
        以重复集合 no-op 或并发收敛形式确认。
        """
        episode = EpisodeRepository(session).get(preview.review_episode_id)
        if episode.revision != preview.base_revision:
            raise StaleBaseRevisionError(
                "审核节点修订号已变化，预览已过期，请重新生成预览"
            )
        current_base = EvidenceActivationService.current_snapshot_id(
            session, preview.review_episode_id
        )
        if current_base != preview.base_snapshot_id:
            raise StaleBaseRevisionError("基准快照已变化，预览已过期，请重新生成预览")

    def _verify_staged_files(self, preview: EvidenceUploadPreview) -> dict[str, bytes]:
        """确认前重读暂存文件并核对 SHA-256；缺失/漂移一律拒绝并回滚事务。"""
        contents: dict[str, bytes] = {}
        for item in preview.items:
            if item.storage_ref is None:
                continue
            path = self.data_paths.boundary.require_v2_target(
                self.data_paths.root / item.storage_ref
            )
            if not path.is_file():
                raise CorruptedStagingError(
                    f"暂存文件缺失：{item.file_name}（{item.storage_ref}）"
                )
            try:
                content = path.read_bytes()
            except OSError as exc:
                raise CorruptedStagingError(
                    f"暂存文件读取失败：{item.file_name}（{exc}）"
                ) from exc
            digest = hashlib.sha256(content).hexdigest()
            if digest != item.sha256:
                raise CorruptedStagingError(
                    f"暂存文件内容与预览指纹不一致：{item.file_name}"
                )
            contents[item.item_id] = content
        return contents

    def _validate_resolutions(
        self,
        preview: EvidenceUploadPreview,
        resolutions: dict[str, UploadConflictResolution],
    ) -> dict[str, UploadConflictResolution]:
        conflict_items = {
            item.item_id
            for item in preview.items
            if item.status == UploadItemStatus.CONFLICT
        }
        for item_id in sorted(conflict_items):
            if item_id not in resolutions:
                raise MissingResolutionError(
                    f"同名异内容文件必须显式选择“作为新版本”或“并列保留”：{item_id}"
                )
        unknown = set(resolutions) - {item.item_id for item in preview.items}
        if unknown:
            raise UnknownResolutionError(
                "处置条目引用了不存在的预览条目：" + ", ".join(sorted(unknown))
            )
        return dict(resolutions)

    def _plan_members(
        self,
        session: Session,
        *,
        preview: EvidenceUploadPreview,
        resolutions: dict[str, UploadConflictResolution],
        scope: tuple[str, str, str],
    ) -> tuple[
        dict[str, tuple[str, SnapshotMemberOrigin]],
        list[_VersionSpec],
        list[ResolutionDecision],
    ]:
        """纯规划：确定目标成员集合（逻辑资料 -> 版本/来源）与需要新建的版本清单。

        不产生任何写入；同一输入产生确定性结果，重复确认收敛到同一成员集合。
        """
        incremental = preview.upload_mode == UploadMode.INCREMENTAL
        planned: dict[str, tuple[str, SnapshotMemberOrigin]] = {}
        version_specs: list[_VersionSpec] = []
        resolution_decisions: list[ResolutionDecision] = []
        if incremental:
            if preview.base_snapshot_id is None:
                raise EvidenceUploadServiceError(
                    "补充资料预览缺少前序快照引用，拒绝确认"
                )
            base = EvidenceSnapshotRepository(session).get(preview.base_snapshot_id)
            for member in base.members:
                planned[member.logical_document_id] = (
                    member.source_document_version_id,
                    SnapshotMemberOrigin.INHERITED,
                )
        for item in preview.items:
            item_sha = item.sha256
            item_logical = item.logical_document_id
            item_existing = item.existing_version_id
            if item.status in (
                UploadItemStatus.CONFLICT,
                UploadItemStatus.EXPECTED_REPROCESSING,
            ) and (item_logical is None or item_existing is None):
                raise EvidenceUploadServiceError(
                    f"预览条目 {item.item_id} 缺少基准资料身份，拒绝确认"
                )
            if item_sha is None:
                if item.status in (UploadItemStatus.ADDED, UploadItemStatus.CONFLICT):
                    raise EvidenceUploadServiceError(
                        f"预览条目 {item.item_id} 缺少内容指纹，拒绝确认"
                    )
                continue
            if item.status == UploadItemStatus.ADDED:
                logical_id = logical_document_id(
                    project_id=scope[0],
                    subject_id=scope[1],
                    review_episode_id=scope[2],
                    sha256=item_sha,
                )
                version_id = source_document_version_id(
                    logical_document_id=logical_id,
                    version_number=1,
                    sha256=item_sha,
                )
                planned[logical_id] = (version_id, SnapshotMemberOrigin.ADDED)
                version_specs.append(
                    _VersionSpec(
                        item=item,
                        logical_document_id=logical_id,
                        version_number=1,
                        version_id=version_id,
                        supersedes_version_id=None,
                    )
                )
            elif item.status == UploadItemStatus.EXPECTED_REPROCESSING:
                if item_logical is None or item_existing is None:
                    raise EvidenceUploadServiceError(
                        f"预览条目 {item.item_id} 缺少基准资料身份，拒绝确认"
                    )
                planned[item_logical] = (item_existing, SnapshotMemberOrigin.ADDED)
            elif item.status == UploadItemStatus.CONFLICT:
                if item_logical is None or item_existing is None:
                    raise EvidenceUploadServiceError(
                        f"预览条目 {item.item_id} 缺少基准资料身份，拒绝确认"
                    )
                resolution = resolutions[item.item_id]
                if resolution == UploadConflictResolution.NEW_VERSION:
                    head = self._latest_version(
                        session, preview.review_episode_id, item_logical
                    )
                    if head is None or head.source_document_version_id != item_existing:
                        raise StaleBaseRevisionError(
                            "同名资料版本链已变化，预览已过期，请重新生成预览"
                        )
                    version_number = head.version_number + 1
                    version_id = source_document_version_id(
                        logical_document_id=item_logical,
                        version_number=version_number,
                        sha256=item_sha,
                    )
                    origin = (
                        SnapshotMemberOrigin.REPLACED
                        if incremental
                        else SnapshotMemberOrigin.ADDED
                    )
                    planned[item_logical] = (version_id, origin)
                    version_specs.append(
                        _VersionSpec(
                            item=item,
                            logical_document_id=item_logical,
                            version_number=version_number,
                            version_id=version_id,
                            supersedes_version_id=item_existing,
                        )
                    )
                    resolution_decisions.append(
                        ResolutionDecision(
                            item_id=item.item_id,
                            logical_document_id=item_logical,
                            resolution=UploadConflictResolution.NEW_VERSION,
                            source_document_version_id=version_id,
                            supersedes_version_id=item_existing,
                        )
                    )
                else:  # KEEP_PARALLEL
                    logical_id = logical_document_id(
                        project_id=scope[0],
                        subject_id=scope[1],
                        review_episode_id=scope[2],
                        sha256=item_sha,
                    )
                    version_id = source_document_version_id(
                        logical_document_id=logical_id,
                        version_number=1,
                        sha256=item_sha,
                    )
                    planned[logical_id] = (version_id, SnapshotMemberOrigin.ADDED)
                    version_specs.append(
                        _VersionSpec(
                            item=item,
                            logical_document_id=logical_id,
                            version_number=1,
                            version_id=version_id,
                            supersedes_version_id=None,
                        )
                    )
                    resolution_decisions.append(
                        ResolutionDecision(
                            item_id=item.item_id,
                            logical_document_id=logical_id,
                            resolution=UploadConflictResolution.KEEP_PARALLEL,
                            source_document_version_id=version_id,
                            supersedes_version_id=None,
                        )
                    )
        return planned, version_specs, resolution_decisions

    @staticmethod
    def _latest_version(
        session: Session, review_episode_id: str, logical_document_id: str
    ) -> SourceDocumentVersion | None:
        return SourceDocumentRepository(session)._latest_version(
            review_episode_id=review_episode_id,
            logical_document_id=logical_document_id,
        )

    def _promote_blob(
        self,
        session: Session,
        *,
        item: EvidenceUploadItem,
        contents: dict[str, bytes],
    ) -> SourceBlob:
        """暂存文件提升为共享内容寻址 blob；同内容并发写入幂等收敛。"""
        if item.sha256 is None:
            raise EvidenceUploadServiceError(
                f"预览条目 {item.item_id} 缺少内容指纹，拒绝提升 blob"
            )
        content = contents[item.item_id]
        blob_path = self.data_paths.blobs_dir / item.sha256
        if not blob_path.exists():
            self.data_paths.boundary.atomic_write_bytes(blob_path, content)
        blob = SourceBlob(
            source_blob_id=item.sha256,
            sha256=item.sha256,
            byte_size=item.byte_size,
            media_type=item.media_type,
            storage_ref=f"blobs/{item.sha256}",
            created_at=datetime.now(UTC),
        )
        return BlobRepository(session).get_or_create_by_sha256(blob)

    def _resolve_version(
        self,
        session: Session,
        *,
        version: SourceDocumentVersion,
    ) -> SourceDocumentVersion:
        """按确定性版本身份 get-or-create；并发同内容提交复用赢家，不重复创建。"""
        existing = session.get(
            SourceDocumentVersionV2Record, version.source_document_version_id
        )
        if existing is not None:
            return self._verify_version_identity(existing, version)
        payload_json, payload_sha256 = encode_contract(version)
        session.execute(
            sqlite_insert(SourceDocumentVersionV2Record)
            .values(
                source_document_version_id=version.source_document_version_id,
                logical_document_id=version.logical_document_id,
                source_blob_sha256=version.source_blob_sha256,
                file_name=version.file_name,
                media_type=version.media_type,
                page_count=version.page_count,
                project_id=version.project_id,
                subject_id=version.subject_id,
                review_episode_id=version.review_episode_id,
                version_number=version.version_number,
                supersedes_version_id=version.supersedes_version_id,
                created_by=version.created_by,
                created_at=to_utc_naive(version.created_at),
                payload_json=payload_json,
                payload_sha256=payload_sha256,
            )
            .on_conflict_do_nothing()
        )
        _flush_guarded(session)
        winner = session.get(
            SourceDocumentVersionV2Record, version.source_document_version_id
        )
        if winner is None:
            raise EvidenceUploadServiceError(
                f"资料版本 {version.source_document_version_id} 写入后无法读取，拒绝返回不完整结果"
            )
        return self._verify_version_identity(winner, version)

    @staticmethod
    def _suggest_initial_metadata(file_name: str) -> tuple[str, str]:
        """根据文件名给出可修改的初始资料分类建议。

        这只是上传后的产品初始态，不是临床事实或最终分类；持久化时明确
        标记为自动建议，后续人工修改必须追加新修订。
        """
        normalized = file_name.casefold()
        categories = (
            (("知情", "icf", "consent"), "知情同意资料"),
            (("病历", "病案", "medical record", "record"), "病历资料"),
            (("用药", "处方", "治疗", "medication", "therapy"), "用药与治疗记录"),
            (("检验", "化验", "血常规", "尿常规", "lab"), "实验室检验结果"),
            (("检查", "心电", "影像", "超声", "ct", "mri", "ecg"), "检查报告"),
            (("评分", "量表", "scale", "score"), "评分与量表"),
        )
        for needles, label in categories:
            if any(needle in normalized for needle in needles):
                return label, "研究中心（待确认）"
        return "其他资料（待确认）", "研究中心（待确认）"

    def _ensure_initial_metadata(
        self,
        session: Session,
        *,
        version: SourceDocumentVersion,
        created_by: str,
    ) -> SourceDocumentMetadataRevision:
        """为新资料版本建立必需的初始分类修订，并发重放时幂等。"""
        repo = SourceDocumentMetadataRevisionRepository(session)
        current = repo.head(version.source_document_version_id)
        if current is not None:
            return current
        document_type, source_party = self._suggest_initial_metadata(version.file_name)
        revision = SourceDocumentMetadataRevision(
            metadata_revision_id=canonical_hash(
                {
                    "kind": "source_document_metadata_revision/v1",
                    "source_document_version_id": version.source_document_version_id,
                    "revision": 1,
                }
            ),
            source_document_version_id=version.source_document_version_id,
            revision=1,
            document_type=document_type,
            source_party=source_party,
            reason="上传后根据文件名生成的初始建议，待用户核对",
            is_auto_suggestion=True,
            supersedes_metadata_revision_id=None,
            created_at=datetime.now(UTC),
            created_by=created_by,
        )
        return repo.append(revision)

    @staticmethod
    def _verify_version_identity(
        record: SourceDocumentVersionV2Record, planned: SourceDocumentVersion
    ) -> SourceDocumentVersion:
        existing = SourceDocumentRepository._decode(record)
        if (
            existing.logical_document_id != planned.logical_document_id
            or existing.version_number != planned.version_number
            or existing.source_blob_sha256 != planned.source_blob_sha256
        ):
            raise EvidenceUploadServiceError(
                f"资料版本 {planned.source_document_version_id} 身份冲突，拒绝复用"
            )
        return existing

    @staticmethod
    def _build_commit(
        *,
        preview: EvidenceUploadPreview,
        command: EvidenceUploadConfirmInput,
        snapshot_id: str,
        commit_id: str,
        duplicate: bool,
        job_id: str | None,
        resolutions: list[ResolutionDecision],
        created_by: str,
    ) -> EvidenceUploadCommit:
        return EvidenceUploadCommit(
            commit_id=commit_id,
            preview_id=preview.preview_id,
            evidence_snapshot_id=snapshot_id,
            project_id=preview.project_id,
            subject_id=preview.subject_id,
            review_episode_id=preview.review_episode_id,
            upload_mode=preview.upload_mode,
            preview_sha256=preview.preview_sha256,
            idempotency_key=command.idempotency_key,
            job_id=job_id,
            duplicate=duplicate,
            resolutions=resolutions,
            created_at=datetime.now(UTC),
            created_by=created_by,
        )


@dataclass(frozen=True)
class _VersionSpec:
    """规划出的新资料版本：确定性身份 + 替代前序 + 来源条目。"""

    item: EvidenceUploadItem
    logical_document_id: str
    version_number: int
    version_id: str
    supersedes_version_id: str | None
