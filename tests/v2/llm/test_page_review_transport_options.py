import json
import asyncio
from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.llm.page_review_transport_options import page_completion_options


@pytest.mark.parametrize("provider", ["omlx", "mtplx", "mlx-serve", "zhipu-coding-plan"])
def test_native_constraints_are_omlx_only_and_preserve_prompt(provider):
    schema = {"type": "object", "required": ["facts"], "additionalProperties": False,
              "properties": {"facts": {"type": "array", "items": {
                  "type": "string", "minLength": 1, "pattern": r"\S"}}}}
    messages = [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,test"}},
        {"type": "text", "text": json.dumps({"output_schema": schema})}]}]
    before = deepcopy(messages)
    options = page_completion_options(provider, messages, 131072)
    assert messages == before
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
    route = SimpleNamespace(provider="omlx", model="test", reasoning_effort="medium",
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
