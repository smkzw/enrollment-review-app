import asyncio
from dataclasses import replace
import json

import pytest
from pydantic import ValidationError

from app.domain.contracts.page_review import PageReviewLane
from app.domain.contracts.page_review_context import PageReviewContext
from app.domain.contracts.page_review_focus import PageReviewFocus
from app.llm.page_review_harness import PageCompletion, PageReviewConfigError, PageReviewHarnessError, read_page
from tests.v2.llm.test_page_review_harness import _routes, _page_input, _clause_pack, _main_response


def focus(**changes):
    return PageReviewFocus(**{
        "original_reconciliation_id": "original", "page_image_sha256": _page_input().page_image_sha256,
        "review_episode_id": "episode", "round_number": 1, "targets": ("项目甲",), **changes})


def page():
    return replace(_page_input(), review_context=PageReviewContext(
        review_episode_id="episode", episode_revision=1, stage="screening"))


@pytest.mark.parametrize("changes", [
    {"round_number": 3}, {"round_number": True}, {"candidate_excerpts": ("候选",)},
    {"round_number": 2}, {"round_number": 2, "previous_round_review_ids": ("a", "a")},
    {"targets": (" ",)}, {"targets": ("甲", "甲")},
])
def test_invalid_scope_rejected(changes):
    with pytest.raises(ValidationError):
        focus(**changes)


@pytest.mark.parametrize("mismatch", ["image", "episode", "effort", "handwriting"])
def test_wrong_scope_fails_before_model(mismatch):
    route = replace(_routes()[PageReviewLane.MAIN_A], reasoning_effort="high")
    scope = focus()
    if mismatch == "image":
        scope = focus(page_image_sha256="0" * 64)
    elif mismatch == "episode":
        scope = focus(review_episode_id="other")
    elif mismatch == "effort":
        route = replace(route, reasoning_effort="low")
    else:
        route = replace(route, lane=PageReviewLane.HANDWRITING_C)

    async def never(*args):
        pytest.fail("must reject before calling model")

    with pytest.raises(PageReviewConfigError):
        asyncio.run(read_page(route, page(), _clause_pack(), completion=never, review_focus=scope))


def test_targeted_scope_is_identity_bound_and_candidates_are_explicit():
    seen = []

    async def completion(route, messages, tokens):
        seen.append(messages)
        return PageCompletion(_main_response(), "stop", {})

    route = replace(_routes()[PageReviewLane.MAIN_A], reasoning_effort="high")
    scopes = [None, focus(), focus(round_number=2, previous_round_review_ids=("a", "b"),
                                  candidate_excerpts=("不同摘录一", "不同摘录二"))]
    records = [asyncio.run(read_page(route, page(), _clause_pack(), completion=completion,
                                    review_focus=scope)) for scope in scopes]
    assert len({record.page_review_id for record in records}) == 3
    assert len({record.response_sha256 for record in records}) == 1
    assert records[1].prompt_version.startswith("page-targeted-review/v3:")
    assert "clause_pack" in json.loads(seen[0][1]["content"][1]["text"])
    assert "clause_pack" not in json.loads(seen[1][1]["content"][1]["text"])
    assert json.loads(seen[1][-1]["content"])["candidates_visible"] is False
    assert json.loads(seen[2][-1]["content"])["candidates_visible"] is True
    assert "不强制二选一" in seen[2][0]["content"]


def test_targeted_response_cannot_emit_clause_signals():
    async def completion(*_args):
        return PageCompletion(_main_response(has_eligibility_value=True,
            clause_signals=[{"clause_id": "any", "signal": "mentions", "region": {"excerpt": "未见判断"}}]), "stop", {})
    route = replace(_routes()[PageReviewLane.MAIN_A], reasoning_effort="high")
    with pytest.raises(PageReviewHarnessError, match="不得输出条款"):
        asyncio.run(read_page(route, page(), _clause_pack(), completion=completion, review_focus=focus()))


def test_handwriting_scope_is_separate_and_excludes_ordinary_facts():
    from tests.v2.llm.test_page_review_format_repair import _valid_fact
    seen = []

    async def completion(_route, messages, _tokens):
        seen.append(messages)
        return PageCompletion(_main_response(has_eligibility_value=True, facts=[_valid_fact()]), "stop", {})

    route = replace(_routes()[PageReviewLane.MAIN_A], reasoning_effort="high")
    with pytest.raises(PageReviewHarnessError, match="手写"):
        asyncio.run(read_page(route, page(), _clause_pack(), completion=completion,
                             review_focus=focus(targets=(), handwriting_review=True)))
    prompt = json.loads(seen[0][1]["content"][1]["text"])
    assert prompt["output_schema"]["properties"]["facts"]["maxItems"] == 0
    assert json.loads(seen[0][-1]["content"])["handwriting_review"] is True
