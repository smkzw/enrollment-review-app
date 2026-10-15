"""Synthetic durable workflow checks, not clinical or provider acceptance."""
from types import SimpleNamespace

import pytest

from app.services import prepared_review_workflow as workflow
from app.services.job_service import JobService, StepSpec
from app.services.review_runtime_ownership import OWNER, WORKFLOW_JOB_TYPE
from app.storage.repositories import ScopeViolationError
from app.workflow.jobstore import JobStore
from app.workflow.runner import JobRunner


def _saved_workflow(session_factory, *, contract, controls=False, failed=False):
    service = JobService(session_factory)
    payload = {"contract": contract, "execution_owner": OWNER, "review_context_id": "synthetic-context",
               "review_context_sha256": "a" * 64, "routes": {}, "includes_controls": controls}
    parent = service.create_job(job_type=WORKFLOW_JOB_TYPE, payload=payload,
        idempotency_key=f"synthetic:{contract}:{controls}:{failed}",
        steps=[StepSpec("candidates", "核对来源")])
    families = ["predicate", "control"] if controls else ["predicate"]
    candidate_ids = {}
    for family in families:
        child = service.create_job(job_type=workflow.CHILD_TYPES[family],
            payload={**payload, "workflow_job_id": parent.job_id},
            idempotency_key=f"{parent.job_id}:{family}", steps=[StepSpec("summary", "保存候选")])
        candidate_ids[family] = child.job_id
    with session_factory() as session, session.begin():
        store = JobStore(session)
        lease = store.claim_job(parent.job_id, "synthetic-owner")
        store.start_step(lease, "candidates")
        store.complete_step(lease, "candidates", checkpoint_payload={"children": candidate_ids})
        store.finish_success(lease)
    names = {"predicate_qualification", "judgment_content", "predicate_proposition_evidence",
             "predicate_observation_relation", "predicate_frequency_evidence"}
    if controls:
        names |= {"control_qualification", "control_judgment_content", "control_proposition_evidence",
                  "control_observation_relation", "control_frequency_evidence"}
    if contract in workflow.COMPUTATION_CONTRACTS:
        names |= {f"{family}_computation_input" for family in families}
    if contract == workflow.CONTRACT:
        names |= {f"{family}_history_source_search" for family in families}
    children = {}
    for name in sorted(names):
        family = "control" if name.startswith("control_") else "predicate"
        child = service.create_job(job_type=workflow.CHILD_TYPES[name],
            payload={**payload, "workflow_job_id": parent.job_id, "candidate_job_id": candidate_ids[family]},
            idempotency_key=f"{parent.job_id}:{name}", steps=[StepSpec("summary", "保存核对")])
        if failed and name == "predicate_computation_input":
            from app.workflow.errors import StepFailure
            def fail(_context):
                raise StepFailure(retryable=False, error_code="SYNTHETIC_SOURCE_FAILURE")
            executor = fail
        else:
            executor = lambda _context: {"synthetic": True}
        JobRunner(session_factory, {workflow.CHILD_TYPES[name]: executor}).run_job(child.job_id)
        children[name] = child.job_id
    return parent.job_id, payload, {"children": children, "review_context_sha256": "a" * 64}


@pytest.mark.parametrize("contract", ["prepared-review-workflow/v7", "prepared-review-workflow/v8", "prepared-review-workflow/v9", workflow.CONTRACT])
@pytest.mark.parametrize("controls", [False, True])
def test_new_source_child_and_historical_scope_are_distinct(session_factory, contract, controls):
    parent, payload, checkpoint = _saved_workflow(session_factory, contract=contract, controls=controls)
    with session_factory() as session:
        assert workflow.PreparedReviewContinuation._dependencies_complete(
            session, parent, payload, checkpoint, "ready")
        before = {row.job_id: row.payload_sha256 for row in
                  workflow.PreparedReviewContinuation._children(session, parent, payload)}
        broken = {**checkpoint, "children": dict(checkpoint["children"])}
        if contract in workflow.COMPUTATION_CONTRACTS:
            broken["children"].pop("predicate_computation_input")
        else:
            broken["children"]["predicate_computation_input"] = "not-a-historical-child"
        with pytest.raises(ScopeViolationError, match="核对范围"):
            workflow.PreparedReviewContinuation._dependencies_complete(session, parent, payload, broken, "ready")
        assert before == {row.job_id: row.payload_sha256 for row in
                          workflow.PreparedReviewContinuation._children(session, parent, payload)}


def test_source_child_failure_does_not_make_parent_ready_or_rewrite_siblings(session_factory):
    parent, payload, checkpoint = _saved_workflow(session_factory, contract=workflow.CONTRACT, failed=True)
    with session_factory() as session:
        store = JobStore(session)
        with pytest.raises(workflow.ReviewDependencyFailed):
            workflow.PreparedReviewContinuation._dependencies_complete(session, parent, payload, checkpoint, "ready")
        assert store.get_job(checkpoint["children"]["predicate_qualification"]).state == "completed"
        assert store.get_job(checkpoint["children"]["predicate_computation_input"]).state == "failed_final"


@pytest.mark.parametrize("controls", [False, True])
def test_verification_schedules_source_checks_with_existing_owner_scope(monkeypatch, controls):
    calls = []
    def enqueue(*_args, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(job_id=f"synthetic-child-{len(calls)}")
    for module, function in (
        ("binding_qualification", "enqueue_binding_qualification"),
        ("judgment_content_job", "enqueue_judgment_content"),
        ("proposition_evidence_job", "enqueue_proposition_evidence"),
        ("observation_relation_job", "enqueue_observation_relation"),
        ("frequency_evidence_job", "enqueue_frequency_evidence"),
        ("computation_input_job", "enqueue_computation_input"),
        ("history_source_search_job", "enqueue_history_source_search"),
    ):
        monkeypatch.setattr(f"app.services.{module}.{function}", enqueue)
    continuation = workflow.PreparedReviewContinuation(None, object(), lambda: {}, worker_id="synthetic-owner")
    candidates = {"predicate": "candidate-predicate", **({"control": "candidate-control"} if controls else {})}
    context = SimpleNamespace(context_id="synthetic-context", context_sha256="a" * 64)
    result = continuation._schedule("verification", "synthetic-parent", {
        "routes": {}, "contract": workflow.CONTRACT, "includes_controls": controls,
    }, context, (None, {"children": candidates}))
    assert {name for name in result["children"] if name.endswith("computation_input")} == {
        f"{family}_computation_input" for family in candidates}
    source_calls = calls[-len(candidates):]
    assert {item["candidate_job_id"] for item in source_calls} == set(candidates.values())
    assert all(item["product_runtime"] is True and item["context_id"] == context.context_id
               for item in source_calls)
    versions = workflow.current_review_task_versions()
    assert versions["computation_input"]["contract"] == "computation-input-job/v2"
    assert versions["history_source_search"]["contract"] == "history-source-search-job/v2"
