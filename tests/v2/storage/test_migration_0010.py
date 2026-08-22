"""Phase 4 迁移 0010：活动指针、base/complete 辨别与 Slice 4.4 旁路表 升级/降级/备份 确定性测试（WP-44A）。

覆盖 P4-AC12（数据完整性）与 0009 -> 0010 无损升级：

1. 从「填充了 review_episodes 子表数据的精确 0009」升级：行数、外键、legacy
   ``EvidenceProcessingRevision`` payload/hash、WAL、``PRAGMA foreign_key_check``
   与 ``integrity_check`` 前后一致；
2. 迁移不按时间/ID/历史 ``ACTIVE`` 状态回填活动指针：升级后指针全部 NULL；
3. 成对指针 CHECK 与指针外键被数据库强制；
4. 含任何 0010 正式历史时有损降级拒绝，空绿地库才允许降级；
5. 升级后 base 修订仍不可激活（``is_activatable=False``、``revision_kind='base'``）。
"""
from __future__ import annotations

import hashlib
import json

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from app.domain.contracts.enums import (
    ExtractionRoute,
    PageArtifactStatus,
    SnapshotMemberOrigin,
    SnapshotStatus,
    UploadMode,
)
from app.domain.contracts.evidence_ingestion import (
    EvidenceSnapshot,
    EvidenceSnapshotMember,
    SourceBlob,
    SourceDocumentVersion,
)
from app.domain.contracts.evidence_processing import (
    EvidenceProcessingRevision,
    EvidenceProcessingRevisionPage,
)
from app.domain.contracts.ocr import (
    OCRPage,
    OCRProfile,
    PageArtifact,
    PageQualityMetrics,
)
from app.domain.publication import (
    evidence_processing_manifest_hash,
    evidence_snapshot_collection_hash,
    ocr_page_cache_hash,
)
from app.evidence.fingerprint import build_profile_fingerprint
from app.storage.db import build_engine, build_session_factory
from app.storage.evidence_repositories import BlobRepository
from app.storage.migrate import (
    MigrationFailure,
    MigrationManager,
    resolve_head_revision,
    verify_schema_matches_metadata,
)
from app.storage.ocr_repositories import OCRProfileRepository
from tests.v2.storage.test_migration_0008 import (
    SLICE44_TABLES,
    _metadata_without_slice44,
    _seed_fixture,
    _upgrade_to_0007,
)

_SHA = "0" * 64
_UTC = "2026-08-19T12:00:00Z"


def _journal_mode(db_path) -> str:
    connection = sa.create_engine(f"sqlite:///{db_path}").connect()
    try:
        return str(connection.exec_driver_sql("PRAGMA journal_mode").scalar_one())
    finally:
        connection.close()


def _integrity(db_path) -> str:
    connection = sa.create_engine(f"sqlite:///{db_path}").connect()
    try:
        return str(connection.exec_driver_sql("PRAGMA integrity_check").scalar_one())
    finally:
        connection.close()


