from __future__ import annotations

import asyncio
from dataclasses import replace
import hashlib
import io
import json

import pytest
from PIL import Image

from app.domain.contracts.enums import Comparator, RuleKind, StudyPhase
from app.domain.contracts.page_review import PageReviewLane
from app.domain.contracts.rules import (
    AtomicExpression,
    AtomicPredicate,
    Rule,
    RuleComponent,
    RuleSet,
)
from app.llm.independent_vlm import PageVisionInput
from app.llm.page_review_harness import (
    PageCompletion,
    PageReviewConfigError,
    PageReviewHarnessError,
    PageReviewInput,
    PAGE_REVIEW_PROMPT_VERSION,
    extract_json_object,
    preflight_page_reader_routes,
    read_page,
    require_page_reader_routes,
)
from app.projections.clause_pack import project_clause_pack

_image_buffer = io.BytesIO()
Image.new("RGB", (8, 8), (240, 240, 240)).save(_image_buffer, format="PNG")
IMAGE_BYTES = _image_buffer.getvalue()
HASH = hashlib.sha256(IMAGE_BYTES).hexdigest()


def test_explicit_cloud_pair_efforts_are_preserved():
    routes = _routes()
    assert routes[PageReviewLane.MAIN_A].reasoning_effort == "high"
    assert routes[PageReviewLane.MAIN_B].reasoning_effort == "high"
    assert set(routes) == {PageReviewLane.MAIN_A, PageReviewLane.MAIN_B}


def test_cms_page_routes_reject_conflicting_explicit_credentials():
    config = {
        "CMS_ROUTER_BASE_URL": "http://127.0.0.1:20128/v1",
        "CMS_ROUTER_API_KEY": "cms-key",
        "PAGE_REVIEW_MAIN_A_PROVIDER": "cms-router",
        "PAGE_REVIEW_MAIN_A_BASE_URL": "https://old.example/v1",
        "PAGE_REVIEW_MAIN_A_API_KEY": "old-a-key",
        "PAGE_REVIEW_MAIN_A_MODEL": "glm-5.3-flash",
        "PAGE_REVIEW_MAIN_B_PROVIDER": "cms-router",
        "PAGE_REVIEW_MAIN_B_BASE_URL": "https://old.example/v1",
        "PAGE_REVIEW_MAIN_B_API_KEY": "old-b-key",
        "PAGE_REVIEW_MAIN_B_MODEL": "deepseek-latest-cloud",
    }
    with pytest.raises(PageReviewConfigError, match="冲突"):
        require_page_reader_routes(config)
    config.pop("PAGE_REVIEW_MAIN_A_BASE_URL")
    config.pop("PAGE_REVIEW_MAIN_A_API_KEY")
    config.pop("PAGE_REVIEW_MAIN_B_BASE_URL")
    config.pop("PAGE_REVIEW_MAIN_B_API_KEY")
    routes = require_page_reader_routes(config)
    assert {route.api_key for route in routes.values()} == {"cms-key"}
    assert {route.base_url for route in routes.values()} == {"http://127.0.0.1:20128/v1"}


def test_identical_response_with_different_effort_has_distinct_identity():
    from dataclasses import replace

    async def completion(*args):
        return PageCompletion(_main_response(), "stop", {})

    route = _routes()[PageReviewLane.MAIN_A]
    records = [asyncio.run(read_page(replace(route, reasoning_effort=effort),
                                    _page_input(), _clause_pack(), completion=completion))
               for effort in ("low", "high")]
    assert records[0].response_sha256 == records[1].response_sha256
    assert records[0].page_review_id != records[1].page_review_id


def test_transport_identity_uses_completion_receipt_not_provider_assumption():
    async def requested(*args):
        return PageCompletion(_main_response(), "stop", {},
                              transport_contract="omlx-schema-request-v1")

    async def unspecified(*args):
        return PageCompletion(_main_response(), "stop", {})

    route = replace(_routes()[PageReviewLane.MAIN_A], provider="omlx")
    records = [asyncio.run(read_page(route, _page_input(), _clause_pack(), completion=fn))
               for fn in (requested, unspecified)]
    assert records[0].prompt_version.endswith(":omlx-schema-request-v1")
    assert records[1].prompt_version == PAGE_REVIEW_PROMPT_VERSION
    assert records[0].page_review_id != records[1].page_review_id


