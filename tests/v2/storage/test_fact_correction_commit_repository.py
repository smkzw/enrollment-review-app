"""修订提交栅栏仓储：权威闭包与类型化谱系行交叉核对。"""

from __future__ import annotations

import pytest
from sqlalchemy import update

from app.domain.contracts.fact_corrections import (
    ConflictCorrectionOutcome,
    FactCorrectionCommitV2,
    FactCorrectionImpactScope,
)
from app.services.patient_profile_service import PatientProfileService
from app.storage.codecs import PersistedContractInvalid
from app.storage.fact_correction_commit_repository import (
    FactCorrectionCommitError,
    FactCorrectionCommitRepository,
)
from app.storage.fact_correction_repository import FactCorrectionRepository
from app.storage.facts_models import (
    FactCorrectionConflictOutcomeRecord,
    FactCorrectionRecord,
)
from tests.v2.services.test_fact_correction_job import NOW, _authority, _publish_fact
from tests.v2.storage.test_fact_correction_repository import (
    _correction_for_facts,
    _create_fact_with_candidate,
    _seed_valid_chain,
)



def _delete_commit(session, correction_id: str) -> None:
    from app.storage.facts_models import (
        FactCorrectionCommitRecord,
        FactCorrectionConflictOutcomeRecord,
    )

    session.execute(
        FactCorrectionConflictOutcomeRecord.__table__.delete().where(
            FactCorrectionConflictOutcomeRecord.correction_id == correction_id
        )
    )
    session.execute(
        FactCorrectionCommitRecord.__table__.delete().where(
            FactCorrectionCommitRecord.correction_id == correction_id
        )
    )


def test_commit_rejects_missing_profile(session_factory):
    from tests.v2.services.test_fact_correction_job import _run, _submit

    with session_factory() as session, session.begin():
        chain = _seed_valid_chain(session, "cmt-miss")
        fact = _publish_fact(session, chain)
        PatientProfileService().generate(
            session, authority=_authority(chain), created_at=NOW, generated_at=NOW
        )
        fact_id = fact.fact_id
    created = _submit(session_factory, chain, type("T", (), {"fact_id": fact_id})())
    assert _run(session_factory) is True
    with session_factory() as session, session.begin():
        _delete_commit(session, created.correction_id)
        original = FactCorrectionRepository(session).get(created.correction_id)
        with pytest.raises(FactCorrectionCommitError, match="病历档案"):
            FactCorrectionCommitRepository(session).create(
                FactCorrectionCommitV2(
                    correction_id=created.correction_id,
                    authority=original.authority,
                    patient_profile_revision_id="missing-profile-revision",
                    impact_scope=original.impact_scope,
                    conflict_outcomes=[],
                    created_at=NOW,
                )
            )


def test_commit_rejects_parent_authority_mismatch(session_factory):
    from tests.v2.services.test_fact_correction_job import _run, _submit

    with session_factory() as session, session.begin():
        chain = _seed_valid_chain(session, "cmt-auth")
        fact = _publish_fact(session, chain)
        profile = PatientProfileService().generate(
            session, authority=_authority(chain), created_at=NOW, generated_at=NOW
        )
        fact_id = fact.fact_id
        profile_id = profile.patient_profile_revision_id
    created = _submit(session_factory, chain, type("T", (), {"fact_id": fact_id})())
    assert _run(session_factory) is True
    with session_factory() as session, session.begin():
        _delete_commit(session, created.correction_id)
        original = FactCorrectionRepository(session).get(created.correction_id)
        mismatched = original.authority.model_copy(
            update={"episode_revision": original.authority.episode_revision + 1}
        )
        with pytest.raises(FactCorrectionCommitError, match="权威"):
            FactCorrectionCommitRepository(session).create(
                FactCorrectionCommitV2(
                    correction_id=created.correction_id,
                    authority=mismatched,
                    patient_profile_revision_id=profile_id,
                    impact_scope=original.impact_scope,
                    conflict_outcomes=[],
                    created_at=NOW,
                )
            )


def test_commit_rejects_pre_correction_profile(session_factory):
    """提交栅栏不得把修订前档案当作本次生成结果。"""
    from tests.v2.services.test_fact_correction_job import _run, _submit

    with session_factory() as session, session.begin():
        chain = _seed_valid_chain(session, "cmt-pre")
        fact = _publish_fact(session, chain)
        pre_profile = PatientProfileService().generate(
            session, authority=_authority(chain), created_at=NOW, generated_at=NOW
        )
        fact_id = fact.fact_id
        pre_profile_id = pre_profile.patient_profile_revision_id
    created = _submit(session_factory, chain, type("T", (), {"fact_id": fact_id})())
    assert _run(session_factory) is True
    with session_factory() as session, session.begin():
        _delete_commit(session, created.correction_id)
        original = FactCorrectionRepository(session).get(created.correction_id)
        with pytest.raises(FactCorrectionCommitError, match="未包含本次新实体"):
            FactCorrectionCommitRepository(session).create(
                FactCorrectionCommitV2(
                    correction_id=created.correction_id,
                    authority=original.authority,
                    patient_profile_revision_id=pre_profile_id,
                    impact_scope=original.impact_scope,
                    conflict_outcomes=[],
                    created_at=NOW,
                )
            )


