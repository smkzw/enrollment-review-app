from __future__ import annotations

import copy
import json

import pytest
from jsonschema import Draft202012Validator

from app.agents.protocol_deconstructor import (
    DNF_WIRE_ERROR_CODES,
    ProtocolWireError,
    _parse_semantic_candidate,
    _parse_semantic_repair,
    build_protocol_deconstruction_prompt,
    protocol_output_response_format,
)
from app.domain.contracts.enums import LogicalOperator
from tests.v2.protocols.test_deconstruction_gate_slice3 import _fixture


def _schema(kind: str = "semantic_candidate") -> dict[str, object]:
    return protocol_output_response_format(kind, compact=True)["json_schema"][
        "schema"
    ]


def _atom(
    *,
    attribute: str,
    negated: bool = False,
    source_clause: str | None = None,
) -> dict[str, object]:
    return {
        "subject": "受试者",
        "attribute": attribute,
        "source_locator": {
            "source_clause": source_clause if source_clause is not None else attribute
        },
        "requires_professional_judgment": False,
        "negated": negated,
    }


def _payload(*, repair: bool = False) -> dict[str, object]:
    group = {
        "existence_atoms": [_atom(attribute="目标疾病")],
        "scalar_atoms": [
            {
                **_atom(attribute="年龄"),
                "comparator": "gte",
                "value": 18,
                "unit": "岁",
                "source_term": "年龄",
            }
        ],
        "set_atoms": [
            {
                **_atom(attribute="分型"),
                "comparator": "in",
                "values": ["A", "B"],
                "unit": "unitless",
            }
        ],
    }
    rule = {
        "official_code": "IN-01",
        "components": [
            {
                "title": "目标人群",
                "expression": [group],
                "exception_expression": None,
                "evidence_requirements": [
                    {
                        "fact_type": "目标疾病",
                        "due_stage": "screening",
                        "description": "核对目标疾病资料",
                    }
                ],
                "source_span_ids": ["span-1"],
                "source_excerpts": ["目标疾病"],
            }
        ],
    }
    payload = {
        "wire_version": "dnf-v1",
        "candidate_id": "candidate-1",
        "batch_id": "1/1",
    }
    if repair:
        payload["replacement_rules"] = [rule]
        payload["replacement_structural_warnings"] = []
        payload["replacement_unresolved_items"] = []
    else:
        payload["proposed_rules"] = [rule]
        payload["structural_warnings"] = []
        payload["unresolved_items"] = []
        payload["created_by_agent_call_id"] = "call-1"
    return payload


def test_compact_candidate_and_repair_schema_are_versioned_reference_free_dnf():
    candidate_schema = _schema()
    repair_schema = _schema("semantic_rule_repair")

    for schema in (candidate_schema, repair_schema):
        serialized = json.dumps(schema, ensure_ascii=False)
        assert schema["properties"]["wire_version"] == {"const": "dnf-v1"}
        assert "wire_dnf_group" in schema["$defs"]
        assert all(
            forbidden not in serialized
            for forbidden in (
                "node_id",
                "children",
                "root_node_id",
                "predicate_id",
                "not_logical_nodes",
                "all_any_logical_nodes",
            )
        )

    candidate_component = candidate_schema["$defs"]["wire_dnf_group"]
    repair_component = repair_schema["$defs"]["wire_dnf_group"]
    assert candidate_component == repair_component


@pytest.mark.parametrize("kind", ["semantic_candidate", "semantic_rule_repair"])
def test_dnf_hydration_rejects_empty_groups_and_requires_null_for_no_exception(
    kind: str,
):
    payload = _payload(repair=kind == "semantic_rule_repair")
    rules_key = "replacement_rules" if kind == "semantic_rule_repair" else "proposed_rules"
    component = payload[rules_key][0]["components"][0]
    component["exception_expression"] = [
        {"existence_atoms": [], "scalar_atoms": [], "set_atoms": []}
    ]

    # The provider schema stays free of anyOf/allOf/oneOf for local-model
    # compatibility.  Cross-array non-emptiness is therefore a deterministic
    # hydration invariant rather than a polymorphic JSON-Schema constraint.
    assert list(Draft202012Validator(_schema(kind)).iter_errors(payload)) == []
    parser = (
        _parse_semantic_candidate
        if kind == "semantic_candidate"
        else _parse_semantic_repair
    )
    with pytest.raises(ProtocolWireError) as caught:
        parser(
            json.dumps(payload, ensure_ascii=False),
            compact=True,
            expected_batch_id="1/1",
        )
    assert caught.value.code == DNF_WIRE_ERROR_CODES["empty_group"]

    component["exception_expression"] = None
    assert list(Draft202012Validator(_schema(kind)).iter_errors(payload)) == []


