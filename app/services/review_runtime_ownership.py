"""Durable scheduling ownership, separate from clinical adoption authority."""
from sqlalchemy import and_, func, or_

from app.storage.codecs import verify_payload_sha256
from app.storage.models import JobRecord
from app.workflow.errors import InvalidJobDefinitionError
from app.workflow.jobstore import JobStore

OWNER = "prepared-review-runtime/v1"
WORKFLOW_JOB_TYPE = "prepared_review_workflow"
OWNED_TYPES = (
    "predicate_binding_candidates", "control_binding_candidates",
    "binding_qualification", "judgment_content", "proposition_evidence", "observation_relation",
    "frequency_evidence",
)


def prepared_review_job_scope():
    # Old isolated tasks can also have preparation IDs. Only an explicit owner
    # created through the product intake opts them into automatic scheduling.
    return or_(
        JobRecord.job_type.not_in((*OWNED_TYPES, WORKFLOW_JOB_TYPE)),
        and_(func.json_extract(JobRecord.payload_json, "$.execution_owner") == OWNER,
             func.json_extract(JobRecord.payload_json, "$.review_context_id").is_not(None),
             func.json_extract(JobRecord.payload_json, "$.review_context_sha256").is_not(None)),
    )


def mark_prepared_review_job(payload, *, enabled, session=None, parent_job_id=None,
                             workflow_job_id=None):
    if not enabled:
        return
    if not all(isinstance(payload.get(key), str) and payload[key].strip()
               for key in ("review_context_id", "review_context_sha256")):
        raise InvalidJobDefinitionError("正式核对任务必须关联已保存的审核准备记录")
    if parent_job_id is not None:
        parent = JobStore(session).get_job(parent_job_id)
        source = verify_payload_sha256(parent.payload_json, parent.payload_sha256)
        if (parent.job_type not in OWNED_TYPES or source.get("execution_owner") != OWNER
                or any(source.get(key) != payload[key]
                       for key in ("review_context_id", "review_context_sha256"))):
            raise InvalidJobDefinitionError("后续核对任务必须沿用同一次正式审核准备")
        inherited_workflow = source.get("workflow_job_id")
        if workflow_job_id is not None and workflow_job_id != inherited_workflow:
            raise InvalidJobDefinitionError("后续核对不能改挂另一份审核任务")
        workflow_job_id = inherited_workflow
    if workflow_job_id is not None:
        from app.services.prepared_review_workflow import require_current_review_tasks

        workflow = JobStore(session).get_job(workflow_job_id)
        frozen = verify_payload_sha256(workflow.payload_json, workflow.payload_sha256)
        if (workflow.job_type != WORKFLOW_JOB_TYPE or frozen.get("execution_owner") != OWNER
                or workflow.cancel_requested or workflow.state not in {"queued", "running"}
                or frozen.get("routes") != payload.get("routes")
                or any(frozen.get(key) != payload[key]
                       for key in ("review_context_id", "review_context_sha256"))):
            raise InvalidJobDefinitionError("本次审核已停止或资料、读取配置已变化，未启动后续核对")
        require_current_review_tasks(frozen)
        payload["workflow_job_id"] = workflow_job_id
    payload["execution_owner"] = OWNER