def test_commit_rejects_missing_conflict_group(session_factory):
    from tests.v2.services.test_fact_correction_job import _run, _submit

    with session_factory() as session, session.begin():
        chain = _seed_valid_chain(session, "cmt-cfg")
        fact = _publish_fact(session, chain)
        PatientProfileService().generate(
            session, authority=_authority(chain), created_at=NOW, generated_at=NOW
        )
        fact_id = fact.fact_id
    created = _submit(session_factory, chain, type("T", (), {"fact_id": fact_id})())
    assert _run(session_factory) is True
    with session_factory() as session, session.begin():
        # 提交栅栏必须绑定修订生成的档案；复用该档案 ID 再伪造冲突谱系。
        post_profile_id = FactCorrectionCommitRepository(session).get(
            created.correction_id
        ).patient_profile_revision_id
        _delete_commit(session, created.correction_id)
        original = FactCorrectionRepository(session).get(created.correction_id)
        with pytest.raises(FactCorrectionCommitError, match="冲突组"):
            FactCorrectionCommitRepository(session).create(
                FactCorrectionCommitV2(
                    correction_id=created.correction_id,
                    authority=original.authority,
                    patient_profile_revision_id=post_profile_id,
                    impact_scope=original.impact_scope,
                    conflict_outcomes=[
                        ConflictCorrectionOutcome(
                            superseded_conflict_group_id="missing-conflict-group",
                            successor_conflict_group_id=None,
                        )
                    ],
                    created_at=NOW,
                )
            )


def test_commit_read_rejects_typed_outcome_row_drift(session_factory):
    from app.domain.contracts.facts import ClinicalConflictGroupV2
    from app.storage.fact_repositories import ClinicalConflictGroupV2Repository

    with session_factory() as session, session.begin():
        chain = _seed_valid_chain(session, "cmt-drift")
        old = _publish_fact(session, chain, suffix="old")
        new = _create_fact_with_candidate(
            session,
            chain,
            fact_id=f"{chain['run_id']}-fact-new",
            run_id=f"{chain['run_id']}-new",
            call_id=f"{chain['call_id']}-new",
            gate_id=f"{chain['run_id']}-gate-new",
            cand_id=f"{chain['run_id']}-cand-new",
            value="130/80",
        )
        extra = _create_fact_with_candidate(
            session,
            chain,
            fact_id=f"{chain['run_id']}-fact-extra",
            run_id=f"{chain['run_id']}-extra",
            call_id=f"{chain['call_id']}-extra",
            gate_id=f"{chain['run_id']}-gate-extra",
            cand_id=f"{chain['run_id']}-cand-extra",
            value="90/60",
        )
        profile = PatientProfileService().generate(
            session, authority=_authority(chain), created_at=NOW, generated_at=NOW
        )
        group = ClinicalConflictGroupV2Repository(session).create(
            ClinicalConflictGroupV2(
                conflict_group_id=f"{chain['run_id']}-drift-group",
                run_id=old.run_id,
                gate_id=old.gate_id,
                authority=_authority(chain),
                fact_ids=sorted([old.fact_id, extra.fact_id]),
                locator_ids=[chain["locator_id"]],
                created_at=NOW,
            )
        )
        FactCorrectionRepository(session).create(
            _correction_for_facts(
                old,
                new,
                [chain["locator_id"]],
                correction_id="cmt-drift-1",
            )
        )
        FactCorrectionCommitRepository(session).create(
            FactCorrectionCommitV2(
                correction_id="cmt-drift-1",
                authority=_authority(chain),
                patient_profile_revision_id=profile.patient_profile_revision_id,
                impact_scope=FactCorrectionImpactScope(
                    scope_kind="local",
                    affected_fact_ids=[old.fact_id],
                ),
                conflict_outcomes=[],
                created_at=NOW,
            )
        )
        session.add(
            FactCorrectionConflictOutcomeRecord(
                outcome_id="cmt-drift-forged",
                correction_id="cmt-drift-1",
                superseded_conflict_group_id=group.conflict_group_id,
                successor_conflict_group_id=None,
            )
        )
        session.flush()
        with pytest.raises(PersistedContractInvalid, match="类型化冲突谱系"):
            FactCorrectionCommitRepository(session).get("cmt-drift-1")


def test_commit_read_revalidates_parent_correction_lineage(session_factory):
    from tests.v2.services.test_fact_correction_job import _run, _submit

    with session_factory() as session, session.begin():
        chain = _seed_valid_chain(session, "cmt-parent-drift")
        fact = _publish_fact(session, chain)
        PatientProfileService().generate(
            session, authority=_authority(chain), created_at=NOW, generated_at=NOW
        )
    created = _submit(session_factory, chain, fact)
    assert _run(session_factory) is True

    with session_factory() as session, session.begin():
        session.execute(
            update(FactCorrectionRecord)
            .where(FactCorrectionRecord.correction_id == created.correction_id)
            .values(episode_revision=FactCorrectionRecord.episode_revision + 1)
        )

    with session_factory() as session:
        with pytest.raises(PersistedContractInvalid, match="权威列 episode_revision"):
            FactCorrectionCommitRepository(session).get(created.correction_id)
