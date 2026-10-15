"""Phase 4 迁移 0009：OCR 工件与基础处理修订表 升级/降级/备份 确定性测试（Slice 4.3）。

覆盖 P4-AC12（数据完整性）与追加迁移链：0007 -> 0008 -> 0008a -> 0009 ->
降级/恢复回归。不回改已验收的 ``0008``/``0008a``。断言包括：0008a 状态无 OCR
表、0009 状态十张 OCR 表齐全且 schema/metadata 一致、迁移前备份保留既有数据、
降级只删 OCR 表并保留证据/上传表、含 OCR 正式数据时拒绝有损降级、WAL/外键/
自引用重试链与跨表外键回归。
"""
from __future__ import annotations

import hashlib
import json

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from app.domain.contracts.enums import ExtractionRoute
from app.domain.contracts.ocr import OCRProfile
from app.evidence.fingerprint import build_profile_fingerprint
from app.storage.db import build_engine, build_session_factory
from app.storage.migrate import (
    MigrationFailure,
    MigrationManager,
    verify_schema_matches_metadata,
)
from app.storage.ocr_repositories import OCRProfileRepository
from tests.v2.storage.test_migration_0008 import (
    EVIDENCE_TABLES,
    EVIDENCE_UPLOAD_TABLES,
    OCR_TABLES,
    _metadata_without_ocr,
    _metadata_without_slice44,
    _seed_fixture,
    _upgrade_to_0007,
)

OCR_PROFILE_FIELDS = {
    "ocr_profile_id": "profile-1",
    "extraction_route": "vision_ocr",
    "provider": "omlx",
    "model_id": "GLM-OCR-bf16",
    "model_revision": "unknown",
    "prompt_sha256": None,
    "parser_version": "v1",
    "render_params_sha256": None,
    "request_params_sha256": None,
    "layout_parser_version": "layout-v1",
    "coordinate_transform_version": "t/v1",
}


def _seed_ocr_profile(data_paths) -> None:
    from datetime import UTC, datetime

    engine = build_engine(data_paths.db_path)
    factory = build_session_factory(engine)
    with factory() as session:
        profile = OCRProfile(
            ocr_profile_id=OCR_PROFILE_FIELDS["ocr_profile_id"],
            profile_sha256=build_profile_fingerprint(
                extraction_route=OCR_PROFILE_FIELDS["extraction_route"],
                provider=OCR_PROFILE_FIELDS["provider"],
                model_id=OCR_PROFILE_FIELDS["model_id"],
                model_revision=OCR_PROFILE_FIELDS["model_revision"],
                prompt_sha256=OCR_PROFILE_FIELDS["prompt_sha256"],
                parser_version=OCR_PROFILE_FIELDS["parser_version"],
                render_params_sha256=OCR_PROFILE_FIELDS["render_params_sha256"],
                request_params_sha256=OCR_PROFILE_FIELDS["request_params_sha256"],
                layout_parser_version=OCR_PROFILE_FIELDS["layout_parser_version"],
                coordinate_transform_version=OCR_PROFILE_FIELDS["coordinate_transform_version"],
            ),
            extraction_route=ExtractionRoute.VISION_OCR,
            provider=OCR_PROFILE_FIELDS["provider"],
            model_id=OCR_PROFILE_FIELDS["model_id"],
            model_revision=OCR_PROFILE_FIELDS["model_revision"],
            parser_version=OCR_PROFILE_FIELDS["parser_version"],
            layout_parser_version=OCR_PROFILE_FIELDS["layout_parser_version"],
            coordinate_transform_version=OCR_PROFILE_FIELDS["coordinate_transform_version"],
            created_at=datetime(2026, 8, 19, 12, 0, 0, tzinfo=UTC),
        )
        OCRProfileRepository(session).get_or_create(profile)
        session.commit()
    engine.dispose()


def _journal_mode(db_path) -> str:
    connection = sa.create_engine(f"sqlite:///{db_path}").connect()
    try:
        return str(connection.exec_driver_sql("PRAGMA journal_mode").scalar_one())
    finally:
        connection.close()


