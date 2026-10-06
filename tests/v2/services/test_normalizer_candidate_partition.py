"""Use the real job, storage, gates, Profile and source-question API."""
from copy import deepcopy
import json

import pytest

from app.agents.evidence_normalizer import EvidenceNormalizerAgentResponse
from app.evidence.artifacts import ArtifactStore
from app.services.evidence_api_read_service import EvidenceApiReadService
from app.services.fact_normalization_executor import FactNormalizationExecutorConfig, create_fact_normalization_executor
from app.services.fact_normalization_job_service import FactNormalizationJobService
from app.storage.fact_repositories import FactNormalizationCallRepository, FactNormalizationRunRepository
from app.workflow.runner import JobRunner, StepContext
from tests.v2.services.test_fact_normalization_persistence import _seed_chain


class SourceDraftTransport:
    def __init__(self, chain, *, missing_value=False):
        self.chain = chain
        self.calls = 0
        self.missing_value = missing_value

    def start(self, *, prompt):
        self.calls += 1
        fact = {"candidate_ref": "good", "assertion_scope": "observed_state", "fact_type": "检验结果",
            "profile_lane": "test_exam_score", "polarity": "affirmed", "asserted_object": "ALT",
            "raw_value": "ALT 5", "canonical_value": "ALT 5", "unit": None,
            "locator_ids": [self.chain["locator_id"]], "candidate_source_semantics": "同期客观结果",
            "assertion_basis": {"asserted_object": "ALT", "assertion_text": "ALT 5",
                "locator_id": self.chain["locator_id"], "contextual_qualifiers": []}, "model_uncertainty": 0}
        broken = deepcopy(fact)
        broken["candidate_ref"] = "bad"
        broken["assertion_basis"]["asserted_object"] = "原文没有的对象"
        if self.missing_value:
            broken["assertion_basis"]["asserted_object"] = "ALT"
            broken.update(raw_value=None, canonical_value=None)
        payload = {"schema_version": "phase5/normalizer-draft/v5", "fact_candidates": [fact, broken],
            "event_candidates": [], "exposure_candidates": [], "actual_exposure_fact_refs": [],
            "non_exposure_medication_fact_refs": [], "unresolved_items": []}
        return EvidenceNormalizerAgentResponse(session_id="source-only", text=json.dumps(payload, ensure_ascii=False))

    def continue_session(self, **kwargs):
        raise AssertionError("该测试局部隔离不得额外调用模型")