@pytest.mark.parametrize("lane,effort", [(PageReviewLane.MAIN_B, "low"),
                                        (PageReviewLane.MAIN_A, "max")])
def test_explicit_comparison_route_records_actual_effort_without_changing_defaults(lane, effort):
    async def completion(route, messages, budget):
        assert route.reasoning_effort == effort
        return PageCompletion(_main_response(), "stop", {})

    record = asyncio.run(read_page(replace(_routes()[lane], reasoning_effort=effort),
        _page_input(), _clause_pack(), completion=completion))
    assert record.reasoning_effort == effort
    assert _routes()[PageReviewLane.MAIN_B].reasoning_effort == "high"
    assert _routes()[PageReviewLane.MAIN_A].reasoning_effort == "high"


def test_atomic_observation_instructions_are_symmetric_across_main_readers():
    from app.llm.page_review_harness import build_page_review_messages

    messages = {lane: build_page_review_messages(route, _page_input(), _clause_pack())
                for lane, route in _routes().items()}
    main_a = messages[PageReviewLane.MAIN_A][0]["content"]
    assert main_a == messages[PageReviewLane.MAIN_B][0]["content"]
    for requirement in ("每条 facts 只记录一个对象的一项事实", "不加章节前缀",
                        "facts 不按条款相关性或结果是否异常筛选", "正常结果也保留",
                        "同页有多张报告时分别读取",
                        "不用既往用药等类别名替代对象", "实际用药起止日期不可互相替代",
                        "raw_value 必须同时抄录该结果明确对应且可见的单位",
                        "单位被遮挡、无法辨认或对应关系不明时不得",
                        "没有实际手写时必须返回 handwriting=[]"):
        assert requirement in main_a


@pytest.mark.parametrize("signal", ["none", "mentions", "evidence_for", "evidence_against"])
@pytest.mark.parametrize("region", [None, {"excerpt": "原文"}])
def test_sent_schema_and_python_agree_on_signal_excerpt(signal, region):
    from jsonschema import Draft202012Validator
    from pydantic import ValidationError
    from app.domain.contracts.page_review import PageReviewPayload
    from app.llm.page_review_harness import build_page_review_messages
    messages = build_page_review_messages(_routes()[PageReviewLane.MAIN_A], _page_input(), _clause_pack())
    schema = json.loads(messages[1]["content"][0]["text"])["output_schema"]
    payload = json.loads(_main_response(has_eligibility_value=True, clause_signals=[
        {"clause_id": "component-1", "signal": signal, "region": region}]))
    valid = (signal == "none") == (region is None)
    assert Draft202012Validator(schema).is_valid(payload) == valid
    if valid:
        PageReviewPayload.model_validate(payload)
    else:
        with pytest.raises(ValidationError):
            PageReviewPayload.model_validate(payload)


def test_identical_response_is_scoped_to_frozen_review_context():
    from dataclasses import replace
    from app.domain.contracts.page_review_context import PageReviewContext

    async def completion(*args):
        return PageCompletion(_main_response(), "stop", {})

    context = PageReviewContext(review_episode_id="screen", episode_revision=1, stage="screening")
    original = replace(_page_input(), review_context=context)
    variants = [original,
                replace(original, source_document_version_id="another-version"),
                replace(original, review_context=context.model_copy(update={"episode_revision": 2})),
                replace(original, review_context=PageReviewContext(
                    review_episode_id="baseline", episode_revision=1, stage="baseline"))]
    records = [asyncio.run(read_page(_routes()[PageReviewLane.MAIN_A], page, _clause_pack(),
                                    completion=completion)) for page in variants]
    assert len({record.response_sha256 for record in records}) == 1
    assert len({record.page_review_id for record in records}) == len(variants)
    repeated = asyncio.run(read_page(_routes()[PageReviewLane.MAIN_A], original, _clause_pack(), completion=completion))
    assert repeated.page_review_id == records[0].page_review_id


