"""Regressions for the serial multi-class repair budget contract.

The ProtocolControlAgentRunner repair budget (default 2 schema repair
rounds, ``DEFAULT_MAX_SCHEMA_REPAIRS``) is shared globally across every
error class in the combined repair scope.  A class that shifts or appears
after a repair round grants no extra rounds; an identical invalid result
stops the loop on the ``no_progress`` fingerprint; and the same transport
response sequence always reproduces the identical result.

These fixtures are synthetic: they never call a model, read a real
protocol, or write a project artifact.
"""

from __future__ import annotations

import pytest

from app.agents.protocol_control_deconstructor import (
    CONTROL_AGENT_WIRE_VERSION,
    DEFAULT_MAX_SCHEMA_REPAIRS,
    DEFAULT_MAX_TRANSPORT_RETRIES,
    ProtocolControlAgentResponse,
    ProtocolControlAgentRunner,
    ProtocolControlAgentWire,
    ProtocolControlAgentWireCandidate,
    ProtocolControlAgentWireConditionAtom,
    ProtocolControlAgentWireConditionDnf,
    ProtocolControlAgentWireConditionGroup,
    ProtocolControlAgentWireDisposition,
    ProtocolControlAgentWireEvidence,
    ProtocolControlAgentWireExceptionDnf,
    ProtocolControlAgentWireObligationAtom,
    ProtocolControlAgentWireObligationDnf,
    ProtocolControlAgentWireObligationGroup,
    ProtocolControlAgentWireValidationError,
)
from app.domain.contracts.enums import PhaseScope, ReviewStage, StudyPhase
from app.domain.contracts.protocol_controls import (
    ControlObligationKind,
    KnownOfficialRuleTarget,
    KnownRequiredProcedureTarget,
    KnownWorkflowStageTarget,
    ProtocolControlDispositionBatch,
    ProtocolStructureUnit,
    ReviewNodeRole,
    StructureUnitDispositionKind,
)


def _unit(unit_id: str, order: int, span_id: str, excerpt: str) -> ProtocolStructureUnit:
    return ProtocolStructureUnit(
        structure_unit_id=unit_id,
        source_ref=f"generic.body.p{order}",
        member_source_refs=[f"generic.body.p{order}"],
        source_span_ids=[span_id],
        unit_kind="paragraph",
        heading_path=["其他方案控制"],
        source_order=order,
        study_phase=StudyPhase.PHASE_II,
        phase_scopes=[PhaseScope.SHARED],
        excerpt=excerpt,
    )


def _batch() -> ProtocolControlDispositionBatch:
    owned = [
        _unit("su-01", 1, "span:01", "其他控制：年龄至少18岁"),
        _unit("su-02", 2, "span:02", "其他控制：筛选时记录末次用药日期"),
    ]
    context = _unit("su-03", 3, "span:03", "只读上下文，不得处置")
    return ProtocolControlDispositionBatch(
        batch_id="pcb-generic-01",
        coverage_manifest_id="manifest:generic-01",
        protocol_version_id="protocol:generic-01",
        study_phase=StudyPhase.PHASE_II,
        batch_number=1,
        batch_total=1,
        owned_units=owned,
        context_units=[context],
        owned_structure_unit_ids=["su-01", "su-02"],
        context_structure_unit_ids=["su-03"],
        owned_source_span_ids=["span:01", "span:02"],
        context_source_span_ids=["span:03"],
        known_official_targets=[
            KnownOfficialRuleTarget(
                catalog_item_id="official-item-1",
                official_code="EX-01",
                label="既有官方排除标准",
                position=0,
                source_span_ids=["span:official"],
            )
        ],
        known_procedure_targets=[
            KnownRequiredProcedureTarget(
                catalog_item_id="procedure-screening-1",
                label="筛选期检查",
                visit_instance="screening-1",
                review_stage=ReviewStage.SCREENING,
                position=0,
                source_span_ids=["span:procedure"],
            )
        ],
        known_workflow_stage_targets=[
            KnownWorkflowStageTarget(
                workflow_stage_id="stage:screening:one",
                review_stage=ReviewStage.SCREENING,
                display_name="筛选期审核一",
                visit_instance="screening-1",
            ),
            KnownWorkflowStageTarget(
                workflow_stage_id="stage:screening:two",
                review_stage=ReviewStage.SCREENING,
                display_name="筛选期审核二",
                visit_instance="screening-2",
            ),
        ],
    )


