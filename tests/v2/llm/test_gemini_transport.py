"""HTTP-mock coverage for the product-native google-antigravity Gemini transport."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json

import httpx
import pytest

from app.domain.contracts.enums import Comparator, RuleKind, StudyPhase
from app.domain.contracts.page_review import PageReviewLane
from app.domain.contracts.rules import (
    AtomicExpression,
    AtomicPredicate,
    Rule,
    RuleComponent,
    RuleSet,
)
from app.llm import gemini_transport
from app.llm import page_review_harness as harness
from app.llm.gemini_transport import GeminiTransportError, direct_gemini_completion
from app.llm.independent_vlm import PageVisionInput
from app.llm.page_review_harness import (
    PageCompletion,
    PageReviewConfigError,
    PageReviewHarnessError,
    PageReviewInput,
    build_page_review_messages,
    read_page,
    require_page_reader_routes,
)
from app.projections.clause_pack import project_clause_pack
from app.services.page_review_job_service import main_reader_identity

HASH = hashlib.sha256(b"page-image").hexdigest()
GEMINI_ENDPOINT = "https://daily-cloudcode-pa.googleapis.com"


def _gemini_env(**extra) -> dict:
    return {
        "INDEPENDENT_VLM_API_KEY": "main-a-key",
        "PAGE_REVIEW_MAIN_B_PROVIDER": "google-antigravity",
        "GEMINI_ACCESS_TOKEN": "gem-token",
        "GEMINI_PROJECT_ID": "proj-1",
        "PAGE_REVIEW_MAIN_B_BASE_URL": GEMINI_ENDPOINT,
        "PAGE_REVIEW_CLOUD_CONCURRENCY": "2",
        "PAGE_REVIEW_MAX_TOKENS": "12000",
        **extra,
    }


def _gemini_route(**overrides):
    route = require_page_reader_routes(_gemini_env())[PageReviewLane.MAIN_B]
    if overrides:
        route = route.__class__(**{**route.__dict__, **overrides})
    return route


def _sse(chunks: list[dict]) -> bytes:
    return b"".join(
        b"data: " + json.dumps(chunk, ensure_ascii=False).encode("utf-8") + b"\n\n"
        for chunk in chunks
    )


def _chunk(*, text="", thought=None, finish=None, response=False, **meta) -> dict:
    parts = []
    if thought is not None:
        parts.append({"text": thought, "thought": True})
    if text:
        parts.append({"text": text})
    candidate: dict = {"content": {"parts": parts}}
    if finish is not None:
        candidate["finishReason"] = finish
    value = {
        "modelVersion": "gemini-3.7-flash",
        "responseId": "resp-1",
        "usageMetadata": {
            "promptTokenCount": 120,
            "candidatesTokenCount": 30,
            "totalTokenCount": 150,
        },
        "candidates": [candidate],
    }
    value.update(meta)
    return {"response": value} if response else value


def _install_stream(monkeypatch, responder) -> list[httpx.Request]:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return responder(request)

    base = httpx.AsyncClient

    def client(**kwargs):
        return base(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(gemini_transport.httpx, "AsyncClient", client)
    return captured


def _stream_response(chunks_provider):
    async def content():
        if callable(chunks_provider):
            async for piece in chunks_provider():
                yield piece
        else:
            yield chunks_provider

    return httpx.Response(200, content=content())


def _messages() -> list[dict]:
    return build_page_review_messages(_gemini_route(), _page_input(), _clause_pack())


@pytest.mark.parametrize("finish", [None, "OTHER", "ERROR"])
def test_missing_or_unknown_finish_is_transport_failure(monkeypatch, finish):
    _install_stream(monkeypatch, lambda _: _stream_response(_sse([
        _chunk(text=_main_response(), finish=finish),
    ])))
    with pytest.raises(GeminiTransportError, match="未完整结束"):
        asyncio.run(direct_gemini_completion(_gemini_route(), _messages(), 65536))


def test_unauthorized_invalidates_cached_oauth(monkeypatch):
    invalidated = []
    monkeypatch.setattr(gemini_transport, "invalidate", lambda: invalidated.append(True))
    _install_stream(monkeypatch, lambda _: httpx.Response(401, json={"error": "expired"}))
    with pytest.raises(GeminiTransportError) as error:
        asyncio.run(direct_gemini_completion(_gemini_route(), _messages(), 65536))
    assert error.value.status_code == 401
    assert invalidated == [True]


@pytest.mark.parametrize("failure", [
    {"error": {"code": 500, "message": "failed"}},
    {"type": "error", "message": "failed"},
    {"response": {"error": {"code": 500}}},
])
def test_stream_error_after_complete_text_is_rejected(monkeypatch, failure):
    _install_stream(monkeypatch, lambda _: _stream_response(_sse([
        _chunk(text=_main_response(), finish="STOP"), failure,
    ])))
    with pytest.raises(GeminiTransportError, match="拒绝采信"):
        asyncio.run(direct_gemini_completion(_gemini_route(), _messages(), 65536))


def _main_response() -> str:
    return json.dumps({
        "has_eligibility_value": False,
        "facts": [],
        "clause_signals": [],
        "handwriting": [],
    }, ensure_ascii=False)


def _page_input() -> PageReviewInput:
    return PageReviewInput(
        page_artifact_id="page-1",
        source_document_version_id="document-1",
        page_number=1,
        page_image_sha256=HASH,
        page=PageVisionInput(source_ref="page-1", page_ordinal=1, image_bytes=b"page-image"),
    )


def _clause_pack():
    predicate = AtomicPredicate(
        predicate_id="predicate-1", subject="受试者", attribute="诊断",
        comparator=Comparator.EXISTS,
    )
    component = RuleComponent(
        rule_component_id="component-1", parent_rule_id="rule-1", display_code="IN-01",
        title="诊断条件", expression=AtomicExpression(predicate=predicate),
    )
    return project_clause_pack(
        RuleSet(
            rule_set_id="ruleset-1", protocol_version_id="protocol-1",
            study_phase=StudyPhase.PHASE_III,
            rules=[Rule(rule_id="rule-1", official_code="IN-01", kind=RuleKind.INCLUSION,
                        source_text="方案原文。", study_phase=StudyPhase.PHASE_III,
                        components=[component])],
        )
    )


async def _sleep_recording(waits: list[float], seconds: float) -> None:
    waits.append(seconds)


def test_main_b_defaults_to_gemini_with_high_effort() -> None:
    route = _gemini_route()
    assert route.provider == "google-antigravity"
    assert route.model == "gemini-3.7-flash"
    assert route.reasoning_effort == "high"
    assert route.project_id == "proj-1"
    assert route.base_url == GEMINI_ENDPOINT
    assert route.max_concurrency == 2
    assert not route.fallback_base_url


def test_request_shape_roles_image_budget_effort(monkeypatch) -> None:
    captured = _install_stream(
        monkeypatch,
        lambda _request: _stream_response(
            _sse([_chunk(text=_main_response(), finish="STOP")])
        ),
    )
    messages = _messages()
    result = asyncio.run(direct_gemini_completion(_gemini_route(), messages, 12000))
    assert result.finish_reason == "stop"

    request = captured[0]
    assert str(request.url) == (
        f"{GEMINI_ENDPOINT}/v1internal:streamGenerateContent?alt=sse"
    )
    assert request.headers["authorization"] == "Bearer gem-token"
    assert request.headers["user-agent"].startswith("antigravity/")
    body = json.loads(request.content)
    assert "temperature" not in request.content.decode()
    assert body["project"] == "proj-1"
    assert body["model"] == "gemini-3.7-flash-high"
    assert body["userAgent"] == "antigravity"
    assert body["requestType"] == "agent"
    assert body["requestId"]
    inner = body["request"]
    assert inner["generationConfig"] == {
        "maxOutputTokens": 12000,
        "thinkingConfig": {"thinkingLevel": "HIGH", "includeThoughts": True},
    }
    system = inner["systemInstruction"]
    assert system["role"] == "user"
    assert system["parts"][0]["text"].startswith("你是入排审核系统的逐页医学资料读片员")
    assert inner["contents"] == [{"role": "user", "parts": [
        {"inlineData": {
            "mimeType": "image/png",
            "data": base64.b64encode(b"page-image").decode(),
        }},
        {"text": messages[1]["content"][1]["text"]},
    ]}]


def test_request_builder_refuses_unknown_roles_and_efforts() -> None:
    with pytest.raises(ValueError, match="角色"):
        gemini_transport.build_gemini_request(
            _gemini_route(),
            [{"role": "tool", "content": [{"type": "text", "text": "x"}]}],
            12000,
        )
    with pytest.raises(ValueError, match="effort"):
        gemini_transport.build_gemini_request(
            _gemini_route(reasoning_effort="max"), _messages(), 12000
        )
    with pytest.raises(ValueError, match="GEMINI_PROJECT_ID"):
        gemini_transport.build_gemini_request(
            _gemini_route(project_id=""), _messages(), 12000
        )


def test_success_stream_separates_thinking_and_records_receipts(monkeypatch) -> None:
    chunks = [
        _chunk(thought="先核对页首信息。"),
        _chunk(text='{"has_eligibility_value":'),
        _chunk(text=' false, "facts": []}', response=True),
        _chunk(finish="STOP"),
    ]
    _install_stream(monkeypatch, lambda _request: _stream_response(_sse(chunks)))
    result = asyncio.run(direct_gemini_completion(_gemini_route(), _messages(), 12000))
    assert result.text == '{"has_eligibility_value": false, "facts": []}'
    assert result.finish_reason == "stop"
    assert result.response_model == "gemini-3.7-flash"
    assert result.response_id == "resp-1"
    assert result.usage == {"promptTokenCount": 120, "candidatesTokenCount": 30,
                            "totalTokenCount": 150}
    assert result.output_lengths == {
        "content_characters": len(result.text),
        "reasoning_content_characters": len("先核对页首信息。"),
    }


def test_http_429_feeds_existing_rate_limit_budget(monkeypatch) -> None:
    calls: list[int] = []

    def responder(_request):
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429, json={"error": {"message": "quota exceeded"}})
        return _stream_response(_sse([_chunk(text=_main_response(), finish="STOP")]))

    _install_stream(monkeypatch, responder)
    waits: list[float] = []
    record = asyncio.run(read_page(
        _gemini_route(), _page_input(), _clause_pack(),
        sleep=lambda seconds: _sleep_recording(waits, seconds),
    ))
    assert len(calls) == 2
    assert waits == [60]
    assert record.finish_reason == "stop"


def test_truncated_stream_maps_to_length_and_budget_doubles(monkeypatch) -> None:
    budgets: list[int] = []

    def responder(request):
        body = json.loads(request.content)
        budgets.append(body["request"]["generationConfig"]["maxOutputTokens"])
        if len(budgets) == 1:
            return _stream_response(
                _sse([_chunk(text='{"has_eligibility', finish="MAX_TOKENS")])
            )
        return _stream_response(_sse([_chunk(text=_main_response(), finish="STOP")]))

    _install_stream(monkeypatch, responder)
    record = asyncio.run(read_page(_gemini_route(), _page_input(), _clause_pack()))
    assert budgets == [12000, 24000]
    assert record.finish_reason == "stop"
    assert record.fallback_used is False


def test_safety_finish_maps_to_content_filter(monkeypatch) -> None:
    _install_stream(
        monkeypatch,
        lambda _request: _stream_response(
            _sse([_chunk(text="部分内容", finish="SAFETY")])
        ),
    )
    with pytest.raises(PageReviewHarnessError) as error:
        asyncio.run(read_page(_gemini_route(), _page_input(), _clause_pack()))
    assert error.value.failure_kind == "content_filter"


def test_prompt_block_without_candidates_maps_to_content_filter(monkeypatch) -> None:
    _install_stream(
        monkeypatch,
        lambda _request: _stream_response(
            _sse([{"promptFeedback": {"blockReason": "SAFETY"}}])
        ),
    )
    with pytest.raises(PageReviewHarnessError) as error:
        asyncio.run(read_page(_gemini_route(), _page_input(), _clause_pack()))
    assert error.value.failure_kind == "content_filter"


def test_stream_interruption_rejects_partial_text(monkeypatch) -> None:
    async def broken():
        yield _sse([_chunk(text='{"has_eligibility_value": false, "facts": [')])
        raise httpx.ReadError("connection reset")

    _install_stream(monkeypatch, lambda _request: _stream_response(broken))
    with pytest.raises(GeminiTransportError, match="流中断"):
        asyncio.run(direct_gemini_completion(_gemini_route(), _messages(), 12000))
    with pytest.raises(PageReviewHarnessError) as error:
        asyncio.run(read_page(_gemini_route(), _page_input(), _clause_pack()))
    assert error.value.failure_kind == "endpoint"


def test_malformed_sse_event_rejects_partial_text(monkeypatch) -> None:
    async def garbled():
        yield b"data: {not-json}\n\n"

    _install_stream(monkeypatch, lambda _request: _stream_response(garbled))
    with pytest.raises(GeminiTransportError, match="拒绝采信"):
        asyncio.run(direct_gemini_completion(_gemini_route(), _messages(), 12000))


def test_cancellation_propagates_mid_stream(monkeypatch) -> None:
    async def hanging():
        yield _sse([_chunk(thought="thinking")])
        await asyncio.Event().wait()

    _install_stream(monkeypatch, lambda _request: _stream_response(hanging))

    async def main() -> None:
        task = asyncio.create_task(
            direct_gemini_completion(_gemini_route(), _messages(), 12000)
        )
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(main())


def test_model_version_mismatch_is_rejected(monkeypatch) -> None:
    _install_stream(
        monkeypatch,
        lambda _request: _stream_response(
            _sse([_chunk(text=_main_response(), finish="STOP",
                         modelVersion="gemini-3.8-pro")])
        ),
    )
    with pytest.raises(GeminiTransportError, match="不一致"):
        asyncio.run(direct_gemini_completion(_gemini_route(), _messages(), 12000))


def test_missing_gemini_credentials_fail_explicitly() -> None:
    without_project = _gemini_env()
    del without_project["GEMINI_PROJECT_ID"]
    with pytest.raises(PageReviewConfigError, match="GEMINI_PROJECT_ID"):
        require_page_reader_routes(without_project)

    without_token = _gemini_env(GEMINI_ACCESS_TOKEN="")
    with pytest.raises(PageReviewConfigError, match="GEMINI_ACCESS_TOKEN"):
        require_page_reader_routes(without_token)


def test_gemini_endpoint_must_be_https() -> None:
    with pytest.raises(PageReviewConfigError, match="HTTPS"):
        require_page_reader_routes(
            _gemenv_http()
        )


def _gemenv_http() -> dict:
    return _gemini_env(
        PAGE_REVIEW_MAIN_B_BASE_URL="http://daily-cloudcode-pa.googleapis.com"
    )


def test_default_main_b_identity_reads_without_credentials(monkeypatch) -> None:
    monkeypatch.setattr(harness, "PAGE_REVIEW_MAIN_B_PROVIDER", "google-antigravity")
    monkeypatch.setattr(harness, "PAGE_REVIEW_MAIN_B_MODEL", "gemini-3.7-flash")
    monkeypatch.setattr(harness, "PAGE_REVIEW_MAIN_B_BASE_URL", GEMINI_ENDPOINT)
    monkeypatch.setattr(harness, "GEMINI_ACCESS_TOKEN", "")
    monkeypatch.setattr(harness, "GEMINI_PROJECT_ID", "")
    monkeypatch.setattr(harness, "PAGE_REVIEW_MAIN_A_API_KEY", "")
    routes = require_page_reader_routes(
        {"PAGE_REVIEW_CLOUD_CONCURRENCY": "2", "PAGE_REVIEW_MAX_TOKENS": "12000"},
        require_credentials=False,
    )
    assert len(main_reader_identity(routes)) == 64
    assert routes[PageReviewLane.MAIN_B].provider == "google-antigravity"
    assert routes[PageReviewLane.MAIN_B].model == "gemini-3.7-flash"
    with pytest.raises(PageReviewConfigError, match="缺少逐页判读凭据"):
        require_page_reader_routes(
            {"PAGE_REVIEW_CLOUD_CONCURRENCY": "2", "PAGE_REVIEW_MAX_TOKENS": "12000"}
        )


def test_preflight_uses_native_transport_not_openai_models(monkeypatch) -> None:
    seen: list[str] = []

    def responder(request):
        seen.append(str(request.url))
        return httpx.Response(200, json={"data": [{"id": "glm-5.3-flash"}]})

    _install_stream(monkeypatch, responder)
    routes = require_page_reader_routes(_gemini_env())
    resolved = asyncio.run(harness.preflight_page_reader_routes(routes))
    assert set(resolved) == {PageReviewLane.MAIN_A, PageReviewLane.MAIN_B}
    assert resolved[PageReviewLane.MAIN_B] == routes[PageReviewLane.MAIN_B]
    assert len(seen) == 1
    assert seen[0].endswith("/models")
    assert "googleapis.com" not in seen[0]


def test_lane_dispatch_selects_native_transport_for_gemini(monkeypatch) -> None:
    dispatched: list[str] = []

    async def fake_gemini(route, messages, budget):
        dispatched.append(route.provider)
        return PageCompletion("{}", "stop", {})

    async def fake_openai(route, messages, budget):
        dispatched.append(route.provider)
        return PageCompletion("{}", "stop", {})

    monkeypatch.setattr(gemini_transport, "direct_gemini_completion", fake_gemini)
    monkeypatch.setattr(harness, "direct_openai_completion", fake_openai)
    asyncio.run(harness.direct_completion(_gemini_route(), [], 1024))
    asyncio.run(harness.direct_completion(
        require_page_reader_routes(_gemini_env(
            PAGE_REVIEW_MAIN_B_PROVIDER="cms-smk",
            PAGE_REVIEW_MAIN_B_MODEL="MiniMax-M3",
            PAGE_REVIEW_MAIN_B_BASE_URL="https://new-api.mediportal.com.cn/v1",
            CMS_SMK_API_KEY="cms-key",
        ))[PageReviewLane.MAIN_B], [], 1024))
    assert dispatched == ["google-antigravity", "cms-smk"]


def test_read_page_records_native_provider_identity(monkeypatch) -> None:
    _install_stream(
        monkeypatch,
        lambda _request: _stream_response(
            _sse([_chunk(text=_main_response(), finish="STOP")])
        ),
    )
    record = asyncio.run(read_page(_gemini_route(), _page_input(), _clause_pack()))
    assert record.provider == "google-antigravity"
    assert record.model == "gemini-3.7-flash"
    assert record.reasoning_effort == "high"
    assert record.endpoint_base_url == GEMINI_ENDPOINT
    assert record.finish_reason == "stop"
    assert record.usage == {"promptTokenCount": 120, "candidatesTokenCount": 30,
                            "totalTokenCount": 150}


def test_historical_local_provider_identity_still_resolvable() -> None:
    routes = require_page_reader_routes({
        "INDEPENDENT_VLM_API_KEY": "a",
        "PAGE_REVIEW_MAIN_B_PROVIDER": "mtplx",
        "PAGE_REVIEW_MAIN_B_MODEL": "mtplx-flash-next-optimized-speed",
        "PAGE_REVIEW_MAIN_B_BASE_URL": "http://127.0.0.1:8002/v1",
    })
    assert routes[PageReviewLane.MAIN_B].provider == "mtplx"
    assert routes[PageReviewLane.MAIN_B].reasoning_effort == "high"
    assert routes[PageReviewLane.MAIN_B].project_id == ""
