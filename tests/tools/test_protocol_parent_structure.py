from __future__ import annotations

from pathlib import Path

from app.domain.contracts.enums import CatalogItemKind
from app.domain.contracts.protocol_ingestion import FrozenCatalogItem
from tools.phase5_acceptance.protocol_parent_structure import (
    ParentStructureFingerprint,
    fingerprint_parent_rule,
    has_minimum_acceptance_challenge,
    select_most_structurally_distinct,
    structural_distance,
)


def _parent(code: str, *texts: str) -> tuple[FrozenCatalogItem, dict[str, str]]:
    span_ids = tuple(f"span-{index}" for index in range(len(texts)))
    return (
        FrozenCatalogItem(
            item_id=f"parent:{code}",
            kind=CatalogItemKind.PARENT_RULE,
            official_code=code,
            label="中性合成父规则",
            position=0,
            source_span_ids=span_ids,
            source_excerpts=tuple(texts),
        ),
        dict(zip(span_ids, texts, strict=True)),
    )


def test_identical_structure_has_zero_distance() -> None:
    item_a, text_a = _parent("A", "节点前4周内发生事件或存在另一条件")
    item_b, text_b = _parent("B", "节点前8天内发生事项或存在另一情况")
    left = fingerprint_parent_rule(item_a, source_text_by_id=text_a)
    right = fingerprint_parent_rule(item_b, source_text_by_id=text_b)
    assert structural_distance(left, right) == 0.0


def test_selector_uses_maximum_nearest_reference_distance() -> None:
    references = [
        ParentStructureFingerprint("REF-A", frozenset({"source:multiple", "logic:disjunction"})),
        ParentStructureFingerprint("REF-B", frozenset({"source:multiple", "condition:temporal-window"})),
    ]
    near = ParentStructureFingerprint(
        "CAND-A", frozenset({"source:multiple", "logic:disjunction"})
    )
    distant = ParentStructureFingerprint(
        "CAND-B", frozenset({"source:single", "condition:numeric-threshold"})
    )

    selected = select_most_structurally_distinct(
        [near, distant], references=references
    )

    assert selected.selected.official_code == "CAND-B"
    assert selected.minimum_distance == 1.0


def test_selector_tie_break_is_stable() -> None:
    reference = ParentStructureFingerprint("REF", frozenset({"source:single"}))
    same_b = ParentStructureFingerprint("B", frozenset({"source:multiple"}))
    same_a = ParentStructureFingerprint("A", frozenset({"source:multiple"}))

    selected = select_most_structurally_distinct(
        [same_b, same_a], references=[reference]
    )

    assert selected.selected.official_code == "A"


def test_minimum_challenge_rejects_plain_qualitative_sentence() -> None:
    plain = ParentStructureFingerprint(
        "PLAIN", frozenset({"source:single", "condition:qualitative"})
    )
    exception = ParentStructureFingerprint(
        "EXCEPTION", frozenset({"source:single", "logic:exception"})
    )

    assert has_minimum_acceptance_challenge(plain) is False
    assert has_minimum_acceptance_challenge(exception) is True


def test_shared_selector_contains_no_project_or_clinical_literals() -> None:
    module = (
        Path(__file__).resolve().parents[2]
        / "tools/phase5_acceptance/protocol_parent_structure.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        "D001",
        "SAR",
        "EX-06",
        "EX-18",
        "银屑病",
        "鼻窦炎",
        "司普奇拜",
        "ECOG",
        "ALT",
        "AST",
    )
    assert not any(item in module for item in forbidden)
