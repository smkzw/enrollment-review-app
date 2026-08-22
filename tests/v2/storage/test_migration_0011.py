"""Phase 4 迁移 0011：审核节点流程节点身份 + 可空 legacy 快照 升级/降级/数据完整性 确定性测试。

覆盖 P4-AC12（数据完整性）与 0010 -> 0011 无损升级：

1. 从「填充了 legacy 审核节点数据的 0007 库」直接升级当前 head：legacy 行
   ``evidence_snapshot_id`` 原样保留、``workflow_stage_id`` 全部 NULL、
   payload/hash 与 fixture 合同逐字一致，WAL / ``PRAGMA foreign_key_check`` /
   ``integrity_check`` 通过；
2. 升级后 schema 与 ORM metadata 完全一致（``evidence_snapshot_id`` 可空、
   ``workflow_stage_id`` 可空且带 FK 到 ``workflow_stages``）；
3. 含自动建立的新式空节点（``workflow_stage_id`` 非空或 ``evidence_snapshot_id``
   为空）时有损降级必须拒绝并保留数据；
4. 仅 legacy 数据的库允许 0011 -> 0010 降级（列形状回到 0010），并可再升级至当前 head。
"""
from __future__ import annotations

import pytest
import sqlalchemy as sa

from app.storage.codecs import encode_contract
from app.storage.db import build_engine
from app.storage.migrate import (
    MigrationFailure,
    MigrationManager,
    resolve_head_revision,
    verify_schema_matches_metadata,
)
from tests.v2.storage.test_migration_0008 import (
    _journal_mode,
    _seed_fixture,
    _upgrade_to_0007,
)
from tests.v2.storage.test_repositories_roundtrip import FIXTURES


def _integrity(db_path: str) -> str:
    connection = sa.create_engine(f"sqlite:///{db_path}").connect()
    try:
        return str(connection.exec_driver_sql("PRAGMA integrity_check").scalar_one())
    finally:
        connection.close()


def _episode_rows(engine) -> list[tuple]:
    with engine.connect() as connection:
        return connection.exec_driver_sql(
            "SELECT review_episode_id, evidence_snapshot_id, workflow_stage_id, "
            "payload_json, payload_sha256 "
            "FROM review_episodes ORDER BY review_episode_id"
        ).fetchall()


def test_0011_upgrade_preserves_legacy_episodes_and_adds_null_stage(data_paths) -> None:
    _upgrade_to_0007(data_paths)
    _seed_fixture(data_paths)

    manager = MigrationManager(data_paths)
    result = manager.upgrade("head")
    assert result.to_revision == resolve_head_revision()
    engine = build_engine(data_paths.db_path)
    try:
        problems = verify_schema_matches_metadata(engine, manager.metadata)
        assert problems == [], f"schema 与 metadata 不一致：{problems}"

        rows = _episode_rows(engine)
        assert len(rows) == 1
        episode_id, snapshot_id, stage_id, payload_json, payload_sha256 = rows[0]
        fixture = FIXTURES[0]
        assert episode_id == fixture.review_episode.review_episode_id
        # legacy 快照原义保留，不为自动节点伪造占位。
        assert snapshot_id == fixture.review_episode.evidence_snapshot_id
        # 升级不推断流程节点身份：既有行保持 NULL。
        assert stage_id is None
        expected_json, expected_sha = encode_contract(fixture.review_episode)
        assert payload_json == expected_json
        assert payload_sha256 == expected_sha

        assert _journal_mode(data_paths.db_path) == "wal"
        assert _integrity(data_paths.db_path) == "ok"
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall() == []
            # 0011 列形状：evidence_snapshot_id 可空，workflow_stage_id 可空。
            inspector = sa.inspect(engine)
            columns = {c["name"]: c for c in inspector.get_columns("review_episodes")}
            assert columns["evidence_snapshot_id"]["nullable"] is True
            assert columns["workflow_stage_id"]["nullable"] is True
    finally:
        engine.dispose()


def test_0011_downgrade_refuses_new_empty_episodes(data_paths) -> None:
    """自动建立的空节点（无 legacy 快照 / 有流程节点身份）时降级必须拒绝。"""
    _upgrade_to_0007(data_paths)
    _seed_fixture(data_paths)
    MigrationManager(data_paths).upgrade("head")
    engine = build_engine(data_paths.db_path)
    try:
        with engine.connect() as connection:
            # 先建立被引用的发布流程节点，使 workflow_stage_id 外键可满足。
            connection.exec_driver_sql(
                "INSERT INTO workflow_stages "
                "(workflow_stage_id, protocol_version_id, stage, payload_json, "
                "payload_sha256, created_at) "
                "SELECT 'ruleset:1:stage-screening', protocol_version_id, "
                "'screening', payload_json, payload_sha256, created_at "
                "FROM review_episodes LIMIT 1"
            )
            # 复制一条 legacy 行并改写为新式空节点形状（workflow_stage_id 非空、
            # evidence_snapshot_id 为空）——与自动创建受试者产生的节点一致。
            connection.exec_driver_sql(
                "INSERT INTO review_episodes "
                "(review_episode_id, subject_id, project_id, rule_set_id, "
                "rule_set_revision, study_phase, stage, protocol_version_id, "
                "evidence_snapshot_id, workflow_stage_id, active_evidence_snapshot_id, "
                "active_evidence_processing_revision_id, anchor_dates_json, due_at, "
                "revision, created_at, updated_at, payload_json, payload_sha256) "
                "SELECT 'episode-auto-empty', subject_id, project_id, rule_set_id, "
                "rule_set_revision, study_phase, stage, protocol_version_id, NULL, "
                "'ruleset:1:stage-screening', NULL, NULL, anchor_dates_json, NULL, "
                "revision, created_at, updated_at, payload_json, payload_sha256 "
                "FROM review_episodes LIMIT 1"
            )
            connection.commit()
    finally:
        engine.dispose()

    with pytest.raises(MigrationFailure, match="拒绝有损降级"):
        MigrationManager(data_paths).downgrade("0010")
    # 数据保留：新式空节点仍在库中，未静默丢弃。
    engine = build_engine(data_paths.db_path)
    try:
        rows = _episode_rows(engine)
        assert any(row[0] == "episode-auto-empty" for row in rows)
    finally:
        engine.dispose()


def test_0011_legacy_only_downgrade_and_reupgrade(data_paths) -> None:
    """仅 legacy 数据（快照非空、节点身份为空）允许 0011 -> 0010 并可再升级。"""
    _upgrade_to_0007(data_paths)
    _seed_fixture(data_paths)
    manager = MigrationManager(data_paths)
    manager.upgrade("head")

    result = manager.downgrade("0010")
    assert result.to_revision == "0010"
    engine = build_engine(data_paths.db_path)
    try:
        inspector = sa.inspect(engine)
        columns = {c["name"]: c for c in inspector.get_columns("review_episodes")}
        assert "workflow_stage_id" not in columns
        assert columns["evidence_snapshot_id"]["nullable"] is False
        with engine.connect() as connection:
            rows = connection.exec_driver_sql(
                "SELECT review_episode_id, evidence_snapshot_id, payload_json, "
                "payload_sha256 FROM review_episodes ORDER BY review_episode_id"
            ).fetchall()
        assert len(rows) == 1
        assert rows[0][1] == FIXTURES[0].review_episode.evidence_snapshot_id
    finally:
        engine.dispose()

    MigrationManager(data_paths).upgrade("head")
    assert MigrationManager(data_paths).read_revision(data_paths.db_path) == resolve_head_revision()
