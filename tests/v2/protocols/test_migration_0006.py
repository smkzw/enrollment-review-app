"""Migration 0006 upgrade/downgrade coverage for slice 4."""
from __future__ import annotations

from datetime import datetime

import alembic
import pytest
from sqlalchemy import inspect, text

from app.storage.db import Base, build_engine, build_session_factory
from app.storage.migrate import (
    MigrationFailure,
    MigrationManager,
    verify_schema_matches_metadata,
)

_NOW = datetime(2026, 8, 17)


SLICE4_TABLES = {
    "protocol_draft_revisions",
    "evidence_expectation_templates",
}


def _add_legacy_requirement(session, requirement_id: str, component_id: str) -> None:
    """在 0005 形状下播种一条组件来源资料要求行。"""
    session.execute(
        text(
            "INSERT OR IGNORE INTO protocol_document_versions "
            "(protocol_version_id, protocol_code, official_version, "
            " official_date_value, official_date_precision, sha256, "
            " integrity_manifest_sha256, authority_record_sha256, "
            " authority_confirmation_id, authority_gate_result_id, "
            " integrity_gate_result_id, payload_json, payload_sha256, created_at) "
            "VALUES ('protocol-version-seed', 'TEST-001', 'V1.0', NULL, 'unknown', "
            " :ps, :ps, :ps, 'confirmation-seed', 'gate-seed', 'gate-seed-2', "
            " '{}', :ps, :ts)"
        ),
        {"ps": "0" * 64, "ts": _NOW},
    )
    session.execute(
        text(
            "INSERT OR IGNORE INTO rule_sets "
            "(rule_set_id, revision, protocol_version_id, study_phase, "
            " payload_json, payload_sha256, created_at) "
            "VALUES ('ruleset-a', 1, 'protocol-version-seed', 'phase_ii', "
            " '{}', :ps, :ts)"
        ),
        {"ps": "0" * 64, "ts": _NOW},
    )
    session.execute(
        text(
            "INSERT OR IGNORE INTO rules "
            "(rule_set_id, rule_set_revision, rule_id, official_code, kind, "
            " study_phase, payload_json, payload_sha256, created_at) "
            "VALUES ('ruleset-a', 1, 'rule-seed', 'IN-01', 'inclusion', "
            " 'phase_ii', '{}', :ps, :ts)"
        ),
        {"ps": "0" * 64, "ts": _NOW},
    )
    session.execute(
        text(
            "INSERT OR IGNORE INTO rule_components "
            "(rule_set_id, rule_set_revision, rule_component_id, parent_rule_id, "
            " display_code, title, expression_json, expression_sha256, "
            " payload_json, payload_sha256, created_at) "
            "VALUES ('ruleset-a', 1, :cid, 'rule-seed', 'IN-01a', '种子组件', "
            " '{}', :ps, '{}', :ps, :ts)"
        ),
        {"cid": component_id, "ps": "0" * 64, "ts": _NOW},
    )
    session.execute(
        text(
            "INSERT INTO evidence_requirements "
            "(rule_set_id, rule_set_revision, requirement_id, rule_component_id, "
            " fact_type, due_stage, payload_json, payload_sha256, created_at) "
            "VALUES (:rs, 1, :rid, :cid, :ft, :ds, :pj, :ps, :ts)"
        ),
        {
            "rs": "ruleset-a",
            "rid": requirement_id,
            "cid": component_id,
            "ft": "方案要求事实",
            "ds": "screening",
            "pj": "{}",
            "ps": "0" * 64,
            "ts": _NOW,
        },
    )


def _seed_0005_schema(data_paths) -> None:
    # MigrationManager.upgrade 会把 0005 与 head 的 ORM metadata 对比，
    # 直接验证会失败；这里用裸 alembic 建到 0005，只播种旧形状数据。
    import alembic.command as alembic_command

    from app.storage.migrate import DEFAULT_SCRIPT_LOCATION

    config = alembic.config.Config()
    config.set_main_option("script_location", str(DEFAULT_SCRIPT_LOCATION))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{data_paths.db_path}")
    data_paths.ensure_directories()
    alembic_command.upgrade(config, "0005")
    engine = build_engine(data_paths.db_path)
    try:
        from app.storage.db import build_session_factory

        with build_session_factory(engine)() as session:
            _add_legacy_requirement(session, "requirement:component:IN-01:01:01", "component-in")
            _add_legacy_requirement(session, "requirement:component:EX-01:01:01", "component-ex")
            session.commit()
    finally:
        engine.dispose()