def test_direct_transport_preserves_server_model_identity(monkeypatch):
    from types import SimpleNamespace
    import app.llm.page_review_harness as harness

    async def create(**kwargs):
        assert "temperature" not in kwargs
        return SimpleNamespace(model="server-returned-model", id="response-123", usage=None,
                               choices=[SimpleNamespace(message=SimpleNamespace(content="{}"),
                                                        finish_reason="stop")])
    monkeypatch.setattr(harness, "AsyncOpenAI", lambda **kwargs: SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    result = asyncio.run(harness.direct_openai_completion(_routes()[PageReviewLane.MAIN_B], [], 1024))
    assert result.response_model == "server-returned-model"
    assert result.response_id == "response-123"
    assert result.output_lengths == {"content_characters": 2, "reasoning_content_characters": None}


def test_direct_transport_does_not_equate_zero_reported_tokens_with_no_thinking(monkeypatch):
    from types import SimpleNamespace
    import app.llm.page_review_harness as harness

    usage = {"completion_tokens": 35, "completion_tokens_details": {"reasoning_tokens": 0}}

    async def create(**kwargs):
        return SimpleNamespace(model="MiniMax-M3", id="probe", usage=SimpleNamespace(model_dump=lambda: usage),
                               choices=[SimpleNamespace(message=SimpleNamespace(content="{}", reasoning_content="思考内容"),
                                                        finish_reason="stop")])

    monkeypatch.setattr(harness, "AsyncOpenAI", lambda **kwargs: SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    result = asyncio.run(harness.direct_openai_completion(_routes()[PageReviewLane.MAIN_B], [], 1024))
    assert result.output_lengths == {"content_characters": 2, "reasoning_content_characters": 4}
    assert result.usage == usage
    assert result.text == "{}"


def test_changed_path_cannot_send_an_unverified_image(tmp_path):
    from app.llm.page_review_harness import build_page_review_messages
    path = tmp_path / "page.png"
    path.write_bytes(IMAGE_BYTES)
    page = PageReviewInput(page_artifact_id="page-1", source_document_version_id="doc-1",
                           page_number=1, page_image_sha256=HASH,
                           page=PageVisionInput(source_ref="page-1", page_ordinal=1, image_path=path))
    path.write_bytes(b"changed-after-input-validation")
    with pytest.raises(ValueError, match="冻结原件不一致"):
        build_page_review_messages(_routes()[PageReviewLane.MAIN_A], page, _clause_pack())


def test_sdk_serializes_original_image_bytes_without_replacement(monkeypatch):
    import base64
    import httpx
    import app.llm.page_review_harness as harness
    raw = b"isolated-image-byte-identity"
    messages = [{"role": "user", "content": [
        {"type": "text", "text": "read the supplied page"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(raw).decode()}},
    ]}]
    captured = []
    def handle(request):
        body = json.loads(request.content)
        captured.append(body)
        assert body["messages"] == messages
        encoded = body["messages"][0]["content"][1]["image_url"]["url"].split(",", 1)[1]
        assert base64.b64decode(encoded, validate=True) == raw
        assert "temperature" not in body
        return httpx.Response(200, json={"id": "image-identity", "object": "chat.completion", "created": 0,
            "model": "MiniMax-M3", "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": "{}"}}]})
    class CapturingClient(httpx.AsyncClient):
        def __init__(self, **kwargs):
            super().__init__(**kwargs, transport=httpx.MockTransport(handle))
    monkeypatch.setattr(harness.httpx, "AsyncClient", CapturingClient)
    result = asyncio.run(harness.direct_openai_completion(_routes()[PageReviewLane.MAIN_B], messages, 1024))
    assert result.response_id == "image-identity"
    assert len(captured) == 1


