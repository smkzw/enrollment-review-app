"""Follow-on qualification JobRunner for completed candidate binding jobs.

Consumes receipt-proven predicate/control candidate comparisons, runs an independent
dual-lane source-qualification stage with bounded pair batches, and persists
structurally validated but clinically unauthorized records. Not registered.
"""
from __future__ import annotations

import asyncio
import dataclasses
import json
from time import monotonic

from app.domain.contracts.binding_qualification import (
    BindingQualificationBatch,
    BindingQualificationLanePayload,
    BindingQualificationPairContext,
)
from app.domain.contracts.control_atom_binding import ControlBindingFrozenInput
from app.domain.contracts.predicate_binding import PredicateBindingFrozenInput
from app.domain.publication import canonical_hash
from app.llm.binding_qualification import (
    DEFAULT_PAIR_BATCH_MAX_CHARACTERS,
    PROMPT_VERSION,
    build_binding_qualification_messages,
    plan_qualification_batches,
    read_binding_qualification,
    validate_binding_qualification_payload,
)
from app.llm.page_reader_capabilities import LOCAL_PAGE_PROVIDERS
from app.llm.page_review_harness import direct_completion
from app.llm.page_review_transport_options import page_completion_options
from app.llm.predicate_binding_candidates import PredicateCandidateReadError
from app.services.binding_qualification_support import (
    _reconstruct_qualification_lane_state,
    CONTRACT,
    JOB_TYPE,
    compose_qualification_summary,
    load_completed_candidate_qualification_input,
)
from app.services.control_binding_input import build_control_binding_frozen_input
from app.services.job_service import JobService, StepSpec
from app.services.page_review_cancellation import run_cancellable
from app.services.page_review_job_service import route_identity
from app.services.predicate_binding_input import build_predicate_binding_frozen_input
from app.services.predicate_binding_job import LANES
from app.workflow.errors import InvalidJobDefinitionError, StepFailure
from app.workflow.jobstore import JobStore
from app.workflow.runner import PreparedStepResult

def enqueue_binding_qualification(
    session_factory, *, candidate_job_id, routes, artifact_store,
    pair_batch_max_characters: int = DEFAULT_PAIR_BATCH_MAX_CHARACTERS,
    product_runtime=False,
):
    if set(routes) != set(LANES) or any(route.lane != lane for lane, route in routes.items()):
        raise InvalidJobDefinitionError("需要两个完整且对应一致的独立读取配置")
    if any(not 65536 <= route.max_tokens <= 131072 for route in routes.values()):
        raise InvalidJobDefinitionError("资格核对输出额度不足或超出约定范围")
    with session_factory() as session, session.begin():
        material = load_completed_candidate_qualification_input(
            session, artifact_store, candidate_job_id,
        )
        pairs = [
            BindingQualificationPairContext.model_validate(item)
            for item in material["pairs"]
        ]
        batches = [
            batch.model_dump(mode="json")
            for batch in plan_qualification_batches(
                pairs, max_characters=pair_batch_max_characters,
            )
        ]
        payload = {
            "contract": CONTRACT,
            "prompt_version": PROMPT_VERSION,
            "purpose": "isolated_source_qualification",
            "candidate_job_id": candidate_job_id,
            "candidate_job_type": material["candidate_job_type"],
            "candidate_contract": material["candidate_contract"],
            "candidate_family": material["family"],
            "identity_field": material["identity_field"],
            "frozen_input": material["frozen_input"],
            "frozen_input_sha256": material["frozen_input_sha256"],
            "comparison_sha256": material["comparison_sha256"],
            "candidate_receipt_sha256s": material["candidate_receipt_sha256s"],
            "pairs": material["pairs"],
            "identity_records": material["identity_records"],
            "pair_batch_max_characters": pair_batch_max_characters,
            "batches": batches,
            "routes": {lane.value: route_identity(routes[lane]) for lane in LANES},
        }
        for key in ("review_context_id", "review_context_sha256"):
            if key in material:
                payload[key] = material[key]
        from app.services.review_runtime_ownership import mark_prepared_review_job
        mark_prepared_review_job(payload, enabled=product_runtime, session=session,
                                 parent_job_id=candidate_job_id)
        if not pairs:
            steps = [StepSpec(step_id="summary", name="保存无候选配对的资格结果")]
            return JobService(session_factory).create_job_in_session(
                session,
                idempotency_key=f"{JOB_TYPE}:{canonical_hash(payload)}",
                job_type=JOB_TYPE,
                payload=payload,
                steps=steps,
            )
        steps = []
        previous = {}
        for index, _batch in enumerate(batches):
            for lane in LANES:
                step_id = f"qualify:{index}:{lane.value}"
                steps.append(StepSpec(
                    step_id=step_id,
                    name="复核候选对应的来源资格与操作数可用性",
                    depends_on=(previous[lane],) if lane in previous else (),
                ))
                previous[lane] = step_id
        local_count = sum(route.provider in LOCAL_PAGE_PROVIDERS for route in routes.values())
        payload["execution_control"] = {
            "max_parallel_steps": 1 if local_count == 2 else 2,
            "parallelizable_step_ids": [step.step_id for step in steps],
        }
        steps.append(StepSpec(
            step_id="summary",
            name="保存结构核对与双路资格结果",
            depends_on=tuple(step.step_id for step in steps),
        ))
        return JobService(session_factory).create_job_in_session(
            session,
            idempotency_key=f"{JOB_TYPE}:{canonical_hash(payload)}",
            job_type=JOB_TYPE,
            payload=payload,
            steps=steps,
        )



