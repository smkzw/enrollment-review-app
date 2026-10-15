"""Frozen single-project review batches on the existing durable job store."""
import logging

from sqlalchemy import and_, func, select

from app.services.job_service import JobService, StepSpec
from app.services.evidence_app_errors import is_database_busy_error
from app.services.page_review_job_service import route_identity
from app.services.prepared_review_intake import require_prepared_review_intent
from app.services.prepared_review_workflow import (
    PreparedReviewContinuation, current_review_task_versions, enqueue_review_workflow,
)
from app.services.review_runtime_ownership import OWNER, WORKFLOW_JOB_TYPE
from app.storage.codecs import PersistedContractInvalid, verify_payload_sha256
from app.storage.models import JobRecord
from app.storage.repositories import ScopeViolationError
from app.storage.review_context_repository import ReviewContextV2Repository
from app.workflow.errors import LeaseLostError
from app.workflow.jobstore import JobStore
from app.workflow.recovery import recover_expired_jobs
from app.workflow.states import TERMINAL_JOB_STATES

BATCH_JOB_TYPE = "batch_review_workflow"
CONTRACT = "batch-review-workflow/v1"
TERMINAL = set(TERMINAL_JOB_STATES)
logger = logging.getLogger(__name__)


def material(session, batch_id):
    row = JobStore(session).get_job(batch_id)
    payload = verify_payload_sha256(row.payload_json, row.payload_sha256)
    if (row.job_type != BATCH_JOB_TYPE or payload.get("contract") != CONTRACT
            or payload.get("execution_owner") != OWNER):
        raise ScopeViolationError("批量审核记录不完整")
    return row, payload


def require_batch_member(session, batch_id, context, workflow_payload):
    row, payload = material(session, batch_id)
    expected = next((item for item in payload["members"] if item["context_id"] == context.context_id), None)
    if (row.cancel_requested or row.state not in {"queued", "running"}
            or expected is None or expected["context_sha256"] != context.context_sha256
            or payload["project_id"] != context.authority.project_id
            or payload["routes"] != workflow_payload["routes"]
            or payload["task_versions"] != workflow_payload["task_versions"]):
        raise ScopeViolationError("批量审核已停止或资料、审核方式已变化，未启动该受试者审核")


def enqueue_batch_review(session_factory, routes, *, project_id, members, request_key):
    if not 1 <= len(members) <= 50 or len({item["context_id"] for item in members}) != len(members):
        raise ScopeViolationError("请一次选择1至50份不同的审核资料")
    frozen = []
    for item in members:
        context = require_prepared_review_intent(session_factory, **item, kind="predicate_candidates")
        if context.authority.project_id != project_id:
            raise ScopeViolationError("同一批审核必须属于同一个研究项目")
        frozen.append({**item, "context_sha256": context.context_sha256})
    if len({item["review_episode_id"] for item in frozen}) != len(frozen):
        raise ScopeViolationError("同一审核节点不能在本批中重复提交")
    payload = {"contract": CONTRACT, "execution_owner": OWNER, "project_id": project_id,
               "members": frozen, "routes": {lane.value: route_identity(route) for lane, route in routes.items()},
               "task_versions": current_review_task_versions()}
    return JobService(session_factory).create_job(
        job_type=BATCH_JOB_TYPE, payload=payload,
        idempotency_key=f"{CONTRACT}:{project_id}:{request_key}",
        steps=[StepSpec(f"member_{index}", f"审核第{index + 1}份资料",
                        depends_on=(() if index == 0 else (f"member_{index - 1}",)))
               for index in range(len(frozen))],
    )


def owned_workflows(session, batch_id, payload, *, for_cancellation=False):
    found = {}
    members = {item["context_id"]: item for item in payload["members"]}
    rows = session.scalars(select(JobRecord).where(
        JobRecord.job_type == WORKFLOW_JOB_TYPE,
        func.json_extract(JobRecord.payload_json, "$.batch_job_id") == batch_id,
    ))
    for row in rows:
        try:
            source = verify_payload_sha256(row.payload_json, row.payload_sha256)
            member = members.get(source.get("review_context_id"))
            if (member is None or source.get("execution_owner") != OWNER
                    or source.get("review_context_sha256") != member["context_sha256"]
                    or source.get("routes") != payload["routes"]
                    or source.get("task_versions") != payload["task_versions"]
                    or member["context_id"] in found):
                raise ScopeViolationError("批量审核的关联记录不一致，未更改其审核")
        except (PersistedContractInvalid, ScopeViolationError):
            if not for_cancellation:
                raise
            logger.exception("保留无法核实归属的批量成员，停止其他已核实成员")
            continue
        found[member["context_id"]] = (row, source)
    return found


