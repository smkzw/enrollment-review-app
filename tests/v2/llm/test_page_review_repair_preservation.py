"""Synthetic offline checks; no reading result is medically accepted here."""

import copy
import json

import pytest

from app.llm.page_review_format_repair import evaluate_page_review_response
from app.llm.page_review_repair_preservation import check_repair_preservation
from tests.v2.domain.test_page_review_contracts import _handwriting
from tests.v2.llm.test_page_review_format_repair import _valid_fact
from tests.v2.llm.test_page_review_harness import _clause_pack, _main_response


def _check(previous, *, facts=(), handwriting=()):
    pack = _clause_pack()
    corrected = evaluate_page_review_response(
        _main_response(has_eligibility_value=bool(facts or handwriting),
                       facts=list(facts), handwriting=list(handwriting)),
        clause_pack=pack, review_focus=None,
    ).payload
    return check_repair_preservation(previous, corrected, clause_pack=pack)


def test_top_level_format_failure_keeps_valid_observation_protected():
    fact = _valid_fact()
    previous = _main_response(has_eligibility_value=False, facts=[fact], extra="invalid")
    renamed = {**fact, "observation_id": "renumbered"}
    result = _check(previous, facts=[renamed])
    assert result.original_parseable
    assert result.protected_observations == 1
    assert result.uncheckable_observations == 0
    assert result.missing_or_changed_observations == 0


@pytest.mark.parametrize("change", [
    {"raw_value": "5.7 mmol/L"},
    {"field_name": "另一检查项目"},
    {"region": {"excerpt": "其他原文"}},
    {"raw_text": "不同原文"},
    {"context": {"target_text": "另一对象", "time_text": "2026-09-02"}},
])
def test_changed_clinical_content_is_not_a_format_only_correction(change):
    fact = _valid_fact()
    result = _check(_main_response(facts=[fact]), facts=[{**fact, **change}])
    assert result.protected_observations == 1
    assert result.missing_or_changed_observations == 1
    assert result.additional_or_changed_observations == 1


def test_same_key_different_excerpt_and_multiplicity_are_not_collapsed():
    first = _valid_fact()
    second = {**first, "observation_id": "fact-2",
              "region": {"excerpt": "复查：检查值 5.6 mmol/L"}}
    third = {**first, "observation_id": "fact-3"}
    result = _check(_main_response(facts=[first, second, third]), facts=[first])
    assert result.protected_observations == 3
    assert result.missing_or_changed_observations == 2


def test_pending_handwritten_judgment_cannot_disappear_in_format_reread():
    handwritten = _handwriting().model_dump(mode="json")
    result = _check(_main_response(handwriting=[handwritten]))
    assert result.protected_observations == 1
    assert result.missing_or_changed_observations == 1


def test_invalid_item_is_reported_as_uncheckable_not_as_preserved():
    fact = _valid_fact()
    invalid = {**fact, "region": {"excerpt": "原文", "unexpected": True}}
    result = _check(_main_response(facts=[fact, invalid]), facts=[fact])
    assert result.protected_observations == 1
    assert result.uncheckable_observations == 1
    assert result.missing_or_changed_observations == 0


def test_invalid_outer_json_is_not_claimed_as_verified():
    result = _check('{"facts":[')
    assert not result.original_parseable
    assert result.protected_observations == 0


def test_input_is_unchanged_and_added_observations_are_not_accepted_by_this_check():
    fact = _valid_fact()
    before = copy.deepcopy(fact)
    previous = _main_response(facts=[fact])
    added = {**fact, "observation_id": "added", "raw_value": "8 mmol/L"}
    result = _check(previous, facts=[added, fact])
    assert fact == before
    assert json.loads(previous)["facts"] == [before]
    assert result.protected_observations == 1
    assert result.missing_or_changed_observations == 0
    assert result.additional_or_changed_observations == 1
