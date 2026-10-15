"""事实规范化 finalize 与 Patient Profile 同事务集成（Slice 5.8 / worker_02）。"""
from __future__ import annotations

import json
import hashlib
from types import SimpleNamespace

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
from app.services.fact_publication_service import FactPublicationError, FactPublicationService
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
from app.storage.repositories import EpisodeRepository, InvalidReferenceError
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


def _targeted_job(session_factory, chain):
    from app.services.fact_normalization_source_adapter import build_fact_normalization_plan
    from app.services.fact_normalization_job_service import FactNormalizationCallSpec
    with session_factory() as session:
        plan, _ = build_fact_normalization_plan(session, authority=chain["authority"],
                                               revision_id=chain["authority"].complete_processing_revision_id)
    return FactNormalizationJobService(session_factory).create_or_reuse_job(
        authority=chain["authority"], prompt_version_id=chain["prompt_version_id"],
        model_config_id=chain["model_config_id"], created_by="tester",
        calls=[FactNormalizationCallSpec.from_planned_call(call) for call in plan.calls],
        targeted_extraction=True,
    )


def test_targeted_format_failure_retains_failed_call_and_partial_run(session_factory):
    from app.storage.fact_repositories import FactNormalizationRunRepository, FactNormalizationCallRepository
    chain, _ = _prepare(session_factory, prefix="targeted-format-failure", requirement_id="req-failure")
    created = _targeted_job(session_factory, chain)
    attempts = []

    def invalid(evidence_input):
        attempts.append(evidence_input.call_id)
        raise ValueError("合成格式失败，不是研究者判断")

    executor = create_fact_normalization_executor(FactNormalizationExecutorConfig(
        session_factory=session_factory, transport_fn=invalid))
    runner = JobRunner(session_factory, {"fact_normalization": executor})
    assert runner.run_job(created.job_id)
    with session_factory() as session:
        run = FactNormalizationRunRepository(session).get(created.run_id)
        calls = FactNormalizationCallRepository(session).list_by_run(created.run_id)
        assert run.status.value == "partial"
        assert len(calls) == 1 and calls[0].status.value == "failed"
        assert calls[0].reading_method is None and calls[0].raw_output_sha256 is None
        checkpoint = JobStore(session).get_last_checkpoint(created.job_id, FACT_NORMALIZATION_FINALIZE_STEP_ID)[1]
        assert checkpoint["unread_page_refs"]
        call_step = next(s for s in JobStore(session).list_steps(created.job_id)
                         if s.step_id != FACT_NORMALIZATION_FINALIZE_STEP_ID)
        payload = json.loads(session.get(JobRecord, created.job_id).payload_json)
        call_checkpoint = JobStore(session).get_last_checkpoint(created.job_id, call_step.step_id)[1]
    replay = executor(StepContext(job_id=created.job_id, step_id=call_step.step_id,
        job_type="fact_normalization", name=call_step.name, last_checkpoint_id=None,
        attempt=2, job_payload=payload, last_checkpoint=call_checkpoint))
    assert replay["call_status"] == "failed"
    assert len(attempts) == 1  # The injected adapter has no inner model retry; replay never calls it.


