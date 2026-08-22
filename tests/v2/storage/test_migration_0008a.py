"""Phase 4 迁移 0008a：上传预览三表 升级/降级/备份 确定性测试（Slice 4.2）。

覆盖 P4-AC12（数据完整性）与追加迁移链：0007 -> 0008 -> 0008a -> 降级/恢复回归。
不回改已验收的 ``0008_evidence_ingestion``，并保持后续 ``0009_ocr_artifacts``
职责不变。断言包括：0008 状态无上传预览表、0008a 状态三表齐全且 schema/metadata
一致、迁移前备份保留 0008 数据、降级只删上传预览表并保留证据表、含预览/确认数据
时拒绝有损降级、WAL/外键与自引用链回归。
"""
from __future__ import annotations

import json

import pytest
import sqlalchemy as sa
from sqlalchemy import MetaData
from sqlalchemy.exc import IntegrityError

from app.storage.db import build_engine, build_session_factory
from app.storage.evidence_models import SourceBlobRecord
from app.storage.evidence_upload_models import EvidenceUploadItemRecord
from app.storage.migrate import (
    MigrationFailure,
    MigrationManager,
    verify_schema_matches_metadata,
)
from tests.v2.storage.test_migration_0008 import (
    EVIDENCE_TABLES,
    EVIDENCE_UPLOAD_TABLES,
    OCR_TABLES,
    PAGE_REVIEW_TABLES,
    SLICE44_TABLES,
    _copy_table_without_slice44,
    _legacy_episode_save,
    _legacy_snapshot_save,
    _metadata_without_ocr,
    _upgrade_to_0007,
)
from tests.v2.storage.test_repositories_roundtrip import FIXTURES


def _metadata_without_upload() -> MetaData:
    """复制 Phase 3 + 0008 证据表（排除 0008a/0009/0010 表）作为 0008 校验目标。"""
    from app.storage.db import Base

    target = MetaData()
    for name, table in Base.metadata.tables.items():
        if name not in (
            EVIDENCE_UPLOAD_TABLES
            | OCR_TABLES
            | SLICE44_TABLES
            | PAGE_REVIEW_TABLES
        ):
            _copy_table_without_slice44(table, target)
    return target


def _seed_fixture(data_paths) -> tuple[str, str, str]:
    """预 0010 状态播种 fixture 最小作用域集（project/subject/episode），
    见 test_migration_0008._seed_fixture 说明。"""
    from app.storage.repositories import (
        PROTOCOL_DOC_CONFIG,
        AppendRepository,
        EpisodeRepository,
        ProjectRepository,
        SubjectRepository,
        save_protocol_authority_chain,
        save_rule_set,
    )

    engine = build_engine(data_paths.db_path)
    factory = build_session_factory(engine)
    with factory() as session:
        fixture = FIXTURES[0]
        AppendRepository(session, PROTOCOL_DOC_CONFIG).save(
            fixture.project.protocol_version
        )
        save_protocol_authority_chain(session, fixture)
        save_rule_set(session, fixture.rule_set)
        ProjectRepository(session).save(
            fixture.project, rule_set_revision=fixture.rule_set.revision
        )
        SubjectRepository(session).save(fixture.subject)
        _legacy_snapshot_save(session, fixture.evidence_snapshot)
        _legacy_episode_save(EpisodeRepository(session), fixture.review_episode)
        session.commit()
        ids = (
            fixture.project.project_id,
            fixture.subject.subject_id,
            fixture.review_episode.review_episode_id,
        )
        session.rollback()
    engine.dispose()
    return ids


def _journal_mode(db_path) -> str:
    connection = sa.create_engine(f"sqlite:///{db_path}").connect()
    try:
        return str(connection.exec_driver_sql("PRAGMA journal_mode").scalar_one())
    finally:
        connection.close()


def test_0008a_chain_0007_to_0008_keeps_upload_tables_absent(data_paths):
    """0008 状态：证据表存在，上传预览三表尚不存在。"""
    _upgrade_to_0007(data_paths)
    MigrationManager(data_paths, metadata=_metadata_without_upload()).upgrade("0008")
    engine = build_engine(data_paths.db_path)
    try:
        actual = set(sa.inspect(engine).get_table_names())
        assert EVIDENCE_TABLES <= actual
        assert not (EVIDENCE_UPLOAD_TABLES & actual), "0008 状态不应存在上传预览表"
    finally:
        engine.dispose()


def test_0008a_upgrade_creates_exact_tables_matching_metadata(data_paths):
    """0008a 升级：上传预览三表齐全，schema 与 metadata 一致，外键无违规。"""
    _upgrade_to_0007(data_paths)
    manager = MigrationManager(data_paths, metadata=_metadata_without_ocr())
    result = manager.upgrade("0008a")
    assert result.to_revision == "0008a"
    engine = build_engine(data_paths.db_path)
    try:
        problems = verify_schema_matches_metadata(engine, manager.metadata)
        assert problems == [], f"schema 与 metadata 不一致：{problems}"
        actual = set(sa.inspect(engine).get_table_names())
        assert EVIDENCE_UPLOAD_TABLES <= actual
        with engine.connect() as connection:
            violations = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
        assert violations == []
    finally:
        engine.dispose()


