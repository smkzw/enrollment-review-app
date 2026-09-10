"""Focused tests for the default-off multi-page batch reading experiment."""

from __future__ import annotations

import asyncio
import hashlib
import json

import pytest

from app.domain.contracts.enums import Comparator, RuleKind, StudyPhase
from app.domain.contracts.page_review import PageReviewLane
from app.domain.contracts.page_review_context import PageReviewContext
from app.domain.contracts.rules import (
    AtomicExpression,
    AtomicPredicate,
    Rule,
    RuleComponent,
    RuleSet,
)
from app.domain.publication import canonical_hash
from app.llm.independent_vlm import PageVisionInput
from app.llm.page_review_batch_experiment import (
    BATCH_PROMPT_VERSION,
    read_page_batch,
)
from app.llm.page_review_harness import (
    PAGE_REVIEW_PROMPT_VERSION,
    PageCompletion,
    PageReviewConfigError,
    PageReviewHarnessError,
    PageReviewInput,
    build_page_review_messages,
    read_page,
    require_page_reader_routes,
)
from app.projections.clause_pack import project_clause_pack
from app.projections.page_review_prompt_pack import page_review_prompt_pack


def _routes():
    return require_page_reader_routes(
        {
            "INDEPENDENT_VLM_API_KEY": "main-a-key",
            "CMS_SMK_API_KEY": "main-b-key",
            "PAGE_REVIEW_MAIN_B_PROVIDER": "cms-smk",
            "PAGE_REVIEW_MAIN_B_MODEL": "MiniMax-M3",
            "PAGE_REVIEW_CLOUD_CONCURRENCY": "3",
            "PAGE_REVIEW_MAX_TOKENS": "12000",
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


def _page_input(page_id, page_number, review_context=None) -> PageReviewInput:
    image = f"page-image-{page_number}".encode()
    return PageReviewInput(
        page_artifact_id=page_id,
        source_document_version_id="document-1",
        page_number=page_number,
        page_image_sha256=hashlib.sha256(image).hexdigest(),
        page=PageVisionInput(
            source_ref=page_id, page_ordinal=page_number, image_bytes=image
        ),
        review_context=review_context,
    )


def _payload(page_id, **extra) -> dict:
    return {
        "has_eligibility_value": False,
        "facts": [],
        "clause_signals": [],
        "handwriting": [],
        **extra,
    }


def _fact(page_id) -> dict:
    return {
        "observation_id": f"fact-{page_id}",
        "field_name": "检查值",
        "raw_text": f"检查值 1.234567 mmol/L {page_id}",
        "raw_value": "1.234567 mmol/L",
        "region": {"excerpt": f"检查值 1.234567 mmol/L {page_id}"},
    }


def _batch_completion(payloads, *, calls, envelope_queue):
    """Serve both the one batch call (multi-image) and per-page read_page validation."""

    async def completion(route, messages, budget):
        images = [part for part in messages[1]["content"] if part.get("type") == "image_url"]
        text_part = next(part for part in messages[1]["content"] if part.get("type") == "text")
        if len(images) > 1:
            calls.append(
                {
                    "kind": "batch",
                    "budget": budget,
                    "images": len(images),
                    "system": messages[0]["content"],
                    "text": text_part["text"],
                }
            )
            return PageCompletion(envelope_queue.pop(0), "stop", {"total_tokens": 99})
        page_id = json.loads(text_part["text"])["page_artifact_id"]
        calls.append({"kind": "page", "budget": budget, "page": page_id})
        return PageCompletion(json.dumps(payloads[page_id], ensure_ascii=False), "stop", {})

    return completion


def _context() -> PageReviewContext:
    return PageReviewContext(
        review_episode_id="episode-screen", episode_revision=1, stage="screening"
    )


def _two_page_setup(context=None):
    pages = [_page_input("page-1", 1, context), _page_input("page-2", 2, context)]
    payloads = {"page-1": _payload("page-1"), "page-2": _payload("page-2")}
    envelope = json.dumps(payloads, ensure_ascii=False)
    return pages, payloads, envelope


def test_batch_returns_each_page_in_order_with_full_shared_context_and_intact_prompt():
    route = _routes()[PageReviewLane.MAIN_A]
    pack = _clause_pack()
    pages = [_page_input("page-1", 1, _context()), _page_input("page-2", 2, _context())]
    payloads = {
        "page-1": _payload("page-1", has_eligibility_value=True, facts=[_fact("page-1")]),
        "page-2": _payload("page-2", has_eligibility_value=True, facts=[_fact("page-2")]),
    }
    envelope = json.dumps(payloads, ensure_ascii=False)
    calls = []
    result = asyncio.run(
        read_page_batch(route, pages, pack, completion=_batch_completion(payloads, calls=calls, envelope_queue=[envelope]))
    )

    assert result.failures == []
    assert [record.page_artifact_id for record in result.records] == ["page-1", "page-2"]
    assert [record.page_number for record in result.records] == [1, 2]
    # Each record carries exactly its own page's envelope entry, validated per page.
    assert result.records[0].facts[0].raw_text.endswith("page-1")
    assert result.records[1].facts[0].raw_text.endswith("page-2")
    assert result.records[0].response_sha256 == canonical_hash(payloads["page-1"])
    assert result.records[1].response_sha256 == canonical_hash(payloads["page-2"])
    assert result.usage == {"total_tokens": 99}
    assert all(record.usage == {} for record in result.records)

    batch_calls = [call for call in calls if call["kind"] == "batch"]
    assert len(batch_calls) == 1

    prompt = json.loads(batch_calls[0]["text"])
    assert prompt["page_count"] == 2
    assert prompt["pages"] == [
        {"page_artifact_id": "page-1", "page_number": 1},
        {"page_artifact_id": "page-2", "page_number": 2},
    ]
    # The full ClausePack and the exact per-page schema are shared once, unmodified.
    assert prompt["clause_pack"] == page_review_prompt_pack(pack)
    expected_schema = json.loads(
        build_page_review_messages(route, pages[0], pack)[1]["content"][1]["text"]
    )["output_schema"]
    assert prompt["output_schema"] == expected_schema
    assert prompt["review_context"] == _context().model_dump(mode="json")
    assert prompt["batch_response_contract"]["keys"] == "page_artifact_id"

    original_system = build_page_review_messages(route, pages[0], pack)[0]["content"]
    assert batch_calls[0]["system"].startswith(original_system)
    framing = batch_calls[0]["system"][len(original_system):]
    assert "page_artifact_id" in framing
    assert "不得新增未提供的页面键" in framing
    assert "共 2 页" in framing


def test_batch_rejects_mixed_nodes_duplicate_pages_and_empty_input_without_calling_model():
    route = _routes()[PageReviewLane.MAIN_A]
    pack = _clause_pack()
    context_a = PageReviewContext(
        review_episode_id="episode-1", episode_revision=1, stage="screening"
    )
    context_b = PageReviewContext(
        review_episode_id="episode-1", episode_revision=2, stage="screening"
    )
    calls = []
    completion = _batch_completion({}, calls=calls, envelope_queue=[])

    with pytest.raises(ValueError, match="同一审核节点"):
        asyncio.run(read_page_batch(
            route,
            [_page_input("page-1", 1, context_a), _page_input("page-2", 2, context_b)],
            pack,
            completion=completion,
        ))
    with pytest.raises(ValueError, match="同一审核节点"):
        asyncio.run(read_page_batch(
            route,
            [_page_input("page-1", 1), _page_input("page-2", 2, context_a)],
            pack,
            completion=completion,
        ))
    with pytest.raises(ValueError, match="不得重复"):
        asyncio.run(read_page_batch(
            route, [_page_input("page-1", 1), _page_input("page-1", 1)], pack,
            completion=completion,
        ))
    with pytest.raises(ValueError, match="至少需要一页"):
        asyncio.run(read_page_batch(route, [], pack, completion=completion))
    assert calls == []


def test_batch_keeps_valid_pages_and_records_per_page_failure():
    route = _routes()[PageReviewLane.MAIN_A]
    pack = _clause_pack()
    pages = [_page_input("page-1", 1), _page_input("page-2", 2)]
    # A value page carrying no observation violates the page-level contract.
    payloads = {
        "page-1": _payload("page-1"),
        "page-2": _payload("page-2", has_eligibility_value=True),
    }
    calls = []
    result = asyncio.run(
        read_page_batch(
            route, pages, pack,
            completion=_batch_completion(payloads, calls=calls, envelope_queue=[json.dumps(payloads)]),
        )
    )

    assert [record.page_artifact_id for record in result.records] == ["page-1"]
    failures = {failure.page_artifact_id: failure for failure in result.failures}
    assert set(failures) == {"page-2"}
    assert failures["page-2"].failure_kind == "schema"
    assert "不符合页级合同" in failures["page-2"].detail


def test_batch_missing_page_fails_explicitly_without_silent_drop():
    route = _routes()[PageReviewLane.MAIN_A]
    pack = _clause_pack()
    pages = [_page_input("page-1", 1), _page_input("page-2", 2)]
    payloads = {"page-1": _payload("page-1")}
    result = asyncio.run(
        read_page_batch(
            route, pages, pack,
            completion=_batch_completion(payloads, calls=[], envelope_queue=[json.dumps(payloads)]),
        )
    )

    assert [record.page_artifact_id for record in result.records] == ["page-1"]
    failures = {failure.page_artifact_id: failure for failure in result.failures}
    assert set(failures) == {"page-2"}
    assert failures["page-2"].failure_kind == "missing_page"
    assert len(result.records) + len(result.failures) == 2


def test_batch_rejects_unknown_returned_page_and_keeps_expected_pages():
    route = _routes()[PageReviewLane.MAIN_A]
    pack = _clause_pack()
    pages = [_page_input("page-1", 1), _page_input("page-2", 2)]
    payloads = {
        "page-1": _payload("page-1"),
        "page-2": _payload("page-2"),
        "page-9": _payload("page-9"),
    }
    result = asyncio.run(
        read_page_batch(
            route, pages, pack,
            completion=_batch_completion(payloads, calls=[], envelope_queue=[json.dumps(payloads)]),
        )
    )

    assert [record.page_artifact_id for record in result.records] == ["page-1", "page-2"]
    failures = {failure.page_artifact_id: failure for failure in result.failures}
    assert set(failures) == {"page-9"}
    assert failures["page-9"].failure_kind == "unknown_page"


def test_batch_refuses_duplicate_returned_page_key():
    route = _routes()[PageReviewLane.MAIN_A]
    pack = _clause_pack()
    pages = [_page_input("page-1", 1), _page_input("page-2", 2)]
    envelope = (
        '{"page-1": ' + json.dumps(_payload("page-1"))
        + ', "page-1": ' + json.dumps(_payload("page-1"))
        + ', "page-2": ' + json.dumps(_payload("page-2")) + "}"
    )
    result = asyncio.run(
        read_page_batch(
            route, pages, pack,
            completion=_batch_completion(
                {"page-1": _payload("page-1"), "page-2": _payload("page-2")},
                calls=[],
                envelope_queue=[envelope],
            ),
        )
    )

    assert [record.page_artifact_id for record in result.records] == ["page-2"]
    failures = {failure.page_artifact_id: failure for failure in result.failures}
    assert set(failures) == {"page-1"}
    assert failures["page-1"].failure_kind == "duplicate_page"


def test_batch_budget_starts_at_route_max_tokens_and_doubles_once_on_truncation():
    route = _routes()[PageReviewLane.MAIN_A]
    pack = _clause_pack()
    pages, payloads, envelope = _two_page_setup()
    budgets = []

    async def completion(batch_route, messages, budget):
        images = [part for part in messages[1]["content"] if part.get("type") == "image_url"]
        if len(images) > 1:
            budgets.append(budget)
            if len(budgets) == 1:
                return PageCompletion("{}", "length", {})
            return PageCompletion(envelope, "stop", {})
        page_id = json.loads(
            next(part["text"] for part in messages[1]["content"] if part.get("type") == "text")
        )["page_artifact_id"]
        return PageCompletion(json.dumps(payloads[page_id]), "stop", {})

    result = asyncio.run(read_page_batch(route, pages, pack, completion=completion))
    assert result.failures == []
    # Initial budget is route.max_tokens itself, not multiplied by the page count.
    assert budgets == [12000, 24000]


def test_batch_budget_passes_configured_65536_route_through_unmultiplied():
    routes = require_page_reader_routes(
        {
            "INDEPENDENT_VLM_API_KEY": "main-a-key",
            "CMS_SMK_API_KEY": "main-b-key",
            "PAGE_REVIEW_MAIN_B_PROVIDER": "cms-smk",
            "PAGE_REVIEW_MAIN_B_MODEL": "MiniMax-M3",
            "PAGE_REVIEW_CLOUD_CONCURRENCY": "2",
            "PAGE_REVIEW_MAX_TOKENS": "65536",
        }
    )
    route = routes[PageReviewLane.MAIN_A]
    pack = _clause_pack()
    pages, payloads, envelope = _two_page_setup()
    budgets = []

    async def completion(_route, messages, budget):
        images = [part for part in messages[1]["content"] if part.get("type") == "image_url"]
        if len(images) > 1:
            budgets.append(budget)
            if len(budgets) == 1:
                return PageCompletion("{}", "length", {})
            return PageCompletion(envelope, "stop", {})
        page_id = json.loads(
            next(part["text"] for part in messages[1]["content"] if part.get("type") == "text")
        )["page_artifact_id"]
        return PageCompletion(json.dumps(payloads[page_id]), "stop", {})

    result = asyncio.run(read_page_batch(route, pages, pack, completion=completion))
    assert result.failures == []
    assert budgets == [65536, 131072]


def test_batch_truncation_twice_fails_without_further_budget_increase():
    route = _routes()[PageReviewLane.MAIN_A]
    pack = _clause_pack()
    pages, _, _ = _two_page_setup()
    budgets = []

    async def completion(_route, messages, budget):
        images = [part for part in messages[1]["content"] if part.get("type") == "image_url"]
        if len(images) > 1:
            budgets.append(budget)
            return PageCompletion("{}", "length", {})
        raise AssertionError("截断失败后不得进入页级校验")

    with pytest.raises(PageReviewHarnessError) as error:
        asyncio.run(read_page_batch(route, pages, pack, completion=completion))
    assert error.value.failure_kind == "length"
    assert budgets == [12000, 24000]


def test_batch_preflight_rejects_mutated_page_image_before_any_call(tmp_path):
    route = _routes()[PageReviewLane.MAIN_A]
    pack = _clause_pack()
    image_path = tmp_path / "page-2.png"
    image_path.write_bytes(b"page-image-2")
    page_1 = _page_input("page-1", 1)
    page_2 = PageReviewInput(
        page_artifact_id="page-2",
        source_document_version_id="document-1",
        page_number=2,
        page_image_sha256=hashlib.sha256(b"page-image-2").hexdigest(),
        page=PageVisionInput(source_ref="page-2", page_ordinal=2, image_path=str(image_path)),
    )
    image_path.write_bytes(b"mutated-after-freeze")
    calls = []
    completion = _batch_completion({}, calls=calls, envelope_queue=[])

    with pytest.raises(ValueError, match="冻结原件不一致"):
        asyncio.run(read_page_batch(route, [page_1, page_2], pack, completion=completion))
    assert calls == []


def test_batch_preflight_rejects_page_identity_drift_before_any_call():
    route = _routes()[PageReviewLane.MAIN_A]
    pack = _clause_pack()
    page = _page_input("page-1", 1)
    # Bypass the frozen-constructor check to simulate identity drift after registration.
    object.__setattr__(page, "page_number", 2)
    calls = []
    completion = _batch_completion({}, calls=calls, envelope_queue=[])

    with pytest.raises(ValueError, match="页码与图像页序不一致"):
        asyncio.run(read_page_batch(route, [page], pack, completion=completion))
    assert calls == []


def test_batch_rate_limit_waits_then_retries_same_route_budget_and_model():
    route = _routes()[PageReviewLane.MAIN_A]
    pack = _clause_pack()
    pages, payloads, envelope = _two_page_setup()
    calls = []
    waits = []

    class RateLimited(RuntimeError):
        status_code = 429

    async def completion(batch_route, messages, budget):
        images = [part for part in messages[1]["content"] if part.get("type") == "image_url"]
        text_part = next(part for part in messages[1]["content"] if part.get("type") == "text")
        if len(images) > 1:
            calls.append(
                {"base_url": batch_route.base_url, "model": batch_route.model, "budget": budget}
            )
            if len(calls) == 1:
                raise RateLimited("429 too many requests")
            return PageCompletion(envelope, "stop", {"total_tokens": 7})
        page_id = json.loads(text_part["text"])["page_artifact_id"]
        return PageCompletion(json.dumps(payloads[page_id], ensure_ascii=False), "stop", {})

    async def sleep(seconds):
        waits.append(seconds)

    result = asyncio.run(
        read_page_batch(route, pages, pack, completion=completion, sleep=sleep)
    )
    assert waits == [60]
    assert len(calls) == 2
    assert {call["base_url"] for call in calls} == {route.base_url}
    assert {call["model"] for call in calls} == {route.model}
    # The 429 wait does not consume an attempt nor change the output budget.
    assert {call["budget"] for call in calls} == {12000}
    assert result.failures == []
    assert len(result.records) == 2


def test_batch_rate_limit_gives_up_after_max_waits_without_model_switch():
    route = _routes()[PageReviewLane.MAIN_A]
    pack = _clause_pack()
    pages, _, _ = _two_page_setup()
    calls = []

    class RateLimited(RuntimeError):
        status_code = 429

    async def completion(_route, _messages, _budget):
        calls.append((_route.base_url, _route.model))
        raise RateLimited("429 too many requests")

    async def sleep(_seconds):
        pass

    with pytest.raises(PageReviewHarnessError) as error:
        asyncio.run(
            read_page_batch(
                route, pages, pack,
                completion=completion, sleep=sleep, max_rate_limit_waits=2,
            )
        )
    assert error.value.failure_kind == "rate_limit"
    assert calls == [(route.base_url, route.model)] * 3


def test_batch_endpoint_failure_raises_without_model_or_endpoint_switch():
    route = _routes()[PageReviewLane.MAIN_A]
    pack = _clause_pack()
    pages, _, _ = _two_page_setup()
    seen = []

    async def completion(batch_route, _messages, _budget):
        seen.append((batch_route.base_url, batch_route.model))
        raise RuntimeError("endpoint unavailable")

    with pytest.raises(PageReviewHarnessError) as error:
        asyncio.run(read_page_batch(route, pages, pack, completion=completion))
    assert error.value.failure_kind == "endpoint"
    assert seen == [(route.base_url, route.model)]


def test_batch_identity_is_deterministic_scoped_to_the_batch_definition():
    route = _routes()[PageReviewLane.MAIN_A]
    pack = _clause_pack()
    pages, payloads, envelope = _two_page_setup()
    completion = _batch_completion(payloads, calls=[], envelope_queue=[envelope])
    first = asyncio.run(read_page_batch(route, pages, pack, completion=completion))
    second = asyncio.run(
        read_page_batch(
            route, pages, pack,
            completion=_batch_completion(payloads, calls=[], envelope_queue=[envelope]),
        )
    )
    assert first.batch_id == second.batch_id
    assert [record.page_review_id for record in first.records] == [
        record.page_review_id for record in second.records
    ]

    extended_pages = [*pages, _page_input("page-3", 3)]
    extended_payloads = {**payloads, "page-3": _payload("page-3")}
    third = asyncio.run(
        read_page_batch(
            route, extended_pages, pack,
            completion=_batch_completion(
                extended_payloads, calls=[], envelope_queue=[json.dumps(extended_payloads)]
            ),
        )
    )
    assert third.batch_id != first.batch_id

    async def plain_completion(*_args):
        return PageCompletion(json.dumps(payloads["page-1"], ensure_ascii=False), "stop", {})

    plain = asyncio.run(read_page(route, pages[0], pack, completion=plain_completion))
    assert plain.prompt_version == PAGE_REVIEW_PROMPT_VERSION
    assert first.records[0].prompt_version == PAGE_REVIEW_PROMPT_VERSION + "+" + BATCH_PROMPT_VERSION
    assert first.records[0].prompt_version != plain.prompt_version
    assert first.records[0].page_review_id != plain.page_review_id
    assert len({record.page_review_id for record in first.records}) == 2
    assert first.prompt_version == PAGE_REVIEW_PROMPT_VERSION + "+" + BATCH_PROMPT_VERSION


def test_batch_rejects_retired_lane_without_calling_model():
    base_route = _routes()[PageReviewLane.MAIN_B]
    route = base_route.__class__(**{**base_route.__dict__, "lane": PageReviewLane.HANDWRITING_C})
    pack = _clause_pack()
    pages = [_page_input("page-1", 1), _page_input("page-2", 2)]
    payloads = {"page-1": {"handwriting": []}, "page-2": {"handwriting": []}}
    calls = []
    with pytest.raises(PageReviewConfigError, match="两个主读"):
        asyncio.run(
            read_page_batch(
                route, pages, pack,
                completion=_batch_completion(payloads, calls=calls, envelope_queue=[json.dumps(payloads)]),
            )
        )
    assert calls == []
