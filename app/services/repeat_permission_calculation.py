"""Check that the decisive permission branch contains verified written judgment."""
from app.domain.contracts.enums import LogicalOperator, TruthValue
from app.domain.expression import EvaluationResult


def written_permission_scoped_to_target(row, identity):
    scopes = [item for item in row.get("evidence_scopes", ())
              if item.get("identity_sha256") == identity]
    return (len(scopes) == 1 and bool(row.get("repeat_group_id"))
            and scopes[0].get("role") == "target_observation"
            and scopes[0].get("reference_group_id") == row["repeat_group_id"]
            and scopes[0].get("acquisition_scope_check") == "verified")


def written_permission_result(*, family, condition, atom_results, written_atom_ids):
    """A numeric-only alternative cannot stand in for investigator authorization.

    Atom truth already includes source, value, time and content qualification.
    Track a written witness through the original Boolean expression; never
    infer one from an empty record set or from a signature's presence alone.
    """
    def combine(operator, children):
        truths = [truth for truth, _ in children]
        if operator == LogicalOperator.NOT:
            truth, witness = children[0]
            return {TruthValue.TRUE: TruthValue.FALSE, TruthValue.FALSE: TruthValue.TRUE,
                    TruthValue.UNKNOWN: TruthValue.UNKNOWN}[truth], witness
        decisive = TruthValue.FALSE if operator == LogicalOperator.ALL else TruthValue.TRUE
        opposite = TruthValue.TRUE if operator == LogicalOperator.ALL else TruthValue.FALSE
        if decisive in truths:
            return decisive, frozenset().union(*(witness for truth, witness in children if truth == decisive))
        if TruthValue.UNKNOWN in truths:
            return TruthValue.UNKNOWN, frozenset()
        return opposite, frozenset().union(*(witness for _, witness in children))

    def leaf(key):
        return atom_results[key].truth, (frozenset({key}) if key in written_atom_ids
                                        and atom_results[key].truth != TruthValue.UNKNOWN else frozenset())

    def official(expression):
        if expression.kind == "predicate":
            return leaf(expression.predicate.predicate_id)
        return combine(expression.operator, [official(child) for child in expression.children])

    if family == "predicate":
        truth, witness = official(condition.expression)
    else:
        truth, witness = combine(LogicalOperator.ANY, [
            combine(LogicalOperator.ALL, [leaf(atom.condition_atom_id) for atom in group.atoms])
            for group in condition.expression.groups
        ])
    usable = truth != TruthValue.UNKNOWN and witness
    return EvaluationResult(
        truth=TruthValue.TRUE if usable else TruthValue.UNKNOWN,
        reason_codes=["repeat_written_permission_verified" if usable else "repeat_written_permission_unverified"],
        used_fact_ids=sorted({key for atom_id in witness for key in atom_results[atom_id].used_fact_ids}),
        evidence_span_ids=sorted({key for atom_id in witness for key in atom_results[atom_id].evidence_span_ids}),
    )
