import asyncio

import httpx
import pytest

from app.domain.contracts.page_review import PageReviewLane
from app.llm import page_review_harness as harness
from app.llm.page_review_harness import require_page_reader_routes
from app.services.page_review_job_service import route_identity
from app.services.page_review_runtime import PageReviewRuntime, PageReviewUnavailable


MODEL = "hub/ddalcu_Qwen3.8-Flash-Next-MLX-Serve-mixed-4-8bit"


def test_invalid_read_only_identity_reports_unavailable(monkeypatch):
    monkeypatch.setenv("PAGE_REVIEW_MAIN_B_PROVIDER", "invalid-provider")
    runtime = PageReviewRuntime(None, None)
    with pytest.raises(PageReviewUnavailable) as error:
        runtime.main_reader_identity()
    assert error.value.status_code == 503
    assert runtime._executor is None


def test_read_only_identity_needs_no_model_credentials(monkeypatch):
    monkeypatch.setattr(harness, "PAGE_REVIEW_MAIN_A_API_KEY", "")
    monkeypatch.delenv("PAGE_REVIEW_MAIN_A_API_KEY", raising=False)
    monkeypatch.delenv("INDEPENDENT_VLM_API_KEY", raising=False)
    runtime = PageReviewRuntime(None, None)
    assert len(runtime.main_reader_identity()) == 64
    assert runtime._executor is None
    with pytest.raises(harness.PageReviewConfigError, match="凭据"):
        require_page_reader_routes()


def test_remote_provider_never_receives_another_providers_fallback_key():
    with pytest.raises(harness.PageReviewConfigError, match="PAGE_REVIEW_MAIN_A_API_KEY"):
        require_page_reader_routes({
            "PAGE_REVIEW_MAIN_A_PROVIDER": "ollama-cloud",
            "PAGE_REVIEW_MAIN_A_MODEL": "deepseek-v4.1-flash",
            "PAGE_REVIEW_MAIN_A_BASE_URL": "https://ollama.com/v1",
            "INDEPENDENT_VLM_API_KEY": "zhipu-only-key",
            "PAGE_REVIEW_MAIN_B_PROVIDER": "mtplx",
            "PAGE_REVIEW_MAIN_B_MODEL": "mtplx-flash-next-optimized-speed",
        })


@pytest.mark.parametrize("loaded,capabilities,valid", [(True, ["vision"], True),
                                                       (False, ["vision"], False),
                                                       (True, ["chat"], False)])
def test_local_preflight_requires_ready_visual_model(monkeypatch, loaded, capabilities, valid):
    client = httpx.AsyncClient
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"data": [{
        "id": MODEL, "loaded": loaded, "state": "ready", "capabilities": capabilities,
    }]}))
    monkeypatch.setattr(harness.httpx, "AsyncClient", lambda **kwargs: client(transport=transport, **kwargs))
    route = require_page_reader_routes({"INDEPENDENT_VLM_API_KEY": "a",
        "PAGE_REVIEW_MAIN_B_PROVIDER": "mlx-serve", "PAGE_REVIEW_MAIN_B_MODEL": MODEL})[PageReviewLane.MAIN_B]
    if valid:
        assert asyncio.run(harness.resolve_route_model(route)) == route
    else:
        with pytest.raises(harness.PageReviewConfigError):
            asyncio.run(harness.resolve_route_model(route))


def test_local_route_keeps_cloud_credentials_out_and_runs_serially(monkeypatch):
    monkeypatch.setattr("app.llm.page_review_harness.PAGE_REVIEW_MAIN_B_API_KEY", "old-cloud-secret")
    routes = require_page_reader_routes({
        "INDEPENDENT_VLM_API_KEY": "a",
        "CMS_SMK_API_KEY": "another-cloud-secret",
        "PAGE_REVIEW_MAIN_B_API_KEY": "legacy-explicit-cloud-secret",
        "PAGE_REVIEW_MAIN_B_PROVIDER": "mlx-serve",
        "PAGE_REVIEW_MAIN_B_MODEL": MODEL,
        "PAGE_REVIEW_MAIN_B_BASE_URL": "http://127.0.0.1:11234/v1",
    })
    route = routes[PageReviewLane.MAIN_B]
    assert route.provider == "mlx-serve"
    assert route.model == MODEL
    assert route.api_key == "local-product"
    assert route.max_concurrency == 1
    assert "api_key" not in route_identity(route)
    assert routes[PageReviewLane.MAIN_A].reasoning_effort == "high"


def test_local_explicit_credential_is_used():
    routes = require_page_reader_routes({
        "INDEPENDENT_VLM_API_KEY": "a",
        "PAGE_REVIEW_MAIN_B_PROVIDER": "mlx-serve",
        "PAGE_REVIEW_MAIN_B_MODEL": MODEL,
        "PAGE_REVIEW_LOCAL_API_KEY": "dedicated-local-key",
    })
    assert routes[PageReviewLane.MAIN_B].api_key == "dedicated-local-key"


@pytest.mark.parametrize("visual", [True, False])
def test_mtplx_main_reader_requires_visual_identity_and_does_not_vote_twice(monkeypatch, visual):
    routes = require_page_reader_routes({
        "INDEPENDENT_VLM_API_KEY": "a", "PAGE_REVIEW_MAIN_B_PROVIDER": "mtplx",
        "PAGE_REVIEW_MAIN_B_MODEL": "mtplx-flash-next-optimized-speed",
        "PAGE_REVIEW_MAIN_B_BASE_URL": "http://127.0.0.1:8002/v1",
        "CMS_SMK_API_KEY": "must-not-leak", "PAGE_REVIEW_MAIN_B_API_KEY": "must-not-leak",
    })
    assert set(routes) == {PageReviewLane.MAIN_A, PageReviewLane.MAIN_B}
    client = httpx.AsyncClient
    def response(request):
        if request.url.host == "127.0.0.1":
            assert request.headers["Authorization"] == "Bearer local-product"
            return httpx.Response(200, json={"data": [{"id": "mtplx-flash-next-optimized-speed", "supports_vision": visual}]})
        return httpx.Response(200, json={"data": [{"id": routes[PageReviewLane.MAIN_A].model}]})

    transport = httpx.MockTransport(response)
    monkeypatch.setattr(harness.httpx, "AsyncClient", lambda **kwargs: client(transport=transport, **kwargs))
    if not visual:
        with pytest.raises(harness.PageReviewConfigError):
            asyncio.run(harness.preflight_page_reader_routes(routes))
        return
    resolved = asyncio.run(harness.preflight_page_reader_routes(routes))
    assert set(resolved) == {PageReviewLane.MAIN_A, PageReviewLane.MAIN_B}
    assert resolved[PageReviewLane.MAIN_B].max_concurrency == 1
    assert resolved[PageReviewLane.MAIN_B].reasoning_effort == "xhigh"