def test_0006_upgrade_preserves_component_rows_and_adds_origin_columns(data_paths) -> None:
    _seed_0005_schema(data_paths)
    MigrationManager(data_paths).upgrade("head")
    engine = build_engine(data_paths.db_path)
    try:
        assert verify_schema_matches_metadata(engine, Base.metadata) == []
        inspector = inspect(engine)
        cols = {c["name"]: c["nullable"] for c in inspector.get_columns("evidence_requirements")}
        assert cols["rule_component_id"] is True
        assert cols["procedure_catalog_item_id"] is True
        assert "study_phase" in [c["name"] for c in inspector.get_columns("workflow_stages")]
        assert SLICE4_TABLES <= set(inspector.get_table_names())
        template_columns = {
            column["name"]: column for column in inspector.get_columns(
                "evidence_expectation_templates"
            )
        }
        assert template_columns["workflow_stage_id"]["nullable"] is False
        template_fks = inspector.get_foreign_keys("evidence_expectation_templates")
        fk_shapes = {
            (
                tuple(item["constrained_columns"]),
                item["referred_table"],
                tuple(item["referred_columns"]),
            )
            for item in template_fks
        }
        assert (
            ("rule_set_id", "rule_set_revision"),
            "rule_sets",
            ("rule_set_id", "revision"),
        ) in fk_shapes
        assert (
            ("rule_set_id", "rule_set_revision", "requirement_id"),
            "evidence_requirements",
            ("rule_set_id", "rule_set_revision", "requirement_id"),
        ) in fk_shapes
        assert (
            ("workflow_stage_id",),
            "workflow_stages",
            ("workflow_stage_id",),
        ) in fk_shapes
        from app.storage.db import build_session_factory

        with build_session_factory(engine)() as session:
            rows = session.execute(
                text(
                    "SELECT requirement_id, rule_component_id, procedure_catalog_item_id "
                    "FROM evidence_requirements ORDER BY requirement_id"
                )
            ).fetchall()
            assert len(rows) == 2
            assert all(row[1] is not None and row[2] is None for row in rows)
            # 引用表外键仍指向 evidence_requirements（未被 RENAME 改写）
            fks = inspector.get_foreign_keys("evidence_expectations")
            referred = {item["referred_table"] for item in fks}
            assert referred == {"evidence_requirements", "review_episodes"}
    finally:
        engine.dispose()


def test_0006_database_rejects_orphan_or_stage_less_template(data_paths) -> None:
    """绕过仓储直接写 SQL 时，数据库仍必须拒绝孤儿模板和空审核节点。"""
    from sqlalchemy.exc import IntegrityError

    MigrationManager(data_paths).upgrade("head")
    engine = build_engine(data_paths.db_path)
    try:
        with build_session_factory(engine)() as session:
            statement = text(
                "INSERT INTO evidence_expectation_templates "
                "(template_id, rule_set_id, rule_set_revision, requirement_id, "
                " due_stage, study_phase, workflow_stage_id, fact_type, "
                " required_source_types, projection_sha256, payload_json, "
                " payload_sha256, created_at) "
                "VALUES (:template_id, 'missing-ruleset', 1, 'missing-requirement', "
                " 'screening', 'phase_ii', :workflow_stage_id, '方案要求事实', "
                " '[]', :ps, '{}', :ps, :ts)"
            )
            with pytest.raises(IntegrityError):
                session.execute(
                    statement,
                    {
                        "template_id": "template:orphan",
                        "workflow_stage_id": "missing-stage",
                        "ps": "0" * 64,
                        "ts": _NOW,
                    },
                )
                session.commit()
            session.rollback()

            with pytest.raises(IntegrityError):
                session.execute(
                    statement,
                    {
                        "template_id": "template:no-stage",
                        "workflow_stage_id": None,
                        "ps": "0" * 64,
                        "ts": _NOW,
                    },
                )
                session.commit()
    finally:
        engine.dispose()


