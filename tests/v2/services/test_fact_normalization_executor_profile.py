"""事实规范化 finalize 与 Patient Profile 同事务集成（Slice 5.8 / worker_02）。"""
from __future__ import annotations

import json

from sqlalchemy import select, update

import pytest

from app.domain.contracts.enums import (
    DurationStatus,
    ExpectationStatus,
    ProfileLane,
    ReviewStage,
)
from app.domain.contracts.evidence_normalizer import EvidenceNormalizerOutput
from app.domain.contracts.facts import ClinicalEventCandidateV2
from app.domain.contracts.patient_profile_v2 import ProfileStatus
from app.domain.contracts.review import ReviewEpisode
from app.services.fact_normalization_executor import (
    FactNormalizationExecutorConfig,
    _profile_lane_conflict_reasons,
    create_fact_normalization_executor,
)
from app.services.fact_normalization_job_service import (
    FACT_NORMALIZATION_FINALIZE_STEP_ID,
    FactNormalizationJobService,
)
from app.services.patient_profile_service import (
    PatientProfileProjectionError,
    PatientProfileService,
)
from app.storage.codecs import decode_contract, encode_contract
from app.storage.evidence_expectation_repository import EvidenceExpectationV2Repository
from app.storage.fact_repositories import (
    ClinicalFactV2Repository,
)
from app.storage.facts_models import (
    ClinicalFactV2Record,
    EvidenceExpectationV2Record,
    FactRuleLinkV2Record,
    PatientProfileRevisionV2Record,
)
from app.storage.models import JobRecord, ReviewEpisodeRecord, WorkflowStageRecord
from app.storage.patient_profile_repository import PatientProfileRevisionRepository
from app.storage.repositories import EpisodeRepository
from app.workflow.errors import StepFailure
from app.workflow.jobstore import JobStore
from app.workflow.runner import JobRunner, PreparedStepResult, StepContext
from tests.v2.projections.test_evidence_expectations import _template
from tests.v2.services.test_fact_normalization_persistence import (
    _candidate_fact,
    _create_job_from_source,
    _seed_chain,
    _update_episode,
)


def _prepare(session_factory, *, prefix: str, requirement_id: str):
    with session_factory() as session:
        chain = _seed_chain(session, prefix=prefix)
        workflow_stage_id = session.execute(
            select(WorkflowStageRecord.workflow_stage_id).where(
                WorkflowStageRecord.protocol_version_id == chain["protocol_version_id"],
                WorkflowStageRecord.stage == "screening",
            )
        ).scalar_one()
        _update_episode(
            session,
            session.get(ReviewEpisodeRecord, chain["episode_id"]),
            workflow_stage_id=workflow_stage_id,
        )
        episode = EpisodeRepository(session).get(chain["episode_id"])
        template = _template(
            session,
            {
                **chain,
                "run_id": prefix,
                "workflow_stage_id": episode.workflow_stage_id,
            },
            requirement_id=requirement_id,
            fact_type="lab_result",
            due_stage=ReviewStage.SCREENING,
            requires_contemporaneous_objective_source=True,
        )
        session.commit()
    return chain, template


def _transport(chain, requirement_id):
    def transport(evidence_input):
        candidate = _candidate_fact(
            evidence_input.run_id, evidence_input.call_id, chain["locator_id"]
        ).model_copy(
            update={
                "raw_value": 5.0,
                "canonical_value": 5.0,
                "unit": "mmol/L",
                "supported_requirement_ids": [requirement_id],
            }
        )
        return EvidenceNormalizerOutput(
            run_id=evidence_input.run_id,
            call_id=evidence_input.call_id,
            logical_document_id=evidence_input.logical_document_id,
            page_numbers=evidence_input.page_numbers,
            fact_candidates=[candidate],
            event_candidates=[],
            exposure_candidates=[],
            unresolved_items=[],
        )

    return transport


def test_profile_lane_drift_rejects_only_conflicting_candidates(
    session_factory,
):
    with session_factory() as session, session.begin():
        chain = _seed_chain(session, prefix="lane-drift-gate")
        original = _candidate_fact(
            "lane-drift-run",
            "lane-drift-call",
            chain["locator_id"],
        ).model_copy(update={"profile_lane": ProfileLane.MEDICAL_HISTORY})
        drifted = original.model_copy(
            update={
                "candidate_id": "lane-drift-new-candidate",
                "profile_lane": ProfileLane.TEST_EXAM_SCORE,
            }
        )

        assert _profile_lane_conflict_reasons(
            session, chain["authority"], [original]
        ) == {}
        reasons = _profile_lane_conflict_reasons(
            session, chain["authority"], [original, drifted]
        )
        expected = [
            "同一临床事实在当前审核节点已有不同主题归属，当前候选未发布；"
            "请核对主题归属。"
        ]
        assert reasons == {
            original.candidate_id: expected,
            "lane-drift-new-candidate": [
                "同一临床事实在当前审核节点已有不同主题归属，当前候选未发布；"
                "请核对主题归属。"
            ]
        }


