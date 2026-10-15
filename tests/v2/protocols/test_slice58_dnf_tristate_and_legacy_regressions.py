from __future__ import annotations

import json

import pytest

from app.agents.protocol_deconstructor import (
    DNF_WIRE_ERROR_CODES,
    ProtocolWireError,
    _parse_semantic_candidate,
    _parse_semantic_repair,
)
from app.domain.contracts.enums import FactPolarity, LogicalOperator, TruthValue
from app.domain.contracts.evidence import ClinicalFact
from app.domain.expression import EvaluationContext, evaluate_expression

from .test_slice58_dnf_wire_contract import _atom, _payload


def _set_atom(
    attribute: str,
    *,
    value: str = "present",
    negated: bool = False,
) -> dict[str, object]:
    return {
        **_atom(
            attribute=attribute,
            negated=negated,
            source_clause=f"不{attribute}" if negated else attribute,
        ),
        "comparator": "in",
        "values": [value],
        "unit": "unitless",
    }


def _group(*atoms: dict[str, object]) -> dict[str, object]:
    return {
        "existence_atoms": [],
        "scalar_atoms": [],
        "set_atoms": list(atoms),
    }


def _candidate_with_expression(groups: list[dict[str, object]]) -> dict[str, object]:
    payload = _payload()
    component = payload["proposed_rules"][0]["components"][0]
    component["expression"] = groups
    component["source_excerpts"] = ["A或B；任一分支"]
    component["exception_expression"] = None
    return payload


def _parse(groups: list[dict[str, object]]):
    return _parse_semantic_candidate(
        json.dumps(_candidate_with_expression(groups), ensure_ascii=False),
        compact=True,
        expected_batch_id="1/1",
    ).proposed_rules[0].components[0].expression


def _fact(attribute: str, value: str, *, fact_id: str | None = None) -> ClinicalFact:
    return ClinicalFact(
        fact_id=fact_id or f"fact-{attribute}",
        project_id="project-1",
        subject_id="subject-1",
        review_episode_id="episode-1",
        evidence_snapshot_id="snapshot-1",
        fact_type=f"受试者.{attribute}",
        value=value,
        unit="unitless",
        polarity=FactPolarity.AFFIRMED,
        certainty=1.0,
        evidence_span_ids=[f"span-{attribute}"],
    )


def _context(*facts: ClinicalFact) -> EvaluationContext:
    return EvaluationContext(
        project_id="project-1",
        subject_id="subject-1",
        review_episode_id="episode-1",
        evidence_snapshot_id="snapshot-1",
        accepted_fact_ids=[fact.fact_id for fact in facts],
        facts=list(facts),
    )


def test_dnf_distribution_and_atom_not_preserve_true_false_unknown() -> None:
    # (A and B) or (C and not D).  The wire has no references to resolve and
    # hydration must produce exactly the formal ALL/ANY/NOT expression.
    expression = _parse(
        [
            _group(_set_atom("A"), _set_atom("B")),
            _group(_set_atom("C"), _set_atom("D", negated=True)),
        ]
    )

    assert expression.kind == "logical"
    assert expression.operator == LogicalOperator.ANY
    assert [child.operator for child in expression.children] == [
        LogicalOperator.ALL,
        LogicalOperator.ALL,
    ]
    assert expression.children[1].children[1].operator == LogicalOperator.NOT

    assignments = [
        (
            "first branch true",
            _context(_fact("A", "present"), _fact("B", "present"), _fact("C", "absent"), _fact("D", "present")),
            TruthValue.TRUE,
        ),
        (
            "both branches false",
            _context(_fact("A", "present"), _fact("B", "absent"), _fact("C", "absent"), _fact("D", "present")),
            TruthValue.FALSE,
        ),
        (
            "unknown branch and false branch",
            _context(_fact("A", "present"), _fact("C", "absent"), _fact("D", "present")),
            TruthValue.UNKNOWN,
        ),
        (
            "second branch true",
            _context(_fact("A", "absent"), _fact("B", "present"), _fact("C", "present"), _fact("D", "absent")),
            TruthValue.TRUE,
        ),
    ]
    for label, context, expected in assignments:
        assert evaluate_expression(expression, context).truth == expected, label