def test_0006_one_origin_check_rejects_both_origins(data_paths) -> None:
    MigrationManager(data_paths).upgrade("head")
    engine = build_engine(data_paths.db_path)
    try:
        from sqlalchemy.exc import IntegrityError
        from app.storage.db import build_session_factory

        with build_session_factory(engine)() as session:
            with pytest.raises(IntegrityError, match="CHECK"):
                session.execute(
                    text(
                        "INSERT INTO evidence_requirements "
                        "(rule_set_id, rule_set_revision, requirement_id, "
                        " rule_component_id, procedure_catalog_item_id, fact_type, "
                        " due_stage, payload_json, payload_sha256, created_at) "
                        "VALUES (:rs, 1, 'both', 'component-in', 'procedure:x', "
                        " 'f', 'screening', '{}', :ps, :ts)"
                    ),
                    {"rs": "ruleset-a", "ps": "0" * 64, "ts": _NOW},
                )
                session.commit()
    finally:
        engine.dispose()


def test_0006_upgrade_downgrade_upgrade_roundtrip(data_paths) -> None:
    manager = MigrationManager(data_paths)
    manager.upgrade("head")
    engine = build_engine(data_paths.db_path)
    try:
        assert SLICE4_TABLES <= set(inspect(engine).get_table_names())
        assert verify_schema_matches_metadata(engine, Base.metadata) == []
    finally:
        engine.dispose()

    manager.downgrade("0005")
    engine = build_engine(data_paths.db_path)
    try:
        inspector = inspect(engine)
        assert SLICE4_TABLES.isdisjoint(set(inspector.get_table_names()))
        cols = {c["name"] for c in inspector.get_columns("evidence_requirements")}
        assert "procedure_catalog_item_id" not in cols
        assert "study_phase" not in [c["name"] for c in inspector.get_columns("workflow_stages")]
    finally:
        engine.dispose()

    manager.upgrade("head")
    engine = build_engine(data_paths.db_path)
    try:
        assert SLICE4_TABLES <= set(inspect(engine).get_table_names())
        assert verify_schema_matches_metadata(engine, Base.metadata) == []
    finally:
        engine.dispose()


def _seed_episode_and_expectation(session) -> None:
    """在 0005 形状下播种 evidence_expectations 子行所需的最小 FK 链。"""
    session.execute(
        text(
            "INSERT OR IGNORE INTO projects "
            "(project_id, project_code, project_name, study_phase, "
            " protocol_version_id, rule_set_id, rule_set_revision, revision, "
            " created_at, updated_at, payload_json, payload_sha256) "
            "VALUES ('project-seed', 'TEST-001', '种子项目', 'phase_ii', "
            " 'protocol-version-seed', 'ruleset-a', 1, 1, :ts, :ts, '{}', :ps)"
        ),
        {"ps": "0" * 64, "ts": _NOW},
    )
    session.execute(
        text(
            "INSERT OR IGNORE INTO subjects "
            "(subject_id, subject_code, project_id, revision, "
            " created_at, updated_at, payload_json, payload_sha256) "
            "VALUES ('subject-seed', 'S-001', 'project-seed', 1, :ts, :ts, '{}', :ps)"
        ),
        {"ps": "0" * 64, "ts": _NOW},
    )
    session.execute(
        text(
            "INSERT OR IGNORE INTO evidence_snapshots "
            "(evidence_snapshot_id, subject_id, review_episode_id, upload_mode, "
            " payload_json, payload_sha256, created_at) "
            "VALUES ('snapshot-seed', 'subject-seed', 'episode-seed', 'full', "
            " '{}', :ps, :ts)"
        ),
        {"ps": "0" * 64, "ts": _NOW},
    )
    session.execute(
        text(
            "INSERT OR IGNORE INTO review_episodes "
            "(review_episode_id, subject_id, project_id, rule_set_id, "
            " rule_set_revision, study_phase, stage, protocol_version_id, "
            " evidence_snapshot_id, anchor_dates_json, revision, "
            " created_at, updated_at, payload_json, payload_sha256) "
            "VALUES ('episode-seed', 'subject-seed', 'project-seed', 'ruleset-a', "
            " 1, 'phase_ii', 'screening', 'protocol-version-seed', "
            " 'snapshot-seed', '{}', 1, :ts, :ts, '{}', :ps)"
        ),
        {"ps": "0" * 64, "ts": _NOW},
    )


