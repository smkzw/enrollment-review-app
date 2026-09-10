"""Project a published RuleSet into the compact R3 page-review ClausePack."""

from __future__ import annotations

from datetime import date
from typing import Iterable

from app.domain.contracts.clause_pack import (
    ClausePack,
    ClausePackClause,
    DeterminationMode,
)
from app.domain.contracts.enums import Comparator
from app.domain.contracts.rules import (
    AtomicExpression,
    LogicalExpression,
    RuleComponent,
    RuleExpression,
    RuleSet,
    iter_atomic_predicates,
)
from app.domain.publication import canonical_hash


class ClausePackProjectionError(ValueError):
    pass


def _expressions(expression: RuleExpression) -> Iterable[RuleExpression]:
    yield expression
    if isinstance(expression, LogicalExpression):
        for child in expression.children:
            yield from _expressions(child)


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_iso_date(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def determine_component_mode(component: RuleComponent) -> DeterminationMode:
    """Classify from structured semantics only; never inspect project vocabulary."""
    predicates = [
        *iter_atomic_predicates(component.expression),
        *(
            iter_atomic_predicates(component.exception_expression)
            if component.exception_expression is not None
            else ()
        ),
    ]
    if any(item.requires_professional_judgment for item in predicates):
        return DeterminationMode.INVESTIGATOR_JUDGMENT

    expressions = [
        *_expressions(component.expression),
        *(
            _expressions(component.exception_expression)
            if component.exception_expression is not None
            else ()
        ),
    ]
    if any(isinstance(item, LogicalExpression) for item in expressions):
        return DeterminationMode.DETERMINISTIC
    if any(
        isinstance(item, AtomicExpression) and item.time_constraint is not None
        for item in expressions
    ):
        return DeterminationMode.DETERMINISTIC
    if any(
        predicate.comparator
        in {Comparator.GT, Comparator.GTE, Comparator.LT, Comparator.LTE}
        for predicate in predicates
    ):
        return DeterminationMode.DETERMINISTIC
    if any(
        _is_number(value) or _is_iso_date(value)
        for predicate in predicates
        for value in (
            predicate.value if isinstance(predicate.value, list) else [predicate.value]
        )
        if value is not None
    ):
        return DeterminationMode.DETERMINISTIC
    return DeterminationMode.SEMANTIC


def clause_pack_hash_material(rule_set: RuleSet) -> dict[str, object]:
    clauses: list[dict[str, object]] = []
    seen_components: set[str] = set()
    for rule in sorted(rule_set.rules, key=lambda item: (item.official_code, item.rule_id)):
        for component in sorted(
            rule.components, key=lambda item: (item.display_code, item.rule_component_id)
        ):
            if component.rule_component_id in seen_components:
                raise ClausePackProjectionError(
                    f"重复的规则组件身份：{component.rule_component_id}"
                )
            seen_components.add(component.rule_component_id)
            clauses.append(
                ClausePackClause(
                    clause_id=component.rule_component_id,
                    rule_id=rule.rule_id,
                    rule_component_id=component.rule_component_id,
                    official_code=rule.official_code,
                    display_code=component.display_code,
                    kind=rule.kind,
                    title=component.title,
                    source_text=rule.source_text,
                    expression=component.expression,
                    exception_expression=component.exception_expression,
                    evidence_requirements=sorted(
                        component.evidence_requirements,
                        key=lambda item: item.requirement_id,
                    ),
                    determination_mode=determine_component_mode(component),
                ).model_dump(mode="json")
            )
    return {
        "projection_version": "clause-pack/v1",
        "rule_set_id": rule_set.rule_set_id,
        "rule_set_revision": rule_set.revision,
        "protocol_version_id": rule_set.protocol_version_id,
        "study_phase": rule_set.study_phase.value,
        "clauses": clauses,
    }


def project_clause_pack(rule_set: RuleSet) -> ClausePack:
    material = clause_pack_hash_material(rule_set)
    digest = canonical_hash(material)
    return ClausePack(
        clause_pack_id=f"clause-pack:{digest[:32]}",
        clause_pack_sha256=digest,
        **material,
    )


def verify_clause_pack(clause_pack: ClausePack) -> None:
    material = clause_pack.model_dump(
        mode="json",
        exclude={"schema_version", "clause_pack_id", "clause_pack_sha256"},
    )
    digest = canonical_hash(material)
    if clause_pack.clause_pack_sha256 != digest:
        raise ClausePackProjectionError("ClausePack 内容哈希不一致")
    if clause_pack.clause_pack_id != f"clause-pack:{digest[:32]}":
        raise ClausePackProjectionError("ClausePack 身份与内容哈希不一致")


__all__ = [
    "ClausePackProjectionError",
    "clause_pack_hash_material",
    "determine_component_mode",
    "project_clause_pack",
    "verify_clause_pack",
]