def test_diagnostic_ablation_changes_only_clause_context():
    from scripts.r3_page_diagnostic import without_clause_context
    payload = {"page_number": 1, "clause_pack": {"clauses": ["example"]}, "output_schema": {}}
    messages = [{"role": "system", "content": "unchanged"},
                {"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64,eA=="}},
                    {"type": "text", "text": json.dumps(payload)}]}]
    result = without_clause_context(messages)
    assert result[0] == messages[0]
    assert result[1]["content"][0] == messages[1]["content"][0]
    assert json.loads(result[1]["content"][1]["text"]) == {"page_number": 1, "output_schema": {}}
    assert json.loads(messages[1]["content"][1]["text"]) == payload


def test_main_reads_share_frozen_context():
    from dataclasses import replace
    from app.domain.contracts.page_review_context import PageReviewContext
    from app.llm.page_review_harness import build_page_review_messages

    context = PageReviewContext(review_episode_id="episode-screen", episode_revision=2,
                                stage="screening", anchor_dates={})
    page = replace(_page_input(), review_context=context)
    for lane in (PageReviewLane.MAIN_A, PageReviewLane.MAIN_B):
        messages = build_page_review_messages(_routes()[lane], page, _clause_pack())
        payload = json.loads(messages[1]["content"][0]["text"])
        assert payload["review_context"] == context.model_dump(mode="json")
        assert payload["review_context"]["anchor_dates"] == {}


@pytest.mark.parametrize("sources", [
    {"image_bytes": b"page-image", "data_url": "data:image/png;base64,b3RoZXI="},
    {"image_bytes": b"page-image", "image_path": "/unused/page.png"},
    {"image_path": "/unused/page.png", "data_url": "data:image/png;base64,b3RoZXI="},
])
def test_page_input_rejects_ambiguous_image_sources(sources):
    with pytest.raises(ValueError, match="一种图像来源"):
        PageReviewInput(
            page_artifact_id="page-1", source_document_version_id="document-1",
            page_number=1, page_image_sha256=HASH,
            page=PageVisionInput(source_ref="page-1", page_ordinal=1, **sources),
        )


def test_diagnostic_verifies_source_and_pack_before_model_calls(tmp_path):
    from scripts.r3_page_diagnostic import load_input

    image = tmp_path / "page.jpg"
    image.write_bytes(IMAGE_BYTES)
    pack_path = tmp_path / "pack.json"
    pack_path.write_text(_clause_pack().model_dump_json(), encoding="utf-8")
    page, pack = load_input(image, HASH, 2, pack_path)
    assert page.page.media_type == "image/jpeg"
    assert page.page_number == 2
    assert pack.clause_pack_sha256 == _clause_pack().clause_pack_sha256
    with pytest.raises(ValueError, match="image hash"):
        load_input(image, "0" * 64, 2, pack_path)
    altered = json.loads(pack_path.read_text())
    altered["clauses"][0]["title"] = "changed"
    pack_path.write_text(json.dumps(altered), encoding="utf-8")
    with pytest.raises(ValueError):
        load_input(image, HASH, 2, pack_path)


def _routes():
    return require_page_reader_routes(
        {
            "INDEPENDENT_VLM_API_KEY": "main-a-key",
            "CMS_SMK_API_KEY": "main-b-key",
            "PAGE_REVIEW_MAIN_B_PROVIDER": "cms-smk",
            "PAGE_REVIEW_MAIN_A_REASONING_EFFORT": "high",
            "PAGE_REVIEW_MAIN_B_REASONING_EFFORT": "high",
            "PAGE_REVIEW_MAIN_B_MODEL": "MiniMax-M3",
            "PAGE_REVIEW_MAIN_B_BASE_URL": "https://new-api.mediportal.com.cn/v1",
            "PAGE_REVIEW_CLOUD_CONCURRENCY": "3",
            "PAGE_REVIEW_MAX_TOKENS": "65536",
        }
    )


