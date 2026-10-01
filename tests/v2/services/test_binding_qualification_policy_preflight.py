"""Rule-side policy gaps stop before qualification, not as missing patient data."""

import json
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from app.domain.contracts.page_review import PageReviewLane
from app.domain.contracts.predicate_binding import predicate_component_identity_sha256
from app.domain.contracts.rules import EvidenceRequirement
from app.evidence.artifacts import ArtifactStore
from app.llm.page_review_harness import PageCompletion
from app.services.binding_qualification import (
    JOB_TYPE as QUALIFICATION_TYPE,
    QualificationSourcePolicyError,
    enqueue_binding_qualification,
)
from app.services.job_service import JobService, StepSpec
from app.services.predicate_binding_job import (
    JOB_TYPE, PredicateBindingJobExecutor, enqueue_predicate_candidates,
)
from app.services.prepared_review_workflow import PreparedReviewContinuation
from app.storage.models import JobRecord
from app.workflow.jobstore import JobStore
from app.workflow.runner import JobRunner
from tests.v2.llm.test_predicate_binding_candidates import _case, _route
from tests.v2.services.test_predicate_binding_input import _frozen_input


def _input(policy):
    frozen, response = _case()
    component = frozen.components[0]
    if policy != "missing":
        refs = [] if policy == "unattributed" else [
            item.predicate_id for item in component.trigger_predicates
        ]
        if policy == "mixed":
            refs = refs[:1]
        requirement = EvidenceRequirement(
            requirement_id="synthetic-source-policy", rule_component_id=component.rule_component_id,
            fact_type="vital_sign", due_stage="screening", description="核对本条件的原始记录",
            allows_screening_record_transcription=True,
            requires_contemporaneous_objective_source=False, predicate_ids=refs,
        )
        values = {name: getattr(component, name) for name in (
            "rule_component_id", "parent_rule_id", "official_code", "kind", "display_code",
            "title", "rule_source_text", "expression", "exception_expression",
            "trigger_predicates", "exception_predicates", "repeat_trigger_conditions",
        )}
        values["evidence_requirements"] = [requirement]
        component = component.model_copy(update={
            "evidence_requirements": [requirement],
            "component_identity_sha256": predicate_component_identity_sha256(**values),
        })
        frozen = _frozen_input([component], frozen.facts, frozen.locators)
    return frozen, response


@pytest.mark.parametrize("policy", ["missing", "unattributed", "present", "mixed"])
def test_actual_candidate_receipts_precede_policy_preflight(
    session_factory, data_paths, monkeypatch, policy,
):
    frozen, response = _input(policy)
    monkeypatch.setattr("app.services.predicate_binding_job.build_predicate_binding_frozen_input",
                        lambda *args, **kwargs: frozen)
    routes = {lane: _route(lane=lane) for lane in (PageReviewLane.MAIN_A, PageReviewLane.MAIN_B)}
    artifacts = ArtifactStore(data_paths)

    async def completion(*args):
        return PageCompletion(json.dumps(response), "stop", {})

    candidate = enqueue_predicate_candidates(
        session_factory, review_episode_id="synthetic", component_ids=["component-a"], routes=routes,
    )
    JobRunner(session_factory, {JOB_TYPE: PredicateBindingJobExecutor(
        session_factory, artifacts, routes, completion=completion,
    )}).run_job(candidate.job_id)
    with session_factory() as session:
        original = JobStore(session).get_job(candidate.job_id).payload_sha256
        assert JobStore(session).get_job(candidate.job_id).state == "completed"
    if policy in {"missing", "unattributed"}:
        with pytest.raises(QualificationSourcePolicyError, match="这不是受试者资料缺失"):
            enqueue_binding_qualification(
                session_factory, candidate_job_id=candidate.job_id, routes=routes, artifact_store=artifacts,
            )
        with session_factory() as session:
            assert session.scalar(select(func.count()).select_from(JobRecord).where(
                JobRecord.job_type == QUALIFICATION_TYPE,
            )) == 0
    else:
        # An independent attributable pair keeps the normal path open. Mixed
        # input is not labelled fully qualified and no missing policy is inferred.
        result = enqueue_binding_qualification(
            session_factory, candidate_job_id=candidate.job_id, routes=routes, artifact_store=artifacts,
        )
        with session_factory() as session:
            job = JobStore(session).get_job(result.job_id)
            assert job.state == "queued"
            material = json.loads(job.payload_json)
            assert material["contract"] == "binding-qualification-job/v3"
            statuses = {pair["source_policy_status"] for pair in material["pairs"]}
            assert statuses == ({"present", "missing"} if policy == "mixed" else {"present"})
    with session_factory() as session:
        assert JobStore(session).get_job(candidate.job_id).payload_sha256 == original
        assert JobStore(session).get_job(candidate.job_id).state == "completed"


