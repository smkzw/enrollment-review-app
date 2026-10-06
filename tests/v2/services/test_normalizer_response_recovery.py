"""Frozen synthetic receipts through real retry, storage, finalize and restart."""
from copy import deepcopy
from types import SimpleNamespace
import hashlib
import json

import pytest

from app.domain.publication import canonical_hash
from app.evidence.artifacts import ArtifactStore
from app.services.fact_normalization_executor import (
    FactNormalizationExecutorConfig, create_fact_normalization_executor, _build_input,
    _get_call_for_step, _load_authority, _load_frozen_agent_config, _prepare_response_revalidation,
)
from app.agents.evidence_normalizer import DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE
from app.services.fact_normalization_job_service import FactNormalizationJobService
from app.services.fact_normalization_job_service import project_fact_normalization_run_status
from app.domain.contracts.enums import FactNormalizationRunStatus
from app.services.fact_normalization_response_recovery import SavedResponseRecovery
from app.storage.fact_repositories import FactNormalizationCallRepository, FactNormalizationRunRepository
from app.workflow.errors import StepFailure
from app.workflow.jobstore import JobStore
from app.workflow.runner import JobRunner, StepContext
from tests.v2.services.test_fact_normalization_persistence import _seed_chain
from tests.v2.services.test_normalizer_candidate_partition import SourceDraftTransport


def frozen_failure(session_factory, data_paths, *, mutation=None, missing_value=True):
    with session_factory() as session:
        chain = _seed_chain(session, prefix="saved-response")
        session.commit()
    service = FactNormalizationJobService(session_factory)
    created = service.create_or_reuse_from_source(authority=chain["authority"],
        prompt_version_id=chain["prompt_version_id"], model_config_id=chain["model_config_id"],
        created_by="tester", allow_candidate_partition=True)
    artifacts = ArtifactStore(data_paths)
    payload = service.get_job(created.job_id)["payload"]
    selection = {}

    def save(kind, body):
        return artifacts.put(kind, json.dumps(body, ensure_ascii=False, sort_keys=True).encode()).sha256

    def fail(context):
        with session_factory() as session:
            call = _get_call_for_step(payload, context.step_id)
            run = FactNormalizationRunRepository(session).get(created.run_id)
            source = _build_input(session, chain["authority"], created.run_id, call,
                max_pages_per_call=payload["max_pages_per_call"], created_at=run.created_at)
            config = _load_frozen_agent_config(session, payload=payload, run_id=created.run_id,
                authority=chain["authority"], prompt_template=DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE)
            request, aliases = _prepare_response_revalidation(payload, source, config,
                DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE, [])
        raw = SourceDraftTransport(chain, missing_value=missing_value).start(prompt="fixture").text
        if mutation == "foreign_locator":
            raw_body = json.loads(raw)
            raw_body["fact_candidates"][1]["locator_ids"] = ["other-call-source"]
            raw = json.dumps(raw_body, ensure_ascii=False)
        bindings = {"job_id": created.job_id, "step_id": context.step_id,
            "run_id": created.run_id, "call_id": call["call_id"]}
        request_body = deepcopy(request)
        if mutation == "prompt":
            request_body["messages"][0]["content"] += "不同来源上下文"
        if mutation == "budget":
            request_body["max_tokens"] *= 2
        if mutation == "repair":
            request_body["messages"].append({"role": "user", "content": "改变上下文"})
        request_sha = save("raw_request", {**bindings, "provider": config.provider,
            "request_receipt_version": "normalizer-request/v1", "request_body": request_body})
        receipt = {**bindings, "provider": config.provider, "raw_text": raw,
            "request_receipt_version": "normalizer-request/v1", "request_artifact_sha256": request_sha,
            "request_sha256": canonical_hash(request_body), "finish_reason": "stop",
            "requested_model": config.model, "response_model": config.model,
            "response_id": "synthetic-fixture-not-a-live-call"}
        if aliases is not None:
            receipt["reference_aliases"] = aliases.aliases
        if mutation == "foreign_job":
            receipt["job_id"] = "other-job"
        if mutation == "length":
            receipt["finish_reason"] = "length"
        if mutation == "request_missing":
            receipt.pop("request_artifact_sha256")
        if mutation == "alias":
            receipt["reference_aliases"] = {"made-up": "other-source"}
        if mutation == "model":
            receipt["response_model"] = "other-model"
        response_sha = save("raw_response", receipt)
        failure = {**bindings, "input_sha256": call["input_sha256"],
            "transport_receipt_sha256": [response_sha],
            "attempts": [{"error_code": "PARTIAL_OUTPUT", "raw_output_sha256": hashlib.sha256(raw.encode()).hexdigest()}]}
        if mutation in {"second_answer", "first_of_two"}:
            second_raw = raw + "\n"
            second_sha = save("raw_response", {**receipt, "raw_text": second_raw})
            failure["transport_receipt_sha256"].append(second_sha)
            failure["attempts"].append({"error_code": "PARTIAL_OUTPUT",
                "raw_output_sha256": hashlib.sha256(second_raw.encode()).hexdigest()})
            if mutation == "second_answer":
                response_sha = second_sha
        if mutation == "input":
            failure["input_sha256"] = "0" * 64
        selection[call["call_id"]] = SavedResponseRecovery(save("evaluation_manifest", failure), response_sha)
        raise StepFailure(retryable=False, error_code="PARTIAL_OUTPUT", detail="旧版本解析失败的合成回执")

    JobRunner(session_factory, {"fact_normalization": fail},
        on_failed=lambda jid: project_fact_normalization_run_status(
            session_factory, jid, FactNormalizationRunStatus.FAILED)).run_job(created.job_id)
    assert service.get_job(created.job_id)["state"] == "failed_final"
    return chain, service, created, artifacts, payload, selection


