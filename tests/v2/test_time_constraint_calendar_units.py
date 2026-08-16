from __future__ import annotations

from datetime import date

import pytest

from app.domain.contracts.common import DateValue
from app.domain.contracts.enums import (
    AnchorType,
    Comparator,
    DatePrecision,
    FactPolarity,
    TimeDirection,
    TruthValue,
)
from app.domain.contracts.evidence import ClinicalFact
from app.domain.contracts.rules import (
    AtomicExpression,
    AtomicPredicate,
    TimeConstraint,
    TimeQuantity,
    TimeUnit,
)
from app.domain.expression import EvaluationContext, evaluate_expression
from app.protocols.deconstruction_gate import ProtocolDeconstructionGate
from tests.v2.protocols.test_deconstruction_gate_slice3 import _fixture


def _evaluate(
    event_date: date,
    anchor_date: date,
    constraint: TimeConstraint,
    *,
    anchor_type: AnchorType = AnchorType.RANDOMIZATION_DATE,
):
    fact = ClinicalFact(
        fact_id="fact-time",
        project_id="project-1",
        subject_id="subject-1",
        review_episode_id="episode-1",
        evidence_snapshot_id="snapshot-1",
        fact_type="history.event_present",
        value=True,
        polarity=FactPolarity.AFFIRMED,
        certainty=1,
        effective_date=DateValue(value=event_date, precision=DatePrecision.DAY),
        evidence_span_ids=["span-time"],
    )
    expression = AtomicExpression(
        predicate=AtomicPredicate(
            predicate_id="predicate-time",
            subject="history",
            attribute="event_present",
            comparator=Comparator.EQ,
            value=True,
        ),
        time_constraint=constraint,
    )
    context = EvaluationContext(
        project_id="project-1",
        subject_id="subject-1",
        review_episode_id="episode-1",
        evidence_snapshot_id="snapshot-1",
        accepted_fact_ids=["fact-time"],
        facts=[fact],
        anchor_dates={
            anchor_type: DateValue(
                value=anchor_date,
                precision=DatePrecision.DAY,
            )
        },
    )
    return evaluate_expression(expression, context)


def _before(**bounds) -> TimeConstraint:
    return TimeConstraint(
        anchor_type=AnchorType.RANDOMIZATION_DATE,
        direction=TimeDirection.BEFORE,
        **bounds,
    )


def _after(**bounds) -> TimeConstraint:
    return TimeConstraint(
        anchor_type=AnchorType.RANDOMIZATION_DATE,
        direction=TimeDirection.AFTER,
        **bounds,
    )


def test_first_dose_anchor_is_evaluated_independently() -> None:
    constraint = TimeConstraint(
        anchor_type=AnchorType.FIRST_DOSE_DATE,
        direction=TimeDirection.BEFORE,
        upper_bound=TimeQuantity(value=7, unit=TimeUnit.DAY),
    )

    result = _evaluate(
        date(2026, 8, 8),
        date(2026, 8, 15),
        constraint,
        anchor_type=AnchorType.FIRST_DOSE_DATE,
    )

    assert result.truth == TruthValue.TRUE


def test_month_quantity_uses_calendar_month_end_not_fixed_days() -> None:
    result = _evaluate(
        date(2024, 1, 31),
        date(2024, 2, 29),
        _before(lower_bound=TimeQuantity(value=1, unit=TimeUnit.MONTH)),
    )

    assert result.truth == TruthValue.TRUE


def test_year_quantity_handles_leap_day_and_rejects_365_day_shortcut() -> None:
    exact_calendar_year = _evaluate(
        date(2023, 2, 28),
        date(2024, 2, 29),
        _before(lower_bound=TimeQuantity(value=1, unit=TimeUnit.YEAR)),
    )
    one_day_short_of_calendar_boundary = _evaluate(
        date(2023, 3, 1),
        date(2024, 2, 29),
        _before(lower_bound=TimeQuantity(value=1, unit=TimeUnit.YEAR)),
    )

    assert exact_calendar_year.truth == TruthValue.TRUE
    assert one_day_short_of_calendar_boundary.truth == TruthValue.FALSE


def test_four_weeks_is_exactly_twenty_eight_days() -> None:
    result = _evaluate(
        date(2024, 2, 1),
        date(2024, 2, 29),
        _before(lower_bound=TimeQuantity(value=4, unit=TimeUnit.WEEK)),
    )

    assert result.truth == TruthValue.TRUE


def test_three_months_is_not_ninety_days() -> None:
    calendar_result = _evaluate(
        date(2024, 3, 1),
        date(2024, 5, 31),
        _before(lower_bound=TimeQuantity(value=3, unit=TimeUnit.MONTH)),
    )
    fixed_day_result = _evaluate(
        date(2024, 3, 1),
        date(2024, 5, 31),
        _before(lower_bound_days=90),
    )

    assert calendar_result.truth == TruthValue.FALSE
    assert fixed_day_result.truth == TruthValue.TRUE


