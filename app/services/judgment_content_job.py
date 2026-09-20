"""Follow-on written-judgment content JobRunner for prepared review contexts.

Consumes receipt-proven candidate material plus prepared judgment
linkage, runs an independent dual-lane content check, and persists structurally
validated but clinically unauthorized records. Uses the shared product runtime.
"""
from __future__ import annotations

import asyncio
import dataclasses
import json
from time import monotonic

from app.domain.contracts.binding_qualification import (
    BindingQualificationBatch,
    BindingQualificationPairContext,
)
from app.domain.publication import canonical_hash
from app.llm.binding_qualification import DEFAULT_PAIR_BATCH_MAX_CHARACTERS
from app.llm.judgment_content import read_judgment_content
from app.llm.page_reader_capabilities import LOCAL_PAGE_PROVIDERS
from app.llm.page_review_harness import direct_completion
from app.llm.page_review_transport_options import page_completion_options
from app.llm.predicate_binding_candidates import PredicateCandidateReadError
from app.services.judgment_content_input import load_judgment_content_input
from app.services.judgment_content_receipts import (
    CONTRACT,
    JOB_TYPE,
    PROMPT_VERSION,
    PURPOSE,
    _reconstruct_judgment_content_lane_state,
    compose_judgment_content_summary,
    plan_judgment_content_batches,
    rebuild_judgment_content_input,
    verify_completed_judgment_content,
)
from app.services.job_service import JobService, StepSpec
from app.services.page_review_cancellation import run_cancellable
from app.services.page_review_job_service import route_identity
from app.services.predicate_binding_job import LANES
from app.workflow.errors import InvalidJobDefinitionError, StepFailure
from app.workflow.runner import PreparedStepResult


def enqueue_judgment_content(
    session_factory,
    *,
    candidate_job_id: str,
    context_id: str,
    routes,
    artifact_store,
    pair_batch_max_characters: int = DEFAULT_PAIR_BATCH_MAX_CHARACTERS,
    product_runtime=False,
):
    return _enqueue_content_job(
        session_factory, candidate_job_id=candidate_job_id, context_id=context_id,
        routes=routes, artifact_store=artifact_store,
        pair_batch_max_characters=pair_batch_max_characters, product_runtime=product_runtime,
        definition=JudgmentContentJobExecutor,
    )


def _enqueue_content_job(
    session_factory, *, candidate_job_id, context_id, routes, artifact_store,
    pair_batch_max_characters, product_runtime, definition,
):
    if set(routes) != set(LANES) or any(route.lane != lane for lane, route in routes.items()):
        raise InvalidJobDefinitionError("需要两个完整且对应一致的独立读取配置")
    if any(not 65536 <= route.max_tokens <= 131072 for route in routes.values()):
        raise InvalidJobDefinitionError("判断内容核实输出额度不足或超出约定范围")
    if len({(route.provider, route.model) for route in routes.values()}) != 2:
        raise InvalidJobDefinitionError("判断内容核实需要两个不同的独立模型")
    with session_factory() as session, session.begin():
        material = definition.load_input(
            session,
            artifact_store,
            candidate_job_id=candidate_job_id,
            context_id=context_id,
        )
        pairs = [
            definition.pair_model.model_validate(item)
            for item in material["pairs"]
        ]
        batches = [
            batch.model_dump(mode="json")
            for batch in definition.plan_batches(
                pairs, max_characters=pair_batch_max_characters,
            )
        ]
        payload = {
            "contract": definition.contract,
            "prompt_version": definition.prompt_version,
            "purpose": definition.purpose,
            "input_version": material["version"],
            "candidate_job_id": candidate_job_id,
            "review_context_id": context_id,
            "review_context_sha256": material["review_context_sha256"],
            "frozen_input_sha256": material["frozen_input_sha256"],
            "comparison_sha256": material["comparison_sha256"],
            "candidate_receipt_sha256s": material["candidate_receipt_sha256s"],
            "pairs": material["pairs"],
            **{key: material[key] for key in definition.coverage_fields},
            "input_sha256": material["input_sha256"],
            "pair_batch_max_characters": pair_batch_max_characters,
            "batches": batches,
            "routes": {lane.value: route_identity(routes[lane]) for lane in LANES},
        }
        from app.services.review_runtime_ownership import mark_prepared_review_job
        mark_prepared_review_job(payload, enabled=product_runtime, session=session,
                                 parent_job_id=candidate_job_id)
        if not pairs:
            steps = [StepSpec(step_id="summary", name=definition.empty_name)]
            return JobService(session_factory).create_job_in_session(
                session,
                idempotency_key=f"{definition.job_type}:{canonical_hash(payload)}",
                job_type=definition.job_type,
                payload=payload,
                steps=steps,
            )
        steps = []
        previous = {}
        for index, _batch in enumerate(batches):
            for lane in LANES:
                step_id = f"content:{index}:{lane.value}"
                steps.append(StepSpec(
                    step_id=step_id,
                    name=definition.step_name,
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
            name=definition.summary_name,
            depends_on=tuple(step.step_id for step in steps),
        ))
        return JobService(session_factory).create_job_in_session(
            session,
            idempotency_key=f"{definition.job_type}:{canonical_hash(payload)}",
            job_type=definition.job_type,
            payload=payload,
            steps=steps,
        )


