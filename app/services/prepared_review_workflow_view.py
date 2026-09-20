"""Saved orchestration progress, separate from the frozen clinical report."""
from app.services.prepared_review_progress import TASK_KINDS
from app.services.prepared_review_workflow import PreparedReviewContinuation, require_workflow_scope
from app.storage.codecs import verify_payload_sha256
from app.workflow.jobstore import JobStore
from app.storage.repositories import AppendRepository, REVIEW_RUN_CONFIG, ScopeViolationError


def read_review_workflow(session, *, subject_id, review_episode_id, workflow_id):
    row, payload, context = require_workflow_scope(
        session, subject_id=subject_id, review_episode_id=review_episode_id, workflow_id=workflow_id,
    )
    children = PreparedReviewContinuation._children(session, workflow_id, payload)
    items = []
    for child in sorted(children, key=lambda item: (item.created_at, item.job_id)):
        child_payload = verify_payload_sha256(child.payload_json, child.payload_sha256)
        items.append({
            "job_id": child.job_id, "kind": TASK_KINDS[child.job_type],
            "candidate_job_id": child_payload.get("candidate_job_id"), "state": child.state,
            "progress_completed": child.progress_completed, "progress_total": child.progress_total,
        })
    steps = JobStore(session).list_steps(workflow_id)
    remaining = [step for step in steps if step.state != "completed"]
    report = AppendRepository(session, REVIEW_RUN_CONFIG).get_or_none(context.review_run_id)
    if report is not None and (report.subject_id != subject_id or report.review_episode_id != review_episode_id
                               or report.context_id != context.context_id):
        raise ScopeViolationError("已保存的审核报告与当前受试者及节点不对应")
    return {
        "job_id": workflow_id, "context_id": context.context_id,
        "context_sha256": context.context_sha256, "review_run_id": context.review_run_id,
        "state": row.state,
        "report_saved": report is not None and report.completed_at is not None,
        "stage_label": remaining[0].name if remaining else "本次核对已结束",
        "progress_completed": row.progress_completed, "progress_total": row.progress_total,
        "items": items,
    }
