"""Advance explicit review requests from the existing runner maintenance loop.

The parent is a normal durable Job, but never claims a model worker while its
children run. Its completion means the requested checks finished, not adoption.
"""
import logging

from sqlalchemy import and_, func, select, text
from sqlalchemy.orm import aliased

from app.domain.publication import canonical_hash
from app.services.job_service import JobService, StepSpec
from app.services.page_review_job_service import route_identity
from app.services.prepared_review_intake import require_prepared_review_intent
from app.services.review_runtime_ownership import OWNER, OWNED_TYPES, WORKFLOW_JOB_TYPE
from app.storage.codecs import PersistedContractInvalid, verify_payload_sha256
from app.storage.fact_authority import FactAuthorityError, FactAuthorityValidator
from app.storage.models import JobRecord
from app.storage.repositories import ScopeViolationError
from app.storage.review_context_repository import ReviewContextV2Repository
from app.workflow.errors import LeaseLostError
from app.workflow.jobstore import JobStore
from app.workflow.recovery import recover_expired_jobs

logger = logging.getLogger(__name__)
CONTRACT = "prepared-review-workflow/v7"
READABLE_CONTRACTS = {"prepared-review-workflow/v1", "prepared-review-workflow/v2", "prepared-review-workflow/v3", "prepared-review-workflow/v4", "prepared-review-workflow/v5", "prepared-review-workflow/v6", CONTRACT}
CHILD_TYPES = {
    "predicate": "predicate_binding_candidates", "control": "control_binding_candidates",
    "predicate_qualification": "binding_qualification", "control_qualification": "binding_qualification",
    "judgment_content": "judgment_content",
    "control_judgment_content": "judgment_content",
    "control_proposition_evidence": "proposition_evidence",
    "predicate_proposition_evidence": "proposition_evidence",
    "predicate_observation_relation": "observation_relation",
    "control_observation_relation": "observation_relation",
    "predicate_frequency_evidence": "frequency_evidence",
    "control_frequency_evidence": "frequency_evidence",
}


class ReviewDependencyFailed(RuntimeError):
    """A child stopped; completed or still-running siblings retain their work."""


def current_review_task_versions():
    from app.services.predicate_binding_job import PredicateBindingJobExecutor
    from app.services.control_binding_job import ControlBindingJobExecutor
    from app.services.binding_qualification import BindingQualificationJobExecutor
    from app.services.judgment_content_job import JudgmentContentJobExecutor
    from app.services.proposition_evidence_job import PropositionEvidenceJobExecutor
    from app.services.observation_relation_job import ObservationRelationJobExecutor
    from app.services.frequency_evidence_job import FrequencyEvidenceJobExecutor
    return {task.job_type: {"contract": task.contract, "prompt_version": task.prompt_version}
            for task in (PredicateBindingJobExecutor, ControlBindingJobExecutor,
                         BindingQualificationJobExecutor, JudgmentContentJobExecutor,
                         PropositionEvidenceJobExecutor, ObservationRelationJobExecutor, FrequencyEvidenceJobExecutor)}


def require_current_review_tasks(payload):
    if payload.get("contract") != CONTRACT or payload.get("task_versions") != current_review_task_versions():
        raise ScopeViolationError("审核方式已更新，请保留原记录并重新开始本次审核")


def enqueue_review_workflow(session_factory, routes, *, subject_id, review_episode_id, context_id,
                            batch_job_id=None):
    context = require_prepared_review_intent(
        session_factory, subject_id=subject_id, review_episode_id=review_episode_id,
        context_id=context_id, kind="predicate_candidates",
    )
    publication = context.clause_pack.control_publication
    payload = {
        "contract": CONTRACT, "execution_owner": OWNER,
        "review_context_id": context.context_id, "review_context_sha256": context.context_sha256,
        "routes": {lane.value: route_identity(route) for lane, route in routes.items()},
        "task_versions": current_review_task_versions(),
        "includes_controls": bool(publication is not None and publication.catalog.controls),
    }
    with session_factory() as session, session.begin():
        session.execute(text("BEGIN IMMEDIATE"))
        if batch_job_id is not None:
            from app.services.batch_review_workflow import require_batch_member
            require_batch_member(session, batch_job_id, context, payload)
            payload["batch_job_id"] = batch_job_id
        active = session.scalars(select(JobRecord).where(
            JobRecord.job_type == WORKFLOW_JOB_TYPE,
            JobRecord.state.not_in(("completed", "cancelled", "failed_final")),
            func.json_extract(JobRecord.payload_json, "$.review_context_id") == context_id,
        ))
        for row in active:
            existing = verify_payload_sha256(row.payload_json, row.payload_sha256)
            if existing.get("batch_job_id") != batch_job_id:
                raise ScopeViolationError("同一份资料已有其他审核正在进行，请待其结束后再提交")
        return JobService(session_factory).create_job_in_session(
            session, job_type=WORKFLOW_JOB_TYPE, payload=payload,
            idempotency_key=f"{CONTRACT}:{canonical_hash(payload)}",
            steps=[StepSpec("candidates", "核对资料与方案要求"),
                   StepSpec("verification", "复核原文与书面判断", depends_on=("candidates",)),
                   StepSpec("ready", "汇集本次核对记录", depends_on=("verification",))],
        )


