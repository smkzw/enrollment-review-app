"""0002 领域 schema：迁移生命周期、PRAGMA 合同与外键/唯一约束执行。"""
from __future__ import annotations

import pytest
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
import alembic.command

import app.storage.models  # noqa: 注册全部 ORM 表
from app.storage.db import Base, check_engine_pragmas, EXPECTED_PRAGMAS
from app.storage.migrate import verify_schema_matches_metadata
from app.storage.models import (
    ProjectRecord,
    ProtocolDocumentVersionRecord,
    RuleSetRecord,
    SubjectRecord,
)


def _alembic_config(db_path):
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    config.set_main_option("script_location", "app/storage/migrations")
    return config


def test_domain_schema_matches_metadata(data_paths, migrated_engine) -> None:
    problems = verify_schema_matches_metadata(migrated_engine, Base.metadata)
    assert problems == []


def test_all_domain_tables_exist(migrated_engine) -> None:
    tables = set(inspect(migrated_engine).get_table_names())
    expected = set(Base.metadata.tables)
    assert expected <= tables
    for name in (
        "projects",
        "subjects",
        "review_episodes",
        "rule_sets",
        "rules",
        "rule_components",
        "evidence_requirements",
        "evidence_snapshots",
        "evidence_spans",
        "clinical_facts",
        "review_runs",
        "final_assessments",
        "action_requests",
        "action_transitions",
        "agent_calls",
        "gate_results",
        "jobs",
        "job_steps",
        "job_checkpoints",
        "job_events",
        "entity_staleness",
        "idempotency_records",
    ):
        assert name in tables


def test_downgrade_and_reupgrade_roundtrip(data_paths, migrated_engine) -> None:
    config = _alembic_config(data_paths.db_path)
    alembic.command.downgrade(config, "0001")
    assert set(inspect(migrated_engine).get_table_names()) == {"alembic_version"}
    alembic.command.upgrade(config, "head")
    assert verify_schema_matches_metadata(migrated_engine, Base.metadata) == []


def test_pragma_contract_holds_on_migrated_engine(migrated_engine) -> None:
    actual = check_engine_pragmas(migrated_engine)
    assert actual == EXPECTED_PRAGMAS


def test_foreign_key_rejects_orphan_subject(migrated_engine, session_factory) -> None:
    with session_factory() as session:
        session.add(
            SubjectRecord(
                subject_id="orphan-subject",
                subject_code="O-1",
                project_id="project-not-exists",
                payload_json="{}",
                payload_sha256="0" * 64,
                revision=1,
                created_at=__import__("datetime").datetime(2026, 8, 14),
                updated_at=__import__("datetime").datetime(2026, 8, 14),
            )
        )
        with pytest.raises(IntegrityError, match="FOREIGN KEY"):
            session.commit()


def test_duplicate_primary_key_is_rejected(migrated_engine, session_factory) -> None:
    with session_factory() as session:
        session.add(
            ProtocolDocumentVersionRecord(
                protocol_version_id="protocol-x",
                protocol_code="X",
                official_version="v1",
                official_date_value=None,
                official_date_precision="unknown",
                sha256="a" * 64,
                integrity_manifest_sha256="b" * 64,
                authority_record_sha256="c" * 64,
                authority_confirmation_id="c1",
                authority_gate_result_id="g1",
                integrity_gate_result_id="g2",
                payload_json="{}",
                payload_sha256="0" * 64,
                created_at=__import__("datetime").datetime(2026, 8, 14),
            )
        )
        session.commit()
    with session_factory() as session:
        session.add(
            ProtocolDocumentVersionRecord(
                protocol_version_id="protocol-x",
                protocol_code="X",
                official_version="v1",
                official_date_value=None,
                official_date_precision="unknown",
                sha256="a" * 64,
                integrity_manifest_sha256="b" * 64,
                authority_record_sha256="c" * 64,
                authority_confirmation_id="c1",
                authority_gate_result_id="g1",
                integrity_gate_result_id="g2",
                payload_json="{}",
                payload_sha256="0" * 64,
                created_at=__import__("datetime").datetime(2026, 8, 14),
            )
        )
        with pytest.raises(IntegrityError, match="UNIQUE"):
            session.commit()


