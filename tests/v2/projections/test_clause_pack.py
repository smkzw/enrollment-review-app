from __future__ import annotations

from copy import deepcopy

import pytest

from app.domain.contracts.clause_pack import ClausePack, DeterminationMode
from app.projections.page_review_prompt_pack import page_review_prompt_pack
from app.domain.contracts.enums import (
    AnchorType,
    Comparator,
    LogicalOperator,
    RuleKind,
    StudyPhase,
    TimeDirection,
)
from app.domain.contracts.rules import (
    AtomicExpression,
    AtomicPredicate,
    LogicalExpression,
    Rule,
    RuleComponent,
    RuleSet,
    TimeConstraint,
)
from app.projections.clause_pack import (
    ClausePackProjectionError,
    determine_component_mode,
    project_clause_pack,
    verify_clause_pack,
)


def _predicate(
    suffix: str,
    *,
    comparator: Comparator = Comparator.EXISTS,
    value=None,
    unit: str | None = None,
    professional: bool = False,
) -> AtomicPredicate:
    return AtomicPredicate(
        predicate_id=f"predicate-{suffix}",
        subject="受试者",
        attribute=f"属性-{suffix}",
        comparator=comparator,
        value=value,
        unit=unit,
        requires_professional_judgment=professional,
    )


def _component(suffix: str, expression) -> RuleComponent:
    return RuleComponent(
        rule_component_id=f"component-{suffix}",
        parent_rule_id=f"rule-{suffix}",
        display_code=f"IN-01-{suffix}",
        title=f"条件 {suffix}",
        expression=expression,
    )


def _rule_set(component: RuleComponent) -> RuleSet:
    return RuleSet(
        rule_set_id="ruleset-generic",
        revision=3,
        protocol_version_id="protocol-version-generic",
        study_phase=StudyPhase.PHASE_III,
        rules=[
            Rule(
                rule_id=component.parent_rule_id,
                official_code="IN-01",
                kind=RuleKind.INCLUSION,
                source_text="方案原文中的完整条件。",
                study_phase=StudyPhase.PHASE_III,
                components=[component],
            )
        ],
    )


def test_mode_is_investigator_judgment_when_any_predicate_requires_it() -> None:
    component = _component(
        "professional",
        AtomicExpression(predicate=_predicate("professional", professional=True)),
    )
    assert determine_component_mode(component) == DeterminationMode.INVESTIGATOR_JUDGMENT


@pytest.mark.parametrize(
    "expression",
    [
        AtomicExpression(
            predicate=_predicate("number", comparator=Comparator.GTE, value=18, unit="岁")
        ),
        AtomicExpression(
            predicate=_predicate("window"),
            time_constraint=TimeConstraint(
                anchor_type=AnchorType.REVIEW_NODE_DATE,
                direction=TimeDirection.BEFORE,
                upper_bound_days=180,
            ),
        ),
        LogicalExpression(
            operator=LogicalOperator.ALL,
            children=[
                AtomicExpression(predicate=_predicate("logic-a")),
                AtomicExpression(predicate=_predicate("logic-b")),
            ],
        ),
    ],
)
def test_structured_numeric_temporal_and_logic_components_are_deterministic(expression) -> None:
    assert (
        determine_component_mode(_component("deterministic", expression))
        == DeterminationMode.DETERMINISTIC
    )


def test_unstructured_presence_component_is_semantic() -> None:
    component = _component("semantic", AtomicExpression(predicate=_predicate("semantic")))
    assert determine_component_mode(component) == DeterminationMode.SEMANTIC


def test_prompt_pack_deduplicates_sources_without_changing_authority():
    component = _component("a", AtomicExpression(predicate=_predicate("a", comparator=Comparator.GTE, value=0, unit="unitless")))
    rules = _rule_set(component)
    other = deepcopy(component)
    other.rule_component_id = "component-b"
    other.display_code = "IN-01-b"
    rules.rules[0].components.append(other)
    original = project_clause_pack(rules)
    before = original.model_dump_json()
    wire = page_review_prompt_pack(original)
    assert len(wire["source_texts"]) == 1
    assert len(wire["clauses"]) == 2
    assert wire["clauses"][0]["expression"]["predicate"]["value"] == 0
    sources = wire.pop("source_texts")
    for clause in wire["clauses"]:
        clause["source_text"] = sources[clause.pop("source_text_ref")]
    restored = ClausePack.model_validate(wire)
    verify_clause_pack(restored)
    assert restored == original
    assert original.model_dump_json() == before


def test_clause_pack_is_stable_content_addressed_and_verifiable() -> None:
    rule_set = _rule_set(
        _component(
            "number",
            AtomicExpression(
                predicate=_predicate("number", comparator=Comparator.GTE, value=18, unit="岁")
            ),
        )
    )
    first = project_clause_pack(rule_set)
    second = project_clause_pack(deepcopy(rule_set))

    assert first == second
    assert first.clauses[0].official_code == "IN-01"
    assert first.clauses[0].determination_mode == DeterminationMode.DETERMINISTIC
    verify_clause_pack(first)

    changed = rule_set.model_copy(deep=True)
    changed.rules[0].source_text = "方案原文发生受控修订。"
    assert project_clause_pack(changed).clause_pack_sha256 != first.clause_pack_sha256


def test_clause_pack_verifier_rejects_tampering() -> None:
    clause_pack = project_clause_pack(
        _rule_set(_component("semantic", AtomicExpression(predicate=_predicate("semantic"))))
    )
    tampered = clause_pack.model_copy(update={"protocol_version_id": "tampered"})
    with pytest.raises(ClausePackProjectionError, match="内容哈希"):
        verify_clause_pack(tampered)
