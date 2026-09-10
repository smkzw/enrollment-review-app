from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.agents.phase_applicability import (
    PHASE_APPLICABILITY_AGENT_WIRE_VERSION,
    PhaseApplicabilityAgentResponse,
    PhaseApplicabilityAgentRunner,
    build_phase_applicability_agent_input,
)
from app.agents.phase_applicability_transport import (
    MTPLX_PROTOCOL_BATCH_MAX_TOKENS,
    OMLX_PROTOCOL_BATCH_MAX_TOKENS,
    OpenAICompatiblePhaseApplicabilityAgentTransport,
)
from app.domain.contracts.enums import PhaseScope, StudyPhase
from app.domain.contracts.phase_applicability import (
    PhaseApplicabilityDisposition,
)
from app.domain.contracts.protocol_controls import (
    ProtocolSectionCoverageManifest,
    ProtocolStructureUnit,
    StructureUnitKind,
)
from app.protocols.phase_applicability import PHASE_APPLICABILITY_GATE_VERSION
from app.protocols.phase_applicability_planning import plan_phase_applicability_batches
from app.services.phase_applicability_execution import (
    PHASE_APPLICABILITY_EXECUTION_VERSION,
    PhaseApplicabilityExecutionError,
    PhaseApplicabilityExecutionService,
    PhaseApplicabilityExecutionStore,
)


_SHA = "a" * 64


def _unit(unit_id: str, order: int, excerpt: str | None = None) -> ProtocolStructureUnit:
    source_ref = f"body.p{order}"
    return ProtocolStructureUnit(
        structure_unit_id=unit_id,
        source_ref=source_ref,
        member_source_refs=[source_ref],
        source_span_ids=[f"span-{unit_id}"],
        unit_kind=StructureUnitKind.PARAGRAPH,
        heading_path=["5 研究设计", "5.2 期别说明"],
        source_order=order,
        study_phase=StudyPhase.PHASE_II,
        phase_scopes=[PhaseScope.UNKNOWN],
        excerpt=excerpt or f"来源 {unit_id}：本条需要判断研究期别。",
    )


def _manifest(count: int = 3) -> ProtocolSectionCoverageManifest:
    return ProtocolSectionCoverageManifest(
        manifest_id="manifest:live-execution",
        protocol_version_id="protocol:live-execution",
        protocol_document_sha256=_SHA,
        study_phase=StudyPhase.PHASE_II,
        snapshot_id="snapshot:live-execution",
        units=[_unit(f"target-{index}", index) for index in range(count)],
    )


def _wire_text(agent_input, *, invalid: bool = False) -> str:
    if invalid:
        return json.dumps(
            {"wire_version": PHASE_APPLICABILITY_AGENT_WIRE_VERSION, "results": []}
        )
    results = []
    for index, unit in enumerate(agent_input.target_units):
        span_index = agent_input.frozen_package.frozen_source_span_ids.index(
            unit.source_span_ids[0]
        )
        results.append(
            {
                "unit_index": index,
                "structure_unit_id": unit.structure_unit_id,
                "evidence": [
                    {
                        "polarity": "supports",
                        "source_unit_indexes": [index],
                        "source_span_indexes": [span_index],
                        "excerpt": unit.excerpt,
                        "rationale": "原文明确说明该要求适用于本期，直接支持选定期别判断",
                    }
                ],
                "candidates": [
                    {
                        "scope": "phase_ii",
                        "supporting_evidence_indexes": [0],
                        "opposing_evidence_indexes": [],
                        "unresolved_evidence_indexes": [],
                    }
                ],
                "final_disposition": PhaseApplicabilityDisposition.SELECTED_PHASE_APPLICABLE.value,
                "rationale": "原文明确说明该要求适用于本期，直接支持选定期别判断",
            }
        )
    return json.dumps(
        {"wire_version": PHASE_APPLICABILITY_AGENT_WIRE_VERSION, "results": results},
        ensure_ascii=False,
    )


