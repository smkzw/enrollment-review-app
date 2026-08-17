"""Migration 0006 upgrade/downgrade coverage for slice 4."""
from __future__ import annotations

from datetime import datetime

import alembic
import pytest
from sqlalchemy import inspect, text

from app.storage.db import Base, build_engine
from app.storage.migrate import MigrationManager, verify_schema_matches_metadata

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