@pytest.mark.parametrize("recovery", [False, True])
@pytest.mark.parametrize("missing_value", [False, True])
def test_partition_persists_good_source_and_bad_question_with_legal_job_and_restart(
    session_factory, data_paths, recovery, missing_value,
):
    with session_factory() as session:
        chain = _seed_chain(session, prefix="source-partition")
        session.commit()
    service = FactNormalizationJobService(session_factory)
    common = dict(authority=chain["authority"], prompt_version_id=chain["prompt_version_id"],
                  model_config_id=chain["model_config_id"], created_by="tester")
    old = service.create_or_reuse_from_source(**common)
    created = service.create_or_reuse_from_source(**common, allow_candidate_partition=True)
    assert old.job_id != created.job_id
    assert service.get_job(old.job_id)["payload"].get("candidate_partition_policy") is None
    artifacts = ArtifactStore(data_paths)
    transport = SourceDraftTransport(chain, missing_value=missing_value)
    executor = create_fact_normalization_executor(FactNormalizationExecutorConfig(
        session_factory=session_factory, transport=transport, artifact_store=artifacts, max_schema_repairs=0))
    payload = service.get_job(created.job_id)["payload"]
    step = "normalize_000_" + chain["logical_document_id"]
    if recovery:
        prepared = executor(StepContext(job_id=created.job_id, job_type="fact_normalization", job_payload=payload,
            step_id=step, name="证据整理", attempt=1, last_checkpoint_id=None, last_checkpoint=None, max_attempts=3))
        with session_factory() as session, session.begin():
            prepared.apply(session)
        assert "candidate_partition_sha256" in prepared.checkpoint
    assert JobRunner(session_factory, {"fact_normalization": executor}).run_job(created.job_id) is True
    assert transport.calls == 1
    with session_factory() as session:
        from app.storage.fact_repositories import ClinicalFactV2Repository
        facts = ClinicalFactV2Repository(session).list_by_episode(chain["episode_id"])
        assert len(facts) == 1
        assert facts[0].assertion_basis.assertion_text == "ALT 5"
        assert facts[0].value == "ALT 5"
        call = FactNormalizationCallRepository(session).list_by_run(created.run_id)[0]
        assert call.candidate_partition_sha256 is not None
        assert call.reading_method == "model_response"
        receipt = json.loads(artifacts.read_by_sha("evaluation_manifest", call.candidate_partition_sha256))
        assert receipt["raw_output_sha256"] == call.raw_output_sha256
        assert receipt["quarantined_candidate_refs"] == ["bad"]
        assert FactNormalizationRunRepository(session).get(created.run_id).status.value == "partial"
    view = EvidenceApiReadService(session_factory, artifacts).normalization_unresolved(
        chain["subject_id"], chain["episode_id"], created.job_id)
    assert any("未作为病史采用" in item["message"] for item in view["items"])
    assert all(item["sources"] for item in view["items"])
    assert len(view["items"]) == 1


@pytest.mark.parametrize("mutation", ["raw_hash", "proof_missing", "candidate_value", "extra_candidate"])
def test_partition_recovery_rejects_missing_proof_or_changed_saved_source(session_factory, data_paths, mutation):
    from app.storage.fact_repositories import FactNormalizationCandidateRepository
    from app.storage.facts_models import FactNormalizationCallRecord, FactNormalizationCandidateRecord
    from app.storage.codecs import encode_contract
    from sqlalchemy import select

    with session_factory() as session:
        chain = _seed_chain(session, prefix="partition-corruption")
        session.commit()
    service = FactNormalizationJobService(session_factory)
    created = service.create_or_reuse_from_source(authority=chain["authority"],
        prompt_version_id=chain["prompt_version_id"], model_config_id=chain["model_config_id"],
        created_by="tester", allow_candidate_partition=True)
    artifacts = ArtifactStore(data_paths)
    transport = SourceDraftTransport(chain)
    executor = create_fact_normalization_executor(FactNormalizationExecutorConfig(
        session_factory=session_factory, transport=transport, artifact_store=artifacts, max_schema_repairs=0))
    payload = service.get_job(created.job_id)["payload"]
    prepared = executor(StepContext(job_id=created.job_id, job_type="fact_normalization", job_payload=payload,
        step_id="normalize_000_" + chain["logical_document_id"], name="证据整理", attempt=1,
        last_checkpoint_id=None, last_checkpoint=None, max_attempts=3))
    with session_factory() as session, session.begin():
        prepared.apply(session)
        if mutation in {"candidate_value", "extra_candidate"}:
            row = session.execute(select(FactNormalizationCandidateRecord)).scalars().one()
            candidate = FactNormalizationCandidateRepository(session).get(row.candidate_id)
            if mutation == "candidate_value":
                row.payload_json, row.payload_sha256 = encode_contract(candidate.model_copy(update={"canonical_value": "ALT 6"}))
            else:
                FactNormalizationCandidateRepository(session).create(candidate.call_id,
                    candidate.model_copy(update={"candidate_id": "not-in-original-answer"}))
        else:
            row = session.execute(select(FactNormalizationCallRecord)).scalars().one()
            call = FactNormalizationCallRepository(session).get(row.call_id)
            changes = {"raw_output_sha256": "0" * 64} if mutation == "raw_hash" else {"candidate_partition_sha256": "0" * 64}
            row.payload_json, row.payload_sha256 = encode_contract(call.model_copy(update=changes))
    assert JobRunner(session_factory, {"fact_normalization": executor}).run_job(created.job_id) is True
    from app.workflow.jobstore import JobStore
    with session_factory() as session:
        assert JobStore(session).job_status(created.job_id).state == "failed_final"
    assert transport.calls == 1