def test_0008a_backup_created_before_upgrade_preserves_0008_data(data_paths):
    """从 0008 升级 0008a 前生成备份；升级后既有证据数据与项目数据保留。"""
    _upgrade_to_0007(data_paths)
    project_id, subject_id, episode_id = _seed_fixture(data_paths)
    MigrationManager(data_paths, metadata=_metadata_without_upload()).upgrade("0008")
    engine = build_engine(data_paths.db_path)
    digest = "d" * 64
    payload = json.dumps(
        {
            "source_blob_id": digest,
            "sha256": digest,
            "byte_size": 1,
            "media_type": "application/pdf",
            "storage_ref": f"blobs/{digest}",
            "created_at": "2026-08-19T12:00:00Z",
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    with build_session_factory(engine)() as session:
        session.add(
            SourceBlobRecord(
                source_blob_id=digest,
                sha256=digest,
                byte_size=1,
                media_type="application/pdf",
                storage_ref=f"blobs/{digest}",
                payload_json=payload,
                payload_sha256=__import__("hashlib").sha256(payload.encode("utf-8")).hexdigest(),
                created_at=sa.func.current_timestamp(),
            )
        )
        session.commit()
    engine.dispose()

    manager = MigrationManager(data_paths)
    result = manager.upgrade("head")
    assert result.backup is not None and result.backup.source_revision == "0008"
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
                "SELECT COUNT(*) FROM source_blobs"
            ).scalar_one() == 1
    finally:
        engine.dispose()
    # 备份可恢复回 0008 状态，数据完好。
    manager.restore(result.backup.path)
    assert MigrationManager(data_paths).read_revision(data_paths.db_path) == "0008"


def test_0008a_downgrade_drops_only_upload_tables_and_preserves_evidence(data_paths):
    """0008a -> 0008 降级只删上传预览三表；0008 证据表与项目数据保留。"""
    _upgrade_to_0007(data_paths)
    project_id, subject_id, _episode_id = _seed_fixture(data_paths)
    MigrationManager(data_paths).upgrade("head")
    manager = MigrationManager(data_paths)
    result = manager.downgrade("0008")
    assert result.to_revision == "0008"
    engine = build_engine(data_paths.db_path)
    try:
        actual = set(sa.inspect(engine).get_table_names())
        assert not (EVIDENCE_UPLOAD_TABLES & actual), "降级后上传预览表仍存在"
        assert EVIDENCE_TABLES <= actual, "降级不得删除 0008 证据表"
        with engine.connect() as connection:
            assert connection.exec_driver_sql(
                "SELECT project_id FROM projects"
            ).scalar_one() == project_id
            assert connection.exec_driver_sql(
                "SELECT subject_id FROM subjects"
            ).scalar_one() == subject_id
    finally:
        engine.dispose()


def test_0008a_downgrade_refuses_upload_data_loss(data_paths):
    """上传预览表已有数据时，0008a 降级必须拒绝并由管理器恢复备份。"""
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
    import hashlib

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
    with pytest.raises(MigrationFailure, match="拒绝降级"):
        manager.downgrade("0008")
    assert manager.read_revision(data_paths.db_path) == "0008a"
    engine = build_engine(data_paths.db_path)
    try:
        with engine.connect() as connection:
            assert connection.exec_driver_sql(
                "SELECT COUNT(*) FROM evidence_upload_previews"
            ).scalar_one() == 1
    finally:
        engine.dispose()


def test_0008a_upgrade_downgrade_upgrade_cycle_preserves_data(data_paths):
    """0007 -> 0008 -> 0008a -> 降级 0008 -> 再升级 0008a 全程数据保留。"""
    _upgrade_to_0007(data_paths)
    project_id, subject_id, episode_id = _seed_fixture(data_paths)
    MigrationManager(data_paths).upgrade("head")
    MigrationManager(data_paths).downgrade("0008")
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
    finally:
        engine.dispose()


def test_0008a_wal_mode_and_foreign_keys_active_after_upgrade(data_paths):
    """0008a 升级后 WAL 与外键运行时合同保持生效。"""
    _upgrade_to_0007(data_paths)
    MigrationManager(data_paths).upgrade("head")
    assert _journal_mode(data_paths.db_path) == "wal"
    engine = build_engine(data_paths.db_path)
    try:
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
    finally:
        engine.dispose()


def test_0008a_upload_tables_enforce_foreign_keys(data_paths):
    """上传条目指向不存在的预览时，外键拒绝写入。"""
    _upgrade_to_0007(data_paths)
    MigrationManager(data_paths).upgrade("head")
    engine = build_engine(data_paths.db_path)
    try:
        with build_session_factory(engine)() as session:
            session.add(
                EvidenceUploadItemRecord(
                    item_id="item-bogus",
                    preview_id="preview-missing",
                    file_name="report.pdf",
                    sha256="a" * 64,
                    byte_size=1,
                    media_type="application/pdf",
                    storage_ref="staging/preview-missing/aaaa",
                    status="added",
                    processing_hint="process_new",
                    logical_document_id=None,
                    existing_version_id=None,
                    error_detail=None,
                    payload_json="{}",
                    payload_sha256="b" * 64,
                    created_at=sa.func.current_timestamp(),
                )
            )
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
        with engine.connect() as connection:
            violations = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
        assert violations == []
    finally:
        engine.dispose()
