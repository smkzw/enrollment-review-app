from types import SimpleNamespace

from app.domain.contracts.enums import TruthValue
from app.domain.expression import EvaluationResult
from app.projections.control_calculation_experiment import _proposition_observation


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
    assert reasons == ["interval_condition_requires_scope_review"]


def test_semantic_interval_still_uses_source_bound_proposition_when_time_is_valid():
    assert _read(
        time_purpose="interval_condition",
        time_truth=TruthValue.TRUE,
        relation="contradicts_agreed",
    )[0] == TruthValue.FALSE
    assert _read(
        time_purpose="interval_condition",
        time_truth=TruthValue.TRUE,
        relation="entails_agreed",
    )[0] == TruthValue.TRUE
