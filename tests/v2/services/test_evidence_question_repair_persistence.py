"""Question recovery uses existing jobs, artifacts, publication and question consumers."""
import json

import pytest
from sqlalchemy import select

from app.agents.evidence_normalizer import EvidenceNormalizerAgentResponse
from app.domain.contracts.enums import ReviewStage
from app.evidence.artifacts import ArtifactStore
from app.services.evidence_api_read_service import EvidenceApiReadService
from app.services.fact_normalization_executor import FactNormalizationExecutorConfig, create_fact_normalization_executor
from app.services.fact_normalization_job_service import FactNormalizationJobService
from app.storage.fact_repositories import ClinicalFactV2Repository, FactNormalizationCallRepository, FactNormalizationRunRepository
from app.storage.models import ReviewEpisodeRecord, WorkflowStageRecord
from app.workflow.jobstore import JobStore
from app.workflow.runner import JobRunner, StepContext
from tests.v2.projections.test_evidence_expectations import _template
from tests.v2.services.test_fact_normalization_persistence import _seed_chain, _update_episode
from tests.v2.services.test_normalizer_candidate_partition import SourceDraftTransport


def _seed(session):
    chain = _seed_chain(session, prefix="question-recovery")
    stage_id = session.execute(select(WorkflowStageRecord.workflow_stage_id).where(
        WorkflowStageRecord.protocol_version_id == chain["protocol_version_id"],
        WorkflowStageRecord.stage == "screening")).scalar_one()
    _update_episode(session, session.get(ReviewEpisodeRecord, chain["episode_id"]), workflow_stage_id=stage_id)
    template = _template(session, {**chain, "run_id": "question-recovery", "workflow_stage_id": stage_id},
        requirement_id="source-question", fact_type="lab_result", due_stage=ReviewStage.SCREENING)
    chain["question_requirement_id"] = template.requirement_id
    return chain


class RecoveryTransport(SourceDraftTransport):
    def __init__(self, chain):
        super().__init__(chain)
        self.proposals = 0
        self.keep_bad_candidate = False
        self.proposed_gap_type = "date_or_anchor_missing"
        self.source_gap_type = "interpretation_conflict"
        self.question_reason = "年份与持续时间尚未区分"
        self.bind_fact = False

    def start(self, *, prompt):
        response = super().start(prompt=prompt)
        payload = json.loads(response.text)
        if not self.keep_bad_candidate:
            payload["fact_candidates"] = payload["fact_candidates"][:1]
        if self.bind_fact:
            payload["fact_candidates"][0]["supported_requirement_ids"] = [self.chain["question_requirement_id"]]
        payload["unresolved_items"] = [{"code": "source_meaning_unclear",
            "message": "来源记录的关系尚待核对", "reason": self.question_reason,
            "affected_pages": [1], "affected_locator_ids": [self.chain["locator_id"]],
            "affected_requirement_ids": [self.chain["question_requirement_id"]],
            "gap_type": self.source_gap_type}]
        return response.model_copy(update={"text": json.dumps(payload, ensure_ascii=False)})

    def propose_question_classifications(self, *, prompt, output_schema):
        self.proposals += 1
        frozen, _ = json.JSONDecoder().raw_decode(prompt[prompt.index("{"):])
        proposal = {key: frozen[key] for key in ("policy", "precondition_sha256", "input_scope_sha256")}
        proposal["changes"] = [{"index": item["index"], "question_sha256": item["question_sha256"],
            "gap_type": self.proposed_gap_type} for item in frozen["targets"]]
        return EvidenceNormalizerAgentResponse(session_id="question-proposal", text=json.dumps(proposal))


def _prepare(session_factory, data_paths):
    with session_factory() as session:
        chain = _seed(session)
        session.commit()
    service = FactNormalizationJobService(session_factory)
    common = dict(authority=chain["authority"], prompt_version_id=chain["prompt_version_id"],
        model_config_id=chain["model_config_id"], created_by="tester", allow_candidate_partition=True)
    old = service.create_or_reuse_from_source(**common)
    created = service.create_or_reuse_from_source(**common, allow_question_classification_repair=True)
    assert old.job_id != created.job_id
    assert service.get_job(old.job_id)["payload"].get("question_classification_repair_policy") is None
    assert service.create_or_reuse_from_source(**common, allow_question_classification_repair=True).job_id == created.job_id
    artifacts, transport = ArtifactStore(data_paths), RecoveryTransport(chain)
    executor = create_fact_normalization_executor(FactNormalizationExecutorConfig(session_factory=session_factory,
        transport=transport, artifact_store=artifacts, max_schema_repairs=1))
    payload = service.get_job(created.job_id)["payload"]
    context = StepContext(job_id=created.job_id, job_type="fact_normalization", job_payload=payload,
        step_id="normalize_000_" + chain["logical_document_id"], name="资料整理", attempt=1,
        last_checkpoint_id=None, last_checkpoint=None, max_attempts=3)
    return chain, service, created, artifacts, transport, executor, context