def test_finalize_checkpoint_also_rechecks_partition_proof(session_factory, data_paths):
    from app.services.fact_normalization_job_service import FACT_NORMALIZATION_FINALIZE_STEP_ID
    from app.storage.facts_models import FactNormalizationCallRecord
    from app.storage.codecs import encode_contract
    from app.workflow.jobstore import JobStore
    from app.workflow.errors import StepFailure

    with session_factory() as session:
        chain = _seed_chain(session, prefix="final-proof")
        session.commit()
    service = FactNormalizationJobService(session_factory)
    created = service.create_or_reuse_from_source(authority=chain["authority"],
        prompt_version_id=chain["prompt_version_id"], model_config_id=chain["model_config_id"],
        created_by="tester", allow_candidate_partition=True)
    transport = SourceDraftTransport(chain)
    executor = create_fact_normalization_executor(FactNormalizationExecutorConfig(
        session_factory=session_factory, transport=transport, artifact_store=ArtifactStore(data_paths), max_schema_repairs=0))
    assert JobRunner(session_factory, {"fact_normalization": executor}).run_job(created.job_id)
    with session_factory() as session, session.begin():
        checkpoint = JobStore(session).list_checkpoints(created.job_id, FACT_NORMALIZATION_FINALIZE_STEP_ID)[-1]
        call = FactNormalizationCallRepository(session).list_by_run(created.run_id)[0]
        row = session.get(FactNormalizationCallRecord, call.call_id)
        row.payload_json, row.payload_sha256 = encode_contract(call.model_copy(update={"candidate_partition_sha256": "0" * 64}))
    with pytest.raises(StepFailure, match="局部保留结果不能复用"):
        executor(StepContext(job_id=created.job_id, job_type="fact_normalization",
            job_payload=service.get_job(created.job_id)["payload"], step_id=FACT_NORMALIZATION_FINALIZE_STEP_ID,
            name="汇总", attempt=1, last_checkpoint_id=checkpoint[0],
            last_checkpoint=checkpoint[1], max_attempts=3))
    assert transport.calls == 1


def test_old_job_cannot_gain_new_recovery_semantics_from_a_policy_string(session_factory, data_paths):
    from app.workflow.errors import StepFailure
    from app.agents.evidence_candidate_partition import CANDIDATE_PARTITION_POLICY
    with session_factory() as session:
        chain = _seed_chain(session, prefix="old-policy")
        session.commit()
    service = FactNormalizationJobService(session_factory)
    created = service.create_or_reuse_from_source(authority=chain["authority"],
        prompt_version_id=chain["prompt_version_id"], model_config_id=chain["model_config_id"], created_by="tester")
    payload = service.get_job(created.job_id)["payload"]
    payload["candidate_partition_policy"] = CANDIDATE_PARTITION_POLICY
    payload["candidate_partition_precondition_scope_sha256"] = payload["input_scope_sha256"]
    transport = SourceDraftTransport(chain)
    executor = create_fact_normalization_executor(FactNormalizationExecutorConfig(
        session_factory=session_factory, transport=transport, artifact_store=ArtifactStore(data_paths)))
    with pytest.raises(StepFailure, match="未进入本次冻结身份"):
        executor(StepContext(job_id=created.job_id, job_type="fact_normalization", job_payload=payload,
            step_id="normalize_000_" + chain["logical_document_id"], name="证据整理", attempt=1,
            last_checkpoint_id=None, last_checkpoint=None, max_attempts=3))
    assert transport.calls == 0