def test_profile_event_lane_drift_rejects_only_conflicting_events(session_factory):
    with session_factory() as session, session.begin():
        chain = _seed_chain(session, prefix="event-lane-drift-gate")
        fact = _candidate_fact(
            "event-lane-drift-run",
            "event-lane-drift-call",
            chain["locator_id"],
        )
        original = ClinicalEventCandidateV2(
            candidate_id="event-lane-original",
            run_id=fact.run_id,
            call_id=fact.call_id,
            event_type="临床事件",
            profile_lane=ProfileLane.MEDICATION,
            duration_status=DurationStatus.SINGLE,
            fact_candidate_ids=[fact.candidate_id],
            locator_ids=[chain["locator_id"]],
            candidate_source_semantics="当前研究病历直接记录",
            model_uncertainty=0.1,
            created_at=fact.created_at,
        )
        drifted = original.model_copy(
            update={
                "candidate_id": "event-lane-drifted",
                "profile_lane": ProfileLane.STUDY_MILESTONE,
            }
        )

        reasons = _profile_lane_conflict_reasons(
            session, chain["authority"], [fact], [original, drifted]
        )
        expected = [
            "同一临床事件在当前审核节点已有不同主题归属，当前候选未发布；"
            "请核对主题归属。"
        ]
        assert reasons == {
            original.candidate_id: expected,
            drifted.candidate_id: expected,
        }


def _run(session_factory, chain, requirement_id):
    service = FactNormalizationJobService(session_factory)
    created = _create_job_from_source(service, chain)
    runner = JobRunner(
        session_factory,
        {
            "fact_normalization": create_fact_normalization_executor(
                FactNormalizationExecutorConfig(
                    session_factory=session_factory,
                    transport_fn=_transport(chain, requirement_id),
                )
            )
        },
    )
    assert runner.run_job(created.job_id) is True
    return service, created


def test_failed_transport_retains_bound_receipt(
    session_factory, data_paths, monkeypatch,
):
    from app.evidence.artifacts import ArtifactStore
    import app.services.fact_normalization_executor as executor_module

    chain, _ = _prepare(
        session_factory, prefix="receipt-failure", requirement_id="receipt-rule"
    )
    service = FactNormalizationJobService(session_factory)
    created = _create_job_from_source(service, chain)
    artifacts = ArtifactStore(data_paths)

    def failed_factory(model_config, *, receipt_callback):
        receipt_callback({"error_type": "TimeoutError", "elapsed_seconds": 1.0})
        raise TimeoutError("injected transport setup failure")

    monkeypatch.setattr(
        executor_module, "evidence_normalizer_transport_from_model_config",
        failed_factory,
    )
    runner = JobRunner(session_factory, {
        "fact_normalization": create_fact_normalization_executor(
            FactNormalizationExecutorConfig(
                session_factory=session_factory, artifact_store=artifacts,
            )
        ),
    })
    runner.run_job(created.job_id)
    receipts = list((data_paths.root / "artifacts" / "raw_response").iterdir())
    assert receipts
    for path in receipts:
        receipt = json.loads(artifacts.read_by_sha("raw_response", path.name))
        assert receipt["job_id"] == created.job_id
        assert receipt["call_id"] and receipt["run_id"] and receipt["step_id"]
        assert receipt["error_type"] == "TimeoutError"
    with session_factory() as session:
        assert not PatientProfileRevisionRepository(session).list_by_episode(
            chain["episode_id"]
        )


