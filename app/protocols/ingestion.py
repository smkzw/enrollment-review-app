"""原始方案文件登记：SHA-256、MIME/格式检测与 :class:`ProtocolSourceArtifact`。

只读原始文件，计算哈希与元信息，并把字节复制到 V2 数据根的内容寻址路径；
不修改源文件，后续派生流程不依赖用户原始路径持续存在。
"""
from __future__ import annotations

import hashlib
import os
import shutil
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from app.domain.contracts.protocol_ingestion import ProtocolSourceArtifact

_CHUNK = 1024 * 1024
_SOURCE_STORAGE_PREFIX = "blobs/protocol_sources"

# 常见文档魔数
_ZIP_MAGIC = b"PK\x03\x04"
_ZIP_EMPTY_MAGIC = b"PK\x05\x06"
_OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_PDF_MAGIC = b"%PDF"

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
DOC_MIME = "application/msword"
PDF_MIME = "application/pdf"
TXT_MIME = "text/plain"
UNKNOWN_MIME = "application/octet-stream"


class ProtocolFileKind(str, Enum):
    DOCX = "docx"
    DOC = "doc"
    PDF = "pdf"
    TXT = "txt"
    UNKNOWN = "unknown"


class SourceIngestionError(RuntimeError):
    """原始方案登记失败：文件缺失、不可读或格式无法判定。"""


def utc_now() -> datetime:
    """当前 UTC 时间（带时区）。

    协议层产出的领域时间戳必须是 timezone-aware UTC；只有存储适配层
    （``app.storage.codecs.to_utc_naive``）才允许将其归一化为 SQLite 的
    UTC naive 物理列形态。
    """
    return datetime.now(timezone.utc)


def compute_sha256(path: str | Path) -> str:
    """分块计算文件 SHA-256；文件缺失或不可读抛 :class:`SourceIngestionError`。"""
    file_path = Path(path)
    if not file_path.is_file():
        raise SourceIngestionError(f"原始方案文件不存在或不可读：{file_path}")
    digest = hashlib.sha256()
    try:
        with file_path.open("rb") as handle:
            while chunk := handle.read(_CHUNK):
                digest.update(chunk)
    except OSError as exc:
        raise SourceIngestionError(f"读取原始方案失败：{file_path}（{exc}）") from exc
    return digest.hexdigest()


def _is_docx_zip(file_path: Path) -> bool:
    """ZIP 魔数之外，还需包含 Word 文档部件才能判定为 DOCX。"""
    try:
        with ZipFile(file_path) as archive:
            names = set(archive.namelist())
    except (BadZipFile, OSError):
        return False
    return "word/document.xml" in names


def detect_format(path: str | Path) -> tuple[str, ProtocolFileKind]:
    """按魔数判定 MIME 与文件类别；未知格式返回 ``application/octet-stream``。"""
    file_path = Path(path)
    if not file_path.is_file():
        raise SourceIngestionError(f"原始方案文件不存在或不可读：{file_path}")
    with file_path.open("rb") as handle:
        head = handle.read(8)

    if head.startswith(_PDF_MAGIC):
        return PDF_MIME, ProtocolFileKind.PDF
    if head.startswith(_ZIP_MAGIC) or head.startswith(_ZIP_EMPTY_MAGIC):
        if _is_docx_zip(file_path):
            return DOCX_MIME, ProtocolFileKind.DOCX
        return UNKNOWN_MIME, ProtocolFileKind.UNKNOWN
    if head.startswith(_OLE_MAGIC):
        return DOC_MIME, ProtocolFileKind.DOC
    # 兜底：纯文本
    try:
        head.decode("utf-8")
    except UnicodeDecodeError:
        return UNKNOWN_MIME, ProtocolFileKind.UNKNOWN
    return TXT_MIME, ProtocolFileKind.TXT


def register_source_artifact(
    path: str | Path,
    *,
    source_artifact_id: str,
    storage_root: str | Path,
    uploaded_at: datetime | None = None,
) -> ProtocolSourceArtifact:
    """登记一份原始方案，产出不可变的 :class:`ProtocolSourceArtifact`。

    只读并哈希源文件，再复制到 V2 数据根下的内容寻址路径。后续流程可用
    ``storage_ref`` 找到不可变副本，不依赖用户原始路径持续存在。
    """
    file_path = Path(path)
    sha256 = compute_sha256(file_path)
    mime_type, _kind = detect_format(file_path)
    size_bytes = file_path.stat().st_size
    suffix = file_path.suffix.lower() or ".bin"
    storage_ref = f"{_SOURCE_STORAGE_PREFIX}/{sha256}{suffix}"
    stored_path = Path(storage_root) / storage_ref
    stored_path.parent.mkdir(parents=True, exist_ok=True)
    if not stored_path.is_file() or compute_sha256(stored_path) != sha256:
        temp_path = stored_path.with_name(stored_path.name + ".tmp")
        try:
            with file_path.open("rb") as source, temp_path.open("wb") as target:
                shutil.copyfileobj(source, target, length=_CHUNK)
            if compute_sha256(temp_path) != sha256:
                raise SourceIngestionError("原始方案复制后哈希不一致，已停止登记")
            os.replace(temp_path, stored_path)
        finally:
            temp_path.unlink(missing_ok=True)
    return ProtocolSourceArtifact(
        source_artifact_id=source_artifact_id,
        file_name=file_path.name,
        sha256=sha256,
        mime_type=mime_type,
        size_bytes=size_bytes,
        storage_ref=storage_ref,
        uploaded_at=uploaded_at or utc_now(),
    )
