from __future__ import annotations

import copy
import json

import pytest

from app.agents.protocol_deconstructor import (
    DNF_WIRE_ERROR_CODES,
    DNF_WIRE_MAX_GROUPS,
    ProtocolWireError,
    _parse_semantic_candidate,
)
from app.domain.contracts.enums import LogicalOperator
from app.domain.contracts.rules import iter_atomic_predicates

from .test_slice58_dnf_wire_contract import _atom, _payload


def _parse(payload: dict[str, object]):
    return _parse_semantic_candidate(
        json.dumps(payload, ensure_ascii=False),
        compact=True,
        expected_batch_id="1/1",
    )


def _group(*atoms: dict[str, object]) -> dict[str, object]:
    return {
        "existence_atoms": list(atoms),
        "scalar_atoms": [],
        "set_atoms": [],
    }


def test_hydration_preserves_negation_as_not_without_comparator_inversion():
    payload = _payload()
    component = payload["proposed_rules"][0]["components"][0]
    negated = {
        **_atom(attribute="年龄", negated=True, source_clause="年龄不满足"),
        "comparator": "gte",
        "value": 18,
        "unit": "岁",
        "source_term": "年龄",
        "time_constraint": {
            "anchor_type": "screening_date",
            "direction": "before",
            "lower_bound": None,
            "upper_bound": {"value": 4, "unit": "week"},
            "allow_partial_date": True,
        },
    }
    component["expression"] = [
        {"existence_atoms": [], "scalar_atoms": [negated], "set_atoms": []}
    ]

    expression = _parse(payload).proposed_rules[0].components[0].expression

    assert expression.kind == "logical"
    assert expression.operator == LogicalOperator.NOT
    inner = expression.children[0]
    assert inner.kind == "predicate"
    assert inner.predicate.comparator.value == "gte"
    assert inner.predicate.value == 18
    assert inner.predicate.unit == "岁"
    assert inner.time_constraint is not None
    assert inner.time_constraint.anchor_type.value == "screening_date"
    assert inner.time_constraint.upper_bound is not None
    assert inner.time_constraint.upper_bound.value == 4
    assert inner.time_constraint.upper_bound.unit.value == "week"


def test_hydration_keeps_direct_all_any_shapes_and_nested_source_windows():
    payload = _payload()
    component = payload["proposed_rules"][0]["components"][0]
    first = {
        **_atom(attribute="病程", negated=False),
        "occurrence_window": {
            "duration": {"value": 12, "unit": "month"},
            "minimum_count": 2,
        },
        "source_locator": {"source_clauses": ["既往", "2次"]},
    }
    second = {
        **_atom(attribute="治疗", negated=True, source_clause="未接受治疗"),
        "prospective_window": {
            "anchor_type": "last_dose_date",
            "upper_bound": {"value": 4, "unit": "week"},
        },
        "prospective_period": {"period": "study_period"},
    }
    third = _atom(attribute="既往手术")
    component["source_excerpts"] = ["既往病程或既往手术；未接受治疗"]
    component["expression"] = [_group(first, second), _group(third)]
    component["exception_expression"] = [_group(_atom(attribute="例外"))]

    hydrated = _parse(payload).proposed_rules[0].components[0]
    assert hydrated.expression.kind == "logical"
    assert hydrated.expression.operator == LogicalOperator.ANY
    assert hydrated.expression.children[0].operator == LogicalOperator.ALL
    assert hydrated.exception_expression is not None
    assert hydrated.exception_expression.kind == "predicate"

    predicates = list(iter_atomic_predicates(hydrated.expression))
    occurrence = next(item for item in predicates if item.attribute == "病程")
    future = next(item for item in predicates if item.attribute == "治疗")
    assert occurrence.source_clauses == ["既往", "2次"]
    assert occurrence.occurrence_window is not None
    assert occurrence.occurrence_window.duration.value == 12
    assert occurrence.occurrence_window.duration.unit.value == "month"
    assert occurrence.occurrence_window.minimum_count == 2
    assert future.prospective_window is not None
    assert future.prospective_window.anchor_type.value == "last_dose_date"
    assert future.prospective_period is not None
    assert future.prospective_period.period.value == "study_period"