def test_after_direction_uses_the_same_calendar_boundary_semantics() -> None:
    exact = _evaluate(
        date(2024, 2, 29),
        date(2024, 1, 31),
        _after(lower_bound=TimeQuantity(value=1, unit=TimeUnit.MONTH)),
    )
    too_early = _evaluate(
        date(2024, 2, 28),
        date(2024, 1, 31),
        _after(lower_bound=TimeQuantity(value=1, unit=TimeUnit.MONTH)),
    )

    assert exact.truth == TruthValue.TRUE
    assert too_early.truth == TruthValue.FALSE


def test_calendar_upper_bound_rejects_dates_beyond_the_window() -> None:
    inside = _evaluate(
        date(2024, 1, 31),
        date(2024, 2, 29),
        _before(upper_bound=TimeQuantity(value=1, unit=TimeUnit.MONTH)),
    )
    outside = _evaluate(
        date(2024, 1, 30),
        date(2024, 3, 1),
        _before(upper_bound=TimeQuantity(value=1, unit=TimeUnit.MONTH)),
    )

    assert inside.truth == TruthValue.TRUE
    assert outside.truth == TruthValue.FALSE


def test_legacy_twenty_eight_day_constraint_remains_compatible() -> None:
    result = _evaluate(
        date(2024, 2, 1),
        date(2024, 2, 29),
        _before(lower_bound_days=28),
    )

    assert result.truth == TruthValue.TRUE


def test_partial_calendar_date_is_unknown_even_when_partial_dates_are_allowed() -> None:
    fact = ClinicalFact(
        fact_id="fact-partial-time",
        project_id="project-1",
        subject_id="subject-1",
        review_episode_id="episode-1",
        evidence_snapshot_id="snapshot-1",
        fact_type="history.event_present",
        value=True,
        polarity=FactPolarity.AFFIRMED,
        certainty=1,
        effective_date=DateValue(
            value=date(2024, 1, 1),
            precision=DatePrecision.MONTH,
        ),
        evidence_span_ids=["span-time"],
    )
    expression = AtomicExpression(
        predicate=AtomicPredicate(
            predicate_id="predicate-partial-time",
            subject="history",
            attribute="event_present",
            comparator=Comparator.EQ,
            value=True,
        ),
        time_constraint=_before(
            lower_bound=TimeQuantity(value=1, unit=TimeUnit.MONTH),
            allow_partial_date=True,
        ),
    )
    context = EvaluationContext(
        project_id="project-1",
        subject_id="subject-1",
        review_episode_id="episode-1",
        evidence_snapshot_id="snapshot-1",
        accepted_fact_ids=["fact-partial-time"],
        facts=[fact],
        anchor_dates={
            AnchorType.RANDOMIZATION_DATE: DateValue(
                value=date(2024, 2, 15), precision=DatePrecision.DAY
            )
        },
    )

    result = evaluate_expression(expression, context)

    assert result.truth == TruthValue.UNKNOWN
    assert "ambiguous_partial_date" in result.reason_codes


def test_partial_calendar_date_is_definitive_when_the_whole_interval_agrees() -> None:
    fact = ClinicalFact(
        fact_id="fact-partial-definitive",
        project_id="project-1",
        subject_id="subject-1",
        review_episode_id="episode-1",
        evidence_snapshot_id="snapshot-1",
        fact_type="history.event_present",
        value=True,
        polarity=FactPolarity.AFFIRMED,
        certainty=1,
        effective_date=DateValue(
            value=date(2023, 1, 1),
            precision=DatePrecision.MONTH,
        ),
        evidence_span_ids=["span-time"],
    )
    expression = AtomicExpression(
        predicate=AtomicPredicate(
            predicate_id="predicate-partial-definitive",
            subject="history",
            attribute="event_present",
            comparator=Comparator.EQ,
            value=True,
        ),
        time_constraint=_before(
            lower_bound=TimeQuantity(value=12, unit=TimeUnit.MONTH),
            allow_partial_date=True,
        ),
    )
    context = EvaluationContext(
        project_id="project-1",
        subject_id="subject-1",
        review_episode_id="episode-1",
        evidence_snapshot_id="snapshot-1",
        accepted_fact_ids=["fact-partial-definitive"],
        facts=[fact],
        anchor_dates={
            AnchorType.RANDOMIZATION_DATE: DateValue(
                value=date(2024, 3, 1), precision=DatePrecision.DAY
            )
        },
    )

    result = evaluate_expression(expression, context)

    assert result.truth == TruthValue.TRUE


def test_time_quantity_schema_round_trip_and_legacy_days() -> None:
    calendar_constraint = _before(
        lower_bound=TimeQuantity(value=3, unit=TimeUnit.MONTH),
        upper_bound=TimeQuantity(value=6, unit=TimeUnit.MONTH),
    )
    round_tripped = TimeConstraint.model_validate_json(
        calendar_constraint.model_dump_json()
    )
    legacy_constraint = TimeConstraint.model_validate(
        {
            "anchor_type": "randomization_date",
            "direction": "before",
            "lower_bound_days": 28,
        }
    )

    assert round_tripped == calendar_constraint
    assert round_tripped.lower_bound == TimeQuantity(value=3, unit=TimeUnit.MONTH)
    assert legacy_constraint.lower_bound_days == 28