class JudgmentContentJobExecutor:
    pair_model = BindingQualificationPairContext
    job_type = JOB_TYPE
    contract = CONTRACT
    prompt_version = PROMPT_VERSION
    purpose = PURPOSE
    coverage_fields = ("excerpt_coverage",)
    step_name = "核实已有书面判断内容与事实值一致性"
    empty_name = "保存无选定配对的判断内容覆盖结果"
    summary_name = "保存结构比较与双路判断内容结果"
    error_prefix = "JUDGMENT_CONTENT"
    load_input = staticmethod(load_judgment_content_input)
    plan_batches = staticmethod(plan_judgment_content_batches)
    rebuild_input = staticmethod(rebuild_judgment_content_input)
    reconstruct = staticmethod(_reconstruct_judgment_content_lane_state)
    compose_summary = staticmethod(compose_judgment_content_summary)
    read_content = staticmethod(read_judgment_content)

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

    def _pairs(self, payload):
        return [
            self.pair_model.model_validate(item)
            for item in payload.get("pairs") or []
        ]

    def _batches(self, payload, pairs) -> list[BindingQualificationBatch]:
        expected = [
            batch.model_dump(mode="json")
            for batch in self.plan_batches(
                pairs,
                max_characters=payload.get(
                    "pair_batch_max_characters", DEFAULT_PAIR_BATCH_MAX_CHARACTERS,
                ),
            )
        ]
        if payload.get("batches") != expected:
            raise StepFailure(
                retryable=False, error_code=f"{self.error_prefix}_BATCH_SCOPE_CHANGED",
            )
        return [BindingQualificationBatch.model_validate(item) for item in expected]

    def _verify_current(self, session, payload):
        try:
            self.rebuild_input(session, self.artifact_store, payload)
        except InvalidJobDefinitionError as exc:
            raise StepFailure(
                retryable=False,
                error_code=f"{self.error_prefix}_INPUT_CHANGED",
                detail=str(exc) or "判断内容输入与当前候选回执或审核准备不一致",
            ) from exc
        except ValueError as exc:
            raise StepFailure(
                retryable=False,
                error_code=f"{self.error_prefix}_INPUT_CHANGED",
                detail=str(exc),
            ) from exc

    def __call__(self, context):
        payload = context.job_payload
        if (
            context.job_type != self.job_type
            or payload.get("contract") != self.contract
            or payload.get("prompt_version") != self.prompt_version
            or payload.get("purpose") != self.purpose
        ):
            raise StepFailure(
                retryable=False, error_code=f"{self.error_prefix}_VERSION_CHANGED",
            )
        if payload["routes"] != {
            lane.value: route_identity(route) for lane, route in self.routes.items()
        }:
            raise StepFailure(
                retryable=False, error_code=f"{self.error_prefix}_ROUTE_CHANGED",
            )
        pairs = self._pairs(payload)
        batches = self._batches(payload, pairs)
        with self.session_factory() as session:
            self._verify_current(session, payload)

        def apply(session):
            self._verify_current(session, payload)

        if context.step_id == "summary":
            with self.session_factory() as session:
                try:
                    lane_reads, lane_receipts = self.reconstruct(
                        session=session,
                        artifact_store=self.artifact_store,
                        job_id=context.job_id,
                        payload=payload,
                        pairs=pairs,
                        batches=batches,
                        routes=payload["routes"],
                    )
                except InvalidJobDefinitionError as exc:
                    raise StepFailure(
                        retryable=False,
                        error_code=f"{self.error_prefix}_RECEIPT_INVALID",
                    ) from exc
            summary = self.compose_summary(
                payload=payload,
                pairs=pairs,
                batches=batches,
                lane_reads=lane_reads,
                lane_receipts=lane_receipts,
            )
            return PreparedStepResult(checkpoint={
                "status": "unverified",
                "accepted": False,
                "authorized_clinical_adoption": False,
                "clinically_qualified": False,
                "frozen_input_sha256": payload["frozen_input_sha256"],
                "input_sha256": payload["input_sha256"],
                "comparison_sha256": payload["comparison_sha256"],
                "candidate_job_id": payload["candidate_job_id"],
                "review_context_id": payload["review_context_id"],
                "summary_sha256": self._put(summary),
            }, apply=apply)

        if not context.step_id.startswith("content:"):
            raise StepFailure(
                retryable=False, error_code=f"{self.error_prefix}_STEP_UNKNOWN",
            )
        _, index_text, lane_name = context.step_id.split(":", 2)
        index = int(index_text)
        lane = next((item for item in LANES if item.value == lane_name), None)
        if lane is None or index < 0 or index >= len(batches):
            raise StepFailure(
                retryable=False, error_code=f"{self.error_prefix}_STEP_UNKNOWN",
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
                lambda: self.read_content(
                    batch_pairs, batch, self.routes[lane], completion=recorded,
                ),
                self.session_factory,
                context.job_id,
            ))
            artifact = {
                "input_sha256": payload["input_sha256"],
                "frozen_input_sha256": result.frozen_input_sha256,
                "batch_sha256": result.batch_sha256,
                "messages_sha256": result.messages_sha256,
                "payload": result.payload.model_dump(mode="json"),
                "accepted": False,
                "authorized_clinical_adoption": False,
                "clinically_qualified": False,
                "candidate_job_id": payload["candidate_job_id"],
                "review_context_id": payload["review_context_id"],
                "comparison_sha256": payload["comparison_sha256"],
            }
            checkpoint = {
                "status": "unverified",
                "content_sha256": self._put(artifact),
            }
        except PredicateCandidateReadError as exc:
            checkpoint = {"status": "incomplete", "failure": str(exc)}
        except StepFailure as exc:
            if exc.error_code != "PAGE_REVIEW_CANCEL_REQUESTED":
                raise
            checkpoint = {
                "status": "incomplete",
                "failure": "判断内容核实已取消，保留已发生的调用记录",
            }
        return PreparedStepResult(checkpoint={
            **checkpoint,
            "accepted": False,
            "authorized_clinical_adoption": False,
            "clinically_qualified": False,
            "receipt_sha256s": attempts,
            "attempt": context.attempt,
            "lane": lane.value,
            "batch_sha256": batch.batch_sha256,
            "frozen_input_sha256": payload["frozen_input_sha256"],
            "input_sha256": payload["input_sha256"],
            "comparison_sha256": payload["comparison_sha256"],
            "candidate_job_id": payload["candidate_job_id"],
            "review_context_id": payload["review_context_id"],
        }, apply=apply)