def test_0009_chain_0007_to_0008a_keeps_ocr_tables_absent(data_paths):
    """0008a 状态：证据/上传表存在，OCR 十表尚不存在。"""
    _upgrade_to_0007(data_paths)
    MigrationManager(data_paths, metadata=_metadata_without_ocr()).upgrade("0008a")
    engine = build_engine(data_paths.db_path)
    try:
        actual = set(sa.inspect(engine).get_table_names())
        assert EVIDENCE_TABLES | EVIDENCE_UPLOAD_TABLES <= actual
        assert not (OCR_TABLES & actual), "0008a 状态不应存在 OCR 表"
    finally:
        engine.dispose()


def test_0009_upgrade_creates_exact_tables_matching_metadata(data_paths):
    """0009 升级：OCR 十表齐全，schema 与 metadata 一致，外键无违规。"""
    _upgrade_to_0007(data_paths)
    manager = MigrationManager(data_paths, metadata=_metadata_without_slice44())
    result = manager.upgrade("0009")
    assert result.to_revision == "0009"
    engine = build_engine(data_paths.db_path)
    try:
        problems = verify_schema_matches_metadata(engine, manager.metadata)
        assert problems == [], f"schema 与 metadata 不一致：{problems}"
        actual = set(sa.inspect(engine).get_table_names())
        assert OCR_TABLES <= actual
        with engine.connect() as connection:
            violations = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
        assert violations == []
    finally:
        engine.dispose()


