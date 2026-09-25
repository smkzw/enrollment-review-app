"""Deterministic end-to-end checks for protocol-control execution."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.agents.protocol_control_deconstructor import (
    CONTROL_AGENT_WIRE_VERSION,
    CONTROL_DISCOVERY_WIRE_VERSION,
    ProtocolControlAgentResponse,
    ProtocolControlAgentWireValidationError,
    ProtocolControlDiscoveryAgentResponse,
)
from app.domain.contracts.enums import ReviewStage
from app.domain.contracts.protocol_controls import (
    ControlObligationKind,
    ProtocolControlDiscoveryDisposition,
    ReviewNodeRole,
    StructureUnitDispositionKind,
)
from app.domain.contracts.rules import WorkflowStage
from app.protocols.deconstruction_service import ProtocolDeconstructionInputAssembler
from app.protocols.docx_structure import StructureExtraction, serialize_blocks
from app.protocols.protocol_control_gate import ProtocolControlGateError
from app.services import protocol_control_execution as protocol_control_execution_module
from app.services.job_service import JobService, StepSpec
from app.services.protocol_control_execution import (
    CANDIDATE_CONTROL_PACKAGE_RESULT_KIND,
    FORMAL_CATALOG_STATUS_NOT_MATERIALIZED,
    PROTOCOL_CONTROL_EXECUTION_JOB_TYPE,
    ProtocolControlExecutorConfig,
    ProtocolControlJobService,
    create_protocol_control_executor,
)
from app.services.protocol_workbench_service import PROTOCOL_DECONSTRUCTION_JOB_TYPE
from app.storage.codecs import verify_payload_sha256
from app.workflow.errors import ProcessDeath, StepFailure
from app.workflow.jobstore import JobStore
from app.workflow.recovery import recover_expired_jobs
from app.workflow.runner import JobRunner, StepContext

from tests.v2.protocols.test_deconstruction_service import _synthetic_fixture


NOW = datetime(2026, 8, 14, tzinfo=timezone.utc)
_DB_NOW = datetime(2026, 8, 14)
_SOURCE_STEP_ORDER = (
    "register_file",
    "extract_structure",
    "render_and_align",
    "identify_identity_phase",
    "await_identity_confirm",
    "freeze_deconstruction_input",
)


def _now() -> datetime:
    return _DB_NOW


def test_deep_repair_reports_independent_candidates_together(monkeypatch) -> None:
    errors = (
        ProtocolControlGateError("TIME_ANCHOR_MISSING", "缺少锚点", entity_id="first"),
        ProtocolControlGateError("BASELINE_VALUE_SCOPE_MISSING", "缺少关系", entity_id="second"),
    )
    monkeypatch.setattr(
        protocol_control_execution_module,
        "check_protocol_control_batch_candidates",
        lambda _batch, _output: errors,
    )
    batch = SimpleNamespace(owned_structure_unit_ids=["u1", "u2"])
    output = SimpleNamespace(candidates=[
        SimpleNamespace(control_candidate_id="first", frozen_structure_unit_ids=["u1"]),
        SimpleNamespace(control_candidate_id="second", frozen_structure_unit_ids=["u2"]),
    ])

    with pytest.raises(ProtocolControlAgentWireValidationError) as exc:
        protocol_control_execution_module._validate_deep_batch_output(batch, output)

    assert {"TIME_ANCHOR_MISSING", "BASELINE_VALUE_SCOPE_MISSING"} <= set(
        exc.value.error_class_codes
    )
    assert set(exc.value.candidate_ids) == {"first", "second"}
    assert set(exc.value.structure_unit_ids) == {"u1", "u2"}


def test_deep_repair_resolves_candidate_repartition_before_field_repair(monkeypatch) -> None:
    errors = (
        ProtocolControlGateError("TIME_ANCHOR_MISSING", "缺少锚点", entity_id="first"),
        ProtocolControlGateError("BASELINE_VALUE_SCOPE_MIXED", "需要拆分", entity_id="second"),
    )
    monkeypatch.setattr(
        protocol_control_execution_module,
        "check_protocol_control_batch_candidates",
        lambda _batch, _output: errors,
    )
    batch = SimpleNamespace(owned_structure_unit_ids=["u1", "u2"])
    output = SimpleNamespace(candidates=[
        SimpleNamespace(control_candidate_id="first", frozen_structure_unit_ids=["u1"]),
        SimpleNamespace(control_candidate_id="second", frozen_structure_unit_ids=["u2"]),
    ])

    with pytest.raises(ProtocolControlAgentWireValidationError) as exc:
        protocol_control_execution_module._validate_deep_batch_output(batch, output)

    assert exc.value.allow_candidate_repartition is True
    assert exc.value.candidate_ids == ("second",)
    assert exc.value.structure_unit_ids == ("u2",)
    assert "TIME_ANCHOR_MISSING" not in exc.value.error_class_codes


@dataclass(frozen=True)
class _Seed:
    source_job_id: str
    snapshot_path: Path
    source_span_excerpts: dict[str, str]
    workflow_stages: tuple[WorkflowStage, ...]


def _seed_frozen_source(data_paths, session_factory, *, key: str) -> _Seed:
    fixture = _synthetic_fixture()
    blocks = fixture.extraction.blocks
    serialized = serialize_blocks(blocks)
    content_sha256 = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    snapshot = fixture.extraction.snapshot.model_copy(
        update={
            "content_sha256": content_sha256,
            "content_storage_ref": f"blobs/protocol_blocks/{key}.json",
        }
    )
    extraction = StructureExtraction(blocks=blocks, snapshot=snapshot)
    package = ProtocolDeconstructionInputAssembler(frozen_at=NOW).assemble(
        project_id="execution-project",
        protocol_version_id="execution-protocol",
        source_artifact=fixture.artifact,
        extraction=extraction,
        source_spans=fixture.spans,
        phase_graph=fixture.phase_graph,
        identity_decision=fixture.identity,
        phase_selection=fixture.selection,
    )

    snapshot_path = data_paths.blobs_dir / snapshot.content_storage_ref
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(serialized, encoding="utf-8")

    steps: list[StepSpec] = []
    previous: str | None = None
    for step_id in _SOURCE_STEP_ORDER:
        steps.append(
            StepSpec(
                step_id=step_id,
                name=step_id,
                depends_on=(previous,) if previous is not None else (),
            )
        )
        previous = step_id
    source = JobService(session_factory, now=_now).create_job(
        idempotency_key=key,
        job_type=PROTOCOL_DECONSTRUCTION_JOB_TYPE,
        payload={"source_input": package.source_input.model_dump(mode="json")},
        steps=steps,
    )

    checkpoint = {
        "source_input": package.source_input.model_dump(mode="json"),
        "extraction_snapshot": snapshot.model_dump(mode="json"),
        "phase_graph": fixture.phase_graph.model_dump(mode="json"),
        "phase_projection": package.projection.model_dump(mode="json"),
        "source_spans": {
            span_id: span.model_dump(mode="json")
            for span_id, span in package.source_spans.items()
        },
    }
    with session_factory() as session, session.begin():
        store = JobStore(session, now=_now)
        lease = store.claim_job(source.job_id, "source-seed")
        assert lease is not None
        for step in steps:
            store.start_step(lease, step.step_id)
            store.complete_step(lease, step.step_id, checkpoint_payload=checkpoint)
        store.finish_success(lease)

    workflow_stages = tuple(
        WorkflowStage(
            workflow_stage_id=f"workflow-{item.item_id}",
            stage=item.review_stage,
            display_name=f"stage-{item.item_id}",
            visit_instance=item.visit_instance,
        )
        for item in package.source_input.required_procedure_catalog.items
    )
    assert all(isinstance(stage.stage, ReviewStage) for stage in workflow_stages)
    source_span_excerpts = {
        span_id: span.excerpt
        for span_id, span in package.source_spans.items()
        if span.excerpt
    }
    return _Seed(
        source_job_id=source.job_id,
        snapshot_path=snapshot_path,
        source_span_excerpts=source_span_excerpts,
        workflow_stages=workflow_stages,
    )


def _build_service(data_paths, session_factory, seed: _Seed, **overrides: Any):
    config = {
        "max_discovery_units_per_batch": 256,
        "discovery_context_radius": 1,
        "max_deep_units_per_batch": 2,
        "actor": "system",
        "workflow_stages": seed.workflow_stages,
        "now": _now,
    }
    config.update(overrides)
    return ProtocolControlJobService(
        session_factory,
        data_paths=data_paths,
        **config,
    )


def test_service_derives_unique_workflow_nodes_from_frozen_source(
    data_paths,
    session_factory,
) -> None:
    seed = _seed_frozen_source(data_paths, session_factory, key="derived-workflow")
    result = ProtocolControlJobService(
        session_factory,
        data_paths=data_paths,
        max_discovery_units_per_batch=256,
        now=_now,
    ).create_from_deconstruction(
        source_job_id=seed.source_job_id,
        idempotency_key="derived-workflow-control",
    )

    with session_factory() as session:
        job = JobStore(session, now=_now).get_job(result.job_id)
    payload = json.loads(job.payload_json)
    procedures = payload["source_input"]["required_procedure_catalog"]["items"]
    stages = payload["workflow_stages"]
    procedure_keys = {
        (item["review_stage"], item["visit_instance"]) for item in procedures
    }
    stage_keys = {(item["stage"], item["visit_instance"]) for item in stages}

    assert stage_keys == procedure_keys
    assert len(stages) == len(stage_keys)
    assert len({item["workflow_stage_id"] for item in stages}) == len(stages)
    assert all(item["display_name"] == item["visit_instance"] for item in stages)


def _build_runner(data_paths, session_factory, discovery, deep):
    executor = create_protocol_control_executor(
        ProtocolControlExecutorConfig(
            data_paths=data_paths,
            session_factory=session_factory,
            now=_now,
            discovery_transport=discovery,
            deep_transport=deep,
        )
    )
    return JobRunner(
        session_factory,
        {PROTOCOL_CONTROL_EXECUTION_JOB_TYPE: executor},
        worker_id="execution-test-worker",
        now=_now,
        sleep=lambda _seconds: None,
    ), executor


def test_previous_discovery_contract_cannot_replay_under_new_prompt(
    data_paths, session_factory
) -> None:
    executor = create_protocol_control_executor(
        ProtocolControlExecutorConfig(
            data_paths=data_paths,
            session_factory=session_factory,
            now=_now,
        )
    )
    context = StepContext(
        job_id="previous-version",
        job_type=PROTOCOL_CONTROL_EXECUTION_JOB_TYPE,
        job_payload={"execution_version": "phase5/protocol-control-execution/v14"},
        step_id="discovery_0001",
        name="发现批次 0001",
        attempt=1,
        last_checkpoint_id="old-checkpoint",
        last_checkpoint={"stage": "discovery"},
    )
    with pytest.raises(StepFailure) as failure:
        executor(context)
    assert failure.value.error_code == "PROTOCOL_CONTROL_EXECUTION_VERSION_MISMATCH"


def _prompt_payload(prompt: str, marker: str) -> dict[str, Any]:
    return json.loads(prompt.split(marker, 1)[1].split("\n\n", 1)[0])


class _DiscoveryTransport:
    def __init__(self, *, invalid: bool = False) -> None:
        self.invalid = invalid
        self.start_calls = 0
        self.continue_calls = 0
        self.routing: dict[str, ProtocolControlDiscoveryDisposition] = {}
        self.candidate_unit_ids: set[str] = set()

    def _response(self, prompt: str) -> ProtocolControlDiscoveryAgentResponse:
        payload = _prompt_payload(prompt, "本次发现输入：")
        units = payload["target_units"]
        if self.invalid:
            return ProtocolControlDiscoveryAgentResponse(session_id="discovery-session", text="{}")

        for unit in units:
            unit_id = unit["structure_unit_id"]
            if unit_id in self.routing:
                continue
            if unit.get("excerpt", "").strip() and len(self.candidate_unit_ids) < 4:
                disposition = (
                    ProtocolControlDiscoveryDisposition.CANDIDATE
                    if len(self.candidate_unit_ids) % 2 == 0
                    else ProtocolControlDiscoveryDisposition.UNCERTAIN
                )
                self.candidate_unit_ids.add(unit_id)
            else:
                disposition = (
                    ProtocolControlDiscoveryDisposition.CONTEXT_ONLY
                    if len(self.routing) % 2 == 0
                    else ProtocolControlDiscoveryDisposition.NON_CONTROL
                )
            self.routing[unit_id] = disposition

        decisions = [
            {
                "structure_unit_id": unit["structure_unit_id"],
                "disposition": self.routing[unit["structure_unit_id"]].value,
                "required_context_structure_unit_ids": [],
                "rationale": "synthetic routing",
            }
            for unit in units
        ]
        return ProtocolControlDiscoveryAgentResponse(
            session_id="discovery-session",
            text=json.dumps(
                {
                    "wire_version": CONTROL_DISCOVERY_WIRE_VERSION,
                    "decisions": decisions,
                },
                ensure_ascii=False,
            ),
        )

    def start(self, *, prompt: str) -> ProtocolControlDiscoveryAgentResponse:
        self.start_calls += 1
        return self._response(prompt)

    def continue_session(
        self,
        *,
        session_id: str,
        prompt: str,
    ) -> ProtocolControlDiscoveryAgentResponse:
        self.continue_calls += 1
        raise AssertionError(f"automatic discovery repair unexpectedly opened {session_id}")


class _DeepTransport:
    def __init__(
        self,
        source_span_excerpts: dict[str, str],
        *,
        invalid: bool = False,
        process_death_once: bool = False,
    ) -> None:
        self.source_span_excerpts = source_span_excerpts
        self.invalid = invalid
        self.process_death_once = process_death_once
        self.start_calls = 0
        self.continue_calls = 0
        self.owned_batches: list[tuple[str, ...]] = []
        self._death_raised = False

    def _response(self, prompt: str) -> ProtocolControlAgentResponse:
        payload = _prompt_payload(prompt, "本次冻结输入：")
        units = payload["owned_units"]
        self.owned_batches.append(tuple(unit["structure_unit_id"] for unit in units))
        if self.invalid:
            return ProtocolControlAgentResponse(session_id="deep-session", text="{}")

        targets = payload["known_workflow_stage_targets"]
        assert targets
        stage = targets[0]
        dispositions = []
        candidates = []
        for unit in units:
            unit_id = unit["structure_unit_id"]
            span_ids = sorted(unit["source_span_ids"])
            excerpts = [
                self.source_span_excerpts.get(span_id, unit["excerpt"])
                for span_id in span_ids
            ]
            assert all(excerpt.strip() for excerpt in excerpts)
            dispositions.append(
                {
                    "structure_unit_id": unit_id,
                    "disposition": StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE.value,
                    "linked_official_code": None,
                    "linked_procedure_catalog_item_id": None,
                    "linked_procedure_catalog_item_ids": [],
                    "notes": "synthetic candidate",
                }
            )
            candidates.append(
                {
                    "title": "candidate package",
                    "applicable_population": "selected scope",
                    "applicability_expression": None,
                    "trigger_expression": None,
                    "obligation_expression": {
                        "groups": [
                            {
                                "atoms": [
                                    {
                                        "kind": ControlObligationKind.REACH_CONDITION.value,
                                        "statement": "record source state",
                                        "evaluation": {
                                            "determination_mode": "semantic",
                                            "proposition": "record source state",
                                            "time_purpose": "not_applicable",
                                            "repeat_scheme": None,
                                            "observation_policy": {
                                                "mode": "unresolved",
                                                "scope": "synthetic fixture has no record selection rule",
                                                "source_span_ids": span_ids,
                                                "source_excerpts": excerpts,
                                            },
                                            "source_span_ids": span_ids,
                                            "source_excerpts": excerpts,
                                        },
                                        "time_constraint": None,
                                        "prospective_period": None,
                                        "modality": "mandatory",
                                        "temporal_scope": None,
                                        "source_span_ids": span_ids,
                                        "source_excerpts": excerpts,
                                        "requires_professional_judgment": False,
                                    }
                                ],
                                "applies_to_trigger_branch_indexes": [],
                            }
                        ]
                    },
                    "exception_expression": None,
                    "repeat_trigger_conditions": [],
                    "review_node_bindings": [
                        {
                            "workflow_stage_id": stage["workflow_stage_id"],
                            "review_stage": stage["review_stage"],
                            "role": ReviewNodeRole.DECIDE_AT_NODE.value,
                            "guidance": None,
                        }
                    ],
                    "minimum_evidence": [
                        {
                            "fact_type": "source",
                            "description": "source evidence",
                            "due_stage": stage["review_stage"],
                            "required_source_types": ["source"],
                            "workflow_stage_ids": [stage["workflow_stage_id"]],
                            "source_policy": {
                                "requires_contemporaneous_objective_source": None,
                                "allows_screening_record_transcription": None,
                                "result_validity_status": "not_specified",
                                "result_validity_constraint": None,
                                "source_span_ids": span_ids,
                                "source_excerpts": excerpts,
                            },
                            "atom_refs": [
                                {
                                    "layer": "obligation",
                                    "group_index": 0,
                                    "atom_index": 0,
                                }
                            ],
                        }
                    ],
                    "source_structure_unit_ids": [unit_id],
                    "source_span_ids": span_ids,
                    "cross_source_relations": [],
                }
            )
        return ProtocolControlAgentResponse(
            session_id="deep-session",
            text=json.dumps(
                {
                    "wire_version": CONTROL_AGENT_WIRE_VERSION,
                    "dispositions": dispositions,
                    "candidate_drafts": candidates,
                },
                ensure_ascii=False,
            ),
        )

    def start(self, *, prompt: str) -> ProtocolControlAgentResponse:
        self.start_calls += 1
        if self.process_death_once and not self._death_raised:
            self._death_raised = True
            raise ProcessDeath()
        return self._response(prompt)

    def continue_session(
        self,
        *,
        session_id: str,
        prompt: str,
    ) -> ProtocolControlAgentResponse:
        self.continue_calls += 1
        raise AssertionError(f"automatic deep repair unexpectedly opened {session_id}")


class _RepairingDeepTransport(_DeepTransport):
    def __init__(self, source_span_excerpts: dict[str, str]) -> None:
        super().__init__(source_span_excerpts)
        self._last_response: ProtocolControlAgentResponse | None = None

    def start(self, *, prompt: str) -> ProtocolControlAgentResponse:
        self.start_calls += 1
        self._last_response = self._response(prompt)
        return self._last_response

    def continue_session(
        self,
        *,
        session_id: str,
        prompt: str,
    ) -> ProtocolControlAgentResponse:
        self.continue_calls += 1
        assert self._last_response is not None
        assert session_id == self._last_response.session_id
        return self._last_response


def _job_snapshot_and_payload(session_factory, job_id: str):
    with session_factory() as session:
        store = JobStore(session, now=_now)
        job = store.get_job(job_id)
        return (
            store.snapshot(job_id),
            verify_payload_sha256(job.payload_json, job.payload_sha256),
        )


def test_service_reuses_frozen_snapshot_and_builds_candidate_package(
    data_paths,
    session_factory,
):
    seed = _seed_frozen_source(data_paths, session_factory, key="full-pipeline")
    discovery = _DiscoveryTransport()
    deep = _DeepTransport(seed.source_span_excerpts)
    service = _build_service(data_paths, session_factory, seed)
    result = service.create_from_deconstruction(
        source_job_id=seed.source_job_id,
        idempotency_key="control-full-pipeline",
    )
    seed.snapshot_path.unlink()
    runner, executor = _build_runner(data_paths, session_factory, discovery, deep)

    assert runner.run_job(result.job_id)
    snapshot, payload = _job_snapshot_and_payload(session_factory, result.job_id)
    assert snapshot.state == "completed"
    step_ids = {step.step_id for step in snapshot.steps}
    assert {"deterministic_closure", "hydrate", "gate"} <= step_ids
    assert {step_id for step_id in step_ids if step_id.startswith("deep_")} == {
        "deep_0001",
        "deep_0002",
    }
    assert set().union(*map(set, deep.owned_batches)) == discovery.candidate_unit_ids
    assert all(set(batch) <= discovery.candidate_unit_ids for batch in deep.owned_batches)

    with session_factory() as session:
        gate_checkpoint = JobStore(session, now=_now).get_last_checkpoint(
            result.job_id, "gate"
        )
    assert gate_checkpoint is not None
    _, gate = gate_checkpoint
    assert gate["result_kind"] == CANDIDATE_CONTROL_PACKAGE_RESULT_KIND
    assert gate["formal_catalog_status"] == FORMAL_CATALOG_STATUS_NOT_MATERIALIZED
    assert "catalog" not in gate
    assert gate["batch_dispositions"]
    assert gate["candidate_ids"]
    assert set(gate["candidate_ids"]) == {
        candidate_id
        for batch in gate["batch_dispositions"]
        for candidate in batch["candidates"]
        for candidate_id in [candidate["control_candidate_id"]]
    }
    assert payload["source_snapshot_id"] == result.snapshot_id

    gate_step = next(step for step in snapshot.steps if step.step_id == "gate")
    replay_context = StepContext(
        job_id=result.job_id,
        job_type=PROTOCOL_CONTROL_EXECUTION_JOB_TYPE,
        job_payload=payload,
        step_id="gate",
        name=gate_step.name,
        attempt=gate_step.attempt,
        last_checkpoint_id=gate_checkpoint[0],
        last_checkpoint=gate,
        max_attempts=gate_step.max_attempts,
    )
    starts_before = (discovery.start_calls, deep.start_calls)
    assert executor(replay_context) == gate
    assert (discovery.start_calls, deep.start_calls) == starts_before


def test_new_job_adopts_only_completed_matching_discovery_decisions(
    data_paths, session_factory
) -> None:
    seed = _seed_frozen_source(data_paths, session_factory, key="discovery-adoption")
    discovery = _DiscoveryTransport()
    deep = _DeepTransport(seed.source_span_excerpts)
    route = lambda stage: protocol_control_execution_module._transport_identity_digest(
        discovery if stage == "discovery" else deep, stage=stage
    )
    service = _build_service(
        data_paths, session_factory, seed, route_identity_factory=route
    )
    source = service.create_from_deconstruction(
        source_job_id=seed.source_job_id, idempotency_key="discovery-adoption-source"
    )
    runner, _ = _build_runner(data_paths, session_factory, discovery, deep)
    assert runner.run_job(source.job_id)
    assert _job_snapshot_and_payload(session_factory, source.job_id)[0].state == "completed"
    original_discovery_calls = discovery.start_calls
    original_deep_calls = deep.start_calls

    adopted = service.create_from_deconstruction(
        source_job_id=seed.source_job_id,
        idempotency_key="discovery-adoption-target",
        discovery_source_job_id=source.job_id,
    )
    assert runner.run_job(adopted.job_id)
    snapshot, _ = _job_snapshot_and_payload(session_factory, adopted.job_id)
    assert snapshot.state == "completed"
    assert discovery.start_calls == original_discovery_calls
    assert deep.start_calls > original_deep_calls
    with session_factory() as session:
        store = JobStore(session, now=_now)
        adopted_checkpoint = store.get_last_checkpoint(adopted.job_id, "discovery_0001")
        original_checkpoint = store.get_last_checkpoint(source.job_id, "discovery_0001")
    assert adopted_checkpoint is not None and original_checkpoint is not None
    assert adopted_checkpoint[1]["adopted_from"] == {
        "job_id": source.job_id, "checkpoint_id": original_checkpoint[0]
    }
    assert adopted_checkpoint[1]["run_result"] == original_checkpoint[1]["run_result"]

    with pytest.raises(protocol_control_execution_module.ProtocolControlExecutionError) as mismatch:
        _build_service(
            data_paths, session_factory, seed,
            max_discovery_units_per_batch=1,
            route_identity_factory=route,
        ).create_from_deconstruction(
            source_job_id=seed.source_job_id,
            idempotency_key="discovery-adoption-wrong-plan",
            discovery_source_job_id=source.job_id,
        )
    assert mismatch.value.code == "PROTOCOL_CONTROL_DISCOVERY_SOURCE_INVALID"


def test_frozen_model_route_rejects_changed_discovery_before_call(
    data_paths, session_factory
) -> None:
    seed = _seed_frozen_source(data_paths, session_factory, key="frozen-route-changed")
    discovery = _DiscoveryTransport()
    deep = _DeepTransport(seed.source_span_excerpts)
    discovery.model = "original-model"
    service = _build_service(
        data_paths,
        session_factory,
        seed,
        route_identity_factory=lambda stage: protocol_control_execution_module._transport_identity_digest(
            discovery if stage == "discovery" else deep, stage=stage
        ),
    )
    result = service.create_from_deconstruction(
        source_job_id=seed.source_job_id,
        idempotency_key="frozen-route-changed-control",
    )
    _, payload = _job_snapshot_and_payload(session_factory, result.job_id)
    assert set(payload["frozen_model_routes"]) == {"discovery", "deep"}
    assert all(len(value) == 64 for value in payload["frozen_model_routes"].values())

    discovery.model = "different-model"
    runner, _ = _build_runner(data_paths, session_factory, discovery, deep)
    assert runner.run_job(result.job_id)
    snapshot, _ = _job_snapshot_and_payload(session_factory, result.job_id)
    failed = next(step for step in snapshot.steps if step.state == "failed_final")
    assert failed.error_code == "PROTOCOL_CONTROL_ROUTE_CHANGED"
    assert discovery.start_calls == 0
    assert deep.start_calls == 0


def test_frozen_model_route_rejects_changed_deep_after_discovery(
    data_paths, session_factory
) -> None:
    seed = _seed_frozen_source(data_paths, session_factory, key="frozen-deep-changed")
    deep = _DeepTransport(seed.source_span_excerpts)
    deep.model = "original-deep-model"

    class DiscoveryThenSwitch(_DiscoveryTransport):
        def start(self, *, prompt: str) -> ProtocolControlDiscoveryAgentResponse:
            response = super().start(prompt=prompt)
            deep.model = "different-deep-model"
            return response

    discovery = DiscoveryThenSwitch()
    service = _build_service(
        data_paths,
        session_factory,
        seed,
        route_identity_factory=lambda stage: protocol_control_execution_module._transport_identity_digest(
            discovery if stage == "discovery" else deep, stage=stage
        ),
        max_deep_units_per_batch=256,
    )
    result = service.create_from_deconstruction(
        source_job_id=seed.source_job_id,
        idempotency_key="frozen-deep-changed-control",
    )
    runner, _ = _build_runner(data_paths, session_factory, discovery, deep)
    assert runner.run_job(result.job_id)
    snapshot, _ = _job_snapshot_and_payload(session_factory, result.job_id)
    failed = next(step for step in snapshot.steps if step.state == "failed_final")
    assert failed.step_id.startswith("deep_")
    assert failed.error_code == "PROTOCOL_CONTROL_ROUTE_CHANGED"
    assert discovery.start_calls >= 1
    assert deep.start_calls == 0


def test_deep_publication_gate_repairs_in_the_originating_session(
    data_paths,
    session_factory,
    monkeypatch,
) -> None:
    seed = _seed_frozen_source(data_paths, session_factory, key="deep-gate-repair")
    discovery = _DiscoveryTransport()
    deep = _RepairingDeepTransport(seed.source_span_excerpts)
    real_validator = (
        protocol_control_execution_module.check_protocol_control_batch_candidates
    )
    validator_calls = 0

    def reject_once(batch, output):
        nonlocal validator_calls
        validator_calls += 1
        if validator_calls == 1:
            candidate = output.candidates[0]
            return (ProtocolControlGateError(
                "MIXED_DECISION_STAGE_CONTROL",
                "当前操作与后续节点有效性必须拆分",
                entity_id=candidate.control_candidate_id,
                structure_unit_ids=candidate.frozen_structure_unit_ids,
                candidate_ids=(candidate.control_candidate_id,),
            ),)
        return real_validator(batch, output)

    monkeypatch.setattr(
        protocol_control_execution_module,
        "check_protocol_control_batch_candidates",
        reject_once,
    )
    result = _build_service(
        data_paths,
        session_factory,
        seed,
        max_deep_units_per_batch=256,
    ).create_from_deconstruction(
        source_job_id=seed.source_job_id,
        idempotency_key="control-deep-gate-repair",
    )
    runner, _ = _build_runner(data_paths, session_factory, discovery, deep)

    assert runner.run_job(result.job_id)
    snapshot, _ = _job_snapshot_and_payload(session_factory, result.job_id)
    assert snapshot.state == "completed"
    assert deep.start_calls == 1
    assert deep.continue_calls == 1
    with session_factory() as session:
        deep_step = next(
            step for step in snapshot.steps if step.step_id.startswith("deep_")
        )
        checkpoint = JobStore(session, now=_now).get_last_checkpoint(
            result.job_id,
            deep_step.step_id,
        )
    assert checkpoint is not None
    attempts = checkpoint[1]["run_result"]["attempts"]
    assert [attempt["outcome"] for attempt in attempts] == [
        "publication_invalid",
        "parsed",
    ]
    assert {attempt["session_id"] for attempt in attempts} == {"deep-session"}
    assert checkpoint[1]["run_result"]["repair_used"] is True

    from app.agents import protocol_control_deconstructor as deconstructor

    monkeypatch.setattr(
        deconstructor, "_CONTROL_REPAIR_CONTRACT",
        deconstructor._CONTROL_REPAIR_CONTRACT + "\n修订补答说明。",
    )
    planned = _build_service(
        data_paths, session_factory, seed, max_deep_units_per_batch=256,
    ).create_from_deconstruction(
        source_job_id=seed.source_job_id,
        idempotency_key="control-deep-gate-repair-new-contract",
        deep_source_job_id=result.job_id,
    )
    _, payload = _job_snapshot_and_payload(session_factory, planned.job_id)
    assert {item["reason"] for item in payload["deep_reuse_plan"]["decisions"].values()} == {
        "repair_material_changed_or_unproven"
    }


def test_uncertain_discovery_is_final_without_blind_retry(data_paths, session_factory):
    seed = _seed_frozen_source(data_paths, session_factory, key="discovery-review")
    discovery = _DiscoveryTransport(invalid=True)
    deep = _DeepTransport(seed.source_span_excerpts)
    service = _build_service(
        data_paths,
        session_factory,
        seed,
        discovery_max_schema_repairs=0,
    )
    result = service.create_from_deconstruction(
        source_job_id=seed.source_job_id,
        idempotency_key="control-discovery-review",
    )
    runner, _ = _build_runner(data_paths, session_factory, discovery, deep)

    assert runner.run_job(result.job_id)
    snapshot, _ = _job_snapshot_and_payload(session_factory, result.job_id)
    assert snapshot.state == "failed_final"
    discovery_step = next(
        step for step in snapshot.steps if step.step_id.startswith("discovery_")
    )
    assert discovery_step.state == "failed_final"
    assert discovery_step.error_code == "PROTOCOL_CONTROL_DISCOVERY_NEEDS_REVIEW"
    assert discovery.start_calls == 1
    assert discovery.continue_calls == 0
    assert not runner.run_job(result.job_id)
    assert discovery.start_calls == 1


def test_uncertain_deep_is_final_without_blind_retry(data_paths, session_factory):
    seed = _seed_frozen_source(data_paths, session_factory, key="deep-review")
    discovery = _DiscoveryTransport()
    deep = _DeepTransport(seed.source_span_excerpts, invalid=True)
    service = _build_service(
        data_paths,
        session_factory,
        seed,
        deep_max_schema_repairs=0,
    )
    result = service.create_from_deconstruction(
        source_job_id=seed.source_job_id,
        idempotency_key="control-deep-review",
    )
    runner, _ = _build_runner(data_paths, session_factory, discovery, deep)

    assert runner.run_job(result.job_id)
    snapshot, _ = _job_snapshot_and_payload(session_factory, result.job_id)
    assert snapshot.state == "failed_final"
    deep_step = next(step for step in snapshot.steps if step.step_id.startswith("deep_"))
    assert deep_step.state == "failed_final"
    assert deep_step.error_code == "PROTOCOL_CONTROL_DEEP_OUTPUT_INVALID"
    with session_factory() as session:
        failure_checkpoint = JobStore(session, now=_now).get_last_checkpoint(
            result.job_id, deep_step.step_id
        )
    assert failure_checkpoint is not None
    saved = failure_checkpoint[1]
    assert saved["stage"] == "deep_failure_diagnostic"
    assert saved["schema_version"] == "phase5/deep-failure-diagnostic/v3"
    assert saved["partial_wire"] is None
    assert saved["batch_id"]
    assert saved["source_interpretation"] is None
    assert saved["source_statement_coverage"] == []
    assert saved["source_target_review"] is None
    assert saved["attempts"][0]["raw_output_sha256"]
    assert saved["attempts"][0]["raw_output_text"] is not None
    assert deep.start_calls == 1
    assert deep.continue_calls == 0
    assert not runner.run_job(result.job_id)
    assert deep.start_calls == 1


def test_manual_retry_reexecutes_failed_deep_instead_of_replaying_diagnostic(
    data_paths, session_factory,
):
    seed = _seed_frozen_source(data_paths, session_factory, key="deep-manual-retry")
    discovery = _DiscoveryTransport()
    deep = _DeepTransport(seed.source_span_excerpts, invalid=True)
    service = _build_service(
        data_paths, session_factory, seed, deep_max_schema_repairs=0,
    )
    result = service.create_from_deconstruction(
        source_job_id=seed.source_job_id, idempotency_key="control-deep-manual-retry",
    )
    runner, _ = _build_runner(data_paths, session_factory, discovery, deep)
    assert runner.run_job(result.job_id)
    assert _job_snapshot_and_payload(session_factory, result.job_id)[0].state == "failed_final"
    with session_factory() as session, session.begin():
        JobStore(session, now=_now).retry_failed(result.job_id)
    deep.invalid = False
    assert runner.run_job(result.job_id)
    snapshot, _ = _job_snapshot_and_payload(session_factory, result.job_id)
    assert snapshot.state == "completed"
    assert deep.start_calls == 3
    assert deep.owned_batches[1] == deep.owned_batches[0]


def test_manual_retry_uses_verified_partial_wire_without_full_reread(
    data_paths, session_factory, monkeypatch,
) -> None:
    from app.agents.protocol_control_deconstructor import (
        ProtocolControlAgentAttempt, ProtocolControlAgentRunResult,
        ProtocolControlAgentRunner, build_protocol_control_agent_prompt,
        parse_protocol_control_agent_wire,
    )
    from app.agents.protocol_control_source_interpretation import (
        SOURCE_INTERPRETATION_VERSION, SourceInterpretation,
    )

    seed = _seed_frozen_source(data_paths, session_factory, key="deep-partial-resume")
    discovery = _DiscoveryTransport()
    deep = _DeepTransport(seed.source_span_excerpts)
    service = _build_service(data_paths, session_factory, seed)
    job = service.create_from_deconstruction(
        source_job_id=seed.source_job_id, idempotency_key="deep-partial-resume-job",
    )
    runner, _ = _build_runner(data_paths, session_factory, discovery, deep)
    original_run = ProtocolControlAgentRunner.run
    resumed = []
    failed_once = False

    def fail_then_resume(self, batch, transport, **kwargs):
        nonlocal failed_once
        if kwargs.get("resume_wire") is not None:
            resumed.append(kwargs["resume_wire"].model_dump(mode="json"))
            return original_run(self, batch, transport, **kwargs)
        if failed_once:
            return original_run(self, batch, transport, **kwargs)
        failed_once = True
        prompt = build_protocol_control_agent_prompt(
            batch, prompt_template=kwargs["prompt_template"],
        )
        wire = parse_protocol_control_agent_wire(deep._response(prompt).text)
        interpretation = SourceInterpretation(
            version=SOURCE_INTERPRETATION_VERSION,
            statements=[],
            units_without_statement=list(batch.owned_structure_unit_ids),
        )
        return ProtocolControlAgentRunResult(
            status="需要核对", batch_id=batch.batch_id, session_id="deep-session",
            attempts=[ProtocolControlAgentAttempt(
                attempt=1, session_id="deep-session",
                raw_output_sha256=hashlib.sha256(wire.model_dump_json().encode()).hexdigest(),
                outcome="publication_invalid",
            )],
            source_interpretation=interpretation, partial_wire=wire,
        )

    monkeypatch.setattr(ProtocolControlAgentRunner, "run", fail_then_resume)
    assert runner.run_job(job.job_id)
    snapshot, _ = _job_snapshot_and_payload(session_factory, job.job_id)
    assert snapshot.state == "failed_final"
    with session_factory() as session:
        saved = JobStore(session, now=_now).get_last_checkpoint(job.job_id, "deep_0001")
    assert saved is not None
    assert saved[1]["partial_wire"] is not None
    assert saved[1]["source_interpretation"] is not None
    with session_factory() as session, session.begin():
        JobStore(session, now=_now).retry_failed(job.job_id)
    assert runner.run_job(job.job_id)
    snapshot, _ = _job_snapshot_and_payload(session_factory, job.job_id)
    assert snapshot.state == "completed", [
        (step.step_id, step.state, step.error_code)
        for step in snapshot.steps if step.state == "failed_final"
    ]
    assert resumed
    assert deep.start_calls == 1  # Only the next batch needs a fresh full read.


def test_same_identity_deep_source_reuses_validated_batches_without_model_calls(
    data_paths, session_factory,
):
    seed = _seed_frozen_source(data_paths, session_factory, key="deep-source-reuse")
    discovery = _DiscoveryTransport()
    deep = _DeepTransport(seed.source_span_excerpts)
    service = _build_service(data_paths, session_factory, seed)
    source = service.create_from_deconstruction(
        source_job_id=seed.source_job_id, idempotency_key="deep-source-first",
    )
    runner, _ = _build_runner(data_paths, session_factory, discovery, deep)
    assert runner.run_job(source.job_id)
    assert _job_snapshot_and_payload(session_factory, source.job_id)[0].state == "completed"
    old_calls = deep.start_calls

    adopted = service.create_from_deconstruction(
        source_job_id=seed.source_job_id,
        idempotency_key="deep-source-adopted",
        deep_source_job_id=source.job_id,
    )
    deep.invalid = True
    assert runner.run_job(adopted.job_id)
    assert _job_snapshot_and_payload(session_factory, adopted.job_id)[0].state == "completed"
    assert deep.start_calls == old_calls
    with session_factory() as session:
        saved = JobStore(session, now=_now).get_last_checkpoint(adopted.job_id, "deep_0001")
    assert saved is not None
    assert saved[1]["adopted_from"]["job_id"] == source.job_id


def test_unused_repair_wording_does_not_rerun_completed_deep_batches(
    data_paths, session_factory, monkeypatch,
):
    from app.agents import protocol_control_deconstructor as deconstructor

    seed = _seed_frozen_source(data_paths, session_factory, key="unused-repair-wording")
    deep = _DeepTransport(seed.source_span_excerpts)
    service = _build_service(data_paths, session_factory, seed)
    source = service.create_from_deconstruction(
        source_job_id=seed.source_job_id, idempotency_key="unused-repair-source",
    )
    runner, _ = _build_runner(data_paths, session_factory, _DiscoveryTransport(), deep)
    assert runner.run_job(source.job_id)
    before = deep.start_calls
    monkeypatch.setattr(
        deconstructor, "_CONTROL_REPAIR_CONTRACT",
        deconstructor._CONTROL_REPAIR_CONTRACT + "\n修订了未使用的补答说明。",
    )
    adopted = service.create_from_deconstruction(
        source_job_id=seed.source_job_id,
        idempotency_key="unused-repair-adopted",
        deep_source_job_id=source.job_id,
    )
    _, payload = _job_snapshot_and_payload(session_factory, adopted.job_id)
    assert {item["decision"] for item in payload["deep_reuse_plan"]["decisions"].values()} == {"reusable"}
    assert runner.run_job(adopted.job_id)
    assert deep.start_calls == before


def test_repair_material_identity_is_required_only_if_repair_was_used(monkeypatch):
    from app.agents import protocol_control_deconstructor as deconstructor

    hash_before = protocol_control_execution_module.protocol_control_agent_repair_contract_sha256()
    no_repair = {"run_result": {"repair_used": False}}
    repaired = {
        "run_result": {"repair_used": True},
        "repair_contract_sha256": hash_before,
    }
    assert protocol_control_execution_module._repair_material_matches(no_repair)
    assert protocol_control_execution_module._repair_material_matches(repaired)
    assert not protocol_control_execution_module._repair_material_matches(
        {"run_result": {}}
    )
    monkeypatch.setattr(
        deconstructor, "_CONTROL_REPAIR_CONTRACT",
        deconstructor._CONTROL_REPAIR_CONTRACT + "\n新补答范围。",
    )
    assert protocol_control_execution_module._repair_material_matches(no_repair)
    assert not protocol_control_execution_module._repair_material_matches(repaired)


def test_corrupt_repair_receipt_fails_preflight_instead_of_cache_refresh(
    data_paths, session_factory, monkeypatch,
):
    seed = _seed_frozen_source(data_paths, session_factory, key="repair-receipt-corrupt")
    deep = _DeepTransport(seed.source_span_excerpts)
    service = _build_service(data_paths, session_factory, seed)
    source = service.create_from_deconstruction(
        source_job_id=seed.source_job_id, idempotency_key="repair-receipt-source",
    )
    runner, _ = _build_runner(data_paths, session_factory, _DiscoveryTransport(), deep)
    assert runner.run_job(source.job_id)
    before = deep.start_calls
    original = JobStore.get_last_checkpoint

    def damaged(self, job_id, step_id):
        checkpoint = original(self, job_id, step_id)
        if job_id != source.job_id or step_id != "deep_0001" or checkpoint is None:
            return checkpoint
        checkpoint_id, saved = checkpoint
        return checkpoint_id, dict(saved, repair_contract_sha256="broken")

    monkeypatch.setattr(JobStore, "get_last_checkpoint", damaged)
    with pytest.raises(protocol_control_execution_module.ProtocolControlExecutionError) as exc:
        service.create_from_deconstruction(
            source_job_id=seed.source_job_id,
            idempotency_key="repair-receipt-corrupt-adopted",
            deep_source_job_id=source.job_id,
        )
    assert exc.value.code == "PROTOCOL_CONTROL_DEEP_SOURCE_INVALID"
    assert deep.start_calls == before


def test_deep_source_identity_compares_frozen_scope_without_version_whitelist() -> None:
    fields = protocol_control_execution_module._DEEP_SOURCE_IDENTITY_FIELDS
    current = {field: {"same": field} for field in fields}
    current["execution_version"] = protocol_control_execution_module.PROTOCOL_CONTROL_EXECUTION_VERSION
    previous = dict(current, execution_version="phase5/protocol-control-execution/v116")
    protocol_control_execution_module._require_compatible_deep_source(current, previous)
    protocol_control_execution_module._require_compatible_deep_source(
        current, dict(previous, execution_version="unrelated-version-label")
    )
    with pytest.raises(StepFailure) as wrong_source:
        protocol_control_execution_module._require_compatible_deep_source(
            current, dict(previous, source_content_sha256="different")
        )
    assert wrong_source.value.error_code == "PROTOCOL_CONTROL_DEEP_SOURCE_INVALID"


def test_deep_source_prompt_change_is_planned_before_job_runs(
    data_paths, session_factory,
):
    from app.evidence.artifacts import ArtifactStore

    seed = _seed_frozen_source(data_paths, session_factory, key="deep-reuse-prompt")
    discovery = _DiscoveryTransport()
    deep = _DeepTransport(seed.source_span_excerpts)
    original = _build_service(data_paths, session_factory, seed)
    source = original.create_from_deconstruction(
        source_job_id=seed.source_job_id, idempotency_key="deep-reuse-prompt-source",
    )
    runner, _ = _build_runner(data_paths, session_factory, discovery, deep)
    assert runner.run_job(source.job_id)
    calls_before = deep.start_calls

    changed = _build_service(
        data_paths, session_factory, seed,
        deep_prompt_template="当前提示材料已修订；旧回执不可当作本次模型输入。",
    )
    planned = changed.create_from_deconstruction(
        source_job_id=seed.source_job_id,
        idempotency_key="deep-reuse-prompt-current",
        deep_source_job_id=source.job_id,
    )
    _, payload = _job_snapshot_and_payload(session_factory, planned.job_id)
    plan = payload["deep_reuse_plan"]
    assert {item["decision"] for item in plan["decisions"].values()} == {
        "refresh_required"
    }
    assert {item["reason"] for item in plan["decisions"].values()} == {
        "prompt_material_changed"
    }
    assert json.loads(ArtifactStore(data_paths).read(
        payload["deep_reuse_plan_artifact_ref"]
    )) == plan
    assert deep.start_calls == calls_before
    assert runner.run_job(planned.job_id)
    assert _job_snapshot_and_payload(session_factory, planned.job_id)[0].state == "completed"
    assert deep.start_calls > calls_before


def test_deep_source_corrupt_completed_checkpoint_rejected_before_job_creation(
    data_paths, session_factory, monkeypatch,
):
    seed = _seed_frozen_source(data_paths, session_factory, key="deep-reuse-corrupt")
    discovery = _DiscoveryTransport()
    deep = _DeepTransport(seed.source_span_excerpts)
    service = _build_service(data_paths, session_factory, seed)
    source = service.create_from_deconstruction(
        source_job_id=seed.source_job_id, idempotency_key="deep-reuse-corrupt-source",
    )
    runner, _ = _build_runner(data_paths, session_factory, discovery, deep)
    assert runner.run_job(source.job_id)
    calls_before = deep.start_calls
    original = JobStore.get_last_checkpoint

    def without_completed_result(self, job_id, step_id):
        if job_id == source.job_id and step_id == "deep_0001":
            return None
        return original(self, job_id, step_id)

    monkeypatch.setattr(JobStore, "get_last_checkpoint", without_completed_result)
    with pytest.raises(protocol_control_execution_module.ProtocolControlExecutionError) as exc:
        service.create_from_deconstruction(
            source_job_id=seed.source_job_id,
            idempotency_key="deep-reuse-corrupt-current",
            deep_source_job_id=source.job_id,
        )
    assert exc.value.code == "PROTOCOL_CONTROL_DEEP_SOURCE_INVALID"
    assert deep.start_calls == calls_before


def test_deep_source_component_change_refreshes_but_corrupt_identity_rejects(
    data_paths, session_factory, monkeypatch,
):
    seed = _seed_frozen_source(data_paths, session_factory, key="deep-reuse-components")
    service = _build_service(data_paths, session_factory, seed)
    source = service.create_from_deconstruction(
        source_job_id=seed.source_job_id, idempotency_key="deep-components-source",
    )
    runner, _ = _build_runner(
        data_paths, session_factory, _DiscoveryTransport(),
        _DeepTransport(seed.source_span_excerpts),
    )
    assert runner.run_job(source.job_id)
    original = JobStore.get_last_checkpoint

    def changed_component(self, job_id, step_id):
        checkpoint = original(self, job_id, step_id)
        if job_id != source.job_id or step_id != "deep_0001":
            return checkpoint
        assert checkpoint is not None
        checkpoint_id, saved = checkpoint
        saved = dict(saved)
        saved["component_identity"] = dict(saved["component_identity"])
        saved["component_identity"]["wire_schema_sha256"] = "0" * 64
        return checkpoint_id, saved

    monkeypatch.setattr(JobStore, "get_last_checkpoint", changed_component)
    refreshed = service.create_from_deconstruction(
        source_job_id=seed.source_job_id,
        idempotency_key="deep-components-refreshed",
        deep_source_job_id=source.job_id,
    )
    _, payload = _job_snapshot_and_payload(session_factory, refreshed.job_id)
    assert next(
        entry["reason"] for entry in payload["deep_reuse_plan"]["decisions"].values()
        if entry["step_id"] == "deep_0001"
    ) == "component_material_changed"
    assert {entry["reason"] for entry in payload["deep_reuse_plan"]["decisions"].values()} <= {
        "component_material_changed", "same_material_and_current_gate"
    }

    def corrupt_component(self, job_id, step_id):
        checkpoint = changed_component(self, job_id, step_id)
        if job_id == source.job_id and step_id == "deep_0001":
            checkpoint_id, saved = checkpoint
            incomplete = dict(saved["component_identity"])
            incomplete.pop("wire_schema_sha256")
            return checkpoint_id, dict(saved, component_identity=incomplete)
        return checkpoint

    monkeypatch.setattr(JobStore, "get_last_checkpoint", corrupt_component)
    with pytest.raises(protocol_control_execution_module.ProtocolControlExecutionError) as exc:
        service.create_from_deconstruction(
            source_job_id=seed.source_job_id,
            idempotency_key="deep-components-corrupt",
            deep_source_job_id=source.job_id,
        )
    assert exc.value.code == "PROTOCOL_CONTROL_DEEP_SOURCE_INVALID"


def test_process_death_recovers_dynamic_step_from_durable_boundary(
    data_paths,
    session_factory,
):
    seed = _seed_frozen_source(data_paths, session_factory, key="process-recovery")
    discovery = _DiscoveryTransport()
    deep = _DeepTransport(seed.source_span_excerpts, process_death_once=True)
    service = _build_service(
        data_paths,
        session_factory,
        seed,
        max_deep_units_per_batch=256,
    )
    result = service.create_from_deconstruction(
        source_job_id=seed.source_job_id,
        idempotency_key="control-process-recovery",
    )
    runner, _ = _build_runner(data_paths, session_factory, discovery, deep)

    with pytest.raises(ProcessDeath):
        runner.run_job(result.job_id)
    snapshot, _ = _job_snapshot_and_payload(session_factory, result.job_id)
    assert snapshot.state == "running"

    with session_factory() as session, session.begin():
        job = JobStore(session, now=_now).get_job(result.job_id)
        job.lease_expires_at = _DB_NOW - timedelta(seconds=1)
    recovery = recover_expired_jobs(session_factory, now=_now)
    assert result.job_id in recovery.requeued_jobs

    assert runner.run_job(result.job_id)
    snapshot, _ = _job_snapshot_and_payload(session_factory, result.job_id)
    assert snapshot.state == "completed"
    assert deep.start_calls == 2
    assert deep.continue_calls == 0

def test_recovery_requeues_interrupted_dynamic_step_without_replaying_source_or_discovery(
    data_paths,
    session_factory,
):
    """恢复动态深析步骤时只重跑未提交步骤和其后的动态步骤。

    发现批次已经各自持久化 checkpoint；删除结构快照后恢复，证明恢复
    依赖冻结任务 payload/checkpoint，而不是重新读取来源文件。
    """
    seed = _seed_frozen_source(data_paths, session_factory, key="recovery-boundary")
    discovery = _DiscoveryTransport()
    deep = _DeepTransport(seed.source_span_excerpts, process_death_once=True)
    result = _build_service(
        data_paths,
        session_factory,
        seed,
        max_discovery_units_per_batch=2,
        max_deep_units_per_batch=256,
    ).create_from_deconstruction(
        source_job_id=seed.source_job_id,
        idempotency_key="control-recovery-boundary",
    )
    initial_snapshot, payload = _job_snapshot_and_payload(
        session_factory, result.job_id
    )
    discovery_step_ids = tuple(
        entry["step_id"] for entry in payload["discovery_step_ids"]
    )
    assert len(discovery_step_ids) > 1
    assert {step.step_id for step in initial_snapshot.steps} >= set(
        discovery_step_ids
    )

    # The control execution must use the frozen payload/checkpoints after
    # creation; the source structure blob is intentionally unavailable.
    seed.snapshot_path.unlink()
    assert not seed.snapshot_path.exists()
    runner, _ = _build_runner(data_paths, session_factory, discovery, deep)

    with pytest.raises(ProcessDeath):
        runner.run_job(result.job_id)

    interrupted, _ = _job_snapshot_and_payload(session_factory, result.job_id)
    assert interrupted.state == "running"
    discovery_steps = [
        step for step in interrupted.steps if step.step_id in discovery_step_ids
    ]
    assert len(discovery_steps) == len(discovery_step_ids)
    assert all(step.state == "completed" and step.attempt == 1 for step in discovery_steps)
    dynamic_steps = [
        step for step in interrupted.steps if step.step_id.startswith("deep_")
    ]
    assert dynamic_steps
    interrupted_dynamic = next(
        step for step in dynamic_steps if step.state == "running"
    )
    discovery_calls_before_recovery = discovery.start_calls
    assert discovery_calls_before_recovery == len(discovery_step_ids)
    assert deep.start_calls == 1

    with session_factory() as session, session.begin():
        job = JobStore(session, now=_now).get_job(result.job_id)
        job.lease_expires_at = _DB_NOW - timedelta(seconds=1)
    recovery = recover_expired_jobs(session_factory, now=_now)
    assert result.job_id in recovery.requeued_jobs

    queued, _ = _job_snapshot_and_payload(session_factory, result.job_id)
    assert queued.state == "queued"
    queued_dynamic = next(
        step for step in queued.steps if step.step_id == interrupted_dynamic.step_id
    )
    assert queued_dynamic.state == "queued"
    assert queued_dynamic.attempt == interrupted_dynamic.attempt
    assert discovery.start_calls == discovery_calls_before_recovery

    assert runner.run_job(result.job_id)
    completed, _ = _job_snapshot_and_payload(session_factory, result.job_id)
    assert completed.state == "completed"
    assert all(
        step.state == "completed" and step.attempt == 1
        for step in completed.steps
        if step.step_id in discovery_step_ids
    )
    assert discovery.start_calls == discovery_calls_before_recovery
    assert deep.start_calls == 1 + len(dynamic_steps)
    assert all(
        sum(
            event.event.event_type.value == "step_started"
            and event.event.step_id == step_id
            for event in completed.events
        )
        == 1
        for step_id in discovery_step_ids
    )