@pytest.mark.parametrize("missing_value,mutation", [(True, None), (False, None), (True, "first_of_two")])
def test_saved_response_revalidates_and_finalizes_without_model_then_restarts(
    session_factory, data_paths, missing_value, mutation,
):
    chain, service, created, artifacts, payload, selection = frozen_failure(
        session_factory, data_paths, missing_value=missing_value, mutation=mutation)
    def forbidden_transport(_):
        raise AssertionError("恢复不得产生新的模型读取")
    executor = create_fact_normalization_executor(FactNormalizationExecutorConfig(
        session_factory=session_factory, artifact_store=artifacts,
        transport_factory=forbidden_transport, saved_response_recovery=selection))
    service.retry(created.job_id)
    JobRunner(session_factory, {"fact_normalization": executor}).run_job(created.job_id)
    assert service.get_job(created.job_id)["state"] == "completed"
    with session_factory() as session:
        from app.storage.fact_repositories import ClinicalFactV2Repository
        facts = ClinicalFactV2Repository(session).list_by_episode(chain["episode_id"])
        assert len(facts) == 1 and facts[0].value == "ALT 5"
        call = FactNormalizationCallRepository(session).list_by_run(created.run_id)[0]
        assert call.response_recovery_sha256 and call.candidate_partition_sha256
        proof = json.loads(artifacts.read_by_sha("evaluation_manifest", call.response_recovery_sha256))
        assert proof["model_called"] is False
        checkpoint = JobStore(session).get_last_checkpoint(created.job_id, "normalize_000_" + chain["logical_document_id"])
    # Restart verification uses the proof, not the transient selection or credentials.
    restarted = create_fact_normalization_executor(FactNormalizationExecutorConfig(
        session_factory=session_factory, artifact_store=artifacts, transport_factory=forbidden_transport))
    result = restarted(StepContext(job_id=created.job_id, job_type="fact_normalization", job_payload=payload,
        step_id="normalize_000_" + chain["logical_document_id"], name="资料整理", attempt=2,
        max_attempts=3, last_checkpoint_id=checkpoint[0], last_checkpoint=checkpoint[1]))
    assert result["model_called"] is False
    # Durable call rebuilding is also checked when the Job checkpoint is absent.
    rebuilt = restarted(StepContext(job_id=created.job_id, job_type="fact_normalization", job_payload=payload,
        step_id="normalize_000_" + chain["logical_document_id"], name="资料整理", attempt=2,
        max_attempts=3, last_checkpoint_id=None, last_checkpoint=None))
    assert rebuilt["response_recovery_sha256"] == call.response_recovery_sha256
    assert rebuilt["model_called"] is False
    from app.services.evidence_api_read_service import EvidenceApiReadService
    view = EvidenceApiReadService(session_factory, artifacts).normalization_unresolved(
        chain["subject_id"], chain["episode_id"], created.job_id)
    assert len(view["items"]) == 1 and view["items"][0]["sources"]


@pytest.mark.parametrize("mutation", ["foreign_job", "input", "length", "request_missing", "prompt",
                                      "budget", "repair", "alias", "foreign_locator", "model", "second_answer"])