@pytest.mark.parametrize("restart", [False, True])
def test_source_bound_question_proof_persists_and_replays_without_rereading(session_factory, data_paths, restart):
    chain, service, created, artifacts, transport, executor, context = _prepare(session_factory, data_paths)
    if restart:
        prepared = executor(context)
        with session_factory() as session, session.begin():
            prepared.apply(session)
        assert prepared.checkpoint["question_classification_sha256"]
    assert JobRunner(session_factory, {"fact_normalization": executor}).run_job(created.job_id)
    with session_factory() as session:
        assert JobStore(session).job_status(created.job_id).state == "completed", [
            row.event.payload.get("detail") for row in JobStore(session).list_event_rows(created.job_id)
            if row.event.payload.get("detail")]
        call = FactNormalizationCallRepository(session).list_by_run(created.run_id)[0]
        assert call.question_classification_sha256 and call.candidate_partition_sha256 is None
        proof = json.loads(artifacts.read_by_sha("evaluation_manifest", call.question_classification_sha256))
        assert proof["raw_output_sha256"] == call.raw_output_sha256
        assert "interpretation_conflict" in proof["original_response"]
        facts = ClinicalFactV2Repository(session).list_by_episode(chain["episode_id"])
        assert len(facts) == 1 and facts[0].assertion_basis.assertion_text == "ALT 5"
        assert FactNormalizationRunRepository(session).get(created.run_id).status.value == "partial"
    assert (transport.calls, transport.proposals) == (1, 1)
    view = EvidenceApiReadService(session_factory, artifacts).normalization_unresolved(
        chain["subject_id"], chain["episode_id"], created.job_id)
    assert len(view["items"]) == 1
    assert view["items"][0]["sources"]
    assert "尚待核对" in view["items"][0]["message"]


@pytest.mark.parametrize("restart", [False, True])
def test_unverified_relationship_survives_save_and_replay_without_upgrading_coverage(session_factory, data_paths, restart):
    from app.domain.contracts.enums import ExpectationStatus, GapType
    from app.storage.evidence_expectation_repository import EvidenceExpectationV2Repository
    from app.services.fact_expectation_gaps import expectation_gap_signals
    from app.storage.fact_repositories import FactNormalizationUnresolvedItemRepository
    chain, service, created, artifacts, transport, executor, context = _prepare(session_factory, data_paths)
    transport.source_gap_type = "source_conflict"
    transport.proposed_gap_type = "observation_unverified"
    transport.question_reason = "两份记录的最终版本关系尚未核定"
    transport.bind_fact = True
    if restart:
        prepared = executor(context)
        with session_factory() as session, session.begin():
            prepared.apply(session)
    assert JobRunner(session_factory, {"fact_normalization": executor}).run_job(created.job_id)
    with session_factory() as session:
        assert JobStore(session).job_status(created.job_id).state == "completed"
        facts = ClinicalFactV2Repository(session).list_by_episode(chain["episode_id"])
        assert len(facts) == 1
        assert chain["question_requirement_id"] in facts[0].supported_requirement_ids
        expectations = EvidenceExpectationV2Repository(session).list_by_episode(chain["episode_id"])
        linked = [e for e in expectations if e.gap_type == GapType.OBSERVATION_UNVERIFIED]
        assert len(linked) == 1
        assert linked[0].status == ExpectationStatus.OBSERVED_WEAK
        assert facts[0].fact_id in linked[0].coverage_fact_ids
        assert linked[0].source_coverage == "complete"
        assert "不代表已确认冲突" in linked[0].gap_detail
        questions = FactNormalizationUnresolvedItemRepository(session).list_by_run(created.run_id)
        assert questions[0].item.reason == transport.question_reason
        call = FactNormalizationCallRepository(session).list_by_run(created.run_id)[0]
        proof = json.loads(artifacts.read_by_sha("evaluation_manifest", call.question_classification_sha256))
        assert json.loads(proof["original_response"])["unresolved_items"][0]["gap_type"] == "source_conflict"
        signals = expectation_gap_signals(session, chain["authority"], questions)
        concrete = [s for s in signals if s.applies_to_template_id == linked[0].template_id]
        assert len(concrete) == 1 and not concrete[0].fallback_only
        assert concrete[0].kind == GapType.OBSERVATION_UNVERIFIED
    view = EvidenceApiReadService(session_factory, artifacts).normalization_unresolved(
        chain["subject_id"], chain["episode_id"], created.job_id)
    assert view["items"][0]["sources"]
    assert view["items"][0]["kind"] == "reading_uncertainty"
    assert view["items"][0]["reason"] == transport.question_reason
    assert (transport.calls, transport.proposals) == (1, 1)


