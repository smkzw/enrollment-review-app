"""One-shot format-repair reread: synthetic coverage, no real model calls."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace

import pytest

from app.domain.contracts.page_review import PageReviewLane
from app.domain.contracts.page_review_context import PageReviewContext
from app.domain.contracts.page_review_focus import PageReviewFocus
from app.llm.page_review_format_repair import (
    PAGE_REVIEW_FORMAT_REPAIR_VERSION,
    build_format_repair_messages,
)
from app.llm.page_review_harness import (
    PageCompletion,
    PageReviewHarnessError,
    read_page,
)
from tests.v2.llm.test_page_review_harness import (
    _clause_pack,
    _main_response,
    _page_input,
    _routes,
)


def _valid_fact() -> dict:
    return {
        "observation_id": "fact-1", "field_name": "检查值",
        "raw_text": "检查值 5.6 mmol/L", "raw_value": "5.6 mmol/L",
        "region": {"excerpt": "检查值 5.6 mmol/L"},
    }


def _recorder(handler):
    calls: list[list[dict]] = []
    routes: list = []
    budgets: list[int] = []

    async def completion(route, messages, max_tokens):
        calls.append(messages)
        routes.append(route)
        budgets.append(max_tokens)
        return await handler(messages, max_tokens)

    return calls, routes, budgets, completion


def test_valid_first_response_reads_once_without_repair_turn():
    calls, routes, _, completion = _recorder(
        lambda _messages, _budget: asyncio.sleep(0, result=PageCompletion(_main_response(), "stop", {})))

    record = asyncio.run(read_page(_routes()[PageReviewLane.MAIN_A], _page_input(),
                                   _clause_pack(), completion=completion))

    assert len(calls) == 1
    assert len(calls[0]) == 2
    assert record.prompt_version == "page-review-r3/v13"
    assert record.response_sha256


@pytest.mark.parametrize("first_response", [
    # 事故主因一：region 对象携带 location 等额外字段。
    _main_response(has_eligibility_value=True, facts=[{
        **_valid_fact(), "region": {"excerpt": "检查值 5.6 mmol/L", "location": "第3行"}}]),
    # 事故主因二：has_eligibility_value=false 却携带 facts。
    _main_response(has_eligibility_value=False, facts=[_valid_fact()]),
    # 事故主因三：复制整个输入模板（顶层多出 clause_pack/output_schema 等字段）。
    _main_response(has_eligibility_value=False, clause_pack={"clauses": []}, output_schema={}),
    # 事故主因五：invalid JSON。
    "抱歉，我无法按要求返回 JSON。",
])
def test_format_failures_get_one_same_prompt_reread_then_correct(first_response):
    corrected = PageCompletion(_main_response(has_eligibility_value=True, facts=[_valid_fact()]),
                               "stop", {})

    def handler(messages, _budget):
        if len(calls) == 1:
            return asyncio.sleep(0, result=PageCompletion(first_response, "stop", {}))
        return asyncio.sleep(0, result=corrected)

    calls, routes, _, completion = _recorder(handler)

    record = asyncio.run(read_page(_routes()[PageReviewLane.MAIN_A], _page_input(),
                                   _clause_pack(), completion=completion))

    # 恰好一次格式纠正：第一次失败 + 一次重读，没有更多调用。
    assert len(calls) == 2
    assert routes[0] is routes[1]
    # 同一完整原提示与同一原图：system 与页输入逐字节相同，仅追加纠正消息。
    assert calls[1][0] == calls[0][0]
    assert calls[1][1] == calls[0][1]
    assert len(calls[1]) == 3
    repair = json.loads(calls[1][2]["content"])
    assert repair["format_repair"]["repair_version"] == PAGE_REVIEW_FORMAT_REPAIR_VERSION
    assert repair["format_repair"]["validation_errors"]
    assert repair["format_repair"]["previous_response"] == first_response
    assert any("不可信参考" in item for item in repair["format_repair"]["requirements"])
    assert any("重新读取本页原图" in item for item in repair["format_repair"]["requirements"])
    assert record.facts[0].observation_id == "fact-1"


def test_repair_turn_keeps_original_image_bytes():
    async def broken_once(messages, _budget):
        if len(calls) == 1:
            return PageCompletion("{不是JSON", "stop", {})
        return PageCompletion(_main_response(), "stop", {})

    calls, _, _, completion = _recorder(broken_once)
    asyncio.run(read_page(_routes()[PageReviewLane.MAIN_A], _page_input(),
                          _clause_pack(), completion=completion))
    first_image = calls[0][1]["content"][0]["image_url"]["url"]
    repair_image = calls[1][1]["content"][0]["image_url"]["url"]
    assert first_image == repair_image
    assert first_image.startswith("data:image/")


def test_second_format_failure_fails_explicitly_without_third_call():
    calls, _, _, completion = _recorder(lambda _messages, _budget: asyncio.sleep(
        0, result=PageCompletion(_main_response(has_eligibility_value=True), "stop", {})))

    with pytest.raises(PageReviewHarnessError) as error:
        asyncio.run(read_page(_routes()[PageReviewLane.MAIN_A], _page_input(),
                              _clause_pack(), completion=completion))

    assert len(calls) == 2
    assert error.value.failure_kind == "schema"
    assert "格式纠正一次后仍失败" in str(error.value)
    assert "不符合页级合同" in str(error.value)


def test_invalid_json_failure_kind_survives_exhausted_repair():
    calls, _, _, completion = _recorder(lambda _messages, _budget: asyncio.sleep(
        0, result=PageCompletion("仍然不是JSON", "stop", {})))

    with pytest.raises(PageReviewHarnessError) as error:
        asyncio.run(read_page(_routes()[PageReviewLane.MAIN_A], _page_input(),
                              _clause_pack(), completion=completion))

    assert len(calls) == 2
    assert error.value.failure_kind == "invalid_json"


def test_unknown_clause_is_reported_in_repair_then_corrected():
    def respond(messages, _budget):
        if len(messages) == 2:
            payload = _main_response(has_eligibility_value=True, clause_signals=[
                {"clause_id": "unknown-clause", "signal": "mentions",
                 "region": {"excerpt": "记录"}}])
        else:
            payload = _main_response(has_eligibility_value=True, clause_signals=[
                {"clause_id": "component-1", "signal": "mentions",
                 "region": {"excerpt": "记录"}}])
        return asyncio.sleep(0, result=PageCompletion(payload, "stop", {}))

    calls, _, _, completion = _recorder(respond)
    record = asyncio.run(read_page(_routes()[PageReviewLane.MAIN_A], _page_input(),
                                   _clause_pack(), completion=completion))

    assert len(calls) == 2
    repair = json.loads(calls[1][2]["content"])
    assert any("unknown-clause" in item for item in repair["format_repair"]["validation_errors"])
    assert record.clause_signals[0].clause_id == "component-1"


def test_date_ambiguity_is_not_repairable_and_reads_once():
    calls, _, _, completion = _recorder(lambda _messages, _budget: asyncio.sleep(0, result=(
        PageCompletion(_main_response(has_eligibility_value=True, facts=[{
            "observation_id": "fact-1", "field_name": "检查日期",
            "raw_text": "2026-13-45", "raw_value": "2026-13-45",
            "region": {"excerpt": "2026-13-45"},
        }]), "stop", {}))))

    with pytest.raises(PageReviewHarnessError) as error:
        asyncio.run(read_page(_routes()[PageReviewLane.MAIN_A], _page_input(),
                              _clause_pack(), completion=completion))

    # 日期/数值歧义不得用格式纠正改写：只有一次调用，立即显式失败。
    assert len(calls) == 1
    assert "资料包含无效日期或数值" in str(error.value)
    assert error.value.failure_kind == "schema"


def test_rate_limit_during_repair_does_not_consume_the_single_repair():
    class RateLimited(RuntimeError):
        status_code = 429

    waits: list[float] = []
    valid_repair = PageCompletion(_main_response(), "stop", {})

    def handler(messages, _budget):
        if len(messages) == 2:
            return asyncio.sleep(0, result=PageCompletion("{残缺", "stop", {}))
        if len(calls) == 3:
            return asyncio.sleep(0, result=valid_repair)
        raise RateLimited("429")

    calls, _, _, completion = _recorder(handler)

    async def sleep(seconds):
        waits.append(seconds)

    record = asyncio.run(read_page(_routes()[PageReviewLane.MAIN_A], _page_input(),
                                   _clause_pack(), completion=completion, sleep=sleep))

    assert len(calls) == 3
    assert waits == [60]
    # 429 重试不消耗唯一一次格式纠正：第 2、3 次调用都携带同一条纠正消息。
    assert len(calls[1]) == 3 and len(calls[2]) == 3
    assert calls[2][2] == calls[1][2]
    assert record.facts == []


def test_length_boundary_still_applies_to_the_repair_turn():
    def respond(messages, budget):
        if len(messages) == 2:
            return asyncio.sleep(0, result=PageCompletion(_main_response(has_eligibility_value=True), "stop", {}))
        if budget == 24000:
            return asyncio.sleep(0, result=PageCompletion(_main_response(), "stop", {}))
        return asyncio.sleep(0, result=PageCompletion(_main_response(), "length", {}))

    calls, _, budgets, completion = _recorder(respond)
    record = asyncio.run(read_page(_routes()[PageReviewLane.MAIN_A], _page_input(),
                                   _clause_pack(), completion=completion))

    assert budgets == [12000, 12000, 24000]
    assert len(calls) == 3
    assert len(calls[2]) == 3
    assert record.prompt_version == "page-review-r3/v13"


@pytest.mark.parametrize("cancel_on", ["first", "repair"])
def test_cancellation_is_never_swallowed_by_format_repair(cancel_on):
    def respond(_messages, _budget):
        if cancel_on == "repair":
            return asyncio.sleep(0, result=PageCompletion("{残缺", "stop", {}))
        raise asyncio.CancelledError()

    async def handler(messages, _budget):
        if len(messages) == 2:
            return await respond(messages, _budget)
        raise asyncio.CancelledError()

    _, _, _, completion = _recorder(handler)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(read_page(_routes()[PageReviewLane.MAIN_A], _page_input(),
                              _clause_pack(), completion=completion))


def test_failed_repair_does_not_leak_into_the_next_read():
    def always_invalid(_messages, _budget):
        return asyncio.sleep(0, result=PageCompletion(_main_response(has_eligibility_value=True), "stop", {}))

    calls_a, _, _, completion_a = _recorder(always_invalid)
    with pytest.raises(PageReviewHarnessError):
        asyncio.run(read_page(_routes()[PageReviewLane.MAIN_A], _page_input(),
                              _clause_pack(), completion=completion_a))

    calls_b, _, _, completion_b = _recorder(lambda _messages, _budget: asyncio.sleep(
        0, result=PageCompletion(_main_response(), "stop", {})))
    record = asyncio.run(read_page(_routes()[PageReviewLane.MAIN_B], _page_input(),
                                   _clause_pack(), completion=completion_b))

    # 下一读从干净的两条原提示开始，不携带上一读的纠正消息或上一回答。
    assert len(calls_b[0]) == 2
    assert record.lane == PageReviewLane.MAIN_B


def test_error_messages_and_repair_payload_never_contain_credentials():
    route = _routes()[PageReviewLane.MAIN_A]

    def always_invalid(_messages, _budget):
        return asyncio.sleep(0, result=PageCompletion(_main_response(has_eligibility_value=True), "stop", {}))

    calls, _, _, completion = _recorder(always_invalid)
    with pytest.raises(PageReviewHarnessError) as error:
        asyncio.run(read_page(route, _page_input(), _clause_pack(), completion=completion))

    assert route.api_key
    assert route.api_key not in str(error.value)
    for call in calls:
        for message in call:
            assert route.api_key not in json.dumps(message, ensure_ascii=False)


def test_targeted_review_repair_stays_inside_focus_scope():
    focus = PageReviewFocus(original_reconciliation_id="original",
                            page_image_sha256=_page_input().page_image_sha256,
                            review_episode_id="episode", round_number=1, targets=("项目甲",))
    page = replace(_page_input(), review_context=PageReviewContext(
        review_episode_id="episode", episode_revision=1, stage="screening"))

    def respond(messages, _budget):
        if len(messages) == 3:
            payload = _main_response(has_eligibility_value=True, clause_signals=[
                {"clause_id": "component-1", "signal": "mentions",
                 "region": {"excerpt": "记录"}}])
        else:
            payload = _main_response()
        return asyncio.sleep(0, result=PageCompletion(payload, "stop", {}))

    calls, _, _, completion = _recorder(respond)
    route = _routes()[PageReviewLane.MAIN_A]
    record = asyncio.run(read_page(replace(route, reasoning_effort="high"), page,
                                   _clause_pack(), completion=completion, review_focus=focus))

    assert len(calls) == 2
    # 针对性复核原提示为三条（system、页输入、targets），纠正消息追加为第四条。
    assert len(calls[0]) == 3 and len(calls[1]) == 4
    assert calls[1][:3] == calls[0]
    assert "format_repair" in calls[1][3]["content"]
    assert record.prompt_version.startswith("page-targeted-review/v3:")
    assert record.clause_signals == []


def test_build_format_repair_messages_does_not_mutate_original_messages():
    original = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]
    snapshot = [dict(message) for message in original]

    repaired = build_format_repair_messages(original, previous_response_text="旧回答",
                                            errors=["错误一"])

    assert original == snapshot
    assert len(repaired) == 3
    payload = json.loads(repaired[2]["content"])
    assert payload["format_repair"]["previous_response"] == "旧回答"
    assert payload["format_repair"]["validation_errors"] == ["错误一"]
