"""契约 JSON Schema、时间戳时区与规范块集工件落盘不变量测试。"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import jsonschema
import pytest
from docx import Document

from app.domain.contracts.enums import ExtractionStatus, RenderStatus
from app.domain.contracts.protocol_ingestion import (
    ProtocolExtractionSnapshot,
    ProtocolRenderArtifact,
    ProtocolSourceArtifact,
    ProtocolSourceSpan,
)
from app.protocols.docx_structure import extract_docx_structure
from app.protocols.ingestion import register_source_artifact, utc_now

_SHA = "0" * 64


def _small_docx(tmp_path):
    path = tmp_path / "small.docx"
    doc = Document()
    doc.add_paragraph("入选标准")
    doc.save(str(path))
    return path


def test_contract_json_schema_validates_instances():
    """契约模型的 JSON Schema 能校验合法实例，并拒绝缺失必需字段的实例。"""
    source = ProtocolSourceArtifact(
        source_artifact_id="src",
        file_name="a.docx",
        sha256=_SHA,
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size_bytes=1,
        storage_ref="ref",
        uploaded_at=datetime.now(timezone.utc),
    )
    schema = ProtocolSourceArtifact.model_json_schema()
    jsonschema.validate(source.model_dump(mode="json"), schema)

    # 缺失必需字段（sha256）必须被拒绝
    bad = source.model_dump(mode="json")
    del bad["sha256"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)


def test_snapshot_schema_requires_content_artifacts():
    """快照 JSON Schema 必须要求 content_sha256 与 content_storage_ref。"""
    schema = ProtocolExtractionSnapshot.model_json_schema()
    required = set(schema.get("required", []))
    assert {"content_sha256", "content_storage_ref", "source_sha256"} <= required


def test_render_schema_requires_status_and_page_identity():
    """渲染契约 JSON Schema 要求 status 与渲染器版本；页数/PDF 哈希可空但受约束。"""
    schema = ProtocolRenderArtifact.model_json_schema()
    required = set(schema.get("required", []))
    assert {"status", "renderer_version", "source_sha256"} <= required
    # pdf_sha256 使用 hex64 模式约束（可空 -> anyOf 首分支）
    props = schema["properties"]
    sha_schema = props["pdf_sha256"]["anyOf"][0]
    assert sha_schema["pattern"] == "^[0-9a-f]{64}$"
    assert sha_schema["type"] == "string"


def test_protocol_layer_timestamps_are_timezone_aware_utc(tmp_path):
    """协议层产出的时间戳必须带 UTC 时区；naive 形态只允许出现在存储层。"""
    path = _small_docx(tmp_path)
    artifact = register_source_artifact(
        path, source_artifact_id="tz", storage_root=tmp_path
    )
    assert artifact.uploaded_at.tzinfo is not None
    assert artifact.uploaded_at.utcoffset().total_seconds() == 0

    ext = extract_docx_structure(
        path, snapshot_id="tz-snap", source_artifact=artifact, output_dir=tmp_path
    )
    assert ext.snapshot.created_at.tzinfo is not None
    assert ext.snapshot.created_at.utcoffset().total_seconds() == 0

    assert utc_now().tzinfo is not None


def test_snapshot_blob_is_persisted_and_sha256_verified(tmp_path):
    path = _small_docx(tmp_path)
    artifact = register_source_artifact(
        path, source_artifact_id="blob", storage_root=tmp_path
    )
    ext = extract_docx_structure(
        path, snapshot_id="blob-snap", source_artifact=artifact, output_dir=tmp_path
    )
    blob = Path(tmp_path) / ext.snapshot.content_storage_ref
    assert blob.is_file(), "成功快照不得指向不存在的块集工件"
    assert hashlib.sha256(blob.read_bytes()).hexdigest() == ext.snapshot.content_sha256


def test_source_registration_creates_content_addressed_immutable_copy(tmp_path):
    path = _small_docx(tmp_path)
    artifact = register_source_artifact(
        path, source_artifact_id="source-copy", storage_root=tmp_path / "data"
    )
    stored = tmp_path / "data" / artifact.storage_ref
    assert stored.is_file()
    assert stored.name == f"{artifact.sha256}.docx"
    original_copy = stored.read_bytes()

    path.write_bytes(b"changed outside the V2 store")
    assert stored.read_bytes() == original_copy
    assert hashlib.sha256(original_copy).hexdigest() == artifact.sha256


def test_preexisting_mismatched_blob_is_repaired(tmp_path):
    path = _small_docx(tmp_path)
    artifact = register_source_artifact(
        path, source_artifact_id="repair", storage_root=tmp_path
    )
    ext = extract_docx_structure(
        path, snapshot_id="repair-snap", source_artifact=artifact, output_dir=tmp_path
    )
    blob = Path(tmp_path) / ext.snapshot.content_storage_ref
    # 用错误内容覆盖既有工件，模拟损坏
    blob.write_text('{"tampered": true}', encoding="utf-8")
    assert hashlib.sha256(blob.read_bytes()).hexdigest() != ext.snapshot.content_sha256

    # 再次提取（确定性）应原子修复
    ext2 = extract_docx_structure(
        path, snapshot_id="repair-snap2", source_artifact=artifact, output_dir=tmp_path
    )
    assert hashlib.sha256(blob.read_bytes()).hexdigest() == ext2.snapshot.content_sha256


def test_span_contract_forbids_inconsistent_locator():
    from app.domain.contracts.enums import AlignmentStatus, DocumentPart, SourceLocatorPrecision

    base = dict(
        source_span_id="s1",
        snapshot_id="snap",
        source_ref="body.p0",
        document_part=DocumentPart.BODY,
        block_order=0,
        precision=SourceLocatorPrecision.BLOCK,
        alignment_status=AlignmentStatus.UNALIGNED,
        degradation_reason="未对齐",
    )
    ProtocolSourceSpan(**base)
    # page_only 携带伪精确摘录必须被拒绝
    with pytest.raises(Exception):
        ProtocolSourceSpan(
            **{**base, "precision": SourceLocatorPrecision.PAGE_ONLY, "excerpt": "伪摘录"}
        )