@pytest.mark.parametrize("mutation", ["raw_hash", "proof_missing", "candidate_value", "question_message"])
def test_restart_rejects_changed_fact_question_or_missing_proof(session_factory, data_paths, mutation):
    from app.storage.codecs import encode_contract
    from app.storage.fact_repositories import FactNormalizationCandidateRepository, FactNormalizationUnresolvedItemRepository
    from app.storage.facts_models import FactNormalizationCallRecord, FactNormalizationCandidateRecord, FactNormalizationUnresolvedItemRecord

    chain, service, created, artifacts, transport, executor, context = _prepare(session_factory, data_paths)
    prepared = executor(context)
    with session_factory() as session, session.begin():
        prepared.apply(session)
        if mutation == "candidate_value":
            row = session.execute(select(FactNormalizationCandidateRecord)).scalars().one()
            value = FactNormalizationCandidateRepository(session).get(row.candidate_id)
            row.payload_json, row.payload_sha256 = encode_contract(value.model_copy(update={"canonical_value": "ALT 6"}))
        elif mutation == "question_message":
            value = FactNormalizationUnresolvedItemRepository(session).list_by_run(created.run_id)[0]
            row = session.get(FactNormalizationUnresolvedItemRecord, value.unresolved_item_id)
            changed = value.model_copy(update={"item": value.item.model_copy(update={"message": "研究者没有记录"})})
            row.payload_json, row.payload_sha256 = encode_contract(changed)
        else:
            row = session.execute(select(FactNormalizationCallRecord)).scalars().one()
            value = FactNormalizationCallRepository(session).get(row.call_id)
            key = "raw_output_sha256" if mutation == "raw_hash" else "question_classification_sha256"
            row.payload_json, row.payload_sha256 = encode_contract(value.model_copy(update={key: "0" * 64}))
    assert JobRunner(session_factory, {"fact_normalization": executor}).run_job(created.job_id)
    with session_factory() as session:
        assert JobStore(session).job_status(created.job_id).state == "failed_final"
        assert ClinicalFactV2Repository(session).list_by_episode(chain["episode_id"]) == []
    assert (transport.calls, transport.proposals) == (1, 1)


def test_legacy_job_cannot_gain_question_repair_by_policy_injection(session_factory, data_paths):
    from app.workflow.errors import StepFailure
    from app.agents.evidence_question_repair import QUESTION_REPAIR_POLICY
    chain, service, created, artifacts, transport, executor, context = _prepare(session_factory, data_paths)
    common = dict(authority=chain["authority"], prompt_version_id=chain["prompt_version_id"],
        model_config_id=chain["model_config_id"], created_by="tester")
    old = service.create_or_reuse_from_source(**common)
    payload = service.get_job(old.job_id)["payload"]
    payload["question_classification_repair_policy"] = QUESTION_REPAIR_POLICY
    payload["question_classification_precondition_scope_sha256"] = payload["input_scope_sha256"]
    with pytest.raises(StepFailure, match="未进入冻结身份"):
        executor(StepContext(job_id=old.job_id, job_type="fact_normalization", job_payload=payload,
            step_id=context.step_id, name=context.name, attempt=1, last_checkpoint_id=None,
            last_checkpoint=None, max_attempts=3))
    assert (transport.calls, transport.proposals) == (0, 0)


@pytest.mark.parametrize("restart", [False, True])
def test_two_proofs_bridge_original_to_composed_partition_and_existing_consumers(session_factory, data_paths, restart):
    chain, service, created, artifacts, transport, executor, context = _prepare(session_factory, data_paths)
    transport.keep_bad_candidate = True
    if restart:
        prepared = executor(context)
        with session_factory() as session, session.begin():
            prepared.apply(session)
    assert JobRunner(session_factory, {"fact_normalization": executor}).run_job(created.job_id)
    with session_factory() as session:
        assert JobStore(session).job_status(created.job_id).state == "completed"
        call = FactNormalizationCallRepository(session).list_by_run(created.run_id)[0]
        question = json.loads(artifacts.read_by_sha("evaluation_manifest", call.question_classification_sha256))
        partition = json.loads(artifacts.read_by_sha("evaluation_manifest", call.candidate_partition_sha256))
        assert call.raw_output_sha256 == question["raw_output_sha256"]
        assert partition["raw_output_sha256"] == question["composed_sha256"]
        assert len(ClinicalFactV2Repository(session).list_by_episode(chain["episode_id"])) == 1
        assert FactNormalizationRunRepository(session).get(created.run_id).status.value == "partial"
    view = EvidenceApiReadService(session_factory, artifacts).normalization_unresolved(
        chain["subject_id"], chain["episode_id"], created.job_id)
    assert len(view["items"]) == 2 and all(item["sources"] for item in view["items"])
    assert (transport.calls, transport.proposals) == (1, 1)