def test_0006_upgrade_preserves_expectation_child_rows_and_fks(data_paths) -> None:
    """evidence_expectations 已有真实子行引用 evidence_requirements 时，
    升级必须保留子行与外键引用，不得损坏。"""
    _seed_0005_schema(data_paths)
    engine = build_engine(data_paths.db_path)
    try:
        from app.storage.db import build_session_factory

        with build_session_factory(engine)() as session:
            _seed_episode_and_expectation(session)
            session.execute(
                text(
                    "INSERT INTO evidence_expectations "
                    "(expectation_id, requirement_id, rule_set_id, rule_set_revision, "
                    " review_episode_id, status, revision, created_at, updated_at, "
                    " payload_json, payload_sha256) "
                    "VALUES ('expectation-seed', 'requirement:component:IN-01:01:01', "
                    " 'ruleset-a', 1, 'episode-seed', 'absent', 1, :ts, :ts, '{}', :ps)"
                ),
                {"ps": "0" * 64, "ts": _NOW},
            )
            session.commit()
    finally:
        engine.dispose()

    # 升级前子行存在；升级必须成功且保留子行与 FK。
    MigrationManager(data_paths).upgrade("head")
    engine = build_engine(data_paths.db_path)
    try:
        assert verify_schema_matches_metadata(engine, Base.metadata) == []
        from app.storage.db import build_session_factory

        with build_session_factory(engine)() as session:
            child = session.execute(
                text(
                    "SELECT expectation_id, requirement_id, rule_set_id, "
                    " rule_set_revision, review_episode_id "
                    "FROM evidence_expectations WHERE expectation_id = 'expectation-seed'"
                )
            ).fetchone()
            assert child is not None
            assert child[1] == "requirement:component:IN-01:01:01"
            # 升级后父行仍在且流程来源列为空（组件来源原样保留）
            parent = session.execute(
                text(
                    "SELECT rule_component_id, procedure_catalog_item_id "
                    "FROM evidence_requirements "
                    "WHERE requirement_id = 'requirement:component:IN-01:01:01'"
                )
            ).fetchone()
            assert parent[0] == "component-in"
            assert parent[1] is None
            # 外键引用仍指向 evidence_requirements（未被 RENAME 改写）
            fk_violations = session.execute(
                text("PRAGMA foreign_key_check")
            ).fetchall()
            assert fk_violations == []
    finally:
        engine.dispose()


