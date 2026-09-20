"""Persist isolated correspondence candidates, never clinical assessments."""

import asyncio
import dataclasses
import json
from time import monotonic

from app.domain.contracts.page_review import PageReviewLane
from app.domain.contracts.predicate_binding import PredicateBindingFrozenInput
from app.domain.publication import canonical_hash
from app.llm.predicate_binding_candidates import (
    PROMPT_VERSION, BATCH_PROMPT_VERSION, PredicateCandidateReadError, read_predicate_candidates,
    predicate_binding_prompt_input,
    candidate_value_shape,
    validate_predicate_candidates,
    build_predicate_binding_messages,
)
from app.services.binding_candidate_comparison import COMPARISON_VERSION, compare_candidate_declarations
from app.llm.predicate_binding_batches import PredicateBindingBatch, plan_binding_batches
from app.llm.page_review_harness import direct_completion
from app.llm.page_reader_capabilities import LOCAL_PAGE_PROVIDERS
from app.llm.page_review_transport_options import page_completion_options
from app.services.job_service import JobService, StepSpec
from app.services.page_review_cancellation import run_cancellable
from app.services.page_review_job_service import route_identity
from app.services.predicate_binding_input import build_predicate_binding_frozen_input
from app.workflow.errors import InvalidJobDefinitionError, StepFailure
from app.workflow.jobstore import JobStore
from app.workflow.runner import PreparedStepResult

JOB_TYPE = "predicate_binding_candidates"
CONTRACT = "predicate-binding-candidate-job/v8"
LANES = (PageReviewLane.MAIN_A, PageReviewLane.MAIN_B)


def _reads(payload):
    if payload.get("batches") is None:
        return [(f"read:{lane.value}", lane, None) for lane in LANES]
    return [(f"read:{index}:{lane.value}", lane, PredicateBindingBatch.model_validate(batch))
            for index, batch in enumerate(payload["batches"]) for lane in LANES]


def enqueue_predicate_candidates(session_factory, *, review_episode_id, component_ids, routes,
                                 batch_max_characters=None, review_context_id=None, product_runtime=False,
                                 workflow_job_id=None):
    """Caller preflights routes; no automatic scheduling or acceptance is added."""
    if set(routes) != set(LANES) or any(route.lane != lane for lane, route in routes.items()):
        raise InvalidJobDefinitionError("需要两个完整且对应一致的独立读取配置")
    if any(not 65536 <= route.max_tokens <= 131072 for route in routes.values()):
        raise InvalidJobDefinitionError("对应任务输出额度不足或超出约定范围")
    with session_factory() as session, session.begin():
        frozen = build_predicate_binding_frozen_input(
            session, review_episode_id, component_ids=component_ids,
        )
        payload = {
            "contract": CONTRACT, "prompt_version": PROMPT_VERSION,
            "purpose": "isolated_unverified_candidates",
            "frozen_input": frozen.model_dump(mode="json"),
            "routes": {lane.value: route_identity(routes[lane]) for lane in LANES},
            "batch_max_characters": batch_max_characters,
            "batch_prompt_version": BATCH_PROMPT_VERSION,
            "batches": None,
        }
        if review_context_id is not None:
            from app.services.review_candidate_scope import require_prepared_candidate_scope
            payload["review_context_sha256"] = require_prepared_candidate_scope(
                session, review_context_id, frozen,
            )
            payload["review_context_id"] = review_context_id
        from app.services.review_runtime_ownership import mark_prepared_review_job
        mark_prepared_review_job(payload, enabled=product_runtime, session=session,
                                 workflow_job_id=workflow_job_id)
        if batch_max_characters is not None:
            payload["batches"] = [batch.model_dump(mode="json") for batch in plan_binding_batches(
                frozen, predicate_binding_prompt_input(frozen), max_characters=batch_max_characters)]
        steps = []
        previous = {}
        for step_id, lane, _ in _reads(payload):
            steps.append(StepSpec(step_id=step_id, name="核对资料与审核条件的对应",
                                  depends_on=(previous[lane],) if lane in previous else ()))
            previous[lane] = step_id
        # Each lane stays serial; two local platforms must also stay serial.
        # Freeze this policy for unbatched reads too, rather than using the
        # runner's serial default for two otherwise independent requests.
        local_count = sum(route.provider in LOCAL_PAGE_PROVIDERS for route in routes.values())
        payload["execution_control"] = {
            "max_parallel_steps": 1 if local_count == 2 else 2,
            "parallelizable_step_ids": [step.step_id for step in steps],
        }
        steps.append(StepSpec(step_id="summary", name="保存尚未核实的对应结果",
                              depends_on=tuple(step.step_id for step in steps)))
        return JobService(session_factory).create_job_in_session(
            session, idempotency_key=f"{JOB_TYPE}:{canonical_hash(payload)}",
            job_type=JOB_TYPE, payload=payload, steps=steps,
        )


