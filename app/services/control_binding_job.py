"""Persist unverified control correspondence using the existing job lifecycle.

This executor is intentionally not registered in the normal application. It is
an explicit candidate entry point, not permission to publish clinical bindings.
"""
from app.domain.contracts.control_atom_binding import ControlBindingFrozenInput
from app.domain.publication import canonical_hash
from app.llm.control_binding_candidates import (
    PROMPT_VERSION, build_control_binding_messages, read_control_candidates, validate_control_candidates,
)
from app.llm.page_reader_capabilities import LOCAL_PAGE_PROVIDERS
from app.projections.control_atom_binding_input import project_control_atom_identities
from app.projections.control_operand_calculation import calculate_control_operands
from app.services.control_binding_input import build_control_binding_frozen_input
from app.services.job_service import JobService, StepSpec
from app.services.page_review_job_service import route_identity
from app.services.predicate_binding_job import LANES, PredicateBindingJobExecutor
from app.workflow.errors import InvalidJobDefinitionError, StepFailure

JOB_TYPE = "control_binding_candidates"
CONTRACT = "control-binding-candidate-job/v6"


def enqueue_control_candidates(session_factory, *, review_episode_id, routes, review_context_id=None,
                               product_runtime=False, workflow_job_id=None):
    """Freeze the full published catalog; callers must preflight both routes."""
    if set(routes) != set(LANES) or any(route.lane != lane for lane, route in routes.items()):
        raise InvalidJobDefinitionError("需要两个完整且对应一致的独立读取配置")
    if any(not 65536 <= route.max_tokens <= 131072 for route in routes.values()):
        raise InvalidJobDefinitionError("对应任务输出额度不足或超出约定范围")
    with session_factory() as session, session.begin():
        frozen = build_control_binding_frozen_input(session, review_episode_id)
        if not frozen.publication.catalog.controls:
            raise InvalidJobDefinitionError("当前方案没有补充控制，无需创建对应任务")
        reads = [StepSpec(step_id=f"read:{lane.value}", name="核对资料与方案补充要求的对应")
                 for lane in LANES]
        payload = {
            "contract": CONTRACT, "prompt_version": PROMPT_VERSION,
            "purpose": "isolated_unverified_candidates",
            "frozen_input": frozen.model_dump(mode="json"),
            "routes": {lane.value: route_identity(routes[lane]) for lane in LANES},
            "batch_max_characters": None, "batch_prompt_version": None, "batches": None,
            "execution_control": {
                "max_parallel_steps": (
                    1 if all(route.provider in LOCAL_PAGE_PROVIDERS for route in routes.values()) else 2
                ),
                "parallelizable_step_ids": [step.step_id for step in reads],
            },
        }
        if review_context_id is not None:
            from app.services.review_candidate_scope import require_prepared_candidate_scope
            payload["review_context_sha256"] = require_prepared_candidate_scope(
                session, review_context_id, frozen.evidence_input, control_input=frozen,
            )
            payload["review_context_id"] = review_context_id
        from app.services.review_runtime_ownership import mark_prepared_review_job
        mark_prepared_review_job(payload, enabled=product_runtime, session=session,
                                 workflow_job_id=workflow_job_id)
        return JobService(session_factory).create_job_in_session(
            session, idempotency_key=f"{JOB_TYPE}:{canonical_hash(payload)}",
            job_type=JOB_TYPE, payload=payload,
            steps=[*reads, StepSpec(
                step_id="summary", name="保存尚未核实的对应结果",
                depends_on=tuple(step.step_id for step in reads),
            )],
        )


class ControlBindingJobExecutor(PredicateBindingJobExecutor):
    """Share cancellation, raw receipts, checkpoints and commit-time rechecks."""

    job_type = JOB_TYPE
    contract = CONTRACT
    prompt_version = PROMPT_VERSION
    batch_prompt_version = None
    frozen_input_type = ControlBindingFrozenInput
    error_prefix = "CONTROL_BINDING"
    candidate_identity_field = "atom_identity_sha256"

    def _validate_candidate_payload(self, frozen, raw_text, batch):
        return validate_control_candidates(frozen, raw_text)

    def _build_messages(self, frozen, batch):
        return build_control_binding_messages(frozen)

    def _verify_current(self, session, frozen):
        current = build_control_binding_frozen_input(
            session, frozen.evidence_input.authority.review_episode_id,
        )
        if current.frozen_input_sha256 != frozen.frozen_input_sha256:
            raise StepFailure(
                retryable=False, error_code="CONTROL_BINDING_INPUT_CHANGED",
                detail="资料或方案补充要求已变化，请保留旧结果并重新核对",
            )

    def _validate_batches(self, payload, frozen):
        if payload.get("batches") is not None or payload.get("batch_max_characters") is not None:
            raise StepFailure(retryable=False, error_code="CONTROL_BINDING_BATCH_UNSUPPORTED")

    async def _read(self, frozen, route, recorded, batch):
        return await read_control_candidates(frozen, route, completion=recorded)

    def _candidate_artifact(self, frozen, result):
        locators = {item.locator_id: item for item in frozen.evidence_input.locators}
        used = {candidate.locator_id for item in result.payload.results for candidate in item.candidates}
        atoms = {item.identity_sha256: item.atom
                 for item in project_control_atom_identities(frozen.publication, include_repeat_triggers=True)}
        selected_checks, checks = [], []
        for item in result.payload.results:
            spec = atoms[item.atom_identity_sha256].evaluation
            for candidate in item.candidates:
                matches = bool(spec is not None and spec.operand_attribute == candidate.fact_attribute)
                check = {
                    "atom_identity_sha256": item.atom_identity_sha256,
                    "fact_id": candidate.fact_id, "fact_attribute": candidate.fact_attribute,
                    "locator_id": candidate.locator_id,
                    "declared_operand_matches": matches,
                    "accepted": False, "calculation": None,
                }
                # Conditional arithmetic is not approval of the model's correspondence.
                if (matches and spec.determination_mode == "deterministic"
                        and candidate.object_correspondence == "supported"
                        and (candidate.attribute_correspondence == "direct" or (
                            spec.operation == "time_constraint"
                            and candidate.attribute_correspondence == "derivation_operand"
                        ))):
                    key = (item.atom_identity_sha256, candidate.fact_id)
                    selected_checks.append((key, check))
                checks.append(check)
        if selected_checks:
            calculations = calculate_control_operands(
                frozen, selections=(key for key, _ in selected_checks),
            )
            serialized = {key: value.model_dump(mode="json") for key, value in calculations.items()}
            for key, check in selected_checks:
                check["calculation"] = serialized[key]
        return {
            "input_sha256": result.input_sha256,
            "messages_sha256": result.messages_sha256,
            "payload": result.payload.model_dump(mode="json"),
            "source_locators": [locators[key].model_dump(mode="json") for key in sorted(used)],
            "operand_checks": checks,
            "accepted": False, "batch_sha256": None,
        }