def test_0006_downgrade_refuses_slice4_data_and_keeps_current(data_paths) -> None:
    """含 Slice 4 正式数据（流程来源行/草稿历史/模板/节点期别）时，
    降级必须显式拒绝而不是静默丢弃；拒绝后 0006 数据保持原样。"""
    MigrationManager(data_paths).upgrade("head")
    engine = build_engine(data_paths.db_path)
    try:
        from app.storage.db import build_session_factory

        with build_session_factory(engine)() as session:
            # 流程来源资料要求行与 episode 链的父行：方案版本 + RuleSet。
            session.execute(
                text(
                    "INSERT OR IGNORE INTO protocol_document_versions "
                    "(protocol_version_id, protocol_code, official_version, "
                    " official_date_value, official_date_precision, sha256, "
                    " integrity_manifest_sha256, authority_record_sha256, "
                    " authority_confirmation_id, authority_gate_result_id, "
                    " integrity_gate_result_id, payload_json, payload_sha256, "
                    " created_at) "
                    "VALUES ('protocol-version-seed', 'TEST-001', 'V1.0', NULL, "
                    " 'unknown', :ps, :ps, :ps, 'confirmation-seed', 'gate-seed', "
                    " 'gate-seed-2', '{}', :ps, :ts)"
                ),
                {"ps": "0" * 64, "ts": _NOW},
            )
            session.execute(
                text(
                    "INSERT OR IGNORE INTO rule_sets "
                    "(rule_set_id, revision, protocol_version_id, study_phase, "
                    " payload_json, payload_sha256, created_at) "
                    "VALUES ('ruleset-a', 1, 'protocol-version-seed', 'phase_ii', "
                    " '{}', :ps, :ts)"
                ),
                {"ps": "0" * 64, "ts": _NOW},
            )
            _seed_episode_and_expectation(session)
            session.execute(
                text(
                    "INSERT INTO evidence_requirements "
                    "(rule_set_id, rule_set_revision, requirement_id, "
                    " rule_component_id, procedure_catalog_item_id, fact_type, "
                    " due_stage, payload_json, payload_sha256, created_at) "
                    "VALUES (:rs, 1, 'procedure-req', NULL, 'procedure:x', "
                    " 'f', 'screening', '{}', :ps, :ts)"
                ),
                {"rs": "ruleset-a", "ps": "0" * 64, "ts": _NOW},
            )
            session.execute(
                text(
                    "INSERT INTO protocol_draft_revisions "
                    "(revision_id, draft_id, revision_number, project_id, "
                    " protocol_version_id, study_phase, status, reason, actor, "
                    " content_sha256, payload_json, payload_sha256, created_at) "
                    "VALUES ('rev-seed', 'draft-seed', 1, 'project-seed', "
                    " 'protocol-version-seed', 'phase_ii', 'saved', 'initial_save', "
                    " 'a', :ps, '{}', :ps, :ts)"
                ),
                {"ps": "0" * 64, "ts": _NOW},
            )
            session.commit()
    finally:
        engine.dispose()

    from app.storage.migrate import MigrationFailure

    # 有损降级被拒绝后，MigrationManager 包装中文失败信息并自动从备份恢复。
    with pytest.raises(MigrationFailure, match="数据库降级或降级后校验失败"):
        MigrationManager(data_paths).downgrade("0005")

    engine = build_engine(data_paths.db_path)
    try:
        # 拒绝后 0006 数据保持原样（MigrationManager 从迁移前备份恢复）
        assert "protocol_draft_revisions" in inspect(engine).get_table_names()
        from app.storage.db import build_session_factory

        with build_session_factory(engine)() as session:
            row = session.execute(
                text(
                    "SELECT procedure_catalog_item_id FROM evidence_requirements "
                    "WHERE requirement_id = 'procedure-req'"
                )
            ).fetchone()
            assert row is not None and row[0] == "procedure:x"
            draft_row = session.execute(
                text(
                    "SELECT revision_number FROM protocol_draft_revisions "
                    "WHERE revision_id = 'rev-seed'"
                )
            ).fetchone()
            assert draft_row is not None and draft_row[0] == 1
    finally:
        engine.dispose()


def test_0006_downgrade_allowed_without_slice4_data(data_paths) -> None:
    """无 Slice 4 正式数据时仍可降级（仅组件来源行的 0002 形状数据库）。"""
    _seed_0005_schema(data_paths)
    MigrationManager(data_paths).upgrade("head")
    MigrationManager(data_paths).downgrade("0005")
    engine = build_engine(data_paths.db_path)
    try:
        inspector = inspect(engine)
        assert SLICE4_TABLES.isdisjoint(set(inspector.get_table_names()))
        # 组件来源行在降级后保留（rule_component_id 非空）
        from app.storage.db import build_session_factory

        with build_session_factory(engine)() as session:
            rows = session.execute(
                text(
                    "SELECT requirement_id, rule_component_id "
                    "FROM evidence_requirements ORDER BY requirement_id"
                )
            ).fetchall()
            assert len(rows) == 2
            assert all(row[1] is not None for row in rows)
    finally:
        engine.dispose()