def _seed_populated_0009(data_paths) -> dict:
    """升级到精确 0009 并填充 review_episodes 子表数据（快照/成员/OCR/基础修订/预览）。

    0009 的 review_episodes 尚无活动指针列，Phase 4 仓储的 episode scope 检查（经
    ORM SELECT）会失败，因此资料版本/快照/成员/状态事件用直接 ORM record 插入，
    OCR Profile/页产物/OCR 页/base 修订用不含 episode 读取的仓储写入。
    """
    from datetime import UTC, datetime

    from app.storage.codecs import encode_contract
    from app.storage.evidence_models import (
        EvidenceSnapshotMemberRecord,
        EvidenceSnapshotStatusEventRecord,
        EvidenceSnapshotV2Record,
        SourceDocumentVersionV2Record,
    )

    _upgrade_to_0007(data_paths)
    project_id, subject_id, episode_id = _seed_fixture(data_paths)
    manager = MigrationManager(data_paths, metadata=_metadata_without_slice44())
    manager.upgrade("0009")
    engine = build_engine(data_paths.db_path)
    fixed = datetime(2026, 8, 19, 12, 0, 0, tzinfo=UTC)
    try:
        with build_session_factory(engine)() as session:
            blob = SourceBlob(
                source_blob_id=_SHA,
                sha256=_SHA,
                byte_size=1,
                media_type="application/pdf",
                storage_ref="blobs/" + _SHA,
                created_at=fixed,
            )
            BlobRepository(session).get_or_create_by_sha256(blob)
            version = SourceDocumentVersion(
                source_document_version_id="doc-1",
                logical_document_id="log-1",
                source_blob_sha256=_SHA,
                file_name="lab.pdf",
                media_type="application/pdf",
                page_count=1,
                project_id=project_id,
                subject_id=subject_id,
                review_episode_id=episode_id,
                version_number=1,
                created_at=fixed,
                created_by="tester",
            )
            _insert_record(session, SourceDocumentVersionV2Record, version, {
                "source_document_version_id": "doc-1",
                "logical_document_id": "log-1",
                "source_blob_sha256": _SHA,
                "file_name": "lab.pdf",
                "media_type": "application/pdf",
                "page_count": 1,
                "project_id": project_id,
                "subject_id": subject_id,
                "review_episode_id": episode_id,
                "version_number": 1,
                "supersedes_version_id": None,
                "created_by": "tester",
            })

            snapshot = EvidenceSnapshot(
                evidence_snapshot_id="snap-1",
                project_id=project_id,
                subject_id=subject_id,
                review_episode_id=episode_id,
                upload_mode=UploadMode.FULL,
                prior_snapshot_id=None,
                comparison_snapshot_id=None,
                members=[
                    EvidenceSnapshotMember(
                        member_id="m-1",
                        snapshot_id="snap-1",
                        logical_document_id="log-1",
                        source_document_version_id="doc-1",
                        origin=SnapshotMemberOrigin.ADDED,
                    )
                ],
                collection_sha256=evidence_snapshot_collection_hash(
                    members=[("log-1", "doc-1")]
                ),
                status=SnapshotStatus.ACTIVE,
                created_at=fixed,
                created_by="tester",
            )
            _insert_record(session, EvidenceSnapshotV2Record, snapshot, {
                "evidence_snapshot_id": "snap-1",
                "project_id": project_id,
                "subject_id": subject_id,
                "review_episode_id": episode_id,
                "upload_mode": "full",
                "prior_snapshot_id": None,
                "comparison_snapshot_id": None,
                "collection_sha256": evidence_snapshot_collection_hash(
                    members=[("log-1", "doc-1")]
                ),
                "created_by": "tester",
            })
            member = EvidenceSnapshotMember(
                member_id="m-1",
                snapshot_id="snap-1",
                logical_document_id="log-1",
                source_document_version_id="doc-1",
                origin=SnapshotMemberOrigin.ADDED,
            )
            _insert_record(session, EvidenceSnapshotMemberRecord, member, {
                "member_id": "m-1",
                "snapshot_id": "snap-1",
                "logical_document_id": "log-1",
                "source_document_version_id": "doc-1",
                "origin": "added",
            })
            # 状态事件：staged -> processing -> ready -> active（active 用于证明不回填）
            status_events = [
                (1, "staged", "processing", "worker_start"),
                (2, "processing", "ready", "all_gates_passed"),
                (3, "ready", "active", "activate"),
            ]
            for seq, from_status, to_status, event in status_events:
                from app.domain.contracts.evidence_ingestion import (
                    EvidenceSnapshotStatusEvent,
                )

                status_event = EvidenceSnapshotStatusEvent(
                    snapshot_id="snap-1",
                    seq=seq,
                    from_status=from_status,
                    to_status=to_status,
                    event=event,
                    actor="tester",
                    reason=event,
                    created_at=fixed,
                )
                _insert_record(session, EvidenceSnapshotStatusEventRecord, status_event, {
                    "snapshot_id": "snap-1",
                    "seq": seq,
                    "from_status": from_status,
                    "to_status": to_status,
                    "event": event,
                    "actor": "tester",
                    "reason": event,
                })

            profile_sha = build_profile_fingerprint(
                extraction_route="vision_ocr",
                provider="omlx",
                model_id="GLM-OCR-bf16",
                model_revision="unknown",
                prompt_sha256=None,
                parser_version="v1",
                render_params_sha256=None,
                request_params_sha256=None,
                layout_parser_version="layout-v1",
                coordinate_transform_version="t/v1",
            )
            profile = OCRProfile(
                ocr_profile_id="profile-1",
                profile_sha256=profile_sha,
                extraction_route=ExtractionRoute.VISION_OCR,
                provider="omlx",
                model_id="GLM-OCR-bf16",
                model_revision="unknown",
                parser_version="v1",
                layout_parser_version="layout-v1",
                coordinate_transform_version="t/v1",
                created_at=fixed,
            )
            OCRProfileRepository(session).get_or_create(profile)
            artifact = PageArtifact(
                page_artifact_id="pa-1",
                source_document_version_id="doc-1",
                page_number=1,
                source_sha256=_SHA,
                page_input_sha256="b" * 64,
                page_image_sha256="b" * 64,
                page_width=595.0,
                page_height=842.0,
                rotation=0,
                renderer_version="renderer-1",
                decoder_version="decoder-1",
                derivative_sha256="d" * 64,
                coordinate_transform_version="t/v1",
                status=PageArtifactStatus.SUCCEEDED,
            )
            from app.storage.ocr_models import OCRPageRecord, PageArtifactRecord

            _insert_record(session, PageArtifactRecord, artifact, {
                "page_artifact_id": "pa-1",
                "source_document_version_id": "doc-1",
                "page_number": 1,
                "original_frame": None,
                "source_sha256": _SHA,
                "page_input_sha256": "b" * 64,
                "page_image_sha256": "b" * 64,
                "native_text_sha256": None,
                "native_coordinates_sha256": None,
                "page_width": 595.0,
                "page_height": 842.0,
                "rotation": 0,
                "renderer_version": "renderer-1",
                "decoder_version": "decoder-1",
                "derivative_sha256": "d" * 64,
                "coordinate_transform_version": "t/v1",
                "status": "succeeded",
                "failure_reason": None,
            })
            cache_key = ocr_page_cache_hash(
                source_sha256=_SHA,
                page_number=1,
                ocr_profile_sha256=profile_sha,
                page_input_sha256="b" * 64,
                layout_parser_version="layout-v1",
                coordinate_transform_version="t/v1",
            )
            page = OCRPage(
                ocr_page_id="op-1",
                page_artifact_id="pa-1",
                source_sha256=_SHA,
                page_number=1,
                page_input_sha256="b" * 64,
                ocr_profile_sha256=profile_sha,
                cache_key=cache_key,
                layout_parser_version="layout-v1",
                coordinate_transform_version="t/v1",
                raw_text="ALT 5.6 mmol/L",
                raw_text_sha256=hashlib.sha256(b"ALT 5.6 mmol/L").hexdigest(),
                normalized_text="ALT 5.6 mmol/L",
                quality=PageQualityMetrics(char_count=14, word_count=3),
                status="succeeded",
                started_at=fixed,
                completed_at=fixed,
            )
            _insert_record(session, OCRPageRecord, page, {
                "ocr_page_id": "op-1",
                "page_artifact_id": "pa-1",
                "source_sha256": _SHA,
                "page_number": 1,
                "page_input_sha256": "b" * 64,
                "ocr_profile_id": "profile-1",
                "ocr_profile_sha256": profile_sha,
                "cache_key": cache_key,
                "layout_parser_version": "layout-v1",
                "coordinate_transform_version": "t/v1",
                "raw_text": "ALT 5.6 mmol/L",
                "raw_text_sha256": hashlib.sha256(b"ALT 5.6 mmol/L").hexdigest(),
                "normalized_text": "ALT 5.6 mmol/L",
                "layout_sidecar_sha256": None,
                "quality_json": '{"char_count":14,"word_count":3,"confidence":null,"layout_block_count":null}',
                "risk_items_json": "[]",
                "status": "succeeded",
                "failure_reason": None,
                "started_at": fixed,
                "completed_at": fixed,
            })

            entry = EvidenceProcessingRevisionPage(
                entry_id="e1",
                position=1,
                source_document_version_id="doc-1",
                page_number=1,
                original_frame=None,
                page_artifact_id="pa-1",
                ocr_page_id="op-1",
                status=PageArtifactStatus.SUCCEEDED,
            )
            revision = EvidenceProcessingRevision(
                evidence_processing_revision_id="rev-1",
                evidence_snapshot_id="snap-1",
                project_id=project_id,
                subject_id=subject_id,
                review_episode_id=episode_id,
                manifest=[entry],
                manifest_sha256=evidence_processing_manifest_hash(
                    entries=[("doc-1", 1, None, "pa-1", "op-1", "succeeded")]
                ),
                status="ready",
                is_activatable=False,
                created_at=fixed,
                created_by="tester",
            )
            from app.storage.codecs import encode_contract, to_utc_naive

            rev_payload, rev_sha = encode_contract(revision)
            session.execute(
                sa.text(
                    "INSERT INTO evidence_processing_revisions ("
                    "evidence_processing_revision_id, evidence_snapshot_id, project_id, "
                    "subject_id, review_episode_id, manifest_sha256, status, "
                    "is_activatable, created_by, payload_json, payload_sha256, created_at) "
                    "VALUES (:rid, :snap, :project, :subject, :episode, :manifest, "
                    ":status, :activatable, :created_by, :payload, :payload_sha, :created_at)"
                ),
                {
                    "rid": "rev-1",
                    "snap": "snap-1",
                    "project": project_id,
                    "subject": subject_id,
                    "episode": episode_id,
                    "manifest": evidence_processing_manifest_hash(
                        entries=[("doc-1", 1, None, "pa-1", "op-1", "succeeded")]
                    ),
                    "status": "ready",
                    "activatable": False,
                    "created_by": "tester",
                    "payload": rev_payload,
                    "payload_sha": rev_sha,
                    "created_at": to_utc_naive(fixed),
                },
            )
            from app.storage.ocr_models import EvidenceProcessingRevisionPageRecord

            _insert_record(session, EvidenceProcessingRevisionPageRecord, entry, {
                "revision_id": "rev-1",
                "position": 1,
                "entry_id": "e1",
                "source_document_version_id": "doc-1",
                "page_number": 1,
                "original_frame": None,
                "page_artifact_id": "pa-1",
                "ocr_page_id": "op-1",
                "status": "succeeded",
                "failure_reason": None,
            })

            # 上传预览：直接 ORM 插入（避免预览仓储对 staged/摘要的额外校验）。
            preview_payload = json.dumps(
                {
                    "preview_id": "preview-1",
                    "project_id": project_id,
                    "subject_id": subject_id,
                    "review_episode_id": episode_id,
                    "upload_mode": "full",
                    "base_revision": 1,
                    "base_snapshot_id": None,
                    "status": "committed",
                    "preview_sha256": "e" * 64,
                    "items": [],
                    "created_at": "2026-08-19T12:00:00Z",
                    "created_by": "tester",
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
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
                    status="committed",
                    preview_sha256="e" * 64,
                    created_by="tester",
                    payload_json=preview_payload,
                    payload_sha256=hashlib.sha256(preview_payload.encode("utf-8")).hexdigest(),
                    created_at=sa.func.current_timestamp(),
                )
            )
            session.commit()
    finally:
        engine.dispose()
    return {
        "project_id": project_id,
        "subject_id": subject_id,
        "episode_id": episode_id,
    }