class PreparedReviewContinuation:
    def __init__(self, session_factory, artifact_store, routes_provider, *, worker_id):
        self.session_factory = session_factory
        self.artifact_store = artifact_store
        self.routes_provider = routes_provider
        self.worker_id = worker_id

    @staticmethod
    def _material(session, workflow_id):
        row = JobStore(session).get_job(workflow_id)
        payload = verify_payload_sha256(row.payload_json, row.payload_sha256)
        if (row.job_type != WORKFLOW_JOB_TYPE or payload.get("contract") not in READABLE_CONTRACTS
                or payload.get("execution_owner") != OWNER):
            raise ScopeViolationError("本次审核记录不完整，未自动续算")
        context = ReviewContextV2Repository(session).get(payload["review_context_id"])
        if context.context_sha256 != payload.get("review_context_sha256"):
            raise ScopeViolationError("本次审核的资料记录已变化，未自动续算")
        publication = context.clause_pack.control_publication
        if payload.get("includes_controls") is not bool(publication is not None and publication.catalog.controls):
            raise ScopeViolationError("本次审核的方案要求范围不完整")
        return row, payload, context

    @staticmethod
    def _children(session, workflow_id, payload, *, for_cancellation=False):
        rows = list(session.scalars(select(JobRecord).where(
            JobRecord.job_type.in_(OWNED_TYPES),
            func.json_extract(JobRecord.payload_json, "$.workflow_job_id") == workflow_id,
        )))
        verified = []
        for row in rows:
            try:
                child = verify_payload_sha256(row.payload_json, row.payload_sha256)
                if (child.get("execution_owner") != OWNER
                        or any(child.get(key) != payload.get(key)
                               for key in ("review_context_id", "review_context_sha256", "routes"))):
                    raise ScopeViolationError("本次审核存在不一致的核对记录，未更改任务")
            except (PersistedContractInvalid, ScopeViolationError):
                if not for_cancellation:
                    raise
                logger.exception("核对记录归属无法确认，保留该记录并停止其他已确认任务")
                continue
            verified.append(row)
        return verified

    @classmethod
    def _cancel_owned(cls, store, workflow_id, payload):
        for child in cls._children(store.session, workflow_id, payload, for_cancellation=True):
            store.request_cancel(child.job_id)

    @classmethod
    def _cancel_boundary(cls, store, lease):
        payload = verify_payload_sha256(store.get_job(lease.job_id).payload_json,
                                         store.get_job(lease.job_id).payload_sha256)
        store.cancel_at_boundary(lease)
        cls._cancel_owned(store, lease.job_id, payload)

    def _cancel_children(self):
        parent = aliased(JobRecord)
        with self.session_factory() as session, session.begin():
            ids = list(session.scalars(select(parent.job_id).join(
                JobRecord, func.json_extract(JobRecord.payload_json, "$.workflow_job_id") == parent.job_id,
            ).where(
                parent.job_type == WORKFLOW_JOB_TYPE,
                func.json_extract(parent.payload_json, "$.execution_owner") == OWNER,
                parent.cancel_requested.is_(True), JobRecord.job_type.in_(OWNED_TYPES),
                JobRecord.state.not_in(("completed", "cancelled", "failed_final", "cancel_requested")),
            ).distinct().limit(50)))
            for workflow_id in ids:
                row = JobStore(session).get_job(workflow_id)
                try:
                    payload = verify_payload_sha256(row.payload_json, row.payload_sha256)
                except PersistedContractInvalid:
                    logger.exception("审核总记录无法核验，未改动其关联任务")
                    continue
                self._cancel_owned(JobStore(session), workflow_id, payload)

    def __call__(self, runner):
        recover_expired_jobs(self.session_factory, now=runner.now, job_scope=and_(
            JobRecord.job_type == WORKFLOW_JOB_TYPE,
            func.json_extract(JobRecord.payload_json, "$.execution_owner") == OWNER,
        ))
        self._cancel_children()
        with self.session_factory() as session, session.begin():
            workflow_id = session.scalar(select(JobRecord.job_id).where(
                JobRecord.job_type == WORKFLOW_JOB_TYPE, JobRecord.state == "queued",
                func.json_extract(JobRecord.payload_json, "$.execution_owner") == OWNER,
            ).order_by(JobRecord.updated_at, JobRecord.job_id).limit(1))
            if workflow_id is None:
                return
            lease = JobStore(session, lease_ttl=runner.lease_ttl).claim_job(workflow_id, self.worker_id)
        if lease is None:
            return
        try:
            with runner.lease_heartbeat(lease) as lease_ref:
                self._advance(lease_ref)
        except LeaseLostError:
            logger.info("审核衔接租约失效，保留持久记录等待恢复", exc_info=True)

    def _advance(self, lease_ref):
        lease = lease_ref[0]
        workflow_id = lease.job_id
        step_id = None
        try:
            with self.session_factory() as session:
                store = JobStore(session)
                step = store.next_runnable_step(workflow_id)
                if step is not None:
                    step_id = step.step_id
                _, payload, context = self._material(session, workflow_id)
                require_current_review_tasks(payload)
                steps = store.list_steps(workflow_id)
                if {item.step_id for item in steps} != {"candidates", "verification", "ready"}:
                    raise ScopeViolationError("本次审核的步骤记录不完整")
                if step_id is None and any(item.state != "completed" for item in steps):
                    raise ScopeViolationError("本次审核尚有未完成步骤")
                if step_id is not None:
                    FactAuthorityValidator(session).validate(context.authority)
                previous = None if step_id in (None, "candidates") else store.get_last_checkpoint(
                    workflow_id, "candidates" if step_id == "verification" else "verification")
                if step_id not in (None, "candidates"):
                    if previous is None:
                        raise ScopeViolationError("前一步审核记录缺失，未自动续算")
                    if not self._dependencies_complete(session, workflow_id, payload, previous[1], step_id):
                        with self.session_factory() as writer, writer.begin():
                            self._release(JobStore(writer), lease)
                        return
            result = {} if step_id is None else self._schedule(step_id, workflow_id, payload, context, previous)
            lease = lease_ref[0]
            with self.session_factory() as session, session.begin():
                store = JobStore(session)
                row = store.get_job(workflow_id)
                if row.cancel_requested:
                    self._cancel_boundary(store, lease)
                elif step_id is None:
                    store.finish_success(lease)
                else:
                    store.start_step(lease, step_id)
                    store.complete_step(lease, step_id, checkpoint_payload=result)
                    if step_id == "ready":
                        store.finish_success(lease)
                    else:
                        store.release_deferred(lease)
        except LeaseLostError:
            logger.info("审核衔接租约失效，保留持久记录等待恢复", exc_info=True)
        except Exception as exc:
            logger.exception("正式审核衔接未完成")
            lease = lease_ref[0]
            with self.session_factory() as session, session.begin():
                store = JobStore(session)
                if store.get_job(workflow_id).cancel_requested:
                    self._cancel_boundary(store, lease)
                elif step_id is not None:
                    store.start_step(lease, step_id)
                    store.fail_step(lease, step_id, retryable=False,
                                    error_code="PREPARED_REVIEW_CONTINUATION_FAILED",
                                    detail=(str(exc) if isinstance(exc, ScopeViolationError) else
                                            "本次审核衔接未完成，已保留完成记录，请核对失败步骤后重试"))
                    if isinstance(exc, (FactAuthorityError, ScopeViolationError)):
                        parent = store.get_job(workflow_id)
                        pinned = verify_payload_sha256(parent.payload_json, parent.payload_sha256)
                        self._cancel_owned(store, workflow_id, pinned)
                else:
                    store.finish_failure(lease)

    @classmethod
    def _release(cls, store, lease):
        if store.get_job(lease.job_id).cancel_requested:
            cls._cancel_boundary(store, lease)
        else:
            store.release_deferred(lease)

    @classmethod
    def _dependencies_complete(cls, session, workflow_id, payload, checkpoint, step_id):
        children = checkpoint.get("children")
        if not isinstance(children, dict) or not children:
            raise ScopeViolationError("前一步审核未保存核对任务清单")
        expected = {"predicate"} if step_id == "verification" else {"predicate_qualification", "judgment_content"}
        if step_id == "ready" and payload["contract"] in {"prepared-review-workflow/v5", "prepared-review-workflow/v6", CONTRACT}:
            expected.add("predicate_proposition_evidence")
        if step_id == "ready" and payload["contract"] in {"prepared-review-workflow/v6", CONTRACT}:
            expected.add("predicate_observation_relation")
        if step_id == "ready" and payload["contract"] == CONTRACT:
            expected.add("predicate_frequency_evidence")
        if payload["includes_controls"]:
            expected.add("control" if step_id == "verification" else "control_qualification")
            if step_id == "ready" and payload["contract"] != "prepared-review-workflow/v1":
                expected.add("control_judgment_content")
            if step_id == "ready" and payload["contract"] not in {"prepared-review-workflow/v1", "prepared-review-workflow/v2"}:
                expected.add("control_proposition_evidence")
            if step_id == "ready" and payload["contract"] in {"prepared-review-workflow/v6", CONTRACT}:
                expected.add("control_observation_relation")
            if step_id == "ready" and payload["contract"] == CONTRACT:
                expected.add("control_frequency_evidence")
        if set(children) != expected or checkpoint.get("review_context_sha256") != payload["review_context_sha256"]:
            raise ScopeViolationError("本次审核的核对范围或资料记录不完整")
        owned = {row.job_id: row for row in cls._children(session, workflow_id, payload)}
        if len(set(children.values())) != len(children):
            raise ScopeViolationError("本次审核的步骤引用重复")
        ready = True
        for name, job_id in children.items():
            row = owned.get(job_id)
            if row is None or row.job_type != CHILD_TYPES.get(name):
                raise ScopeViolationError("本次审核的前一步记录不对应")
            if step_id == "ready":
                origin = JobStore(session).get_last_checkpoint(workflow_id, "candidates")
                candidate_name = "control" if name in {"control_qualification", "control_judgment_content", "control_proposition_evidence", "control_observation_relation", "control_frequency_evidence"} else "predicate"
                child_payload = verify_payload_sha256(row.payload_json, row.payload_sha256)
                if (origin is None or child_payload.get("candidate_job_id")
                        != origin[1].get("children", {}).get(candidate_name)):
                    raise ScopeViolationError("后续核对与原始对应记录不一致")
            if row.state in {"failed_final", "cancelled"}:
                raise ReviewDependencyFailed("前一步核对未完成，请处理后再继续")
            ready = ready and row.state == "completed"
        return ready

    def _schedule(self, step_id, workflow_id, payload, context, previous):
        if step_id == "ready":
            return {"children": previous[1]["children"], "checks_complete": True,
                    "clinical_adoption": False, "review_context_sha256": context.context_sha256}
        routes = self.routes_provider()
        if {lane.value: route_identity(route) for lane, route in routes.items()} != payload["routes"]:
            raise ScopeViolationError("读取配置已变化，请使用原配置恢复或重新准备审核")
        if step_id == "candidates":
            from app.services.predicate_binding_job import enqueue_predicate_candidates
            from app.services.control_binding_job import enqueue_control_candidates
            arguments = dict(review_episode_id=context.authority.review_episode_id, routes=routes,
                             review_context_id=context.context_id, product_runtime=True,
                             workflow_job_id=workflow_id)
            children = {"predicate": enqueue_predicate_candidates(
                self.session_factory, component_ids=None, **arguments).job_id}
            if payload["includes_controls"]:
                children["control"] = enqueue_control_candidates(self.session_factory, **arguments).job_id
        elif step_id == "verification":
            from app.services.binding_qualification import enqueue_binding_qualification
            from app.services.judgment_content_job import enqueue_judgment_content
            candidates = previous[1]["children"]
            children = {f"{name}_qualification": enqueue_binding_qualification(
                self.session_factory, candidate_job_id=job_id, routes=routes,
                artifact_store=self.artifact_store, product_runtime=True).job_id
                for name, job_id in candidates.items()}
            children["judgment_content"] = enqueue_judgment_content(
                self.session_factory, candidate_job_id=candidates["predicate"],
                context_id=context.context_id, routes=routes, artifact_store=self.artifact_store,
                product_runtime=True).job_id
            if payload["contract"] in {"prepared-review-workflow/v5", "prepared-review-workflow/v6", CONTRACT}:
                from app.services.proposition_evidence_job import enqueue_proposition_evidence
                children["predicate_proposition_evidence"] = enqueue_proposition_evidence(
                    self.session_factory, candidate_job_id=candidates["predicate"],
                    context_id=context.context_id, routes=routes, artifact_store=self.artifact_store,
                    product_runtime=True).job_id
            if payload["includes_controls"] and payload["contract"] != "prepared-review-workflow/v1":
                children["control_judgment_content"] = enqueue_judgment_content(
                    self.session_factory, candidate_job_id=candidates["control"],
                    context_id=context.context_id, routes=routes, artifact_store=self.artifact_store,
                    product_runtime=True).job_id
            if payload["includes_controls"] and payload["contract"] not in {"prepared-review-workflow/v1", "prepared-review-workflow/v2"}:
                from app.services.proposition_evidence_job import enqueue_proposition_evidence
                children["control_proposition_evidence"] = enqueue_proposition_evidence(
                    self.session_factory, candidate_job_id=candidates["control"],
                    context_id=context.context_id, routes=routes, artifact_store=self.artifact_store,
                    product_runtime=True).job_id
            if payload["contract"] in {"prepared-review-workflow/v6", CONTRACT}:
                from app.services.observation_relation_job import enqueue_observation_relation
                for family, candidate_id in candidates.items():
                    children[f"{family}_observation_relation"] = enqueue_observation_relation(
                        self.session_factory, candidate_job_id=candidate_id, context_id=context.context_id,
                        routes=routes, artifact_store=self.artifact_store, product_runtime=True,
                    ).job_id
            if payload["contract"] == CONTRACT:
                from app.services.frequency_evidence_job import enqueue_frequency_evidence
                for family, candidate_id in candidates.items():
                    children[f"{family}_frequency_evidence"] = enqueue_frequency_evidence(
                        self.session_factory, candidate_job_id=candidate_id, context_id=context.context_id,
                        routes=routes, artifact_store=self.artifact_store, product_runtime=True,
                    ).job_id
        else:
            raise ScopeViolationError("本次审核包含未知步骤")
        return {"children": children, "review_context_sha256": context.context_sha256}