def cancel_owned(session, batch_id, payload):
    store = JobStore(session)
    for row, source in owned_workflows(session, batch_id, payload, for_cancellation=True).values():
        if row.state not in TERMINAL:
            store.request_cancel(row.job_id)
            PreparedReviewContinuation._cancel_owned(store, row.job_id, source)


def validate_completed_members(session, batch_id, payload, owned):
    store = JobStore(session)
    steps = {item.step_id: item for item in store.list_steps(batch_id)}
    if set(steps) != {f"member_{index}" for index in range(len(payload["members"]))}:
        raise ScopeViolationError("批量审核步骤与所选资料不一致")
    for index, member in enumerate(payload["members"]):
        step = steps[f"member_{index}"]
        if step.state != "completed":
            continue
        checkpoint = store.get_last_checkpoint(batch_id, step.step_id)
        child = owned.get(member["context_id"])
        if (checkpoint is None or child is None
                or checkpoint[1].get("workflow_job_id") != child[0].job_id
                or checkpoint[1].get("context_sha256") != member["context_sha256"]
                or checkpoint[1].get("member_state") not in TERMINAL
                or checkpoint[1].get("clinical_adoption") is not False):
            raise ScopeViolationError("批量审核的已完成记录不能与原资料核对，未继续处理")


def cancel_batch_children(session_factory, batch_id):
    with session_factory() as session, session.begin():
        row = JobStore(session).get_job(batch_id)
        if row.job_type != BATCH_JOB_TYPE:
            return False
        if not row.cancel_requested:
            return True
        _, payload = material(session, batch_id)
        cancel_owned(session, batch_id, payload)
        return True


def change_batch_review(session_factory, routes, *, project_id, batch_id, operation):
    with session_factory() as session, session.begin():
        row, payload = material(session, batch_id)
        if payload["project_id"] != project_id:
            raise ScopeViolationError("这批审核不属于所选研究项目")
        store = JobStore(session)
        if operation == "cancel":
            result = store.request_cancel(batch_id)
            cancel_owned(session, batch_id, payload)
            return result
        if operation != "retry" or row.cancel_requested:
            raise ScopeViolationError("已停止的批量审核不能重试，请重新准备未完成资料")
        if (payload["task_versions"] != current_review_task_versions()
                or payload["routes"] != {lane.value: route_identity(route) for lane, route in routes.items()}):
            raise ScopeViolationError("审核方式或读取配置已变化，不能混用新旧方式继续")
        return store.retry_failed(batch_id)


class BatchReviewRetryService:
    def __init__(self, session_factory, routes_provider):
        self.session_factory = session_factory
        self.routes_provider = routes_provider

    def retry(self, batch_id):
        with self.session_factory() as session:
            _, payload = material(session, batch_id)
        return change_batch_review(self.session_factory, self.routes_provider(),
            project_id=payload["project_id"], batch_id=batch_id, operation="retry")


