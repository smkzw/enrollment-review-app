"""Read-only synthetic regressions for the protocol-control production route.

The route is intentionally tested with opaque, heterogeneous structure units and
fake transports only.  These checks prove that discovery is complete and
lexically neutral, deep analysis is limited to discovered candidates, and
transport/repair/recovery/gate outcomes remain explicit without invoking a live
model or writing a clinical artifact.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.agents.protocol_control_agent_transport import (
    OpenAICompatibleProtocolControlAgentTransport,
    ProtocolControlAgentCallError,
)
from app.agents.protocol_control_deconstructor import (
    CONTROL_AGENT_WIRE_VERSION,
    ProtocolControlAgentResponse,
    ProtocolControlAgentRunner,
    ProtocolControlAgentWire,
    ProtocolControlAgentWireDisposition,
    ProtocolControlAgentWireValidationError,
)
from app.domain.contracts.enums import PhaseScope, StudyPhase
from app.domain.contracts.protocol_controls import (
    ProtocolControlDiscoveryDecision,
    ProtocolControlDiscoveryDisposition,
    ProtocolSectionCoverageManifest,
    ProtocolStructureUnit,
    StructureUnitDispositionKind,
    StructureUnitKind,
    TableCellContext,
)
from app.protocols import protocol_control_planning as planning_module
from app.protocols.protocol_control_planning import (
    plan_protocol_control_deep_batches_from_discovery,
    plan_protocol_control_discovery,
    validate_protocol_control_discovery_results,
)


ROOT = Path(__file__).resolve().parents[3]
_CORPUS_MARKERS = (
    "D001",
    "MG-K10-SAR",
    "银屑病",
    "PASI",
    "PGA",
    "BSA",
    "DLQI",
)


class _ScriptedTransport:
    """Deterministic transport double retaining every logical prompt."""

    def __init__(self, responses: Sequence[object]) -> None:
        self.responses = list(responses)
        self.start_prompts: list[str] = []
        self.continue_prompts: list[str] = []
        self.continue_session_ids: list[str] = []

    def _next(self) -> ProtocolControlAgentResponse:
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        assert isinstance(response, ProtocolControlAgentResponse)
        return response

    def start(self, *, prompt: str) -> ProtocolControlAgentResponse:
        self.start_prompts.append(prompt)
        return self._next()

    def continue_session(
        self,
        *,
        session_id: str,
        prompt: str,
    ) -> ProtocolControlAgentResponse:
        self.continue_session_ids.append(session_id)
        self.continue_prompts.append(prompt)
        response = self._next()
        assert response.session_id == session_id
        return response


def _unit(index: int, kind: StructureUnitKind) -> ProtocolStructureUnit:
    source_ref = f"opaque.body.p{index + 1}"
    table_context = None
    if kind in {
        StructureUnitKind.TABLE_HEADER,
        StructureUnitKind.TABLE_ROW,
        StructureUnitKind.TABLE_NOTE,
    }:
        table_context = TableCellContext(
            table_path=(index, 0),
            row_index=index,
            column_index=0,
            member_cell_paths=[(index, 0)],
            row_headers=[f"row-{index}"],
            column_headers=["opaque-column"],
        )
    return ProtocolStructureUnit(
        structure_unit_id=f"unit-{index:02d}",
        source_ref=source_ref,
        member_source_refs=[source_ref],
        source_span_ids=[f"span:{index:02d}"],
        unit_kind=kind,
        heading_path=["opaque section"],
        table_context=table_context,
        is_footnote_or_note=kind == StructureUnitKind.FOOTNOTE_OR_ANNOTATION,
        source_order=index,
        study_phase=StudyPhase.PHASE_II,
        phase_scopes=[PhaseScope.SHARED],
        excerpt=f"opaque structural payload {index}",
    )


def _manifest() -> ProtocolSectionCoverageManifest:
    kinds = (
        StructureUnitKind.PARAGRAPH,
        StructureUnitKind.LIST_ITEM,
        StructureUnitKind.TABLE_HEADER,
        StructureUnitKind.TABLE_ROW,
        StructureUnitKind.TABLE_NOTE,
        StructureUnitKind.FOOTNOTE_OR_ANNOTATION,
    )
    return ProtocolSectionCoverageManifest(
        manifest_id="manifest:opaque-production",
        protocol_version_id="protocol:opaque-production",
        protocol_document_sha256="c" * 64,
        study_phase=StudyPhase.PHASE_II,
        snapshot_id="snapshot:opaque-production",
        units=[_unit(index, kind) for index, kind in enumerate(kinds)],
    )


def _discovery_decisions(plan) -> list[list[ProtocolControlDiscoveryDecision]]:
    dispositions = (
        ProtocolControlDiscoveryDisposition.CANDIDATE,
        ProtocolControlDiscoveryDisposition.NON_CONTROL,
        ProtocolControlDiscoveryDisposition.UNCERTAIN,
        ProtocolControlDiscoveryDisposition.CONTEXT_ONLY,
        ProtocolControlDiscoveryDisposition.NON_CONTROL,
        ProtocolControlDiscoveryDisposition.CANDIDATE,
    )
    by_id = {
        f"unit-{index:02d}": disposition
        for index, disposition in enumerate(dispositions)
    }
    return [
        [
            ProtocolControlDiscoveryDecision(
                structure_unit_id=unit_id,
                disposition=by_id[unit_id],
                rationale=f"synthetic route: {by_id[unit_id].value}",
            )
            for unit_id in batch.target_structure_unit_ids
        ]
        for batch in plan.batches
    ]


def _deep_fixture():
    manifest = _manifest()
    discovery_plan = plan_protocol_control_discovery(
        manifest,
        max_units_per_batch=2,
        context_radius=1,
    )
    raw_decisions = _discovery_decisions(discovery_plan)
    decisions = validate_protocol_control_discovery_results(
        discovery_plan,
        raw_decisions,
    )
    deep_plan = plan_protocol_control_deep_batches_from_discovery(
        manifest,
        discovery_plan,
        raw_decisions,
        max_owned_units_per_batch=2,
    )
    return manifest, discovery_plan, decisions, deep_plan


def _supporting_wire(batch) -> ProtocolControlAgentWire:
    return ProtocolControlAgentWire(
        wire_version=CONTROL_AGENT_WIRE_VERSION,
        dispositions=[
            ProtocolControlAgentWireDisposition(
                structure_unit_id=unit_id,
                disposition=StructureUnitDispositionKind.SUPPORTING_OR_SUPPLEMENT,
                linked_official_code=None,
                linked_procedure_catalog_item_id=None,
                linked_procedure_catalog_item_ids=[],
                notes="synthetic non-control context",
            )
            for unit_id in batch.owned_structure_unit_ids
        ],
        candidate_drafts=[],
    )


def test_heterogeneous_discovery_is_exactly_once_without_action_vocabulary(
    monkeypatch,
) -> None:
    """Every structure kind is discovered even when action-word lookup is unavailable."""

    def fail_if_called(_text: str) -> tuple[str, ...]:
        raise AssertionError("discovery must not consult the action vocabulary")

    monkeypatch.setattr(
        planning_module,
        "detect_required_action_kinds",
        fail_if_called,
    )
    manifest = _manifest()
    plan = plan_protocol_control_discovery(
        manifest,
        max_units_per_batch=2,
        context_radius=1,
    )

    target_units = [
        unit
        for batch in plan.batches
        for unit in batch.target_units
    ]
    assert [unit.structure_unit_id for unit in target_units] == [
        f"unit-{index:02d}" for index in range(6)
    ]
    assert [unit.unit_kind for unit in target_units] == list(StructureUnitKind)
    assert len(target_units) == len(manifest.units) == len(
        {unit.structure_unit_id for unit in target_units}
    )
    assert plan.manifest_structure_unit_count == len(manifest.units)


def test_protocol_control_chain_has_no_project_specific_branching() -> None:
    """Shared production modules contain no D001/SAR-specific branch markers."""

    patterns = (
        "app/agents/protocol_control*.py",
        "app/domain/contracts/protocol_control*.py",
        "app/protocols/protocol_control*.py",
        "app/services/protocol_control*.py",
        "app/api/v2/protocol*.py",
    )
    paths = sorted(
        {
            path
            for pattern in patterns
            for path in ROOT.glob(pattern)
            if path.is_file()
        }
    )
    assert paths
    for path in paths:
        source = path.read_text(encoding="utf-8").casefold()
        assert not any(marker.casefold() in source for marker in _CORPUS_MARKERS), path


def test_deep_execution_runs_only_discovered_units_once() -> None:
    """Deep prompts are bounded to candidate/uncertain units, not the full manifest."""

    manifest, _discovery_plan, decisions, deep_plan = _deep_fixture()
    assert [decision.structure_unit_id for decision in decisions] == [
        f"unit-{index:02d}" for index in range(6)
    ]
    assert deep_plan.deep_structure_unit_ids == (
        "unit-00",
        "unit-02",
        "unit-05",
    )
    assert deep_plan.non_deep_structure_unit_ids == (
        "unit-01",
        "unit-03",
        "unit-04",
    )

    transport = _ScriptedTransport(
        [
            ProtocolControlAgentResponse(
                session_id=f"deep-session-{index}",
                text=_supporting_wire(batch).model_dump_json(),
            )
            for index, batch in enumerate(deep_plan.batches)
        ]
    )
    runner = ProtocolControlAgentRunner(max_transport_retries=0)
    results = [runner.run(batch, transport) for batch in deep_plan.batches]

    assert len(manifest.units) == 6
    assert len(deep_plan.batches) == 2
    assert len(transport.start_prompts) == len(deep_plan.batches)
    assert all(result.status == "已解析" for result in results)
    prompts = "\n".join(transport.start_prompts)
    for unit_id in deep_plan.deep_structure_unit_ids:
        assert unit_id in prompts
    for unit_id in deep_plan.non_deep_structure_unit_ids:
        assert unit_id not in prompts


def test_uncertain_transport_failure_is_visible_without_fallback() -> None:
    """An uncertain request is not retried or silently routed to another model."""

    _manifest_value, _discovery_plan, _decisions, deep_plan = _deep_fixture()
    transport = _ScriptedTransport(
        [
            ProtocolControlAgentCallError(
                "session:uncertain",
                "synthetic transport outage",
                uncertain_completion=True,
            )
        ]
    )
    result = ProtocolControlAgentRunner(max_transport_retries=3).run(
        deep_plan.batches[0],
        transport,
    )

    assert result.status == "需要核对"
    assert len(result.attempts) == 1
    assert result.attempts[0].outcome == "transport_failed"
    assert len(transport.start_prompts) == 1
    assert transport.continue_prompts == []
    assert transport.responses == []


def test_gate_rejection_repairs_in_same_session_and_recovers() -> None:
    """A deterministic gate rejection gets one bounded same-session repair."""

    _manifest_value, _discovery_plan, _decisions, deep_plan = _deep_fixture()
    batch = deep_plan.batches[0]
    wire_text = _supporting_wire(batch).model_dump_json()
    transport = _ScriptedTransport(
        [
            ProtocolControlAgentResponse(session_id="session:gate", text=wire_text),
            ProtocolControlAgentResponse(session_id="session:gate", text=wire_text),
        ]
    )
    gate_calls: list[str] = []

    def gate(output) -> None:
        gate_calls.append(output.batch_id)
        if len(gate_calls) == 1:
            raise ProtocolControlAgentWireValidationError(
                "SYNTHETIC_GATE_REJECTED",
                "synthetic publication gate rejection",
                structure_unit_ids=batch.owned_structure_unit_ids,
            )

    result = ProtocolControlAgentRunner(max_transport_retries=0).run(
        batch,
        transport,
        output_validator=gate,
    )

    assert result.status == "已解析"
    assert [attempt.outcome for attempt in result.attempts] == [
        "publication_invalid",
        "parsed",
    ]
    assert gate_calls == [batch.batch_id, batch.batch_id]
    assert len(transport.start_prompts) == 1
    assert len(transport.continue_prompts) == 1
    assert transport.continue_session_ids == ["session:gate"]
    assert "SYNTHETIC_GATE_REJECTED" in transport.continue_prompts[0]


class _FakeCompletions:
    def __init__(self, outputs: Sequence[str]) -> None:
        self.outputs = iter(outputs)
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(content=next(self.outputs)),
                )
            ]
        )


def _transport_with_fake_outputs(outputs: Sequence[str]):
    completions = _FakeCompletions(outputs)
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions),
    )
    transport = OpenAICompatibleProtocolControlAgentTransport(
        client=client,
        backend="mtplx",
        model="opaque-control-model",
        max_tokens=8192,
    )
    return transport, completions


def test_persisted_history_restores_and_continues_same_session() -> None:
    """A restart resumes the logical session instead of starting a new one."""

    first, first_completions = _transport_with_fake_outputs(['{"first":true}'])
    response = first.start(prompt="synthetic frozen control input")
    persisted_history = first.history(response.session_id)

    restored, restored_completions = _transport_with_fake_outputs(
        ['{"recovered":true}']
    )
    restored.restore_history(
        session_id=response.session_id,
        messages=persisted_history,
    )
    resumed = restored.continue_session(
        session_id=response.session_id,
        prompt="synthetic recovery repair",
    )

    assert len(first_completions.calls) == 1
    assert resumed.session_id == response.session_id
    assert resumed.text == '{"recovered":true}'
    assert restored_completions.calls[0]["messages"] == [
        *persisted_history,
        {"role": "user", "content": "synthetic recovery repair"},
    ]
    assert restored.history(response.session_id) == (
        *persisted_history,
        {"role": "user", "content": "synthetic recovery repair"},
        {"role": "assistant", "content": '{"recovered":true}'},
    )


@pytest.mark.parametrize(
    "disposition",
    [
        ProtocolControlDiscoveryDisposition.CANDIDATE,
        ProtocolControlDiscoveryDisposition.UNCERTAIN,
        ProtocolControlDiscoveryDisposition.CONTEXT_ONLY,
        ProtocolControlDiscoveryDisposition.NON_CONTROL,
    ],
)
def test_discovery_dispositions_are_provider_neutral(disposition) -> None:
    """The four routing outcomes remain stable for arbitrary synthetic text."""

    manifest = _manifest()
    plan = plan_protocol_control_discovery(manifest, max_units_per_batch=6)
    decisions = [
        [
            ProtocolControlDiscoveryDecision(
                structure_unit_id=unit_id,
                disposition=disposition,
                rationale="opaque synthetic rationale",
            )
            for unit_id in plan.batches[0].target_structure_unit_ids
        ]
    ]
    closed = validate_protocol_control_discovery_results(plan, decisions)
    assert len(closed) == len(manifest.units)
    assert all(item.disposition == disposition for item in closed)