def _insert_record(session, record_cls, contract, columns) -> None:
    """用 canonical payload/hash + 规范化列直接写一条追加记录（绕过 episode scope 检查）。"""
    from app.storage.codecs import encode_contract, to_utc_naive

    payload_json, payload_sha256 = encode_contract(contract)
    created_at = getattr(contract, "created_at", None)
    session.add(
        record_cls(
            payload_json=payload_json,
            payload_sha256=payload_sha256,
            created_at=to_utc_naive(created_at) if created_at is not None else utc_now(),
            **columns,
        )
    )
    session.flush()


def utc_now():
    from app.storage.codecs import utc_now as _u

    return _u()


def _row_counts(engine) -> dict[str, int]:
    with engine.connect() as connection:
        return {
            name: connection.exec_driver_sql(
                f"SELECT COUNT(*) FROM {name}"
            ).scalar_one()
            for name in (
                "review_episodes",
                "evidence_upload_previews",
                "evidence_snapshots_v2",
                "evidence_snapshot_members",
                "evidence_snapshot_status_events",
                "source_blobs",
                "source_document_versions_v2",
                "ocr_profiles",
                "page_artifacts",
                "ocr_pages",
                "evidence_processing_revisions",
                "evidence_processing_revision_pages",
            )
        }


def _legacy_revision_rows(engine) -> list[tuple]:
    with engine.connect() as connection:
        return connection.exec_driver_sql(
            "SELECT evidence_processing_revision_id, payload_json, payload_sha256, "
            "manifest_sha256, is_activatable FROM evidence_processing_revisions "
            "ORDER BY evidence_processing_revision_id"
        ).fetchall()


