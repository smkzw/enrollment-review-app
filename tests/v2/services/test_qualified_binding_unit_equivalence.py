"""Only identical canonical units can clear a frozen numeric-pair unit gap."""

from types import SimpleNamespace

import pytest

from app.domain.contracts.predicate_binding import PredicateBindingFrozenInput
from app.services.binding_qualification_support import SEMANTIC_DIMENSIONS
from app.services.qualified_binding_selection import (
    _numeric_predicate_units,
    _unit_equivalence_verified,
    pair_direct_selection_rejection_reasons,
)


def _pair(unit: str, *, body_matches_frozen: bool = True):
    judgment = SimpleNamespace(
        public_agreement_key=lambda: "same-source-and-meaning",
        source_admissibility="admissible", object_match="supported",
        attribute_match="direct", denial_scope="compatible",
        direct_operand_usable="usable", temporal_role="not_applicable",
        unresolved_reasons=[],
    )
    return SimpleNamespace(
        identity_sha256="predicate", fact_attribute="value",
        structurally_valid=True, dual_agreement=True,
        semantic_dimensions_rechecked=SEMANTIC_DIMENSIONS,
        structural=SimpleNamespace(
            pending_checks=["unit_equivalence_unverified"],
            source_policy_status="present", reasons=[],
            referenced_unit=unit, operand_shape="numeric_value",
            body_matches_frozen=body_matches_frozen,
        ),
        lane_judgments={"main-A": judgment, "main-B": judgment},
        remaining_unverified=[],
    )


@pytest.mark.parametrize(("unit", "expected", "frozen", "resolved"), [
    ("岁", "周岁", True, True),
    ("years", "周岁", True, True),
    ("月", "周岁", True, False),
    ("岁", None, True, False),
    ("岁", "周岁", False, False),
])
def test_unit_gap_only_resolves_for_same_frozen_canonical_unit(unit, expected, frozen, resolved):
    pair = _pair(unit, body_matches_frozen=frozen)
    verified = _unit_equivalence_verified(pair, {"predicate": expected})
    assert verified is resolved
    reasons = pair_direct_selection_rejection_reasons(pair, unit_equivalence_verified=verified)
    assert ("pending:unit_equivalence_unverified" not in reasons) is resolved


def test_unit_gap_never_overrides_a_model_disagreement():
    pair = _pair("岁")
    pair.dual_agreement = False
    reasons = pair_direct_selection_rejection_reasons(pair, unit_equivalence_verified=True)
    assert "pending:unit_equivalence_unverified" in reasons
    assert "dual_lane_disagreement_or_incomplete" in reasons


def test_expected_unit_comes_from_the_frozen_predicate_not_the_model_pair():
    frozen = PredicateBindingFrozenInput.model_construct(components=[
        SimpleNamespace(binding_predicates=[
            SimpleNamespace(predicate_identity_sha256="predicate",
                            predicate=SimpleNamespace(unit="周岁")),
        ]),
    ])
    units = _numeric_predicate_units(frozen)
    assert _unit_equivalence_verified(_pair("years"), units)
    assert not _unit_equivalence_verified(_pair("月"), units)