def require_workflow_scope(session, *, subject_id, review_episode_id, workflow_id):
    row, payload, context = PreparedReviewContinuation._material(session, workflow_id)
    if (context.authority.subject_id != subject_id
            or context.authority.review_episode_id != review_episode_id):
        raise ScopeViolationError("本次审核不属于所选受试者及节点")
    return row, payload, context


def cancel_workflow_children(session_factory, workflow_id):
    """Called after the existing cancellation transaction; never touches other work."""
    with session_factory() as session, session.begin():
        store = JobStore(session)
        row = store.get_job(workflow_id)
        if row.job_type != WORKFLOW_JOB_TYPE or not row.cancel_requested:
            return
        payload = verify_payload_sha256(row.payload_json, row.payload_sha256)
        if payload.get("execution_owner") != OWNER:
            return
        PreparedReviewContinuation._cancel_owned(store, workflow_id, payload)


def change_review_workflow(session_factory, *, subject_id, review_episode_id, workflow_id,
                           operation, routes=None):
    with session_factory() as session, session.begin():
        row, payload, context = require_workflow_scope(
            session, subject_id=subject_id, review_episode_id=review_episode_id, workflow_id=workflow_id,
        )
        store = JobStore(session)
        if operation == "cancel":
            result = store.request_cancel(workflow_id)
            PreparedReviewContinuation._cancel_owned(store, workflow_id, payload)
            return result
        children = PreparedReviewContinuation._children(session, workflow_id, payload)
        if operation != "retry":
            raise ScopeViolationError("不支持该审核操作")
        require_current_review_tasks(payload)
        FactAuthorityValidator(session).validate(context.authority)
        if routes is None or {lane.value: route_identity(route) for lane, route in routes.items()} != payload["routes"]:
            raise ScopeViolationError("读取配置已变化，不能把新模型接入原审核")
        if row.cancel_requested or any(child.cancel_requested or child.state == "cancelled" for child in children):
            raise ScopeViolationError("本次审核已取消，请重新准备审核，原记录仍保留")
        # Validate the parent transition before changing child states; one transaction.
        result = store.retry_failed(workflow_id)
        for child in children:
            if child.state in {"failed_final", "failed_retryable"}:
                store.retry_failed(child.job_id)
        return result
