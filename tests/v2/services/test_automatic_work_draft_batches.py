"""Synthetic source reader with the real automatic Job graph and recovery store."""
from hashlib import sha256
import json
from types import SimpleNamespace

import pytest

from app.domain.contracts.agents import ModelConfigContract
from app.domain.contracts.enums import ReviewStage
from app.domain.publication import canonical_hash
from app.evidence.artifacts import ArtifactStore
from app.services import work_draft_review as service, work_draft_semantics as semantics
from app.workflow.errors import StepFailure
from app.workflow.jobstore import JobStore
from app.workflow.runner import JobRunner, PreparedStepResult
from tests.v2.services.test_work_draft_source_relations import page, row, target
from tests.v2.services.test_work_draft_calculation import material


@pytest.mark.parametrize("count,restart,changed_source", [(0, False, False), (1, False, False),
    (37, False, False), (37, True, False), (37, False, True)])
def test_automatic_reading_uses_durable_short_batches_without_repeating_saved_work(
    session_factory, data_paths, monkeypatch, count, restart, changed_source,
):
    from app.storage import fact_repositories
    authority = material().authority
    rules = SimpleNamespace(rules=[], scope_supplement=None, model_dump=lambda **_: {"rules": []})
    frame = SimpleNamespace(context_id="frozen-context", review_run_id="frozen-run", work_draft=True,
        authority=authority, rule_set_sha256=canonical_hash(rules.model_dump()), facts=[], system_issues=[],
        clause_pack=SimpleNamespace(clauses=[], restricted_clauses=[]), evaluator_version=service.CALCULATION_VERSION,
        review_episode=SimpleNamespace(stage=ReviewStage.SCREENING, evidence_cutoff_date=None, anchor_dates={},
            model_dump=lambda **_: {"anchor_dates": {}}), source_pages=[page()])
    frame.model_copy = lambda **kwargs: SimpleNamespace(**(vars(frame) | kwargs.get("update", {})))
    targets = [{**target(), "target_id": f"target:{i}", "component_id": f"component:{i}",
                "source_text": f"要求{i}：" + "有来源的独立要求。" * 800} for i in range(count)]
    model = ModelConfigContract(model_config_id="synthetic-model", provider="synthetic", model="fixture",
        reasoning_effort="high", parameters={"max_tokens": 65536})
    monkeypatch.setattr(semantics, "runtime_model", lambda: model)
    monkeypatch.setattr(semantics, "targets_for_review", lambda *_: targets)
    monkeypatch.setattr(service, "_reusable_source_reads", lambda *_: ({}, {}))
    monkeypatch.setattr(service, "prepare_review", lambda *_, **__: frame)
    monkeypatch.setattr(service, "ReviewContextV2Repository", lambda _: SimpleNamespace(get=lambda _: frame))
    monkeypatch.setattr(fact_repositories, "FactNormalizationRunRepository", lambda _: SimpleNamespace(
        get=lambda _: SimpleNamespace(authority=authority, status=SimpleNamespace(value="partial"))))
    monkeypatch.setattr(service, "authority_from_active_episode", lambda *_: authority)
    monkeypatch.setattr(service, "get_rule_set", lambda *_: rules)
    monkeypatch.setattr(service, "_fact_refs", lambda *_: {})
    composed = []

    def procedures(*_, source_results=None, **__):
        if source_results is not None:
            composed.append(set(source_results))
        return []

    monkeypatch.setattr(service, "calculate_procedures", procedures)
    prompts = []

    class Transport:
        def propose_question_classifications(self, *, prompt, output_schema):
            assert len(prompt) <= 200000
            material = json.loads(prompt.split("\n", 1)[1])
            prompts.append(material)
            return SimpleNamespace(text=json.dumps({"results": [row(target_id=t["target_id"],
                relation="not_found", quotes=[]).model_dump() for t in material["targets"]]}))

    monkeypatch.setattr("app.agents.deepseek_evidence_normalizer_transport.evidence_normalizer_transport_from_model_config",
                        lambda *_, **__: Transport())
    artifacts = ArtifactStore(data_paths)
    with session_factory() as session, session.begin():
        result = service.enqueue_normalized_work_draft(session, authority=authority, run_id="normalization")
        assert service.enqueue_normalized_work_draft(session, authority=authority, run_id="normalization") == result
        initial = JobStore(session).job_status(result["job_id"])
        assert initial.progress_total == 1
        assert [step.step_id for step in JobStore(session).list_steps(result["job_id"])] == ["calculate"]
        payload_sha = JobStore(session).get_job(result["job_id"]).payload_sha256
    executor = service.WorkDraftReviewService(session_factory, artifacts).execute
    interrupted = False
    saved = []

    def execute(context):
        nonlocal interrupted
        if restart and context.step_id == "semantic:0001" and not interrupted:
            interrupted = True
            raise StepFailure(retryable=False, error_code="SYNTHETIC_OUTAGE", detail="合成中断")
        if context.step_id == "save":
            # This fixture checks graph/reader/composition, not clinical signing.
            saved.append(True)
            return {"saved": True}
        prepared = executor(context)
        if changed_source and context.step_id == "calculate":
            original_apply = prepared.apply
            def change_then_apply(session):
                monkeypatch.setattr(service, "authority_from_active_episode", lambda *_: object())
                original_apply(session)
            return PreparedStepResult(checkpoint=prepared.checkpoint, apply=change_then_apply)
        return prepared

    assert JobRunner(session_factory, {service.JOB_TYPE: execute}).run_job(result["job_id"])
    if restart:
        assert len(prompts) == 1
        with session_factory() as session, session.begin():
            store = JobStore(session)
            assert store.job_status(result["job_id"]).state == "failed_final"
            assert store.get_last_checkpoint(result["job_id"], "semantic:0000")
            store.retry_failed(result["job_id"])
        assert JobRunner(session_factory, {service.JOB_TYPE: execute}).run_job(result["job_id"])
    with session_factory() as session:
        store = JobStore(session)
        status = store.job_status(result["job_id"])
        assert store.get_job(result["job_id"]).payload_sha256 == payload_sha
        if changed_source:
            assert status.state == "failed_final" and len(store.list_steps(result["job_id"])) == 1
            assert not prompts and not saved
            checkpoint = store.get_last_checkpoint(result["job_id"], "calculate")
            assert checkpoint is None or "semantic_batches" not in checkpoint[1]
            return
        expected_batches = max(1, (count + semantics.BATCH_SIZE - 1) // semantics.BATCH_SIZE)
        assert status.state == "completed" and status.progress_completed == status.progress_total == 3 + expected_batches
        plan = store.get_last_checkpoint(result["job_id"], "calculate")[1]
        assert plan["context_id"] == frame.context_id and plan["review_run_id"] == frame.review_run_id
        assert [t for batch in plan["semantic_batches"] for t in batch] == targets
        assert len(prompts) == (expected_batches if count else 0)
        assert all(len(p["targets"]) <= semantics.BATCH_SIZE for p in prompts)
        assert all(p["pages"][0]["text"] == frame.source_pages[0].effective_text for p in prompts)
        assert composed == [{t["target_id"] for t in targets}] and saved == [True]
        assert len({sha256(json.dumps(p).encode()).hexdigest() for p in prompts}) == len(prompts)