def test_system_predicate_identity_is_order_stable_and_scope_unique():
    payload = _payload()
    component = payload["proposed_rules"][0]["components"][0]
    component["source_excerpts"] = ["共同条件或分支一或分支二"]
    repeated = _atom(attribute="共同条件")
    component["expression"] = [
        _group(repeated, _atom(attribute="分支一")),
        _group(copy.deepcopy(repeated), _atom(attribute="分支二")),
    ]
    component["exception_expression"] = [_group(copy.deepcopy(repeated))]

    first = _parse(payload).proposed_rules[0].components[0]
    reordered = copy.deepcopy(payload)
    groups = reordered["proposed_rules"][0]["components"][0]["expression"]
    groups.reverse()
    groups[0]["existence_atoms"].reverse()
    second = _parse(reordered).proposed_rules[0].components[0]

    first_trigger_ids = sorted(
        item.predicate_id for item in iter_atomic_predicates(first.expression)
    )
    second_trigger_ids = sorted(
        item.predicate_id for item in iter_atomic_predicates(second.expression)
    )
    first_exception_ids = {
        item.predicate_id
        for item in iter_atomic_predicates(first.exception_expression)
    }
    assert first_trigger_ids == second_trigger_ids
    assert len(first_trigger_ids) == len(set(first_trigger_ids))
    assert first_exception_ids.isdisjoint(first_trigger_ids)
    assert all("__wire_atom__" not in item for item in first_trigger_ids)


def test_source_clause_order_is_preserved_in_predicate_identity():
    payload = _payload()
    component = payload["proposed_rules"][0]["components"][0]
    atom = _atom(attribute="顺序敏感来源")
    atom["source_locator"] = {"source_clauses": ["上位限定语", "结尾条件"]}
    component["expression"] = [_group(atom)]

    first = _parse(payload).proposed_rules[0].components[0]
    first_predicate = next(iter_atomic_predicates(first.expression))

    reversed_payload = copy.deepcopy(payload)
    reversed_atom = reversed_payload["proposed_rules"][0]["components"][0][
        "expression"
    ][0]["existence_atoms"][0]
    reversed_atom["source_locator"]["source_clauses"].reverse()
    second = _parse(reversed_payload).proposed_rules[0].components[0]
    second_predicate = next(iter_atomic_predicates(second.expression))

    assert first_predicate.source_clauses == ["上位限定语", "结尾条件"]
    assert second_predicate.source_clauses == ["结尾条件", "上位限定语"]
    assert first_predicate.predicate_id != second_predicate.predicate_id


def test_hydration_leaves_negation_semantics_for_the_formal_gate():
    payload = _payload()
    atom = _atom(attribute="年龄", negated=True)
    atom.update(
        {
            "comparator": "gte",
            "value": 18,
            "unit": "岁",
            "source_term": "年龄",
        }
    )
    payload["proposed_rules"][0]["components"][0]["expression"] = [
        {"existence_atoms": [], "scalar_atoms": [atom], "set_atoms": []}
    ]

    expression = _parse(payload).proposed_rules[0].components[0].expression
    assert expression.kind == "logical"
    assert expression.operator == LogicalOperator.NOT


def test_hydration_leaves_alternative_semantics_for_the_formal_gate():
    payload = _payload()
    component = payload["proposed_rules"][0]["components"][0]
    component["expression"] = [
        _group(_atom(attribute="目标疾病")),
        _group(_atom(attribute="年龄")),
    ]

    expression = _parse(payload).proposed_rules[0].components[0].expression
    assert expression.kind == "logical"
    assert expression.operator == LogicalOperator.ANY


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        ("empty", DNF_WIRE_ERROR_CODES["empty_group"]),
        ("duplicate_atom", DNF_WIRE_ERROR_CODES["duplicate_atom"]),
        ("duplicate_group", DNF_WIRE_ERROR_CODES["duplicate_group"]),
        ("legacy", DNF_WIRE_ERROR_CODES["legacy_graph_field"]),
        ("complex", DNF_WIRE_ERROR_CODES["complexity_limit"]),
    ],
)
def test_dnf_rejections_expose_stable_internal_codes(mutation: str, code: str):
    payload = _payload()
    component = payload["proposed_rules"][0]["components"][0]
    if mutation == "empty":
        component["expression"] = [_group()]
    elif mutation == "duplicate_atom":
        atom = _atom(attribute="重复")
        component["expression"] = [_group(atom, copy.deepcopy(atom))]
    elif mutation == "duplicate_group":
        group = _group(_atom(attribute="重复组"))
        component["expression"] = [group, copy.deepcopy(group)]
    elif mutation == "legacy":
        component["root_node_id"] = "old-root"
    else:
        component["expression"] = [
            _group(*[_atom(attribute=f"a-{index}") for index in range(65)])
        ]

    with pytest.raises(ProtocolWireError) as caught:
        _parse(payload)
    assert caught.value.code == code


def test_dnf_schema_complexity_is_rejected_without_truncation():
    payload = _payload()
    component = payload["proposed_rules"][0]["components"][0]
    component["expression"] = [
        _group(_atom(attribute=f"group-{index}"))
        for index in range(DNF_WIRE_MAX_GROUPS + 1)
    ]
    with pytest.raises(ProtocolWireError) as caught:
        _parse(payload)
    assert caught.value.code == DNF_WIRE_ERROR_CODES["complexity_limit"]
    assert len(component["expression"]) == DNF_WIRE_MAX_GROUPS + 1