def _condition(
    statement: str,
    span_id: str,
    excerpt: str,
) -> ProtocolControlAgentWireConditionAtom:
    return ProtocolControlAgentWireConditionAtom(
        statement=statement,
        source_span_ids=[span_id],
        source_excerpts=[excerpt],
        time_constraint=None,
        requires_professional_judgment=False,
    )


def _candidate() -> ProtocolControlAgentWireCandidate:
    return ProtocolControlAgentWireCandidate(
        title="年龄资料控制",
        applicable_population="拟入组受试者",
        applicability_expression=ProtocolControlAgentWireConditionDnf(
            groups=[
                ProtocolControlAgentWireConditionGroup(
                    atoms=[_condition("年龄条件", "span:01", "年龄至少18岁")]
                )
            ]
        ),
        trigger_expression=None,
        obligation_expression=ProtocolControlAgentWireObligationDnf(
            groups=[
                ProtocolControlAgentWireObligationGroup(
                    atoms=[
                        ProtocolControlAgentWireObligationAtom(
                            kind=ControlObligationKind.REACH_CONDITION,
                            statement="年龄达到18岁",
                            time_constraint=None,
                            prospective_period=None,
                            source_span_ids=["span:01"],
                            source_excerpts=["年龄至少18岁"],
                            requires_professional_judgment=False,
                        )
                    ]
                )
            ]
        ),
        exception_expression=ProtocolControlAgentWireExceptionDnf(
            groups=[
                ProtocolControlAgentWireConditionGroup(
                    atoms=[_condition("无例外", "span:01", "年龄至少18岁")]
                )
            ]
        ),
        review_node_bindings=[
            {
                "workflow_stage_id": "stage:screening:one",
                "review_stage": ReviewStage.SCREENING,
                "role": ReviewNodeRole.DECIDE_AT_NODE,
                "guidance": None,
            }
        ],
        minimum_evidence=[
            ProtocolControlAgentWireEvidence(
                fact_type="demographics",
                description="核对年龄资料",
                due_stage=ReviewStage.SCREENING,
                required_source_types=["原始资料"],
            )
        ],
        source_structure_unit_ids=["su-01"],
        source_span_ids=["span:01"],
        cross_source_relations=[],
    )


def _wire(*, candidate: ProtocolControlAgentWireCandidate | None = None) -> ProtocolControlAgentWire:
    return ProtocolControlAgentWire(
        wire_version=CONTROL_AGENT_WIRE_VERSION,
        dispositions=[
            ProtocolControlAgentWireDisposition(
                structure_unit_id="su-01",
                disposition=(
                    StructureUnitDispositionKind.OTHER_CONTROL_CANDIDATE
                    if candidate is not None
                    else StructureUnitDispositionKind.SUPPORTING_OR_SUPPLEMENT
                ),
                linked_official_code=None,
                linked_procedure_catalog_item_id=None,
                linked_procedure_catalog_item_ids=[],
                notes=None if candidate is not None else "仅作背景说明，不形成控制候选",
            ),
            ProtocolControlAgentWireDisposition(
                structure_unit_id="su-02",
                disposition=StructureUnitDispositionKind.SUPPORTING_OR_SUPPLEMENT,
                linked_official_code=None,
                linked_procedure_catalog_item_id=None,
                linked_procedure_catalog_item_ids=[],
                notes="仅作补充语境，不形成控制候选",
            ),
        ],
        candidate_drafts=[] if candidate is None else [candidate],
    )


class _FakeTransport:
    def __init__(self, responses: list[ProtocolControlAgentResponse]) -> None:
        self.responses = list(responses)
        self.prompts: list[str] = []

    def start(self, *, prompt: str) -> ProtocolControlAgentResponse:
        self.prompts.append(prompt)
        return self.responses.pop(0)

    def continue_session(
        self,
        *,
        session_id: str,
        prompt: str,
    ) -> ProtocolControlAgentResponse:
        self.prompts.append(prompt)
        response = self.responses.pop(0)
        assert response.session_id == session_id
        return response