def _clause_pack():
    predicate = AtomicPredicate(
        predicate_id="predicate-1",
        subject="受试者",
        attribute="诊断",
        comparator=Comparator.EXISTS,
    )
    component = RuleComponent(
        rule_component_id="component-1",
        parent_rule_id="rule-1",
        display_code="IN-01",
        title="诊断条件",
        expression=AtomicExpression(predicate=predicate),
    )
    return project_clause_pack(
        RuleSet(
            rule_set_id="ruleset-1",
            protocol_version_id="protocol-1",
            study_phase=StudyPhase.PHASE_III,
            rules=[
                Rule(
                    rule_id="rule-1",
                    official_code="IN-01",
                    kind=RuleKind.INCLUSION,
                    source_text="方案原文。",
                    study_phase=StudyPhase.PHASE_III,
                    components=[component],
                )
            ],
        )
    )


def _page_input() -> PageReviewInput:
    return PageReviewInput(
        page_artifact_id="page-1",
        source_document_version_id="document-1",
        page_number=1,
        page_image_sha256=HASH,
        page=PageVisionInput(
            source_ref="page-1",
            page_ordinal=1,
            image_bytes=IMAGE_BYTES,
        ),
    )


def _main_response(**extra) -> str:
    payload = {
        "has_eligibility_value": False,
        "facts": [],
        "clause_signals": [],
        "handwriting": [],
        **extra,
    }
    return json.dumps(payload, ensure_ascii=False)


def test_route_contract_uses_only_explicit_product_environment(monkeypatch) -> None:
    def reject_file_read(*_args, **_kwargs):
        raise AssertionError("不得读取外部 harness 文件")

    monkeypatch.setattr("pathlib.Path.read_text", reject_file_read)
    routes = _routes()

    assert routes[PageReviewLane.MAIN_A].provider == "zhipu-coding-plan"
    assert routes[PageReviewLane.MAIN_B].provider == "cms-smk"
    assert set(routes) == {PageReviewLane.MAIN_A, PageReviewLane.MAIN_B}


def test_route_contract_fails_closed_without_cloud_keys(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.llm.page_review_harness.PAGE_REVIEW_MAIN_A_API_KEY", ""
    )
    monkeypatch.setattr(
        "app.llm.page_review_harness.PAGE_REVIEW_MAIN_B_API_KEY", ""
    )
    with pytest.raises(PageReviewConfigError, match="缺少逐页判读凭据"):
        require_page_reader_routes(
            {
                "PAGE_REVIEW_CLOUD_CONCURRENCY": "2",
                "PAGE_REVIEW_MAX_TOKENS": "65536",
            }
        )


def test_route_contract_rejects_concurrency_outside_two_or_three() -> None:
    with pytest.raises(PageReviewConfigError, match="并发必须为 2 或 3"):
        require_page_reader_routes(
            {
                "INDEPENDENT_VLM_API_KEY": "a",
                "CMS_SMK_API_KEY": "b",
                "PAGE_REVIEW_CLOUD_CONCURRENCY": "4",
            }
        )


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("INDEPENDENT_VLM_PROVIDER", "bigmodel", "main-A"),
        ("PAGE_REVIEW_MAIN_A_MODEL", "", "main-A"),
        ("PAGE_REVIEW_MAIN_B_MODEL", "", "main-B"),
    ],
)
def test_route_contract_rejects_model_identity_drift(
    name: str, value: str, message: str
) -> None:
    env = {
        "INDEPENDENT_VLM_API_KEY": "a",
        "CMS_SMK_API_KEY": "b",
        "PAGE_REVIEW_MAIN_B_PROVIDER": "cms-smk",
        "PAGE_REVIEW_MAIN_B_REASONING_EFFORT": "high",
        "PAGE_REVIEW_MAIN_B_BASE_URL": "https://test.example/v1",
        "PAGE_REVIEW_MAIN_B_MODEL": "MiniMax-M3",
        name: value,
    }
    with pytest.raises(PageReviewConfigError, match=message):
        require_page_reader_routes(env)


def test_page_input_rejects_image_hash_mismatch() -> None:
    with pytest.raises(ValueError, match="哈希"):
        PageReviewInput(
            page_artifact_id="page-1",
            source_document_version_id="document-1",
            page_number=1,
            page_image_sha256="a" * 64,
            page=PageVisionInput(
                source_ref="page-1",
                page_ordinal=1,
                image_bytes=b"page-image",
            ),
        )


