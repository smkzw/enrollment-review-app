"""外部共享 MTPLX 实例（多路复用）的逐页判读预检合同。

未配置产品装卸清单、端口上已有外部实例在服务唯一模型时：
- /models 报告的模型 id 与配置名不同（MTPLX 内部 id）→ 不再直接拒绝；
- 身份由 /health 的 ``model_path`` 逐词绑定配置名，模型不符仍失败关闭；
- /health 声明 ``vision.enabled`` 时预检放行，未声明时仍失败关闭。
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from app.domain.contracts.page_review import PageReviewLane
from app.llm.page_review_harness import (
    PageReviewConfigError,
    resolve_route_model,
    require_page_reader_routes,
)


def _route():
    return require_page_reader_routes({
        "INDEPENDENT_VLM_PROVIDER": "zhipu-coding-plan",
        "INDEPENDENT_VLM_API_KEY": "test-a",
        "PAGE_REVIEW_MAIN_A_MODEL": "glm-5.3-flash",
        "PAGE_REVIEW_MAIN_A_BASE_URL": "https://cloud.example/v1",
        "PAGE_REVIEW_MAIN_B_PROVIDER": "mtplx",
        "PAGE_REVIEW_MAIN_B_MODEL": "mtplx-flash-next-optimized-speed",
        "PAGE_REVIEW_MAIN_B_BASE_URL": "http://localhost:8002/v1",
        "PAGE_REVIEW_LOCAL_API_KEY": "test-local",
        "PAGE_REVIEW_MAIN_B_REASONING_EFFORT": "xhigh",
        "PAGE_REVIEW_MAX_TOKENS": "65536",
        "PAGE_REVIEW_CLOUD_CONCURRENCY": "2",
    })[PageReviewLane.MAIN_B]


def _mock_client(monkeypatch, models_json, health_json):
    import app.llm.mtplx_model_lifecycle as _lifecycle
    monkeypatch.setattr(_lifecycle, "_external_shared_mtplx_available",
                        lambda base_url, model: True)

    calls = []

    def handle(request):
        calls.append(str(request.url))
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json=models_json)
        if request.url.path.endswith("/health"):
            return httpx.Response(200, json=health_json)
        return httpx.Response(404)

    class Client(httpx.AsyncClient):
        def __init__(self, **kwargs):
            super().__init__(**kwargs, transport=httpx.MockTransport(handle))

    monkeypatch.setattr(
        __import__("app.llm.page_review_harness", fromlist=["httpx"]).httpx,
        "AsyncClient", Client,
    )
    return calls


def test_external_shared_instance_preflight_passes_with_health_vision(monkeypatch):
    route = _route()
    _mock_client(
        monkeypatch,
        {"data": [{"id": "mtplx-qwen36-27b-native-mtp", "context_length": 262144}]},
        {"ok": True, "model": "mtplx-qwen36-27b-native-mtp",
         "model_path": "/models/Youssofal--Qwen3.8-Flash-Next-MTPLX-Optimized-Speed",
         "vision": {"enabled": True, "formats": ["png", "jpeg"]}},
    )
    resolved = asyncio.run(resolve_route_model(route))
    assert resolved.model == "mtplx-flash-next-optimized-speed"


def test_external_shared_instance_with_wrong_model_fails_closed(monkeypatch):
    route = _route()
    _mock_client(
        monkeypatch,
        {"data": [{"id": "mtplx-qwen36-27b-native-mtp", "context_length": 262144}]},
        {"ok": True, "model": "mtplx-qwen36-27b-native-mtp",
         "model_path": "/models/Youssofal--Qwen3.8-27B-MTPLX-Optimized-Quality",
         "vision": {"enabled": True}},
    )
    with pytest.raises(PageReviewConfigError):
        asyncio.run(resolve_route_model(route))


def test_external_shared_instance_without_vision_declaration_fails_closed(monkeypatch):
    route = _route()
    _mock_client(
        monkeypatch,
        {"data": [{"id": "mtplx-qwen36-27b-native-mtp", "context_length": 262144}]},
        {"ok": True, "model": "mtplx-qwen36-27b-native-mtp",
         "model_path": "/models/Youssofal--Qwen3.8-Flash-Next-MTPLX-Optimized-Speed"},
    )
    with pytest.raises(PageReviewConfigError):
        asyncio.run(resolve_route_model(route))


def test_multi_model_port_with_unmatched_id_still_rejected(monkeypatch):
    route = _route()
    _mock_client(
        monkeypatch,
        {"data": [{"id": "a"}, {"id": "b"}]},
        {"ok": True, "model_path": "/models/Youssofal--Qwen3.8-Flash-Next-MTPLX-Optimized-Speed"},
    )
    with pytest.raises(PageReviewConfigError):
        asyncio.run(resolve_route_model(route))


def test_gateway_publishes_prefixed_id_but_accepts_root_name(monkeypatch):
    route = require_page_reader_routes({
        "INDEPENDENT_VLM_PROVIDER": "zhipu-coding-plan",
        "INDEPENDENT_VLM_API_KEY": "test-a",
        "PAGE_REVIEW_MAIN_B_PROVIDER": "cms-smk",
        "PAGE_REVIEW_MAIN_B_MODEL": "MiniMax-M3",
        "PAGE_REVIEW_MAIN_B_BASE_URL": "http://gateway.example/v1",
        "PAGE_REVIEW_MAIN_B_API_KEY": "test-b",
        "PAGE_REVIEW_MAIN_B_REASONING_EFFORT": "xhigh",
        "PAGE_REVIEW_MAX_TOKENS": "65536",
        "PAGE_REVIEW_CLOUD_CONCURRENCY": "2",
    })[PageReviewLane.MAIN_B]
    _mock_client(
        monkeypatch,
        {"data": [{"id": "/v1/MiniMax-M3", "root": "MiniMax-M3", "name": "MiniMax-M3",
                   "context_length": 1048576, "max_output_tokens": 512000}]},
        {},
    )
    resolved = asyncio.run(resolve_route_model(route))
    assert resolved.model == "MiniMax-M3"