def _class_a(candidate_id: str) -> ProtocolControlAgentWireValidationError:
    return ProtocolControlAgentWireValidationError(
        "ACTION_TARGET_SCOPE_MISMATCH",
        "候选必须按来源作用域拆分",
        candidate_ids=[candidate_id],
        structure_unit_ids=["su-01"],
    )


def _class_b(candidate_id: str) -> ProtocolControlAgentWireValidationError:
    return ProtocolControlAgentWireValidationError(
        "MIXED_DECISION_STAGE_CONTROL",
        "同一候选不得混合不同决策阶段控制",
        candidate_ids=[candidate_id],
        structure_unit_ids=["su-01"],
    )


def _class_c(candidate_id: str) -> ProtocolControlAgentWireValidationError:
    return ProtocolControlAgentWireValidationError(
        "CONDITIONAL_EXEMPTION_BINDING_MISSING",
        "条件豁免缺少绑定",
        candidate_ids=[candidate_id],
        structure_unit_ids=["su-01"],
    )


def _combined(
    *underlying: ProtocolControlAgentWireValidationError,
) -> ProtocolControlAgentWireValidationError:
    """Mirror combined_repair_error: one scope exposing every active class."""

    return ProtocolControlAgentWireValidationError(
        "OUTPUT_VALIDATION_REJECTED",
        "\n".join(str(error) for error in underlying),
        structure_unit_ids=sorted(
            {unit_id for error in underlying for unit_id in error.structure_unit_ids}
        ),
        candidate_ids=sorted(
            {candidate_id for error in underlying for candidate_id in error.candidate_ids}
        ),
        error_class_codes=[
            code for error in underlying for code in error.error_class_codes
        ],
    )


def _valid_text() -> str:
    return _wire(candidate=_candidate()).model_dump_json()


def _transport(text: str, count: int) -> _FakeTransport:
    return _FakeTransport(
        [ProtocolControlAgentResponse(session_id="session-1", text=text) for _ in range(count)]
    )


def _multi_class_exhausting_validator() -> "object":
    """Calls 1..3 raise a shifting multi-class combined scope; never recovers."""

    state = {"calls": 0}

    def validate_after_hydration(output) -> None:
        state["calls"] += 1
        candidate_id = output.candidates[0].control_candidate_id
        if state["calls"] == 1:
            raise _combined(_class_a(candidate_id), _class_b(candidate_id))
        if state["calls"] == 2:
            raise _combined(_class_b(candidate_id))
        # A brand-new class appears after both budget-consuming rounds; the
        # contract forbids granting it an extra round.
        raise _combined(_class_c(candidate_id))

    return validate_after_hydration, state


def test_default_budget_is_global_not_per_error_class() -> None:
    """默认2次预算在全局多类错误之间共享，错误类转移不追加轮次。"""

    batch = _batch()
    transport = _transport(_valid_text(), 3)
    validate_after_hydration, state = _multi_class_exhausting_validator()

    result = ProtocolControlAgentRunner().run(
        batch,
        transport,
        output_validator=validate_after_hydration,
    )

    assert result.status == "需要核对"
    assert state["calls"] == 3
    assert len(result.attempts) == 3
    # One initial call plus exactly two repair rounds: no third round for the
    # new class that appeared on the final attempt.
    assert len(transport.prompts) == 3
    assert [attempt.outcome for attempt in result.attempts] == [
        "publication_invalid",
        "publication_invalid",
        "publication_invalid",
    ]
    # Per-attempt class accounting makes the exhaustion auditable class by
    # class: the combined scope shrinks and then a new class appears.
    assert result.attempts[0].error_classes == [
        "ACTION_TARGET_SCOPE_MISMATCH",
        "MIXED_DECISION_STAGE_CONTROL",
        "OUTPUT_VALIDATION_REJECTED",
    ]
    assert result.attempts[1].error_classes == [
        "MIXED_DECISION_STAGE_CONTROL",
        "OUTPUT_VALIDATION_REJECTED",
    ]
    assert result.attempts[2].error_classes == [
        "CONDITIONAL_EXEMPTION_BINDING_MISSING",
        "OUTPUT_VALIDATION_REJECTED",
    ]
    assert all(attempt.error_classes for attempt in result.attempts)
    assert result.final_output is None


