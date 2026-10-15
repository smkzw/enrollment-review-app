"""判断检索读器 429 限流等待语义测试（合成假件，无真实模型）。

回归锚：runtime06c 第 19 页 GLM 429（0.32s 即拒）被 2 次硬重试耗尽、
诚实落页级失败。修复后读器与页判读 harness 同语义：429 按有界等待重试
（默认 12 次 × 60s），等待不消耗内容核查轮次；非 429 传输异常与上限耗尽
仍收敛 transport。两读器（单目标/批次）都必须覆盖。
"""
from __future__ import annotations

import asyncio
import json

import pytest

from app.llm import judgment_search_reader as reader_module
from app.llm.judgment_search_reader import (
    JudgmentSearchReaderError,
    read_judgment_search_page,
    read_judgment_search_page_batch,
)
from app.llm.page_review_harness import PageCompletion
from tests.v2.llm.test_judgment_search_batch_reader import (
    _page_input,
    _route,
    _scope,
    _TARGET_A,
)


class _RateLimited(Exception):
    """带 status_code=429 的假传输异常（模拟 openai RateLimitError 形状）。"""

    status_code = 429


def _ok_single_text(requirement_id: str) -> str:
    del requirement_id
    channel = {"disposition": "not_found", "candidates": []}
    return json.dumps(
        {"handwritten": channel, "printed_analysis": dict(channel)},
        ensure_ascii=False)


def test_single_reader_waits_through_rate_limit(monkeypatch):
    """单目标读器：429 → 等待 → 重试成功，不落失败。"""
    monkeypatch.setattr(reader_module, "_RATE_LIMIT_WAIT_SECONDS", 0.0)
    calls = {"n": 0}

    async def completion(route, messages, max_tokens):
        calls["n"] += 1
        if calls["n"] == 1:
            raise _RateLimited("rate limited")
        return PageCompletion(text=_ok_single_text(_scope("req-rl").requirement_id),
                              finish_reason="stop", usage={},
                              response_model=route.model)

    receipt = asyncio.run(read_judgment_search_page(
        scope=_scope("req-rl"), page_input=_page_input(), target_text=_TARGET_A,
        route=_route(), completion=completion,
    ))
    assert calls["n"] == 2
    assert receipt.page_result.handwritten.disposition.value == "not_found"


def test_batch_reader_rate_limit_exhausts_to_transport(monkeypatch):
    """批次读器：持续 429 超过等待上限 → 收敛 transport（诚实失败）。"""
    monkeypatch.setattr(reader_module, "_MAX_RATE_LIMIT_WAITS", 2)
    monkeypatch.setattr(reader_module, "_RATE_LIMIT_WAIT_SECONDS", 0.0)
    calls = {"n": 0}

    async def completion(route, messages, max_tokens):
        calls["n"] += 1
        raise _RateLimited("rate limited")

    with pytest.raises(JudgmentSearchReaderError) as error:
        asyncio.run(read_judgment_search_page_batch(
            page_input=_page_input(), route=_route(),
            targets=[(_scope("req-rl"), _TARGET_A)], completion=completion,
        ))
    assert error.value.failure_kind == "transport"
    assert calls["n"] == 3  # 首次 + 2 次等待后重试


def test_batch_reader_waits_through_rate_limit_then_succeeds(monkeypatch):
    """批次读器：429 → 等待 → 重试成功（与单读器对称）。"""
    monkeypatch.setattr(reader_module, "_RATE_LIMIT_WAIT_SECONDS", 0.0)
    calls = {"n": 0}

    async def completion(route, messages, max_tokens):
        calls["n"] += 1
        if calls["n"] == 1:
            raise _RateLimited("rate limited")
        text = json.dumps({"results": [
            {"requirement_id": _scope("req-rl").requirement_id,
             "handwritten": {"disposition": "not_found", "candidates": []},
             "printed_analysis": {"disposition": "not_found", "candidates": []}},
        ]}, ensure_ascii=False)
        return PageCompletion(text=text, finish_reason="stop", usage={},
                              response_model=route.model)

    receipts = asyncio.run(read_judgment_search_page_batch(
        page_input=_page_input(), route=_route(),
        targets=[(_scope("req-rl"), _TARGET_A)], completion=completion,
    ))
    assert calls["n"] == 2
    assert len(receipts) == 1
