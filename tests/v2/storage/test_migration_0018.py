"""0018 修订提交栅栏与冲突谱系迁移。"""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.services.fact_correction_executor import (
    FactCorrectionExecutorConfig,
    create_fact_correction_executor,
)
from app.services.fact_correction_job_service import FACT_CORRECTION_JOB_TYPE
from app.services.patient_profile_service import PatientProfileService
from app.storage.codecs import utc_now
from app.storage.db import build_engine
from app.storage.facts_models import (
    FactCorrectionCommitRecord,
    FactCorrectionConflictOutcomeRecord,
)
from app.storage.migrate import MigrationFailure, MigrationManager, resolve_head_revision
from app.workflow.runner import JobRunner
from tests.v2.services.test_fact_correction_job import NOW, _authority, _publish_fact, _submit
from tests.v2.storage.test_migration_0008 import PHASE5_V2_TABLES
from tests.v2.storage.test_fact_correction_repository import _seed_valid_chain


_MIGRATION_0018_TABLES = frozenset(
    {"fact_correction_commits", "fact_correction_conflict_outcomes"}
)


def test_0018_tables_are_registered_for_historical_metadata_snapshots() -> None:
    """后续 Phase 5 表不得污染 0007-0012 的历史 metadata 校验。"""
    assert _MIGRATION_0018_TABLES <= PHASE5_V2_TABLES


def test_0018_adds_commit_and_conflict_outcome_tables(data_paths):
    manager = MigrationManager(data_paths)
    manager.upgrade("head")
    engine = build_engine(data_paths.db_path)
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "fact_correction_commits" in tables
        assert "fact_correction_conflict_outcomes" in tables
        cols = {c["name"] for c in inspector.get_columns("fact_correction_commits")}
        assert "patient_profile_revision_id" in cols
        assert "impact_scope_json" in cols
        outcome_cols = {
            c["name"] for c in inspector.get_columns("fact_correction_conflict_outcomes")
        }
        assert "superseded_conflict_group_id" in outcome_cols
        assert "successor_conflict_group_id" in outcome_cols
        fks = inspector.get_foreign_keys("fact_correction_commits")
        referred = {fk["referred_table"] for fk in fks}
        assert "fact_corrections" in referred
        assert "patient_profile_revisions_v2" in referred
        assert "evidence_processing_revisions" in referred
        outcome_fks = inspector.get_foreign_keys("fact_correction_conflict_outcomes")
        outcome_referred = {fk["referred_table"] for fk in outcome_fks}
        assert "fact_correction_commits" in outcome_referred
        assert "clinical_conflict_groups_v2" in outcome_referred
        checks = {
            item["name"] or ""
            for item in inspector.get_check_constraints("fact_correction_commits")
        }
        assert any("ck_fcorr_commit_scope_kind" in name for name in checks)
        outcome_checks = {
            item["name"] or ""
            for item in inspector.get_check_constraints(
                "fact_correction_conflict_outcomes"
            )
        }
        assert any("ck_fcorr_conflict_outcome_distinct" in name for name in outcome_checks)
    finally:
        engine.dispose()
    manager.downgrade("0017")
    engine = build_engine(data_paths.db_path)
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "fact_correction_commits" not in tables
        assert "fact_correction_conflict_outcomes" not in tables
        assert "fact_corrections" in tables
    finally:
        engine.dispose()


def test_0018_foreign_key_and_check_enforcement(session_factory):
    from sqlalchemy import update

    with session_factory() as session, session.begin():
        chain = _seed_valid_chain(session, "m18-fk")
        fact = _publish_fact(session, chain)
        profile = PatientProfileService().generate(
            session, authority=_authority(chain), created_at=NOW, generated_at=NOW
        )
        authority_cols = {
            "project_id": chain["authority"].project_id,
            "subject_id": chain["authority"].subject_id,
            "review_episode_id": chain["authority"].review_episode_id,
            "episode_revision": chain["authority"].episode_revision,
            "protocol_version_id": chain["authority"].protocol_version_id,
            "rule_set_id": chain["authority"].rule_set_id,
            "rule_set_revision": chain["authority"].rule_set_revision,
            "evidence_snapshot_v2_id": chain["authority"].evidence_snapshot_v2_id,
            "complete_processing_revision_id": (
                chain["authority"].complete_processing_revision_id
            ),
        }
        ghost = FactCorrectionCommitRecord(
            correction_id="missing-correction",
            patient_profile_revision_id=profile.patient_profile_revision_id,
            impact_scope_kind="local",
            impact_fallback_reason=None,
            impact_scope_json={"scope_kind": "local", "affected_fact_ids": [fact.fact_id]},
            superseded_conflict_group_ids_json=[],
            successor_conflict_group_ids_json=[],
            payload_json="{}",
            payload_sha256="a" * 64,
            created_at=datetime(2026, 8, 23, 8, 0, 0),
            **authority_cols,
        )
        with pytest.raises(IntegrityError, match="FOREIGN KEY"):
            session.add(ghost)
            session.flush()

    with session_factory() as session, session.begin():
        chain = _seed_valid_chain(session, "m18-chk")
        fact = _publish_fact(session, chain)
        PatientProfileService().generate(
            session, authority=_authority(chain), created_at=NOW, generated_at=NOW
        )
        fact_ref = fact
        chain_ref = chain
    created = _submit(session_factory, chain_ref, fact_ref)
    runner = JobRunner(
        session_factory,
        {
            FACT_CORRECTION_JOB_TYPE: create_fact_correction_executor(
                FactCorrectionExecutorConfig(session_factory=session_factory)
            )
        },
        worker_id="w1",
        now=utc_now,
        poll_interval=0.01,
    )
    assert runner.run_once() is True
    with session_factory() as session, session.begin():
        with pytest.raises(IntegrityError):
            session.execute(
                update(FactCorrectionCommitRecord)
                .where(
                    FactCorrectionCommitRecord.correction_id == created.correction_id
                )
                .values(impact_scope_kind="bogus")
            )
            session.flush()
    with session_factory() as session, session.begin():
        with pytest.raises(IntegrityError, match="FOREIGN KEY"):
            session.add(
                FactCorrectionConflictOutcomeRecord(
                    outcome_id="m18-missing-group",
                    correction_id=created.correction_id,
                    superseded_conflict_group_id="missing-group",
                    successor_conflict_group_id=None,
                )
            )
            session.flush()


def test_0018_downgrade_refuses_populated_commits(
    data_paths, session_factory, migrated_engine
):
    manager = MigrationManager(data_paths)
    manager.upgrade("head")
    with session_factory() as session, session.begin():
        chain = _seed_valid_chain(session, "m18-pop")
        fact = _publish_fact(session, chain)
        PatientProfileService().generate(
            session, authority=_authority(chain), created_at=NOW, generated_at=NOW
        )
    created = _submit(session_factory, chain, fact)
    runner = JobRunner(
        session_factory,
        {
            FACT_CORRECTION_JOB_TYPE: create_fact_correction_executor(
                FactCorrectionExecutorConfig(session_factory=session_factory)
            )
        },
        worker_id="w1",
        now=utc_now,
        poll_interval=0.01,
    )
    assert runner.run_once() is True
    with session_factory() as session:
        from app.storage.fact_correction_commit_repository import (
            FactCorrectionCommitRepository,
        )

        assert FactCorrectionCommitRepository(session).get(created.correction_id)
    migrated_engine.dispose()
    with pytest.raises(MigrationFailure, match="0018"):
        manager.downgrade("0017")
    assert manager.read_revision(data_paths.db_path) == resolve_head_revision()
