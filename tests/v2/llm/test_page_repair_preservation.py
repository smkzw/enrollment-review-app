"""Formatting repair must not silently replace otherwise valid observations."""

import asyncio
import json

import pytest

from app.domain.contracts.page_review import PageReviewLane
from app.llm.page_review_harness import PageCompletion, PageReviewHarnessError, read_page
from tests.v2.llm.test_page_review_format_repair import _valid_fact
from tests.v2.llm.test_page_review_harness import _clause_pack, _main_response, _page_input, _routes


@pytest.mark.parametrize("change", ["drop", "value", "date", "excerpt"])
def test_format_repair_cannot_erase_or_change_valid_observation(change):
    original = _valid_fact()
    first = _main_response(has_eligibility_value=False, facts=[original])
    repaired = dict(original)
    if change == "value":
        repaired["raw_value"] = "3.1 mmol/L"
    elif change == "date":
        repaired["context"] = {"target_text": "检查值", "time_text": "2026-09-01"}
    elif change == "excerpt":
        repaired["region"] = {"excerpt": "另一行的检查值"}
    second = _main_response(has_eligibility_value=change != "drop", facts=[] if change == "drop" else [repaired])
    responses = iter([first, second])
    calls = []

    async def completion(*_args):
        calls.append(1)
        return PageCompletion(next(responses), "stop", {})

    with pytest.raises(PageReviewHarnessError, match="原有观察"):
        asyncio.run(read_page(_routes()[PageReviewLane.MAIN_A], _page_input(),
                              _clause_pack(), completion=completion))
    assert len(calls) == 2
    assert json.loads(first)["facts"] == [original]


def test_format_repair_allows_renumbering_and_reordering_without_content_change():
    first_fact = _valid_fact()
    second_fact = {**_valid_fact(), "observation_id": "fact-2",
                   "context": {"target_text": "另一次检查", "time_text": "2026-09-02"}}
    first = _main_response(has_eligibility_value=False, facts=[first_fact, second_fact])
    second = _main_response(has_eligibility_value=True, facts=[
        {**second_fact, "observation_id": "renumbered-1"},
        {**first_fact, "observation_id": "renumbered-2"}])
    responses = iter([first, second])

    async def completion(*_args):
        return PageCompletion(next(responses), "stop", {})

    record = asyncio.run(read_page(_routes()[PageReviewLane.MAIN_A], _page_input(),
                                   _clause_pack(), completion=completion))
    assert len(record.facts) == 2
    assert record.facts[0].context.time_text == "2026-09-02"


def test_repaired_read_identity_retains_the_actual_repair_context():
    final = _main_response(has_eligibility_value=True, facts=[_valid_fact()])
    records = []
    for first in (None, _main_response(has_eligibility_value=False, facts=[_valid_fact()]),
                  _main_response(has_eligibility_value=True, facts=[_valid_fact()], extra_field="invalid")):
        responses = iter([final] if first is None else [first, final])

        async def completion(*_args):
            return PageCompletion(next(responses), "stop", {})

        records.append(asyncio.run(read_page(_routes()[PageReviewLane.MAIN_A], _page_input(),
                                             _clause_pack(), completion=completion)))
    assert len({record.response_sha256 for record in records}) == 1
    assert len({record.page_review_id for record in records}) == 3
    # The base prompt stays compatible; the full request is retained in job receipts.
    assert len({record.prompt_version for record in records}) == 1
