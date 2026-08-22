"""Phase 4 迁移 0008：证据摄入表 升级/降级/备份 确定性测试（Slice 4.1，worker_03）。

覆盖 P4-AC12（数据完整性）：迁移前自动备份；迁移后 schema、外键、WAL、内容哈希
与镜像字段一致；旧项目数据在升级/降级/再升级全程只读保留。

策略：要达到 0007 状态，必须用「仅 Phase 3 表」的 metadata 建迁移管理器
（完整 ``Base.metadata`` 含 0008 的 6 张新表，0007 校验会报缺失）；随后用完整
metadata 的管理器升级到 head（0008），此时才生成迁移前备份并做全量校验。
降级不校验 metadata（migrate.py 约定）；仅空的 0008 证据表允许降级，含正式证据数据时
必须拒绝，以避免静默删除不可变历史。
"""
from __future__ import annotations

import hashlib
import json

import pytest
import sqlalchemy as sa
from sqlalchemy import MetaData
from sqlalchemy.exc import IntegrityError

from app.storage.db import build_engine, build_session_factory
from app.storage.evidence_models import (
    SourceBlobRecord,
    SourceDocumentVersionV2Record,
)
from app.storage.migrate import (
    MigrationFailure,
    MigrationManager,
    verify_schema_matches_metadata,
)
from app.storage.repositories import EpisodeRepository
from tests.v2.storage.test_repositories_roundtrip import FIXTURES

EVIDENCE_TABLES = frozenset(
    {
        "source_blobs",
        "source_document_versions_v2",
        "source_document_metadata_revisions",
        "evidence_snapshots_v2",
        "evidence_snapshot_members",
        "evidence_snapshot_status_events",
    }
)

#: 0008a 追加的上传预览三表；同样不属于 0007 的 Phase 3 schema。
EVIDENCE_UPLOAD_TABLES = frozenset(
    {
        "evidence_upload_previews",
        "evidence_upload_items",
        "evidence_upload_commits",
    }
)

#: 0009 追加的 OCR 工件/基础处理修订十表；同样不属于 0007 的 Phase 3 schema。
OCR_TABLES = frozenset(
    {
        "ocr_profiles",
        "page_artifacts",
        "raw_ocr_request_artifacts",
        "raw_ocr_response_artifacts",
        "ocr_pages",
        "ocr_runs",
        "ocr_attempts",
        "evidence_processing_revisions",
        "evidence_processing_revision_pages",
        "page_work_leases",
    }
)

#: 0010 追加的 Slice 4.4 旁路工件/事件/关联十七表；同样不属于 0007/0008a/0009 schema。
SLICE44_TABLES = frozenset(
    {
        "evidence_locator_artifacts",
        "ocr_risk_scans",
        "ocr_risk_flags",
        "ocr_risk_reviews",
        "correction_records",
        "referenced_document_revisions",
        "referenced_document_resolution_revisions",
        "evidence_activation_events",
        "evidence_processing_candidates",
        "evidence_processing_candidate_events",
        "processing_revision_locators",
        "processing_revision_risk_scans",
        "processing_revision_risk_reviews",
        "processing_revision_corrections",
        "processing_revision_metadata_revisions",
        "processing_revision_referenced_documents",
        "processing_revision_resolutions",
    }
)

#: 0010 给 review_episodes 追加的成对活动指针列；预 0010 目标必须剥离。
_SLICE44_EPISODE_POINTER_COLUMNS = frozenset(
    {"active_evidence_snapshot_id", "active_evidence_processing_revision_id"}
)

#: 0010 给 evidence_processing_revisions 追加的 base/complete 辨别列；预 0010 目标必须剥离。
_SLICE44_EPR_DISCRIMINATOR_COLUMNS = frozenset(
    {
        "revision_kind",
        "base_processing_revision_id",
        "producer_candidate_id",
        "candidate_input_sha256",
        "completion_manifest_sha256",
    }
)

#: 0012 追加的页级原子风险核对审计表；同样不属于 0007/0008a/0009/0010/0011 schema。
PAGE_REVIEW_TABLES = frozenset({"ocr_risk_page_reviews"})