def test_saved_response_faults_do_not_fall_back_to_new_calls_or_publish(
    session_factory, data_paths, mutation,
):
    chain, service, created, artifacts, payload, selection = frozen_failure(session_factory, data_paths, mutation=mutation)
    def forbidden_transport(_):
        raise AssertionError("无效恢复不能静默转为付费读取")
    executor = create_fact_normalization_executor(FactNormalizationExecutorConfig(
        session_factory=session_factory, artifact_store=artifacts,
        transport_factory=forbidden_transport, saved_response_recovery=selection))
    service.retry(created.job_id)
    JobRunner(session_factory, {"fact_normalization": executor}).run_job(created.job_id)
    assert service.get_job(created.job_id)["state"] == "failed_final"
    with session_factory() as session:
        from app.storage.fact_repositories import ClinicalFactV2Repository
        assert not ClinicalFactV2Repository(session).list_by_episode(chain["episode_id"])
        assert not FactNormalizationCallRepository(session).list_by_run(created.run_id)


def test_saved_response_proof_is_required_after_restart(session_factory, data_paths):
    chain, service, created, artifacts, payload, selection = frozen_failure(session_factory, data_paths)
    executor = create_fact_normalization_executor(FactNormalizationExecutorConfig(
        session_factory=session_factory, artifact_store=artifacts, saved_response_recovery=selection))
    service.retry(created.job_id)
    JobRunner(session_factory, {"fact_normalization": executor}).run_job(created.job_id)
    with session_factory() as session:
        call = FactNormalizationCallRepository(session).list_by_run(created.run_id)[0]
        checkpoint = JobStore(session).get_last_checkpoint(created.job_id, "finalize")
    path = data_paths.root / "artifacts/evaluation_manifest" / call.response_recovery_sha256
    path.unlink()  # Synthetic fixture only; retain real failed artifacts.
    with pytest.raises(StepFailure, match="保存原答恢复不能复用"):
        executor(StepContext(job_id=created.job_id, job_type="fact_normalization", job_payload=payload,
            step_id="finalize", name="汇总", attempt=2, max_attempts=3,
            last_checkpoint_id=checkpoint[0], last_checkpoint=checkpoint[1]))
    with pytest.raises(StepFailure, match="保存原答恢复不能复用"):
        executor(StepContext(job_id=created.job_id, job_type="fact_normalization", job_payload=payload,
            step_id="normalize_000_" + chain["logical_document_id"], name="资料整理", attempt=2,
            max_attempts=3, last_checkpoint_id=None, last_checkpoint=None))


@pytest.mark.parametrize("strategy", [None, "text_reference_strategy", "verified_evidence_strategy"])
def test_revalidation_request_matches_actual_runner_transport_request(session_factory, data_paths, strategy):
    from app.agents.deepseek_evidence_normalizer_transport import evidence_normalizer_transport_from_model_config
    from app.agents.evidence_normalizer import EvidenceNormalizerRunner

    chain, service, created, artifacts, payload, selection = frozen_failure(session_factory, data_paths)
    if strategy:
        payload = {**payload, strategy: "isolated-contract-fixture"}
    with session_factory() as session:
        call = payload["calls"][0]
        run = FactNormalizationRunRepository(session).get(created.run_id)
        source = _build_input(session, chain["authority"], created.run_id, call,
            max_pages_per_call=payload["max_pages_per_call"], created_at=run.created_at)
        config = _load_frozen_agent_config(session, payload=service.get_job(created.job_id)["payload"],
            run_id=created.run_id, authority=chain["authority"],
            prompt_template=DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE)
    captured = []
    if strategy == "verified_evidence_strategy":
        from tests.v2.agents.test_evidence_normalizer_adapter import _r3_input
        source = _r3_input()
    response = SimpleNamespace(id="synthetic-not-live", model=config.model, usage=None,
        choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content="{}"))])
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
        create=lambda **kwargs: (captured.append(kwargs), response)[1])))
    transport = evidence_normalizer_transport_from_model_config(config, client=client)
    verified = strategy == "verified_evidence_strategy"
    EvidenceNormalizerRunner(max_transport_retries=0, max_schema_repairs=0).run(source, transport,
        prompt_template=DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE,
        pending_details_retained=verified, compact_references=strategy is not None,
        verified_scope_prompt=verified, require_current_draft=True)
    expected, _ = _prepare_response_revalidation(payload, source, config,
        DEFAULT_EVIDENCE_NORMALIZER_PROMPT_TEMPLATE, [])
    assert len(captured) == 1
    assert captured[0] == expected