def test_failed_page_continuation_preserves_old_terminal_and_has_derived_scope(session_factory, monkeypatch):
    from dataclasses import replace
    from app.services import fact_normalization_source_adapter as source_module
    from app.domain.variables.dictionary import load_dictionary
    from app.workflow.errors import InvalidJobDefinitionError
    chain, _ = _prepare(session_factory, prefix="failed-page-continuation", requirement_id="req-continuation")
    original = _targeted_job(session_factory, chain)
    runner = JobRunner(session_factory, {"fact_normalization": create_fact_normalization_executor(
        FactNormalizationExecutorConfig(session_factory=session_factory,
            transport_fn=lambda _input: (_ for _ in ()).throw(ValueError("synthetic invalid output"))))})
    assert runner.run_job(original.job_id)
    service = FactNormalizationJobService(session_factory)
    before = service.get_job(original.job_id)
    build = source_module.build_fact_normalization_plan
    def targeted(*args, **kwargs):
        from app.domain.planning.fact_normalization_planning import compute_call_input_hash
        plan, source = build(*args, **kwargs)
        variables = (load_dictionary()["age"],)
        return replace(plan, calls=tuple(replace(call, variable_definitions=variables,
            input_sha256=compute_call_input_hash(authority=plan.authority, revision=source.revision,
                logical_document_id=call.logical_document_id, context=call.context,
                related_requirements=call.related_requirements, page_numbers=list(call.page_numbers),
                page_inputs=list(call.page_inputs), variable_definitions=variables)) for call in plan.calls)), source
    monkeypatch.setattr(source_module, "build_fact_normalization_plan", targeted)
    kwargs = dict(authority=chain["authority"], prompt_version_id=chain["prompt_version_id"],
        model_config_id=chain["model_config_id"], created_by="tester", retry_failed_from_run_id=original.run_id)
    continued = service.create_or_reuse_from_source(**kwargs)
    payload = service.get_job(continued.job_id)["payload"]
    assert continued.job_id != original.job_id and len(payload["calls"]) == 1
    assert payload["retry_failed_from_run_id"] == original.run_id
    assert payload["targeted_extraction"] and payload["candidate_partition_policy"]
    assert service.create_or_reuse_from_source(**kwargs).job_id == continued.job_id
    assert service.get_job(original.job_id) == before
    selected_pages = [(row["logical_document_id"], page) for row in payload["calls"] for page in row["page_numbers"]]
    limited = service.create_or_reuse_from_source(**kwargs, retry_pages=selected_pages)
    limited_payload = service.get_job(limited.job_id)["payload"]
    assert limited.job_id != continued.job_id
    assert limited_payload["retry_pages"] == [list(page) for page in selected_pages]
    assert service.create_or_reuse_from_source(**kwargs, retry_pages=selected_pages).job_id == limited.job_id
    with pytest.raises(InvalidJobDefinitionError, match="待核页面"):
        service.create_or_reuse_from_source(**kwargs, retry_pages=[("other-document", 1)])
    from app.services.fact_normalization_job_service import FactNormalizationCallSpec, _validate_call_specs
    separated = [FactNormalizationCallSpec(logical_document_id="doc", page_numbers=[page], input_sha256="a" * 64)
                 for page in (3, 8)]
    with pytest.raises(InvalidJobDefinitionError, match="间隙"):
        _validate_call_specs(separated)
    _validate_call_specs(separated, allow_gaps=True)
    with pytest.raises(InvalidJobDefinitionError, match="重复"):
        _validate_call_specs(separated + separated[:1], allow_gaps=True)
    from app.services.fact_normalization_executor import _load_frozen_agent_config
    from app.agents.evidence_normalizer import DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE
    with session_factory() as session:
        _load_frozen_agent_config(session, payload=limited_payload, run_id=limited.run_id,
            authority=chain["authority"], prompt_template=DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE)
        with pytest.raises(StepFailure, match="冻结身份"):
            _load_frozen_agent_config(session, payload=limited_payload | {"retry_pages": [["other-document", 1]]},
                run_id=limited.run_id, authority=chain["authority"],
                prompt_template=DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE)
        _load_frozen_agent_config(session, payload=payload, run_id=continued.run_id,
            authority=chain["authority"], prompt_template=DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE)
        with pytest.raises(StepFailure, match="冻结身份"):
            _load_frozen_agent_config(session, payload=payload | {"retry_failed_from_run_id": "different-run"},
                run_id=continued.run_id, authority=chain["authority"],
                prompt_template=DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE)
    with pytest.raises(InvalidJobDefinitionError, match="同一资料范围"):
        service.create_or_reuse_from_source(**(kwargs | {"authority": chain["authority"].model_copy(
            update={"subject_id": "foreign-subject"})}))


def test_targeted_finalize_keeps_accepted_fact_when_page_coverage_has_failure(
    session_factory, monkeypatch,
):
    from app.domain.contracts.enums import GateOutcome
    import app.services.fact_normalization_executor as module
    chain, template = _prepare(session_factory, prefix="targeted-partial-finalize", requirement_id="req-partial")
    created = _targeted_job(session_factory, chain)
    # Inject a coverage diagnostic into the real finalizer, not into the model or adopted value.
    monkeypatch.setattr(module, "validate_page_coverage", lambda *_args, **_kwargs:
                        (GateOutcome.REJECTED, ["合成缺页诊断"], ["unread-document:2"]))
    runner = JobRunner(session_factory, {"fact_normalization": create_fact_normalization_executor(
        FactNormalizationExecutorConfig(session_factory=session_factory,
                                       transport_fn=_transport(chain, template.requirement_id)))})
    assert runner.run_job(created.job_id)
    with session_factory() as session:
        store = JobStore(session)
        assert store.get_job(created.job_id).state == "completed", [
            store.get_last_checkpoint(created.job_id, step.step_id)
            for step in store.list_steps(created.job_id)]
        facts = ClinicalFactV2Repository(session).list_by_episode(chain["episode_id"])
        assert any(fact.value == 5.0 for fact in facts)
        checkpoint = store.get_last_checkpoint(created.job_id, FACT_NORMALIZATION_FINALIZE_STEP_ID)[1]
        assert checkpoint["status"] == "partial"
        assert checkpoint["published_fact_count"] == 1
        assert checkpoint["unread_page_refs"] == ["unread-document:2"]


