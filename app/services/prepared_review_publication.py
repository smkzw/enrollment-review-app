"""Publish from a completed product workflow without accepting client job lists."""
from app.services.prepared_review_workflow import (
    PreparedReviewContinuation, ReviewDependencyFailed, require_workflow_scope, require_current_review_tasks,
)
from app.services.qualified_review_command import submit_qualified_review
from app.storage.repositories import ScopeViolationError
from app.workflow.jobstore import JobStore


def publish_prepared_review(session, artifact_store, *, subject_id: str,
                            review_episode_id: str, workflow_id: str,
                            method_approval_gate_id: str) -> str:
    """Caller owns the transaction; method approval remains independently verified."""
    row, payload, context = require_workflow_scope(
        session, subject_id=subject_id, review_episode_id=review_episode_id,
        workflow_id=workflow_id,
    )
    if row.state != "completed" or row.cancel_requested:
        raise ScopeViolationError("本次核对尚未完成，暂不能生成审核报告")
    require_current_review_tasks(payload)
    if not method_approval_gate_id.strip():
        raise ScopeViolationError("当前审核方式尚未完成验证，暂不能生成正式报告")
    store = JobStore(session)
    candidates = store.get_last_checkpoint(workflow_id, "candidates")
    verification = store.get_last_checkpoint(workflow_id, "verification")
    ready = store.get_last_checkpoint(workflow_id, "ready")
    if candidates is None or verification is None or ready is None:
        raise ScopeViolationError("本次核对记录尚不完整，未生成审核报告")
    try:
        for checkpoint, step in ((candidates, "verification"), (verification, "ready")):
            if not PreparedReviewContinuation._dependencies_complete(
                session, workflow_id, payload, checkpoint[1], step,
            ):
                raise ScopeViolationError("本次核对仍有未完成内容，未生成审核报告")
    except ReviewDependencyFailed as exc:
        raise ScopeViolationError("本次核对有未完成或已取消的内容，未生成审核报告") from exc
    summary = ready[1]
    if (summary.get("checks_complete") is not True
            or summary.get("clinical_adoption") is not False
            or summary.get("review_context_sha256") != context.context_sha256
            or summary.get("children") != verification[1]["children"]):
        raise ScopeViolationError("本次核对完成记录不对应，未生成审核报告")
    children = verification[1]["children"]
    qualifications = [children["predicate_qualification"]]
    content_jobs = {children["predicate_qualification"]: children["judgment_content"]}
    proposition_jobs = {}
    observation_jobs = {}
    frequency_jobs = {}
    if payload["includes_controls"]:
        qualifications.append(children["control_qualification"])
        if "control_judgment_content" in children:
            content_jobs[children["control_qualification"]] = children["control_judgment_content"]
    for family in ("predicate", "control"):
        name = f"{family}_proposition_evidence"
        if name in children:
            from app.services.proposition_evidence_receipts import verify_completed_proposition_evidence
            evidence = verify_completed_proposition_evidence(
                session, artifact_store, children[name],
            )
            if evidence["payload"]["identity_coverage"]:
                proposition_jobs[children[f"{family}_qualification"]] = children[name]
        observation_name = f"{family}_observation_relation"
        if observation_name in children:
            from app.services.observation_relation_job import verify_completed_observation_relation
            evidence = verify_completed_observation_relation(session, artifact_store, children[observation_name])
            if evidence["payload"]["identity_coverage"]:
                observation_jobs[children[f"{family}_qualification"]] = children[observation_name]
        frequency_name = f"{family}_frequency_evidence"
        if frequency_name in children:
            from app.services.frequency_evidence_job import verify_completed_frequency_evidence
            evidence = verify_completed_frequency_evidence(session, artifact_store, children[frequency_name])
            if evidence["payload"]["identity_coverage"]:
                frequency_jobs[children[f"{family}_qualification"]] = children[frequency_name]
    return submit_qualified_review(
        session, artifact_store, subject_id=subject_id, review_episode_id=review_episode_id,
        context_id=context.context_id, qualification_job_ids=qualifications,
        judgment_content_job_ids=content_jobs,
        proposition_evidence_job_ids=proposition_jobs,
        observation_relation_job_ids=observation_jobs,
        frequency_evidence_job_ids=frequency_jobs,
        method_approval_gate_id=method_approval_gate_id,
        idempotency_key=f"prepared-review-publication:{workflow_id}",
    )