class BindingQualificationJobExecutor:
    job_type = JOB_TYPE
    contract = CONTRACT
    prompt_version = PROMPT_VERSION

    def __init__(self, session_factory, artifact_store, routes, *, completion=direct_completion):
        self.session_factory = session_factory
        self.artifact_store = artifact_store
        self.routes = routes
        self.completion = completion

    def _put(self, value):
        return self.artifact_store.put(
            "raw_response",
            json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8"),
        ).sha256

    def _frozen(self, payload):
        if payload["candidate_family"] == "predicate":
            return PredicateBindingFrozenInput.model_validate(payload["frozen_input"])
        return ControlBindingFrozenInput.model_validate(payload["frozen_input"])

    def _pairs(self, payload) -> list[BindingQualificationPairContext]:
        return [
            BindingQualificationPairContext.model_validate(item)
            for item in payload.get("pairs") or []
        ]

    def _batches(self, payload, pairs) -> list[BindingQualificationBatch]:
        expected = [
            batch.model_dump(mode="json")
            for batch in plan_qualification_batches(
                pairs,
                max_characters=payload.get(
                    "pair_batch_max_characters", DEFAULT_PAIR_BATCH_MAX_CHARACTERS,
                ),
            )
        ]
        if payload.get("batches") != expected:
            raise StepFailure(
                retryable=False, error_code="BINDING_QUALIFICATION_BATCH_SCOPE_CHANGED",
            )
        return [BindingQualificationBatch.model_validate(item) for item in expected]

    def _verify_current(self, session, payload):
        rebuilt = load_completed_candidate_qualification_input(
            session, self.artifact_store, payload["candidate_job_id"],
        )
        if payload["candidate_family"] == "predicate":
            frozen = PredicateBindingFrozenInput.model_validate(payload["frozen_input"])
            current = build_predicate_binding_frozen_input(
                session,
                frozen.authority.review_episode_id,
                component_ids=[item.rule_component_id for item in frozen.components],
            ).frozen_input_sha256
        else:
            frozen = ControlBindingFrozenInput.model_validate(payload["frozen_input"])
            current = build_control_binding_frozen_input(
                session, frozen.evidence_input.authority.review_episode_id,
            ).frozen_input_sha256
        if current != payload["frozen_input_sha256"]:
            raise StepFailure(
                retryable=False,
                error_code="BINDING_QUALIFICATION_INPUT_CHANGED",
                detail="资料或审核要求已变化，请保留旧候选结果并重新资格核对",
            )
        expected = {
            "candidate_job_type": payload["candidate_job_type"],
            "candidate_contract": payload["candidate_contract"],
            "family": payload["candidate_family"],
            "identity_field": payload["identity_field"],
            "frozen_input_sha256": payload["frozen_input_sha256"],
            "comparison_sha256": payload["comparison_sha256"],
            "pairs": payload["pairs"],
            "identity_records": payload["identity_records"],
            "candidate_receipt_sha256s": payload["candidate_receipt_sha256s"],
        }
        actual = {key: rebuilt[key] for key in expected}
        for key in ("review_context_id", "review_context_sha256"):
            if key in rebuilt or key in payload:
                expected[key] = payload.get(key)
                actual[key] = rebuilt.get(key)
        if actual != expected:
            raise StepFailure(
                retryable=False,
                error_code="BINDING_QUALIFICATION_MATERIAL_CHANGED",
                detail="资格配对或政策材料与来源候选任务重建结果不一致",
            )

    def __call__(self, context):
        payload = context.job_payload
        if (
            context.job_type != self.job_type
            or payload.get("contract") != self.contract
            or payload.get("prompt_version") != self.prompt_version
            or payload.get("purpose") != "isolated_source_qualification"
        ):
            raise StepFailure(
                retryable=False, error_code="BINDING_QUALIFICATION_VERSION_CHANGED",
            )
        if payload["routes"] != {
            lane.value: route_identity(route) for lane, route in self.routes.items()
        }:
            raise StepFailure(
                retryable=False, error_code="BINDING_QUALIFICATION_ROUTE_CHANGED",
            )
        frozen = self._frozen(payload)
        pairs = self._pairs(payload)
        batches = self._batches(payload, pairs)
        with self.session_factory() as session:
            self._verify_current(session, payload)

        def apply(session):
            self._verify_current(session, payload)

        if context.step_id == "summary":
            with self.session_factory() as session:
                try:
                    lane_payloads, lane_receipts = _reconstruct_qualification_lane_state(
                        session=session, artifact_store=self.artifact_store,
                        job_id=context.job_id, payload=payload, pairs=pairs, batches=batches,
                        routes=payload["routes"],
                    )
                except InvalidJobDefinitionError as exc:
                    raise StepFailure(retryable=False,
                                      error_code="BINDING_QUALIFICATION_RECEIPT_INVALID") from exc
            summary = compose_qualification_summary(
                payload=payload,
                frozen=frozen,
                pairs=pairs,
                batches=batches,
                lane_payloads=lane_payloads,
                lane_receipts=lane_receipts,
            )
            return PreparedStepResult(checkpoint={
                "status": "unverified",
                "accepted": False,
                "authorized_clinical_adoption": False,
                "clinically_qualified": False,
                "frozen_input_sha256": payload["frozen_input_sha256"],
                "comparison_sha256": payload["comparison_sha256"],
                "candidate_job_id": payload["candidate_job_id"],
                "summary_sha256": self._put(summary.model_dump(mode="json")),
            }, apply=apply)

        if not context.step_id.startswith("qualify:"):
            raise StepFailure(
                retryable=False, error_code="BINDING_QUALIFICATION_STEP_UNKNOWN",
            )
        _, index_text, lane_name = context.step_id.split(":", 2)
        index = int(index_text)
        lane = next((item for item in LANES if item.value == lane_name), None)
        if lane is None or index < 0 or index >= len(batches):
            raise StepFailure(
                retryable=False, error_code="BINDING_QUALIFICATION_STEP_UNKNOWN",
            )
        batch = batches[index]
        batch_pairs = [item for item in pairs if item.pair_id in set(batch.pair_ids)]
        attempts = []

        async def recorded(route, messages, budget):
            request = {
                "model": route.model,
                "reasoning_effort": route.reasoning_effort,
                "messages": messages,
                "max_tokens": budget,
                **page_completion_options(route.provider, messages, budget),
            }
            receipt = {
                "job_id": context.job_id,
                "step_id": context.step_id,
                "attempt": context.attempt,
                "route_identity": route_identity(route),
                "request_sha256": self._put(request),
            }
            start = monotonic()
            try:
                result = await self.completion(route, messages, budget)
                receipt["response_sha256"] = self._put(dataclasses.asdict(result))
                return result
            except (Exception, asyncio.CancelledError) as exc:
                receipt.update(
                    error_type=type(exc).__name__,
                    status_code=getattr(exc, "status_code", None),
                )
                raise
            finally:
                receipt["elapsed_seconds"] = monotonic() - start
                attempts.append(self._put(receipt))

        try:
            result = asyncio.run(run_cancellable(
                lambda: read_binding_qualification(
                    batch_pairs, batch, self.routes[lane], completion=recorded,
                ),
                self.session_factory,
                context.job_id,
            ))
            artifact = {
                "input_sha256": result.frozen_input_sha256,
                "batch_sha256": result.batch_sha256,
                "messages_sha256": result.messages_sha256,
                "payload": result.payload.model_dump(mode="json"),
                "accepted": False,
                "authorized_clinical_adoption": False,
                "clinically_qualified": False,
                "candidate_job_id": payload["candidate_job_id"],
                "comparison_sha256": payload["comparison_sha256"],
            }
            checkpoint = {
                "status": "unverified",
                "qualification_sha256": self._put(artifact),
            }
        except PredicateCandidateReadError as exc:
            checkpoint = {"status": "incomplete", "failure": str(exc)}
        except StepFailure as exc:
            if exc.error_code != "PAGE_REVIEW_CANCEL_REQUESTED":
                raise
            checkpoint = {
                "status": "incomplete",
                "failure": "资格核对已取消，保留已发生的调用记录",
            }
        return PreparedStepResult(checkpoint={
            **checkpoint,
            "accepted": False,
            "authorized_clinical_adoption": False,
            "clinically_qualified": False,
            "receipt_sha256s": attempts,
            "lane": lane.value,
            "batch_sha256": batch.batch_sha256,
            "frozen_input_sha256": payload["frozen_input_sha256"],
            "comparison_sha256": payload["comparison_sha256"],
            "candidate_job_id": payload["candidate_job_id"],
        }, apply=apply)
