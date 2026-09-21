"""Binding evaluation harness: gold validation and scoring math (pure logic)."""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.services.binding_evaluation import (
    BindingEvaluationError,
    GOLD_SPLIT_VERSION,
    _evaluated_route,
    _score_entries,
    _validated_gold_split,
)


class _Pred:
    def __init__(self, identity: str, predicate_id: str):
        self.predicate_identity_sha256 = identity
        self.predicate_id = predicate_id


class _Comp:
    def __init__(self, preds):
        self.binding_predicates = preds


class _Frozen:
    def __init__(self, comps, facts):
        self.components = comps
        self.facts = facts


class _Fact:
    def __init__(self, fact_id: str):
        self.fact_id = fact_id


def _verified():
    return {
        "qualification_job_id": "job-1",
        "frozen": _Frozen(
            [_Comp([_Pred("a" * 64, "IN-01-A1"), _Pred("b" * 64, "IN-01-A2")])],
            [_Fact("fact:1"), _Fact("fact:2"), _Fact("fact:3")],
        ),
    }


def _gold():
    return {
        "version": GOLD_SPLIT_VERSION,
        "qualification_job_id": "job-1",
        "annotated_by": "临床审核员",
        "entries": [
            {
                "predicate_id": "IN-01-A1",
                "predicate_identity_sha256": "a" * 64,
                "expected_fact_ids": ["fact:1", "fact:2"],
                "forbidden_fact_ids": ["fact:3"],
            },
            {
                "predicate_id": "IN-01-A2",
                "predicate_identity_sha256": "b" * 64,
                "expected_fact_ids": ["fact:1"],
            },
        ],
    }


def test_gold_split_accepts_valid_and_normalizes() -> None:
    gold = _validated_gold_split(_gold(), _verified())
    assert len(gold["entries"]) == 2


@pytest.mark.parametrize("mutate,reason", [
    (lambda g: g.update(version="binding-gold-split/v0"), "版本"),
    (lambda g: g.update(qualification_job_id="other"), "任务"),
    (lambda g: g.update(annotated_by=" "), "标注人"),
    (lambda g: g.update(entries=[]), "条目"),
    (lambda g: g["entries"][0].update(predicate_identity_sha256="c" * 64), "身份"),
    (lambda g: g["entries"].append(dict(g["entries"][0])), "重复"),
    (lambda g: g["entries"][0].update(expected_fact_ids=[1]), "期望类型"),
    (lambda g: g["entries"][0]["forbidden_fact_ids"].append("fact:1"), "重叠"),
    (lambda g: g["entries"][0]["expected_fact_ids"].append("fact:9"), "未知事实"),
])
def test_gold_split_rejects_invalid(mutate, reason) -> None:
    gold = _gold()
    mutate(gold)
    with pytest.raises(BindingEvaluationError):
        _validated_gold_split(gold, _verified())


def test_scoring_counts_recall_precision_and_missing() -> None:
    selections = {"a" * 64: {"fact:1", "fact:3"}, "b" * 64: set()}
    per_entry, recall, precision, silent_missing, forbidden_hits = _score_entries(
        _gold(), selections,
    )
    # entry1: expected {1,2}, selected {1,3} -> 1 correct, 0 wrong, 1 forbidden
    assert per_entry[0]["correct_count"] == 1
    assert per_entry[0]["wrong_selected_count"] == 0
    assert per_entry[0]["forbidden_selected_count"] == 1
    assert per_entry[0]["silent_missing"] is False
    # entry2: expected {1}, selected {} -> silent missing
    assert per_entry[1]["silent_missing"] is True
    assert recall == Decimal(1) / Decimal(3)
    assert precision == Decimal(1) / Decimal(2)
    assert silent_missing == 1
    assert forbidden_hits == 1


def test_scoring_with_no_selection_reports_unavailable_precision() -> None:
    *_, precision, _silent, _forbidden = _score_entries(_gold(), {})
    assert precision is None


def test_evaluated_route_requires_complete_fields() -> None:
    base = {
        "provider": "p", "base_url": "https://x", "model": "m",
        "reasoning_effort": "high", "max_tokens": 1024,
        "max_concurrency": 2, "fallback_base_url": "",
    }
    assert _evaluated_route(base).model == "m"
    incomplete = dict(base)
    incomplete.pop("max_concurrency")
    with pytest.raises(BindingEvaluationError):
        _evaluated_route(incomplete)
