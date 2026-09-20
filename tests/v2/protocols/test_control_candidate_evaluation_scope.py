"""Candidate atoms and formal control-wide time bindings are separate contracts."""
import pytest

from app.domain.contracts.control_evaluation_spec import (
    ControlAtomEvaluationSpec,
    validate_control_evaluations,
    validate_control_expression_evaluations,
)
from tests.v2.protocols.test_slice58c_protocol_control_gate import _candidate, _control


def test_candidate_without_formal_time_fields_still_checks_atom_specifications():
    candidate = _candidate().semantics
    assert not hasattr(candidate, "control_time_bindings")
    with pytest.raises(ValueError, match="控制原子尚未提供求值规格"):
        validate_control_expression_evaluations(candidate)


def test_candidate_with_explicit_atom_specification_can_be_checked():
    candidate = _candidate().semantics
    atom = candidate.obligation_expression.groups[0].atoms[0]
    atom.evaluation = ControlAtomEvaluationSpec(
        determination_mode="semantic",
        proposition=atom.statement,
        time_purpose="not_applicable",
        observation_policy={
            "mode": "unresolved",
            "scope": "尚待核实原文是否限定记录范围",
            "source_span_ids": atom.source_span_ids,
            "source_excerpts": atom.source_excerpts,
        },
        source_span_ids=atom.source_span_ids,
        source_excerpts=atom.source_excerpts,
    )
    validate_control_expression_evaluations(candidate)


def test_formal_control_still_rejects_unbound_control_wide_time_requirement():
    control = _control().model_copy(update={"control_time_constraint": object()})
    with pytest.raises(ValueError, match="控制级时间要求尚未明确对应条目"):
        validate_control_evaluations(control)