class _QueueTransport:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.start_calls = 0
        self.continue_calls = 0

    def start(self, *, prompt: str) -> PhaseApplicabilityAgentResponse:
        self.start_calls += 1
        return PhaseApplicabilityAgentResponse(
            session_id=f"session-{self.start_calls}",
            text=self.responses.pop(0),
        )

    def continue_session(
        self,
        *,
        session_id: str,
        prompt: str,
    ) -> PhaseApplicabilityAgentResponse:
        self.continue_calls += 1
        return PhaseApplicabilityAgentResponse(
            session_id=session_id,
            text=self.responses.pop(0),
        )


class _InterruptingRepairTransport(_QueueTransport):
    def __init__(self, responses: list[str], *, interrupt: bool = True) -> None:
        super().__init__(responses)
        self.interrupt = interrupt

    def continue_session(
        self,
        *,
        session_id: str,
        prompt: str,
    ) -> PhaseApplicabilityAgentResponse:
        if not self.interrupt:
            return super().continue_session(session_id=session_id, prompt=prompt)
        self.continue_calls += 1
        raise KeyboardInterrupt("模拟修复调用中断")


class _FakeCompletions:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(content=self.responses.pop(0)),
                )
            ]
        )


class _FakeClient:
    def __init__(self, responses: list[str]) -> None:
        self.chat = SimpleNamespace(completions=_FakeCompletions(responses))


def test_real_transport_uses_phase_schema_and_restorable_same_session_history():
    client = _FakeClient(['{"first": 1}', '{"second": 2}'])
    transport = OpenAICompatiblePhaseApplicabilityAgentTransport(
        client=client,
        backend="omlx",
        model="phase-model",
        max_tokens=60000,
    )

    first = transport.start(prompt="冻结输入")
    second = transport.continue_session(session_id=first.session_id, prompt="定向修复")
    calls = client.chat.completions.calls
    assert calls[0]["model"] == "phase-model"
    assert calls[0]["max_tokens"] == 8192
    assert calls[0]["temperature"] == 0.0
    assert calls[0]["response_format"]["json_schema"]["name"] == (
        "phase_applicability_agent_wire_v2"
    )
    assert calls[0]["response_format"]["json_schema"]["strict"] is True
    assert (
        calls[0]["response_format"]["json_schema"]["schema"][
            "additionalProperties"
        ]
        is False
    )
    assert len(calls[1]["messages"]) == 3
    assert second.session_id == first.session_id

    restored_client = _FakeClient(['{"third": 3}'])
    restored = OpenAICompatiblePhaseApplicabilityAgentTransport(
        client=restored_client,
        backend="omlx",
        model="phase-model",
        max_tokens=8192,
    )
    restored.restore_history(
        session_id=first.session_id,
        messages=transport.history(first.session_id),
    )
    resumed = restored.continue_session(
        session_id=first.session_id,
        prompt="重启后继续",
    )
    assert resumed.session_id == first.session_id
    assert len(restored.history(first.session_id)) == 6


def test_mtplx_phase_transport_uses_quality_output_budget() -> None:
    transport = OpenAICompatiblePhaseApplicabilityAgentTransport(
        client=_FakeClient([]),
        backend="mtplx",
        model="mtplx-qwen38-27b-optimized-quality",
        max_tokens=60000,
    )

    assert transport.max_tokens == MTPLX_PROTOCOL_BATCH_MAX_TOKENS
    assert transport.max_tokens > OMLX_PROTOCOL_BATCH_MAX_TOKENS