@pytest.mark.parametrize("compact", [False, True])
def test_failed_transport_retains_bound_receipt(
    session_factory, data_paths, monkeypatch, compact,
):
    from app.evidence.artifacts import ArtifactStore
    import app.services.fact_normalization_executor as executor_module

    chain, _ = _prepare(
        session_factory, prefix="receipt-failure", requirement_id="receipt-rule"
    )
    service = FactNormalizationJobService(session_factory)
    created = service.create_or_reuse_from_source(
        authority=chain["authority"], prompt_version_id=chain["prompt_version_id"],
        model_config_id=chain["model_config_id"], created_by="test",
        compact_text_references=compact,
    )
    artifacts = ArtifactStore(data_paths)

    def failed_factory(model_config, *, receipt_callback, request_callback):
        from app.agents.deepseek_evidence_normalizer_transport import DeepSeekEvidenceNormalizerTransport

        def fail(**kwargs):
            raise TimeoutError("injected transport request failure")

        return DeepSeekEvidenceNormalizerTransport(
            backend="omlx", model=model_config.model,
            client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=fail))),
            receipt_callback=receipt_callback,
            request_callback=request_callback,
        )

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
        assert receipt["request_receipt_version"] == "normalizer-request/v1"
        request = json.loads(artifacts.read_by_sha("raw_request", receipt["request_artifact_sha256"]))
        for key in ("job_id", "run_id", "call_id", "step_id"):
            assert request[key] == receipt[key]
        assert request["request_body"]["messages"][0]["role"] == "user"
        assert request["request_body"]["messages"][0]["content"]
        assert receipt["request_sha256"] == hashlib.sha256(json.dumps(
            request["request_body"], ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
        if compact:
            assert receipt["text_reference_strategy"]["version"] == "text-reference-aliases/v1"
            assert receipt["reference_aliases"]["locator"]
        else:
            assert "reference_aliases" not in receipt
    with session_factory() as session:
        assert not PatientProfileRevisionRepository(session).list_by_episode(
            chain["episode_id"]
        )


@pytest.mark.parametrize("fallback_only", [False, True])
def test_new_normalization_batch_preserves_unresolved_prior_issue(
    session_factory, fallback_only
):
    from app.domain.contracts.enums import GapType
    from app.domain.contracts.evidence_expectations_v2 import CoverageGapSignal
    from app.services.evidence_expectation_projection_service import (
        EvidenceExpectationProjectionService,
    )

    chain, template = _prepare(
        session_factory, prefix="fn-prior-issue", requirement_id="prior-issue"
    )
    with session_factory() as session, session.begin():
        EvidenceExpectationProjectionService().project(
            session,
            authority=chain["authority"],
            gap_signals=[CoverageGapSignal(
                kind=GapType.OBSERVATION_UNVERIFIED,
                detail="该项资料的检查时间尚未核实",
                applies_to_template_id=template.template_id,
                fallback_only=fallback_only,
            )],
        )

    _, created = _run(session_factory, chain, template.requirement_id)
    with session_factory() as session:
        assert JobStore(session).job_status(created.job_id).state == "completed"
        latest = EvidenceExpectationV2Repository(session).latest_by_template(
            chain["episode_id"], template.template_id
        )
        assert latest.status == (
            ExpectationStatus.OBSERVED if fallback_only
            else ExpectationStatus.OBSERVED_WEAK
        )
        assert latest.gap_type == (
            None if fallback_only else GapType.OBSERVATION_UNVERIFIED
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


@pytest.mark.parametrize("failure", [PatientProfileProjectionError, InvalidReferenceError, FactPublicationError])
def test_finalize_rolls_back_when_profile_projection_fails(session_factory, monkeypatch, failure):
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
        raise failure("forced profile projection failure")

    if failure is FactPublicationError:
        original_publish = FactPublicationService.publish

        def publish_then_fail(self, session, run_id):
            published = original_publish(self, session, run_id)
            assert published.fact_ids
            assert ClinicalFactV2Repository(session).get(published.fact_ids[0])
            raise FactPublicationError("injected failure after publication writes")

        monkeypatch.setattr(FactPublicationService, "publish", publish_then_fail)
    else:
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