def test_finalize_generates_immutable_succeeded_profile(session_factory):
    chain, template = _prepare(
        session_factory, prefix="fn-profile-ok", requirement_id="alt-profile-ok"
    )
    _service, created = _run(session_factory, chain, template.requirement_id)

    with session_factory() as session:
        assert JobStore(session).job_status(created.job_id).state == "completed"
        assert (
            len(ClinicalFactV2Repository(session).list_by_episode(chain["episode_id"]))
            == 1
        )
        expectations = EvidenceExpectationV2Repository(session).list_by_episode(
            chain["episode_id"]
        )
        assert len(expectations) == 1
        assert expectations[0].status == ExpectationStatus.OBSERVED

        profiles = PatientProfileRevisionRepository(session).list_by_episode(
            chain["episode_id"]
        )
        assert len(profiles) == 1
        profile = profiles[0]
        assert profile.status == ProfileStatus.SUCCEEDED
        assert profile.revision == 1
        assert profile.authority == chain["authority"]

        last = JobStore(session).get_last_checkpoint(
            created.job_id, FACT_NORMALIZATION_FINALIZE_STEP_ID
        )
        assert last is not None
        _checkpoint_id, finalize_checkpoint = last
        assert (
            finalize_checkpoint["patient_profile_revision_id"]
            == profile.patient_profile_revision_id
        )
        assert finalize_checkpoint["patient_profile_revision"] == profile.revision
        assert (
            finalize_checkpoint["patient_profile_status"]
            == ProfileStatus.SUCCEEDED.value
        )
        assert (
            finalize_checkpoint["patient_profile_pending_review_count"]
            == profile.pending_review_count
        )

        again = PatientProfileService().generate(session, authority=profile.authority)
        assert again.patient_profile_revision_id == profile.patient_profile_revision_id
        assert again.revision == 1
        assert (
            len(
                PatientProfileRevisionRepository(session).list_by_episode(
                    chain["episode_id"]
                )
            )
            == 1
        )


def test_finalize_replay_verifies_persisted_profile(session_factory):
    chain, template = _prepare(
        session_factory, prefix="fn-profile-replay", requirement_id="alt-profile-replay"
    )
    service, created = _run(session_factory, chain, template.requirement_id)

    with session_factory() as session:
        last = JobStore(session).get_last_checkpoint(
            created.job_id, FACT_NORMALIZATION_FINALIZE_STEP_ID
        )
        assert last is not None
        finalize_checkpoint = dict(last[1])
        profile_id = finalize_checkpoint["patient_profile_revision_id"]
        before_count = len(
            PatientProfileRevisionRepository(session).list_by_episode(chain["episode_id"])
        )

    job_payload = service.get_job(created.job_id)["payload"]
    executor = create_fact_normalization_executor(
        FactNormalizationExecutorConfig(session_factory=session_factory)
    )
    replayed = executor(
        StepContext(
            job_id=created.job_id,
            job_type="fact_normalization",
            job_payload=job_payload,
            step_id=FACT_NORMALIZATION_FINALIZE_STEP_ID,
            name="finalize",
            attempt=2,
            last_checkpoint_id="ckpt-replay",
            last_checkpoint=finalize_checkpoint,
            max_attempts=3,
        )
    )
    assert isinstance(replayed, dict)
    assert replayed["patient_profile_revision_id"] == profile_id
    assert (
        replayed["patient_profile_revision"]
        == finalize_checkpoint["patient_profile_revision"]
    )

    with session_factory() as session:
        after = PatientProfileRevisionRepository(session).list_by_episode(
            chain["episode_id"]
        )
        assert len(after) == before_count
        assert after[-1].patient_profile_revision_id == profile_id

    bad = dict(finalize_checkpoint)
    bad["patient_profile_revision"] = (
        int(finalize_checkpoint["patient_profile_revision"]) + 99
    )
    with pytest.raises(StepFailure) as exc:
        executor(
            StepContext(
                job_id=created.job_id,
                job_type="fact_normalization",
                job_payload=job_payload,
                step_id=FACT_NORMALIZATION_FINALIZE_STEP_ID,
                name="finalize",
                attempt=3,
                last_checkpoint_id="ckpt-bad",
                last_checkpoint=bad,
                max_attempts=3,
            )
        )
    assert exc.value.error_code == "PARTIAL_OUTPUT"


def test_finalize_stale_authority_rejects_without_profile(session_factory):
    chain, template = _prepare(
        session_factory, prefix="fn-profile-stale", requirement_id="alt-profile-stale"
    )
    service = FactNormalizationJobService(session_factory)
    created = _create_job_from_source(service, chain)

    with session_factory() as session:
        rec = session.get(ReviewEpisodeRecord, chain["episode_id"])
        decoded = decode_contract(ReviewEpisode, rec.payload_json, rec.payload_sha256)
        bumped = decoded.model_copy(update={"revision": decoded.revision + 1})
        payload_json, payload_sha256 = encode_contract(bumped)
        session.execute(
            update(ReviewEpisodeRecord)
            .where(ReviewEpisodeRecord.review_episode_id == chain["episode_id"])
            .values(
                payload_json=payload_json,
                payload_sha256=payload_sha256,
                revision=bumped.revision,
            )
        )
        session.commit()

    runner = JobRunner(
        session_factory,
        {
            "fact_normalization": create_fact_normalization_executor(
                FactNormalizationExecutorConfig(
                    session_factory=session_factory,
                    transport_fn=_transport(chain, template.requirement_id),
                )
            )
        },
    )
    assert runner.run_job(created.job_id) is True

    with session_factory() as session:
        job = session.get(JobRecord, created.job_id)
        assert job is not None
        assert job.state == "failed_final"
        assert (
            session.execute(
                select(ClinicalFactV2Record).where(
                    ClinicalFactV2Record.run_id == created.run_id
                )
            )
            .scalars()
            .all()
            == []
        )
        assert (
            session.execute(
                select(PatientProfileRevisionV2Record).where(
                    PatientProfileRevisionV2Record.review_episode_id
                    == chain["episode_id"]
                )
            )
            .scalars()
            .all()
            == []
        )


