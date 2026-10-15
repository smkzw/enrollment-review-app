"""Quotation repair must not broaden a nested source or change clinical values."""
from copy import deepcopy

import pytest

from app.agents.control_excerpt_restoration import restore_source_fields


def test_nested_sources_and_predicate_quotes_follow_the_declared_parent():
    original = {
        "source_span_ids": ["a"], "source_excerpts": ["记录'甲'结果"],
        "proposition": "记录'甲'结果",
        "observation_policy": {"source_span_ids": ["a"], "source_excerpts": ["'甲'结果"]},
        "predicate": {"source_clause": "'甲'结果", "value": "'甲'"},
    }
    before = deepcopy(original)
    restored = restore_source_fields(original, {"a": ["记录‘甲’结果；其他说明"]})
    assert original == before
    assert restored["source_excerpts"] == ["记录‘甲’结果"]
    assert restored["observation_policy"]["source_excerpts"] == ["‘甲’结果"]
    assert restored["predicate"]["source_clause"] == "‘甲’结果"
    assert restored["predicate"]["value"] == "'甲'"
    assert restored["proposition"] == original["proposition"]


@pytest.mark.parametrize("excerpt", ["'甲'≥3mg", "'甲'>2mg", "'甲'≥2g", "'甲' ≥2mg", "'乙'≥2mg"])
def test_non_quote_differences_are_not_repaired(excerpt):
    payload = {"source_span_ids": ["a"], "source_excerpts": [excerpt]}
    assert restore_source_fields(payload, {"a": ["‘甲’≥2mg"]}) == payload


def test_nested_sources_cannot_borrow_another_span_or_parent_excerpt():
    payload = {
        "source_span_ids": ["a"], "source_excerpts": ["‘甲’"],
        "observation_policy": {"source_span_ids": ["b"], "source_excerpts": ["'乙'"]},
        "predicate": {"source_clauses": ["'丙'"]},
    }
    assert restore_source_fields(payload, {"a": ["‘甲’与‘丙’"], "b": ["‘乙’"]}) == payload


def test_ambiguous_quote_matches_are_not_selected():
    payload = {"source_span_ids": ["a"], "source_excerpts": ["'甲'"]}
    assert restore_source_fields(payload, {"a": ["‘甲’和‘甲’"]}) == payload


def test_half_life_singular_source_and_subject_quote_remain_consistent():
    from app.domain.contracts.half_life_evidence import HalfLifeEvidence

    evidence = HalfLifeEvidence(value=2, unit="day", source_span_id="a",
                                source_excerpt="'甲'的半衰期为2天",
                                applies_to_quote="'甲'", duration_quote="2天")
    restored = HalfLifeEvidence.model_validate(restore_source_fields(
        evidence.model_dump(mode="json"), {"a": ["‘甲’的半衰期为2天"]},
    ))
    assert restored.source_excerpt == "‘甲’的半衰期为2天"
    assert restored.applies_to_quote == "‘甲’"
    assert (restored.value, restored.unit, restored.duration_quote) == (evidence.value, "day", "2天")


def test_unpaired_repeat_and_frequency_sources_use_the_containing_scope():
    payload = {
        "source_span_ids": ["a"], "source_excerpts": ["‘甲’异常可复查"],
        "repeat_scheme": {"source_excerpts": ["'甲'异常可复查"],
                          "trigger_excerpt": "'甲'异常", "scope": "'甲'异常"},
        "horizon": {"source_excerpts": ["'甲'异常"]},
        "evidence_role": {"source_excerpts": ["'甲'异常"]},
    }
    restored = restore_source_fields(payload, {"a": ["‘甲’异常可复查"]})
    assert restored["repeat_scheme"]["trigger_excerpt"] == "‘甲’异常"
    assert restored["repeat_scheme"]["scope"] == "'甲'异常"
    assert restored["horizon"]["source_excerpts"] == ["‘甲’异常"]
    assert restored["evidence_role"]["source_excerpts"] == ["‘甲’异常"]