#: 0013 追加的 Phase 5 v2 临床事实/Profile 表；同样不属于 0007-0012 任一 schema。
PHASE5_V2_TABLES = frozenset(
    {
        "fact_normalization_runs",
        "fact_normalization_calls",
        "fact_normalization_candidates",
        "fact_gate_results",
        "clinical_facts_v2",
        "clinical_events_v2",
        "medication_exposures_v2",
        "fact_evidence_locator_links",
        "event_fact_links",
        "exposure_fact_links",
        "clinical_conflict_groups_v2",
        "clinical_conflict_members_v2",
        "fact_rule_links_v2",
        "evidence_expectations_v2",
        "patient_profile_revisions_v2",
    }
)

#: 各表在预 0010 目标中必须剥离的 0010 列。
_SLICE44_STRIP_COLUMNS = {
    "review_episodes": _SLICE44_EPISODE_POINTER_COLUMNS,
    "evidence_processing_revisions": _SLICE44_EPR_DISCRIMINATOR_COLUMNS,
}


def _copy_table_without_slice44(table, target: MetaData):
    """复制单表；剥离 0010 新增列及其外键与索引，使预 0010 校验目标与 0007-0009 schema 一致。"""
    copied = table.to_metadata(target)
    strip = _SLICE44_STRIP_COLUMNS.get(copied.name, frozenset())
    if copied.name == "evidence_processing_revisions":
        for index in [i for i in copied.indexes if i.name == "ix_epr_revision_kind"]:
            copied.indexes.remove(index)
        for constraint in list(copied.constraints):
            if any(column.name in strip for column in constraint.columns):
                copied.constraints.remove(constraint)
    for column in [c for c in copied.columns if c.name in strip]:
        copied._columns.remove(column)
        for fk in list(copied.foreign_keys):
            if fk.parent is column:
                copied.foreign_keys.remove(fk)
    if copied.name == "review_episodes":
        # 0011 形状（可空 workflow_stage_id + 可空 evidence_snapshot_id）只在
        # 0011 及以后存在；预 0011 校验目标保持 0010 形状：去掉 workflow_stage_id
        # 列与其外键，evidence_snapshot_id 恢复 NOT NULL。
        for column in [c for c in copied.columns if c.name == "workflow_stage_id"]:
            copied._columns.remove(column)
            for fk in list(copied.foreign_keys):
                if fk.parent is column:
                    copied.foreign_keys.remove(fk)
        for column in copied.columns:
            if column.name == "evidence_snapshot_id":
                column.nullable = False
    return copied


def _phase3_metadata() -> MetaData:
    """复制 Phase 3 表（排除 0008/0008a/0009/0010/0012/0013 的全部 Phase 4/5 表）作为 0007 校验目标。"""
    from app.storage.db import Base

    excluded = (
        EVIDENCE_TABLES
        | EVIDENCE_UPLOAD_TABLES
        | OCR_TABLES
        | SLICE44_TABLES
        | PAGE_REVIEW_TABLES
        | PHASE5_V2_TABLES
    )
    target = MetaData()
    for name, table in Base.metadata.tables.items():
        if name not in excluded:
            _copy_table_without_slice44(table, target)
    return target


def _metadata_without_ocr() -> MetaData:
    """复制 Phase 3 + 0008 + 0008a 表（排除 0009/0010/0012/0013 表）作为 0008a 校验目标。"""
    from app.storage.db import Base

    target = MetaData()
    for name, table in Base.metadata.tables.items():
        if name not in OCR_TABLES | SLICE44_TABLES | PAGE_REVIEW_TABLES | PHASE5_V2_TABLES:
            _copy_table_without_slice44(table, target)
    return target


def _metadata_without_slice44() -> MetaData:
    """复制 Phase 3 + 0008 + 0008a + 0009 表（排除 0010/0012/0013 表）作为 0009 校验目标。"""
    from app.storage.db import Base

    target = MetaData()
    for name, table in Base.metadata.tables.items():
        if name not in SLICE44_TABLES | PAGE_REVIEW_TABLES | PHASE5_V2_TABLES:
            _copy_table_without_slice44(table, target)
    return target


def _upgrade_to_0007(data_paths) -> None:
    """以仅 Phase 3 的 metadata 升到 0007（此时 metadata 校验通过）。"""
    MigrationManager(data_paths, metadata=_phase3_metadata()).upgrade("0007")