def test_time_constraint_rejects_duplicate_boundary_and_on_boundary() -> None:
    duplicate = {
        "anchor_type": "randomization_date",
        "direction": "before",
        "lower_bound_days": 28,
        "lower_bound": {"value": 4, "unit": "week"},
    }
    on_with_quantity = {
        "anchor_type": "randomization_date",
        "direction": "on",
        "lower_bound": {"value": 1, "unit": "month"},
    }

    with pytest.raises(ValueError, match="同时使用"):
        TimeConstraint.model_validate(duplicate)
    with pytest.raises(ValueError, match="on 仅表示"):
        TimeConstraint.model_validate(on_with_quantity)


@pytest.mark.parametrize("value", [0, -1, 1.5, True])
def test_time_quantity_requires_a_positive_integer(value) -> None:
    with pytest.raises(ValueError):
        TimeQuantity(value=value, unit=TimeUnit.MONTH)


def test_gate_accepts_three_months_only_when_month_unit_is_preserved() -> None:
    source_input, draft, spans = _fixture()
    source_input.parent_rule_catalog = source_input.parent_rule_catalog.model_copy(
        update={
            "items": (
                source_input.parent_rule_catalog.items[0].model_copy(
                    update={"label": "随机前3个月内年龄≥18岁"}
                ),
                source_input.parent_rule_catalog.items[1],
            )
        }
    )
    source_input.source_materials[0].text = "随机前3个月内年龄≥18岁"
    draft.component_drafts[0].source_excerpts = ["随机前3个月内年龄≥18岁"]
    draft.proposed_rules[0].components[0].expression.predicate.source_clause = (
        "随机前3个月内年龄≥18岁"
    )
    draft.proposed_rules[0].components[0].expression.time_constraint = _before(
        lower_bound=TimeQuantity(value=3, unit=TimeUnit.MONTH)
    )

    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )

    temporal = next(item for item in result.checks if item.check_name == "temporal_semantics")
    assert result.publishable
    assert not any(item.issue_code == "TIME_BOUND_UNIT_CHANGED" for item in temporal.issues)


def test_gate_blocks_ninety_days_for_a_three_month_source_window() -> None:
    source_input, draft, spans = _fixture()
    source_input.parent_rule_catalog = source_input.parent_rule_catalog.model_copy(
        update={
            "items": (
                source_input.parent_rule_catalog.items[0].model_copy(
                    update={"label": "随机前3个月内年龄≥18岁"}
                ),
                source_input.parent_rule_catalog.items[1],
            )
        }
    )
    source_input.source_materials[0].text = "随机前3个月内年龄≥18岁"
    draft.component_drafts[0].source_excerpts = ["随机前3个月内年龄≥18岁"]
    draft.proposed_rules[0].components[0].expression.predicate.source_clause = (
        "随机前3个月内年龄≥18岁"
    )
    draft.proposed_rules[0].components[0].expression.time_constraint = _before(
        lower_bound_days=90
    )

    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )

    temporal = next(item for item in result.checks if item.check_name == "temporal_semantics")
    assert not result.publishable
    assert not temporal.passed
    assert any(item.issue_code == "TIME_BOUND_UNIT_CHANGED" for item in temporal.issues)


def test_gate_can_prove_four_weeks_equals_twenty_eight_days() -> None:
    source_input, draft, spans = _fixture()
    source_input.parent_rule_catalog = source_input.parent_rule_catalog.model_copy(
        update={
            "items": (
                source_input.parent_rule_catalog.items[0].model_copy(
                    update={"label": "随机前4周内年龄≥18岁"}
                ),
                source_input.parent_rule_catalog.items[1],
            )
        }
    )
    source_input.source_materials[0].text = "随机前4周内年龄≥18岁"
    draft.component_drafts[0].source_excerpts = ["随机前4周内年龄≥18岁"]
    draft.proposed_rules[0].components[0].expression.predicate.source_clause = (
        "随机前4周内年龄≥18岁"
    )
    draft.proposed_rules[0].components[0].expression.time_constraint = _before(
        lower_bound_days=28
    )

    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )

    temporal = next(item for item in result.checks if item.check_name == "temporal_semantics")
    assert temporal.passed


def test_gate_blocks_screening_procedure_mapped_to_baseline_stage() -> None:
    source_input, draft, spans = _fixture()
    draft.procedure_catalog_mappings[0].proposed_workflow_stage_id = "stage-baseline"

    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )

    workflow = next(item for item in result.checks if item.check_name == "workflow_coverage")
    assert any(
        item.issue_code == "PROCEDURE_REVIEW_STAGE_MISMATCH"
        for item in workflow.issues
    )