def test_execution_persists_complete_manifest_plan_and_resumes_only_failed_batches(
    tmp_path: Path,
):
    manifest = _manifest()
    plan = plan_phase_applicability_batches(
        manifest,
        max_owned_units_per_batch=1,
        context_radius=0,
    )
    valid = [
        _wire_text(build_phase_applicability_agent_input(package))
        for package in plan.packages
    ]
    first_transport = _QueueTransport(
        [
            valid[0],
            _wire_text(
                build_phase_applicability_agent_input(plan.packages[1]),
                invalid=True,
            ),
            valid[2],
        ]
    )
    service = PhaseApplicabilityExecutionService(
        PhaseApplicabilityExecutionStore(tmp_path / "runs"),
        runner=PhaseApplicabilityAgentRunner(max_schema_repairs=0),
    )
    partial = service.execute(
        run_id="run-live-1",
        coverage_manifest=manifest,
        plan=plan,
        transport=first_transport,
    )
    assert partial.status == "needs_review"
    assert len(partial.coverage_manifest.units) == 3
    assert len(partial.plan.packages) == 3
    assert [record.status for record in partial.batches] == [
        "accepted",
        "needs_review",
        "accepted",
    ]
    assert partial.unresolved_structure_unit_ids == ("target-1",)
    assert partial.batches[1].raw_output_sha256
    assert (tmp_path / "runs" / "run-live-1.json").is_file()

    persisted_payload = json.loads(
        (tmp_path / "runs" / "run-live-1.json").read_text(encoding="utf-8")
    )
    assert len(persisted_payload["coverage_manifest"]["units"]) == 3
    assert len(persisted_payload["plan"]["packages"]) == 3
    assert persisted_payload["batches"][1]["run_results"][0]["status"] == "需要核对"

    retry_transport = _QueueTransport(
        [valid[1]]
    )
    completed = service.execute(
        run_id="run-live-1",
        coverage_manifest=manifest,
        plan=plan,
        transport=retry_transport,
    )
    assert completed.status == "completed"
    assert retry_transport.start_calls == 1
    assert completed.accepted_structure_unit_ids == (
        "target-0",
        "target-1",
        "target-2",
    )
    assert completed.batches[1].recovery_count == 2
    assert len(completed.batches[1].run_results) == 2


def test_execution_rejects_changed_frozen_input_on_resume(tmp_path: Path):
    manifest = _manifest(1)
    store = PhaseApplicabilityExecutionStore(tmp_path / "run.json")
    service = PhaseApplicabilityExecutionService(store)
    service.prepare(run_id="run-conflict", coverage_manifest=manifest)
    changed = manifest.model_copy(
        update={
            "units": [
                _unit("target-0", 0, excerpt="来源已漂移。重试不得静默覆盖。")
            ]
        },
    )
    with pytest.raises(PhaseApplicabilityExecutionError, match="EXECUTION_INPUT_CONFLICT"):
        service.prepare(run_id="run-conflict", coverage_manifest=changed)


