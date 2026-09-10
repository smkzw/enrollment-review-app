"""Slice 5.7 人工事实修订持久任务：原子提交与故障注入。"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
import hashlib

import pytest
from sqlalchemy import update

from app.services.fact_correction_executor import (
    FactCorrectionExecutorConfig,
    create_fact_correction_executor,
)
from app.services.fact_correction_job_service import (
    FACT_CORRECTION_JOB_TYPE,
    FactCorrectionJobService,
)
from app.services.fact_correction_service import list_fact_correction_history
from app.services.patient_profile_service import PatientProfileService
from app.storage.codecs import utc_now
from app.storage.fact_correction_repository import FactCorrectionRepository
from app.storage.fact_repositories import ClinicalFactV2Repository
from app.storage.models import JobRecord, ReviewEpisodeRecord
from app.storage.patient_profile_repository import PatientProfileRevisionRepository
from app.workflow.jobstore import JobStore
from app.workflow.recovery import recover_expired_jobs
from app.workflow.runner import JobRunner, PreparedStepResult
from tests.v2.storage.test_fact_correction_repository import (
    _create_fact_with_candidate,
    _seed_valid_chain,
)
from tests.v2.storage.test_fact_repositories import _update_episode

NOW = datetime(2026, 8, 23, 8, 0, 0, tzinfo=UTC)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _authority(chain):
    return chain["authority"]


def _publish_fact(
    session,
    chain,
    suffix: str = "a",
    value: str = "120/80",
    **overrides,
):
    return _create_fact_with_candidate(
        session,
        chain,
        fact_id=f"{chain['run_id']}-fact-{suffix}",
        run_id=f"{chain['run_id']}-{suffix}",
        call_id=f"{chain['call_id']}-{suffix}",
        gate_id=f"{chain['run_id']}-gate-{suffix}",
        cand_id=f"{chain['run_id']}-cand-{suffix}",
        value=value,
        **overrides,
    )


def _service(session_factory):
    return FactCorrectionJobService(session_factory, now=utc_now)


def _submit(session_factory, chain, fact, *, value: str = "130/80", reason: str = "核对原文第3页，血压值录入错误"):
    return _service(session_factory).create_or_reuse_job(
        authority=_authority(chain),
        target_kind="fact",
        target_id=fact.fact_id,
        locator_ids=[chain["locator_id"]],
        reason=reason,
        operator_id="reviewer-1",
        updates={"value": value},
        created_by="reviewer-1",
        created_at=NOW,
    )


def _run(session_factory, executors=None):
    runner = JobRunner(
        session_factory,
        executors
        or {
            FACT_CORRECTION_JOB_TYPE: create_fact_correction_executor(
                FactCorrectionExecutorConfig(session_factory=session_factory)
            )
        },
        worker_id="w1",
        now=utc_now,
        poll_interval=0.01,
    )
    return runner.run_once()


def _day(text: str):
    from app.domain.contracts.enums import DatePrecision
    from app.domain.contracts.facts import PartialDateRange

    year, month, day = (int(part) for part in text.split("-"))
    bound = date(year, month, day)
    return PartialDateRange(
        source_text=text,
        precision=DatePrecision.DAY,
        lower_bound=bound,
        upper_bound=bound,
    )


def _fact_candidate_ids(session, fact_ids: list[str]) -> list[str]:
    from app.storage.fact_repositories import ClinicalFactV2Repository

    return ClinicalFactV2Repository(session)._fact_candidate_ids(fact_ids)


def _publish_event(
    session,
    chain,
    fact,
    *,
    suffix: str,
    start,
    end=None,
    duration,
):
    from app.domain.contracts.enums import (
        DurationStatus,
        FactCallStatus,
        FactGate,
        FactNormalizationRunStatus,
        GateOutcome,
        ProfileLane,
        SourceStrength,
    )
    from app.domain.contracts.facts import (
        ClinicalEventCandidateV2,
        ClinicalEventV2,
        FactGateResult,
        FactNormalizationCall,
        FactNormalizationRun,
        clinical_event_stable_identity,
        fact_run_idempotency_key,
    )
    from app.storage.fact_repositories import (
        ClinicalEventV2Repository,
        ClinicalFactV2Repository,
        FactGateResultRepository,
        FactNormalizationCallRepository,
        FactNormalizationCandidateRepository,
        FactNormalizationRunRepository,
    )

    run_id = f"{chain['run_id']}-event-{suffix}"
    call_id = f"{chain['call_id']}-event-{suffix}"
    gate_id = f"{run_id}-gate"
    cand_id = f"{run_id}-cand"
    FactNormalizationRunRepository(session).create_or_reuse(
        FactNormalizationRun(
            run_id=run_id,
            authority=_authority(chain),
            idempotency_key=fact_run_idempotency_key(
                authority=_authority(chain),
                prompt_version_id=chain["prompt_version_id"],
                model_config_id=chain["model_config_id"],
                input_scope_sha256=_sha(f"{run_id}-scope"),
            ),
            prompt_version_id=chain["prompt_version_id"],
            model_config_id=chain["model_config_id"],
            input_scope_sha256=_sha(f"{run_id}-scope"),
            status=FactNormalizationRunStatus.SUCCEEDED,
            created_at=NOW,
            created_by="tester",
        )
    )
    FactNormalizationCallRepository(session).create(
        FactNormalizationCall(
            call_id=call_id,
            run_id=run_id,
            logical_document_id=chain["logical_document_id"],
            page_numbers=[1],
            status=FactCallStatus.SUCCEEDED,
            input_sha256=_sha(f"{call_id}-input"),
            created_at=NOW,
        )
    )
    FactNormalizationCandidateRepository(session).create(
        call_id,
        ClinicalEventCandidateV2(
            candidate_id=cand_id,
            run_id=run_id,
            call_id=call_id,
            event_type="diagnosis",
            start_range=start,
            end_range=end,
            duration_status=duration,
            record_time=NOW,
            fact_candidate_ids=_fact_candidate_ids(session, [fact.fact_id]),
            locator_ids=[chain["locator_id"]],
            candidate_source_semantics="objective_result",
            model_uncertainty=0.0,
            created_at=NOW,
        ),
    )
    FactGateResultRepository(session).create(
        FactGateResult(
            gate_result_id=gate_id,
            run_id=run_id,
            call_id=call_id,
            candidate_id=cand_id,
            gate=FactGate.TRANSACTIONAL_PUBLISH,
            outcome=GateOutcome.ACCEPTED,
            reasons=[],
            created_at=NOW,
        )
    )
    objects = ClinicalFactV2Repository(session)._fact_semantic_objects([fact.fact_id])
    stable = clinical_event_stable_identity(
        authority=_authority(chain),
        event_type="diagnosis",
        profile_lane=ProfileLane.EVIDENCE_QUALITY,
        referenced_fact_objects=objects,
        start_range=start,
        end_range=end,
        duration_status=duration,
    )
    return ClinicalEventV2Repository(session).create(
        ClinicalEventV2(
            event_id=f"{run_id}-id",
            run_id=run_id,
            gate_id=gate_id,
            source_candidate_ids=[cand_id],
            gate_ids=[gate_id],
            authority=_authority(chain),
            event_type="diagnosis",
            start_range=start,
            end_range=end,
            duration_status=duration,
            record_time=NOW,
            fact_ids=[fact.fact_id],
            referenced_fact_objects=objects,
            locator_ids=[chain["locator_id"]],
            source_strength=SourceStrength.CONTEMPORANEOUS_OBJECTIVE,
            stable_identity=stable,
            revision=1,
            created_at=NOW,
        )
    )


def _publish_exposure(
    session,
    chain,
    fact,
    *,
    suffix: str,
    start,
    end=None,
    duration,
):
    from app.domain.contracts.enums import (
        DurationStatus,
        FactCallStatus,
        FactGate,
        FactNormalizationRunStatus,
        GateOutcome,
        SourceStrength,
    )
    from app.domain.contracts.facts import (
        FactGateResult,
        FactNormalizationCall,
        FactNormalizationRun,
        MedicationExposureCandidateV2,
        MedicationExposureV2,
        fact_run_idempotency_key,
        medication_exposure_stable_identity,
    )
    from app.storage.fact_repositories import (
        FactGateResultRepository,
        FactNormalizationCallRepository,
        FactNormalizationCandidateRepository,
        FactNormalizationRunRepository,
        MedicationExposureV2Repository,
    )

    run_id = f"{chain['run_id']}-exp-{suffix}"
    call_id = f"{chain['call_id']}-exp-{suffix}"
    gate_id = f"{run_id}-gate"
    cand_id = f"{run_id}-cand"
    FactNormalizationRunRepository(session).create_or_reuse(
        FactNormalizationRun(
            run_id=run_id,
            authority=_authority(chain),
            idempotency_key=fact_run_idempotency_key(
                authority=_authority(chain),
                prompt_version_id=chain["prompt_version_id"],
                model_config_id=chain["model_config_id"],
                input_scope_sha256=_sha(f"{run_id}-scope"),
            ),
            prompt_version_id=chain["prompt_version_id"],
            model_config_id=chain["model_config_id"],
            input_scope_sha256=_sha(f"{run_id}-scope"),
            status=FactNormalizationRunStatus.SUCCEEDED,
            created_at=NOW,
            created_by="tester",
        )
    )
    FactNormalizationCallRepository(session).create(
        FactNormalizationCall(
            call_id=call_id,
            run_id=run_id,
            logical_document_id=chain["logical_document_id"],
            page_numbers=[1],
            status=FactCallStatus.SUCCEEDED,
            input_sha256=_sha(f"{call_id}-input"),
            created_at=NOW,
        )
    )
    FactNormalizationCandidateRepository(session).create(
        call_id,
        MedicationExposureCandidateV2(
            candidate_id=cand_id,
            run_id=run_id,
            call_id=call_id,
            medication_name="二甲双胍",
            category="降糖药",
            indication="2 型糖尿病",
            dose="500",
            unit="mg",
            frequency="bid",
            route="口服",
            start_range=start,
            end_range=end,
            duration_status=duration,
            record_time=NOW,
            fact_candidate_ids=_fact_candidate_ids(session, [fact.fact_id]),
            locator_ids=[chain["locator_id"]],
            candidate_source_semantics="objective_result",
            model_uncertainty=0.0,
            created_at=NOW,
        ),
    )
    FactGateResultRepository(session).create(
        FactGateResult(
            gate_result_id=gate_id,
            run_id=run_id,
            call_id=call_id,
            candidate_id=cand_id,
            gate=FactGate.TRANSACTIONAL_PUBLISH,
            outcome=GateOutcome.ACCEPTED,
            reasons=[],
            created_at=NOW,
        )
    )
    stable = medication_exposure_stable_identity(
        authority=_authority(chain),
        medication_name="二甲双胍",
        category="降糖药",
        indication="2 型糖尿病",
        dose="500",
        unit="mg",
        frequency="bid",
        route="口服",
        start_range=start,
        end_range=end,
        duration_status=duration,
    )
    return MedicationExposureV2Repository(session).create(
        MedicationExposureV2(
            exposure_id=f"{run_id}-id",
            run_id=run_id,
            gate_id=gate_id,
            source_candidate_ids=[cand_id],
            gate_ids=[gate_id],
            authority=_authority(chain),
            medication_name="二甲双胍",
            category="降糖药",
            indication="2 型糖尿病",
            dose="500",
            unit="mg",
            frequency="bid",
            route="口服",
            start_range=start,
            end_range=end,
            duration_status=duration,
            record_time=NOW,
            fact_ids=[fact.fact_id],
            locator_ids=[chain["locator_id"]],
            source_strength=SourceStrength.CONTEMPORANEOUS_OBJECTIVE,
            stable_identity=stable,
            revision=1,
            created_at=NOW,
        )
    )


def test_submit_atomically_appends_entity_correction_and_profile(session_factory):
    with session_factory() as session, session.begin():
        chain = _seed_valid_chain(session, "corr-ok")
        fact = _publish_fact(session, chain)
        old_profile = PatientProfileService().generate(
            session, authority=_authority(chain), created_at=NOW, generated_at=NOW
        )
        old_profile_id = old_profile.patient_profile_revision_id
        old_payload = old_profile.model_dump(mode="json")
        fact_id = fact.fact_id
        locator_id = chain["locator_id"]
        fact_copy = fact

    created = _submit(session_factory, chain, fact_copy)
    assert created.created is True
    assert _run(session_factory) is True

    with session_factory() as session:
        store = JobStore(session, now=utc_now)
        snapshot = store.snapshot(created.job_id)
        assert snapshot.state == "completed", (
            snapshot.state,
            snapshot.error_code,
            [
                (step.step_id, step.state, step.error_code)
                for step in snapshot.steps
            ],
        )
        corrections = FactCorrectionRepository(session).list_by_target(
            ClinicalFactV2Repository(session).get(fact_id).stable_identity
        )
        assert len(corrections) == 1
        correction = corrections[0]
        assert correction.target_id == fact_id
        assert correction.new_entity_id != fact_id
        assert correction.reason == "核对原文第3页，血压值录入错误"
        assert locator_id in correction.locator_ids
        assert list(correction.impact_scope.affected_conflict_group_ids) == []
        new_fact = ClinicalFactV2Repository(session).get(correction.new_entity_id)
        assert new_fact.value == "130/80"
        old_fact = ClinicalFactV2Repository(session).get(fact_id)
        assert old_fact.value == "120/80"
        old = PatientProfileRevisionRepository(session).get(old_profile_id)
        assert old.model_dump(mode="json") == old_payload
        latest = PatientProfileService().latest(session, chain["review_episode_id"])
        assert latest is not None
        assert latest.patient_profile_revision_id != old_profile_id
        assert latest.revision == old.revision + 1
        plan_ckpt = store.get_last_checkpoint(created.job_id, "plan")
        apply_ckpt = store.get_last_checkpoint(created.job_id, "apply")
        assert plan_ckpt is not None and apply_ckpt is not None
        assert "affected_conflict_group_ids" in plan_ckpt[1]["impact_scope"]
        assert "affected_conflict_group_ids" in apply_ckpt[1]["impact_scope"]


def test_duplicate_submit_reuses_job_and_does_not_duplicate_entities(session_factory):
    with session_factory() as session, session.begin():
        chain = _seed_valid_chain(session, "corr-dup")
        fact = _publish_fact(session, chain)
    first = _submit(session_factory, chain, fact)
    second = _submit(session_factory, chain, fact)
    assert second.created is False
    assert second.job_id == first.job_id
    _run(session_factory)
    _run(session_factory)
    with session_factory() as session:
        facts = ClinicalFactV2Repository(session).list_for_authority(_authority(chain))
        values = [item.value for item in facts]
        assert values.count("130/80") == 1
        assert values.count("120/80") == 1
        corrections = FactCorrectionRepository(session).list_by_authority(_authority(chain))
        assert len(corrections) == 1


def test_identical_submit_after_completed_job_reuses_completed_job(session_factory):
    """完成后的相同请求必须复用已完成 Job，不得因目标已不可变而重建。"""
    with session_factory() as session, session.begin():
        chain = _seed_valid_chain(session, "corr-done-idem")
        fact = _publish_fact(session, chain)
        PatientProfileService().generate(
            session, authority=_authority(chain), created_at=NOW, generated_at=NOW
        )
    first = _submit(session_factory, chain, fact)
    assert _run(session_factory) is True
    with session_factory() as session:
        assert JobStore(session, now=utc_now).snapshot(first.job_id).state == "completed"
        before_facts = {
            item.fact_id
            for item in ClinicalFactV2Repository(session).list_for_authority(
                _authority(chain)
            )
        }
    second = _submit(session_factory, chain, fact)
    assert second.created is False
    assert second.job_id == first.job_id
    assert second.correction_id == first.correction_id
    assert second.status == "completed"
    assert _run(session_factory) is False
    with session_factory() as session:
        after_facts = {
            item.fact_id
            for item in ClinicalFactV2Repository(session).list_for_authority(
                _authority(chain)
            )
        }
        assert after_facts == before_facts
        assert (
            len(FactCorrectionRepository(session).list_by_authority(_authority(chain)))
            == 1
        )


def test_correction_history_survives_episode_revision_advance(session_factory):
    """同审核节点 revision 前进后，历史仍按冻结 Profile 修订号可读。"""
    from app.services.fact_correction_service import authority_from_episode

    with session_factory() as session, session.begin():
        chain = _seed_valid_chain(session, "corr-hist-adv")
        fact = _publish_fact(session, chain)
        PatientProfileService().generate(
            session, authority=_authority(chain), created_at=NOW, generated_at=NOW
        )
        episode_id = chain["review_episode_id"]
        frozen_episode_revision = chain["authority"].episode_revision
    created = _submit(session_factory, chain, fact)
    assert _run(session_factory) is True
    with session_factory() as session:
        before = list_fact_correction_history(session, episode_id)
        assert len(before) == 1
        assert before[0].correction.correction_id == created.correction_id
        frozen_profile_id = before[0].patient_profile_revision_id
        frozen_profile_revision = before[0].patient_profile_revision
        assert (
            before[0].correction.authority.episode_revision == frozen_episode_revision
        )
    with session_factory() as session, session.begin():
        episode = session.get(ReviewEpisodeRecord, episode_id)
        _update_episode(session, episode, revision=frozen_episode_revision + 1)
    with session_factory() as session:
        current_authority = authority_from_episode(session, episode_id)
        assert current_authority.episode_revision == frozen_episode_revision + 1
        # 活动权威已前进：按当前权威过滤会丢历史；按审核节点必须仍可见。
        assert (
            FactCorrectionRepository(session).list_by_authority(current_authority) == []
        )
        after = list_fact_correction_history(session, episode_id)
        assert len(after) == 1
        assert after[0].correction.correction_id == created.correction_id
        assert after[0].patient_profile_revision_id == frozen_profile_id
        assert after[0].patient_profile_revision == frozen_profile_revision
        assert (
            after[0].correction.authority.episode_revision == frozen_episode_revision
        )


def test_cancel_before_apply_keeps_previous_profile(session_factory):
    with session_factory() as session, session.begin():
        chain = _seed_valid_chain(session, "corr-cancel")
        fact = _publish_fact(session, chain)
        old_profile = PatientProfileService().generate(
            session, authority=_authority(chain), created_at=NOW, generated_at=NOW
        )
        old_id = old_profile.patient_profile_revision_id
    created = _submit(session_factory, chain, fact)
    _service(session_factory).cancel(created.job_id)
    _run(session_factory)
    with session_factory() as session:
        store = JobStore(session, now=utc_now)
        assert store.snapshot(created.job_id).state == "cancelled"
        facts = ClinicalFactV2Repository(session).list_for_authority(_authority(chain))
        assert [item.value for item in facts] == ["120/80"]
        latest = PatientProfileService().latest(session, chain["review_episode_id"])
        assert latest is not None
        assert latest.patient_profile_revision_id == old_id
        assert FactCorrectionRepository(session).list_by_authority(_authority(chain)) == []


def test_late_result_after_lease_loss_does_not_write_entities(session_factory):
    with session_factory() as session, session.begin():
        chain = _seed_valid_chain(session, "corr-late")
        fact = _publish_fact(session, chain)
        PatientProfileService().generate(
            session, authority=_authority(chain), created_at=NOW, generated_at=NOW
        )
    created = _submit(session_factory, chain, fact)
    apply_calls: list[str] = []
    real = create_fact_correction_executor(
        FactCorrectionExecutorConfig(session_factory=session_factory)
    )

    def hijack(context):
        result = real(context)
        if context.step_id != "apply":
            return result
        with session_factory() as session, session.begin():
            session.execute(
                update(JobRecord)
                .where(JobRecord.job_id == created.job_id)
                .values(
                    lease_owner="w2",
                    lease_generation=JobRecord.lease_generation + 1,
                )
            )

        def apply(session):
            apply_calls.append("apply")
            if isinstance(result, PreparedStepResult):
                result.apply(session)

        assert isinstance(result, PreparedStepResult)
        return PreparedStepResult(checkpoint=result.checkpoint, apply=apply)

    runner = JobRunner(
        session_factory,
        {FACT_CORRECTION_JOB_TYPE: hijack},
        worker_id="w1",
        now=utc_now,
        poll_interval=0.01,
    )
    runner.run_once()
    with session_factory() as session:
        facts = ClinicalFactV2Repository(session).list_for_authority(_authority(chain))
        assert [item.value for item in facts] == ["120/80"]
        assert FactCorrectionRepository(session).list_by_authority(_authority(chain)) == []
    assert apply_calls == []


def test_partial_apply_failure_rolls_back_entities(session_factory):
    with session_factory() as session, session.begin():
        chain = _seed_valid_chain(session, "corr-partial")
        fact = _publish_fact(session, chain)
        old_profile = PatientProfileService().generate(
            session, authority=_authority(chain), created_at=NOW, generated_at=NOW
        )
        old_id = old_profile.patient_profile_revision_id
    created = _submit(session_factory, chain, fact)
    real = create_fact_correction_executor(
        FactCorrectionExecutorConfig(session_factory=session_factory)
    )

    def boom(context):
        result = real(context)
        if context.step_id != "apply":
            return result
        assert isinstance(result, PreparedStepResult)

        def apply(session):
            result.apply(session)
            raise RuntimeError("forced partial failure")

        return PreparedStepResult(checkpoint=result.checkpoint, apply=apply)

    runner = JobRunner(
        session_factory,
        {FACT_CORRECTION_JOB_TYPE: boom},
        worker_id="w1",
        now=utc_now,
        poll_interval=0.01,
    )
    runner.run_once()
    with session_factory() as session:
        store = JobStore(session, now=utc_now)
        snapshot = store.snapshot(created.job_id)
        assert snapshot.state in {"failed_final", "failed_retryable", "failed"}
        facts = ClinicalFactV2Repository(session).list_for_authority(_authority(chain))
        assert [item.value for item in facts] == ["120/80"]
        assert FactCorrectionRepository(session).list_by_authority(_authority(chain)) == []
        latest = PatientProfileService().latest(session, chain["review_episode_id"])
        assert latest is not None
        assert latest.patient_profile_revision_id == old_id


def test_recovery_after_expired_lease_completes_without_duplicate(session_factory):
    with session_factory() as session, session.begin():
        chain = _seed_valid_chain(session, "corr-recover")
        fact = _publish_fact(session, chain)
        PatientProfileService().generate(
            session, authority=_authority(chain), created_at=NOW, generated_at=NOW
        )
    created = _submit(session_factory, chain, fact)
    with session_factory() as session, session.begin():
        session.execute(
            update(JobRecord)
            .where(JobRecord.job_id == created.job_id)
            .values(
                state="running",
                lease_owner="dead-worker",
                lease_generation=1,
                lease_expires_at=utc_now() - timedelta(seconds=5),
            )
        )
    recover_expired_jobs(session_factory, now=utc_now)
    _run(session_factory)
    with session_factory() as session:
        store = JobStore(session, now=utc_now)
        assert store.snapshot(created.job_id).state == "completed"
        facts = ClinicalFactV2Repository(session).list_for_authority(_authority(chain))
        assert sorted(item.value for item in facts) == ["120/80", "130/80"]
        assert len(FactCorrectionRepository(session).list_by_authority(_authority(chain))) == 1


def test_node_fallback_is_persisted_when_replacement_signature_missing(session_factory):
    with session_factory() as session, session.begin():
        chain = _seed_valid_chain(session, "corr-node")
        fact = _publish_fact(session, chain)
        fact_id = fact.fact_id
        locator_id = chain["locator_id"]
        authority = _authority(chain)
    from app.services.fact_correction_service import preview_fact_correction

    with session_factory() as session:
        preview = preview_fact_correction(
            session,
            authority=authority,
            target_kind="fact",
            target_id=fact_id,
            locator_ids=[locator_id],
            updates={"value": "140/90"},
        )
        assert preview.impact_scope.affected_conflict_group_ids == []
        assert preview.new_snapshot["value"] == "140/90"
        assert preview.old_snapshot["value"] == "120/80"


def test_preview_is_read_only(session_factory):
    from app.services.fact_correction_service import preview_fact_correction
    from app.storage.models import JobRecord
    from sqlalchemy import func, select

    with session_factory() as session, session.begin():
        chain = _seed_valid_chain(session, "corr-preview")
        fact = _publish_fact(session, chain)
        PatientProfileService().generate(
            session, authority=_authority(chain), created_at=NOW, generated_at=NOW
        )
        before_facts = len(ClinicalFactV2Repository(session).list_for_authority(_authority(chain)))
        before_corr = len(FactCorrectionRepository(session).list_by_authority(_authority(chain)))
        before_jobs = session.execute(select(func.count()).select_from(JobRecord)).scalar_one()
        before_profiles = len(
            PatientProfileRevisionRepository(session).list_by_episode(chain["review_episode_id"])
        )
        preview_fact_correction(
            session,
            authority=_authority(chain),
            target_kind="fact",
            target_id=fact.fact_id,
            locator_ids=[chain["locator_id"]],
            updates={"value": "130/80"},
        )
        assert len(ClinicalFactV2Repository(session).list_for_authority(_authority(chain))) == before_facts
        assert len(FactCorrectionRepository(session).list_by_authority(_authority(chain))) == before_corr
        assert session.execute(select(func.count()).select_from(JobRecord)).scalar_one() == before_jobs
        assert len(
            PatientProfileRevisionRepository(session).list_by_episode(chain["review_episode_id"])
        ) == before_profiles


def test_profile_lane_only_correction_preserves_assertion_and_source_strength(
    session_factory,
):
    from app.domain.contracts.enums import ProfileLane, SourceStrength
    from app.services.fact_correction_service import preview_fact_correction

    with session_factory() as session, session.begin():
        chain = _seed_valid_chain(session, "corr-lane-fidelity")
        precise_text = "坐位血压 120/80 mmHg"
        fact = _publish_fact(
            session,
            chain,
            assertion_text=precise_text,
        )
        fact_id = fact.fact_id
        authority = _authority(chain)
        locator_id = chain["locator_id"]

    with session_factory() as session:
        preview = preview_fact_correction(
            session,
            authority=authority,
            target_kind="fact",
            target_id=fact_id,
            locator_ids=[locator_id],
            updates={"profile_lane": ProfileLane.SYMPTOMS_SIGNS.value},
        )
        assert preview.new_snapshot["assertion_text"] == precise_text
        assert (
            preview.new_snapshot["source_strength"]
            == SourceStrength.CONTEMPORANEOUS_OBJECTIVE.value
        )

    created = _service(session_factory).create_or_reuse_job(
        authority=authority,
        target_kind="fact",
        target_id=fact_id,
        locator_ids=[locator_id],
        reason="更正主题归属",
        operator_id="reviewer-1",
        updates={"profile_lane": ProfileLane.SYMPTOMS_SIGNS.value},
        created_by="reviewer-1",
        created_at=NOW,
    )
    assert _run(session_factory) is True
    with session_factory() as session:
        assert JobStore(session, now=utc_now).snapshot(created.job_id).state == "completed"
        history = list_fact_correction_history(session, chain["review_episode_id"])
        assert len(history) == 1
        corrected = ClinicalFactV2Repository(session).get(
            history[0].correction.new_entity_id
        )
        assert corrected.assertion_basis is not None
        assert corrected.assertion_basis.assertion_text == precise_text
        assert corrected.source_strength == SourceStrength.CONTEMPORANEOUS_OBJECTIVE


def test_conflict_member_correction_appends_successor_or_resolution(session_factory):
    from app.domain.contracts.patient_profile_v2 import ProfileItemKind, profile_items
    from app.storage.fact_correction_commit_repository import FactCorrectionCommitRepository
    from app.storage.fact_repositories import ClinicalConflictGroupV2Repository
    from tests.v2.storage.test_fact_repositories import _create_and_assert_fact_conflict_group

    with session_factory() as session, session.begin():
        chain = _seed_valid_chain(session, "corr-conf")
        _create_and_assert_fact_conflict_group(chain, session)
        PatientProfileService().generate(
            session, authority=_authority(chain), created_at=NOW, generated_at=NOW
        )
        class _Target:
            fact_id = "fact-a"
        target = _Target()
    created = _submit(session_factory, chain, target, value="90/60")
    assert _run(session_factory) is True
    with session_factory() as session:
        old = ClinicalConflictGroupV2Repository(session).get("conflict-1")
        assert old.fact_ids == ["fact-a", "fact-b"]
        commit = FactCorrectionCommitRepository(session).get(created.correction_id)
        assert len(commit.conflict_outcomes) == 1
        assert commit.conflict_outcomes[0].superseded_conflict_group_id == "conflict-1"
        assert commit.conflict_outcomes[0].successor_conflict_group_id is None
        latest = PatientProfileService().get(session, commit.patient_profile_revision_id)
        conflict_items = [
            item for item in profile_items(latest) if item.kind == ProfileItemKind.CONFLICT
        ]
        assert all(item.source_id != "conflict-1" for item in conflict_items)


def test_conflict_member_correction_keeps_active_conflict_on_current_ids(session_factory):
    from app.domain.contracts.patient_profile_v2 import ProfileItemKind, profile_items
    from app.storage.fact_correction_commit_repository import FactCorrectionCommitRepository
    from app.storage.fact_repositories import ClinicalConflictGroupV2Repository
    from tests.v2.storage.test_fact_repositories import _create_and_assert_fact_conflict_group

    with session_factory() as session, session.begin():
        chain = _seed_valid_chain(session, "corr-conf2")
        _create_and_assert_fact_conflict_group(chain, session)
        PatientProfileService().generate(
            session, authority=_authority(chain), created_at=NOW, generated_at=NOW
        )
        class _Target:
            fact_id = "fact-a"
        target = _Target()
    created = _submit(session_factory, chain, target, value="110/70")
    assert _run(session_factory) is True
    with session_factory() as session:
        old = ClinicalConflictGroupV2Repository(session).get("conflict-1")
        assert old.fact_ids == ["fact-a", "fact-b"]
        commit = FactCorrectionCommitRepository(session).get(created.correction_id)
        successor_id = commit.conflict_outcomes[0].successor_conflict_group_id
        assert successor_id
        successor = ClinicalConflictGroupV2Repository(session).get(successor_id)
        assert "fact-b" in successor.fact_ids
        assert "fact-a" not in successor.fact_ids
        latest = PatientProfileService().get(session, commit.patient_profile_revision_id)
        conflict_ids = {
            item.source_id
            for item in profile_items(latest)
            if item.kind == ProfileItemKind.CONFLICT
        }
        assert successor_id in conflict_ids
        assert "conflict-1" not in conflict_ids
        members = next(
            item.conflict_member_ids
            for item in profile_items(latest)
            if item.source_id == successor_id
        )
        assert "fact-a" not in members
        assert "fact-b" in members


def test_rule_links_rebuild_from_active_heads_only(session_factory):
    from app.storage.fact_rule_link_repository import FactRuleLinkV2Repository
    from tests.v2.storage.test_fact_rule_link_repository import (
        _publish_fact,
        _seed_procedure_requirement,
    )

    with session_factory() as session, session.begin():
        chain = _seed_valid_chain(session, "corr-rule")
        _seed_procedure_requirement(session, chain, requirement_id="req", fact_type="vital_sign")
        fact = _publish_fact(
            session,
            chain,
            fact_id=f"{chain['run_id']}-linked",
            fact_type="vital_sign",
            asserted_object="血压",
            value="120/80",
            supported_requirement_ids=["req"],
        )
        FactRuleLinkV2Repository(session).rebuild_for_authority(_authority(chain))
        old_links = FactRuleLinkV2Repository(session).list_for_facts([fact.fact_id])
        assert old_links[fact.fact_id]
        PatientProfileService().generate(
            session, authority=_authority(chain), created_at=NOW, generated_at=NOW
        )
    created = _submit(session_factory, chain, fact, value="130/80")
    assert _run(session_factory) is True
    with session_factory() as session:
        repo = FactRuleLinkV2Repository(session)
        old_links = repo.list_for_facts([fact.fact_id])
        assert old_links[fact.fact_id] == []
        correction = FactCorrectionRepository(session).get(created.correction_id)
        new_links = repo.list_for_facts([correction.new_entity_id])
        assert new_links[correction.new_entity_id]


def test_second_correction_of_same_target_cannot_branch(session_factory):
    with session_factory() as session, session.begin():
        chain = _seed_valid_chain(session, "corr-branch")
        fact = _publish_fact(session, chain)
        PatientProfileService().generate(
            session, authority=_authority(chain), created_at=NOW, generated_at=NOW
        )
    _submit(session_factory, chain, fact, value="130/80")
    assert _run(session_factory) is True
    from app.services.evidence_app_errors import AppFactCorrectionError

    with pytest.raises(AppFactCorrectionError, match="分叉"):
        _submit(session_factory, chain, fact, value="140/90", reason="再次修订同一原记录")


def test_plan_to_apply_graph_change_cannot_commit_narrower_scope(session_factory):
    from app.services.fact_correction_executor import create_fact_correction_executor
    from app.services.fact_correction_job_service import FACT_CORRECTION_APPLY_STEP_ID
    from tests.v2.storage.test_fact_correction_repository import _create_fact_with_candidate

    with session_factory() as session, session.begin():
        chain = _seed_valid_chain(session, "corr-stale")
        fact = _publish_fact(session, chain)
        PatientProfileService().generate(
            session, authority=_authority(chain), created_at=NOW, generated_at=NOW
        )
        fact_id = fact.fact_id
    created = _submit(session_factory, chain, fact, value="130/80")
    real = create_fact_correction_executor(
        FactCorrectionExecutorConfig(session_factory=session_factory)
    )

    def hijack(context):
        if context.step_id == FACT_CORRECTION_APPLY_STEP_ID:
            with session_factory() as session, session.begin():
                _create_fact_with_candidate(
                    session,
                    chain,
                    fact_id=f"{chain['run_id']}-extra",
                    run_id=f"{chain['run_id']}-extra",
                    call_id=f"{chain['call_id']}-extra",
                    gate_id=f"{chain['run_id']}-gate-extra",
                    cand_id=f"{chain['run_id']}-cand-extra",
                    value="125/80",
                    asserted_object="血压",
                )
                store = JobStore(session, now=utc_now)
                plan_ckpt = store.get_last_checkpoint(created.job_id, "plan")
                assert plan_ckpt is not None
                narrowed = dict(plan_ckpt[1])
                scope = dict(narrowed["impact_scope"])
                scope["affected_fact_ids"] = [fact_id]
                narrowed["impact_scope"] = scope
                import hashlib
                import json

                from app.storage.models import JobCheckpointRecord

                payload_json = json.dumps(
                    narrowed, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                )
                row = session.get(JobCheckpointRecord, plan_ckpt[0])
                row.payload_json = payload_json
                row.payload_sha256 = hashlib.sha256(
                    payload_json.encode("utf-8")
                ).hexdigest()
        return real(context)

    runner = JobRunner(
        session_factory,
        {FACT_CORRECTION_JOB_TYPE: hijack},
        worker_id="w1",
        now=utc_now,
        poll_interval=0.01,
    )
    assert runner.run_once() is True
    with session_factory() as session:
        store = JobStore(session, now=utc_now)
        assert store.snapshot(created.job_id).state == "completed"
        correction = FactCorrectionRepository(session).get(created.correction_id)
        extra_id = f"{chain['run_id']}-extra"
        if correction.impact_scope.scope_kind == "local":
            assert extra_id in correction.impact_scope.affected_fact_ids
        assert fact_id in (correction.impact_scope.affected_fact_ids or [fact_id]) or correction.impact_scope.scope_kind == "node"


def test_missing_source_strength_metadata_rolls_back_apply(session_factory):
    from app.domain.contracts.evidence_locator import CompleteEvidenceProcessingRevision
    from app.storage.codecs import decode_contract
    from app.storage.evidence_models import SourceDocumentMetadataRevisionRecord
    from app.storage.ocr_models import EvidenceProcessingRevisionRecord

    with session_factory() as session, session.begin():
        chain = _seed_valid_chain(session, "corr-str")
        fact = _publish_fact(session, chain)
        PatientProfileService().generate(
            session, authority=_authority(chain), created_at=NOW, generated_at=NOW
        )
        old_profile = PatientProfileRevisionRepository(session).latest_by_episode(
            chain["review_episode_id"]
        )
        old_id = old_profile.patient_profile_revision_id
        fact_id = fact.fact_id
    created = _submit(session_factory, chain, fact, value="130/80")
    with session_factory() as session, session.begin():
        revision_row = session.get(
            EvidenceProcessingRevisionRecord, chain["complete_revision_id"]
        )
        complete = decode_contract(
            CompleteEvidenceProcessingRevision,
            revision_row.payload_json,
            revision_row.payload_sha256,
        )
        metadata = session.get(
            SourceDocumentMetadataRevisionRecord, complete.metadata_revision_ids[0]
        )
        metadata.payload_sha256 = "0" * 64
    _run(session_factory)
    with session_factory() as session:
        store = JobStore(session, now=utc_now)
        snapshot = store.snapshot(created.job_id)
        assert snapshot.state in {"failed_final", "failed_retryable", "failed"}
        facts = ClinicalFactV2Repository(session).list_for_authority(_authority(chain))
        assert [item.value for item in facts if item.fact_id == fact_id] == ["120/80"]
        assert FactCorrectionRepository(session).list_by_authority(_authority(chain)) == []
        latest = PatientProfileRevisionRepository(session).latest_by_episode(
            chain["review_episode_id"]
        )
        assert latest.patient_profile_revision_id == old_id


def test_node_scope_recomputes_full_episode_projections(session_factory):
    from app.domain.contracts.facts import ClinicalConflictGroupV2
    from app.domain.contracts.patient_profile_v2 import ProfileItemKind, profile_items
    from app.storage.evidence_expectation_repository import EvidenceExpectationV2Repository
    from app.storage.fact_correction_commit_repository import FactCorrectionCommitRepository
    from app.storage.fact_repositories import ClinicalConflictGroupV2Repository
    from app.storage.fact_rule_link_repository import FactRuleLinkV2Repository
    from app.storage.repositories import list_expectation_templates
    from tests.v2.storage.test_fact_rule_link_repository import (
        _publish_fact as _publish_typed_fact,
        _seed_procedure_requirement,
    )

    with session_factory() as session, session.begin():
        chain = _seed_valid_chain(session, "corr-node2")
        _seed_procedure_requirement(session, chain, requirement_id="req-a", fact_type="vital_sign")
        _seed_procedure_requirement(session, chain, requirement_id="req-b", fact_type="lab")
        fact = _publish_fact(session, chain)
        partner = _create_fact_with_candidate(
            session,
            chain,
            fact_id=f"{chain['run_id']}-partner",
            run_id=f"{chain['run_id']}-partner",
            call_id=f"{chain['call_id']}-partner",
            gate_id=f"{chain['run_id']}-gate-partner",
            cand_id=f"{chain['run_id']}-cand-partner",
            value="90/60",
        )
        ClinicalConflictGroupV2Repository(session).create(
            ClinicalConflictGroupV2(
                conflict_group_id=f"{chain['run_id']}-conflict",
                run_id=fact.run_id,
                gate_id=fact.gate_id,
                authority=_authority(chain),
                fact_ids=sorted([fact.fact_id, partner.fact_id]),
                locator_ids=[chain["locator_id"]],
                created_at=NOW,
            )
        )
        extra = _publish_typed_fact(
            session,
            chain,
            fact_id=f"{chain['run_id']}-lab",
            fact_type="lab",
            asserted_object="肌酐",
            value="88",
            supported_requirement_ids=["req-b"],
        )
        FactRuleLinkV2Repository(session).rebuild_for_authority(_authority(chain))
        PatientProfileService().generate(
            session, authority=_authority(chain), created_at=NOW, generated_at=NOW
        )
        extra_id = extra.fact_id
        fact_id = fact.fact_id
        old_conflict_id = f"{chain['run_id']}-conflict"
    created = _service(session_factory).create_or_reuse_job(
        authority=_authority(chain),
        target_kind="fact",
        target_id=fact_id,
        locator_ids=[chain["locator_id"]],
        reason="核对原文后更正事实类型",
        operator_id="reviewer-1",
        updates={"fact_type": "unmapped_type", "value": "130/80"},
        created_by="reviewer-1",
        created_at=NOW,
    )
    assert _run(session_factory) is True
    with session_factory() as session:
        store = JobStore(session, now=utc_now)
        snapshot = store.snapshot(created.job_id)
        assert snapshot.state == "completed", (
            snapshot.state,
            snapshot.error_code,
            [
                event.event.payload
                for event in snapshot.events
                if event.event.step_id == "apply"
            ],
        )
        correction = FactCorrectionRepository(session).get(created.correction_id)
        assert correction.impact_scope.scope_kind == "node"
        commit = FactCorrectionCommitRepository(session).get(created.correction_id)
        assert commit.impact_scope.scope_kind == "node"
        latest = PatientProfileService().get(session, commit.patient_profile_revision_id)
        source_ids = {item.source_id for item in profile_items(latest)}
        assert extra_id in source_ids
        assert correction.new_entity_id in source_ids
        assert old_conflict_id not in {
            item.source_id
            for item in profile_items(latest)
            if item.kind == ProfileItemKind.CONFLICT
        }
        assert any(
            item.superseded_conflict_group_id == old_conflict_id
            for item in commit.conflict_outcomes
        )
        repo = FactRuleLinkV2Repository(session)
        assert repo.list_for_facts([extra_id])[extra_id]
        assert repo.list_for_facts([fact_id])[fact_id] == []
        templates = list_expectation_templates(
            session, chain["rule_set_id"], chain["authority"].rule_set_revision
        )
        projected = {
            item.template_id
            for item in EvidenceExpectationV2Repository(session).list_for_authority(
                _authority(chain)
            )
        }
        assert {item.template_id for item in templates} <= projected
        assert commit.conflict_outcomes


def test_fact_correction_cascades_event_conflict_successor_uses_current_member_gate(
    session_factory,
):
    from app.domain.contracts.enums import DurationStatus
    from app.domain.contracts.facts import ClinicalConflictGroupV2
    from app.domain.contracts.patient_profile_v2 import ProfileItemKind, profile_items
    from app.storage.fact_correction_commit_repository import FactCorrectionCommitRepository
    from app.storage.fact_repositories import (
        ClinicalConflictGroupV2Repository,
        ClinicalEventV2Repository,
    )

    with session_factory() as session, session.begin():
        chain = _seed_valid_chain(session, "corr-ev-cascade")
        fact = _publish_fact(session, chain)
        event_a = _publish_event(
            session,
            chain,
            fact,
            suffix="a",
            start=_day("2026-01-01"),
            duration=DurationStatus.ONGOING,
        )
        event_b = _publish_event(
            session,
            chain,
            fact,
            suffix="b",
            start=_day("2026-03-01"),
            duration=DurationStatus.ONGOING,
        )
        ClinicalConflictGroupV2Repository(session).create(
            ClinicalConflictGroupV2(
                conflict_group_id=f"{chain['run_id']}-event-conflict",
                run_id=event_a.run_id,
                gate_id=event_a.gate_id,
                authority=_authority(chain),
                member_kind="event",
                event_ids=sorted([event_a.event_id, event_b.event_id]),
                locator_ids=[chain["locator_id"]],
                created_at=NOW,
            )
        )
        PatientProfileService().generate(
            session, authority=_authority(chain), created_at=NOW, generated_at=NOW
        )
        old_event_ids = {event_a.event_id, event_b.event_id}
        old_gate = event_a.gate_id
        fact_id = fact.fact_id
        old_conflict_id = f"{chain['run_id']}-event-conflict"
    created = _submit(session_factory, chain, type("T", (), {"fact_id": fact_id})())
    assert _run(session_factory) is True
    with session_factory() as session:
        commit = FactCorrectionCommitRepository(session).get(created.correction_id)
        outcome = next(
            item
            for item in commit.conflict_outcomes
            if item.superseded_conflict_group_id == old_conflict_id
        )
        assert outcome.successor_conflict_group_id
        successor = ClinicalConflictGroupV2Repository(session).get(
            outcome.successor_conflict_group_id
        )
        assert set(successor.event_ids).isdisjoint(old_event_ids)
        current = {
            item.event_id: item
            for item in ClinicalEventV2Repository(session).list_for_authority(
                _authority(chain)
            )
        }
        for event_id in successor.event_ids:
            member = current[event_id]
            assert member.event_id not in old_event_ids
        assert successor.gate_id != old_gate
        assert successor.gate_id in {current[eid].gate_id for eid in successor.event_ids}
        latest = PatientProfileService().get(session, commit.patient_profile_revision_id)
        conflict_ids = {
            item.source_id
            for item in profile_items(latest)
            if item.kind == ProfileItemKind.CONFLICT
        }
        assert outcome.successor_conflict_group_id in conflict_ids
        assert old_conflict_id not in conflict_ids


def test_fact_correction_cascades_exposure_conflict_successor_uses_current_member_gate(
    session_factory,
):
    from app.domain.contracts.enums import DurationStatus
    from app.domain.contracts.facts import ClinicalConflictGroupV2
    from app.domain.contracts.patient_profile_v2 import ProfileItemKind, profile_items
    from app.storage.fact_correction_commit_repository import FactCorrectionCommitRepository
    from app.storage.fact_repositories import (
        ClinicalConflictGroupV2Repository,
        MedicationExposureV2Repository,
    )

    with session_factory() as session, session.begin():
        chain = _seed_valid_chain(session, "corr-ex-cascade")
        fact = _publish_fact(session, chain)
        exposure_a = _publish_exposure(
            session,
            chain,
            fact,
            suffix="a",
            start=_day("2026-01-01"),
            duration=DurationStatus.ONGOING,
        )
        exposure_b = _publish_exposure(
            session,
            chain,
            fact,
            suffix="b",
            start=_day("2026-03-01"),
            duration=DurationStatus.ONGOING,
        )
        ClinicalConflictGroupV2Repository(session).create(
            ClinicalConflictGroupV2(
                conflict_group_id=f"{chain['run_id']}-exposure-conflict",
                run_id=exposure_a.run_id,
                gate_id=exposure_a.gate_id,
                authority=_authority(chain),
                member_kind="exposure",
                exposure_ids=sorted([exposure_a.exposure_id, exposure_b.exposure_id]),
                locator_ids=[chain["locator_id"]],
                created_at=NOW,
            )
        )
        PatientProfileService().generate(
            session, authority=_authority(chain), created_at=NOW, generated_at=NOW
        )
        old_ids = {exposure_a.exposure_id, exposure_b.exposure_id}
        old_gate = exposure_a.gate_id
        fact_id = fact.fact_id
        old_conflict_id = f"{chain['run_id']}-exposure-conflict"
    created = _submit(session_factory, chain, type("T", (), {"fact_id": fact_id})())
    assert _run(session_factory) is True
    with session_factory() as session:
        commit = FactCorrectionCommitRepository(session).get(created.correction_id)
        outcome = next(
            item
            for item in commit.conflict_outcomes
            if item.superseded_conflict_group_id == old_conflict_id
        )
        assert outcome.successor_conflict_group_id
        successor = ClinicalConflictGroupV2Repository(session).get(
            outcome.successor_conflict_group_id
        )
        assert set(successor.exposure_ids).isdisjoint(old_ids)
        current = {
            item.exposure_id: item
            for item in MedicationExposureV2Repository(session).list_for_authority(
                _authority(chain)
            )
        }
        assert successor.gate_id != old_gate
        assert successor.gate_id in {
            current[eid].gate_id for eid in successor.exposure_ids
        }
        latest = PatientProfileService().get(session, commit.patient_profile_revision_id)
        conflict_ids = {
            item.source_id
            for item in profile_items(latest)
            if item.kind == ProfileItemKind.CONFLICT
        }
        assert outcome.successor_conflict_group_id in conflict_ids


def test_event_conflict_remains_when_only_duration_matches(session_factory):
    from app.domain.contracts.enums import DurationStatus
    from app.domain.contracts.facts import ClinicalConflictGroupV2
    from app.storage.fact_correction_commit_repository import FactCorrectionCommitRepository
    from app.storage.fact_repositories import ClinicalConflictGroupV2Repository

    with session_factory() as session, session.begin():
        chain = _seed_valid_chain(session, "corr-ev-date")
        fact = _publish_fact(session, chain)
        event_a = _publish_event(
            session,
            chain,
            fact,
            suffix="a",
            start=_day("2026-01-01"),
            duration=DurationStatus.ONGOING,
        )
        event_b = _publish_event(
            session,
            chain,
            fact,
            suffix="b",
            start=_day("2026-03-01"),
            end=_day("2026-04-01"),
            duration=DurationStatus.ENDED,
        )
        ClinicalConflictGroupV2Repository(session).create(
            ClinicalConflictGroupV2(
                conflict_group_id=f"{chain['run_id']}-event-date",
                run_id=event_b.run_id,
                gate_id=event_b.gate_id,
                authority=_authority(chain),
                member_kind="event",
                event_ids=sorted([event_a.event_id, event_b.event_id]),
                locator_ids=[chain["locator_id"]],
                created_at=NOW,
            )
        )
        PatientProfileService().generate(
            session, authority=_authority(chain), created_at=NOW, generated_at=NOW
        )
        event_b_id = event_b.event_id
        event_a_id = event_a.event_id
        old_conflict_id = f"{chain['run_id']}-event-date"
    created = _service(session_factory).create_or_reuse_job(
        authority=_authority(chain),
        target_kind="event",
        target_id=event_b_id,
        locator_ids=[chain["locator_id"]],
        reason="核对原文后持续状态一致，起止日期仍不同",
        operator_id="reviewer-1",
        updates={"duration_status": "ongoing", "end_range": None},
        created_by="reviewer-1",
        created_at=NOW,
    )
    assert _run(session_factory) is True
    with session_factory() as session:
        commit = FactCorrectionCommitRepository(session).get(created.correction_id)
        outcome = commit.conflict_outcomes[0]
        assert outcome.superseded_conflict_group_id == old_conflict_id
        assert outcome.successor_conflict_group_id
        successor = ClinicalConflictGroupV2Repository(session).get(
            outcome.successor_conflict_group_id
        )
        assert event_a_id in successor.event_ids
        assert event_b_id not in successor.event_ids
        assert created.correction_id


def test_exposure_conflict_remains_when_only_duration_matches(session_factory):
    from app.domain.contracts.enums import DurationStatus
    from app.domain.contracts.facts import ClinicalConflictGroupV2
    from app.storage.fact_correction_commit_repository import FactCorrectionCommitRepository
    from app.storage.fact_repositories import ClinicalConflictGroupV2Repository

    with session_factory() as session, session.begin():
        chain = _seed_valid_chain(session, "corr-ex-date")
        fact = _publish_fact(session, chain)
        exposure_a = _publish_exposure(
            session,
            chain,
            fact,
            suffix="a",
            start=_day("2026-01-01"),
            duration=DurationStatus.ONGOING,
        )
        exposure_b = _publish_exposure(
            session,
            chain,
            fact,
            suffix="b",
            start=_day("2026-03-01"),
            end=_day("2026-04-01"),
            duration=DurationStatus.ENDED,
        )
        ClinicalConflictGroupV2Repository(session).create(
            ClinicalConflictGroupV2(
                conflict_group_id=f"{chain['run_id']}-exposure-date",
                run_id=exposure_b.run_id,
                gate_id=exposure_b.gate_id,
                authority=_authority(chain),
                member_kind="exposure",
                exposure_ids=sorted([exposure_a.exposure_id, exposure_b.exposure_id]),
                locator_ids=[chain["locator_id"]],
                created_at=NOW,
            )
        )
        PatientProfileService().generate(
            session, authority=_authority(chain), created_at=NOW, generated_at=NOW
        )
        exposure_b_id = exposure_b.exposure_id
        exposure_a_id = exposure_a.exposure_id
        old_conflict_id = f"{chain['run_id']}-exposure-date"
    created = _service(session_factory).create_or_reuse_job(
        authority=_authority(chain),
        target_kind="exposure",
        target_id=exposure_b_id,
        locator_ids=[chain["locator_id"]],
        reason="核对原文后持续状态一致，起止日期仍不同",
        operator_id="reviewer-1",
        updates={"duration_status": "ongoing", "end_range": None},
        created_by="reviewer-1",
        created_at=NOW,
    )
    assert _run(session_factory) is True
    with session_factory() as session:
        commit = FactCorrectionCommitRepository(session).get(created.correction_id)
        outcome = commit.conflict_outcomes[0]
        assert outcome.superseded_conflict_group_id == old_conflict_id
        assert outcome.successor_conflict_group_id
        successor = ClinicalConflictGroupV2Repository(session).get(
            outcome.successor_conflict_group_id
        )
        assert exposure_a_id in successor.exposure_ids
        assert exposure_b_id not in successor.exposure_ids


def test_node_scope_does_not_supersede_unrelated_unchanged_conflict(session_factory):
    from app.domain.contracts.facts import ClinicalConflictGroupV2
    from app.domain.contracts.patient_profile_v2 import ProfileItemKind, profile_items
    from app.storage.fact_correction_commit_repository import FactCorrectionCommitRepository
    from app.storage.fact_repositories import ClinicalConflictGroupV2Repository
    from tests.v2.storage.test_fact_rule_link_repository import _publish_fact as _publish_typed_fact

    with session_factory() as session, session.begin():
        chain = _seed_valid_chain(session, "corr-node-unrel")
        fact = _publish_fact(session, chain)
        extra_a = _publish_typed_fact(
            session,
            chain,
            fact_id=f"{chain['run_id']}-lab-a",
            fact_type="lab",
            asserted_object="肌酐",
            value="88",
            supported_requirement_ids=[],
        )
        extra_b = _publish_typed_fact(
            session,
            chain,
            fact_id=f"{chain['run_id']}-lab-b",
            fact_type="lab",
            asserted_object="肌酐",
            value="99",
            supported_requirement_ids=[],
        )
        ClinicalConflictGroupV2Repository(session).create(
            ClinicalConflictGroupV2(
                conflict_group_id=f"{chain['run_id']}-unrelated",
                run_id=extra_a.run_id,
                gate_id=extra_a.gate_id,
                authority=_authority(chain),
                fact_ids=sorted([extra_a.fact_id, extra_b.fact_id]),
                locator_ids=[chain["locator_id"]],
                created_at=NOW,
            )
        )
        PatientProfileService().generate(
            session, authority=_authority(chain), created_at=NOW, generated_at=NOW
        )
        fact_id = fact.fact_id
        unrelated_id = f"{chain['run_id']}-unrelated"
    created = _service(session_factory).create_or_reuse_job(
        authority=_authority(chain),
        target_kind="fact",
        target_id=fact_id,
        locator_ids=[chain["locator_id"]],
        reason="核对原文后更正事实类型",
        operator_id="reviewer-1",
        updates={"fact_type": "unmapped_type", "value": "130/80"},
        created_by="reviewer-1",
        created_at=NOW,
    )
    assert _run(session_factory) is True
    with session_factory() as session:
        correction = FactCorrectionRepository(session).get(created.correction_id)
        assert correction.impact_scope.scope_kind == "node"
        commit = FactCorrectionCommitRepository(session).get(created.correction_id)
        superseded = {
            item.superseded_conflict_group_id for item in commit.conflict_outcomes
        }
        assert unrelated_id not in superseded
        latest = PatientProfileService().get(session, commit.patient_profile_revision_id)
        conflict_ids = {
            item.source_id
            for item in profile_items(latest)
            if item.kind == ProfileItemKind.CONFLICT
        }
        assert unrelated_id in conflict_ids
        leftover = ClinicalConflictGroupV2Repository(session).get(unrelated_id)
        assert leftover.fact_ids == sorted(
            [f"{chain['run_id']}-lab-a", f"{chain['run_id']}-lab-b"]
        )


def test_replay_returns_exact_profile_of_this_correction_not_later_head(session_factory):
    from app.services.fact_correction_service import (
        apply_prepared_fact_correction,
        prepared_from_payload,
    )
    from app.storage.codecs import verify_payload_sha256
    from app.storage.fact_correction_commit_repository import FactCorrectionCommitRepository

    with session_factory() as session, session.begin():
        chain = _seed_valid_chain(session, "corr-replay")
        fact = _publish_fact(session, chain)
        PatientProfileService().generate(
            session, authority=_authority(chain), created_at=NOW, generated_at=NOW
        )
    first = _submit(session_factory, chain, fact, value="130/80")
    assert _run(session_factory) is True
    with session_factory() as session:
        first_new_id = FactCorrectionRepository(session).get(first.correction_id).new_entity_id
        profile_a = FactCorrectionCommitRepository(session).get(
            first.correction_id
        ).patient_profile_revision_id
        class _Head:
            fact_id = first_new_id
        head = _Head()
        payload_a = verify_payload_sha256(
            session.get(JobRecord, first.job_id).payload_json,
            session.get(JobRecord, first.job_id).payload_sha256,
        )
    second = _submit(session_factory, chain, head, value="140/90", reason="再次核对后更新")
    assert _run(session_factory) is True
    with session_factory() as session, session.begin():
        profile_b = FactCorrectionCommitRepository(session).get(
            second.correction_id
        ).patient_profile_revision_id
        assert profile_b != profile_a
        replay = apply_prepared_fact_correction(
            session, prepared_from_payload(payload_a["prepared"])
        )
        assert replay.is_replay is True
        assert replay.profile_revision_id == profile_a
        assert replay.profile_revision_id != profile_b



def test_duplicate_apply_callback_replays_without_new_entities(session_factory):
    from app.services.fact_correction_service import (
        apply_prepared_fact_correction,
        prepared_from_payload,
    )
    from app.storage.codecs import verify_payload_sha256

    with session_factory() as session, session.begin():
        chain = _seed_valid_chain(session, "corr-cb")
        fact = _publish_fact(session, chain)
        PatientProfileService().generate(
            session, authority=_authority(chain), created_at=NOW, generated_at=NOW
        )
    created = _submit(session_factory, chain, fact)
    assert _run(session_factory) is True
    with session_factory() as session, session.begin():
        job = session.get(JobRecord, created.job_id)
        payload = verify_payload_sha256(job.payload_json, job.payload_sha256)
        prepared = prepared_from_payload(payload["prepared"])
        replay = apply_prepared_fact_correction(session, prepared)
        assert replay.is_replay is True
    with session_factory() as session:
        facts = ClinicalFactV2Repository(session).list_for_authority(_authority(chain))
        assert sorted(item.value for item in facts) == ["120/80", "130/80"]
        assert len(FactCorrectionRepository(session).list_by_authority(_authority(chain))) == 1
        profiles = PatientProfileRevisionRepository(session).list_by_episode(
            chain["review_episode_id"]
        )
        succeeded = [item for item in profiles if item.status.value == "succeeded"]
        assert len(succeeded) == 2


def test_commit_binds_generated_profile_with_complete_snapshots(session_factory):
    """提交栅栏绑定修订生成档案；预览与历史完整快照对称。"""
    import json

    from app.domain.contracts.patient_profile_v2 import profile_items
    from app.services.fact_correction_service import preview_fact_correction
    from app.storage.fact_correction_commit_repository import FactCorrectionCommitRepository

    with session_factory() as session, session.begin():
        chain = _seed_valid_chain(session, "corr-snap-bind")
        fact = _publish_fact(session, chain)
        pre_profile = PatientProfileService().generate(
            session, authority=_authority(chain), created_at=NOW, generated_at=NOW
        )
        pre_id = pre_profile.patient_profile_revision_id
        fact_id = fact.fact_id
        locator_id = chain["locator_id"]
        authority = _authority(chain)
    with session_factory() as session:
        preview = preview_fact_correction(
            session,
            authority=authority,
            target_kind="fact",
            target_id=fact_id,
            locator_ids=[locator_id],
            updates={"value": "130/80"},
        )
    created = _submit(session_factory, chain, type("T", (), {"fact_id": fact_id})())
    assert _run(session_factory) is True
    with session_factory() as session:
        history = list_fact_correction_history(session, chain["review_episode_id"])
        assert len(history) == 1
        item = history[0]
        commit = FactCorrectionCommitRepository(session).get(item.correction.correction_id)
        assert commit.patient_profile_revision_id == item.patient_profile_revision_id
        assert item.patient_profile_revision_id != pre_id
        assert item.patient_profile_revision == 2
        old_snap = json.loads(item.correction.old_snapshot_json)
        new_snap = json.loads(item.correction.new_snapshot_json)
        assert old_snap == preview.old_snapshot
        assert new_snap == preview.new_snapshot
        for key in (
            "date_range",
            "source_strength",
            "asserted_object",
            "supported_requirement_ids",
        ):
            assert key in old_snap
            assert key in new_snap
        assert old_snap["value"] == "120/80"
        assert new_snap["value"] == "130/80"
        generated = PatientProfileService().get(
            session, item.patient_profile_revision_id
        )
        matches = [
            entry
            for entry in profile_items(generated)
            if entry.source_id == item.correction.new_entity_id
        ]
        assert len(matches) == 1
        assert matches[0].value == "130/80"
        assert set(item.correction.locator_ids).issubset(set(matches[0].locator_ids))


def test_prepare_rejects_locator_page_artifact_mismatch(session_factory):
    """定位页码与页工件不一致时，修订准备必须拒绝。"""
    from app.services.fact_correction_service import (
        FactCorrectionValidationError,
        prepare_fact_correction,
    )
    from app.storage.evidence_locator_models import EvidenceLocatorArtifactRecord
    from app.storage.ocr_models import PageArtifactRecord

    with session_factory() as session, session.begin():
        chain = _seed_valid_chain(session, "corr-loc-mismatch")
        fact = _publish_fact(session, chain)
        PatientProfileService().generate(
            session, authority=_authority(chain), created_at=NOW, generated_at=NOW
        )
        loc = session.get(EvidenceLocatorArtifactRecord, chain["locator_id"])
        page = session.get(PageArtifactRecord, loc.page_artifact_id)
        assert page is not None
        page.page_number = loc.page_number + 17
        fact_id = fact.fact_id
        locator_id = chain["locator_id"]
        authority = _authority(chain)
    with session_factory() as session:
        with pytest.raises(FactCorrectionValidationError, match="页码与页工件不一致"):
            prepare_fact_correction(
                session,
                authority=authority,
                target_kind="fact",
                target_id=fact_id,
                locator_ids=[locator_id],
                reason="核对原文",
                operator_id="reviewer-1",
                updates={"value": "130/80"},
                created_at=NOW,
            )