class BatchReviewContinuation:
    def __init__(self, session_factory, routes_provider, *, worker_id):
        self.session_factory = session_factory
        self.routes_provider = routes_provider
        self.worker_id = worker_id

    def __call__(self, runner):
        recover_expired_jobs(self.session_factory, now=runner.now, job_scope=and_(
            JobRecord.job_type == BATCH_JOB_TYPE,
            func.json_extract(JobRecord.payload_json, "$.execution_owner") == OWNER,
        ))
        with self.session_factory() as session, session.begin():
            cancelled = list(session.scalars(select(JobRecord.job_id).where(
                JobRecord.job_type == BATCH_JOB_TYPE, JobRecord.cancel_requested.is_(True),
                func.json_extract(JobRecord.payload_json, "$.execution_owner") == OWNER,
            )))
            for batch_id in cancelled:
                try:
                    _, payload = material(session, batch_id)
                    cancel_owned(session, batch_id, payload)
                except (PersistedContractInvalid, ScopeViolationError):
                    logger.exception("批量记录无法核实，保留该记录并继续处理其他审核")
            batch_id = session.scalar(select(JobRecord.job_id).where(
                JobRecord.job_type == BATCH_JOB_TYPE, JobRecord.state == "queued",
                func.json_extract(JobRecord.payload_json, "$.execution_owner") == OWNER,
            ).order_by(JobRecord.updated_at, JobRecord.job_id).limit(1))
            if batch_id is None:
                return
            lease = JobStore(session, lease_ttl=runner.lease_ttl).claim_job(batch_id, self.worker_id)
        if lease is None:
            return
        with runner.lease_heartbeat(lease) as lease_ref:
            self._advance(lease_ref)

    def _advance(self, lease_ref):
        batch_id = lease_ref[0].job_id
        step_id = None
        try:
            with self.session_factory() as session:
                store = JobStore(session)
                row, payload = material(session, batch_id)
                step = store.next_runnable_step(batch_id)
                step_id = step.step_id if step else None
                if {item.step_id for item in store.list_steps(batch_id)} != {
                    f"member_{index}" for index in range(len(payload["members"]))
                }:
                    raise ScopeViolationError("批量审核步骤与所选资料不一致")
                if step_id is None:
                    raise ScopeViolationError("批量审核缺少可处理步骤")
                member = payload["members"][int(step_id.removeprefix("member_"))]
                context = ReviewContextV2Repository(session).get(member["context_id"])
                if context.context_sha256 != member["context_sha256"]:
                    raise ScopeViolationError("本批审核资料记录已变化")
                owned = owned_workflows(session, batch_id, payload)
                validate_completed_members(session, batch_id, payload, owned)
                existing = owned.get(member["context_id"])
                child_id = existing[0].job_id if existing else None
            if child_id is None:
                if payload["task_versions"] != current_review_task_versions():
                    raise ScopeViolationError("审核方式已更新，请保留本批记录并重新准备未完成资料")
                routes = self.routes_provider()
                if payload["routes"] != {lane.value: route_identity(route) for lane, route in routes.items()}:
                    raise ScopeViolationError("读取配置已变化，请恢复原配置后继续")
                child_id = enqueue_review_workflow(self.session_factory, routes,
                    subject_id=member["subject_id"], review_episode_id=member["review_episode_id"],
                    context_id=member["context_id"], batch_job_id=batch_id).job_id
            with self.session_factory() as session, session.begin():
                store = JobStore(session)
                row, payload = material(session, batch_id)
                owned = owned_workflows(session, batch_id, payload)
                child = owned[member["context_id"]][0]
                if child.job_id != child_id:
                    raise ScopeViolationError("批量审核关联已变化")
                if row.cancel_requested:
                    store.cancel_at_boundary(lease_ref[0])
                    cancel_owned(session, batch_id, payload)
                elif child.state not in TERMINAL:
                    store.release_deferred(lease_ref[0])
                else:
                    store.start_step(lease_ref[0], step_id)
                    store.complete_step(lease_ref[0], step_id, checkpoint_payload={
                        "workflow_job_id": child_id, "context_sha256": member["context_sha256"],
                        "member_state": child.state, "clinical_adoption": False,
                    })
                    if all(item.state == "completed" for item in store.list_steps(batch_id)):
                        store.finish_success(lease_ref[0])
                    else:
                        store.release_deferred(lease_ref[0])
        except LeaseLostError:
            logger.info("批量审核衔接租约已释放，保留记录等待恢复", exc_info=True)
        except Exception as exc:
            logger.exception("批量审核衔接未完成")
            with self.session_factory() as session, session.begin():
                store = JobStore(session)
                if store.get_job(batch_id).cancel_requested:
                    store.cancel_at_boundary(lease_ref[0])
                    _, payload = material(session, batch_id)
                    cancel_owned(session, batch_id, payload)
                elif is_database_busy_error(exc):
                    store.release_deferred(lease_ref[0])
                elif step_id is not None:
                    store.start_step(lease_ref[0], step_id)
                    store.fail_step(lease_ref[0], step_id, retryable=False,
                        error_code="BATCH_REVIEW_CONTINUATION_FAILED",
                        detail=str(exc) if isinstance(exc, ScopeViolationError) else "批量审核暂未完成，已保留先前记录")
                else:
                    store.finish_failure(lease_ref[0])