def test_execution_gate_version_is_part_of_resume_identity(tmp_path: Path):
    manifest = _manifest(1)
    path = tmp_path / "run.json"
    service = PhaseApplicabilityExecutionService(
        PhaseApplicabilityExecutionStore(path)
    )
    current = service.prepare(run_id="run-gate-version", coverage_manifest=manifest)
    assert current.gate_version == PHASE_APPLICABILITY_GATE_VERSION

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.pop("gate_version")
    legacy_scope = {
        "execution_version": PHASE_APPLICABILITY_EXECUTION_VERSION,
        "coverage_manifest": payload["coverage_manifest"],
        "plan": payload["plan"],
    }
    payload["input_scope_sha256"] = hashlib.sha256(
        json.dumps(
            legacy_scope,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(PhaseApplicabilityExecutionError, match="EXECUTION_INPUT_CONFLICT"):
        service.prepare(run_id="run-gate-version", coverage_manifest=manifest)


def test_execution_rejects_changed_effective_transport_parameters_on_resume(
    tmp_path: Path,
):
    manifest = _manifest(1)
    plan = plan_phase_applicability_batches(
        manifest,
        max_owned_units_per_batch=1,
        context_radius=0,
    )
    invalid = _wire_text(
        build_phase_applicability_agent_input(plan.packages[0]),
        invalid=True,
    )
    store = PhaseApplicabilityExecutionStore(tmp_path / "runs")
    service = PhaseApplicabilityExecutionService(
        store,
        runner=PhaseApplicabilityAgentRunner(max_schema_repairs=0),
    )
    first_transport = OpenAICompatiblePhaseApplicabilityAgentTransport(
        client=_FakeClient([invalid]),
        backend="omlx",
        model="phase-model",
        max_tokens=8192,
        temperature=0.0,
    )
    partial = service.execute(
        run_id="run-transport-conflict",
        coverage_manifest=manifest,
        plan=plan,
        transport=first_transport,
    )
    assert partial.status == "needs_review"
    assert partial.transport_identity["temperature"] == "0.0"
    assert partial.transport_identity["timeout"] == "600.0"
    assert partial.transport_identity["max_retries"] == "0"
    assert len(partial.transport_identity["response_format_sha256"]) == 64

    changed_transport = OpenAICompatiblePhaseApplicabilityAgentTransport(
        client=_FakeClient([]),
        backend="omlx",
        model="phase-model",
        max_tokens=8192,
        temperature=0.2,
    )
    with pytest.raises(
        PhaseApplicabilityExecutionError,
        match="EXECUTION_TRANSPORT_CONFLICT",
    ):
        service.execute(
            run_id="run-transport-conflict",
            coverage_manifest=manifest,
            plan=plan,
            transport=changed_transport,
        )
    assert changed_transport._client.chat.completions.calls == []


def test_interrupted_repair_checkpoint_preserves_attempt_and_resumes_only_batch(
    tmp_path: Path,
):
    manifest = _manifest(1)
    plan = plan_phase_applicability_batches(
        manifest,
        max_owned_units_per_batch=1,
        context_radius=0,
    )
    package = plan.packages[0]
    valid = _wire_text(build_phase_applicability_agent_input(package))
    invalid = _wire_text(
        build_phase_applicability_agent_input(package),
        invalid=True,
    )
    store = PhaseApplicabilityExecutionStore(tmp_path / "runs")
    service = PhaseApplicabilityExecutionService(
        store,
        runner=PhaseApplicabilityAgentRunner(max_schema_repairs=1),
    )

    with pytest.raises(KeyboardInterrupt, match="模拟修复调用中断"):
        service.execute(
            run_id="run-interrupted-repair",
            coverage_manifest=manifest,
            plan=plan,
            transport=_InterruptingRepairTransport([invalid]),
        )

    interrupted = store.load("run-interrupted-repair")
    interrupted_record = interrupted.batches[0]
    assert interrupted_record.status == "running"
    assert len(interrupted_record.run_results) == 1
    assert interrupted_record.run_results[0].status == "需要核对"
    assert len(interrupted_record.run_results[0].attempts) == 1
    assert interrupted_record.run_results[0].attempts[0].outcome == "schema_invalid"
    first_hash = interrupted_record.run_results[0].attempts[0].raw_output_sha256
    assert interrupted_record.raw_output_sha256 == [first_hash]

    resumed_transport = _InterruptingRepairTransport([valid], interrupt=False)
    resumed = service.execute(
        run_id="run-interrupted-repair",
        coverage_manifest=manifest,
        plan=plan,
        transport=resumed_transport,
    )
    assert resumed.status == "completed"
    assert resumed_transport.start_calls == 1
    assert resumed_transport.continue_calls == 0
    resumed_record = resumed.batches[0]
    assert resumed_record.recovery_count == 2
    assert len(resumed_record.run_results) == 2
    assert resumed_record.run_results[0].attempts[0].raw_output_sha256 == first_hash
    assert resumed_record.run_results[1].attempts[0].outcome == "parsed"
    assert resumed_record.raw_output_sha256 == [
        first_hash,
        resumed_record.run_results[1].attempts[0].raw_output_sha256,
    ]
