import json
import asyncio
from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.llm.page_review_transport_options import page_completion_options


@pytest.mark.parametrize("provider", ["omlx", "mtplx", "mlx-serve", "zhipu-coding-plan"])
def test_native_constraints_are_adapter_specific_and_preserve_prompt(provider):
    schema = {"type": "object", "required": ["facts"], "additionalProperties": False,
              "properties": {"facts": {"type": "array", "items": {
                  "type": "string", "minLength": 1, "pattern": r"\S"}}}}
    messages = [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,test"}},
        {"type": "text", "text": json.dumps({"output_schema": schema})}]}]
    before = deepcopy(messages)
    options = page_completion_options(provider, messages, 131072)
    assert messages == before
    if provider == "mtplx":
        assert options["response_format"]["json_schema"]["schema"] == schema
        assert options["extra_body"] == {"generation_mode": "mtp"}
        assert "temperature" not in options
        return
    if provider != "omlx":
        assert options == {}
        return
    projected = deepcopy(schema)
    del projected["properties"]["facts"]["items"]["pattern"]
    assert options["response_format"]["json_schema"]["schema"] == projected
    assert options["extra_body"] == {"thinking_budget": 131072}
    assert "temperature" not in options


def test_no_page_schema_does_not_change_other_requests():
    assert page_completion_options("omlx", [{"role": "user", "content": "hello"}], 128) == {}


def test_mtplx_conditional_decoding_subset_does_not_remove_product_checks():
    from app.domain.contracts.page_review import ClauseEvidenceSignal
    from pydantic import ValidationError
    schema = ClauseEvidenceSignal.model_json_schema()
    schema["properties"]["if"] = {"type": "string"}
    messages = [{"role": "user", "content": [{"type": "text", "text": json.dumps({"output_schema": schema})}]}]
    original = deepcopy(messages)
    options = page_completion_options("mtplx", messages, 65536)
    assert options["extra_body"] == {"generation_mode": "ar"}
    decoded = options["response_format"]["json_schema"]["schema"]
    assert not {"if", "then", "else"}.intersection(decoded)
    assert decoded["properties"]["if"] == {"type": "string"}
    assert decoded["required"] == schema["required"]
    assert messages == original
    with pytest.raises(ValidationError, match="必须携带原文摘录"):
        ClauseEvidenceSignal(clause_id="arbitrary-clause", signal="mentions")


def test_repair_keeps_original_schema_and_current_budget():
    messages = [{"role": "user", "content": [{"type": "text", "text": json.dumps({
        "output_schema": {"type": "object"}})}]}]
    original = page_completion_options("omlx", messages, 65536)
    messages.append({"role": "user", "content": "修复前次格式"})
    repaired = page_completion_options("omlx", messages, 131072)
    assert repaired["response_format"] == original["response_format"]
    assert repaired["extra_body"]["thinking_budget"] == 131072


@pytest.mark.parametrize("warning", [None, "299 omlx structured output not enforced"])
def test_sdk_native_body_and_downgrade_rejection(monkeypatch, warning):
    import httpx
    from app.domain.contracts.page_review import PageReviewLane
    from app.llm import page_review_harness as harness
    messages = [{"role": "user", "content": [{"type": "text", "text": json.dumps({
        "output_schema": {"type": "object"}})}]}]
    captured = []

    def handle(request):
        captured.append(json.loads(request.content))
        return httpx.Response(200, headers={"Warning": warning} if warning else {}, json={
            "id": "test", "object": "chat.completion", "created": 0, "model": "test",
            "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": "{}"}}]})

    class Client(httpx.AsyncClient):
        def __init__(self, **kwargs):
            super().__init__(**kwargs, transport=httpx.MockTransport(handle))

    monkeypatch.setattr(harness.httpx, "AsyncClient", Client)
    route = SimpleNamespace(lane=PageReviewLane.MAIN_B, provider="omlx", model="test", reasoning_effort="medium",
                            base_url="http://localhost/v1", api_key="test")
    if warning:
        with pytest.raises(harness.PageReviewHarnessError, match="未能启用"):
            asyncio.run(harness.direct_openai_completion(route, messages, 131072))
    else:
        assert asyncio.run(harness.direct_openai_completion(route, messages, 131072)).text == "{}"
    expected = page_completion_options("omlx", messages, 131072)
    assert captured[0]["response_format"] == expected["response_format"]
    assert captured[0]["thinking_budget"] == 131072
    assert captured[0]["max_tokens"] == 131072
    assert "temperature" not in captured[0]


def test_ollama_cloud_page_request_uses_direct_model_and_image(monkeypatch):
    import httpx
    from app.domain.contracts.page_review import PageReviewLane
    from app.llm import page_review_harness as harness
    from app.llm.page_review_harness import require_page_reader_routes

    route = require_page_reader_routes({
        "PAGE_REVIEW_MAIN_A_PROVIDER": "cms-router",
        "CMS_ROUTER_API_KEY": "main-a-only",
        "PAGE_REVIEW_MAIN_B_PROVIDER": "ollama-cloud",
        "PAGE_REVIEW_MAIN_B_MODEL": "deepseek-v4.1-flash",
        "PAGE_REVIEW_MAIN_B_REASONING_EFFORT": "high",
        "OLLAMA_API_KEY": "ollama-test-only",
    })[PageReviewLane.MAIN_B]
    messages = [{"role": "user", "content": [
        {"type": "text", "text": "只读取这一页"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,eA=="}},
    ]}]
    captured = []

    def handle(request):
        captured.append((str(request.url), json.loads(request.content)))
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, text=(
            'data: {"id":"ollama-test","model":"deepseek-v4.1-flash",'
            '"choices":[{"index":0,"delta":{"content":"{}"},"finish_reason":"stop"}]}\n\n'
            'data: [DONE]\n\n'
        ))

    class Client(httpx.AsyncClient):
        def __init__(self, **kwargs):
            super().__init__(**kwargs, transport=httpx.MockTransport(handle))

    monkeypatch.setattr(harness.httpx, "AsyncClient", Client)
    result = asyncio.run(harness.direct_openai_completion(route, messages, 65536))
    assert result.text == "{}"
    assert result.response_model == "deepseek-v4.1-flash"
    assert len(captured) == 1
    url, body = captured[0]
    assert url == "https://ollama.com/v1/chat/completions"
    assert body["model"] == "deepseek-v4.1-flash"
    assert body["reasoning_effort"] == "high"
    assert body["max_tokens"] == 65536
    assert body["messages"] == messages
    assert body["stream_options"] == {"include_usage": True}
    assert "response_format" not in body
    assert "temperature" not in body