def test_identical_multi_class_error_stops_on_no_progress_before_budget() -> None:
    """相同多类无效结果第二次出现即触发 no_progress，不消费剩余预算。"""

    batch = _batch()
    transport = _transport(_valid_text(), 3)
    validator_calls = 0

    def validate_after_hydration(output) -> None:
        nonlocal validator_calls
        validator_calls += 1
        candidate_id = output.candidates[0].control_candidate_id
        raise _combined(_class_a(candidate_id), _class_b(candidate_id))

    result = ProtocolControlAgentRunner(max_schema_repairs=10).run(
        batch,
        transport,
        output_validator=validate_after_hydration,
    )

    assert result.status == "需要核对"
    # Even with a budget of 10, the identical invalid result stops the loop
    # on its second occurrence: no infinite loop, no wasted repair rounds.
    assert validator_calls == 2
    assert len(result.attempts) == 2
    assert len(transport.prompts) == 2
    assert "停止自动修订" in result.attempts[-1].issues[-1]
    assert result.attempts[0].error_classes == result.attempts[1].error_classes == [
        "ACTION_TARGET_SCOPE_MISMATCH",
        "MIXED_DECISION_STAGE_CONTROL",
        "OUTPUT_VALIDATION_REJECTED",
    ]


def test_multi_class_serial_repairs_within_default_budget_succeed() -> None:
    """默认2次预算内串行修复两类错误可以成功。"""

    batch = _batch()
    transport = _transport(_valid_text(), 3)
    validator_calls = 0

    def validate_after_hydration(output) -> None:
        nonlocal validator_calls
        validator_calls += 1
        candidate_id = output.candidates[0].control_candidate_id
        if validator_calls == 1:
            raise _combined(_class_a(candidate_id), _class_b(candidate_id))
        if validator_calls == 2:
            raise _combined(_class_b(candidate_id))

    result = ProtocolControlAgentRunner().run(
        batch,
        transport,
        output_validator=validate_after_hydration,
    )

    assert result.status == "已解析"
    assert validator_calls == 3
    assert len(result.attempts) == 3
    assert len(transport.prompts) == 3
    assert [attempt.outcome for attempt in result.attempts] == [
        "publication_invalid",
        "publication_invalid",
        "parsed",
    ]
    assert result.attempts[0].error_classes == [
        "ACTION_TARGET_SCOPE_MISMATCH",
        "MIXED_DECISION_STAGE_CONTROL",
        "OUTPUT_VALIDATION_REJECTED",
    ]
    assert result.attempts[1].error_classes == [
        "MIXED_DECISION_STAGE_CONTROL",
        "OUTPUT_VALIDATION_REJECTED",
    ]
    assert result.attempts[2].error_classes == []
    assert result.final_output is not None


def test_same_transport_sequence_reproduces_invariant_result() -> None:
    """相同 transport 响应序列两次运行产生逐字段一致的不变输出。"""

    def make_run():
        batch = _batch()
        transport = _transport(_valid_text(), 3)
        validate_after_hydration, _ = _multi_class_exhausting_validator()
        result = ProtocolControlAgentRunner().run(
            batch,
            transport,
            output_validator=validate_after_hydration,
        )
        return result, transport.prompts

    first, prompts_a = make_run()
    second, prompts_b = make_run()

    assert first.status == "需要核对"
    # Harness-level determinism: same response sequence, identical result and
    # identical prompt sequence field for field.
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert prompts_a == prompts_b


def test_default_budget_is_explicit_and_guarded() -> None:
    """默认预算以显式常量声明，且保留非负校验。"""

    assert DEFAULT_MAX_SCHEMA_REPAIRS == 2
    assert DEFAULT_MAX_TRANSPORT_RETRIES == 1
    with pytest.raises(ValueError, match="重试上限必须为非负整数"):
        ProtocolControlAgentRunner(max_schema_repairs=-1)
    with pytest.raises(ValueError, match="重试上限必须为非负整数"):
        ProtocolControlAgentRunner(max_transport_retries=-1)
