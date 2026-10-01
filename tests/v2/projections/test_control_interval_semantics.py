from types import SimpleNamespace
from datetime import date

import pytest

from app.domain.contracts.common import DateValue
from app.domain.contracts.control_evaluation_spec import ControlAtomEvaluationSpec
from app.domain.contracts.facts import PartialDateRange
from app.domain.contracts.protocol_controls import ControlConditionAtom
from app.domain.contracts.rules import TimeConstraint
from app.domain.contracts.enums import TruthValue
from app.domain.expression import EvaluationResult
from app.projections.control_calculation_experiment import (
    ControlCalculationExperiment, _conditional_observation, _proposition_observation,
)
from app.projections.control_operand_calculation import _calculate_operand


def _read(*, time_purpose: str, time_truth: TruthValue, relation: str):
    atom = SimpleNamespace(
        evaluation=SimpleNamespace(time_purpose=time_purpose, observation_policy=None),
        time_constraint=object(),
        prospective_period=None,
    )
    calculation = SimpleNamespace(
        unresolved_reason=None,
        time_result=EvaluationResult(truth=time_truth, reason_codes=["outside_window"]),
    )
    return _proposition_observation(atom, [{"status": relation}], calculation)


def test_semantic_interval_outside_window_does_not_disprove_continuous_completion():
    truth, reasons = _read(
        time_purpose="interval_condition",
        time_truth=TruthValue.FALSE,
        relation="entails_agreed",
    )
    assert truth == TruthValue.UNKNOWN
    assert reasons == ["interval_calculation_unsupported"]


@pytest.mark.parametrize("time_truth", list(TruthValue))
@pytest.mark.parametrize("relation", ["entails_agreed", "contradicts_agreed"])
def test_semantic_interval_cannot_be_certified_by_a_single_date(time_truth, relation):
    assert _read(
        time_purpose="interval_condition",
        time_truth=time_truth,
        relation=relation,
    ) == (TruthValue.UNKNOWN, ["interval_calculation_unsupported"])


@pytest.mark.parametrize("relation,expected", [
    ("entails_agreed", TruthValue.TRUE), ("contradicts_agreed", TruthValue.FALSE),
])
def test_source_bound_semantic_statement_without_separate_calendar_constraint_is_retained(relation, expected):
    atom = SimpleNamespace(
        evaluation=SimpleNamespace(time_purpose="not_applicable", observation_policy=None),
        time_constraint=None, prospective_period=None,
    )
    assert _proposition_observation(atom, [{"status": relation}], None)[0] == expected


def _operand(purpose, *, mode="semantic", event=date(2026, 8, 29)):
    quote = "核对本节点所需的时间要求"
    constraint = TimeConstraint(anchor_type="screening_date", direction="before", upper_bound_days=7)
    spec = ControlAtomEvaluationSpec(
        determination_mode=mode, proposition=quote,
        operation="time_constraint" if mode == "deterministic" else None,
        operand_attribute="date_range" if mode == "deterministic" else None,
        time_operand_attribute="date_range" if mode == "semantic" else None,
        time_purpose=purpose, source_span_ids=["s1"], source_excerpts=[quote],
    )
    atom = ControlConditionAtom(
        condition_atom_id="a1", statement=quote, evaluation=spec,
        source_span_ids=["s1"], source_excerpts=[quote], time_constraint=constraint,
    )
    frozen = SimpleNamespace(
        frozen_input_sha256="a" * 64,
        evidence_input=SimpleNamespace(episode=SimpleNamespace(
            anchor_dates={constraint.anchor_type: DateValue(value=date(2026, 9, 1), precision="day")},
        )),
    )
    fact = SimpleNamespace(
        fact_id="f1", locator_ids=["l1"],
        date_range=PartialDateRange(precision="day", lower_bound=event, upper_bound=event),
    )
    return atom, _calculate_operand(
        frozen, identity=SimpleNamespace(identity_sha256="b" * 64, atom=atom),
        fact=fact, anchors_sha256="c" * 64,
    )


@pytest.mark.parametrize("mode", ["semantic", "deterministic"])
def test_real_operand_path_does_not_treat_event_precision_as_exposure_interval(mode):
    atom, result = _operand("interval_condition", mode=mode)
    assert result.accepted is False
    assert result.time_result.truth == TruthValue.UNKNOWN
    assert result.time_result.reason_codes == ["interval_calculation_unsupported"]
    if mode == "deterministic":
        assert _conditional_observation(atom, result) == (
            TruthValue.UNKNOWN, ["interval_calculation_unsupported"],
        )


@pytest.mark.parametrize("purpose", ["event_membership", "source_validity"])
@pytest.mark.parametrize("event,truth", [
    (date(2026, 8, 29), TruthValue.TRUE), (date(2026, 8, 1), TruthValue.FALSE),
])
def test_event_membership_and_report_validity_calculations_are_unchanged(purpose, event, truth):
    _, result = _operand(purpose, event=event)
    assert result.time_result.truth == truth


@pytest.mark.parametrize("truth", [TruthValue.TRUE, TruthValue.FALSE])
def test_deterministic_consumer_rejects_legacy_point_result_as_duration(truth):
    atom, result = _operand("interval_condition", mode="deterministic")
    legacy = result.model_copy(update={"time_result": EvaluationResult(truth=truth)})
    assert _conditional_observation(atom, legacy) == (
        TruthValue.UNKNOWN, ["interval_calculation_unsupported"],
    )


def test_new_calculation_identity_preserves_readable_old_receipts():
    material = dict(frozen_input_sha256="a" * 64, selections_sha256="b" * 64, layers=[], calculations=[])
    assert ControlCalculationExperiment(**material).version == "control-calculation-experiment/v16"
    old = ControlCalculationExperiment(version="control-calculation-experiment/v15", **material)
    assert old.model_dump(mode="json")["version"] == "control-calculation-experiment/v15"