def test_preflight_requires_and_resolves_both_main_lanes(monkeypatch) -> None:
    seen: list[PageReviewLane] = []

    async def resolve(route):
        seen.append(route.lane)
        return route

    monkeypatch.setattr("app.llm.page_review_harness.resolve_route_model", resolve)
    resolved = asyncio.run(preflight_page_reader_routes(_routes()))
    assert seen == [PageReviewLane.MAIN_A, PageReviewLane.MAIN_B]
    assert set(resolved) == {PageReviewLane.MAIN_A, PageReviewLane.MAIN_B}

    incomplete = _routes()
    del incomplete[PageReviewLane.MAIN_B]
    with pytest.raises(PageReviewConfigError, match="必须同时声明"):
        asyncio.run(preflight_page_reader_routes(incomplete))


def test_json_repair_migrates_benchmark_quote_recovery() -> None:
    repaired = extract_json_object('{"text":"首字符"I"需要保留","items":[]}')
    assert repaired["text"] == '首字符"I"需要保留'


def test_harness_normalizes_raw_facts_without_model_computed_keys() -> None:
    raw = json.loads(_main_response(has_eligibility_value=True, facts=[{
        "observation_id": "fact-1", "field_name": "检查值",
        "raw_text": "检查值 1.234567 mmol/L", "raw_value": "1.234567 mmol/L",
        "region": {"excerpt": "检查值 1.234567 mmol/L"},
    }]))

    async def completion(_route, _messages, _budget):
        schema = json.loads(_messages[1]["content"][0]["text"])["output_schema"]
        assert "normalization_key" not in schema["$defs"]["PageFactObservation"]["properties"]
        assert "没有则为 null" in _messages[0]["content"]
        assert "日期字段本身的 time_text 为 null" in _messages[0]["content"]
        assert "handwriting=[]" in _messages[0]["content"]
        assert "不是受试者事实来源" in _messages[0]["content"]
        assert "一个 JSON 对象" in _messages[0]["content"]
        assert "忠实摘录原文不受此限制" in _messages[0]["content"]
        return PageCompletion(json.dumps(raw), "stop", {})

    record = asyncio.run(read_page(_routes()[PageReviewLane.MAIN_A], _page_input(), _clause_pack(), completion=completion))
    assert record.facts[0].normalized_value == "1.234567"
    assert record.facts[0].normalized_unit == "mmol/l"
    assert record.prompt_version == PAGE_REVIEW_PROMPT_VERSION


def test_harness_rejects_clause_not_present_in_pack() -> None:
    async def completion(_route, _messages, _budget):
        return PageCompletion(_main_response(has_eligibility_value=True,
            clause_signals=[{"clause_id": "unknown", "signal": "mentions",
                             "region": {"excerpt": "记录"}}]), "stop", {})

    with pytest.raises(PageReviewHarnessError, match="不存在的条款"):
        asyncio.run(read_page(_routes()[PageReviewLane.MAIN_A], _page_input(), _clause_pack(), completion=completion))


@pytest.mark.parametrize("failed_lane", [PageReviewLane.MAIN_A, PageReviewLane.MAIN_B])
def test_main_preflight_failure_blocks_reads(monkeypatch, failed_lane) -> None:
    async def resolve(route):
        if route.lane == failed_lane:
            raise PageReviewConfigError("端点暂不可用")
        return route

    monkeypatch.setattr("app.llm.page_review_harness.resolve_route_model", resolve)
    with pytest.raises(PageReviewConfigError, match="端点暂不可用"):
        asyncio.run(preflight_page_reader_routes(_routes()))


def test_local_early_length_does_not_expand_or_accept_partial_output():
    route = replace(_routes()[PageReviewLane.MAIN_A], provider="mlx-serve")
    calls = []

    async def completion(_route, _messages, budget):
        calls.append(budget)
        return PageCompletion(_main_response(), "length", {"completion_tokens": 1000})

    with pytest.raises(PageReviewHarnessError) as error:
        asyncio.run(read_page(route, _page_input(), _clause_pack(), completion=completion))
    assert error.value.failure_kind == "early_termination"
    assert calls == [route.max_tokens]