def _legacy_episode_save(self, episode) -> None:
    """预 0010 schema（0007/0008a/0009）下用 legacy 列写入 review_episodes。

    0010 之前 review_episodes 没有成对活动指针列，而 ORM 的 INSERT 总是包含全部
    mapped 列；播种 fixture 时把 EpisodeRepository.save 替换为本实现，payload 仍
    完整编码（指针为 None），读取端用 ``payload.get`` 兼容旧 payload。
    """
    from app.storage.codecs import encode_contract, parse_datetime_column, utc_now

    payload_json, payload_sha256 = encode_contract(episode)
    payload = json.loads(payload_json)
    self.session.execute(
        sa.text(
            "INSERT INTO review_episodes (review_episode_id, subject_id, project_id, "
            "rule_set_id, rule_set_revision, study_phase, stage, protocol_version_id, "
            "evidence_snapshot_id, anchor_dates_json, due_at, revision, created_at, "
            "updated_at, payload_json, payload_sha256) "
            "VALUES (:review_episode_id, :subject_id, :project_id, :rule_set_id, "
            ":rule_set_revision, :study_phase, :stage, :protocol_version_id, "
            ":evidence_snapshot_id, :anchor_dates_json, :due_at, :revision, :created_at, "
            ":updated_at, :payload_json, :payload_sha256)"
        ),
        {
            "review_episode_id": payload["review_episode_id"],
            "subject_id": payload["subject_id"],
            "project_id": payload["project_id"],
            "rule_set_id": payload["rule_set_id"],
            "rule_set_revision": payload["rule_set_revision"],
            "study_phase": payload["study_phase"],
            "stage": payload["stage"],
            "protocol_version_id": payload["protocol_version_id"],
            "evidence_snapshot_id": payload["evidence_snapshot_id"],
            "anchor_dates_json": json.dumps(
                payload["anchor_dates"], ensure_ascii=False, sort_keys=True
            ),
            "due_at": (
                parse_datetime_column(payload["due_at"]) if payload.get("due_at") else None
            ),
            "revision": payload["revision"],
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "payload_json": payload_json,
            "payload_sha256": payload_sha256,
        },
    )


def _legacy_snapshot_save(session, snapshot) -> None:
    """预 0010 schema 下用 legacy 列写入 Phase 3 evidence_snapshots（不走 ORM scope 检查）。"""
    from app.storage.codecs import encode_contract, to_utc_naive

    payload_json, payload_sha256 = encode_contract(snapshot)
    session.execute(
        sa.text(
            "INSERT INTO evidence_snapshots (evidence_snapshot_id, subject_id, "
            "review_episode_id, upload_mode, prior_snapshot_id, payload_json, "
            "payload_sha256, created_at) VALUES (:evidence_snapshot_id, :subject_id, "
            ":review_episode_id, :upload_mode, :prior_snapshot_id, :payload_json, "
            ":payload_sha256, :created_at)"
        ),
        {
            "evidence_snapshot_id": snapshot.evidence_snapshot_id,
            "subject_id": snapshot.subject_id,
            "review_episode_id": snapshot.review_episode_id,
            "upload_mode": (
                snapshot.upload_mode.value
                if hasattr(snapshot.upload_mode, "value")
                else snapshot.upload_mode
            ),
            "prior_snapshot_id": snapshot.prior_snapshot_id,
            "payload_json": payload_json,
            "payload_sha256": payload_sha256,
            "created_at": to_utc_naive(snapshot.created_at),
        },
    )


