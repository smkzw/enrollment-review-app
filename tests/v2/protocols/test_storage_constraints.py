"""Phase 3 提取层存储约束：源工件 SHA-256 去重、table_path JSON 与 render_error 镜像列。"""
from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app.storage.models import (
    ProtocolExtractionSnapshotRecord,
    ProtocolRenderArtifactRecord,
    ProtocolSourceArtifactRecord,
    ProtocolSourceSpanRecord,
)

_NOW = datetime(2026, 8, 14)


def _add_source_artifact(session, artifact_id, sha256):
    session.add(
        ProtocolSourceArtifactRecord(
            source_artifact_id=artifact_id,
            sha256=sha256,
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            size_bytes=1,
            storage_ref=f"ref/{artifact_id}",
            uploaded_at=_NOW,
            payload_json="{}",
            payload_sha256="0" * 64,
            created_at=_NOW,
        )
    )


def test_source_artifact_sha256_unique(migrated_engine, session_factory):
    sha = "a" * 64
    with session_factory() as session:
        _add_source_artifact(session, "src-1", sha)
        session.commit()
    with session_factory() as session:
        _add_source_artifact(session, "src-2", sha)
        with pytest.raises(IntegrityError, match="UNIQUE"):
            session.commit()


def test_span_table_path_and_render_error_mirror_columns(migrated_engine, session_factory):
    """table_path 以 JSON 列持久化，render_error 以镜像列持久化。"""
    with session_factory() as session:
        _add_source_artifact(session, "src", "b" * 64)
        session.flush()  # 先持久化父行，避免无 relationship 的 ORM 插入顺序问题
        session.add(
            ProtocolExtractionSnapshotRecord(
                snapshot_id="snap",
                source_artifact_id="src",
                source_sha256="b" * 64,
                parser_name="docx-ooxml",
                parser_version="1.1.0",
                status="completed",
                content_sha256="c" * 64,
                content_storage_ref="blobs/protocol_blocks/x.json",
                payload_json="{}",
                payload_sha256="0" * 64,
                created_at=_NOW,
            )
        )
        session.add(
            ProtocolRenderArtifactRecord(
                render_artifact_id="render",
                source_artifact_id="src",
                source_sha256="b" * 64,
                renderer="libreoffice",
                renderer_version="26.2.5.2",
                pdf_sha256="d" * 64,
                page_count=3,
                status="succeeded",
                storage_ref="ref/pdf",
                render_error=None,
                payload_json="{}",
                payload_sha256="0" * 64,
                created_at=_NOW,
            )
        )
        session.add(
            ProtocolSourceSpanRecord(
                source_span_id="span",
                snapshot_id="snap",
                source_ref="body.t0.r1.c2.t0.r0.c0.p0",
                document_part="body",
                precision="block",
                alignment_status="unaligned",
                render_artifact_id=None,
                render_page=None,
                table_path=[1, 2, 0, 0],
                payload_json="{}",
                payload_sha256="0" * 64,
                created_at=_NOW,
            )
        )
        session.commit()

    with session_factory() as session:
        span = session.get(ProtocolSourceSpanRecord, "span")
        assert span.table_path == [1, 2, 0, 0]
        render = session.get(ProtocolRenderArtifactRecord, "render")
        assert render.render_error is None
