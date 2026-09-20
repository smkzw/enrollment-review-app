"""Batch membership and progress from frozen contexts and owned workflows."""
from datetime import UTC
from app.services.batch_review_workflow import material, owned_workflows, validate_completed_members
from app.storage.repositories import ScopeViolationError
from app.storage.review_context_repository import ReviewContextV2Repository
from app.workflow.jobstore import JobStore
from sqlalchemy import func, select
from app.storage.models import JobRecord
from app.services.batch_review_workflow import BATCH_JOB_TYPE
from app.services.review_runtime_ownership import OWNER
from app.services.review_action_worklist import _workflow_stage_label
from app.storage.codecs import PersistedContractInvalid
from app.storage.repositories import ProjectRepository


def recent_review_batches(session, *, project_id, offset=0):
    if offset < 0 or offset > 100000:
        raise ScopeViolationError("批量记录的页码超出范围")
    ProjectRepository(session).get(project_id)
    rows = list(session.scalars(select(JobRecord).where(
        JobRecord.job_type == BATCH_JOB_TYPE,
        func.json_extract(JobRecord.payload_json, "$.execution_owner") == OWNER,
        func.json_extract(JobRecord.payload_json, "$.project_id") == project_id,
    ).order_by(JobRecord.created_at.desc(), JobRecord.job_id.desc()).offset(offset).limit(21)))
    items = []
    unavailable_count = 0
    for row in rows[:20]:
        try:
            _, payload = material(session, row.job_id)
            if payload["project_id"] != project_id:
                raise ScopeViolationError("批次项目归属不一致")
            created_at = row.created_at.replace(tzinfo=UTC) if row.created_at.tzinfo is None else row.created_at
            items.append({"job_id": row.job_id, "state": row.state, "member_count": len(payload["members"]),
                          "created_at": created_at.isoformat()})
        except (PersistedContractInvalid, ScopeViolationError):
            unavailable_count += 1
    return {"project_id": project_id, "has_more": len(rows) > 20, "offset": offset,
            "items": items, "unavailable_count": unavailable_count}


def batch_review_view(session, *, project_id, batch_id):
    row, payload = material(session, batch_id)
    if payload["project_id"] != project_id:
        raise ScopeViolationError("这批审核不属于所选研究项目")
    children = owned_workflows(session, batch_id, payload)
    validate_completed_members(session, batch_id, payload, children)
    store = JobStore(session)
    failure_detail = None
    if row.state in {"failed_final", "failed_retryable"}:
        for event in reversed(store.list_event_rows(batch_id)):
            if event.event.payload.get("error_code") == "BATCH_REVIEW_CONTINUATION_FAILED":
                failure_detail = event.event.payload.get("detail")
                break
    items = []
    for index, member in enumerate(payload["members"]):
        context = ReviewContextV2Repository(session).get(member["context_id"])
        if (context.context_sha256 != member["context_sha256"]
                or context.authority.project_id != project_id
                or context.authority.subject_id != member["subject_id"]
                or context.authority.review_episode_id != member["review_episode_id"]):
            raise ScopeViolationError("批量审核资料归属不一致")
        child = children.get(member["context_id"])
        checkpoint = store.get_last_checkpoint(batch_id, f"member_{index}")
        if checkpoint is not None and (
            child is None or checkpoint[1].get("workflow_job_id") != child[0].job_id
            or checkpoint[1].get("context_sha256") != member["context_sha256"]
        ):
            raise ScopeViolationError("批量审核完成记录与原资料不一致")
        items.append({"subject_id": member["subject_id"],
            "subject_code": context.subject.subject_code,
            "workflow_stage_label": _workflow_stage_label(review_run_id=context.review_run_id, context=context),
            "review_episode_id": member["review_episode_id"],
            "workflow_job_id": child[0].job_id if child else None,
            "state": child[0].state if child else "not_started",
            "recorded_state": checkpoint[1].get("member_state") if checkpoint else None})
    return {"job_id": batch_id, "project_id": project_id, "state": row.state,
            "items": items, "clinical_adoption": False, "failure_detail": failure_detail}