@pytest.mark.parametrize("kind", ["semantic_candidate", "semantic_rule_repair"])
def test_dnf_wire_requires_negation_and_value_units(kind: str):
    payload = _payload(repair=kind == "semantic_rule_repair")
    errors = list(Draft202012Validator(_schema(kind)).iter_errors(payload))
    assert errors == []
    parser = (
        _parse_semantic_candidate
        if kind == "semantic_candidate"
        else _parse_semantic_repair
    )
    parsed = parser(
        json.dumps(payload, ensure_ascii=False),
        compact=True,
        expected_batch_id="1/1",
    )
    assert parsed.candidate_id == "candidate-1"

    atom = payload["replacement_rules" if kind == "semantic_rule_repair" else "proposed_rules"][0][
        "components"
    ][0]["expression"][0]["scalar_atoms"][0]
    atom.pop("negated")
    assert list(Draft202012Validator(_schema(kind)).iter_errors(payload))

    invalid_unit = copy.deepcopy(_payload(repair=kind == "semantic_rule_repair"))
    invalid_atom = invalid_unit[
        "replacement_rules" if kind == "semantic_rule_repair" else "proposed_rules"
    ][0]["components"][0]["expression"][0]["set_atoms"][0]
    invalid_atom["unit"] = "非"
    with pytest.raises(ProtocolWireError) as caught:
        parser(
            json.dumps(invalid_unit, ensure_ascii=False),
            compact=True,
            expected_batch_id="1/1",
        )
    assert caught.value.code == DNF_WIRE_ERROR_CODES["categorical_unit"]


@pytest.mark.parametrize("kind", ["semantic_candidate", "semantic_rule_repair"])
@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        ("string_scalar", DNF_WIRE_ERROR_CODES["shape_mismatch"]),
        ("numeric_set", DNF_WIRE_ERROR_CODES["shape_mismatch"]),
    ],
)
def test_candidate_and_repair_reject_ambiguous_value_shapes(
    kind: str, mutation: str, code: str
):
    repair = kind == "semantic_rule_repair"
    payload = _payload(repair=repair)
    rules_key = "replacement_rules" if repair else "proposed_rules"
    expression = payload[rules_key][0]["components"][0]["expression"][0]
    if mutation == "string_scalar":
        expression["scalar_atoms"][0]["value"] = "18"
    else:
        expression["set_atoms"][0]["values"] = [1, 2]

    assert list(Draft202012Validator(_schema(kind)).iter_errors(payload))
    parser = _parse_semantic_repair if repair else _parse_semantic_candidate
    with pytest.raises(ProtocolWireError) as caught:
        parser(
            json.dumps(payload, ensure_ascii=False),
            compact=True,
            expected_batch_id="1/1",
        )
    assert caught.value.code == code


def test_wire_rejects_double_negation_shape():
    payload = _payload()
    atom = payload["proposed_rules"][0]["components"][0]["expression"][0][
        "set_atoms"
    ][0]
    atom["comparator"] = "not_in"
    atom["negated"] = True

    with pytest.raises(ProtocolWireError) as caught:
        _parse_semantic_candidate(
            json.dumps(payload, ensure_ascii=False),
            compact=True,
            expected_batch_id="1/1",
        )

    assert caught.value.code == DNF_WIRE_ERROR_CODES["shape_mismatch"]


@pytest.mark.parametrize("repair", [False, True])
def test_candidate_and_repair_wire_reject_missing_and_unknown_fields(repair: bool):
    parser = _parse_semantic_repair if repair else _parse_semantic_candidate
    required = (
        "replacement_unresolved_items" if repair else "created_by_agent_call_id"
    )

    missing = _payload(repair=repair)
    missing.pop(required)
    assert list(Draft202012Validator(_schema("semantic_rule_repair" if repair else "semantic_candidate")).iter_errors(missing))
    with pytest.raises(ValueError, match="缺少字段"):
        parser(
            json.dumps(missing, ensure_ascii=False),
            compact=True,
            expected_batch_id="1/1",
        )

    unknown = _payload(repair=repair)
    unknown["unexpected_wire_field"] = True
    assert list(Draft202012Validator(_schema("semantic_rule_repair" if repair else "semantic_candidate")).iter_errors(unknown))
    with pytest.raises(ValueError, match="含未知字段"):
        parser(
            json.dumps(unknown, ensure_ascii=False),
            compact=True,
            expected_batch_id="1/1",
        )