def test_continuation_persists_specific_policy_failure_and_preserves_previous_step(
    session_factory, monkeypatch,
):
    from app.services import prepared_review_workflow as module

    job = JobService(session_factory).create_job(
        idempotency_key="synthetic-policy-continuation", job_type="prepared_review_workflow",
        steps=[StepSpec("candidates", "核对原文"),
               StepSpec("verification", "核对采用要求", depends_on=("candidates",)),
               StepSpec("ready", "汇集结果", depends_on=("verification",))],
    )
    with session_factory() as session, session.begin():
        store = JobStore(session)
        lease = store.claim_job(job.job_id, "synthetic-owner")
        store.start_step(lease, "candidates")
        store.complete_step(lease, "candidates", checkpoint_payload={"children": {}})
        candidate_checkpoint = store.get_last_checkpoint(job.job_id, "candidates")
        store.release_deferred(lease)
    with session_factory() as session, session.begin():
        lease = JobStore(session).claim_job(job.job_id, "synthetic-owner")
    continuation = PreparedReviewContinuation(session_factory, None, lambda: {}, worker_id="synthetic-owner")
    monkeypatch.setattr(continuation, "_material", lambda *args: (
        None, {}, SimpleNamespace(authority=object()),
    ))
    monkeypatch.setattr(module, "require_current_review_tasks", lambda *args: None)
    monkeypatch.setattr(module, "FactAuthorityValidator", lambda *args: SimpleNamespace(validate=lambda *args: None))
    monkeypatch.setattr(continuation, "_dependencies_complete", lambda *args: True)

    def schedule(*args):
        raise QualificationSourcePolicyError()

    monkeypatch.setattr(continuation, "_schedule", schedule)
    continuation._advance([lease])
    with session_factory() as session:
        store = JobStore(session)
        steps = {step.step_id: step for step in store.list_steps(job.job_id)}
        assert steps["verification"].error_code == "REVIEW_SOURCE_POLICY_NOT_READY"
        failures = [row.event for row in store.list_event_rows(job.job_id)
                    if row.event.step_id == "verification"
                    and row.event.payload.get("error_code") == "REVIEW_SOURCE_POLICY_NOT_READY"]
        assert len(failures) == 1
        assert "不需要因此重复上传原件" in failures[0].payload["detail"]
        assert steps["candidates"].state == "completed"
        assert store.get_last_checkpoint(job.job_id, "candidates") == candidate_checkpoint
        assert store.get_last_checkpoint(job.job_id, "ready") is None

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api.v2.qualified_review import router
    from app.services import prepared_review_workflow_view as view
    from app.services.page_review_runtime import PageReviewRuntime
    from app.services.evidence_app_errors import EvidenceAppError
    from app.storage.repositories import ScopeViolationError

    context = SimpleNamespace(context_id="synthetic-context", context_sha256="a" * 64,
                              review_run_id="synthetic-run")
    def scoped(session, *, subject_id, review_episode_id, workflow_id):
        if (subject_id, review_episode_id, workflow_id) != ("synthetic", "screen", job.job_id):
            raise ScopeViolationError("本次审核不属于所选受试者及节点")
        return JobStore(session).get_job(job.job_id), {}, context
    monkeypatch.setattr(module, "require_workflow_scope", scoped)
    monkeypatch.setattr(view, "require_workflow_scope", scoped)
    monkeypatch.setattr(PreparedReviewContinuation, "_children", lambda *args, **kwargs: [])
    app = FastAPI()
    app.include_router(router)
    app.state.session_factory = session_factory
    with TestClient(app) as client:
        response = client.get(f"/api/v2/subjects/synthetic/review-episodes/screen/prepared-review-workflows/{job.job_id}")
    assert response.status_code == 200
    assert response.json()["retry_available"] is False
    assert "这不是受试者资料缺失" in response.json()["failure_reason"]

    runtime = PageReviewRuntime(session_factory, None)
    monkeypatch.setattr(runtime, "_prepare", lambda: pytest.fail("政策缺口不能初始化模型"))
    with pytest.raises(EvidenceAppError, match="完善方案"):
        runtime.retry_review_workflow(subject_id="synthetic", review_episode_id="screen", workflow_id=job.job_id)
    with pytest.raises(ScopeViolationError, match="完善方案"):
        module.change_review_workflow(session_factory, subject_id="synthetic",
                                      review_episode_id="screen", workflow_id=job.job_id, operation="retry")
    with session_factory() as session:
        assert JobStore(session).get_job(job.job_id).state == "failed_final"
        assert JobStore(session).get_last_checkpoint(job.job_id, "candidates") == candidate_checkpoint

    # Cancellation of a terminal failure is a no-op, not a way to erase its
    # recorded reason or pretend the failed preparation was cancelled.
    module.change_review_workflow(session_factory, subject_id="synthetic",
                                  review_episode_id="screen", workflow_id=job.job_id, operation="cancel")
    with session_factory() as session:
        projection = view.read_review_workflow(session, subject_id="synthetic",
                                              review_episode_id="screen", workflow_id=job.job_id)
    assert projection["state"] == "failed_final"
    assert "这不是受试者资料缺失" in projection["failure_reason"]
    assert projection["retry_available"] is False


def test_ordinary_failure_remains_recoverable_in_saved_workflow_view(session_factory, monkeypatch):
    from app.services import prepared_review_workflow_view as view

    job = JobService(session_factory).create_job(
        idempotency_key="synthetic-transient-continuation", job_type="prepared_review_workflow",
        steps=[StepSpec("verification", "复核原文依据")],
    )
    with session_factory() as session, session.begin():
        store = JobStore(session)
        lease = store.claim_job(job.job_id, "synthetic-owner")
        store.start_step(lease, "verification")
        store.fail_step(lease, "verification", error_code="TEMPORARY_SERVICE_FAILURE", retryable=False)
    context = SimpleNamespace(context_id="synthetic-context", context_sha256="a" * 64,
                              review_run_id="synthetic-run")
    monkeypatch.setattr(view, "require_workflow_scope", lambda session, **kwargs: (
        JobStore(session).get_job(job.job_id), {}, context,
    ))
    monkeypatch.setattr(PreparedReviewContinuation, "_children", lambda *args, **kwargs: [])
    with session_factory() as session:
        result = view.read_review_workflow(session, subject_id="synthetic",
                                          review_episode_id="screen", workflow_id=job.job_id)
    assert result["retry_available"] is True
    assert result["failure_reason"] is None
