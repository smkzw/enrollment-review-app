"""Deployment choices must survive the same product harness unchanged."""

import asyncio
from dataclasses import replace
import json

import httpx
import pytest

from app.domain.contracts.page_review import PageReviewLane
from app.llm.page_review_harness import (
    PageCompletion, PageReviewConfigError, PageReviewHarnessError,
    preflight_page_reader_routes, read_page, require_page_reader_routes,
)
from app.services.targeted_page_review_jobs import targeted_routes
from tests.v2.llm.test_page_review_harness import _clause_pack, _main_response, _page_input
from tests.v2.llm.test_targeted_page_review import focus, page


def deployment(**overrides):
    return require_page_reader_routes({
        "INDEPENDENT_VLM_PROVIDER": "zhipu-coding-plan",
        "INDEPENDENT_VLM_API_KEY": "test-a",
        "PAGE_REVIEW_MAIN_A_MODEL": "glm-5.3-flash",
        "PAGE_REVIEW_MAIN_A_BASE_URL": "https://cloud.example/v1",
        "PAGE_REVIEW_MAIN_A_REASONING_EFFORT": "high",
        "PAGE_REVIEW_MAIN_B_PROVIDER": "mtplx",
        "PAGE_REVIEW_MAIN_B_MODEL": "mtplx-flash-next-optimized-speed",
        "PAGE_REVIEW_MAIN_B_BASE_URL": "http://localhost:8002/v1",
        "PAGE_REVIEW_LOCAL_API_KEY": "test-local",
        "PAGE_REVIEW_MAIN_B_REASONING_EFFORT": "xhigh",
        "PAGE_REVIEW_MAX_TOKENS": "65536",
        "PAGE_REVIEW_CLOUD_CONCURRENCY": "2",
        **overrides,
    })


def test_current_pair_preserves_explicit_effort_budget_and_local_credential():
    routes = deployment()
    assert routes[PageReviewLane.MAIN_A].reasoning_effort == "high"
    assert routes[PageReviewLane.MAIN_B].reasoning_effort == "xhigh"
    assert routes[PageReviewLane.MAIN_B].api_key == "test-local"
    assert [routes[lane].max_concurrency for lane in PageReviewLane if lane in routes] == [2, 1]
    assert {route.max_tokens for route in routes.values()} == {65536}


def test_targeted_review_preserves_both_frozen_routes_instead_of_downgrading():
    routes = deployment()
    assert targeted_routes(routes) == routes
    seen = []

    async def completion(route, messages, budget):
        seen.append((route.model, route.reasoning_effort, budget))
        return PageCompletion(_main_response(), "stop", {})

    for route in targeted_routes(routes).values():
        asyncio.run(read_page(route, page(), _clause_pack(), completion=completion, review_focus=focus()))
    assert seen == [("glm-5.3-flash", "high", 65536),
                    ("mtplx-flash-next-optimized-speed", "xhigh", 65536)]


def test_supported_adapter_does_not_hardcode_a_clinical_model_name():
    routes = deployment(PAGE_REVIEW_MAIN_B_MODEL="another-vision-weight")
    assert routes[PageReviewLane.MAIN_B].model == "another-vision-weight"


@pytest.mark.parametrize("value", ["8192", "16384", "131073", "garbage"])
def test_new_deployments_reject_unsupported_output_allowances(value):
    with pytest.raises(PageReviewConfigError):
        deployment(PAGE_REVIEW_MAX_TOKENS=value)


def test_declared_model_capability_blocks_request_before_inference(monkeypatch):
    import app.llm.page_review_harness as harness
    requested = []

    def handle(request):
        requested.append(request.method)
        return httpx.Response(200, json={"data": [{
            "id": "mtplx-flash-next-optimized-speed", "supports_vision": True,
            "supported_reasoning_efforts": ["low", "high"], "max_output_tokens": 32768,
        }]})

    class Client(httpx.AsyncClient):
        def __init__(self, **kwargs):
            super().__init__(**kwargs, transport=httpx.MockTransport(handle))

    monkeypatch.setattr(harness.httpx, "AsyncClient", Client)
    with pytest.raises(PageReviewConfigError):
        asyncio.run(harness.resolve_route_model(deployment()[PageReviewLane.MAIN_B]))
    assert requested == ["GET"]


def test_length_at_maximum_budget_does_not_send_a_larger_request():
    budgets = []

    async def completion(route, messages, budget):
        budgets.append(budget)
        return PageCompletion("", "length", {"completion_tokens": budget})

    route = replace(deployment()[PageReviewLane.MAIN_A], max_tokens=131072)
    with pytest.raises(PageReviewHarnessError, match="额度"):
        asyncio.run(read_page(route, _page_input(), _clause_pack(), completion=completion))
    assert budgets == [131072]


def test_mtplx_image_json_uses_mtp_without_altering_the_prompt_or_sampling(monkeypatch):
    import app.llm.page_review_harness as harness
    messages = harness.build_page_review_messages(deployment()[PageReviewLane.MAIN_B], _page_input(), _clause_pack())
    captured = []

    def handle(request):
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"id": "test", "object": "chat.completion", "created": 0,
            "model": "mtplx-flash-next-optimized-speed", "choices": [{"index": 0,
            "finish_reason": "stop", "message": {"role": "assistant", "content": _main_response()}}]})

    class Client(httpx.AsyncClient):
        def __init__(self, **kwargs):
            super().__init__(**kwargs, transport=httpx.MockTransport(handle))

    monkeypatch.setattr(harness.httpx, "AsyncClient", Client)
    result = asyncio.run(harness.direct_openai_completion(deployment()[PageReviewLane.MAIN_B], messages, 65536))
    body = captured[0]
    assert body["generation_mode"] == "mtp"
    assert body["reasoning_effort"] == "xhigh"
    assert body["max_tokens"] == 65536
    assert body["response_format"]["type"] == "json_schema"
    assert body["messages"] == messages
    assert "temperature" not in body and "top_p" not in body
    assert result.transport_contract == "mtplx-schema-mtp-conditional-validation-v3"