def test_0010_upgrade_preserves_all_rows_payloads_hashes_and_integrity(data_paths):
    """0009 填充子表数据 -> 0010：行数/FK/payload/hash/WAL/integrity 前后一致。"""
    _seed_populated_0009(data_paths)
    engine = build_engine(data_paths.db_path)
    try:
        before_counts = _row_counts(engine)
        before_revisions = _legacy_revision_rows(engine)
        before_wal = _journal_mode(data_paths.db_path)
        with engine.connect() as connection:
            before_fk = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
        before_integrity = _integrity(data_paths.db_path)
        # 升级前指针列尚不存在；断言 ACTIVE 快照存在（用于证明不回填）。
        with engine.connect() as connection:
            active = connection.exec_driver_sql(
                "SELECT COUNT(*) FROM evidence_snapshot_status_events "
                "WHERE to_status = 'active'"
            ).scalar_one()
        assert active == 1
    finally:
        engine.dispose()

    manager = MigrationManager(data_paths)
    result = manager.upgrade("head")
    assert result.to_revision == resolve_head_revision()
    engine = build_engine(data_paths.db_path)
    try:
        assert _row_counts(engine) == before_counts
        assert _legacy_revision_rows(engine) == before_revisions
        assert _journal_mode(data_paths.db_path) == "wal" == before_wal
        assert _integrity(data_paths.db_path) == "ok" == before_integrity
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall() == before_fk
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
            # 活动指针不按历史 ACTIVE 状态回填，全部保持 NULL
            null_pointers = connection.exec_driver_sql(
                "SELECT COUNT(*) FROM review_episodes WHERE "
                "active_evidence_snapshot_id IS NULL AND "
                "active_evidence_processing_revision_id IS NULL"
            ).scalar_one()
            assert null_pointers == before_counts["review_episodes"]
            # 0009 行投影为 base 且不可激活
            kind_counts = connection.exec_driver_sql(
                "SELECT revision_kind, COUNT(*) FROM evidence_processing_revisions "
                "GROUP BY revision_kind"
            ).fetchall()
            assert kind_counts == [("base", 1)]
            assert connection.exec_driver_sql(
                "SELECT is_activatable FROM evidence_processing_revisions"
            ).scalar_one() == 0
        # 0010 旁路表全部存在且为空（无猜填）
        actual = set(sa.inspect(engine).get_table_names())
        assert SLICE44_TABLES <= actual
        for table_name in SLICE44_TABLES:
            with engine.connect() as connection:
                assert connection.exec_driver_sql(
                    f"SELECT COUNT(*) FROM {table_name}"
                ).scalar_one() == 0
    finally:
        engine.dispose()