def test_finalize_rolls_back_when_profile_projection_fails(session_factory, monkeypatch):
    chain, template = _prepare(
        session_factory, prefix="fn-profile-fail", requirement_id="alt-profile-fail"
    )

    def boom(
        self,
        session,
        *,
        authority,
        created_at=None,
        generated_at=None,
        exclude_conflict_group_ids=None,
        run_id=None,
    ):
        raise PatientProfileProjectionError("forced profile projection failure")

    monkeypatch.setattr(PatientProfileService, "generate", boom)

    service = FactNormalizationJobService(session_factory)
    created = _create_job_from_source(service, chain)
    runner = JobRunner(
        session_factory,
        {
            "fact_normalization": create_fact_normalization_executor(
                FactNormalizationExecutorConfig(
                    session_factory=session_factory,
                    transport_fn=_transport(chain, template.requirement_id),
                )
            )
        },
    )
    assert runner.run_job(created.job_id) is True

    with session_factory() as session:
        job = session.get(JobRecord, created.job_id)
        assert job is not None
        assert job.state == "failed_final"
        assert (
            session.execute(
                select(ClinicalFactV2Record).where(
                    ClinicalFactV2Record.run_id == created.run_id
                )
            )
            .scalars()
            .all()
            == []
        )
        assert session.execute(select(FactRuleLinkV2Record)).scalars().all() == []
        assert (
            session.execute(select(EvidenceExpectationV2Record)).scalars().all() == []
        )
        assert (
            session.execute(
                select(PatientProfileRevisionV2Record).where(
                    PatientProfileRevisionV2Record.review_episode_id
                    == chain["episode_id"]
                )
            )
            .scalars()
            .all()
            == []
        )


def test_finalize_profile_failure_preserves_prior_succeeded_profile(
    session_factory, monkeypatch
):
    """先前成功的 Profile 在后续 finalize 的 Profile 投影失败后保持可读且不被替换。"""
    chain, template = _prepare(
        session_factory, prefix="fn-profile-keep", requirement_id="alt-profile-keep"
    )
    service, created = _run(session_factory, chain, template.requirement_id)

    with session_factory() as session:
        prior = PatientProfileRevisionRepository(session).latest_by_episode(
            chain["episode_id"]
        )
        assert prior is not None
        assert prior.status == ProfileStatus.SUCCEEDED
        prior_id = prior.patient_profile_revision_id
        prior_revision = prior.revision
        prior_row = session.get(PatientProfileRevisionV2Record, prior_id)
        assert prior_row is not None
        prior_sha = prior_row.payload_sha256
        authority = prior.authority

    def boom(
        self,
        session,
        *,
        authority,
        created_at=None,
        generated_at=None,
        exclude_conflict_group_ids=None,
        run_id=None,
    ):
        raise PatientProfileProjectionError("second finalize profile failure")

    monkeypatch.setattr(PatientProfileService, "generate", boom)

    # 在独立事务中模拟 finalize 末尾的 Profile 生成失败：
    # 若误写了新的失败/生成中状态或新 revision，回滚后先前成功档案必须原样保留。
    with session_factory() as session:
        with pytest.raises(PatientProfileProjectionError):
            with session.begin():
                PatientProfileService().record_status(
                    session,
                    authority=authority,
                    status=ProfileStatus.GENERATING,
                )
                PatientProfileService().generate(session, authority=authority)

    with session_factory() as session:
        latest = PatientProfileRevisionRepository(session).latest_by_episode(
            chain["episode_id"]
        )
        assert latest is not None
        assert latest.patient_profile_revision_id == prior_id
        assert latest.revision == prior_revision
        row = session.get(PatientProfileRevisionV2Record, prior_id)
        assert row is not None
        assert row.payload_sha256 == prior_sha
        assert row.status == ProfileStatus.SUCCEEDED.value
        profiles = PatientProfileRevisionRepository(session).list_by_episode(
            chain["episode_id"]
        )
        assert len(profiles) == 1
        assert all(item.status == ProfileStatus.SUCCEEDED for item in profiles)