def _seed_fixture(data_paths) -> tuple[str, str, str]:
    """在预 0010 状态播种 fixture 的最小作用域集（project/subject/episode）。

    0010 之后 ORM 的 ``review_episodes`` 含活动指针列，无法写入/读取 0007-0009 的
    legacy 形状，因此不走 ``persist_fixture``（其 scope 检查会 SELECT 审核节点）；
    改为复刻 persist_fixture 前五步（协议/规则/项目/受试者，均不读审核节点）再以
    ``_legacy_episode_save`` 写入审核节点。迁移测试只读 projects/subjects/
    review_episodes/source_blobs，不需要 fixture 的 facts/runs/spans 等实体。
    """
    from app.storage.repositories import (
        PROTOCOL_DOC_CONFIG,
        AppendRepository,
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
        _legacy_episode_save(
            EpisodeRepository(session), fixture.review_episode
        )
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


def test_0008_upgrade_creates_exact_tables_matching_metadata(data_paths):
    """升级到 0008a 后全部 Phase 4 证据表存在且 schema 与 metadata 一致。"""
    _upgrade_to_0007(data_paths)
    manager = MigrationManager(data_paths, metadata=_metadata_without_ocr())
    result = manager.upgrade("0008a")
    assert result.to_revision == "0008a"
    engine = build_engine(data_paths.db_path)
    try:
        problems = verify_schema_matches_metadata(engine, manager.metadata)
        assert problems == [], f"schema 与 metadata 不一致：{problems}"
        inspector = sa.inspect(engine)
        actual = set(inspector.get_table_names())
        assert EVIDENCE_TABLES | EVIDENCE_UPLOAD_TABLES <= actual
        with engine.connect() as connection:
            violations = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
        assert violations == []
    finally:
        engine.dispose()


def test_0008_backup_created_before_upgrade_preserves_data(data_paths):
    _upgrade_to_0007(data_paths)
    project_id, subject_id, episode_id = _seed_fixture(data_paths)
    manager = MigrationManager(data_paths)
    before = sorted(p.name for p in data_paths.backups_dir.glob("*.sqlite3"))
    result = manager.upgrade("head")
    backups = sorted(p for p in data_paths.backups_dir.glob("*.sqlite3"))
    assert len(backups) == len(before) + 1
    record = result.backup
    assert record is not None
    assert record.source_revision == "0007"
    assert record.integrity == "ok"
    engine = build_engine(data_paths.db_path)
    try:
        # 升级到 0008 后，旧项目数据只读保留。
        with engine.connect() as connection:
            rows = connection.exec_driver_sql(
                "SELECT project_id FROM projects"
            ).fetchall()
            assert [r[0] for r in rows] == [project_id]
            rows = connection.exec_driver_sql(
                "SELECT subject_id FROM subjects"
            ).fetchall()
            assert [r[0] for r in rows] == [subject_id]
            rows = connection.exec_driver_sql(
                "SELECT review_episode_id FROM review_episodes"
            ).fetchall()
            assert [r[0] for r in rows] == [episode_id]
    finally:
        engine.dispose()
    # 备份清单与文件 SHA-256 一致，可被 restore 接受，且备份里保留了 0007 数据。
    manager.restore(record.path)
    restored = MigrationManager(data_paths)
    assert restored.read_revision(data_paths.db_path) == "0007"
    engine = build_engine(data_paths.db_path)
    try:
        with engine.connect() as connection:
            assert connection.exec_driver_sql(
                "SELECT project_id FROM projects"
            ).scalar_one() == project_id
            assert connection.exec_driver_sql(
                "SELECT subject_id FROM subjects"
            ).scalar_one() == subject_id
    finally:
        engine.dispose()


def test_0008_downgrade_drops_tables_and_preserves_data(data_paths):
    _upgrade_to_0007(data_paths)
    project_id, subject_id, _episode_id = _seed_fixture(data_paths)
    MigrationManager(data_paths).upgrade("head")
    manager = MigrationManager(data_paths)
    result = manager.downgrade("0007")
    assert result.to_revision == "0007"
    engine = build_engine(data_paths.db_path)
    try:
        inspector = sa.inspect(engine)
        actual = set(inspector.get_table_names())
        assert not (EVIDENCE_TABLES & actual), "降级后 0008 表仍存在"
        with engine.connect() as connection:
            rows = connection.exec_driver_sql(
                "SELECT project_id FROM projects"
            ).fetchall()
            assert [r[0] for r in rows] == [project_id]
            rows = connection.exec_driver_sql(
                "SELECT subject_id FROM subjects"
            ).fetchall()
            assert [r[0] for r in rows] == [subject_id]
    finally:
        engine.dispose()


def test_0008_downgrade_refuses_evidence_data_loss(data_paths):
    """已有不可变证据时，降级必须失败并由管理器恢复备份。"""
    _upgrade_to_0007(data_paths)
    manager = MigrationManager(data_paths, metadata=_metadata_without_ocr())
    manager.upgrade("0008a")
    engine = build_engine(data_paths.db_path)
    factory = build_session_factory(engine)
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
    with factory() as session:
        session.add(
            SourceBlobRecord(
                source_blob_id=digest,
                sha256=digest,
                byte_size=1,
                media_type="application/pdf",
                storage_ref=f"blobs/{digest}",
                payload_json=payload,
                payload_sha256=hashlib.sha256(payload.encode("utf-8")).hexdigest(),
                created_at=sa.func.current_timestamp(),
            )
        )
        session.commit()
    engine.dispose()

    with pytest.raises(MigrationFailure, match="拒绝降级"):
        manager.downgrade("0007")

    assert manager.read_revision(data_paths.db_path) == "0008a"
    engine = build_engine(data_paths.db_path)
    try:
        with engine.connect() as connection:
            assert connection.exec_driver_sql(
                "SELECT COUNT(*) FROM source_blobs"
            ).scalar_one() == 1
    finally:
        engine.dispose()


def test_0008_upgrade_downgrade_upgrade_cycle_preserves_data(data_paths):
    _upgrade_to_0007(data_paths)
    project_id, subject_id, episode_id = _seed_fixture(data_paths)
    MigrationManager(data_paths).upgrade("head")
    MigrationManager(data_paths).downgrade("0007")
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
    finally:
        engine.dispose()


def test_0008_wal_mode_and_foreign_keys_active_after_upgrade(data_paths):
    MigrationManager(data_paths).upgrade("head")
    assert _journal_mode(data_paths.db_path) == "wal"
    engine = build_engine(data_paths.db_path)
    try:
        with engine.connect() as connection:
            fk = connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one()
            assert fk == 1
    finally:
        engine.dispose()


def test_0008_new_tables_enforce_foreign_keys(data_paths):
    MigrationManager(data_paths).upgrade("head")
    engine = build_engine(data_paths.db_path)
    factory = build_session_factory(engine)
    try:
        with factory() as session:
            row = SourceDocumentVersionV2Record(
                source_document_version_id="bogus-version",
                logical_document_id="logical-1",
                source_blob_sha256="a" * 64,  # 指向不存在的 blob -> 外键拒绝
                file_name="report.pdf",
                media_type="application/pdf",
                page_count=1,
                project_id="missing-project",
                subject_id="missing-subject",
                review_episode_id="missing-episode",
                version_number=1,
                supersedes_version_id=None,
                created_by="tester",
                payload_json="{}",
                payload_sha256="b" * 64,
                created_at=sa.func.current_timestamp(),
            )
            session.add(row)
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
        # 有效 blob 可写，且外键检查无残留违规。
        with factory() as session:
            session.add(
                SourceBlobRecord(
                    source_blob_id="ok-blob",
                    sha256="a" * 64,
                    byte_size=1,
                    media_type="application/pdf",
                    storage_ref="blobs/ok",
                    payload_json="{}",
                    payload_sha256="b" * 64,
                    created_at=sa.func.current_timestamp(),
                )
            )
            session.commit()
        with engine.connect() as connection:
            violations = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
            assert violations == []
    finally:
        engine.dispose()


def test_0008_payload_hash_matches_content_and_mirrors(data_paths):
    """追加写记录：payload_sha256 必须等于 payload_json 的 SHA-256；镜像列一致。"""
    import hashlib

    MigrationManager(data_paths).upgrade("head")
    engine = build_engine(data_paths.db_path)
    factory = build_session_factory(engine)
    try:
        payload = json.dumps(
            {
                "source_blob_id": "mirror-1",
                "sha256": "c" * 64,
                "byte_size": 5,
                "media_type": "application/pdf",
                "storage_ref": "blobs/mirror",
                "created_at": "2026-08-19T12:00:00Z",
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        with factory() as session:
            session.add(
                SourceBlobRecord(
                    source_blob_id="mirror-1",
                    sha256="c" * 64,
                    byte_size=5,
                    media_type="application/pdf",
                    storage_ref="blobs/mirror",
                    payload_json=payload,
                    payload_sha256=digest,
                    created_at=sa.func.current_timestamp(),
                )
            )
            session.commit()
        with factory() as session:
            row = session.get(SourceBlobRecord, "mirror-1")
            assert row is not None
            assert row.payload_sha256 == digest
            assert row.sha256 == "c" * 64
            assert row.byte_size == 5
            assert row.media_type == "application/pdf"
            assert row.storage_ref == "blobs/mirror"
    finally:
        engine.dispose()