def test_0010_schema_matches_metadata_at_head(data_paths):
    """升级到 0010 后 schema 与完整 ORM metadata 一致（含 review_episodes 指针列）。"""
    _seed_populated_0009(data_paths)
    manager = MigrationManager(data_paths)
    manager.upgrade("head")
    engine = build_engine(data_paths.db_path)
    try:
        problems = verify_schema_matches_metadata(engine, manager.metadata)
        assert problems == [], f"schema 与 metadata 不一致：{problems}"
    finally:
        engine.dispose()


def test_0010_paired_pointer_check_enforced(data_paths):
    """只设一个活动指针必须被数据库 CHECK 拒绝（成对约束兜底）。"""
    _seed_populated_0009(data_paths)
    MigrationManager(data_paths).upgrade("head")
    engine = build_engine(data_paths.db_path)
    try:
        with build_session_factory(engine)() as session:
            with pytest.raises(IntegrityError):
                session.execute(
                    sa.text(
                        "UPDATE review_episodes SET active_evidence_snapshot_id = 'snap-1' "
                        "WHERE review_episode_id = :episode"
                    ),
                    {"episode": _episode_id(data_paths)},
                )
            session.rollback()
    finally:
        engine.dispose()


def _episode_id(data_paths) -> str:
    engine = build_engine(data_paths.db_path)
    try:
        with engine.connect() as connection:
            return connection.exec_driver_sql(
                "SELECT review_episode_id FROM review_episodes"
            ).scalar_one()
    finally:
        engine.dispose()