def test_rule_set_revision_unique_constraint(data_paths, migrated_engine, session_factory) -> None:
    row = dict(
        protocol_version_id="protocol-x",
        study_phase="phase_iii",
        payload_json="{}",
        payload_sha256="0" * 64,
        created_at=__import__("datetime").datetime(2026, 8, 14),
    )
    with session_factory() as session:
        session.add(
            ProtocolDocumentVersionRecord(
                protocol_version_id="protocol-x",
                protocol_code="X",
                official_version="v1",
                official_date_value=None,
                official_date_precision="unknown",
                sha256="a" * 64,
                integrity_manifest_sha256="b" * 64,
                authority_record_sha256="c" * 64,
                authority_confirmation_id="c1",
                authority_gate_result_id="g1",
                integrity_gate_result_id="g2",
                payload_json="{}",
                payload_sha256="0" * 64,
                created_at=__import__("datetime").datetime(2026, 8, 14),
            )
        )
        session.add(RuleSetRecord(rule_set_id="rs", revision=1, **row))
        session.add(RuleSetRecord(rule_set_id="rs", revision=2, **row))
        session.commit()
    with session_factory() as session:
        session.add(RuleSetRecord(rule_set_id="rs", revision=2, **row))
        with pytest.raises(IntegrityError, match="UNIQUE"):
            session.commit()


def test_episode_snapshot_cycle_allowed_in_one_transaction(
    data_paths, migrated_engine, session_factory
) -> None:
    """episode <-> snapshot 双向外键均为 DEFERRED：同一事务内双向引用可提交。"""
    from app.storage.models import EvidenceSnapshotRecord, ReviewEpisodeRecord

    now = __import__("datetime").datetime(2026, 8, 14)

    def flush_add(session, record) -> None:
        # 仓储按实体 flush；此处镜像该行为，避免无 relationship 的 ORM 批量插入顺序问题
        session.add(record)
        session.flush()

    with session_factory() as session:
        flush_add(session, ProtocolDocumentVersionRecord(
            protocol_version_id="protocol-cycle",
            protocol_code="PC",
            official_version="v1",
            official_date_value=None,
            official_date_precision="unknown",
            sha256="a" * 64,
            integrity_manifest_sha256="b" * 64,
            authority_record_sha256="c" * 64,
            authority_confirmation_id="c1",
            authority_gate_result_id="g1",
            integrity_gate_result_id="g2",
            payload_json="{}",
            payload_sha256="0" * 64,
            created_at=now,
        ))
        flush_add(session, RuleSetRecord(
            rule_set_id="rs-cycle",
            revision=1,
            protocol_version_id="protocol-cycle",
            study_phase="phase_iii",
            payload_json="{}",
            payload_sha256="0" * 64,
            created_at=now,
        ))
        flush_add(session, ProjectRecord(
            project_id="project-cycle",
            project_code="PC",
            project_name="cycle",
            study_phase="phase_iii",
            protocol_version_id="protocol-cycle",
            rule_set_id="rs-cycle",
            rule_set_revision=1,
            payload_json="{}",
            payload_sha256="0" * 64,
            revision=1,
            created_at=now,
            updated_at=now,
        ))
        flush_add(session, SubjectRecord(
            subject_id="subject-cycle",
            subject_code="C-1",
            project_id="project-cycle",
            payload_json="{}",
            payload_sha256="0" * 64,
            revision=1,
            created_at=now,
            updated_at=now,
        ))
        # episode 先插入（引用尚未存在的 snapshot），snapshot 后插入 -> 提交时校验
        flush_add(session, ReviewEpisodeRecord(
            review_episode_id="episode-cycle",
            subject_id="subject-cycle",
            project_id="project-cycle",
            rule_set_id="rs-cycle",
            rule_set_revision=1,
            study_phase="phase_iii",
            stage="screening",
            protocol_version_id="protocol-cycle",
            evidence_snapshot_id="snapshot-cycle",
            anchor_dates_json={},
            payload_json="{}",
            payload_sha256="0" * 64,
            revision=1,
            created_at=now,
            updated_at=now,
        ))
        flush_add(session, EvidenceSnapshotRecord(
            evidence_snapshot_id="snapshot-cycle",
            subject_id="subject-cycle",
            review_episode_id="episode-cycle",
            upload_mode="full",
            payload_json="{}",
            payload_sha256="0" * 64,
            created_at=now,
        ))
        session.commit()  # 不抛 IntegrityError
