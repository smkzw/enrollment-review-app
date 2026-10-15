"""A one-sided missing time can request rereading, never automatic acceptance."""

import pytest
from pydantic import ValidationError

from app.domain.contracts.page_review import PageReviewRecord
from app.domain.page_normalization import fact_normalization_key
from app.domain.targeted_page_review import compare_targeted_reads, explicit_conflict_fields
from tests.v2.domain.test_page_review_contracts import _fact, _review_payload


def records(*, both_missing=False, right_patch=None, duplicate=False):
    result = []
    for lane in ("main-A", "main-B"):
        fact = _fact().model_dump(mode="json")
        fact["context"]["time_text"] = "2026-01-17" if lane == "main-A" and not both_missing else None
        if lane == "main-B" and right_patch:
            fact["context"].update(right_patch)
        key, value, unit = fact_normalization_key(fact["field_name"], fact["raw_value"], context=fact["context"])
        fact.update(normalization_key=key, normalized_value=value, normalized_unit=unit)
        facts = [fact]
        if duplicate and lane == "main-B":
            facts.append({**fact, "observation_id": "second-occurrence"})
        result.append(PageReviewRecord.model_validate({**_review_payload(), "lane": lane,
            "page_review_id": lane, "facts": facts}))
    return result


def test_missing_time_enters_reread_without_accepting_or_rewriting():
    pair = records()
    before = [r.model_dump() for r in pair]
    assert explicit_conflict_fields(pair) == ("实验室检查值",)
    assert compare_targeted_reads(pair, ("实验室检查值",)) == {
        "agreed_candidate_targets": [], "pending_targets": ["实验室检查值"],
        "candidate_auto_accept": False,
    }
    assert [r.model_dump() for r in pair] == before
    assert explicit_conflict_fields(list(reversed(pair))) == ("实验室检查值",)


@pytest.mark.parametrize("options", [
    {"both_missing": True}, {"duplicate": True},
    {"right_patch": {"target_text": "另一个检查项目"}},
    {"right_patch": {"location_text": "其他位置"}},
    {"right_patch": {"polarity": "negated"}},
    {"right_patch": {"time_text": "2026-01-17"}},
    {"right_patch": {"time_text": "2026-01-18"}},
])
def test_ambiguous_or_unrelated_observations_do_not_get_time_pairing(options):
    assert explicit_conflict_fields(records(**options)) == ()


def test_empty_target_is_rejected_before_pairing():
    with pytest.raises(ValidationError, match="target_text"):
        records(right_patch={"target_text": ""})