def test_0010_pointer_foreign_keys_enforced(data_paths):
    """活动指针必须指向真实存在的快照/处理修订（外键拒绝悬空引用）。"""
    _seed_populated_0009(data_paths)
    MigrationManager(data_paths).upgrade("head")
    engine = build_engine(data_paths.db_path)
    try:
        with build_session_factory(engine)() as session:
            # 快照存在但处理修订不存在 → 外键拒绝（raw UPDATE 立即执行）
            with pytest.raises(IntegrityError):
                session.execute(
                    sa.text(
                        "UPDATE review_episodes SET active_evidence_snapshot_id = 'snap-1', "
                        "active_evidence_processing_revision_id = 'no-such-rev' "
                        "WHERE review_episode_id = :episode"
                    ),
                    {"episode": _episode_id(data_paths)},
                )
            session.rollback()
    finally:
        engine.dispose()


def test_0010_downgrade_refuses_slice44_history(data_paths):
    """含 0010 正式历史时有损降级必须拒绝并保留数据。"""
    ids = _seed_populated_0009(data_paths)
    manager = MigrationManager(data_paths)
    manager.upgrade("head")
    engine = build_engine(data_paths.db_path)
    try:
        from datetime import UTC, datetime

        from app.domain.contracts.enums import (
            ReferencedDocumentOrigin,
            ReferencedDocumentStatus,
        )
        from app.domain.contracts.evidence_locator import (
            ReferencedDocumentRevision,
        )
        from app.storage.evidence_locator_repositories import (
            ReferencedDocumentRepository,
        )

        with build_session_factory(engine)() as session:
            ReferencedDocumentRepository(session).create_revision(
                ReferencedDocumentRevision(
                    revision_id="refdoc-rev-1",
                    referenced_document_id="refdoc-1",
                    project_id=ids["project_id"],
                    subject_id=ids["subject_id"],
                    review_episode_id=ids["episode_id"],
                    description="资料中提及但尚未提供的既往检查报告",
                    origin=ReferencedDocumentOrigin.DETERMINISTIC_CANDIDATE,
                    status=ReferencedDocumentStatus.PROPOSED,
                    revision=1,
                    created_at=datetime(2026, 8, 19, 12, 0, 0, tzinfo=UTC),
                    created_by="tester",
                )
            )
            session.commit()
    finally:
        engine.dispose()

    with pytest.raises(MigrationFailure, match="拒绝有损降级"):
        manager.downgrade("0009")
    assert manager.read_revision(data_paths.db_path) == resolve_head_revision()
    engine = build_engine(data_paths.db_path)
    try:
        with engine.connect() as connection:
            assert connection.exec_driver_sql(
                "SELECT COUNT(*) FROM referenced_document_revisions"
            ).scalar_one() == 1
    finally:
        engine.dispose()


def test_0010_downgrade_refuses_pointer_or_complete_history(data_paths):
    """非空活动指针或 complete 修订同样拒绝降级。"""
    ids = _seed_populated_0009(data_paths)
    manager = MigrationManager(data_paths)
    manager.upgrade("head")
    engine = build_engine(data_paths.db_path)
    try:
        with build_session_factory(engine)() as session:
            session.execute(
                sa.text(
                    "UPDATE review_episodes SET active_evidence_snapshot_id = 'snap-1', "
                    "active_evidence_processing_revision_id = 'rev-1' "
                    "WHERE review_episode_id = :episode"
                ),
                {"episode": ids["episode_id"]},
            )
            session.commit()
    finally:
        engine.dispose()
    with pytest.raises(MigrationFailure, match="拒绝有损降级"):
        manager.downgrade("0009")
    assert manager.read_revision(data_paths.db_path) == resolve_head_revision()


def test_0010_empty_greenfield_downgrade_and_reupgrade(data_paths):
    """空绿地库允许 0010 -> 0009 降级并可再升级（无正式历史）。"""
    _upgrade_to_0007(data_paths)
    _seed_fixture(data_paths)
    MigrationManager(data_paths).upgrade("head")
    manager = MigrationManager(data_paths)
    result = manager.downgrade("0009")
    assert result.to_revision == "0009"
    engine = build_engine(data_paths.db_path)
    try:
        actual = set(sa.inspect(engine).get_table_names())
        assert not (SLICE44_TABLES & actual), "降级后 0010 表仍存在"
    finally:
        engine.dispose()
    MigrationManager(data_paths).upgrade("head")
    assert MigrationManager(data_paths).read_revision(data_paths.db_path) == resolve_head_revision()