def test_0009_backup_created_before_upgrade_preserves_0008a_data(data_paths):
    """从 0008a 升级 0009 前生成备份；升级后既有证据/上传/项目数据保留。"""
    _upgrade_to_0007(data_paths)
    project_id, subject_id, episode_id = _seed_fixture(data_paths)
    MigrationManager(data_paths, metadata=_metadata_without_ocr()).upgrade("0008a")
    engine = build_engine(data_paths.db_path)
    payload = json.dumps(
        {
            "preview_id": "preview-1",
            "project_id": project_id,
            "subject_id": subject_id,
            "review_episode_id": episode_id,
            "upload_mode": "full",
            "base_revision": 1,
            "base_snapshot_id": None,
            "status": "staged",
            "preview_sha256": "e" * 64,
            "items": [],
            "created_at": "2026-08-19T12:00:00Z",
            "created_by": "tester",
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    with build_session_factory(engine)() as session:
        from app.storage.evidence_upload_models import EvidenceUploadPreviewRecord

        session.add(
            EvidenceUploadPreviewRecord(
                preview_id="preview-1",
                project_id=project_id,
                subject_id=subject_id,
                review_episode_id=episode_id,
                upload_mode="full",
                base_revision=1,
                base_snapshot_id=None,
                status="staged",
                preview_sha256="e" * 64,
                created_by="tester",
                payload_json=payload,
                payload_sha256=hashlib.sha256(payload.encode("utf-8")).hexdigest(),
                created_at=sa.func.current_timestamp(),
            )
        )
        session.commit()
    engine.dispose()

    manager = MigrationManager(data_paths)
    result = manager.upgrade("head")
    assert result.backup is not None and result.backup.source_revision == "0008a"
    engine = build_engine(data_paths.db_path)
    try:
        with engine.connect() as connection:
            assert connection.exec_driver_sql(
                "SELECT project_id FROM projects"
            ).scalar_one() == project_id
            assert connection.exec_driver_sql(
                "SELECT subject_id FROM subjects"
            ).scalar_one() == subject_id
            assert connection.exec_driver_sql(
                "SELECT review_episode_id FROM review_episodes"
            ).scalar_one() == episode_id
            assert connection.exec_driver_sql(
                "SELECT COUNT(*) FROM evidence_upload_previews"
            ).scalar_one() == 1
    finally:
        engine.dispose()
    # 备份可恢复回 0008a 状态，数据完好。
    manager.restore(result.backup.path)
    assert MigrationManager(data_paths).read_revision(data_paths.db_path) == "0008a"


def test_0009_downgrade_drops_only_ocr_tables_and_preserves_evidence_upload(data_paths):
    """0009 -> 0008a 降级只删 OCR 十表；0008/0008a 证据与项目数据保留。"""
    _upgrade_to_0007(data_paths)
    project_id, subject_id, _episode_id = _seed_fixture(data_paths)
    MigrationManager(data_paths).upgrade("head")
    manager = MigrationManager(data_paths)
    result = manager.downgrade("0008a")
    assert result.to_revision == "0008a"
    engine = build_engine(data_paths.db_path)
    try:
        actual = set(sa.inspect(engine).get_table_names())
        assert not (OCR_TABLES & actual), "降级后 OCR 表仍存在"
        assert EVIDENCE_TABLES | EVIDENCE_UPLOAD_TABLES <= actual, "降级不得删除证据/上传表"
        with engine.connect() as connection:
            assert connection.exec_driver_sql(
                "SELECT project_id FROM projects"
            ).scalar_one() == project_id
            assert connection.exec_driver_sql(
                "SELECT subject_id FROM subjects"
            ).scalar_one() == subject_id
    finally:
        engine.dispose()


def test_0009_downgrade_refuses_ocr_data_loss(data_paths):
    """OCR 表已有数据时，0009 降级必须拒绝并由管理器恢复备份。"""
    _upgrade_to_0007(data_paths)
    _seed_fixture(data_paths)
    MigrationManager(data_paths, metadata=_metadata_without_slice44()).upgrade("0009")
    _seed_ocr_profile(data_paths)

    manager = MigrationManager(data_paths)
    with pytest.raises(MigrationFailure, match="拒绝降级"):
        manager.downgrade("0008a")
    assert manager.read_revision(data_paths.db_path) == "0009"
    engine = build_engine(data_paths.db_path)
    try:
        with engine.connect() as connection:
            assert connection.exec_driver_sql(
                "SELECT COUNT(*) FROM ocr_profiles"
            ).scalar_one() == 1
    finally:
        engine.dispose()


def test_0009_upgrade_downgrade_upgrade_cycle_preserves_data(data_paths):
    """0007 -> 0008 -> 0008a -> 0009 -> 降级 0008a -> 再升级 0009 全程数据保留。"""
    _upgrade_to_0007(data_paths)
    project_id, subject_id, episode_id = _seed_fixture(data_paths)
    MigrationManager(data_paths).upgrade("head")
    MigrationManager(data_paths).downgrade("0008a")
    MigrationManager(data_paths).upgrade("head")
    engine = build_engine(data_paths.db_path)
    try:
        with engine.connect() as connection:
            assert connection.exec_driver_sql(
                "SELECT project_id FROM projects"
            ).scalar_one() == project_id
            assert connection.exec_driver_sql(
                "SELECT subject_id FROM subjects"
            ).scalar_one() == subject_id
            assert connection.exec_driver_sql(
                "SELECT review_episode_id FROM review_episodes"
            ).scalar_one() == episode_id
            assert connection.exec_driver_sql(
                "SELECT COUNT(*) FROM evidence_upload_previews"
            ).scalar_one() == 0
            assert connection.exec_driver_sql(
                "SELECT COUNT(*) FROM ocr_profiles"
            ).scalar_one() == 0
    finally:
        engine.dispose()


def test_0009_wal_mode_and_foreign_keys_active_after_upgrade(data_paths):
    """0009 升级后 WAL 与外键运行时合同保持生效。"""
    _upgrade_to_0007(data_paths)
    MigrationManager(data_paths).upgrade("head")
    assert _journal_mode(data_paths.db_path) == "wal"
    engine = build_engine(data_paths.db_path)
    try:
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
    finally:
        engine.dispose()


def test_0009_page_artifact_requires_existing_document_version(data_paths):
    """页产物指向不存在的资料版本时，外键拒绝写入。"""
    _upgrade_to_0007(data_paths)
    _seed_fixture(data_paths)
    MigrationManager(data_paths).upgrade("head")
    engine = build_engine(data_paths.db_path)
    try:
        with build_session_factory(engine)() as session:
            from app.storage.ocr_models import PageArtifactRecord

            session.add(
                PageArtifactRecord(
                    page_artifact_id="pa-bogus",
                    source_document_version_id="doc-missing",
                    page_number=1,
                    source_sha256="a" * 64,
                    page_input_sha256="b" * 64,
                    page_image_sha256="c" * 64,
                    page_width=595.0,
                    page_height=842.0,
                    rotation=0,
                    derivative_sha256="d" * 64,
                    coordinate_transform_version="t/v1",
                    status="succeeded",
                    payload_json=json.dumps(
                        {
                            "page_artifact_id": "pa-bogus",
                            "source_document_version_id": "doc-missing",
                            "page_number": 1,
                            "source_sha256": "a" * 64,
                            "page_input_sha256": "b" * 64,
                            "page_image_sha256": "c" * 64,
                            "page_width": 595.0,
                            "page_height": 842.0,
                            "rotation": 0,
                            "derivative_sha256": "d" * 64,
                            "coordinate_transform_version": "t/v1",
                            "status": "succeeded",
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    payload_sha256=hashlib.sha256(
                        json.dumps(
                            {
                                "page_artifact_id": "pa-bogus",
                                "source_document_version_id": "doc-missing",
                                "page_number": 1,
                                "source_sha256": "a" * 64,
                                "page_input_sha256": "b" * 64,
                                "page_image_sha256": "c" * 64,
                                "page_width": 595.0,
                                "page_height": 842.0,
                                "rotation": 0,
                                "derivative_sha256": "d" * 64,
                                "coordinate_transform_version": "t/v1",
                                "status": "succeeded",
                            },
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode("utf-8")
                    ).hexdigest(),
                    created_at=sa.func.current_timestamp(),
                )
            )
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
    finally:
        engine.dispose()


def test_0009_attempt_self_fk_retry_chain_enforced(data_paths):
    """尝试的 retry_of_attempt_id 自引用外键：指向不存在尝试时拒绝写入。"""
    _upgrade_to_0007(data_paths)
    project_id, subject_id, episode_id = _seed_fixture(data_paths)
    MigrationManager(data_paths).upgrade("head")
    engine = build_engine(data_paths.db_path)
    try:
        with build_session_factory(engine)() as session:
            # 需要存在的依赖：资料版本 + Profile + OCRRun
            from app.domain.contracts.evidence_ingestion import (
                SourceBlob,
                SourceDocumentVersion,
            )
            from app.storage.evidence_repositories import (
                BlobRepository,
                SourceDocumentRepository,
            )
            from app.storage.ocr_models import OCRAttemptRecord

            blob = SourceBlob(
                source_blob_id="a" * 64,
                sha256="a" * 64,
                byte_size=1,
                media_type="application/pdf",
                storage_ref="blobs/" + "a" * 64,
                created_at=__import__("datetime").datetime(
                    2026, 8, 19, 12, 0, 0, tzinfo=__import__("datetime").UTC
                ),
            )
            BlobRepository(session).get_or_create_by_sha256(blob)
            version = SourceDocumentVersion(
                source_document_version_id="doc-1",
                logical_document_id="log-1",
                source_blob_sha256="a" * 64,
                file_name="x.pdf",
                media_type="application/pdf",
                page_count=1,
                project_id=project_id,
                subject_id=subject_id,
                review_episode_id=episode_id,
                version_number=1,
                created_at=__import__("datetime").datetime(
                    2026, 8, 19, 12, 0, 0, tzinfo=__import__("datetime").UTC
                ),
                created_by="tester",
            )
            SourceDocumentRepository(session).create_version(version)
            session.flush()
            session.add(
                OCRAttemptRecord(
                    attempt_id="at-bogus",
                    ocr_run_id="run-missing",
                    cache_key="b" * 64,
                    attempt_number=1,
                    status="succeeded",
                    started_at=sa.func.current_timestamp(),
                    completed_at=sa.func.current_timestamp(),
                    retry_of_attempt_id="at-no-such",
                    payload_json="{}",
                    payload_sha256=hashlib.sha256(b"{}").hexdigest(),
                    created_at=sa.func.current_timestamp(),
                )
            )
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
    finally:
        engine.dispose()


def test_0009_partial_unique_index_on_ocr_pages_succeeded(data_paths):
    """ocr_pages 用部分唯一索引强制“同一缓存键至多一条成功结果”。

    迁移后断言索引形状（unique + sqlite_where）并实测强制：绕过仓储预检直插
    两条 SUCCEEDED 同 cache_key 行被索引拒绝；失败 + 成功行可共存。
    """
    from datetime import UTC, datetime

    from app.domain.contracts.enums import PageArtifactStatus
    from app.domain.contracts.evidence_ingestion import (
        SourceBlob,
        SourceDocumentVersion,
    )
    from app.domain.contracts.ocr import PageArtifact
    from app.storage.evidence_repositories import (
        BlobRepository,
        SourceDocumentRepository,
    )
    from app.storage.ocr_models import OCRPageRecord
    from app.storage.ocr_repositories import PageArtifactRepository

    _upgrade_to_0007(data_paths)
    project_id, subject_id, episode_id = _seed_fixture(data_paths)
    MigrationManager(data_paths).upgrade("head")
    _seed_ocr_profile(data_paths)
    engine = build_engine(data_paths.db_path)
    try:
        insp = sa.inspect(engine)
        indexes = {i["name"]: i for i in insp.get_indexes("ocr_pages")}
        partial = indexes["uq_ocr_pages_cache_key_succeeded"]
        assert partial["unique"], "部分唯一索引必须是唯一索引"
        assert "sqlite_where" in (partial.get("dialect_options") or {})
        # 旧的整列 cache_key 唯一约束已移除（不应再有同名唯一项）
        assert "uq_ocr_pages_cache_key" not in indexes
        assert "ix_ocr_pages_cache_key" in indexes

        factory = build_session_factory(engine)
        with factory() as session:
            blob = SourceBlob(
                source_blob_id="a" * 64,
                sha256="a" * 64,
                byte_size=1,
                media_type="application/pdf",
                storage_ref="blobs/" + "a" * 64,
                created_at=datetime(2026, 8, 19, 12, 0, 0, tzinfo=UTC),
            )
            BlobRepository(session).get_or_create_by_sha256(blob)
            version = SourceDocumentVersion(
                source_document_version_id="doc-1",
                logical_document_id="log-1",
                source_blob_sha256="a" * 64,
                file_name="x.pdf",
                media_type="application/pdf",
                page_count=1,
                project_id=project_id,
                subject_id=subject_id,
                review_episode_id=episode_id,
                version_number=1,
                created_at=datetime(2026, 8, 19, 12, 0, 0, tzinfo=UTC),
                created_by="tester",
            )
            SourceDocumentRepository(session).create_version(version)
            artifact = PageArtifact(
                page_artifact_id="pa-1",
                source_document_version_id="doc-1",
                page_number=1,
                source_sha256="b" * 64,
                page_input_sha256="c" * 64,
                page_image_sha256="d" * 64,
                page_width=595.0,
                page_height=842.0,
                rotation=0,
                renderer_version="render/v1",
                decoder_version="decode/v1",
                derivative_sha256="e" * 64,
                coordinate_transform_version="t/v1",
                status=PageArtifactStatus.SUCCEEDED,
            )
            PageArtifactRepository(session).get_or_create(artifact)
            session.commit()

        cache_key = "f" * 64
        started = datetime(2026, 8, 19, 12, 0, 0, tzinfo=UTC)

        def _row(page_id, status):
            return OCRPageRecord(
                ocr_page_id=page_id,
                page_artifact_id="pa-1",
                source_sha256="b" * 64,
                page_number=1,
                page_input_sha256="c" * 64,
                ocr_profile_id="profile-1",
                ocr_profile_sha256="g" * 64,
                cache_key=cache_key,
                layout_parser_version=None,
                coordinate_transform_version="t/v1",
                raw_text="t",
                raw_text_sha256=hashlib.sha256(b"t").hexdigest(),
                normalized_text="t",
                quality_json="{}",
                risk_items_json="[]",
                status=status,
                started_at=started,
                completed_at=started,
                payload_json="{}",
                payload_sha256=hashlib.sha256(b"{}").hexdigest(),
                created_at=started,
            )

        # 两条 SUCCEEDED 同 cache_key → 部分唯一索引拒绝
        with factory() as session:
            session.add(_row("op-1", "succeeded"))
            session.add(_row("op-2", "succeeded"))
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
        # 失败 + 成功可共存（同 cache_key）
        with factory() as session:
            session.add(_row("op-f", "failed"))
            session.add(_row("op-s", "succeeded"))
            session.commit()
            assert session.execute(
                sa.select(sa.func.count()).select_from(OCRPageRecord)
            ).scalar_one() == 2
    finally:
        engine.dispose()


def test_0009_page_artifact_geometry_columns_nullable(data_paths):
    """page_artifacts 几何/输入列可空，schema 与 ORM 一致；失败页可用 NULL 几何写入。

    迁移后列 nullable 与 ORM metadata 一致（verify_schema_matches_metadata 覆盖
    可空性），实测失败页（无输入/页宽/页高/旋转/页图，全部 NULL）可插入并回读。
    """
    from datetime import UTC, datetime

    from app.domain.contracts.enums import PageArtifactStatus
    from app.domain.contracts.evidence_ingestion import (
        SourceBlob,
        SourceDocumentVersion,
    )
    from app.domain.contracts.ocr import PageArtifact
    from app.storage.evidence_repositories import (
        BlobRepository,
        SourceDocumentRepository,
    )
    from app.storage.ocr_models import PageArtifactRecord
    from app.storage.ocr_repositories import PageArtifactRepository

    _upgrade_to_0007(data_paths)
    project_id, subject_id, episode_id = _seed_fixture(data_paths)
    manager = MigrationManager(data_paths)
    manager.upgrade("head")
    engine = build_engine(data_paths.db_path)
    try:
        # 1) 迁移后 schema 与 ORM metadata 完全一致（含可空性）
        problems = verify_schema_matches_metadata(engine, manager.metadata)
        assert problems == [], f"schema 与 metadata 不一致：{problems}"
        # 2) 四列可空
        insp = sa.inspect(engine)
        cols = {c["name"]: c for c in insp.get_columns("page_artifacts")}
        for name in ("page_input_sha256", "page_width", "page_height", "rotation"):
            assert cols[name]["nullable"] is True, f"{name} 应为可空列"
        assert cols["page_number"]["nullable"] is False

        # 3) 失败页（全部未知字段 NULL）可写入并回读
        factory = build_session_factory(engine)
        with factory() as session:
            blob = SourceBlob(
                source_blob_id="a" * 64,
                sha256="a" * 64,
                byte_size=1,
                media_type="application/pdf",
                storage_ref="blobs/" + "a" * 64,
                created_at=datetime(2026, 8, 19, 12, 0, 0, tzinfo=UTC),
            )
            BlobRepository(session).get_or_create_by_sha256(blob)
            version = SourceDocumentVersion(
                source_document_version_id="doc-1",
                logical_document_id="log-1",
                source_blob_sha256="a" * 64,
                file_name="x.pdf",
                media_type="application/pdf",
                page_count=1,
                project_id=project_id,
                subject_id=subject_id,
                review_episode_id=episode_id,
                version_number=1,
                created_at=datetime(2026, 8, 19, 12, 0, 0, tzinfo=UTC),
                created_by="tester",
            )
            SourceDocumentRepository(session).create_version(version)
            session.commit()
            failed = PageArtifact(
                page_artifact_id="pa-fail",
                source_document_version_id="doc-1",
                page_number=1,
                source_sha256="b" * 64,
                page_input_sha256=None,
                page_image_sha256=None,
                page_width=None,
                page_height=None,
                rotation=None,
                derivative_sha256="c" * 64,
                coordinate_transform_version="t/v1",
                status=PageArtifactStatus.FAILED,
                failure_reason="页面解码失败",
            )
            PageArtifactRepository(session).get_or_create(failed)
            session.commit()
            row = session.get(PageArtifactRecord, "pa-fail")
            assert row is not None
            assert row.page_input_sha256 is None
            assert row.page_width is None and row.page_height is None and row.rotation is None
            assert row.page_image_sha256 is None
    finally:
        engine.dispose()
