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
    ProtocolControlAgentRunResult,
    ProtocolControlAgentResponse,
    ProtocolControlAgentWireValidationError,
    ProtocolControlDiscoveryAgentResponse,
)
from app.agents.protocol_control_source_interpretation import SOURCE_INTERPRETATION_VERSION
from app.domain.contracts.enums import Comparator, PhaseScope, ReviewStage, StudyPhase
from app.domain.contracts.protocol_controls import (
    ControlObligationKind,
    ProtocolControlDiscoveryDisposition,
    ReviewNodeRole,
    ProtocolStructureUnit,
    StructureUnitDispositionKind,
    TableCellContext,
)
from app.domain.contracts.rules import WorkflowStage
from app.protocols.deconstruction_service import ProtocolDeconstructionInputAssembler
from app.protocols.docx_structure import StructureExtraction, serialize_blocks
from app.protocols.protocol_control_gate import ProtocolControlGateError, _check_evaluation_numeric_sources
from app.services import protocol_control_execution as protocol_control_execution_module
from app.services.job_service import JobService, StepSpec
from app.services.protocol_control_execution import (
    CANDIDATE_CONTROL_PACKAGE_RESULT_KIND,
    FORMAL_CATALOG_STATUS_NOT_MATERIALIZED,
    PROTOCOL_CONTROL_EXECUTION_JOB_TYPE,
    ProtocolControlExecutionError,
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
from tests.v2.domain.test_control_catalog_restricted_contract import _unresolved_batch_review
from tests.v2.protocols.test_slice58c_control_deconstructor import _candidate, _wire, _evaluation, _FakeTransport


def test_old_table_row_requires_new_source_alignment_before_deep_review(monkeypatch) -> None:
    row = ProtocolStructureUnit(
        structure_unit_id="row-generic", source_ref="body.t0.r1",
        member_source_refs=["body.t0.r1.c0.p0", "body.t0.r1.c1.p0"],
        source_span_ids=["span:0", "span:1"], unit_kind="table_row",
        heading_path=["访视安排"], source_order=1,
        study_phase=StudyPhase.PHASE_II, phase_scopes=[PhaseScope.SHARED],
        excerpt="检查 | X",
        table_context=TableCellContext(
            table_path=(1, 0), row_index=1, column_index=0,
            member_cell_paths=[(1, 0), (1, 1)],
        ),
    )
    with pytest.raises(ValueError, match="须从原方案重建来源清单"):
        protocol_control_execution_module._require_schedule_member_sources([row])
    batch = SimpleNamespace(batch_id="batch-a", owned_units=[row], context_units=[])
    module = protocol_control_execution_module
    monkeypatch.setattr(module, "_closure_checkpoint", lambda *_: {"deep_plan": {}})
    monkeypatch.setattr(module.ProtocolControlDiscoveryToDeepPlan, "model_validate",
                        staticmethod(lambda _: SimpleNamespace(batches=[batch])))
    monkeypatch.setattr(module, "_deep_batch_for_step", lambda *_: batch)
    context = StepContext(
        job_id="job-a", job_type=PROTOCOL_CONTROL_EXECUTION_JOB_TYPE,
        job_payload={}, step_id="deep_0001", name="深审", attempt=1,
        last_checkpoint_id=None, last_checkpoint=None,
    )
    with pytest.raises(StepFailure) as error:
        module._execute_deep(context, SimpleNamespace())
    assert error.value.error_code == "PROTOCOL_CONTROL_TABLE_SOURCE_INVALID"
    row.member_texts = ["检查", "X"]
    protocol_control_execution_module._require_schedule_member_sources([row])
    row.excerpt = "检查 | X | 无来源补充"
    with pytest.raises(ValueError, match="展示文字与逐项来源原文不一致"):
        protocol_control_execution_module._require_schedule_member_sources([row])


def test_atomized_table_paragraph_is_checked_before_deep_review() -> None:
    unit = ProtocolStructureUnit(
        structure_unit_id="paragraph-1", source_ref="body.t0.r1.c0.p1",
        member_source_refs=["body.t0.r1.c0.p1"], member_texts=["完成检查"],
        source_span_ids=["span:1"], unit_kind="table_row",
        heading_path=["访视安排"], source_order=1,
        study_phase=StudyPhase.PHASE_II, phase_scopes=[PhaseScope.SHARED],
        excerpt="完成检查",
        table_context=TableCellContext(
            table_path=(1, 0), row_index=1, column_index=0,
            member_cell_paths=[(1, 0)],
        ),
    )
    protocol_control_execution_module._require_schedule_member_sources([unit])
    unit.excerpt = "完成检查 | 未核原文"
    with pytest.raises(ValueError, match="展示文字与逐项来源原文不一致"):
        protocol_control_execution_module._require_schedule_member_sources([unit])
    unit.excerpt = "完成检查"
    unit.member_source_refs = ["body.t0.r1.c2.p1"]
    with pytest.raises(ValueError, match="冻结单元格位置"):
        protocol_control_execution_module._require_schedule_member_sources([unit])


def test_pending_cross_chapter_result_survives_checkpoint_contract() -> None:
    payload = {
        "status": "待跨章核验",
        "batch_id": "batch-a",
        "session_id": "session-a",
        "attempts": [{
            "attempt": 1, "session_id": "session-a",
            "raw_output_sha256": "a" * 64, "outcome": "parsed",
        }],
    }
    saved = ProtocolControlAgentRunResult.model_validate(payload).model_dump(mode="json")
    assert ProtocolControlAgentRunResult.model_validate(saved).status == "待跨章核验"
    with pytest.raises(ValueError):
        ProtocolControlAgentRunResult.model_validate({**payload, "status": "已发布"})


def test_deep_step_preserves_pending_cross_chapter_for_final_relation_check(monkeypatch) -> None:
    module = protocol_control_execution_module
    batch = SimpleNamespace(batch_id="batch-a", owned_units=[], context_units=[])
    monkeypatch.setattr(module, "_closure_checkpoint", lambda *_: {"deep_plan": {}})
    monkeypatch.setattr(module.ProtocolControlDiscoveryToDeepPlan, "model_validate",
                        staticmethod(lambda _: SimpleNamespace(batches=[batch])))
    monkeypatch.setattr(module, "_deep_batch_for_step", lambda *_: batch)
    monkeypatch.setattr(module, "_prompt_from_payload", lambda *_: "冻结提示")
    monkeypatch.setattr(module, "_limits_from_payload", lambda *_: (1, 2))
    monkeypatch.setattr(module, "_resolve_transport", lambda *_ , **__: SimpleNamespace(
        start_source_interpretation=lambda **_: None,
        take_call_receipts=lambda: [{"request_id": "request-1", "usage": None}],
    ))
    monkeypatch.setattr(module, "_require_frozen_route", lambda *_ , **__: None)
    monkeypatch.setattr(module, "_deep_component_identity", lambda *_: {})
    monkeypatch.setattr(module, "_transport_identity", lambda *_ , **__: {})
    result = SimpleNamespace(
        status="待跨章核验", final_output=SimpleNamespace(model_dump=lambda **_: {}),
        attempts=[],
        model_dump=lambda **_: {"status": "待跨章核验", "batch_id": "batch-a"},
    )
    monkeypatch.setattr(module.ProtocolControlAgentRunner, "run", lambda *_ , **__: result)
    context = StepContext(
        job_id="job-a", job_type=PROTOCOL_CONTROL_EXECUTION_JOB_TYPE,
        job_payload={}, step_id="deep_0001", name="深审", attempt=1,
        last_checkpoint_id=None, last_checkpoint=None,
    )
    config = SimpleNamespace()
    checkpoint = module._execute_deep(context, config)
    assert checkpoint["stage"] == "deep"
    assert checkpoint["run_result"]["status"] == "待跨章核验"
    assert checkpoint["model_call_receipts"] == [{"request_id": "request-1", "usage": None}]


def _independent_candidate_and_unresolved_review():
    batch, result = _unresolved_batch_review()
    result.source_interpretation.statements[0].unresolved = []
    result.source_target_review.items = result.source_target_review.items[1:]
    result.partial_wire = _wire(candidate=_candidate())
    result.partial_wire.candidate_drafts[0].obligation_expression.groups[0].atoms[0].statement = "年龄至少18岁"
    result.partial_wire.candidate_drafts[0].exception_expression = None
    result.source_statement_coverage = protocol_control_execution_module.source_statement_coverage(
        batch, result.source_interpretation, result.partial_wire,
    )
    assert result.source_statement_coverage[0].status == "expressed"
    return batch, result


@pytest.mark.parametrize("code, message", [
    ("SOURCE_TARGET_REVIEW_UNRESOLVED", "对应关系仍需核清"),
    ("SOURCE_REQUIREMENT_CONSUMER_UNAVAILABLE", "尚缺可靠的装配核验能力"),
    ("SOURCE_REQUIREMENT_INSERTION_LIMIT_REACHED", "本次限定修订次数内"),
    ("SOURCE_CANDIDATE_SEMANTICS_UNVERIFIED", "忠实表达了原文含义"),
])
def test_deep_failure_keeps_reason_and_partial_source_without_false_adoption(monkeypatch, code, message):
    module = protocol_control_execution_module
    batch, result = _independent_candidate_and_unresolved_review()
    # Target matching uncertainty is not evidence that the source is ambiguous.
    result.source_interpretation.statements[1].unresolved = []
    result.attempts[-1].error_classes = [code]
    result.attempts[-1].error_detail = {
        "code": code, "statement_ids": [1], "source_refs": ["span:02"],
    }
    assert module.restricted_batch_from_review(batch, result) is None
    monkeypatch.setattr(module, "_closure_checkpoint", lambda *_: {"deep_plan": {}})
    monkeypatch.setattr(module.ProtocolControlDiscoveryToDeepPlan, "model_validate",
                        staticmethod(lambda _: SimpleNamespace(batches=[batch])))
    monkeypatch.setattr(module, "_deep_batch_for_step", lambda *_: batch)
    monkeypatch.setattr(module, "_frozen_official_predicates", lambda *_: ({}, {}))
    monkeypatch.setattr(module, "_prompt_from_payload", lambda *_: "冻结提示")
    monkeypatch.setattr(module, "_limits_from_payload", lambda *_: (1, 2))
    monkeypatch.setattr(module, "_resolve_transport", lambda *_, **__: SimpleNamespace(
        start_source_interpretation=lambda **_: None,
    ))
    monkeypatch.setattr(module, "_require_frozen_route", lambda *_, **__: None)
    monkeypatch.setattr(module, "_deep_component_identity", lambda *_: {})
    monkeypatch.setattr(module, "_transport_identity", lambda *_, **__: {})
    monkeypatch.setattr(module.ProtocolControlAgentRunner, "run", lambda *_, **__: result)
    context = StepContext(
        job_id="job-a", job_type=PROTOCOL_CONTROL_EXECUTION_JOB_TYPE,
        job_payload={}, step_id="deep_0001", name="深审", attempt=1,
        last_checkpoint_id=None, last_checkpoint=None,
    )
    with pytest.raises(StepFailure) as caught:
        module._execute_deep(context, SimpleNamespace())
    failure = caught.value
    assert failure.error_code == "PROTOCOL_CONTROL_" + code
    assert failure.retryable is False
    assert message in failure.detail
    restored = ProtocolControlAgentRunResult.model_validate({
        "status": "需要核对", "batch_id": batch.batch_id, "session_id": result.session_id,
        "source_interpretation": failure.diagnostic_checkpoint["source_interpretation"],
        "source_statement_coverage": failure.diagnostic_checkpoint["source_statement_coverage"],
        "source_target_review": failure.diagnostic_checkpoint["source_target_review"],
        "partial_wire": failure.diagnostic_checkpoint["partial_wire"],
        "attempts": result.model_dump(mode="json")["attempts"],
    })
    assert restored.partial_wire == result.partial_wire
    assert restored.source_target_review == result.source_target_review
    assert failure.diagnostic_checkpoint["attempts"][-1]["error_detail"]["code"] == code
    assert failure.diagnostic_checkpoint["failure_reason_version"] == module.SOURCE_REQUIREMENT_FAILURE_REASON_VERSION
    assert module.restricted_batch_from_review(batch, restored) is None


def test_failure_reason_reporting_does_not_invalidate_author_or_repair_material(monkeypatch):
    import app.agents.protocol_control_deconstructor as agent

    prompt = agent.DEFAULT_PROTOCOL_CONTROL_AGENT_PROMPT_TEMPLATE
    author_before = agent.protocol_control_agent_prompt_template_sha256(prompt)
    repair_before = agent.protocol_control_agent_repair_contract_sha256()
    monkeypatch.setattr(agent, "SOURCE_REQUIREMENT_FAILURE_REASON_VERSION", "test/reporting-only")
    assert agent.protocol_control_agent_prompt_template_sha256(prompt) == author_before
    assert agent.protocol_control_agent_repair_contract_sha256() == repair_before


def test_unresolved_sibling_retention_versions_recovery_not_author_material(monkeypatch):
    import app.agents.protocol_control_deconstructor as agent

    prompt = agent.DEFAULT_PROTOCOL_CONTROL_AGENT_PROMPT_TEMPLATE
    author = agent.protocol_control_agent_prompt_template_sha256(prompt)
    current = agent.protocol_control_agent_repair_contract_sha256()
    monkeypatch.setattr(agent, "SOURCE_REQUIREMENT_FAILURE_POLICY_VERSION", "phase5/source-requirement-failure-policy/v3")
    assert agent.protocol_control_agent_prompt_template_sha256(prompt) == author
    assert agent.protocol_control_agent_repair_contract_sha256() != current


def _independent_candidate_and_clock_capability():
    batch, result = _independent_candidate_and_unresolved_review()
    quote = "给药前90分钟内采集样本"
    batch.owned_units[1].excerpt = quote
    source = result.source_interpretation.statements[1]
    source.quoted_text = quote
    source.time_words = ["90分钟"]
    source.unresolved = []
    clock = _candidate().model_dump(mode="json")
    clock.update(title="采样时间核对", applicability_expression=None,
                 exception_expression=None, source_structure_unit_ids=["su-02"],
                 source_span_ids=["span:02"])
    atom = clock["obligation_expression"]["groups"][0]["atoms"][0]
    atom.update(kind="complete_or_verify", statement=quote,
                evaluation=_evaluation(quote, "span:02", quote),
                source_span_ids=["span:02"], source_excerpts=[quote])
    evidence = clock["minimum_evidence"][0]
    evidence.update(fact_type="procedure", description="核对采样记录")
    evidence["source_policy"].update(source_span_ids=["span:02"], source_excerpts=[quote])
    wire = result.partial_wire.model_copy(deep=True)
    wire.candidate_drafts.append(type(wire.candidate_drafts[0]).model_validate(clock))
    wire.dispositions[1].disposition = StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE
    result.capability_wire = wire
    result.partial_wire = None
    result.source_target_review = None
    result.source_statement_coverage = protocol_control_execution_module.source_statement_coverage(
        batch, result.source_interpretation, wire,
    )
    result.attempts[-1].error_classes = ["TIME_PRECISION_UNSUPPORTED"]
    return batch, result


_SAME_UNIT_INDEPENDENT = "年龄至少18岁"
_SAME_UNIT_RESTRICTED = "给药前90分钟内完成首次给药"


def _same_unit_two_requirement_review(*, swap: bool = False):
    """One frozen unit holding an executable requirement beside an exact restriction."""

    batch, result = _independent_candidate_and_unresolved_review()
    unit = batch.owned_units[0]
    separator = "；\n" if swap else "；"
    first, second = (
        (_SAME_UNIT_RESTRICTED, _SAME_UNIT_INDEPENDENT) if swap
        else (_SAME_UNIT_INDEPENDENT, _SAME_UNIT_RESTRICTED)
    )
    unit.excerpt = f"{first}{separator}{second}"
    interpretation = result.source_interpretation
    interpretation.statements[1].structure_unit_id = unit.structure_unit_id
    interpretation.statements[1].quoted_text = _SAME_UNIT_RESTRICTED
    interpretation.statements[1].time_words = ["90分钟"]
    interpretation.units_without_statement = ["su-02"]
    result.source_target_review.items[0].source_action_excerpt = _SAME_UNIT_RESTRICTED
    result.source_statement_coverage = protocol_control_execution_module.source_statement_coverage(
        batch, interpretation, result.partial_wire,
    )
    return batch, result


def _independent_candidate_and_temporal_gap(*, same_unit: bool = False):
    batch, result = (_same_unit_two_requirement_review() if same_unit
                     else _independent_candidate_and_unresolved_review())
    quote = "拟参加者须持续接受治疗7天"
    source = result.source_interpretation.statements[1]
    unit = next(item for item in batch.owned_units
                if item.structure_unit_id == source.structure_unit_id)
    unit.excerpt = (_SAME_UNIT_INDEPENDENT + "；" + quote if same_unit else quote)
    source.quoted_text = quote
    source.time_words = ["7天"]
    source.unresolved = []
    review = result.source_target_review.items[0]
    review.decision = "additional_requirement"
    review.source_action_excerpt = quote
    review.unresolved_aspects = ["本条时间要求尚未进入可用控制"]
    result.source_statement_coverage = protocol_control_execution_module.source_statement_coverage(
        batch, result.source_interpretation, result.partial_wire,
    )
    attempt = result.attempts[-1]
    attempt.error_classes = ["TEMPORAL_SCOPE_UNRESOLVED"]
    attempt.error_detail = {
        "code": "TEMPORAL_SCOPE_UNRESOLVED", "statement_ids": [1],
        "json_path": "/items", "source_refs": sorted(unit.source_span_ids),
        "retry_class": "temporal_scope_review", "affected_dependents": [1],
    }
    return batch, result


@pytest.mark.parametrize("same_unit", [False, True])
@pytest.mark.parametrize("saved_review", [False, True])
def test_actual_temporal_runner_keeps_independent_requirement_without_transport_failure(
    same_unit: bool, saved_review: bool,
) -> None:
    from app.agents.protocol_control_deconstructor import ProtocolControlAgentRunner
    from app.services.eligibility_review_projection import _restricted_control_projections
    from tests.v2.domain.test_control_catalog_restricted_contract import _catalog, _publication

    batch, fixture = _independent_candidate_and_temporal_gap(same_unit=same_unit)

    class TemporalTransport(_FakeTransport):
        review_calls = 0

        def start_source_target_review(self, *, prompt):
            assert not saved_review, "有效保存核对不得重新读取"
            self.review_calls += 1
            return ProtocolControlAgentResponse(
                session_id="temporal-review", text=fixture.source_target_review.model_dump_json(),
            )

        def start_source_insert(self, **_):
            pytest.fail("持续期要求不得伪装为单访视操作补入")

    transport = TemporalTransport([])
    result = ProtocolControlAgentRunner().run(
        batch, transport, resume_wire=fixture.partial_wire,
        resume_source_interpretation=fixture.source_interpretation,
        resume_session_id="temporal-wire",
        resume_source_target_review=fixture.source_target_review if saved_review else None,
        resume_source_statement_coverage=fixture.source_statement_coverage if saved_review else (),
        output_validator=lambda output: protocol_control_execution_module._validate_deep_batch_output(batch, output),
    )
    assert result.status == "需要核对"
    assert result.final_output is None
    assert result.attempts[-1].outcome == "publication_invalid"
    assert result.attempts[-1].error_classes == ["TEMPORAL_SCOPE_UNRESOLVED"]
    if saved_review:
        assert result.attempts[-1].raw_output_text is None
    else:
        assert result.attempts[-1].raw_output_text
    assert transport.review_calls == int(not saved_review)
    saved = ProtocolControlAgentRunResult.model_validate(result.model_dump(mode="json"))
    restricted = protocol_control_execution_module.restricted_batch_from_review(batch, saved)
    assert restricted is not None
    assert restricted.candidates == protocol_control_execution_module.hydrate_protocol_control_agent_output(
        fixture.partial_wire, batch,
    ).candidates
    statement = restricted.restricted_statements[0]
    assert statement.limitation_kind == "consumer_unavailable"
    assert statement.source_quote == fixture.source_interpretation.statements[1].quoted_text
    assert (statement.independent_scope_proof is not None) == same_unit
    protocol_control_execution_module._validate_deep_batch_output(batch, restricted)
    projected = _restricted_control_projections(_publication(_catalog(
        restricted=tuple(restricted.restricted_statements),
        allowed=tuple(batch.owned_source_span_ids),
    )))[0]
    assert projected.obligations[0].status == "restricted"
    assert "尚未完成" in projected.obligations[0].reason
    assert projected.obligations[0].fact_refs == ()


@pytest.mark.parametrize("failure", [
    "missing_detail", "wrong_code", "wrong_scope", "wrong_source", "wrong_dependents",
    "bool_index", "extra_index", "extra_error", "transport", "non_temporal",
    "unresolved_semantics", "definition", "recommended", "shared_scope", "overlap",
    "unreported_prefix", "candidate_cites_restriction", "changed_sibling_value",
])
def test_temporal_restriction_does_not_approve_unproven_error_ranges(failure: str) -> None:
    batch, result = _independent_candidate_and_temporal_gap(same_unit=True)
    source = result.source_interpretation.statements[1]
    attempt = result.attempts[-1]
    if failure == "missing_detail":
        attempt.error_detail = None
    elif failure == "wrong_code":
        attempt.error_detail["code"] = "SOURCE_TARGET_REVIEW_UNRESOLVED"
    elif failure == "wrong_scope":
        attempt.error_detail["statement_ids"] = [0]
    elif failure == "wrong_source":
        attempt.error_detail["source_refs"] = ["span:02"]
    elif failure == "wrong_dependents":
        attempt.error_detail["affected_dependents"] = []
    elif failure == "bool_index":
        attempt.error_detail["statement_ids"] = [True]
    elif failure == "extra_index":
        attempt.error_detail["statement_ids"] = [0, 1]
        attempt.error_detail["affected_dependents"] = [0, 1]
    elif failure == "extra_error":
        attempt.error_classes.append("POST_HYDRATION_INVALID")
    elif failure == "transport":
        attempt.outcome = "transport_failed"
    elif failure == "non_temporal":
        quote = "拟参加者须完成核查记录"
        batch.owned_units[0].excerpt = _SAME_UNIT_INDEPENDENT + "；" + quote
        source.quoted_text = quote
        source.time_words = []
        result.source_target_review.items[0].source_action_excerpt = quote
    elif failure == "unresolved_semantics":
        source.unresolved = ["适用对象不明确"]
    elif failure == "definition":
        source.decision_functions = ["action", "definition"]
    elif failure == "recommended":
        source.force = "recommended"
    elif failure == "shared_scope":
        batch.owned_units[0].excerpt = "符合下述条件者：" + batch.owned_units[0].excerpt
        source.scope_quote = "符合下述条件者"
    elif failure == "unreported_prefix":
        batch.owned_units[0].excerpt = "仅用于已符合资格者：" + batch.owned_units[0].excerpt
    elif failure == "candidate_cites_restriction":
        atom = result.partial_wire.candidate_drafts[0].obligation_expression.groups[0].atoms[0]
        atom.source_excerpts = [batch.owned_units[0].excerpt]
    elif failure == "changed_sibling_value":
        atom = result.partial_wire.candidate_drafts[0].obligation_expression.groups[0].atoms[0]
        atom.evaluation.predicate.value = 19
    elif failure == "overlap":
        source.quoted_text = batch.owned_units[0].excerpt
        result.source_target_review.items[0].source_action_excerpt = source.quoted_text
    result.source_statement_coverage = protocol_control_execution_module.source_statement_coverage(
        batch, result.source_interpretation, result.partial_wire,
    )
    assert protocol_control_execution_module.restricted_batch_from_review(batch, result) is None


def test_same_unit_independent_requirement_keeps_source_proven_candidate() -> None:
    batch, result = _same_unit_two_requirement_review()
    assert result.source_statement_coverage[0].status == "expressed"
    output = protocol_control_execution_module.restricted_batch_from_review(batch, result)
    assert output is not None
    assert [item.disposition for item in output.dispositions] == [
        StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE,
        StructureUnitDispositionKind.SUPPORTING_OR_SUPPLEMENT,
    ]
    assert len(output.candidates) == 1
    assert [item.source_structure_unit_id for item in output.restricted_statements] == ["su-01"]
    statement = output.restricted_statements[0]
    assert statement.source_quote == _SAME_UNIT_RESTRICTED
    assert statement.time_words == ["90分钟"]
    assert statement.independent_scope_proof is not None
    proof = statement.independent_scope_proof
    excerpt = batch.owned_units[0].excerpt
    assert excerpt[proof.restricted_source_start:proof.restricted_source_end] == (
        _SAME_UNIT_RESTRICTED
    )
    entry = proof.independent_excerpts[0]
    assert entry.source_quote == _SAME_UNIT_INDEPENDENT
    assert excerpt[entry.source_start:entry.source_end] == _SAME_UNIT_INDEPENDENT
    assert entry.candidate_control_ids == [
        output.candidates[0].control_candidate_id
    ]
    protocol_control_execution_module._validate_deep_batch_output(batch, output)

    reloaded = type(output).model_validate(output.model_dump(mode="json"))
    assert reloaded == output
    assert reloaded.model_dump(mode="json") == output.model_dump(mode="json")
    protocol_control_execution_module._validate_deep_batch_output(batch, reloaded)


def test_same_unit_proof_holds_for_a_semantics_preserving_arrangement() -> None:
    batch, result = _same_unit_two_requirement_review(swap=True)
    output = protocol_control_execution_module.restricted_batch_from_review(batch, result)
    assert output is not None
    proof = output.restricted_statements[0].independent_scope_proof
    assert proof is not None
    excerpt = batch.owned_units[0].excerpt
    assert excerpt.count(_SAME_UNIT_INDEPENDENT) == 1
    entry = proof.independent_excerpts[0]
    assert excerpt[entry.source_start:entry.source_end] == _SAME_UNIT_INDEPENDENT
    assert entry.source_start > proof.restricted_source_start
    protocol_control_execution_module._validate_deep_batch_output(batch, output)


def test_same_unit_restriction_stays_whole_without_an_independent_proof() -> None:
    # 受限陈述覆盖了整个单元：独立区间与受限区间重叠，同一个语义点不得同时可执行与受限。
    batch, result = _same_unit_two_requirement_review()
    unit = batch.owned_units[0]
    result.source_interpretation.statements[1].quoted_text = unit.excerpt
    result.source_target_review.items[0].source_action_excerpt = unit.excerpt
    result.source_statement_coverage = protocol_control_execution_module.source_statement_coverage(
        batch, result.source_interpretation, result.partial_wire,
    )
    assert result.source_statement_coverage[1].status != "expressed"
    assert protocol_control_execution_module.restricted_batch_from_review(batch, result) is None


def test_whole_unit_restriction_reads_back_without_projection_fields() -> None:
    batch, result = _unresolved_batch_review()
    output = protocol_control_execution_module.restricted_batch_from_review(batch, result)
    assert output is not None
    dumped = output.model_dump(mode="json")
    assert all(
        "independent_scope_proof" not in item
        for item in dumped["restricted_statements"]
    )
    assert type(output).model_validate(dumped).model_dump(mode="json") == dumped
    protocol_control_execution_module._validate_deep_batch_output(batch, output)


def test_same_unit_shared_scope_cannot_be_proved_by_disjoint_actions() -> None:
    batch, result = _same_unit_two_requirement_review()
    batch.owned_units[0].excerpt = "符合下述条件者：" + batch.owned_units[0].excerpt
    result.source_interpretation.statements[1].scope_quote = "符合下述条件者"
    assert protocol_control_execution_module.restricted_batch_from_review(batch, result) is None


@pytest.mark.parametrize("position", ["before", "between", "after"])
def test_same_unit_independence_cannot_omit_source_words(position: str) -> None:
    batch, result = _same_unit_two_requirement_review()
    extra = "仅用于已符合资格者"
    if position == "before":
        batch.owned_units[0].excerpt = extra + "：" + batch.owned_units[0].excerpt
    elif position == "between":
        batch.owned_units[0].excerpt = (
            _SAME_UNIT_INDEPENDENT + "；" + extra + "：" + _SAME_UNIT_RESTRICTED
        )
    else:
        batch.owned_units[0].excerpt += "；" + extra
    assert protocol_control_execution_module.restricted_batch_from_review(batch, result) is None


@pytest.mark.parametrize("function", ["definition", "threshold", "calculation_input", "unclassified"])
def test_same_unit_source_function_cannot_be_promoted_by_literal_separation(function: str) -> None:
    batch, result = _same_unit_two_requirement_review()
    result.source_interpretation.statements[1].decision_functions = ["action", function]
    assert protocol_control_execution_module.restricted_batch_from_review(batch, result) is None


def test_restricted_source_keeps_its_context_without_guessing_independence() -> None:
    batch, result = _unresolved_batch_review()
    source = result.source_interpretation.statements[0]
    source.scope_quote = source.quoted_text
    source.exception_words = source.quoted_text
    output = protocol_control_execution_module.restricted_batch_from_review(batch, result)
    assert output is not None
    record = output.restricted_statements[0]
    assert record.scope_quote == source.quoted_text
    assert record.exception_words == source.quoted_text
    assert type(output).model_validate(output.model_dump(mode="json")) == output


@pytest.mark.parametrize("kind", ["interpretation", "temporal"])
def test_same_unit_restriction_survives_real_checkpoint_and_rebuild(
    session_factory, monkeypatch, kind,
) -> None:
    from app.services.eligibility_review_projection import _restricted_control_projections
    from tests.v2.domain.test_control_catalog_restricted_contract import _catalog, _publication

    module = protocol_control_execution_module
    batch, result = (_independent_candidate_and_temporal_gap(same_unit=True)
                     if kind == "temporal" else _same_unit_two_requirement_review())
    output = module.restricted_batch_from_review(batch, result)
    assert output is not None
    payload = {"run_result": result.model_dump(mode="json"),
               "restricted_batch": output.model_dump(mode="json")}
    job = JobService(session_factory, now=_now).create_job(
        idempotency_key="same-unit-restricted-proof",
        job_type=PROTOCOL_CONTROL_EXECUTION_JOB_TYPE,
        payload={"purpose": "synthetic same-unit consumer verification"},
        steps=[StepSpec(step_id="deep_0001", name="深审")],
    )
    with session_factory() as session, session.begin():
        store = JobStore(session, now=_now)
        lease = store.claim_job(job.job_id, "same-unit-test")
        assert lease is not None
        store.start_step(lease, "deep_0001")
        store.complete_step(lease, "deep_0001", checkpoint_payload=payload)
        store.finish_success(lease)
    with session_factory() as session:
        original = JobStore(session, now=_now).get_last_checkpoint(job.job_id, "deep_0001")
    assert original is not None and original[1] == dict(payload, attempt=1)
    monkeypatch.setattr(module.ProtocolControlDiscoveryToDeepPlan, "model_validate",
                        staticmethod(lambda _: SimpleNamespace(batches=[batch])))
    context = SimpleNamespace(job_id=job.job_id)
    closure = {"deep_plan": {}, "deep_step_ids": [
        {"step_id": "deep_0001", "batch_id": batch.batch_id},
    ]}
    rebuilt, _, _ = module._deep_results(
        context, SimpleNamespace(session_factory=session_factory, now=_now), closure,
    )
    assert rebuilt[batch.batch_id] == output
    catalog = _catalog(restricted=tuple(output.restricted_statements),
                       allowed=tuple(batch.owned_source_span_ids))
    projected = _restricted_control_projections(_publication(catalog))[0]
    assert projected.obligations[0].status == "restricted"
    assert projected.obligations[0].fact_refs == ()
    with session_factory() as session:
        assert JobStore(session, now=_now).get_last_checkpoint(job.job_id, "deep_0001") == original


def test_actual_runner_clock_failure_round_trips_to_restricted_consumer() -> None:
    from app.agents.protocol_control_deconstructor import ProtocolControlAgentRunner
    from tests.v2.domain.test_control_catalog_restricted_contract import _catalog, _publication
    from app.services.eligibility_review_projection import _restricted_control_projections

    batch, fixture = _independent_candidate_and_clock_capability()
    transport = _FakeTransport([ProtocolControlAgentResponse(
        session_id="clock-runner", text=fixture.capability_wire.model_dump_json(),
    )])
    result = ProtocolControlAgentRunner(max_schema_repairs=2).run(
        batch, transport, resume_source_interpretation=fixture.source_interpretation,
        output_validator=lambda output: protocol_control_execution_module._validate_deep_batch_output(batch, output),
    )
    assert result.status == "需要核对"
    assert result.final_output is None
    assert result.capability_wire is not None
    assert len(transport.prompts) == 1
    saved = ProtocolControlAgentRunResult.model_validate(result.model_dump(mode="json"))
    output = protocol_control_execution_module.restricted_batch_from_review(batch, saved)
    assert output is not None
    assert len(output.candidates) == 1
    catalog = _catalog(restricted=tuple(output.restricted_statements), allowed=tuple(batch.owned_source_span_ids))
    projected = _restricted_control_projections(_publication(catalog))[0]
    assert projected.obligations[0].status == "restricted"
    assert projected.obligations[0].fact_refs == ()
    assert "研究者" not in projected.obligations[0].reason
    assert "小时" in projected.obligations[0].reason or "分钟" in projected.obligations[0].reason


@pytest.mark.parametrize("failure", [
    "none", "schema", "wrong_number", "wrong_comparator", "incomplete_quote",
    "scope", "mixed_statement", "shared_source", "unresolved_semantics", "missing_wire",
    "ordinary_clock_free",
])
def test_capability_restriction_keeps_source_and_rejects_unproven_failures(failure: str) -> None:
    batch, result = _independent_candidate_and_clock_capability()
    if failure == "schema":
        result.attempts[-1].outcome = "schema_invalid"
    elif failure == "wrong_number":
        result.capability_wire.candidate_drafts[0].obligation_expression.groups[0].atoms[0].evaluation.predicate.value = 19
    elif failure == "wrong_comparator":
        result.capability_wire.candidate_drafts[0].obligation_expression.groups[0].atoms[0].evaluation.predicate.comparator = Comparator.LT
    elif failure == "incomplete_quote":
        result.source_interpretation.statements[1].quoted_text = "采集样本"
        result.source_interpretation.statements[1].time_words = []
    elif failure == "scope":
        result.source_interpretation.statements[1].scope_quote = batch.owned_units[1].excerpt
    elif failure == "mixed_statement":
        result.source_interpretation.statements.append(
            result.source_interpretation.statements[1].model_copy(deep=True))
    elif failure == "shared_source":
        result.capability_wire.candidate_drafts[1].source_structure_unit_ids.append("su-01")
        result.capability_wire.candidate_drafts[1].source_span_ids.append("span:01")
    elif failure == "unresolved_semantics":
        result.source_interpretation.statements[1].unresolved = ["采样对象不明确"]
    elif failure == "missing_wire":
        result.capability_wire = None
    elif failure == "ordinary_clock_free":
        result.capability_wire.candidate_drafts.pop()
        result.capability_wire.dispositions[1].disposition = StructureUnitDispositionKind.SUPPORTING_OR_SUPPLEMENT
    output = protocol_control_execution_module.restricted_batch_from_review(batch, result)
    if failure != "none":
        assert output is None
        return
    assert len(output.candidates) == 1
    assert output.candidates[0] == protocol_control_execution_module.hydrate_protocol_control_agent_output(
        result.capability_wire, batch).candidates[0]
    assert output.restricted_statements[0].source_quote == batch.owned_units[1].excerpt
    assert output.restricted_statements[0].limitation_kind == "consumer_unavailable"
    assert output.restricted_statements[0].source_span_ids == ["span:02"]
    protocol_control_execution_module._validate_deep_batch_output(batch, output)


def _restriction_case(kind: str):
    return (_independent_candidate_and_clock_capability() if kind == "clock"
            else _independent_candidate_and_temporal_gap() if kind == "temporal"
            else _independent_candidate_and_unresolved_review() if kind == "independent"
            else _unresolved_batch_review())


@pytest.mark.parametrize("kind", ["unresolved", "independent", "clock", "temporal"])
def test_unresolved_source_survives_deep_checkpoint_and_rejects_changed_quote(
    monkeypatch, kind: str,
) -> None:
    module = protocol_control_execution_module
    batch, result = _restriction_case(kind)
    independent_candidate = kind != "unresolved"
    monkeypatch.setattr(module, "_closure_checkpoint", lambda *_: {
        "deep_plan": {}, "deep_step_ids": [{"step_id": "deep_0001", "batch_id": batch.batch_id}],
    })
    monkeypatch.setattr(module.ProtocolControlDiscoveryToDeepPlan, "model_validate",
                        staticmethod(lambda _: SimpleNamespace(batches=[batch])))
    monkeypatch.setattr(module, "_deep_batch_for_step", lambda *_: batch)
    monkeypatch.setattr(module, "_prompt_from_payload", lambda *_: "冻结提示")
    monkeypatch.setattr(module, "_limits_from_payload", lambda *_: (1, 2))
    monkeypatch.setattr(module, "_frozen_official_predicates", lambda *_: ({}, {}))
    monkeypatch.setattr(module, "_resolve_transport", lambda *_, **__: SimpleNamespace(
        start_source_interpretation=lambda **_: None,
        take_call_receipts=lambda: [{"request_id": "request-1"}],
    ))
    monkeypatch.setattr(module, "_require_frozen_route", lambda *_, **__: None)
    monkeypatch.setattr(module, "_deep_component_identity", lambda *_: {})
    monkeypatch.setattr(module, "_transport_identity", lambda *_, **__: {})
    monkeypatch.setattr(module.ProtocolControlAgentRunner, "run", lambda *_, **__: result)
    context = StepContext(
        job_id="job-a", job_type=PROTOCOL_CONTROL_EXECUTION_JOB_TYPE,
        job_payload={}, step_id="deep_0001", name="深审", attempt=1,
        last_checkpoint_id=None, last_checkpoint=None,
    )
    saved = module._execute_deep(context, SimpleNamespace())
    assert len(saved["restricted_batch"]["candidates"]) == int(independent_candidate)
    assert len(saved["restricted_batch"]["restricted_statements"]) == 2 - int(independent_candidate)

    original_restriction = module.restricted_batch_from_review

    def invalid_restriction(*_args):
        raise ValueError("来源范围与已覆盖决定冲突")

    monkeypatch.setattr(module, "restricted_batch_from_review", invalid_restriction)
    with pytest.raises(StepFailure) as invalid_error:
        module._execute_deep(context, SimpleNamespace())
    assert invalid_error.value.error_code == "PROTOCOL_CONTROL_RESTRICTED_SOURCE_INVALID"
    assert invalid_error.value.diagnostic_checkpoint["source_interpretation"] is not None
    monkeypatch.setattr(module, "restricted_batch_from_review", original_restriction)

    if kind == "clock":
        result.source_interpretation.statements[1].scope_quote = batch.owned_units[1].excerpt
        with pytest.raises(StepFailure) as rejected:
            module._execute_deep(context, SimpleNamespace())
        assert rejected.value.error_code == "PROTOCOL_CONTROL_CAPABILITY_RESTRICTION_UNPROVEN"
        diagnostic = rejected.value.diagnostic_checkpoint
        assert diagnostic["partial_wire"] is None
        assert diagnostic["capability_wire"] == result.capability_wire.model_dump(mode="json")
        assert diagnostic["stage"] == "deep_failure_diagnostic"
        assert "restricted_batch" not in diagnostic
        result.source_interpretation.statements[1].scope_quote = None

    class FakeStore:
        def __init__(self, *_args, **_kwargs):
            pass

        def get_last_checkpoint(self, _job_id, _step_id):
            return ("checkpoint-a", saved)

    class SessionFactory:
        def __enter__(self):
            return None

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(module, "JobStore", FakeStore)
    config = SimpleNamespace(session_factory=SessionFactory, now=lambda: NOW)
    outputs, relations, definition_consumers = module._deep_results(
        context, config, module._closure_checkpoint(context, config),
    )
    assert len(outputs[batch.batch_id].restricted_statements) == 2 - int(independent_candidate)
    assert len(outputs[batch.batch_id].candidates) == int(independent_candidate)
    if independent_candidate:
        expected = protocol_control_execution_module.hydrate_protocol_control_agent_output(
            result.capability_wire if kind == "clock" else result.partial_wire, batch,
        )
        assert outputs[batch.batch_id].candidates == expected.candidates[:1]
    assert relations == []
    assert definition_consumers == []

    saved["restricted_batch"]["restricted_statements"][0]["source_quote"] = "原文未写的结论"
    with pytest.raises(StepFailure) as error:
        module._deep_results(context, config, module._closure_checkpoint(context, config))
    assert error.value.error_code == "PROTOCOL_CONTROL_RESTRICTED_SOURCE_INVALID"


@pytest.mark.parametrize("kind", ["unresolved", "independent", "clock", "temporal"])
def test_completed_restricted_source_reuse_rechecks_saved_review(monkeypatch, kind) -> None:
    module = protocol_control_execution_module
    batch, result = _restriction_case(kind)
    restricted = module.restricted_batch_from_review(batch, result)
    assert restricted is not None
    prompt = "冻结提示"
    saved = {
        "stage": "deep", "batch_id": batch.batch_id,
        "prompt_template_sha256": module.protocol_control_agent_prompt_template_sha256(prompt),
        "component_identity": {}, "repair_contract_sha256": module.protocol_control_agent_repair_contract_sha256(),
        "transport_identity": {}, "run_result": result.model_dump(mode="json"),
        "restricted_batch": restricted.model_dump(mode="json"),
    }

    class FakeStore:
        def get_job(self, _job_id):
            return SimpleNamespace(payload_json="{}")

        def get_last_checkpoint(self, _job_id, step_id):
            if step_id == module.STEP_CLOSURE:
                return "closure-a", {"stage": "closure", "deep_plan": {}}
            return "checkpoint-a", saved

        def list_steps(self, _job_id):
            return [SimpleNamespace(step_id="deep_0001", state="completed")]

    monkeypatch.setattr(module, "_require_compatible_deep_source", lambda *_: None)
    monkeypatch.setattr(module.ProtocolControlDiscoveryToDeepPlan, "model_validate",
                        staticmethod(lambda _: SimpleNamespace(batches=[batch])))
    monkeypatch.setattr(module, "_deep_component_identity", lambda *_: {})
    monkeypatch.setattr(module, "_same_deep_components_with_current_gate", lambda *_: True)
    monkeypatch.setattr(module, "_transport_identity", lambda *_, **__: {})
    args = (FakeStore(), {}, "source-job", batch, "deep_0001", SimpleNamespace(), prompt)
    assert module._validated_deep_source(*args)[0] == "checkpoint-a"

    saved["restricted_batch"]["restricted_statements"][0]["source_quote"] = "原文未写的结论"
    with pytest.raises(StepFailure) as error:
        module._validated_deep_source(*args)
    assert error.value.error_code == "PROTOCOL_CONTROL_DEEP_SOURCE_INVALID"


@pytest.mark.parametrize("code, retryable", [
    ("FLOW_TRANSPORT_FAILED", True),
    ("FLOW_COMPLETION_UNCERTAIN", False),
    ("SOURCE_REQUIREMENT_TRANSPORT_FAILED", True),
    ("SOURCE_INTERPRETATION_CORRECTION_TRANSPORT_FAILED", False),
    ("MODEL_IDENTITY_INVALID", False),
    ("FLOW_RESPONSE_INVALID", False),
    ("FLOW_COMPILER_CAPABILITY_GAP", False),
    ("LOGICAL_BUDGET_EXHAUSTED", False),
    ("SOURCE_FUNCTION_RECHECK_TRANSPORT_FAILED", True),
    ("SOURCE_FUNCTION_RECHECK_SCHEMA_INVALID", False),
    ("SOURCE_FUNCTION_RECHECK_INVALID", False),
    ("SOURCE_FUNCTION_RECHECK_UNRESOLVED", False),
    ("SOURCE_TARGET_REVIEW_TRANSPORT_FAILED", True),
    ("SOURCE_TARGET_FOCUSED_TRANSPORT_FAILED", True),
    ("SOURCE_TARGET_FOCUSED_INVALID", False),
    ("SOURCE_TARGET_FOCUSED_SCHEMA_INVALID", False),
    ("SOURCE_TARGET_REVIEW_UNAVAILABLE", False),
])
def test_deep_service_preserves_recheck_failure_kind_and_checkpoint(monkeypatch, code, retryable):
    from app.agents.protocol_control_deconstructor import ProtocolControlAgentAttempt

    module = protocol_control_execution_module
    batch, result = _restriction_case("independent")
    result.attempts = [ProtocolControlAgentAttempt(
        attempt=1, session_id="function-failed",
        raw_output_sha256=hashlib.sha256(b"isolated failure").hexdigest(),
        raw_output_text=None if retryable else "isolated response",
        outcome="transport_failed" if retryable else "publication_invalid",
        error_classes=[code], error_detail={"code": code, "statement_id": 0},
    )]
    monkeypatch.setattr(module, "_closure_checkpoint", lambda *_: {"deep_plan": {}})
    monkeypatch.setattr(module.ProtocolControlDiscoveryToDeepPlan, "model_validate",
                        staticmethod(lambda _: SimpleNamespace(batches=[batch])))
    monkeypatch.setattr(module, "_deep_batch_for_step", lambda *_: batch)
    monkeypatch.setattr(module, "_prompt_from_payload", lambda *_: "合成隔离提示")
    monkeypatch.setattr(module, "_limits_from_payload", lambda *_: (1, 2))
    monkeypatch.setattr(module, "_frozen_official_predicates", lambda *_: ({}, {}))
    monkeypatch.setattr(module, "_resolve_transport", lambda *_, **__: SimpleNamespace(
        start_source_interpretation=lambda **_: None,
        take_call_receipts=lambda: [{"request_id": "recheck-1"}],
    ))
    monkeypatch.setattr(module, "_require_frozen_route", lambda *_, **__: None)
    monkeypatch.setattr(module, "_transport_identity", lambda *_, **__: {})
    monkeypatch.setattr(module.ProtocolControlAgentRunner, "run", lambda *_, **__: result)
    monkeypatch.setattr(module, "restricted_batch_from_review", lambda *_: None)
    context = StepContext(
        job_id="synthetic", job_type=PROTOCOL_CONTROL_EXECUTION_JOB_TYPE,
        job_payload={}, step_id="deep_0001", name="深审", attempt=1,
        last_checkpoint_id=None, last_checkpoint=None,
    )
    with pytest.raises(StepFailure) as failure:
        module._execute_deep(context, SimpleNamespace())
    assert failure.value.retryable is retryable
    assert failure.value.error_code == "PROTOCOL_CONTROL_" + code
    checkpoint = failure.value.diagnostic_checkpoint
    assert checkpoint["attempts"][-1]["raw_output_text"] == result.attempts[-1].raw_output_text
    assert checkpoint["partial_wire"] == result.partial_wire.model_dump(mode="json")
    assert checkpoint["source_interpretation"] == result.source_interpretation.model_dump(mode="json")
    assert checkpoint["attempts"][-1]["error_classes"] == [code]
    assert checkpoint["model_call_receipts"] == [{"request_id": "recheck-1"}]


def test_mixed_front_progress_survives_actual_failure_checkpoint_without_adoption(monkeypatch):
    from app.agents.protocol_control_deconstructor import ProtocolControlAgentRunner
    from app.agents.protocol_control_fixed_flow import FIXED_FLOW
    from tests.v2.protocols.test_protocol_control_fixed_flow import _independent_mixed_example, _MixedTransport
    from app.protocols.protocol_control_gate import validate_protocol_control_batch_candidates

    module = protocol_control_execution_module
    batch, inventory, review, selection = _independent_mixed_example()
    inventory.statements[0].decision_functions = ["action", "definition"]
    review.items[0] = review.items[0].model_copy(update={
        "decision": "additional_requirement", "target_id": None,
        "target_action_excerpt": None, "source_time_excerpt": None,
        "target_time_excerpt": None, "unresolved_aspects": ["独立定义尚待装配"],
    })
    result = ProtocolControlAgentRunner().run(
        batch, _MixedTransport(review, selection), resume_source_interpretation=inventory,
        workflow_variant=FIXED_FLOW,
        output_validator=lambda output: validate_protocol_control_batch_candidates(batch, output),
    )
    assert result.final_output is None and result.source_candidate_alignment is not None
    monkeypatch.setattr(module, "_closure_checkpoint", lambda *_: {"deep_plan": {}})
    monkeypatch.setattr(module.ProtocolControlDiscoveryToDeepPlan, "model_validate",
                        staticmethod(lambda _: SimpleNamespace(batches=[batch])))
    monkeypatch.setattr(module, "_deep_batch_for_step", lambda *_: batch)
    monkeypatch.setattr(module, "_prompt_from_payload", lambda *_: "合成隔离提示")
    monkeypatch.setattr(module, "_limits_from_payload", lambda *_: (1, 2))
    monkeypatch.setattr(module, "_frozen_official_predicates", lambda *_: ({}, {}))
    monkeypatch.setattr(module, "_resolve_transport", lambda *_, **__: SimpleNamespace(
        start_source_interpretation=lambda **_: None, take_call_receipts=lambda: [],
    ))
    monkeypatch.setattr(module, "_require_frozen_route", lambda *_, **__: None)
    monkeypatch.setattr(module, "_transport_identity", lambda *_, **__: {})
    monkeypatch.setattr(module.ProtocolControlAgentRunner, "run", lambda *_, **__: result)
    context = StepContext(
        job_id="synthetic", job_type=PROTOCOL_CONTROL_EXECUTION_JOB_TYPE,
        job_payload={}, step_id="deep_0001", name="深审", attempt=1,
        last_checkpoint_id=None, last_checkpoint=None,
    )
    with pytest.raises(StepFailure) as failure:
        module._execute_deep(context, SimpleNamespace())
    assert failure.value.error_code == "PROTOCOL_CONTROL_FLOW_COMPILER_CAPABILITY_GAP"
    assert not failure.value.retryable
    checkpoint = failure.value.diagnostic_checkpoint
    assert checkpoint["partial_wire"] == result.partial_wire.model_dump(mode="json")
    assert checkpoint["source_front_target_review"] == review.model_dump(mode="json")
    assert checkpoint["source_candidate_alignment"] == result.source_candidate_alignment.model_dump(mode="json")
    assert checkpoint["attempts"][-1]["error_detail"] == result.attempts[-1].error_detail
    assert checkpoint["stage"] == "deep_failure_diagnostic"
    with pytest.raises(ValueError):
        module._validate_saved_source_review(batch, result)


@pytest.mark.parametrize("corrected", [False, True])
def test_front_review_failure_checkpoint_keeps_structured_cause_and_actual_composition(monkeypatch, corrected):
    from app.agents.protocol_control_deconstructor import ProtocolControlAgentRunner, ProtocolControlAgentResponse
    from app.agents.protocol_control_fixed_flow import FIXED_FLOW
    from app.agents.protocol_control_source_interpretation import SourceTargetReview, SOURCE_TARGET_REVIEW_VERSION
    from tests.v2.protocols.test_protocol_control_fixed_flow import _covered_procedure_example, _Transport
    module = protocol_control_execution_module
    batch, inventory, valid, selection = _covered_procedure_example()
    bad = valid.model_copy(update={"target_time_excerpt": None})
    class Local(_Transport):
        def start_source_target_review(self, *, prompt):
            self.calls.append("review")
            item = valid if corrected and len(self.calls) == 2 else bad
            return ProtocolControlAgentResponse(session_id=f"actual-{len(self.calls)}", text=SourceTargetReview(
                version=SOURCE_TARGET_REVIEW_VERSION, items=[item]).model_dump_json())
    def reject_output(output):
        raise ValueError("synthetic downstream failure")
    result = ProtocolControlAgentRunner().run(
        batch, Local(valid, selection), resume_source_interpretation=inventory,
        workflow_variant=FIXED_FLOW, output_validator=reject_output,
    )
    monkeypatch.setattr(module, "_closure_checkpoint", lambda *_: {"deep_plan": {}})
    monkeypatch.setattr(module.ProtocolControlDiscoveryToDeepPlan, "model_validate",
                        staticmethod(lambda _: SimpleNamespace(batches=[batch])))
    monkeypatch.setattr(module, "_deep_batch_for_step", lambda *_: batch)
    monkeypatch.setattr(module, "_prompt_from_payload", lambda *_: "合成隔离提示")
    monkeypatch.setattr(module, "_limits_from_payload", lambda *_: (0, 1))
    monkeypatch.setattr(module, "_frozen_official_predicates", lambda *_: ({}, {}))
    monkeypatch.setattr(module, "_resolve_transport", lambda *_, **__: SimpleNamespace(
        start_source_interpretation=lambda **_: None, take_call_receipts=lambda: [],
    ))
    monkeypatch.setattr(module, "_require_frozen_route", lambda *_, **__: None)
    monkeypatch.setattr(module, "_transport_identity", lambda *_, **__: {})
    monkeypatch.setattr(module.ProtocolControlAgentRunner, "run", lambda *_, **__: result)
    context = StepContext(job_id="synthetic", job_type=PROTOCOL_CONTROL_EXECUTION_JOB_TYPE,
        job_payload={}, step_id="deep_0001", name="深审", attempt=1,
        last_checkpoint_id=None, last_checkpoint=None)
    with pytest.raises(StepFailure) as failure:
        module._execute_deep(context, SimpleNamespace())
    checkpoint = failure.value.diagnostic_checkpoint
    assert checkpoint["partial_wire"] is None
    assert checkpoint["attempts"][0]["raw_output_text"] == result.attempts[0].raw_output_text
    recovered = module._resumable_saved_source_review(batch, inventory, checkpoint)
    if corrected:
        assert recovered.state == "reused" and recovered.review.items == [valid]
    else:
        assert recovered.state == "absent" and recovered.review is None
        detail = checkpoint["attempts"][-1]["error_detail"]
        assert detail["code"] == "TIME_SCOPE_MISMATCH"
        assert detail["statement_id"] == 0 and detail["json_path"].endswith("target_time_excerpt")
        assert detail["source_refs"] and detail["retry_class"] == "single_statement"
    with pytest.raises(ValueError):
        module._validate_saved_source_review(batch, result)


@pytest.mark.parametrize("failure", [
    "shared_source", "invalid_evaluation", "wrong_comparator", "wrong_unit", "unresolved_candidate",
])
def test_restricted_review_does_not_approve_dependent_or_invalid_candidate(failure: str) -> None:
    batch, result = _independent_candidate_and_unresolved_review()
    if failure == "shared_source":
        batch.owned_units[1].source_span_ids = ["span:01", "span:02"]
        result.source_statement_coverage = protocol_control_execution_module.source_statement_coverage(
            batch, result.source_interpretation, result.partial_wire,
        )
    elif failure in {"invalid_evaluation", "wrong_comparator", "wrong_unit"}:
        evaluation = result.partial_wire.candidate_drafts[0].obligation_expression.groups[0].atoms[0].evaluation
        if failure == "invalid_evaluation":
            evaluation.predicate.value = 19
        elif failure == "wrong_comparator":
            evaluation.predicate.comparator = Comparator.LTE
        else:
            evaluation.predicate.unit = "月"
    else:
        result.source_interpretation.statements[0].unresolved = ["适用对象仍待核清"]
    assert protocol_control_execution_module.restricted_batch_from_review(batch, result) is None


@pytest.mark.parametrize(("value", "unit"), [(18, "岁"), (18.0, "years")])
def test_restricted_review_preserves_normalized_numeric_candidate(value, unit) -> None:
    batch, result = _independent_candidate_and_unresolved_review()
    predicate = result.partial_wire.candidate_drafts[0].obligation_expression.groups[0].atoms[0].evaluation.predicate
    predicate.value = value
    predicate.unit = unit
    output = protocol_control_execution_module.restricted_batch_from_review(batch, result)
    assert output is not None
    saved = output.candidates[0].semantics.obligation_expression.groups[0].atoms[0].evaluation.predicate
    assert saved.value == value
    assert saved.unit == unit
    assert len(output.restricted_statements) == 1


@pytest.mark.parametrize(("quote", "value", "comparator", "unit", "expected"), [
    ("Age at least 18 years", 18, Comparator.GTE, "years", None),
    ("Age at least 18 years", 18, Comparator.LT, "years", "COMPARATOR_CHANGED"),
    ("Age >=18 years", 18, Comparator.LT, "years", "COMPARATOR_CHANGED"),
    ("年龄大于或等于18岁", 18, Comparator.GTE, "岁", None),
    ("年龄大于或等于18岁", 18, Comparator.LT, "岁", "COMPARATOR_CHANGED"),
    ("浓度至少5mg", 5, Comparator.GTE, "g", "NUMERIC_UNIT_NOT_IN_SOURCE"),
    ("数值至少-5", -5, Comparator.GTE, "unitless", None),
    ("数值至少-5", 5, Comparator.GTE, "unitless", "NUMERIC_VALUE_NOT_IN_SOURCE"),
    ("数量至少1,000", 1000, Comparator.GTE, "unitless", None),
    ("年龄18-65岁", 18, Comparator.GTE, "岁", "SOURCE_NUMERIC_SEMANTICS_UNVERIFIED"),
    ("年龄至少18岁；体重至少19kg", 19, Comparator.GTE, "岁", "NUMERIC_UNIT_NOT_IN_SOURCE"),
    ("年龄至少18岁且体重至少19kg", 19, Comparator.GTE, "岁", "SOURCE_NUMERIC_SEMANTICS_UNVERIFIED"),
])
def test_control_numeric_source_does_not_borrow_direction_unit_or_sibling_value(
    quote, value, comparator, unit, expected,
) -> None:
    candidate = _candidate()
    candidate.exception_expression = None
    candidate.applicability_expression = None
    atom = candidate.obligation_expression.groups[0].atoms[0]
    atom.statement = quote
    atom.source_excerpts = [quote]
    atom.evaluation = atom.evaluation.model_copy(update={"source_excerpts": [quote]}, deep=True)
    predicate = atom.evaluation.predicate
    predicate.source_clause = quote
    predicate.value = value
    predicate.comparator = comparator
    predicate.unit = unit
    if expected is None:
        _check_evaluation_numeric_sources("candidate:generic", candidate)
    else:
        with pytest.raises(ProtocolControlGateError) as caught:
            _check_evaluation_numeric_sources("candidate:generic", candidate)
        assert caught.value.code == expected
        assert caught.value.obligation_source_span_ids == ("span:01",)


def test_mixed_source_review_keeps_covered_procedure_and_restricts_only_gap() -> None:
    batch, result = _unresolved_batch_review()
    target = batch.known_procedure_targets[0]
    batch.known_procedure_targets[0] = target.model_copy(update={
        "source_excerpts": ["筛选时记录末次用药日期"],
    })
    result.source_interpretation.statements[1].time_words = ["筛选时"]
    result.source_interpretation.statements[1].unresolved = []
    result.source_statement_coverage[1].status = "linked_only"
    result.source_statement_coverage[1].disposition = "required_procedure"
    result.source_statement_coverage[1].linked_procedure_target_ids = [target.catalog_item_id]
    covered = result.source_target_review.items[1]
    covered.decision = "covered_by_procedure"
    covered.target_id = target.catalog_item_id
    covered.target_action_excerpt = "筛选时记录末次用药日期"
    covered.source_time_excerpt = "筛选时"
    covered.target_time_excerpt = "筛选时"
    covered.unresolved_aspects = []
    wire = _wire().model_copy(deep=True)
    wire.dispositions[1].disposition = StructureUnitDispositionKind.REQUIRED_PROCEDURE
    wire.dispositions[1].linked_procedure_catalog_item_id = target.catalog_item_id
    result.partial_wire = wire
    result.source_statement_coverage = protocol_control_execution_module.source_statement_coverage(
        batch, result.source_interpretation, wire,
    )

    still_uncertain = result.model_copy(deep=True)
    still_uncertain.source_interpretation.statements[1].unresolved = ["适用对象未核清"]
    still_uncertain.source_statement_coverage = protocol_control_execution_module.source_statement_coverage(
        batch, still_uncertain.source_interpretation, wire,
    )
    with pytest.raises(ValueError, match="来源陈述仍有未核清内容"):
        protocol_control_execution_module.restricted_batch_from_review(batch, still_uncertain)

    mixed = protocol_control_execution_module.restricted_batch_from_review(batch, result)
    assert mixed is not None
    assert [item.disposition for item in mixed.dispositions] == [
        StructureUnitDispositionKind.RESTRICTED_SOURCE,
        StructureUnitDispositionKind.REQUIRED_PROCEDURE,
    ]
    assert [item.source_structure_unit_id for item in mixed.restricted_statements] == ["su-01"]
    protocol_control_execution_module._validate_deep_batch_output(batch, mixed)

    result.source_statement_coverage[1].linked_procedure_target_ids = []
    with pytest.raises(ValueError, match="覆盖目标与草稿链接不一致"):
        protocol_control_execution_module.restricted_batch_from_review(batch, result)
    result.source_statement_coverage = protocol_control_execution_module.source_statement_coverage(
        batch, result.source_interpretation, wire,
    )

    result.partial_wire = None
    assert protocol_control_execution_module.restricted_batch_from_review(batch, result) is None


def test_unresolved_review_keeps_non_enrollment_execution_from_verified_wire() -> None:
    batch, result = _unresolved_batch_review()
    wire = _wire().model_copy(deep=True)
    wire.dispositions[1].disposition = StructureUnitDispositionKind.POST_TREATMENT_EXECUTION
    result.partial_wire = wire
    result.source_target_review.items = result.source_target_review.items[:1]
    result.source_statement_coverage = protocol_control_execution_module.source_statement_coverage(
        batch, result.source_interpretation, wire,
    )

    restricted = protocol_control_execution_module.restricted_batch_from_review(batch, result)
    assert restricted is not None
    assert [item.disposition for item in restricted.dispositions] == [
        StructureUnitDispositionKind.RESTRICTED_SOURCE,
        StructureUnitDispositionKind.POST_TREATMENT_EXECUTION,
    ]
    assert [item.source_structure_unit_id for item in restricted.restricted_statements] == ["su-01"]
    protocol_control_execution_module._validate_deep_batch_output(batch, restricted)

    result.source_statement_coverage[1].disposition = "required_procedure"
    with pytest.raises(ValueError, match="逐项来源核对必须且只能覆盖"):
        protocol_control_execution_module.restricted_batch_from_review(batch, result)


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
    assert "TIME_ANCHOR_MISSING" in exc.value.error_class_codes
    assert len(exc.value.validation_findings) == 2


@pytest.mark.parametrize("structural_code", [
    "BASELINE_VALUE_SCOPE_MIXED", "ENROLLMENT_PROHIBITION_UNCOVERED",
])
def test_actual_deep_gate_keeps_numeric_hard_stop_beside_structural_scope(monkeypatch, structural_code):
    from app.agents.protocol_control_deconstructor import ProtocolControlAgentRunner
    from tests.v2.protocols.test_slice58c_control_deconstructor import (
        _batch, _candidate_for_second_unit, _wire_with_two_candidates,
    )

    batch = _batch()
    initial = _wire_with_two_candidates(_candidate(), _candidate_for_second_unit())

    def errors(_batch, output):
        return (
            ProtocolControlGateError(
                "NUMERIC_VALUE_NOT_IN_SOURCE", "数值无源", entity_id=output.candidates[0].control_candidate_id,
            ),
            ProtocolControlGateError(
                structural_code, "结构需核", entity_id=output.candidates[1].control_candidate_id
                if structural_code != "ENROLLMENT_PROHIBITION_UNCOVERED" else "su-02",
                structure_unit_ids=["su-02"], obligation_source_span_ids=["span:02"],
            ),
        )

    monkeypatch.setattr(protocol_control_execution_module, "check_protocol_control_batch_candidates", errors)
    transport = _FakeTransport([
        ProtocolControlAgentResponse(session_id="hard-stop-before-structure", text=initial.model_dump_json()),
    ])
    result = ProtocolControlAgentRunner(max_schema_repairs=2).run(
        batch, transport, output_validator=lambda output: protocol_control_execution_module._validate_deep_batch_output(batch, output),
    )
    assert result.status == "需要核对" and result.final_output is None
    assert len(transport.prompts) == 1
    assert {"NUMERIC_VALUE_NOT_IN_SOURCE", structural_code} <= set(result.attempts[0].error_classes)
    assert len(result.attempts[0].error_detail["findings"]) == 2


def test_cross_chapter_source_pair_requires_independent_target_result(monkeypatch) -> None:
    action = "每次给药10 mg，每日1次"
    source_unit = SimpleNamespace(structure_unit_id="su-a", source_span_ids=["span:a"])
    target_unit = SimpleNamespace(structure_unit_id="su-b", source_span_ids=["span:b"])
    source_batch = SimpleNamespace(batch_id="batch-a", owned_structure_unit_ids=["su-a"],
                                   owned_units=[source_unit], context_structure_unit_ids=["su-b"])
    target_batch = SimpleNamespace(batch_id="batch-b", owned_structure_unit_ids=["su-b"],
                                   owned_units=[target_unit], context_structure_unit_ids=[])
    plan = SimpleNamespace(batches=[source_batch, target_batch])
    monkeypatch.setattr(protocol_control_execution_module.ProtocolControlDiscoveryToDeepPlan,
                        "model_validate", staticmethod(lambda _: plan))
    monkeypatch.setattr(protocol_control_execution_module, "validate_source_target_review",
                        lambda *_: None)
    monkeypatch.setattr(protocol_control_execution_module, "_validate_saved_source_review",
                        lambda *_: None)
    statement = SimpleNamespace(structure_unit_id="su-a", quoted_text=action, force="required",
                                decision_functions=["action"], unresolved=[])
    target_statement = SimpleNamespace(structure_unit_id="su-b", quoted_text="自筛选期开始接受背景治疗：" + action,
                                       scope_quote="自筛选期开始", force="required",
                                       decision_functions=["action"], unresolved=[])
    relation = SimpleNamespace(decision="potential_same_requirement", statement_index=0,
                               target_id="su-b", source_action_excerpt=action,
                               target_action_excerpt=action, target_scope_excerpt="自筛选期开始",
                               source_object_excerpt="背景治疗", target_object_excerpt="背景治疗")
    source_result = SimpleNamespace(status="待跨章核验", batch_id="batch-a",
                                    final_output=SimpleNamespace(owned_structure_unit_ids=["su-a"],
                                                                 candidates=[]),
                                    source_target_review=SimpleNamespace(items=[relation]),
                                    source_interpretation=SimpleNamespace(statements=[statement]),
                                    source_statement_coverage=[],
                                    source_definition_consumers=None)
    candidate = SimpleNamespace(control_candidate_id="candidate-b", frozen_structure_unit_ids=["su-b"],
                                semantics=SimpleNamespace(
                                    applicability_expression=None, trigger_expression=None,
                                    obligation_expression=SimpleNamespace(groups=[SimpleNamespace(atoms=[
                                        SimpleNamespace(source_excerpts=["自筛选期开始接受背景治疗：" + action])
                                    ])]), exception_expression=None))
    target_result = SimpleNamespace(status="已解析", batch_id="batch-b",
                                    final_output=SimpleNamespace(owned_structure_unit_ids=["su-b"],
                                                                  candidates=[candidate]),
                                    source_target_review=None,
                                    source_interpretation=SimpleNamespace(statements=[target_statement]),
                                    source_definition_consumers=None,
                                    source_statement_coverage=[SimpleNamespace(
                                        status="expressed", statement_index=0, candidate_indexes=[0],
                                    )])
    records = {"deep_0001": source_result, "deep_0002": target_result}
    class FakeStore:
        def __init__(self, *_args, **_kwargs):
            pass

        def get_last_checkpoint(self, _job_id, step_id):
            return (step_id, {"run_result": records[step_id]})

    class SessionFactory:
        def __enter__(self):
            return None

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(protocol_control_execution_module, "JobStore", FakeStore)
    monkeypatch.setattr(protocol_control_execution_module.ProtocolControlAgentRunResult,
                        "model_validate", staticmethod(lambda item: item))
    context = SimpleNamespace(job_id="job")
    config = SimpleNamespace(session_factory=SessionFactory, now=lambda: NOW)
    closure = {"deep_plan": {}, "deep_step_ids": [
        {"step_id": "deep_0001", "batch_id": "batch-a"},
        {"step_id": "deep_0002", "batch_id": "batch-b"},
    ]}
    _, proofs, definition_consumers = protocol_control_execution_module._deep_results(
        context, config, closure,
    )
    assert len(proofs) == 1
    assert proofs[0].target_candidate_id == "candidate-b"
    assert definition_consumers == []
    target_result.status = "待跨章核验"
    with pytest.raises(StepFailure) as error:
        protocol_control_execution_module._deep_results(context, config, closure)
    assert error.value.error_code == "PROTOCOL_CONTROL_SOURCE_RELATION_INVALID" or error.value.error_code == "PROTOCOL_CONTROL_SOURCE_RELATION_UNRESOLVED"


@dataclass(frozen=True)
class _Seed:
    source_job_id: str
    snapshot_path: Path
    source_span_excerpts: dict[str, str]
    workflow_stages: tuple[WorkflowStage, ...]


def _seed_frozen_source(data_paths, session_factory, *, key: str, waiting_at: str | None = None) -> _Seed:
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
    if waiting_at is not None:
        steps.append(StepSpec(waiting_at, waiting_at, depends_on=(previous,), waiting_user_kind="review"))
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
            if step.step_id == waiting_at:
                store.enter_user_wait(lease, step.step_id, awaiting_user="review")
                break
            store.start_step(lease, step.step_id)
            store.complete_step(lease, step.step_id, checkpoint_payload=checkpoint)
        if waiting_at is None:
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


def test_fixed_flow_is_frozen_in_job_prompt_and_requires_explicit_budget(data_paths, session_factory):
    seed = _seed_frozen_source(data_paths, session_factory, key="rv1001-flow")
    with pytest.raises(ValueError, match="累计请求"):
        _build_service(data_paths, session_factory, seed, deep_workflow_variant="RV1001-FLOW")
    service = _build_service(
        data_paths, session_factory, seed,
        deep_workflow_variant="RV1001-FLOW", deep_request_limit=12,
    )
    result = service.create_from_deconstruction(
        source_job_id=seed.source_job_id, idempotency_key="rv1001-flow-control",
    )
    with session_factory() as session:
        payload = json.loads(JobStore(session, now=_now).get_job(result.job_id).payload_json)
    assert payload["deep_workflow_variant"] == "RV1001-FLOW"
    assert payload["deep_request_limit"] == 12
    from app.agents.protocol_control_fixed_flow import FIXED_FLOW_VERSION
    assert payload["prompt_templates"]["deep"].endswith(FIXED_FLOW_VERSION)
    context = StepContext(
        job_id=result.job_id, job_type=PROTOCOL_CONTROL_EXECUTION_JOB_TYPE,
        job_payload=payload, step_id="deep_0001", name="test", attempt=1,
        last_checkpoint_id=None, last_checkpoint=None,
    )
    config = ProtocolControlExecutorConfig(data_paths=data_paths, session_factory=session_factory)
    assert protocol_control_execution_module._prompt_from_payload(context, "deep", config) == payload["prompt_templates"]["deep"]
    current_template = payload["prompt_templates"]["deep"]
    payload["prompt_templates"]["deep"] = current_template.removesuffix(FIXED_FLOW_VERSION) + "rv1001/front-stage-flow/v12"
    with pytest.raises(StepFailure) as old_flow:
        protocol_control_execution_module._prompt_from_payload(context, "deep", config)
    assert old_flow.value.error_code == "PROTOCOL_CONTROL_WORKFLOW_IDENTITY_INVALID"
    payload["prompt_templates"]["deep"] = current_template
    payload["deep_workflow_variant"] = "RV1001-BASELINE"
    with pytest.raises(StepFailure) as caught:
        protocol_control_execution_module._prompt_from_payload(context, "deep", config)
    assert caught.value.error_code == "PROTOCOL_CONTROL_WORKFLOW_IDENTITY_INVALID"


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


@pytest.mark.parametrize("waiting_at", ["await_review", "publish"])
def test_control_creation_freezes_registered_review_source_not_initial_input(
    data_paths, session_factory, waiting_at,
):
    from app.domain.contracts.agent_io import ProtocolDeconstructionInput
    from app.domain.contracts.enums import InterpretationSourceType
    from app.domain.contracts.protocol_metadata import InterpretationSource
    from app.domain.publication import canonical_hash
    from app.services.protocol_workbench_service import ProtocolWorkbenchService

    seed = _seed_frozen_source(data_paths, session_factory, key=f"registered-{waiting_at}", waiting_at=waiting_at)
    with session_factory() as session, session.begin():
        store = JobStore(session, now=_now)
        original = store.get_last_checkpoint(seed.source_job_id, "freeze_deconstruction_input")
        before_sha = canonical_hash(original[1])
        source = ProtocolDeconstructionInput.model_validate(original[1]["source_input"])
        clarification = InterpretationSource(
            interpretation_source_id="registered-clarification", protocol_version_id=source.protocol_version_id,
            source_type=InterpretationSourceType.MEDICAL_INTERPRETATION,
            file_sha256="8" * 64, source_ref="clarification:1",
            excerpt="未命名的回溯时间从当前审核节点计算。", explanation="逐节点核对，不更改阈值。",
            clarifies_ambiguity=True, applies_to_rule_refs=["IN-01"],
        )
        updated = ProtocolDeconstructionInput.model_validate(source.model_dump(mode="json") | {
            "interpretation_source_ids": [clarification.interpretation_source_id],
            "interpretation_sources": [clarification.model_dump(mode="json")],
        })
        store.record_user_update(seed.source_job_id, waiting_at,
            checkpoint_payload={"source_input": updated.model_dump(mode="json")})
    workbench = ProtocolWorkbenchService(session_factory, data_paths=data_paths, now=_now)
    expected = workbench._merged_payload(seed.source_job_id)["source_input"]
    assert expected == updated.model_dump(mode="json")
    service = _build_service(data_paths, session_factory, seed)
    created = service.create_from_deconstruction(source_job_id=seed.source_job_id,
        idempotency_key=f"controls-{waiting_at}")
    _, payload = _job_snapshot_and_payload(session_factory, created.job_id)
    assert payload["source_input"] == expected
    assert payload["source_input"]["interpretation_sources"][0]["authority"] == "clarification_only"
    with session_factory() as session:
        assert canonical_hash(JobStore(session, now=_now).get_last_checkpoint(
            seed.source_job_id, "freeze_deconstruction_input")[1]) == before_sha


def test_invalid_review_source_is_rejected_instead_of_falling_back_to_old_freeze(data_paths, session_factory):
    seed = _seed_frozen_source(data_paths, session_factory, key="invalid-review-source", waiting_at="await_review")
    with session_factory() as session, session.begin():
        store = JobStore(session, now=_now)
        source = dict(store.get_last_checkpoint(seed.source_job_id, "freeze_deconstruction_input")[1]["source_input"])
        source["protocol_file_sha256"] = "9" * 64
        store.record_user_update(seed.source_job_id, "await_review", checkpoint_payload={"source_input": source})
        before = session.connection().exec_driver_sql("select count(*) from jobs").scalar()
    with pytest.raises(ProtocolControlExecutionError) as rejected:
        _build_service(data_paths, session_factory, seed).create_from_deconstruction(
            source_job_id=seed.source_job_id, idempotency_key="reject-invalid-review-source")
    assert rejected.value.code == "PROTOCOL_CONTROL_SOURCE_HASH_MISMATCH"
    with session_factory() as session:
        assert session.connection().exec_driver_sql("select count(*) from jobs").scalar() == before


def test_control_job_freezes_current_draft_and_rejects_stale_request(
    data_paths, session_factory, monkeypatch,
) -> None:
    seed = _seed_frozen_source(data_paths, session_factory, key="draft-bound-source")
    original_checkpoint = JobStore.get_last_checkpoint

    def with_draft(self, job_id, step_id):
        if job_id == seed.source_job_id and step_id == "generate_draft":
            return "draft-checkpoint", {"draft_revision_id": "revision-current"}
        return original_checkpoint(self, job_id, step_id)

    monkeypatch.setattr(JobStore, "get_last_checkpoint", with_draft)
    from app.storage.repositories import ProtocolDraftRevisionRepository
    with session_factory() as session:
        source_payload = verify_payload_sha256(
            JobStore(session, now=_now).get_job(seed.source_job_id).payload_json,
            JobStore(session, now=_now).get_job(seed.source_job_id).payload_sha256,
        )["source_input"]
    monkeypatch.setattr(ProtocolDraftRevisionRepository, "get", lambda self, revision_id: SimpleNamespace(
        project_id=source_payload["project_id"], protocol_version_id=source_payload["protocol_version_id"],
        study_phase=source_payload["selected_phase"],
        content_sha256="a" * 64,
    ))
    service = _build_service(data_paths, session_factory, seed)
    with pytest.raises(ProtocolControlExecutionError, match="草稿版本已变化"):
        service.create_from_deconstruction(
            source_job_id=seed.source_job_id, draft_revision_id="revision-old",
            idempotency_key="stale-draft-control",
        )
    created = service.create_from_deconstruction(
        source_job_id=seed.source_job_id, draft_revision_id="revision-current",
        idempotency_key="current-draft-control",
    )
    _, payload = _job_snapshot_and_payload(session_factory, created.job_id)
    assert (payload["draft_revision_id"], payload["draft_content_sha256"]) == (
        "revision-current", "a" * 64,
    )


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


def test_frozen_slice_replanning_keeps_complete_ledger_and_old_checkpoint(
    data_paths, session_factory,
) -> None:
    from scripts.run_frozen_control_slice import replan_frozen_slice
    from app.domain.contracts.protocol_controls import ProtocolControlDiscoveryToDeepPlan

    seed = _seed_frozen_source(data_paths, session_factory, key="slice-replan-source")
    job = _build_service(data_paths, session_factory, seed).create_from_deconstruction(
        source_job_id=seed.source_job_id, idempotency_key="slice-replan-control",
    )
    runner, _ = _build_runner(data_paths, session_factory, _DiscoveryTransport(),
                             _DeepTransport(seed.source_span_excerpts))
    runner.run_job(job.job_id)
    with session_factory() as session:
        store = JobStore(session)
        row = store.get_job(job.job_id)
        payload = verify_payload_sha256(row.payload_json, row.payload_sha256)
        checkpoint = store.get_last_checkpoint(job.job_id, "deterministic_closure")
    previous = ProtocolControlDiscoveryToDeepPlan.model_validate(checkpoint[1]["deep_plan"])
    smaller = replan_frozen_slice(payload, previous, 1)
    assert smaller.discovery_decisions == previous.discovery_decisions
    assert smaller.expected_structure_unit_ids == previous.expected_structure_unit_ids
    assert [unit for batch in smaller.batches for unit in batch.owned_structure_unit_ids] == [
        unit for batch in previous.batches for unit in batch.owned_structure_unit_ids
    ]
    assert smaller.protocol_document_sha256 == previous.protocol_document_sha256
    for batch in smaller.batches:
        assert not set(batch.owned_structure_unit_ids) & set(batch.context_structure_unit_ids)
        assert batch.known_official_targets == previous.batches[0].known_official_targets
        assert batch.known_procedure_targets == previous.batches[0].known_procedure_targets
    with pytest.raises(ValueError):
        replan_frozen_slice(payload, previous, 0)
    with session_factory() as session:
        assert JobStore(session).get_last_checkpoint(job.job_id, "deterministic_closure") == checkpoint
        assert JobStore(session).get_job(job.job_id).payload_sha256 == row.payload_sha256


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
                            "required_source_types": [],  # No source-type restriction in this fixture.
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

    def start_source_interpretation(self, *, prompt: str) -> ProtocolControlAgentResponse:
        # This fixture exercises Job/checkpoint mechanics, not source semantics.
        payload = _prompt_payload(prompt, "冻结来源：")
        units = payload["owned"]
        return ProtocolControlAgentResponse(
            session_id="synthetic-source-session",
            text=json.dumps({
                "version": SOURCE_INTERPRETATION_VERSION,
                "statements": [],
                "units_without_statement": [unit["structure_unit_id"] for unit in units],
            }, ensure_ascii=False),
        )

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
    assert "continue_after_final_failure" not in payload["execution_control"]
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
    # The runner owns the next attempt number; replay returns business content only.
    assert executor(replay_context) == {key: value for key, value in gate.items() if key != "attempt"}
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


def test_new_job_can_reuse_discovery_and_deep_from_same_verified_source(
    data_paths, session_factory,
) -> None:
    seed = _seed_frozen_source(data_paths, session_factory, key="dual-source-adoption")
    discovery = _DiscoveryTransport()
    deep = _DeepTransport(seed.source_span_excerpts)
    route = lambda stage: protocol_control_execution_module._transport_identity_digest(
        discovery if stage == "discovery" else deep, stage=stage
    )
    service = _build_service(
        data_paths, session_factory, seed, route_identity_factory=route
    )
    source = service.create_from_deconstruction(
        source_job_id=seed.source_job_id, idempotency_key="dual-source-original"
    )
    runner, _ = _build_runner(data_paths, session_factory, discovery, deep)
    assert runner.run_job(source.job_id)
    calls = discovery.start_calls, deep.start_calls

    adopted = service.create_from_deconstruction(
        source_job_id=seed.source_job_id,
        idempotency_key="dual-source-adopted",
        discovery_source_job_id=source.job_id,
        deep_source_job_id=source.job_id,
    )
    _, payload = _job_snapshot_and_payload(session_factory, adopted.job_id)
    assert {item["decision"] for item in payload["deep_reuse_plan"]["decisions"].values()} == {
        "reusable"
    }
    assert runner.run_job(adopted.job_id)
    assert _job_snapshot_and_payload(session_factory, adopted.job_id)[0].state == "completed"
    assert (discovery.start_calls, deep.start_calls) == calls

    with pytest.raises(protocol_control_execution_module.ProtocolControlExecutionError) as mismatch:
        _build_service(
            data_paths, session_factory, seed,
            max_discovery_units_per_batch=1,
            route_identity_factory=route,
        ).create_from_deconstruction(
            source_job_id=seed.source_job_id,
            idempotency_key="dual-source-wrong-discovery-plan",
            discovery_source_job_id=source.job_id,
            deep_source_job_id=source.job_id,
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
        "parsed",
        "publication_invalid",
        "parsed",
    ]
    assert attempts[0]["issues"] == ["有源陈述：实际回答，尚未采用"]
    assert {attempt["session_id"] for attempt in attempts[1:]} == {"deep-session"}
    assert checkpoint[1]["run_result"]["repair_used"] is True
    import hashlib

    raw_answers = checkpoint[1]["attempt_raw_outputs"]
    assert len(raw_answers) == len(attempts)
    for answer, attempt in zip(raw_answers, attempts):
        assert answer["session_id"] == attempt["session_id"]
        assert answer["raw_output_text"]
        assert hashlib.sha256(answer["raw_output_text"].encode("utf-8")).hexdigest() == answer["raw_output_sha256"]
        assert "raw_output_text" not in attempt

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


@pytest.mark.parametrize("damage", [None, "gate-records", "old-version"])
def test_completed_job_prepares_full_publication_object_without_definition_records(
    data_paths, session_factory, damage,
):
    """Exercise the actual assembly return, not only its release-check helper."""
    from app.domain.contracts.agent_io import ProcedureCatalogMapping, ProtocolDeconstructionInput
    from app.domain.contracts.protocol_ingestion import ProtocolSourceSpan
    from app.domain.contracts.rules import RuleSet
    from app.services.protocol_control_catalog_publication import prepare_control_catalog_publication
    from app.services.protocol_draft_service import ProtocolDraftService
    from app.storage.codecs import encode_value
    from tests.v2.protocols.slice4_helpers import confirmed_fixture

    seed = _seed_frozen_source(data_paths, session_factory, key="publication-assembly")
    result = _build_service(data_paths, session_factory, seed).create_from_deconstruction(
        source_job_id=seed.source_job_id, idempotency_key="publication-assembly-control",
    )
    _, payload = _job_snapshot_and_payload(session_factory, result.job_id)
    source = ProtocolDeconstructionInput.model_validate(payload["source_input"])
    _, draft, _ = confirmed_fixture()
    draft.project_id = source.project_id
    draft.protocol_version_id = source.protocol_version_id
    draft.selected_phase = source.selected_phase
    for rule in draft.proposed_rules:
        rule.study_phase = source.selected_phase
    draft.proposed_workflow_stages = [item.model_copy(deep=True) for item in seed.workflow_stages]
    by_visit = {(item.stage, item.visit_instance): item for item in draft.proposed_workflow_stages}
    draft.procedure_catalog_mappings = []
    for item in source.required_procedure_catalog.items:
        stage = by_visit[(item.review_stage, item.visit_instance)]
        requirement_id = f"fixture-requirement:{item.item_id}"
        stage.due_requirement_ids.append(requirement_id)
        draft.procedure_catalog_mappings.append(ProcedureCatalogMapping(
            catalog_item_id=item.item_id, proposed_requirement_ids=[requirement_id],
            proposed_workflow_stage_id=stage.workflow_stage_id, source_span_ids=item.source_span_ids,
        ))
    # Fixture setup freezes the draft before execution; no old production receipt is rewritten.
    with session_factory() as session, session.begin():
        revision = ProtocolDraftService(session).save_initial_draft(draft, actor="test", created_at=NOW)
        payload.update(draft_revision_id=revision.revision_id, draft_content_sha256=revision.content_sha256)
        job = JobStore(session, now=_now).get_job(result.job_id)
        job.payload_json, job.payload_sha256 = encode_value(payload)
    runner, _ = _build_runner(data_paths, session_factory, _DiscoveryTransport(),
                              _DeepTransport(seed.source_span_excerpts))
    assert runner.run_job(result.job_id)
    assert _job_snapshot_and_payload(session_factory, result.job_id)[0].state == "completed"
    rule_set = RuleSet(rule_set_id="assembly-rules", revision=1,
                       protocol_version_id=source.protocol_version_id,
                       study_phase=source.selected_phase, rules=draft.proposed_rules)
    prefix = f"{rule_set.rule_set_id}:1:"
    stages = [item.model_copy(update={"workflow_stage_id": prefix + item.workflow_stage_id})
              for item in draft.proposed_workflow_stages]
    with session_factory() as session:
        checkpoint = JobStore(session, now=_now).get_last_checkpoint(result.job_id, "gate")
        assert checkpoint is not None
        if damage:
            from app.storage.models import JobCheckpointRecord
            from app.storage.repositories import ScopeViolationError
            from app.services.protocol_control_status import protocol_control_execution_status, ProtocolControlCheckpointInvalidError
            if damage == "gate-records":
                changed = dict(checkpoint[1], source_definition_consumers=[{"scope_complete": True}])
                row = session.get(JobCheckpointRecord, checkpoint[0])
                row.payload_json, row.payload_sha256 = encode_value(changed)
            else:
                job = JobStore(session).get_job(result.job_id)
                job.payload_json, job.payload_sha256 = encode_value(dict(payload, execution_version="older-execution"))
            session.commit()
            with pytest.raises(ProtocolControlCheckpointInvalidError):
                protocol_control_execution_status(session_factory, job_id=result.job_id)
            with pytest.raises(ScopeViolationError):
                prepare_control_catalog_publication(
                    session, source_job_id=result.job_id, source_checkpoint_id=checkpoint[0],
                    source_input=source,
                    source_spans={key: ProtocolSourceSpan.model_validate(value)
                                  for key, value in payload["source_spans"].items()},
                    draft=draft, rule_set=rule_set, published_stages=stages,
                    project_id=source.project_id, created_at=NOW,
                )
            return
        publication = prepare_control_catalog_publication(
            session, source_job_id=result.job_id, source_checkpoint_id=checkpoint[0],
            source_input=source,
            source_spans={key: ProtocolSourceSpan.model_validate(value)
                          for key, value in payload["source_spans"].items()},
            draft=draft, rule_set=rule_set, published_stages=stages,
            project_id=source.project_id, created_at=NOW,
        )
    assert publication.schema_version == "control-catalog/v1"
    assert publication.definition_consumer_records == []
    assert publication.catalog.controls
    assert set(publication.workflow_stage_map.values()) == {item.workflow_stage_id for item in stages}


def test_joint_publication_persists_source_bound_rules_and_controls_for_consumers(
    data_paths, session_factory,
):
    """A complete synthetic package uses the real publication transaction."""
    from sqlalchemy import select
    from app.agents.protocol_deconstructor import (
        _hydrate_semantic_candidate, semantic_candidate_from_draft,
    )
    from app.domain.contracts.agent_io import (
        ProtocolDeconstructionInput, ProtocolSemanticDeconstructionCandidate,
        SemanticRule,
    )
    from app.domain.contracts.protocol_ingestion import ProtocolSourceSpan
    from app.projections.clause_pack import project_clause_pack, verify_clause_pack
    from app.services.protocol_draft_service import ProtocolDraftService
    from app.services.protocol_publication_service import (
        ProtocolPublicationRequest, ProtocolPublicationService, PublicationLineageError,
    )
    from app.storage.codecs import encode_value
    from app.storage.control_catalog_repository import ControlCatalogPublicationRepository
    from app.storage.models import RuleSetRecord
    from app.storage.repositories import get_rule_set
    from tests.v2.protocols.slice4_helpers import confirmed_fixture

    seed = _seed_frozen_source(data_paths, session_factory, key="joint-publication")
    with session_factory() as session:
        frozen = JobStore(session, now=_now).get_last_checkpoint(seed.source_job_id, "freeze_deconstruction_input")
    assert frozen is not None
    source = ProtocolDeconstructionInput.model_validate(frozen[1]["source_input"])
    spans = {key: ProtocolSourceSpan.model_validate(value)
             for key, value in frozen[1]["source_spans"].items()}
    first = source.parent_rule_catalog.items[0]
    age = semantic_candidate_from_draft(confirmed_fixture()[1]).proposed_rules[0]
    age.components[0].source_span_ids = list(first.source_span_ids)
    predicate = age.components[0].expression.predicate
    predicate.observation_policy = predicate.observation_policy.model_copy(
        update={"source_span_ids": list(first.source_span_ids)},
    )
    rules = [age]
    for item in source.parent_rule_catalog.items[1:]:
        component = age.components[0].model_copy(deep=True)
        quote = spans[item.source_span_ids[0]].excerpt
        component.title = quote
        component.source_span_ids = list(item.source_span_ids)
        component.source_excerpts = [spans[key].excerpt for key in item.source_span_ids]
        predicate_data = component.expression.predicate.model_dump(mode="json")
        predicate_data.update(
            predicate_id=f"predicate:{item.official_code}", attribute=quote,
            source_term=quote, source_clause=quote, comparator="eq", value=True,
            unit=None, requires_professional_judgment="研究者判断" in quote,
            observation_policy={
                "mode": "unresolved", "scope": "合成来源未规定多份记录的选取方式",
                "source_span_ids": list(item.source_span_ids), "source_excerpts": [quote],
            },
        )
        component.expression.predicate = type(component.expression.predicate).model_validate(predicate_data)
        rules.append(SemanticRule(
            official_code=item.official_code, components=[component],
        ))
    draft = _hydrate_semantic_candidate(source, ProtocolSemanticDeconstructionCandidate(
        candidate_id="joint-publication", proposed_rules=rules,
        created_by_agent_call_id="synthetic-official-call",
    ))
    with session_factory() as session, session.begin():
        revision = ProtocolDraftService(session).save_initial_draft(draft, actor="test", created_at=NOW)
    result = _build_service(
        data_paths, session_factory, seed,
        workflow_stages=tuple(draft.proposed_workflow_stages),
    ).create_from_deconstruction(
        source_job_id=seed.source_job_id, idempotency_key="joint-publication-control",
    )
    with session_factory() as session, session.begin():
        job = JobStore(session, now=_now).get_job(result.job_id)
        payload = verify_payload_sha256(job.payload_json, job.payload_sha256)
        payload.update(draft_revision_id=revision.revision_id, draft_content_sha256=revision.content_sha256)
        job.payload_json, job.payload_sha256 = encode_value(payload)
    runner, _ = _build_runner(data_paths, session_factory, _DiscoveryTransport(),
                              _DeepTransport(seed.source_span_excerpts))
    assert runner.run_job(result.job_id)
    assert _job_snapshot_and_payload(session_factory, result.job_id)[0].state == "completed"
    with session_factory() as session:
        checkpoint = JobStore(session, now=_now).get_last_checkpoint(result.job_id, "gate")
    assert checkpoint is not None
    service = ProtocolPublicationService(session_factory, now=_now)
    request = ProtocolPublicationRequest(
        idempotency_key="joint-publish", draft_revision_id=revision.revision_id,
        source_input=source, source_spans=spans, actor="test", published_at=NOW,
        control_job_id=result.job_id, control_checkpoint_id=checkpoint[0],
    )
    from dataclasses import replace
    with pytest.raises(PublicationLineageError, match="补充审核要求"):
        service.publish(replace(request, control_checkpoint_id="missing-checkpoint"))
    with session_factory() as session:
        assert session.scalar(select(RuleSetRecord.rule_set_id)) is None
    published = service.publish(request)
    with session_factory() as session:
        rule_set = get_rule_set(session, published.rule_set_id, published.rule_set_revision)
        controls = ControlCatalogPublicationRepository(session).get_for_rule_set(
            published.rule_set_id, published.rule_set_revision,
        )
        assert controls is not None
        pack = project_clause_pack(rule_set, control_publication=controls)
        verify_clause_pack(pack)
    assert {item.official_code for item in rule_set.rules} == {item.official_code for item in rules}
    assert len(pack.clauses) == 4
    assert pack.restricted_clauses == []
    assert controls.catalog.controls
    assert pack.control_publication.publication_id == controls.publication_id
    assert service.publish(request).replay is True


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
    assert saved["source_interpretation"]["version"] == SOURCE_INTERPRETATION_VERSION
    assert saved["source_interpretation"]["statements"] == []
    assert len(saved["source_interpretation"]["units_without_statement"]) == 2
    assert saved["source_statement_coverage"] == []
    assert saved["source_target_review"] is None
    assert saved["attempts"][0]["raw_output_sha256"]
    assert saved["attempts"][0]["raw_output_text"] is not None
    assert deep.start_calls == 1
    assert next(step for step in snapshot.steps if step.step_id == "deep_0002").state == "queued"
    assert deep.continue_calls == 0
    assert not runner.run_job(result.job_id)
    assert deep.start_calls == 1  # Neither blind retry nor unnecessary sibling inference.


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
    assert deep.owned_batches[2] != deep.owned_batches[0]


@pytest.mark.parametrize("new_job, reuse_change", [
    (False, None), (True, None), (True, "repair_expired"),
    (True, "repair_corrupt"), (True, "compiler_old"), (True, "wire_corrupt"),
    (True, "source_witness_compiler"), (True, "source_witness_repair"),
    (True, "source_witness_validator"), (True, "source_witness_old_gate"),
    (True, "source_witness_two_scopes"),
])
def test_manual_retry_uses_verified_partial_wire_without_full_reread(
    data_paths, session_factory, monkeypatch, new_job: bool, reuse_change: str | None,
) -> None:
    from app.agents.protocol_control_deconstructor import (
        ProtocolControlAgentAttempt, ProtocolControlAgentRunResult,
        ProtocolControlAgentRunner, build_protocol_control_agent_prompt,
        parse_protocol_control_agent_wire,
    )
    from app.agents.protocol_control_source_interpretation import (
        SOURCE_INTERPRETATION_VERSION, SourceInterpretation, SourceStatement, SourceScopeCorrection,
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
    source_resumed = []
    failed_once = False

    def fail_then_resume(self, batch, transport, **kwargs):
        nonlocal failed_once
        if kwargs.get("resume_source_interpretation") is not None:
            source_resumed.append(kwargs["resume_source_interpretation"])
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
        if reuse_change == "source_witness_two_scopes":
            initial = SourceInterpretation(
                version=SOURCE_INTERPRETATION_VERSION,
                statements=[SourceStatement(structure_unit_id=unit.structure_unit_id,
                                            quoted_text=unit.excerpt, scope_quote="不在原文的范围",
                                            force="descriptive", decision_functions=["background"], time_words=[])
                            for unit in batch.owned_units[:2]],
                units_without_statement=list(batch.owned_structure_unit_ids[2:]),
            )
            class ScopeTransport(_FakeTransport):
                correction_count = 0
                def start_source_interpretation(self, *, prompt):
                    return ProtocolControlAgentResponse(session_id="source", text=initial.model_dump_json())
                def correct_source_scope(self, *, prompt):
                    unit = batch.owned_units[self.correction_count]
                    self.correction_count += 1
                    return ProtocolControlAgentResponse(session_id=f"scope-{self.correction_count}",
                        text=SourceScopeCorrection(version="phase5/control-source-scope-correction/v1",
                            structure_unit_id=unit.structure_unit_id, scope_quote=None,
                            affected_stage=None, time_words=[], unresolved=None).model_dump_json())
            scope_transport = ScopeTransport([ProtocolControlAgentResponse(session_id="author", text=wire.model_dump_json())])
            produced = original_run(self, batch, scope_transport, **kwargs)
            assert scope_transport.correction_count == 2, [(a.outcome, a.error_classes) for a in produced.attempts]
            assert produced.source_interpretation is not None
            assert len([a for a in produced.attempts if a.error_detail
                        and a.error_detail.get("workflow_phase") == "source_scope_correction"]) == 2
            return produced.model_copy(update={"status": "需要核对", "final_output": None, "partial_wire": wire})
        return ProtocolControlAgentRunResult(
            status="需要核对", batch_id=batch.batch_id, session_id="deep-session",
            attempts=[ProtocolControlAgentAttempt(
                attempt=1, session_id="deep-session",
                raw_output_sha256=hashlib.sha256((
                    interpretation if reuse_change and reuse_change.startswith("source_witness")
                    else wire
                ).model_dump_json().encode()).hexdigest(),
                raw_output_text=(interpretation.model_dump_json()
                                 if reuse_change and reuse_change.startswith("source_witness") else None),
                outcome=("parsed" if reuse_change and reuse_change.startswith("source_witness")
                         else "publication_invalid"),
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
    before_source = _job_checkpoint_fingerprint(session_factory, job.job_id)
    if new_job:
        original_checkpoint = JobStore.get_last_checkpoint

        def changed(self, job_id, step_id):
            checkpoint = original_checkpoint(self, job_id, step_id)
            if job_id != job.job_id or step_id != "deep_0001" or checkpoint is None:
                return checkpoint
            checkpoint_id, record = checkpoint
            if reuse_change in {"repair_expired", "repair_corrupt", "source_witness_repair"}:
                record = dict(record, repair_contract_sha256=(
                    "broken" if reuse_change == "repair_corrupt" else
                    hashlib.sha256(b"previous frozen repair contract").hexdigest()
                ))
            elif reuse_change in {"compiler_old", "source_witness_compiler", "source_witness_old_gate", "source_witness_two_scopes"}:
                component = dict(record["component_identity"])
                component["compiler_versions"] = [version for version in component["compiler_versions"]
                                                   if version != protocol_control_execution_module.SOURCE_FUNCTION_RECHECK_VERSION]
                record = dict(record, component_identity=component)
            elif reuse_change == "source_witness_validator":
                record = dict(record, component_identity=dict(record["component_identity"], validator_version="previous gate"))
            elif reuse_change == "wire_corrupt":
                record = dict(record, partial_wire={"unknown": "broken"},
                              repair_contract_sha256=hashlib.sha256(b"old repair").hexdigest())
            return checkpoint_id, record

        monkeypatch.setattr(JobStore, "get_last_checkpoint", changed)
        if reuse_change in {"repair_corrupt", "wire_corrupt"}:
            with pytest.raises(protocol_control_execution_module.ProtocolControlExecutionError) as error:
                service.create_from_deconstruction(
                    source_job_id=seed.source_job_id, deep_source_job_id=job.job_id,
                    idempotency_key="deep-partial-corrupt-repair",
                )
            assert error.value.code == "PROTOCOL_CONTROL_DEEP_SOURCE_INVALID"
            assert deep.start_calls == 0
            return
        original_gate = protocol_control_execution_module._validate_deep_batch_output
        if reuse_change in {"source_witness_old_gate", "source_witness_two_scopes"}:
            def reject_obsolete_author(*args):
                raise ValueError("旧作者结果在现行语义门禁不成立")
            monkeypatch.setattr(protocol_control_execution_module, "_validate_deep_batch_output", reject_obsolete_author)
        continued = service.create_from_deconstruction(
            source_job_id=seed.source_job_id,
            deep_source_job_id=job.job_id,
            idempotency_key="deep-partial-resume-new-version",
        )
        monkeypatch.setattr(protocol_control_execution_module, "_validate_deep_batch_output", original_gate)
        _, payload = _job_snapshot_and_payload(session_factory, continued.job_id)
        expected = ("refresh_required" if reuse_change and not reuse_change.startswith("source_witness")
                    else "resume_partial")
        assert expected in {
            entry["decision"] for entry in payload["deep_reuse_plan"]["decisions"].values()
        }
        target_job_id = continued.job_id
    else:
        with session_factory() as session, session.begin():
            JobStore(session, now=_now).retry_failed(job.job_id)
        target_job_id = job.job_id
    assert runner.run_job(target_job_id)
    snapshot, _ = _job_snapshot_and_payload(session_factory, target_job_id)
    if reuse_change == "source_witness_two_scopes":
        # Source replay reaches the real consumer; absent review is not fabricated success.
        assert snapshot.state == "failed_final"
        assert next(step for step in snapshot.steps if step.step_id == "deep_0001").error_code == "PROTOCOL_CONTROL_SOURCE_TARGET_REVIEW_UNAVAILABLE"
    else:
        assert snapshot.state == "completed", [
            (step.step_id, step.state, step.error_code)
            for step in snapshot.steps if step.state == "failed_final"
        ]
    assert bool(resumed) == (reuse_change is None)
    if reuse_change and reuse_change.startswith("source_witness"):
        assert source_resumed
        with session_factory() as session:
            checkpoint = JobStore(session, now=_now).get_last_checkpoint(target_job_id, "deep_0001")[1]
        assert checkpoint["source_review_reuse"]["proof_scope"] == "revalidated_source_interpretation"
        assert checkpoint["source_review_reuse"]["source_seed_proof"]["reused"] == ["source_interpretation"]
        assert "partial_wire" in checkpoint["source_review_reuse"]["source_seed_proof"]["discarded"]
    if new_job:
        monkeypatch.setattr(JobStore, "get_last_checkpoint", original_checkpoint)
        assert _job_checkpoint_fingerprint(session_factory, job.job_id) == before_source
    assert deep.start_calls == (1 if reuse_change == "source_witness_two_scopes" else 2 if reuse_change else 1)


@pytest.mark.parametrize("change", [
    "compiler", "repair_only", "validator", "source", "prompt", "wire_schema", "route",
    "changed_snapshot", "missing_raw", "corrupt_raw", "missing_session", "false_attempt",
])
def test_revalidated_source_seed_never_reuses_changed_material_or_author_approval(change):
    from copy import deepcopy
    from tests.v2.protocols.test_slice58c_control_deconstructor import (
        _two_independent_candidate_linked_alignment_material,
    )
    module = protocol_control_execution_module
    batch, inventory, _, wire, _ = _two_independent_candidate_linked_alignment_material()
    current = module._deep_component_identity({}, module.DEFAULT_PROTOCOL_CONTROL_AGENT_PROMPT_TEMPLATE)
    components = deepcopy(current)
    if change == "compiler":
        components["compiler_versions"] = ["previous compiler"]
    elif change == "validator":
        components["validator_version"] = "previous validator"
    elif change in {"source", "prompt", "wire_schema", "route"}:
        field = {"source": "source_sha256", "prompt": "prompt_material_sha256",
                 "wire_schema": "wire_schema_sha256", "route": "requested_route_sha256"}[change]
        components[field] = "0" * 64
    raw = inventory.model_dump_json()
    saved = dict(partial_wire=wire.model_dump(mode="json"), source_interpretation=inventory.model_dump(mode="json"),
                 component_identity=components, prompt_template_sha256=current["prompt_material_sha256"],
                 attempts=[dict(attempt=1, session_id="source-session", outcome="parsed", error_classes=[],
                                raw_output_text=raw, raw_output_sha256=hashlib.sha256(raw.encode()).hexdigest())])
    if change == "changed_snapshot":
        saved["source_interpretation"]["statements"][0]["unresolved"] = ["未核范围"]
    elif change == "missing_raw":
        saved["attempts"][0]["raw_output_text"] = None
    elif change == "corrupt_raw":
        saved["attempts"][0]["raw_output_sha256"] = "0" * 64
    elif change == "missing_session":
        saved["attempts"][0].pop("session_id")
    elif change == "false_attempt":
        saved["attempts"][0]["attempt"] = True
    before = deepcopy(saved)
    args = dict(source_job_id="source-job", step_id="deep_0001", checkpoint_id="source-checkpoint")
    if change == "corrupt_raw":
        with pytest.raises(ValueError, match="摘要损坏"):
            module._revalidated_source_seed_proof(batch, saved, current, **args)
    else:
        proof = module._revalidated_source_seed_proof(batch, saved, current, **args)
        assert bool(proof) is (change in {"compiler", "repair_only", "validator"})
        if proof:
            assert proof["reused"] == ["source_interpretation"]
            assert set(proof["discarded"]) >= {"partial_wire", "source_target_review", "session_id"}
    assert saved == before


@pytest.mark.parametrize("change", ["same", "wrong_target", "wrong_reason", "changed_sibling", "corrupt_correction"])
def test_revalidated_source_seed_replays_only_proven_scope_corrections(change):
    from copy import deepcopy
    from tests.v2.protocols.test_slice58c_control_deconstructor import (
        _two_independent_candidate_linked_alignment_material,
    )
    from app.agents.protocol_control_source_interpretation import (
        SourceScopeCorrection, SourceInterpretationValidationError, validate_source_interpretation,
    )
    module = protocol_control_execution_module
    batch, inventory, _, wire, _ = _two_independent_candidate_linked_alignment_material()
    original = inventory.model_copy(deep=True)
    original.statements[0].scope_quote = "不存在的阶段"
    with pytest.raises(SourceInterpretationValidationError) as error:
        validate_source_interpretation(batch, original)
    issue = error.value
    correction = SourceScopeCorrection(
        version="phase5/control-source-scope-correction/v1", structure_unit_id="su-01",
        scope_quote=None, affected_stage=None, time_words=[], unresolved=None,
    )
    raw, corrected = original.model_dump_json(), correction.model_dump_json()
    current = module._deep_component_identity({}, module.DEFAULT_PROTOCOL_CONTROL_AGENT_PROMPT_TEMPLATE)
    components = dict(current, compiler_versions=["previous compiler"])
    saved = dict(partial_wire=wire.model_dump(mode="json"), source_interpretation=inventory.model_dump(mode="json"),
                 component_identity=components, prompt_template_sha256=current["prompt_material_sha256"],
                 attempts=[
                     dict(attempt=1, session_id="source-session", outcome="schema_invalid",
                          error_classes=[issue.code], raw_output_text=raw,
                          raw_output_sha256=hashlib.sha256(raw.encode()).hexdigest(),
                          error_detail=dict(code=issue.code, statement_id=issue.statement_id, source_refs=issue.source_refs)),
                     dict(attempt=2, session_id="scope-session", outcome="parsed", error_classes=[],
                          raw_output_text=corrected, raw_output_sha256=hashlib.sha256(corrected.encode()).hexdigest()),
                 ])
    if change in {"wrong_target", "wrong_reason"}:
        saved["attempts"][0]["error_detail"]["statement_id" if change == "wrong_target" else "code"] = (
            1 if change == "wrong_target" else "SOURCE_QUOTE_UNGROUNDED")
    elif change == "changed_sibling":
        saved["source_interpretation"]["statements"][1]["quoted_text"] += "且不得调整"
    elif change == "corrupt_correction":
        saved["attempts"][1]["raw_output_sha256"] = "0" * 64
    before = deepcopy(saved)
    args = dict(source_job_id="source-job", step_id="deep_0001", checkpoint_id="source-checkpoint")
    if change == "corrupt_correction":
        with pytest.raises(ValueError, match="摘要损坏"):
            module._revalidated_source_seed_proof(batch, saved, current, **args)
    else:
        proof = module._revalidated_source_seed_proof(batch, saved, current, **args)
        assert bool(proof) is (change == "same")
        if proof:
            assert proof["scope_correction_indexes"] == [0]
            assert len(proof["source_response_sha256"]) == 2
    assert saved == before


@pytest.mark.parametrize("change", ["same", "missing_trigger", "wrong_trigger", "wrong_sequence", "boolean_sequence"])
def test_revalidated_source_seed_requires_second_correction_provenance(change):
    from copy import deepcopy
    from tests.v2.protocols.test_slice58c_control_deconstructor import _two_independent_candidate_linked_alignment_material
    from app.agents.protocol_control_source_interpretation import (
        SourceScopeCorrection, SourceInterpretationValidationError, validate_source_interpretation,
        apply_source_scope_correction,
    )
    module = protocol_control_execution_module
    batch, inventory, _, _, _ = _two_independent_candidate_linked_alignment_material()
    source = inventory.model_copy(deep=True)
    for statement in source.statements:
        statement.scope_quote = "不存在的范围"
    raw = source.model_dump_json()
    attempts = [dict(attempt=1, session_id="source", outcome="schema_invalid", raw_output_text=raw,
                     raw_output_sha256=hashlib.sha256(raw.encode()).hexdigest())]
    for index in range(2):
        with pytest.raises(SourceInterpretationValidationError) as error:
            validate_source_interpretation(batch, source)
        issue = error.value
        detail = dict(code=issue.code, statement_id=issue.statement_id, source_refs=issue.source_refs)
        if index == 0:
            attempts[0]["error_detail"] = detail
            attempts[0]["error_classes"] = [issue.code]
        correction = SourceScopeCorrection(version="phase5/control-source-scope-correction/v1",
                                           structure_unit_id=source.statements[index].structure_unit_id,
                                           scope_quote=None, affected_stage=inventory.statements[index].affected_stage,
                                           time_words=inventory.statements[index].time_words, unresolved=None)
        text = correction.model_dump_json()
        attempts.append(dict(attempt=index + 2, session_id=f"scope-{index}", outcome="parsed", error_classes=[],
                             error_detail=detail, raw_output_text=text, raw_output_sha256=hashlib.sha256(text.encode()).hexdigest()))
        source = apply_source_scope_correction(batch, source, index, correction)
    current = module._deep_component_identity({}, module.DEFAULT_PROTOCOL_CONTROL_AGENT_PROMPT_TEMPLATE)
    saved = dict(component_identity=dict(current, compiler_versions=["previous compiler"]),
                 prompt_template_sha256=current["prompt_material_sha256"], attempts=attempts,
                 source_interpretation=source.model_dump(mode="json"))
    if change == "missing_trigger":
        attempts[2].pop("error_detail")
    elif change == "wrong_trigger":
        attempts[2]["error_detail"]["statement_id"] = 0
    elif change == "wrong_sequence":
        attempts[2]["attempt"] = 4
    elif change == "boolean_sequence":
        attempts[2]["attempt"] = True
    before = deepcopy(saved)
    proof = module._revalidated_source_seed_proof(batch, saved, current, source_job_id="old",
                                                 step_id="deep_0001", checkpoint_id="checkpoint")
    assert bool(proof) is (change == "same")
    assert saved == before


@pytest.mark.parametrize("new_job, repair_changed", [(False, False), (True, False), (True, True)])
def test_manual_retry_reuses_verified_source_without_partial_wire(
    data_paths, session_factory, monkeypatch, new_job: bool, repair_changed: bool,
) -> None:
    from app.agents.protocol_control_deconstructor import (
        ProtocolControlAgentAttempt, ProtocolControlAgentRunResult,
        ProtocolControlAgentRunner,
    )
    from app.agents.protocol_control_source_interpretation import (
        SOURCE_INTERPRETATION_VERSION, SourceInterpretation,
    )

    seed = _seed_frozen_source(data_paths, session_factory, key="deep-source-only-resume")
    deep = _DeepTransport(seed.source_span_excerpts)
    service = _build_service(data_paths, session_factory, seed)
    job = service.create_from_deconstruction(
        source_job_id=seed.source_job_id, idempotency_key="deep-source-only-resume-job",
    )
    runner, _ = _build_runner(data_paths, session_factory, _DiscoveryTransport(), deep)
    original_run = ProtocolControlAgentRunner.run
    resumed = []
    first = True

    def fail_then_resume(self, batch, transport, **kwargs):
        nonlocal first
        if first:
            first = False
            inventory = SourceInterpretation(
                version=SOURCE_INTERPRETATION_VERSION,
                statements=[], units_without_statement=list(batch.owned_structure_unit_ids),
            )
            return ProtocolControlAgentRunResult(
                status="需要核对", batch_id=batch.batch_id, session_id="source-only",
                attempts=[ProtocolControlAgentAttempt(
                    attempt=1, session_id="source-only",
                    raw_output_sha256=hashlib.sha256(inventory.model_dump_json().encode()).hexdigest(),
                    raw_output_text=inventory.model_dump_json(), outcome="parsed",
                )], source_interpretation=inventory,
            )
        resumed.append(kwargs.get("resume_source_interpretation"))
        assert kwargs.get("resume_wire") is None
        return original_run(self, batch, transport, **kwargs)

    monkeypatch.setattr(ProtocolControlAgentRunner, "run", fail_then_resume)
    assert runner.run_job(job.job_id)
    assert _job_snapshot_and_payload(session_factory, job.job_id)[0].state == "failed_final"
    source_history = _job_checkpoint_fingerprint(session_factory, job.job_id)
    if repair_changed:
        monkeypatch.setattr(protocol_control_execution_module, "protocol_control_agent_repair_contract_sha256",
                            lambda **_: hashlib.sha256(b"new downstream repair guidance").hexdigest())
    if new_job:
        continued = service.create_from_deconstruction(
            source_job_id=seed.source_job_id,
            deep_source_job_id=job.job_id,
            idempotency_key="deep-source-only-resume-new-job",
        )
        _, payload = _job_snapshot_and_payload(session_factory, continued.job_id)
        expected_reason = ("verified_source_interpretation_repair_material_changed" if repair_changed
                           else "verified_source_interpretation")
        assert expected_reason in {
            item["reason"] for item in payload["deep_reuse_plan"]["decisions"].values()
        }
        if repair_changed:
            entry = next(item for item in payload["deep_reuse_plan"]["decisions"].values()
                         if item["step_id"] == "deep_0001")
            assert entry["decision"] == "resume_partial"
            assert entry["source_seed_proof"]["source_job_id"] == job.job_id
        target_job_id = continued.job_id
    else:
        with session_factory() as session, session.begin():
            JobStore(session, now=_now).retry_failed(job.job_id)
        target_job_id = job.job_id
    assert runner.run_job(target_job_id)
    assert _job_snapshot_and_payload(session_factory, target_job_id)[0].state == "completed"
    assert any(item is not None for item in resumed)
    if repair_changed:
        with session_factory() as session:
            saved = JobStore(session, now=_now).get_last_checkpoint(target_job_id, "deep_0001")[1]
        assert saved["source_review_reuse"]["proof_scope"] == "unrepaired_source_interpretation"
        assert saved["source_review_reuse"]["source_seed_proof"] == entry["source_seed_proof"]
        assert _job_checkpoint_fingerprint(session_factory, job.job_id) == source_history


@pytest.mark.parametrize("change", ["same", "checkpoint_session", "missing_session", "changed_source", "missing_raw", "not_parsed", "wire_present", "bad_hash"])
def test_source_only_repair_change_proof_is_content_bound_and_corruption_is_not_a_miss(change):
    from tests.v2.protocols.test_slice58c_control_deconstructor import (
        _two_independent_candidate_linked_alignment_material,
    )
    from copy import deepcopy
    module = protocol_control_execution_module
    batch, inventory, _, wire, _ = _two_independent_candidate_linked_alignment_material()
    raw = inventory.model_dump_json()
    saved = dict(partial_wire=None, source_interpretation=inventory.model_dump(mode="json"),
                 prompt_template_sha256="a" * 64, component_identity={},
                 attempts=[dict(attempt=1, outcome="parsed", session_id="source-session",
                                error_classes=[], raw_output_text=raw,
                                raw_output_sha256=hashlib.sha256(raw.encode()).hexdigest())])
    if change == "checkpoint_session":
        saved["attempts"][0].pop("session_id")
        saved["session_id"] = "historical-checkpoint-session"
    elif change == "missing_session":
        saved["attempts"][0].pop("session_id")
    elif change == "changed_source":
        saved["source_interpretation"]["statements"][0]["unresolved"] = ["有待核对的范围"]
    elif change == "missing_raw":
        saved["attempts"][0]["raw_output_text"] = None
    elif change == "not_parsed":
        saved["attempts"][0]["outcome"] = "schema_invalid"
    elif change == "wire_present":
        saved["partial_wire"] = wire.model_dump(mode="json")
    elif change == "bad_hash":
        saved["attempts"][0]["raw_output_sha256"] = "0" * 64
    before = deepcopy(saved)
    args = dict(source_job_id="source-job", step_id="deep_0001", checkpoint_id="source-checkpoint")
    if change == "bad_hash":
        with pytest.raises(ValueError, match="摘要不一致"):
            module._unrepaired_source_seed_proof(batch, saved, **args)
    else:
        proof = module._unrepaired_source_seed_proof(batch, saved, **args)
        assert bool(proof) is (change in {"same", "checkpoint_session"})
        if proof is not None:
            assert proof["checkpoint_id"] == "source-checkpoint"
            assert proof["reused"] == ["source_interpretation"]
            assert "session_id" in proof["discarded"]
            assert proof["session_record_scope"] == ("checkpoint" if change == "checkpoint_session" else "attempt")
    assert saved == before


@pytest.mark.parametrize("new_job", [False, True])
def test_manual_retry_reuses_saved_source_review_without_partial_wire(
    data_paths, session_factory, monkeypatch, new_job: bool,
) -> None:
    """A saved review stays reusable when no partial wire survived the failure."""

    from app.agents.protocol_control_deconstructor import ProtocolControlAgentRunner

    seed = _seed_frozen_source(data_paths, session_factory, key="saved-review-no-wire")
    source_history = _job_checkpoint_fingerprint(session_factory, seed.source_job_id)
    discovery = _DiscoveryTransport()
    deep = _ReviewRecordingDeepTransport(seed.source_span_excerpts)
    service = _build_service(data_paths, session_factory, seed)
    job = service.create_from_deconstruction(
        source_job_id=seed.source_job_id, idempotency_key="saved-review-no-wire-job",
    )
    runner, _ = _build_runner(data_paths, session_factory, discovery, deep)
    original_run, _state = _fail_with_saved_review(
        monkeypatch, deep, keep_partial_wire=False,
    )
    assert runner.run_job(job.job_id)
    assert _job_snapshot_and_payload(session_factory, job.job_id)[0].state == "failed_final"
    saved_step = _step_with_saved_review(session_factory, job.job_id)
    assert saved_step is not None
    with session_factory() as session:
        saved = JobStore(session, now=_now).get_last_checkpoint(job.job_id, saved_step)
    assert saved is not None
    assert saved[1]["source_target_review"] is not None
    assert saved[1]["source_statement_coverage"]
    assert saved[1]["partial_wire"] is None
    assert deep.review_calls == 0

    if new_job:
        continued = service.create_from_deconstruction(
            source_job_id=seed.source_job_id,
            deep_source_job_id=job.job_id,
            idempotency_key="saved-review-no-wire-continuation",
        )
        _, payload = _job_snapshot_and_payload(session_factory, continued.job_id)
        entry = next(
            item for item in payload["deep_reuse_plan"]["decisions"].values()
            if item["step_id"] == saved_step
        )
        assert entry["decision"] == "resume_partial"
        assert entry["source_review"] == "reused"
        assert entry["reason"] == "verified_source_interpretation_source_review_reused"
        target_job_id = continued.job_id
    else:
        with session_factory() as session, session.begin():
            JobStore(session, now=_now).retry_failed(job.job_id)
        target_job_id = job.job_id

    monkeypatch.setattr(ProtocolControlAgentRunner, "run", original_run)
    assert runner.run_job(target_job_id)
    snapshot, _ = _job_snapshot_and_payload(session_factory, target_job_id)
    assert snapshot.state == "completed", [
        (step.step_id, step.state, step.error_code)
        for step in snapshot.steps if step.state == "failed_final"
    ]
    assert deep.review_calls == 0  # The saved review still suppressed the reader.
    with session_factory() as session:
        resumed = JobStore(session, now=_now).get_last_checkpoint(target_job_id, saved_step)
    assert resumed[1]["source_review_reuse"] == {
        "state": "reused",
        "reason": "saved_source_review_still_current",
        "proof_scope": "saved_source_target_review",
        "verified_seed_statements": [0],
    }
    assert _job_checkpoint_fingerprint(session_factory, seed.source_job_id) == source_history


class _ReviewRecordingDeepTransport(_DeepTransport):
    """Deep adapter that records reviewer calls without generating answers."""

    review_calls = 0

    def start_source_target_review(self, *, prompt: str) -> ProtocolControlAgentResponse:
        self.review_calls += 1
        raise AssertionError("已保存且经当前校验仍有效的逐项来源核对不得重读")


def _saved_covered_source_review(batch, wire):
    """One real statement in the frozen batch that an official target covers.

    Returns ``None`` for a frozen batch whose owned units contain no official
    target excerpt; the caller keeps its normal path for that batch.
    """

    from app.agents.protocol_control_deconstructor import (
        hydrate_protocol_control_agent_output,
        source_statement_coverage,
    )
    from app.agents.protocol_control_source_interpretation import (
        SOURCE_TARGET_REVIEW_VERSION,
        SourceInterpretation,
        SourceTargetReview,
        validate_source_interpretation,
        validate_source_target_review,
    )

    quote = next(
        (
            excerpt
            for target in batch.known_official_targets
            for excerpt in target.source_excerpts
            if excerpt and any(excerpt in unit.excerpt for unit in batch.owned_units)
        ),
        None,
    )
    if quote is None:
        return None
    target = next(
        item for item in batch.known_official_targets if quote in item.source_excerpts
    )
    unit = next(unit for unit in batch.owned_units if quote in unit.excerpt)
    interpretation = SourceInterpretation.model_validate({
        "version": SOURCE_INTERPRETATION_VERSION,
        "statements": [{
            "structure_unit_id": unit.structure_unit_id,
            "quoted_text": quote,
            "force": "required",
            "time_words": [],
            "decision_functions": ["action"],
        }],
        "units_without_statement": [
            item.structure_unit_id for item in batch.owned_units
            if item.structure_unit_id != unit.structure_unit_id
        ],
    })
    validate_source_interpretation(batch, interpretation)
    protocol_control_execution_module._validate_deep_batch_output(
        batch, hydrate_protocol_control_agent_output(wire, batch),
    )
    coverage = source_statement_coverage(batch, interpretation, wire)
    review = SourceTargetReview.model_validate({
        "version": SOURCE_TARGET_REVIEW_VERSION,
        "items": [{
            "statement_index": 0,
            "decision": "covered_by_official",
            "target_id": target.official_code,
            "source_action_excerpt": quote,
            "target_action_excerpt": quote,
            "unresolved_aspects": [],
        }],
    })
    validate_source_target_review(batch, interpretation, coverage, review)
    return interpretation, coverage, review


def _job_checkpoint_fingerprint(session_factory, job_id: str) -> list[tuple[str, str]]:
    with session_factory() as session:
        store = JobStore(session, now=_now)
        return [
            (
                step.step_id,
                json.dumps(
                    (checkpoint[1] if (checkpoint := store.get_last_checkpoint(job_id, step.step_id)) else None),
                    ensure_ascii=False, sort_keys=True, default=str,
                ),
            )
            for step in store.list_steps(job_id)
        ]


def _step_with_saved_review(session_factory, job_id: str) -> str | None:
    """Locate the deep step whose latest checkpoint carries a saved review."""

    with session_factory() as session:
        store = JobStore(session, now=_now)
        for step in store.list_steps(job_id):
            if not step.step_id.startswith("deep_"):
                continue
            checkpoint = store.get_last_checkpoint(job_id, step.step_id)
            if checkpoint is not None and checkpoint[1].get("source_target_review") is not None:
                return step.step_id
    return None


def _fail_with_saved_review(monkeypatch, deep, *, keep_partial_wire: bool = True,
                            invalid_success: bool = False):
    """Record a validated source review beside a gate-valid draft, then fail.

    Batches whose frozen units contain no official-target excerpt keep their
    normal path; the fabricated failure lands on the first batch that can carry
    a covered-by-official statement. With ``keep_partial_wire=False`` the saved
    review survives without a reusable partial wire, matching the production
    failure shape where candidate insertion failed after the review was saved.
    """

    from app.agents.protocol_control_deconstructor import (
        ProtocolControlAgentAttempt,
        ProtocolControlAgentRunner,
        build_protocol_control_agent_prompt,
        hydrate_protocol_control_agent_output,
        parse_protocol_control_agent_wire,
    )

    original_run = ProtocolControlAgentRunner.run
    state: dict[str, Any] = {"failed_once": False, "saved": None}

    def fail_then_resume(self, batch, transport, **kwargs):
        if kwargs.get("resume_wire") is None and not state["failed_once"]:
            prompt = build_protocol_control_agent_prompt(
                batch, prompt_template=kwargs["prompt_template"],
            )
            wire = parse_protocol_control_agent_wire(deep._response(prompt).text)
            fabricated = _saved_covered_source_review(batch, wire)
            if fabricated is None:
                return original_run(self, batch, transport, **kwargs)
            state["failed_once"] = True
            interpretation, coverage, review = fabricated
            state["saved"] = (interpretation, coverage, review)
            return ProtocolControlAgentRunResult(
                status="已解析" if invalid_success else "需要核对", batch_id=batch.batch_id,
                session_id="saved-review-session",
                attempts=[ProtocolControlAgentAttempt(
                    attempt=1, session_id="saved-review-session",
                    raw_output_sha256=hashlib.sha256(b"saved-review").hexdigest(),
                    outcome="publication_invalid",
                )],
                source_interpretation=interpretation,
                source_statement_coverage=coverage,
                source_target_review=None if invalid_success else review,
                final_output=(hydrate_protocol_control_agent_output(wire, batch)
                              if invalid_success else None),
                partial_wire=wire if keep_partial_wire else None,
            )
        return original_run(self, batch, transport, **kwargs)

    monkeypatch.setattr(ProtocolControlAgentRunner, "run", fail_then_resume)
    return original_run, state


def test_deep_step_rejects_missing_review_before_completing_without_alignment(
    data_paths, session_factory, monkeypatch,
) -> None:
    seed = _seed_frozen_source(data_paths, session_factory, key="deep-final-review-gate")
    discovery = _DiscoveryTransport()
    deep = _ReviewRecordingDeepTransport(seed.source_span_excerpts)
    service = _build_service(data_paths, session_factory, seed)
    job = service.create_from_deconstruction(
        source_job_id=seed.source_job_id, idempotency_key="deep-final-review-gate-job",
    )
    runner, _ = _build_runner(data_paths, session_factory, discovery, deep)
    _original, state = _fail_with_saved_review(monkeypatch, deep, invalid_success=True)
    assert runner.run_job(job.job_id)
    assert state["failed_once"] is True
    snapshot, _payload = _job_snapshot_and_payload(session_factory, job.job_id)
    failed = [step for step in snapshot.steps
              if step.state == "failed_final" and step.error_code != "DEPENDENCY_FAILED"]
    assert len(failed) == 1
    assert failed[0].step_id.startswith("deep_")
    assert failed[0].error_code == "PROTOCOL_CONTROL_RESTRICTED_SOURCE_INVALID"
    with session_factory() as session:
        checkpoint = JobStore(session, now=_now).get_last_checkpoint(job.job_id, failed[0].step_id)
    assert checkpoint[1]["stage"] == "deep_failure_diagnostic"
    assert checkpoint[1]["source_target_review"] is None


def test_partial_resume_reuses_saved_source_review_and_keeps_source_history(
    data_paths, session_factory, monkeypatch,
) -> None:
    from app.agents.protocol_control_deconstructor import ProtocolControlAgentRunner

    seed = _seed_frozen_source(data_paths, session_factory, key="saved-review-source")
    source_history = _job_checkpoint_fingerprint(session_factory, seed.source_job_id)
    discovery = _DiscoveryTransport()
    deep = _ReviewRecordingDeepTransport(seed.source_span_excerpts)
    service = _build_service(data_paths, session_factory, seed)
    job = service.create_from_deconstruction(
        source_job_id=seed.source_job_id, idempotency_key="saved-review-job",
    )
    runner, _ = _build_runner(data_paths, session_factory, discovery, deep)
    original_run, state = _fail_with_saved_review(monkeypatch, deep)

    assert runner.run_job(job.job_id)
    assert _job_snapshot_and_payload(session_factory, job.job_id)[0].state == "failed_final"
    saved_step = _step_with_saved_review(session_factory, job.job_id)
    assert saved_step is not None
    with session_factory() as session:
        saved = JobStore(session, now=_now).get_last_checkpoint(job.job_id, saved_step)
    assert saved is not None
    assert saved[1]["source_target_review"] is not None
    assert saved[1]["source_statement_coverage"]
    assert saved[1]["partial_wire"] is not None
    assert deep.review_calls == 0  # The fabricated failure came from the reviewer-free path.

    monkeypatch.setattr(ProtocolControlAgentRunner, "run", original_run)
    with session_factory() as session, session.begin():
        JobStore(session, now=_now).retry_failed(job.job_id)
    assert runner.run_job(job.job_id)
    snapshot, _ = _job_snapshot_and_payload(session_factory, job.job_id)
    assert snapshot.state == "completed", [
        (step.step_id, step.state, step.error_code)
        for step in snapshot.steps if step.state == "failed_final"
    ]
    assert deep.review_calls == 0  # The saved review suppressed the whole reader round.
    with session_factory() as session:
        resumed = JobStore(session, now=_now).get_last_checkpoint(job.job_id, saved_step)
    assert resumed[1]["source_review_reuse"] == {
        "state": "reused",
        "reason": "saved_source_review_still_current",
        "proof_scope": "saved_source_target_review",
        "verified_seed_statements": [0],
    }
    assert resumed[1]["run_result"]["source_target_review"] == (
        state["saved"][2].model_dump(mode="json")
    )
    assert _job_checkpoint_fingerprint(session_factory, seed.source_job_id) == source_history


def test_continuation_plan_refreshes_a_changed_saved_source_review(
    data_paths, session_factory, monkeypatch,
) -> None:
    seed = _seed_frozen_source(data_paths, session_factory, key="changed-review-source")
    discovery = _DiscoveryTransport()
    deep = _ReviewRecordingDeepTransport(seed.source_span_excerpts)
    service = _build_service(data_paths, session_factory, seed)
    job = service.create_from_deconstruction(
        source_job_id=seed.source_job_id, idempotency_key="changed-review-job",
    )
    runner, _ = _build_runner(data_paths, session_factory, discovery, deep)
    _fail_with_saved_review(monkeypatch, deep)
    assert runner.run_job(job.job_id)
    saved_step = _step_with_saved_review(session_factory, job.job_id)
    assert saved_step is not None
    with session_factory() as session:
        saved = JobStore(session, now=_now).get_last_checkpoint(job.job_id, saved_step)
    assert saved is not None
    from app.storage.repositories import JobRepository

    tampered = json.loads(json.dumps(saved[1], ensure_ascii=False))
    tampered["source_target_review"]["items"][0]["target_action_excerpt"] = "不存在于目标原文"
    with session_factory() as session, session.begin():
        JobRepository(session).create_checkpoint(
            checkpoint_id="tampered-saved-review",
            job_id=job.job_id, step_id=saved_step, payload=tampered,
        )

    continued = service.create_from_deconstruction(
        source_job_id=seed.source_job_id,
        deep_source_job_id=job.job_id,
        idempotency_key="changed-review-continuation",
    )
    _, payload = _job_snapshot_and_payload(session_factory, continued.job_id)
    entry = next(
        item for item in payload["deep_reuse_plan"]["decisions"].values()
        if item["step_id"] == saved_step
    )
    assert entry["decision"] == "resume_partial"
    assert entry["source_review"] == "refresh_required"
    assert entry["reason"] == (
        "verified_unpublished_draft_source_review_refresh_required"
    )


def test_continuation_rejects_a_changed_model_route_before_reusing_a_saved_review(
    data_paths, session_factory, monkeypatch,
) -> None:
    seed = _seed_frozen_source(data_paths, session_factory, key="route-review-source")
    discovery = _DiscoveryTransport()
    deep = _ReviewRecordingDeepTransport(seed.source_span_excerpts)
    service = _build_service(
        data_paths, session_factory, seed,
        route_identity_factory=lambda stage: (
            protocol_control_execution_module._transport_identity_digest(
                discovery if stage == "discovery" else deep, stage=stage,
            )
        ),
    )
    job = service.create_from_deconstruction(
        source_job_id=seed.source_job_id, idempotency_key="route-review-job",
    )
    runner, _ = _build_runner(data_paths, session_factory, discovery, deep)
    _fail_with_saved_review(monkeypatch, deep)
    assert runner.run_job(job.job_id)
    saved_step = _step_with_saved_review(session_factory, job.job_id)
    assert saved_step is not None
    with session_factory() as session:
        saved = JobStore(session, now=_now).get_last_checkpoint(job.job_id, saved_step)
    assert saved is not None and saved[1]["source_target_review"] is not None

    class _OtherRouteDeepTransport(_ReviewRecordingDeepTransport):
        model = "different-model"

    other = _OtherRouteDeepTransport(seed.source_span_excerpts)
    other_service = _build_service(
        data_paths, session_factory, seed,
        route_identity_factory=lambda stage: (
            protocol_control_execution_module._transport_identity_digest(
                discovery if stage == "discovery" else other, stage=stage,
            )
        ),
    )
    with pytest.raises(ProtocolControlExecutionError) as mismatch:
        other_service.create_from_deconstruction(
            source_job_id=seed.source_job_id,
            deep_source_job_id=job.job_id,
            idempotency_key="route-review-continuation",
        )
    assert mismatch.value.code == "PROTOCOL_CONTROL_DEEP_SOURCE_INVALID"


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

    from app.domain.contracts.protocol_controls import ProtocolControlDiscoveryToDeepPlan
    from app.agents.protocol_control_deconstructor import build_protocol_control_agent_prompt
    with session_factory() as session:
        closure = JobStore(session, now=_now).get_last_checkpoint(source.job_id, "deterministic_closure")
    assert closure is not None
    batch = ProtocolControlDiscoveryToDeepPlan.model_validate(closure[1]["deep_plan"]).batches[0]
    new_total = batch.model_copy(update={"batch_total": batch.batch_total + 1})
    assert protocol_control_execution_module._same_deep_batch_material(batch, new_total)
    assert build_protocol_control_agent_prompt(batch) == build_protocol_control_agent_prompt(new_total)
    changed_source_gate = batch.model_copy(update={
        "owned_required_action_kinds_by_structure_unit_id": {
            batch.owned_structure_unit_ids[0]: ["different_action"],
        },
    })
    assert not protocol_control_execution_module._same_deep_batch_material(batch, changed_source_gate)


def test_preflight_marks_changed_action_gate_batch_for_refresh_before_model_call(
    data_paths, session_factory, monkeypatch,
):
    from app.protocols import protocol_control_planning as planning

    seed = _seed_frozen_source(data_paths, session_factory, key="action-gate-change")
    deep = _DeepTransport(seed.source_span_excerpts)
    service = _build_service(data_paths, session_factory, seed)
    source = service.create_from_deconstruction(
        source_job_id=seed.source_job_id,
        idempotency_key="action-gate-source",
    )
    runner, _ = _build_runner(data_paths, session_factory, _DiscoveryTransport(), deep)
    assert runner.run_job(source.job_id)
    before = deep.start_calls

    monkeypatch.setattr(
        planning, "detect_required_action_kinds", lambda _text: ("perform_ecg",),
    )
    planned = service.create_from_deconstruction(
        source_job_id=seed.source_job_id,
        idempotency_key="action-gate-current",
        deep_source_job_id=source.job_id,
    )
    _, payload = _job_snapshot_and_payload(session_factory, planned.job_id)
    assert {entry["reason"] for entry in payload["deep_reuse_plan"]["decisions"].values()} == {
        "planning_material_changed"
    }
    assert deep.start_calls == before
    assert runner.run_job(planned.job_id)
    snapshot, _ = _job_snapshot_and_payload(session_factory, planned.job_id)
    assert snapshot.state == "failed_final"
    assert snapshot.error_code != "PROTOCOL_CONTROL_DEEP_SOURCE_INVALID"
    assert deep.start_calls > before


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


def test_changed_repair_guidance_only_refreshes_affected_attempts() -> None:
    prior_atom = protocol_control_execution_module.protocol_control_agent_repair_contract_sha256(
        legacy_atom_v2=True
    )
    assert protocol_control_execution_module._repair_material_matches({
        "run_result": {"repair_used": True, "attempts": [
            {"error_classes": ["SOURCE_TARGET_REVIEW_INVALID"]},
        ]},
        "repair_contract_sha256": prior_atom,
    })
    assert not protocol_control_execution_module._repair_material_matches({
        "run_result": {"repair_used": True, "attempts": [
            {"error_classes": ["WIRE_SCHEMA_INVALID"]},
        ]},
        "repair_contract_sha256": prior_atom,
    })
    assert protocol_control_execution_module._repair_material_matches({
        "run_result": {"repair_used": True, "attempts": [
            {"outcome": "parsed", "error_classes": []},
        ]},
        "repair_contract_sha256": prior_atom,
    })
    assert not protocol_control_execution_module._repair_material_matches({
        "run_result": {"repair_used": True, "attempts": [
            {"outcome": "schema_invalid", "error_classes": []},
        ]},
        "repair_contract_sha256": prior_atom,
    })
    old_base = protocol_control_execution_module.protocol_control_agent_repair_contract_sha256(
        base_only=True
    )
    def saved(code: str) -> dict[str, object]:
        return {
            "run_result": {"repair_used": True, "attempts": [
                {"error_classes": [code]},
            ]},
            "repair_contract_sha256": old_base,
        }

    assert protocol_control_execution_module._repair_material_matches(saved("WIRE_SCHEMA_INVALID"))
    assert not protocol_control_execution_module._repair_material_matches(
        saved("SOURCE_TARGET_ADDITIONAL_REQUIREMENT")
    )
    assert not protocol_control_execution_module._repair_material_matches(
        saved("OPTIONAL_ACTION_MODALITY_DROPPED")
    )
    assert not protocol_control_execution_module._repair_material_matches({
        "run_result": {"repair_used": True, "attempts": []},
        "repair_contract_sha256": old_base,
    })
    prior_duration = protocol_control_execution_module.protocol_control_agent_repair_contract_sha256(
        without_duration_guidance=True
    )
    assert protocol_control_execution_module._repair_material_matches({
        "run_result": {"repair_used": True, "attempts": [{"error_classes": ["WIRE_SCHEMA_INVALID"]}]},
        "repair_contract_sha256": prior_duration,
    })
    assert not protocol_control_execution_module._repair_material_matches({
        "run_result": {"repair_used": True, "attempts": [
            {"error_classes": ["TREATMENT_DURATION_USED_AS_EVENT_WINDOW"]},
        ]},
        "repair_contract_sha256": prior_duration,
    })


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


def test_gate_only_change_revalidates_reusable_batch_without_model_call(
    data_paths, session_factory, monkeypatch,
):
    seed = _seed_frozen_source(data_paths, session_factory, key="gate-only-reuse")
    deep = _DeepTransport(seed.source_span_excerpts)
    service = _build_service(data_paths, session_factory, seed)
    source = service.create_from_deconstruction(
        source_job_id=seed.source_job_id, idempotency_key="gate-only-source",
    )
    runner, _ = _build_runner(data_paths, session_factory, _DiscoveryTransport(), deep)
    assert runner.run_job(source.job_id)
    calls_before = deep.start_calls
    original = JobStore.get_last_checkpoint
    old_gate = "phase5/control-publication-gate/v31"

    def previous_gate_checkpoint(self, job_id, step_id):
        checkpoint = original(self, job_id, step_id)
        if job_id != source.job_id or step_id != "deep_0001" or checkpoint is None:
            return checkpoint
        checkpoint_id, saved = checkpoint
        saved = dict(saved)
        saved["component_identity"] = dict(saved["component_identity"], validator_version=old_gate)
        return checkpoint_id, saved

    monkeypatch.setattr(JobStore, "get_last_checkpoint", previous_gate_checkpoint)
    adopted = service.create_from_deconstruction(
        source_job_id=seed.source_job_id,
        idempotency_key="gate-only-adopted",
        deep_source_job_id=source.job_id,
    )
    _, payload = _job_snapshot_and_payload(session_factory, adopted.job_id)
    assert {entry["decision"] for entry in payload["deep_reuse_plan"]["decisions"].values()} == {"reusable"}
    assert runner.run_job(adopted.job_id)
    assert deep.start_calls == calls_before
    with session_factory() as session:
        checkpoint = JobStore(session, now=_now).get_last_checkpoint(adopted.job_id, "deep_0001")
    assert checkpoint is not None
    assert checkpoint[1]["revalidated_from_gate_version"] == old_gate
    assert checkpoint[1]["component_identity"]["validator_version"] == (
        protocol_control_execution_module.CONTROL_PUBLICATION_GATE_VERSION
    )


@pytest.mark.parametrize("changed_material", [
    "wire_schema", "source_insert_authority", "continuation_source_contract",
])
def test_deep_source_component_change_refreshes_but_corrupt_identity_rejects(
    data_paths, session_factory, monkeypatch, changed_material,
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
        if changed_material == "wire_schema":
            saved["component_identity"]["wire_schema_sha256"] = "0" * 64
        else:
            removed_version = (
                protocol_control_execution_module.CONTROL_CONTINUATION_SOURCE_VERSION
                if changed_material == "continuation_source_contract"
                else "source-insert-pending-authority-and-append-order/v1"
            )
            saved["component_identity"]["compiler_versions"] = [
                version for version in saved["component_identity"]["compiler_versions"]
                if version != removed_version
            ]
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


def _partial_alignment_failure_fixture():
    from app.agents.protocol_control_candidate_alignment import (
        SOURCE_CANDIDATE_ALIGNMENT_VERSION,
        SourceCandidateAlignment,
        bind_candidate_alignment,
    )
    from app.agents.protocol_control_deconstructor import (
        ProtocolControlAgentAttempt,
        ProtocolControlAgentRunResult,
        source_statement_coverage,
    )
    from tests.v2.protocols.test_slice58c_control_deconstructor import (
        _two_independent_candidate_linked_alignment_material,
    )

    batch, inventory, review, wire, alignment_payload = (
        _two_independent_candidate_linked_alignment_material()
    )
    coverage = source_statement_coverage(batch, inventory, wire)
    coverage[0] = coverage[0].model_copy(update={
        "status": "semantically_aligned", "candidate_indexes": [0],
    })
    alignment = SourceCandidateAlignment.model_validate(alignment_payload)
    alignment = bind_candidate_alignment(
        batch, inventory, coverage, wire, alignment,
        json.dumps(alignment_payload, ensure_ascii=False),
    )
    result = ProtocolControlAgentRunResult(
        status="需要核对", batch_id=batch.batch_id, session_id="partial-align",
        attempts=[ProtocolControlAgentAttempt(
            attempt=1, session_id="partial-align",
            raw_output_sha256="a" * 64, outcome="publication_invalid",
            error_classes=["TEMPORAL_SCOPE_UNRESOLVED"],
            error_detail={
                "code": "TEMPORAL_SCOPE_UNRESOLVED", "statement_ids": [1],
                "json_path": "/items", "source_refs": ["span:02"],
                "retry_class": "temporal_scope_review", "affected_dependents": [1],
            },
        )],
        source_interpretation=inventory,
        source_statement_coverage=coverage,
        source_target_review=review,
        source_candidate_alignment=alignment,
        partial_wire=wire,
    )
    return batch, result


def test_failure_checkpoint_preserves_partial_candidate_alignment_and_revalidates(monkeypatch) -> None:
    from app.agents.protocol_control_candidate_alignment import SOURCE_CANDIDATE_ALIGNMENT_VERSION
    from app.agents.protocol_control_deconstructor import ProtocolControlAgentRunner
    from app.workflow.errors import StepFailure

    batch, fixture = _partial_alignment_failure_fixture()
    module = protocol_control_execution_module
    monkeypatch.setattr(module, "_closure_checkpoint", lambda *_: {"deep_plan": {
        "batches": [batch.model_dump(mode="json")],
    }})
    monkeypatch.setattr(
        module.ProtocolControlDiscoveryToDeepPlan, "model_validate",
        staticmethod(lambda payload: SimpleNamespace(
            batches=[batch],
        )),
    )
    monkeypatch.setattr(module, "_deep_batch_for_step", lambda *_: batch)
    monkeypatch.setattr(module, "_prompt_from_payload", lambda *_: "冻结提示")
    monkeypatch.setattr(module, "_limits_from_payload", lambda *_: (1, 2))
    monkeypatch.setattr(module, "_require_frozen_route", lambda *_ , **__: None)
    monkeypatch.setattr(module, "_deep_component_identity", lambda *_: {
        "schema_version": "phase5/deep-component-identity/v3",
        "validator_version": "gate",
    })
    monkeypatch.setattr(module, "_transport_identity", lambda *_ , **__: {"route": "deep"})
    monkeypatch.setattr(
        module, "protocol_control_agent_prompt_template_sha256", lambda *_: "prompt",
    )
    monkeypatch.setattr(
        module, "protocol_control_agent_repair_contract_sha256", lambda **_: "repair",
    )
    monkeypatch.setattr(module, "_require_schedule_member_sources", lambda *_: None)
    monkeypatch.setattr(module, "_frozen_official_predicates", lambda *_: ({}, {}))
    monkeypatch.setattr(module, "restricted_batch_from_review", lambda *_: None)
    monkeypatch.setattr(module, "_validate_deep_batch_output", lambda *_: None)
    monkeypatch.setattr(
        module, "hydrate_protocol_control_agent_output",
        lambda wire, batch: SimpleNamespace(batch_id=batch.batch_id),
    )
    monkeypatch.setattr(module, "_resolve_transport", lambda *_ , **__: SimpleNamespace(
        start_source_interpretation=lambda **_: None,
        take_call_receipts=lambda: [],
    ))
    monkeypatch.setattr(ProtocolControlAgentRunner, "run", lambda *_ , **__: fixture)
    context = StepContext(
        job_id="job-partial-align", job_type=PROTOCOL_CONTROL_EXECUTION_JOB_TYPE,
        job_payload={}, step_id="deep_0001", name="深审", attempt=1,
        last_checkpoint_id=None, last_checkpoint=None,
    )
    with pytest.raises(StepFailure) as raised:
        module._execute_deep(context, SimpleNamespace())
    diagnostic = raised.value.diagnostic_checkpoint
    assert diagnostic is not None
    assert diagnostic["stage"] == "deep_failure_diagnostic"
    assert diagnostic["source_candidate_alignment"]["version"] == SOURCE_CANDIDATE_ALIGNMENT_VERSION
    assert [
        (item["statement_index"], item["decision"])
        for item in diagnostic["source_candidate_alignment"]["items"]
    ] == [(0, "fully_expressed"), (1, "incomplete")]
    assert diagnostic["partial_wire"] is not None

    coverage = [
        module.SourceStatementCoverage.model_validate(item)
        for item in diagnostic["source_statement_coverage"]
    ]
    wire = module.ProtocolControlAgentWire.model_validate(diagnostic["partial_wire"])
    interpretation = module.SourceInterpretation.model_validate(
        diagnostic["source_interpretation"]
    )
    reused = module._resumable_saved_candidate_alignment(
        batch, interpretation, coverage, wire, diagnostic,
    )
    assert reused is not None
    assert [(item.statement_index, item.decision) for item in reused.items] == [
        (0, "fully_expressed")
    ]

    changed = dict(diagnostic)
    changed_alignment = json.loads(json.dumps(diagnostic["source_candidate_alignment"]))
    changed_alignment["items"][0]["source_excerpt"] = "年龄至少21岁"
    changed["source_candidate_alignment"] = changed_alignment
    assert module._resumable_saved_candidate_alignment(
        batch, interpretation, coverage, wire, changed,
    ) is None

    missing = dict(diagnostic)
    missing["source_candidate_alignment"] = None
    assert module._resumable_saved_candidate_alignment(
        batch, interpretation, coverage, wire, missing,
    ) is None

    malformed = dict(diagnostic)
    malformed["source_candidate_alignment"] = {"version": "bad", "items": []}
    assert module._resumable_saved_candidate_alignment(
        batch, interpretation, coverage, wire, malformed,
    ) is None

    captured = {}

    def capture_run(self, batch_arg, transport, **kwargs):
        captured.update(kwargs)
        return fixture

    monkeypatch.setattr(ProtocolControlAgentRunner, "run", capture_run)
    resume_context = StepContext(
        job_id="job-partial-align", job_type=PROTOCOL_CONTROL_EXECUTION_JOB_TYPE,
        job_payload={}, step_id="deep_0001", name="深审", attempt=2,
        last_checkpoint_id="cp-1", last_checkpoint=diagnostic,
    )
    with pytest.raises(StepFailure) as resumed:
        module._execute_deep(resume_context, SimpleNamespace())
    assert resumed.value.error_code == "PROTOCOL_CONTROL_DEEP_OUTPUT_INVALID"
    assert "resume_source_candidate_alignment" in captured, sorted(captured)
    assert captured["resume_source_candidate_alignment"] is not None
    assert [
        (item.statement_index, item.decision)
        for item in captured["resume_source_candidate_alignment"].items
    ] == [(0, "fully_expressed")]


@pytest.mark.parametrize("damage", ["sibling", "response_hash", "duplicate", "coverage", "old_version"])
def test_partial_alignment_readback_never_repairs_a_skip_proof(damage) -> None:
    batch, result = _partial_alignment_failure_fixture()
    saved = result.model_dump(mode="json")
    if damage == "sibling":
        saved["source_candidate_alignment"]["items"][1]["decision"] = "invalid"
    elif damage == "response_hash":
        saved["source_candidate_alignment"]["proofs"][0]["response_sha256"] = "0" * 64
    elif damage == "duplicate":
        saved["source_candidate_alignment"]["items"].append(
            saved["source_candidate_alignment"]["items"][0].copy())
    elif damage == "coverage":
        saved["source_statement_coverage"][0]["structure_unit_id"] = "other-source"
    else:
        saved["source_candidate_alignment"]["version"] = "phase5/control-source-candidate-alignment/v7"
    coverage = [protocol_control_execution_module.SourceStatementCoverage.model_validate(item)
                for item in saved["source_statement_coverage"]]
    reused = protocol_control_execution_module._resumable_saved_candidate_alignment(
        batch, result.source_interpretation, coverage, result.partial_wire, saved,
    )
    if damage == "sibling":
        assert reused is not None and len(reused.items) == 1
    else:
        assert reused is None


def test_actual_alignment_runner_failure_checkpoint_roundtrip_and_bounded_resume(
    session_factory, monkeypatch,
) -> None:
    from app.agents.protocol_control_deconstructor import ProtocolControlAgentRunner
    from tests.v2.protocols.test_slice58c_control_deconstructor import (
        _two_independent_candidate_linked_alignment_material,
    )
    module = protocol_control_execution_module
    batch, inventory, review, wire, alignment = _two_independent_candidate_linked_alignment_material()

    class Transport(_FakeTransport):
        asked = []

        def start_source_interpretation(self, *, prompt):
            raise AssertionError("已核来源不得在局部恢复时全量重读")

        def start_source_target_review(self, *, prompt):
            requested = [entry for entry in review.items
                         if f'"statement_index": {entry.statement_index}' in prompt]
            return ProtocolControlAgentResponse(session_id="target", text=review.model_copy(
                update={"items": requested},
            ).model_dump_json())

        def start_source_candidate_alignment(self, *, prompt):
            self.asked.append(prompt)
            requested = [entry for entry in alignment["items"]
                         if f'"statement_index": {entry["statement_index"]}' in prompt]
            return ProtocolControlAgentResponse(session_id="alignment", text=json.dumps({
                "version": alignment["version"], "items": requested,
            }, ensure_ascii=False))

    transport = Transport([])
    result = ProtocolControlAgentRunner().run(
        batch, transport, resume_wire=wire, resume_source_interpretation=inventory,
        resume_session_id="source", output_validator=lambda _: None,
    )
    assert result.final_output is None and result.source_candidate_alignment is not None
    # Only the closure/route fixture is isolated. The actual Runner, identity,
    # repair contract and SQLite checkpoint verification remain in use.
    monkeypatch.setattr(module, "_closure_checkpoint", lambda *_: {"deep_plan": {}})
    monkeypatch.setattr(module.ProtocolControlDiscoveryToDeepPlan, "model_validate",
                        staticmethod(lambda _: SimpleNamespace(batches=[batch])))
    monkeypatch.setattr(module, "_deep_batch_for_step", lambda *_: batch)
    monkeypatch.setattr(module, "_prompt_from_payload", lambda *_: "冻结合成提示")
    monkeypatch.setattr(module, "_limits_from_payload", lambda *_: (1, 2))
    monkeypatch.setattr(module, "_resolve_transport", lambda *_, **__: transport)
    monkeypatch.setattr(module, "_require_frozen_route", lambda *_, **__: None)
    monkeypatch.setattr(module, "_frozen_official_predicates", lambda *_: ({}, {}))
    monkeypatch.setattr(module, "_validate_deep_batch_output", lambda *_: None)
    monkeypatch.setattr(module, "restricted_batch_from_review", lambda *_: None)
    component = module._deep_component_identity({}, "冻结合成提示")
    diagnostic = {
        **result.model_dump(mode="json"), "stage": "deep_failure_diagnostic",
        "schema_version": "phase5/deep-failure-diagnostic/v3",
        "component_identity": component,
        "repair_contract_sha256": module.protocol_control_agent_repair_contract_sha256(),
        "prompt_template_sha256": module.protocol_control_agent_prompt_template_sha256("冻结合成提示"),
        "transport_identity": module._transport_identity(transport, stage="deep"),
    }
    job = JobService(session_factory, now=_now).create_job(
        idempotency_key="alignment-proof-real-checkpoint", job_type=PROTOCOL_CONTROL_EXECUTION_JOB_TYPE,
        payload={"purpose": "synthetic alignment recovery"},
        steps=[StepSpec(step_id="deep_0001", name="深审")],
    )
    with session_factory() as session, session.begin():
        store = JobStore(session, now=_now)
        lease = store.claim_job(job.job_id, "alignment-test")
        store.start_step(lease, "deep_0001")
        store.fail_step(lease, "deep_0001", error_code="PROTOCOL_CONTROL_DEEP_OUTPUT_INVALID",
                        retryable=False, diagnostic_checkpoint=diagnostic)
    with session_factory() as session:
        checkpoint = JobStore(session, now=_now).get_last_checkpoint(job.job_id, "deep_0001")
    assert checkpoint is not None and checkpoint[1] == dict(diagnostic, attempt=1)
    config = SimpleNamespace()

    def execute(saved):
        return module._execute_deep(StepContext(
            job_id=job.job_id, job_type=PROTOCOL_CONTROL_EXECUTION_JOB_TYPE, job_payload={},
            step_id="deep_0001", name="深审", attempt=2,
            last_checkpoint_id=checkpoint[0], last_checkpoint=saved,
        ), config)

    before = len(transport.asked)
    with pytest.raises(StepFailure) as resumed:
        execute(checkpoint[1])
    assert len(transport.asked) == before + 1, (resumed.value.error_code, resumed.value.detail)
    assert '"statement_index": 0' not in transport.asked[-1]
    assert '"statement_index": 1' in transport.asked[-1]
    assert resumed.value.diagnostic_checkpoint["source_candidate_alignment"]["proofs"]
    for field in ("component_identity", "repair_contract_sha256"):
        corrupted = {**checkpoint[1], field: {} if field == "component_identity" else "0" * 64}
        with pytest.raises(StepFailure) as rejected:
            execute(corrupted)
        assert rejected.value.error_code == "PROTOCOL_CONTROL_DEEP_SOURCE_INVALID"
    assert len(transport.asked) == before + 1
    with session_factory() as session:
        assert JobStore(session, now=_now).get_last_checkpoint(job.job_id, "deep_0001") == checkpoint