def test_dnf_does_not_apply_classical_tautology_simplification_under_unknown() -> None:
    # (A and B) or not A is classically true only when B is known.  With A
    # true and B unobserved, strong Kleene evaluation must remain UNKNOWN.
    expression = _parse(
        [
            _group(_set_atom("A"), _set_atom("B")),
            _group(_set_atom("A", negated=True)),
        ]
    )

    result = evaluate_expression(expression, _context(_fact("A", "present")))
    assert result.truth == TruthValue.UNKNOWN


def test_golden_conjunction_mutation_to_alternative_path_changes_evaluation() -> None:
    # Golden source: both conditions are required.  Splitting the group into
    # two groups is the v6-v9 failure mode: it silently weakens AND to OR.
    golden = _parse([_group(_set_atom("A"), _set_atom("B"))])
    weakened = _parse([_group(_set_atom("A")), _group(_set_atom("B"))])
    context = _context(_fact("A", "present"), _fact("B", "absent"))

    assert evaluate_expression(golden, context).truth == TruthValue.FALSE
    assert evaluate_expression(weakened, context).truth == TruthValue.TRUE


def _legacy_graph_payload(
    *,
    root: str,
    children: list[str],
) -> dict[str, object]:
    payload = _payload()
    component = payload["proposed_rules"][0]["components"][0]
    component.update(
        {
            "root_node_id": root,
            "existence_predicate_nodes": [
                {
                    "node_id": "p1",
                    "predicate": {
                        "predicate_id": "legacy-p1",
                        "subject": "受试者",
                        "attribute": "旧图条件",
                        "source_locator": {"source_clause": "旧图条件"},
                        "unit": None,
                        "requires_professional_judgment": False,
                    },
                    "comparator": "exists",
                    "time_constraint": None,
                }
            ],
            "not_logical_nodes": [],
            "all_any_logical_nodes": [
                {"node_id": root, "operator": "all", "children": children}
            ],
        }
    )
    return payload


@pytest.mark.parametrize(
    ("failure", "root", "children"),
    [
        ("v6 dangling p2", "root", ["p1", "p2"]),
        ("v8 dangling p3", "a1", ["p3", "n1"]),
        ("v9 attempt 1 dangling p3", "a1", ["p3", "n1"]),
        ("v9 attempt 2 dangling p4", "a1", ["p1", "p4"]),
    ],
)
def test_v6_v8_v9_dangling_graph_payloads_are_rejected_as_legacy(failure, root, children):
    with pytest.raises(ProtocolWireError) as caught:
        _parse_semantic_candidate(
            json.dumps(
                _legacy_graph_payload(root=root, children=children),
                ensure_ascii=False,
            ),
            compact=True,
            expected_batch_id="1/1",
        )

    assert caught.value.code == DNF_WIRE_ERROR_CODES["legacy_graph_field"], failure
    assert "不存在的 node_id" not in str(caught.value)


def test_v7_missing_value_unit_is_rejected_in_the_new_wire_before_domain_hydration():
    payload = _payload()
    atom = payload["proposed_rules"][0]["components"][0]["expression"][0][
        "scalar_atoms"
    ][0]
    atom["unit"] = None

    with pytest.raises(ProtocolWireError) as caught:
        _parse_semantic_candidate(
            json.dumps(payload, ensure_ascii=False),
            compact=True,
            expected_batch_id="1/1",
        )

    assert caught.value.code == DNF_WIRE_ERROR_CODES["missing_unit"]


def test_legacy_graph_payloads_are_not_accepted_by_repair_contract_either():
    payload = _legacy_graph_payload(root="root", children=["p1", "p2"])
    repair = {
        "wire_version": payload["wire_version"],
        "candidate_id": payload["candidate_id"],
        "batch_id": "repair:IN-01",
        "replacement_rules": payload["proposed_rules"],
        "replacement_structural_warnings": [],
        "replacement_unresolved_items": [],
    }

    with pytest.raises(ProtocolWireError) as caught:
        _parse_semantic_repair(
            json.dumps(repair, ensure_ascii=False),
            compact=True,
            expected_batch_id="repair:IN-01",
        )
    assert caught.value.code == DNF_WIRE_ERROR_CODES["legacy_graph_field"]