def test_length_finish_retries_once_with_double_budget() -> None:
    route = _routes()[PageReviewLane.MAIN_A]
    budgets: list[int] = []

    async def completion(_route, _messages, max_tokens):
        budgets.append(max_tokens)
        if len(budgets) == 1:
            return PageCompletion("{}", "length", {})
        return PageCompletion(_main_response(), "stop", {})

    record = asyncio.run(
        read_page(route, _page_input(), _clause_pack(), completion=completion)
    )
    assert budgets == [65536, 131072]
    assert record.lane == PageReviewLane.MAIN_A


@pytest.mark.parametrize("finish_reason", [None, "", "tool_calls", "function_call", "unknown"])
@pytest.mark.parametrize("lane", [PageReviewLane.MAIN_A, PageReviewLane.MAIN_B])
def test_nonterminal_or_unknown_finish_cannot_accept_valid_json(finish_reason, lane):
    route = replace(_routes()[lane], model="fixture-model")
    async def completion(_route, _messages, _budget):
        return PageCompletion(_main_response(), finish_reason, {})

    with pytest.raises(PageReviewHarnessError, match="完整结束") as error:
        asyncio.run(read_page(route, _page_input(), _clause_pack(), completion=completion))
    assert error.value.failure_kind == "schema"


def test_rate_limit_wait_does_not_consume_call_attempt() -> None:
    route = _routes()[PageReviewLane.MAIN_B]
    calls = 0
    waits: list[float] = []

    class RateLimited(RuntimeError):
        status_code = 429

    async def completion(_route, _messages, _max_tokens):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RateLimited("429")
        return PageCompletion(_main_response(), "stop", {})

    async def sleep(seconds):
        waits.append(seconds)

    asyncio.run(
        read_page(
            route,
            _page_input(),
            _clause_pack(),
            completion=completion,
            sleep=sleep,
        )
    )
    assert calls == 2
    assert waits == [60]


def test_endpoint_failure_uses_same_model_fallback_once() -> None:
    route = _routes()[PageReviewLane.MAIN_A]
    route = route.__class__(
        **{**route.__dict__, "fallback_base_url": "https://fallback.example/v1"}
    )
    endpoints: list[str] = []

    async def completion(active_route, _messages, _max_tokens):
        endpoints.append(active_route.base_url)
        if len(endpoints) == 1:
            raise RuntimeError("endpoint unavailable")
        return PageCompletion(_main_response(), "stop", {})

    record = asyncio.run(
        read_page(route, _page_input(), _clause_pack(), completion=completion)
    )
    assert endpoints == [route.base_url, "https://fallback.example/v1"]
    assert record.model == route.model
    assert record.endpoint_base_url == "https://fallback.example/v1"
    assert record.fallback_used is True


def test_content_filter_finish_reason_uses_same_model_fallback_once() -> None:
    route = _routes()[PageReviewLane.MAIN_A]
    route = route.__class__(
        **{**route.__dict__, "fallback_base_url": "https://fallback.example/v1"}
    )
    endpoints: list[str] = []

    async def completion(active_route, _messages, _max_tokens):
        endpoints.append(active_route.base_url)
        if len(endpoints) == 1:
            return PageCompletion("", "content_filter", {})
        return PageCompletion(_main_response(), "stop", {})

    asyncio.run(read_page(route, _page_input(), _clause_pack(), completion=completion))
    assert endpoints == [route.base_url, "https://fallback.example/v1"]


@pytest.mark.parametrize("forbidden", ["exclusion_triggered", "supports_not_met"])
def test_harness_rejects_model_determination_words(forbidden: str) -> None:
    route = _routes()[PageReviewLane.MAIN_A]

    async def completion(_route, _messages, _max_tokens):
        return PageCompletion(_main_response(**{forbidden: True}), "stop", {})

    with pytest.raises(PageReviewHarnessError, match="不符合页级合同"):
        asyncio.run(
            read_page(route, _page_input(), _clause_pack(), completion=completion)
        )
