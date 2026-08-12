from __future__ import annotations

from collections.abc import Callable

from app.domain.contracts.enums import LogicalOperator
from app.domain.contracts.rules import AtomicPredicate, RuleExpression


PredicateResolver = Callable[[AtomicPredicate], bool]


def evaluate_expression(expression: RuleExpression, resolve: PredicateResolver) -> bool:
    """Evaluate only the logical tree; clinical predicate meaning stays outside this layer."""
    if expression.kind == "predicate":
        return resolve(expression.predicate)
    values = [evaluate_expression(child, resolve) for child in expression.children]
    if expression.operator == LogicalOperator.ALL:
        return all(values)
    if expression.operator == LogicalOperator.ANY:
        return any(values)
    if expression.operator == LogicalOperator.NOT:
        return not values[0]
    raise ValueError(f"不支持的逻辑运算符: {expression.operator}")