class PredicateBindingJobExecutor:
    job_type = JOB_TYPE
    contract = CONTRACT
    prompt_version = PROMPT_VERSION
    batch_prompt_version = BATCH_PROMPT_VERSION
    frozen_input_type = PredicateBindingFrozenInput
    error_prefix = "PREDICATE"
    candidate_identity_field = "predicate_identity_sha256"

    def __init__(self, session_factory, artifact_store, routes, *, completion=direct_completion):
        self.session_factory = session_factory
        self.artifact_store = artifact_store
        self.routes = routes
        self.completion = completion

    def _verify_current(self, session, frozen):
        current = build_predicate_binding_frozen_input(
            session, frozen.authority.review_episode_id,
            component_ids=[component.rule_component_id for component in frozen.components],
        )
        if current.frozen_input_sha256 != frozen.frozen_input_sha256:
            raise StepFailure(retryable=False, error_code="PREDICATE_INPUT_CHANGED",
                              detail="资料或审核要求已变化，请保留旧结果并重新核对")

    def _put(self, value):
        return self.artifact_store.put(
            "raw_response", json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8"),
        ).sha256

    def _validate_batches(self, payload, frozen):
        if payload.get("batch_max_characters") is not None:
            expected = [batch.model_dump(mode="json") for batch in plan_binding_batches(
                frozen, predicate_binding_prompt_input(frozen), max_characters=payload["batch_max_characters"])]
            if payload.get("batches") != expected:
                raise StepFailure(retryable=False, error_code="PREDICATE_BATCH_SCOPE_CHANGED")
        elif payload.get("batches") is not None:
            raise StepFailure(retryable=False, error_code="PREDICATE_BATCH_SCOPE_CHANGED")

    async def _read(self, frozen, route, recorded, batch):
        return await read_predicate_candidates(frozen, route, completion=recorded, batch=batch)

    def _validate_candidate_payload(self, frozen, raw_text, batch):
        return validate_predicate_candidates(frozen, raw_text, batch=batch)

    def _build_messages(self, frozen, batch):
        return build_predicate_binding_messages(frozen, batch=batch)

    def _comparison_artifact(self, frozen, payload, reads, *, job_id):
        groups = {}
        for step_id, lane, batch in _reads(payload):
            read = reads[step_id]
            artifact = json.loads(self.artifact_store.read_by_sha("raw_response", read["candidate_sha256"]))
            batch_hash = batch.batch_sha256 if batch else None
            if (artifact.get("input_sha256") != frozen.frozen_input_sha256
                    or artifact.get("batch_sha256") != batch_hash
                    or artifact.get("accepted") is not False):
                raise StepFailure(retryable=False, error_code=f"{self.error_prefix}_CANDIDATE_SCOPE_CHANGED")
            validated = self._validate_candidate_payload(
                frozen, json.dumps(artifact["payload"], ensure_ascii=False), batch,
            )
            receipt_ids = read.get("receipt_sha256s")
            if not receipt_ids:
                raise StepFailure(retryable=False, error_code=f"{self.error_prefix}_RECEIPT_MISSING")
            # Bind the saved candidates to this lane's final successful raw response,
            # not just to another artifact carrying the same input fingerprint.
            receipt = json.loads(self.artifact_store.read_by_sha("raw_response", receipt_ids[-1]))
            if receipt.get("job_id") != job_id or receipt.get("step_id") != step_id:
                raise StepFailure(retryable=False, error_code=f"{self.error_prefix}_RECEIPT_SCOPE_CHANGED")
            request = json.loads(self.artifact_store.read_by_sha("raw_response", receipt["request_sha256"]))
            response = json.loads(self.artifact_store.read_by_sha("raw_response", receipt["response_sha256"]))
            route = self.routes[lane]
            expected_messages_sha = canonical_hash(self._build_messages(frozen, batch))
            if (canonical_hash(request.get("messages")) != expected_messages_sha
                    or artifact.get("messages_sha256") != expected_messages_sha
                    or request.get("model") != route.model
                    or request.get("reasoning_effort") != route.reasoning_effort
                    or response.get("finish_reason") != "stop"):
                raise StepFailure(retryable=False, error_code=f"{self.error_prefix}_RECEIPT_SCOPE_CHANGED")
            original = self._validate_candidate_payload(frozen, response["text"], batch)
            if original != validated:
                raise StepFailure(retryable=False, error_code=f"{self.error_prefix}_CANDIDATE_RESPONSE_CHANGED")
            group = groups.setdefault(batch_hash, {})
            if lane in group:
                raise StepFailure(retryable=False, error_code=f"{self.error_prefix}_READ_DUPLICATED")
            group[lane] = (validated, read)
        comparisons = []
        for batch_hash, group in groups.items():
            if set(group) != set(LANES):
                raise StepFailure(retryable=False, error_code=f"{self.error_prefix}_READ_INCOMPLETE")
            comparisons.append({
                "batch_sha256": batch_hash,
                "sources": {lane.value: group[lane][1] for lane in LANES},
                "results": compare_candidate_declarations(
                    group[LANES[0]][0], group[LANES[1]][0],
                    identity_field=self.candidate_identity_field,
                ),
            })
        return {
            "version": COMPARISON_VERSION, "accepted": False,
            "frozen_input_sha256": frozen.frozen_input_sha256, "batches": comparisons,
        }

    def _candidate_artifact(self, frozen, result):
        predicates = {
            predicate.predicate_identity_sha256: predicate.predicate
            for component in frozen.components
            for predicate in component.binding_predicates
        }
        facts = {fact.fact_id: fact for fact in frozen.facts}
        return {
            "input_sha256": result.input_sha256, "messages_sha256": result.messages_sha256,
            "payload": result.payload.model_dump(mode="json"),
            "source_excerpts": result.source_excerpts, "accepted": False,
            "batch_sha256": result.batch_sha256,
            "operand_checks": [
                {"predicate_identity_sha256": item.predicate_identity_sha256,
                 "fact_id": candidate.fact_id, "fact_attribute": candidate.fact_attribute,
                 "locator_id": candidate.locator_id,
                 **candidate_value_shape(
                     predicates[item.predicate_identity_sha256],
                     facts[candidate.fact_id],
                     candidate.fact_attribute)}
                for item in result.payload.results for candidate in item.candidates
            ],
        }

    def __call__(self, context):
        payload = context.job_payload
        if (context.job_type != self.job_type or payload.get("contract") != self.contract
                or payload.get("prompt_version") != self.prompt_version
                or payload.get("batch_prompt_version") != self.batch_prompt_version
                or payload.get("purpose") != "isolated_unverified_candidates"):
            raise StepFailure(retryable=False, error_code=f"{self.error_prefix}_VERSION_CHANGED")
        if payload["routes"] != {lane.value: route_identity(route) for lane, route in self.routes.items()}:
            raise StepFailure(retryable=False, error_code=f"{self.error_prefix}_ROUTE_CHANGED")
        frozen = self.frozen_input_type.model_validate(payload["frozen_input"])
        self._validate_batches(payload, frozen)
        with self.session_factory() as session:
            self._verify_current(session, frozen)
            from app.services.review_candidate_scope import verify_candidate_preparation
            verify_candidate_preparation(session, payload, frozen)

        def apply(session):
            self._verify_current(session, frozen)
            verify_candidate_preparation(session, payload, frozen)

        if context.step_id == "summary":
            with self.session_factory() as session:
                store = JobStore(session)
                reads = {}
                for step_id, lane, batch in _reads(payload):
                    checkpoint = store.get_last_checkpoint(context.job_id, step_id)
                    if checkpoint is None:
                        raise StepFailure(retryable=False, error_code=f"{self.error_prefix}_RECEIPT_MISSING")
                    if (checkpoint[1].get("frozen_input_sha256") != frozen.frozen_input_sha256
                            or checkpoint[1].get("batch_sha256") != (batch.batch_sha256 if batch else None)
                            or checkpoint[1].get("lane") != lane.value):
                        raise StepFailure(retryable=False, error_code=f"{self.error_prefix}_RECEIPT_SCOPE_CHANGED")
                    reads[step_id] = checkpoint[1]
            if any(read["status"] != "unverified" for read in reads.values()):
                raise StepFailure(retryable=False, error_code=f"{self.error_prefix}_READ_INCOMPLETE",
                                  detail="部分资料对应尚未核实，原回答已保留，不能采用本次结果")
            return PreparedStepResult(checkpoint={
                "status": "unverified",
                "accepted": False, "frozen_input_sha256": frozen.frozen_input_sha256,
                "reads": reads,
                "comparison_sha256": self._put(self._comparison_artifact(
                    frozen, payload, reads, job_id=context.job_id,
                )),
            }, apply=apply)

        selected = next((item for item in _reads(payload) if item[0] == context.step_id), None)
        if selected is None:
            raise StepFailure(retryable=False, error_code=f"{self.error_prefix}_STEP_UNKNOWN")
        _, lane, batch = selected
        attempts = []

        async def recorded(route, messages, budget):
            request = {"model": route.model, "reasoning_effort": route.reasoning_effort,
                       "messages": messages, "max_tokens": budget,
                       **page_completion_options(route.provider, messages, budget)}
            receipt = {"job_id": context.job_id, "step_id": context.step_id,
                       "attempt": context.attempt, "route_identity": route_identity(route),
                       "request_sha256": self._put(request)}
            start = monotonic()
            try:
                result = await self.completion(route, messages, budget)
                receipt["response_sha256"] = self._put(dataclasses.asdict(result))
                return result
            except (Exception, asyncio.CancelledError) as exc:
                receipt.update(error_type=type(exc).__name__, status_code=getattr(exc, "status_code", None))
                raise
            finally:
                receipt["elapsed_seconds"] = monotonic() - start
                attempts.append(self._put(receipt))

        try:
            result = asyncio.run(run_cancellable(
                lambda: self._read(frozen, self.routes[lane], recorded, batch),
                self.session_factory, context.job_id,
            ))
            candidate_sha = self._put(self._candidate_artifact(frozen, result))
            checkpoint = {"status": "unverified", "candidate_sha256": candidate_sha}
        except PredicateCandidateReadError as exc:
            checkpoint = {"status": "incomplete", "failure": str(exc)}
        except StepFailure as exc:
            if exc.error_code != "PAGE_REVIEW_CANCEL_REQUESTED":
                raise
            checkpoint = {"status": "incomplete", "failure": "读取已取消，保留已发生的调用记录"}
        return PreparedStepResult(checkpoint={
            **checkpoint, "accepted": False, "receipt_sha256s": attempts,
            "lane": lane.value, "frozen_input_sha256": frozen.frozen_input_sha256,
            "batch_sha256": batch.batch_sha256 if batch else None,
        }, apply=apply)
