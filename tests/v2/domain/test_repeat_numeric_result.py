"""Shared exact arithmetic for verified acquisition groups."""

from datetime import date
from fractions import Fraction

from app.domain.contracts.common import DateValue
from app.domain.contracts.enums import DatePrecision, FactPolarity
from app.domain.contracts.evidence import ClinicalFact
from app.domain.expression import EvaluationContext
from app.domain.observation_relation_graph import analyze_observation_appearances, observation_appearance_id
from app.domain.publication import canonical_hash
from app.domain.repeat_numeric_result import aggregate_numeric_acquisitions, calculate_repeat_numeric_result
from app.domain.repeat_result_selection import RepeatResultSelection, select_repeat_result_groups
from app.domain.contracts.repeat_scheme import RepeatScheme


def _fact(identifier: str, value: float, *, unit: str = "分", polarity=FactPolarity.AFFIRMED):
    return ClinicalFact(
        fact_id=identifier, project_id="p", subject_id="s", review_episode_id="e",
        evidence_snapshot_id="snap", fact_type="量表得分", value=value, unit=unit,
        polarity=polarity, certainty=1, effective_date=DateValue(
            value=date(2026, 9, 1), precision=DatePrecision.DAY,
        ), evidence_span_ids=[identifier],
    )


def test_independent_equal_acquisitions_are_not_deduplicated():
    value, unit, reasons = aggregate_numeric_acquisitions(
        [[_fact("a", 2), _fact("a-copy", 2)], [_fact("b", 2)], [_fact("c", 5)]],
        operation="mean", unit_required=True,
    )
    assert (value, unit, reasons) == (Fraction(3), "分", ())


def test_one_fact_cannot_be_counted_as_two_acquisitions():
    first = _fact("same-source", 2)
    assert aggregate_numeric_acquisitions(
        [[first], [first], [_fact("independent-source", 5)]],
        operation="mean", unit_required=True,
    ) == (None, None, ("repeat_result_acquisition_overlap",))


def test_conflicting_same_acquisition_and_mixed_units_stay_unresolved():
    assert aggregate_numeric_acquisitions(
        [[_fact("a", 2), _fact("a-copy", 3)]], operation="mean", unit_required=True,
    )[2] == ("repeat_same_acquisition_value_conflict",)
    assert aggregate_numeric_acquisitions(
        [[_fact("a", 2)], [_fact("b", 2, unit="mg")]], operation="mean", unit_required=True,
    )[2] == ("repeat_result_unit_unverified",)


def test_unsupported_operation_and_empty_scope_do_not_produce_value():
    assert aggregate_numeric_acquisitions([], operation="mean", unit_required=True) == (
        None, None, ("repeat_result_missing",),
    )
    assert aggregate_numeric_acquisitions(
        [[_fact("a", 2)]], operation="median", unit_required=True,
    )[2] == ("repeat_result_combination_unverified",)


def test_reused_fact_needs_a_quoted_repeat_chain_and_qualified_source_positions():
    fact = _fact("same", 2)
    appearances = [
        {"fact_id": "same", "locator_id": locator,
         "appearance_id": observation_appearance_id("same", locator)}
        for locator in ("first", "later")
    ]
    graph = analyze_observation_appearances(
        appearances,
        [("repeat_of", appearances[1]["appearance_id"],
          appearances[0]["appearance_id"], "initial_observation")],
        origins={appearances[0]["appearance_id"]: "initial",
                 appearances[1]["appearance_id"]: "repeat"},
    )
    scheme = RepeatScheme(
        scope="本次筛选", source_span_ids=["p"], source_excerpts=["复查取均值"],
        permission="required", trigger="unconditional", count_status="not_specified",
        time_status="not_specified", result_use="combine", result_combine="mean",
        result_population="initial_and_repeats",
    )
    roles = {item["role"]: item["group_id"] for item in graph["acquisition_roles"]}
    selected = select_repeat_result_groups(
        scheme, graph, initial_group_id=roles["initial"],
        repeat_group_ids=(roles["repeat"],), scope_complete=True,
        supplied_scope_sha256="a" * 64, initial_scope_complete=True,
    )
    assert selected.reason_codes == ()
    assert set(selected.selected_group_ids) == set(roles.values())
    context = EvaluationContext(
        project_id="p", subject_id="s", review_episode_id="e",
        evidence_snapshot_id="snap", accepted_fact_ids=["same"], facts=[fact],
    )

    def calculate(source_ids, current_graph=graph):
        current_selection = selected if current_graph is graph else RepeatResultSelection(
            graph_sha256=current_graph["graph_sha256"],
            scheme_sha256=selected.scheme_sha256,
            supplied_scope_sha256=selected.supplied_scope_sha256,
            considered_group_ids=tuple(item["group_id"] for item in current_graph["acquisition_groups"]),
            selected_group_ids=tuple(item["group_id"] for item in current_graph["acquisition_groups"]),
            combination="mean",
        )
        return calculate_repeat_numeric_result(
            current_selection, current_graph, context, scheme=scheme,
            qualified_value_fact_ids=frozenset({"same"}),
            qualified_value_appearance_ids=frozenset(source_ids),
        )

    assert calculate({item["appearance_id"] for item in appearances}).value == Fraction(2)
    assert calculate({appearances[0]["appearance_id"]}).reason_codes == (
        "repeat_result_value_unverified",
    )
    unlinked = analyze_observation_appearances(appearances, [])
    assert calculate({item["appearance_id"] for item in appearances}, unlinked).reason_codes == (
        "repeat_acquisition_identity_unverified",
    )
