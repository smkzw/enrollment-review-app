"""逐页判读云端补全的流式传输合同。

网关（cms-router 等）对长生成有短超时，非流式请求在首字前被 504 截断；
云端道必须流式累积，并以完整结束事件为准；不支持 stream_options 的端点
回退纯流式（用量缺失允许，不作为判读依据）。
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.llm.page_review_harness import (
    PageReviewHarnessError,
    _streamed_chat_completion,
)


def _chunk(*, content=None, reasoning=None, finish=None, usage=None, model="m1", id="c1"):
    delta = SimpleNamespace(content=content, reasoning_content=reasoning)
    return SimpleNamespace(
        model=model, id=id, usage=usage,
        choices=[SimpleNamespace(delta=delta, finish_reason=finish)],
    )


def _client(chunks, *, reject_stream_options=False):
    calls = []

    async def _create(**kwargs):
        calls.append(kwargs)
        if reject_stream_options and kwargs.get("stream_options"):
            raise RuntimeError("stream_options is not supported")
        if kwargs.get("stream") is not True:
            raise AssertionError("云端补全必须使用流式")

        async def _iterator():
            for c in chunks:
                yield c

        return _iterator()

    return SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=_create))
    ), calls


def _usage():
    return SimpleNamespace(model_dump=lambda: {"prompt_tokens": 3, "completion_tokens": 5})


def test_streaming_accumulates_content_reasoning_and_usage():
    client, calls = _client([
        _chunk(reasoning="思考"),
        _chunk(content="你好"),
        _chunk(content="，世界", finish="stop", usage=_usage()),
    ])
    response = asyncio.run(_streamed_chat_completion(
        client, {"model": "m1", "messages": [], "max_tokens": 10}))
    assert response.choices[0].message.content == "你好，世界"
    assert response.choices[0].message.reasoning_content == "思考"
    assert response.choices[0].finish_reason == "stop"
    assert response.usage.model_dump()["completion_tokens"] == 5
    assert calls[0]["stream_options"] == {"include_usage": True}


def test_missing_finish_event_fails_closed():
    client, _ = _client([_chunk(content="半截")])
    with pytest.raises(PageReviewHarnessError):
        asyncio.run(_streamed_chat_completion(
            client, {"model": "m1", "messages": [], "max_tokens": 10}))


def test_endpoint_without_stream_options_falls_back_pure_streaming():
    client, calls = _client(
        [_chunk(content="OK", finish="stop")], reject_stream_options=True)
    response = asyncio.run(_streamed_chat_completion(
        client, {"model": "m1", "messages": [], "max_tokens": 10}))
    assert response.choices[0].message.content == "OK"
    assert calls[0].get("stream_options") is not None
    assert calls[1].get("stream_options") is None


def test_other_errors_are_not_swallowed():
    client, _ = _client([])

    async def _create(**kwargs):
        raise RuntimeError("connection refused")

    client.chat.completions.create = _create
    with pytest.raises(RuntimeError):
        asyncio.run(_streamed_chat_completion(
            client, {"model": "m1", "messages": [], "max_tokens": 10}))