@pytest.mark.parametrize("repair", [False, True])
@pytest.mark.parametrize(
    "locator",
    [
        {},
        {"source_clause": "连续原文", "source_clauses": ["不连续片段"]},
    ],
)
def test_candidate_and_repair_source_locator_is_exactly_one_shape(
    repair: bool, locator: dict[str, object]
):
    kind = "semantic_rule_repair" if repair else "semantic_candidate"
    parser = _parse_semantic_repair if repair else _parse_semantic_candidate
    payload = _payload(repair=repair)
    rules_key = "replacement_rules" if repair else "proposed_rules"
    atom = payload[rules_key][0]["components"][0]["expression"][0][
        "existence_atoms"
    ][0]
    atom["source_locator"] = locator

    assert list(Draft202012Validator(_schema(kind)).iter_errors(payload))
    with pytest.raises(ValueError, match="source_locator"):
        parser(
            json.dumps(payload, ensure_ascii=False),
            compact=True,
            expected_batch_id="1/1",
        )


@pytest.mark.parametrize("atom_field", ["scalar_atoms", "set_atoms"])
def test_value_bearing_atoms_reject_null_units_with_stable_error_code(atom_field: str):
    payload = _payload()
    atom = payload["proposed_rules"][0]["components"][0]["expression"][0][
        atom_field
    ][0]
    atom["unit"] = None

    assert list(Draft202012Validator(_schema()).iter_errors(payload))
    with pytest.raises(ProtocolWireError) as caught:
        _parse_semantic_candidate(
            json.dumps(payload, ensure_ascii=False),
            compact=True,
            expected_batch_id="1/1",
        )
    assert caught.value.code == DNF_WIRE_ERROR_CODES["missing_unit"]


def test_dnf_parser_compiles_alternative_groups_and_atom_negation_for_domain_seam():
    payload = _payload()
    rule = payload["proposed_rules"][0]
    rule["components"][0]["source_excerpts"] = ["目标疾病不存在或既往治疗"]
    first_group = rule["components"][0]["expression"][0]
    first_group["existence_atoms"][0].update(
        {
            "negated": True,
            "source_locator": {"source_clause": "目标疾病不存在"},
        }
    )
    rule["components"][0]["expression"].append(
        {
            "existence_atoms": [_atom(attribute="既往治疗")],
            "scalar_atoms": [],
            "set_atoms": [],
        }
    )

    parsed = _parse_semantic_candidate(
        json.dumps(payload, ensure_ascii=False),
        compact=True,
        expected_batch_id="1/1",
    )
    expression = parsed.proposed_rules[0].components[0].expression
    assert expression.operator == LogicalOperator.ANY
    assert expression.children[0].operator == LogicalOperator.ALL
    assert expression.children[0].children[0].operator == LogicalOperator.NOT
    assert expression.children[1].kind == "predicate"


def test_old_graph_fields_are_rejected_by_schema_and_parser():
    payload = _payload()
    payload["proposed_rules"][0]["components"][0]["root_node_id"] = "root"
    assert list(Draft202012Validator(_schema()).iter_errors(payload))
    with pytest.raises(ValueError, match="未知字段"):
        _parse_semantic_candidate(
            json.dumps(payload, ensure_ascii=False),
            compact=True,
            expected_batch_id="1/1",
        )


def test_compact_prompt_states_native_dnf_semantics_without_formal_or_graph_ids():
    source_input, _draft, _spans = _fixture()
    prompt = build_protocol_deconstruction_prompt(
        source_input,
        prompt_template="按正式方案原文进行结构化解构。",
        requested_rule_codes=["IN-01"],
        batch_number=1,
        batch_total=1,
        candidate_id="candidate-1",
        batch_id="1/1",
        agent_call_id="call-1",
        compact=True,
    )
    for fragment in (
        "wire_version='dnf-v1'",
        "一个 group 表示其中所有条件必须共同满足",
        "多个 group 表示完整的替代路径",
        "且/同时/并且",
        "exception_expression 是独立的 DNF",
        "每个 atom 都必须带 negated",
        "不得自行发明单位、时间窗、否定范围或替代路径",
    ):
        assert fragment in prompt
    for forbidden in (
        "node_id",
        "children",
        "root_node_id",
        "predicate_id",
        "not_logical_nodes",
        "all_any_logical_nodes",
    ):
        assert forbidden not in prompt
