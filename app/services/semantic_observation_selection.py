"""Source-bound ordering over verified semantic relation rows.

Construction helper only. Callers own version-bound integration and clinical
adoption permission. This module never mutates inputs, never invents dates or
favorable values, and never treats supplied-fact coverage as clinical completeness.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from app.domain.publication import canonical_hash
from app.services.ordered_observation_selection import select_ordered_observation

CONTENT_ATTRIBUTES = frozenset({"value", "assertion_basis"})


@dataclass(frozen=True)
class SemanticObservationSelection:
    """Selected governing semantic observations plus separately retained exclusions.

    ``scope_candidates_complete`` on returned relation copies records only whether
    every supplied content pair for the identity is represented by a verified
    relation row. It is not proof of extraction completeness or clinical history.
    """

    fact_ids: tuple[str, ...]
    pair_ids: tuple[str, ...]
    reasons: tuple[str, ...]
    ordering: dict[str, Any] | None = None
    selected_relations: tuple[dict[str, Any], ...] = ()
    not_selected_relations: tuple[tuple[dict[str, Any], str], ...] = ()


def _sorted_unique(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted({item for item in values if item and str(item).strip()}))


def _unresolved(
    *reasons: str,
    ordering: dict[str, Any] | None = None,
    not_selected_relations: Sequence[tuple[dict[str, Any], str]] = (),
) -> SemanticObservationSelection:
    if ordering is not None:
        ordering = {**ordering, "selected_fact_ids": []}
    return SemanticObservationSelection(
        fact_ids=(),
        pair_ids=(),
        reasons=_sorted_unique(reasons),
        ordering=ordering,
        selected_relations=(),
        not_selected_relations=tuple(not_selected_relations),
    )


def _relation_copies(
    relations: Sequence[Mapping[str, Any]],
    *,
    scope_candidates_complete: bool,
) -> list[dict[str, Any]]:
    copies: list[dict[str, Any]] = []
    for relation in relations:
        item = deepcopy(dict(relation))
        item["scope_candidates_complete"] = scope_candidates_complete
        copies.append(item)
    return copies


def _ordering_audit(*, policy, accounting: Sequence[Mapping[str, Any]], selection) -> dict[str, Any]:
    return {
        "policy_sha256": canonical_hash(policy.model_dump(mode="json")),
        "accounting_sha256": canonical_hash(list(accounting)),
        "scope": "supplied_facts_only",
        "selected_fact_ids": list(selection.fact_ids),
        "not_selected": [
            {"fact_id": fact_id, "reason": reason}
            for fact_id, reason in selection.excluded
        ],
    }


def select_semantic_ordered_observation(
    *,
    policy,
    facts: Mapping[str, Any],
    relations: Sequence[Mapping[str, Any]],
    usable_records: Sequence[Any],
    source_records: Sequence[Any],
    accounting: Sequence[Mapping[str, Any]],
    time_constraint,
    anchor_dates: Mapping[str, Any],
    time_purpose: str,
    review_context,
    content_attributes: frozenset[str] | set[str] = CONTENT_ATTRIBUTES,
    date_attribute: str = "date_range",
) -> SemanticObservationSelection:
    """Choose date-dominant verified semantic relations under an explicit policy.

    Requires ``policy.mode == "single"`` with an explicit latest/earliest selection
    supported by ``select_ordered_observation``. Date dominance is delegated to
    that selector; this helper only gates source-bound relation coverage, retains
    excluded relations as not-selected, and never mutates caller collections.
    """
    if review_context is None:
        return _unresolved("observation_scope_unverified")
    if policy is None or policy.mode == "unresolved" or policy.selection is None:
        return _unresolved("observation_selection_unverified")
    if policy.mode != "single" or policy.selection.criterion not in {"latest", "earliest"}:
        return _unresolved("observation_selection_unverified")
    if policy.selection.ordering_attribute != "date_range":
        return _unresolved("observation_selection_unverified")

    content_attrs = frozenset(content_attributes)
    if not content_attrs or not content_attrs <= CONTENT_ATTRIBUTES:
        return _unresolved("observation_selection_unverified")
    if date_attribute != "date_range":
        return _unresolved("known_date_unqualified")

    source_content_pairs = {
        record.pair_id
        for record in source_records
        if getattr(record, "fact_attribute", None) in content_attrs
    }
    relation_pair_ids = {item["pair_id"] for item in relations}
    source_by_pair = {record.pair_id: record for record in source_records
                      if getattr(record, "fact_attribute", None) in content_attrs}
    if len(relation_pair_ids) != len(relations) or any(
        item["pair_id"] not in source_by_pair
        or source_by_pair[item["pair_id"]].fact_id != item["fact_id"]
        or source_by_pair[item["pair_id"]].identity_sha256 != item["identity_sha256"]
        for item in relations
    ):
        return _unresolved("semantic_evidence_unverified")
    scope_candidates_complete = source_content_pairs == relation_pair_ids
    relation_copies = _relation_copies(
        relations, scope_candidates_complete=scope_candidates_complete,
    )
    if not scope_candidates_complete:
        return _unresolved("single_observation_relations_incomplete")
    if not relation_copies:
        return _unresolved("semantic_evidence_unverified")

    operand_fact_ids = _sorted_unique(item["fact_id"] for item in relation_copies)
    date_fact_ids = _sorted_unique(
        record.fact_id
        for record in usable_records
        if getattr(record, "fact_attribute", None) == date_attribute
    )
    # Ordering requires a qualified date_range for every content candidate, even
    # when the protocol declares no separate time constraint.
    if not set(operand_fact_ids) <= set(date_fact_ids):
        return _unresolved("known_date_unqualified")

    conflicting_fact_ids = [
        fact_id
        for group in review_context.conflict_groups
        for fact_id in group.fact_ids
    ]
    selection = select_ordered_observation(
        policy=policy,
        facts=facts,
        operand_fact_ids=list(operand_fact_ids),
        date_fact_ids=list(date_fact_ids),
        accounting=accounting,
        time_constraint=time_constraint,
        anchor_dates=anchor_dates,
        time_purpose=time_purpose,
        conflicting_fact_ids=conflicting_fact_ids,
    )
    ordering = _ordering_audit(policy=policy, accounting=accounting, selection=selection)
    excluded_by_fact = {fact_id: reason for fact_id, reason in selection.excluded}
    not_selected_relations = tuple(
        (item, excluded_by_fact[item["fact_id"]])
        for item in relation_copies
        if item["fact_id"] in excluded_by_fact
    )
    if selection.reasons:
        return _unresolved(
            *selection.reasons,
            ordering=ordering,
            not_selected_relations=not_selected_relations,
        )

    selected_ids = set(selection.fact_ids)
    selected_relations = tuple(
        item for item in relation_copies if item["fact_id"] in selected_ids
    )
    if not selected_relations or set(item["fact_id"] for item in selected_relations) != selected_ids:
        return _unresolved(
            "semantic_evidence_unverified",
            ordering=ordering,
            not_selected_relations=not_selected_relations,
        )

    pair_ids = _sorted_unique([
        *(item["pair_id"] for item in selected_relations),
        *(
            record.pair_id
            for record in usable_records
            if record.fact_id in selected_ids
            and getattr(record, "fact_attribute", None) == date_attribute
        ),
    ])
    return SemanticObservationSelection(
        fact_ids=tuple(selection.fact_ids),
        pair_ids=pair_ids,
        reasons=(),
        ordering=ordering,
        selected_relations=selected_relations,
        not_selected_relations=not_selected_relations,
    )
