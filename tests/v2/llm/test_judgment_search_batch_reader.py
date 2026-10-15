"""多目标批次候选读器测试（合成 fake completion，恰好一次调用，无真实模型）。"""
from __future__ import annotations

import asyncio
import hashlib
import json

import pytest

from app.domain.contracts.facts import FactAuthority
from app.domain.contracts.judgment_search import (
    JudgmentSearchPageIdentity,
    JudgmentSearchScope,
    judgment_search_scope_sha256,
)
from app.domain.contracts.page_review import PageReviewLane
from app.llm.independent_vlm import PageVisionInput
from app.llm.judgment_search_reader import (
    JUDGMENT_SEARCH_BATCH_PROMPT_VERSION,
    JUDGMENT_SEARCH_PROMPT_VERSION,
    JudgmentSearchReaderError,
    read_judgment_search_page_batch,
)
from app.llm.page_review_harness import (
    PageCompletion,
    PageReaderRoute,
    PageReviewInput,
)

_IMAGE = b"\x89PNG-batch-page-bytes"
_TARGET_A = "ALT 5.6 mmol/L 的研究者临床意义判断"
_TARGET_B = "AST 3.1 U/L 的研究者临床意义判断"
_PROVIDER_A, _MODEL_A = "zhipu-coding-plan", "GLM-5.3-Flash"
_PROVIDER_B, _MODEL_B = "google", "gemini-3.7-flash"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _scope(requirement_id: str, *, authority_project: str = "proj-1",
           extra_page: bool = False) -> JudgmentSearchScope:
    pages = [
        JudgmentSearchPageIdentity(
            source_document_version_id="doc-1",
            page_artifact_id="pa-1",
            page_number=1,
            page_image_sha256=hashlib.sha256(_IMAGE).hexdigest(),
        )
    ]
    if extra_page:
        pages.append(
            JudgmentSearchPageIdentity(
                source_document_version_id="doc-1",
                page_artifact_id="pa-2",
                page_number=2,
                page_image_sha256=hashlib.sha256(b"other-page").hexdigest(),
            )
        )
    ordered = tuple(sorted(pages, key=lambda page: page.order_key))
    authority = FactAuthority(
        project_id=authority_project,
        subject_id="S1",
        review_episode_id="ep-1",
        episode_revision=1,
        protocol_version_id="prot-v1",
        rule_set_id="rules-1",
        rule_set_revision=1,
        evidence_snapshot_v2_id="snap-1",
        complete_processing_revision_id="proc-1",
    )
    return JudgmentSearchScope(
        authority=authority,
        requirement_id=requirement_id,
        pages=ordered,
        scope_sha256=judgment_search_scope_sha256(
            authority=authority, requirement_id=requirement_id, pages=ordered
        ),
    )


def _route(lane: PageReviewLane = PageReviewLane.MAIN_A,
           provider: str = _PROVIDER_A, model: str = _MODEL_A) -> PageReaderRoute:
    return PageReaderRoute(
        lane=lane, provider=provider, base_url="https://endpoint.example",
        api_key="secret-key", model=model, reasoning_effort="high",
        max_tokens=2048, max_concurrency=2,
    )


def _page_input(artifact: str = "pa-1", number: int = 1, image: bytes = _IMAGE,
                path=None) -> PageReviewInput:
    if path is not None:
        page = PageVisionInput(source_ref="file-src", page_ordinal=number,
                               image_path=str(path))
        recorded = hashlib.sha256(path.read_bytes()).hexdigest()
    else:
        page = PageVisionInput(source_ref="src-1", page_ordinal=number,
                               image_bytes=image)
        recorded = hashlib.sha256(image).hexdigest()
    return PageReviewInput(
        page_artifact_id=artifact,
        source_document_version_id="doc-1",
        page_number=number,
        page_image_sha256=recorded,
        page=page,
    )


def _channel(disposition: str, texts=()) -> dict:
    return {"disposition": disposition,
            "candidates": [{"text": text} for text in texts]}


def _batch_text(results: dict[str, tuple[str, list[str]]], *, fence: bool = False
                ) -> str:
    payload = {"results": [
        {"requirement_id": requirement_id,
         "handwritten": _channel(disposition, texts[:1]),
         "printed_analysis": _channel(
             "ambiguous", texts[1:]
         ) if len(texts) > 1 else _channel("not_found")}
        for requirement_id, (disposition, texts) in results.items()
    ]}
    text = json.dumps(payload, ensure_ascii=False)
    return f"```json\n{text}\n```" if fence else text


def _fake(text: str, *, finish: str = "stop", model: str = _MODEL_A, exc=None):
    calls: list[tuple[PageReaderRoute, list[dict], int]] = []

    async def fake(route, messages, max_tokens):
        calls.append((route, messages, max_tokens))
        if exc is not None:
            raise exc
        return PageCompletion(text=text, finish_reason=finish, usage={},
                              response_model=model, response_id="resp-batch-1")

    return fake, calls


def _targets(*pairs):
    return [(scope, target) for scope, target in pairs]


def _run(page_input, route, targets, completion):
    return asyncio.run(read_judgment_search_page_batch(
        page_input=page_input, route=route, targets=targets, completion=completion,
    ))


# --------------------------------------------------------------------------- 正常批次


def test_two_targets_one_call_ordered_receipts_shared_raw_response():
    scope_a = _scope("req-alt")
    scope_b = _scope("req-ast")
    text = _batch_text({
        "req-alt": ("found", [" 医生批注：ALT 异常已核查，CS "]),
        "req-ast": ("not_found", []),
    })
    fake, calls = _fake(text)
    receipts = _run(
        _page_input(), _route(),
        _targets((scope_a, _TARGET_A), (scope_b, _TARGET_B)),
        fake,
    )
    assert len(calls) == 1
    route_used, messages, budget = calls[0]
    assert budget == 2048
    assert route_used.model == "GLM-5.3-Flash"
    dumped = json.dumps(messages, ensure_ascii=False)
    assert "clause_pack" not in dumped
    assert _TARGET_A in dumped and _TARGET_B in dumped
    assert "handwritten" in dumped and "printed_analysis" in dumped
    assert len(receipts) == 2
    assert [r.scope_sha256 for r in receipts] == [
        scope_a.scope_sha256, scope_b.scope_sha256
    ]
    assert receipts[0].target_sha256 == _sha(_TARGET_A)
    assert receipts[1].target_sha256 == _sha(_TARGET_B)
    for receipt in receipts:
        assert receipt.prompt_version == JUDGMENT_SEARCH_BATCH_PROMPT_VERSION
        assert receipt.completion.text == text
        assert receipt.messages_sha256 == receipts[0].messages_sha256
        assert receipt.requested.max_tokens == 2048
        assert receipt.product_acceptance is False
        assert len(receipt.batch_targets) == 2
        assert {g.requirement_id for g in receipt.batch_targets} == {
            "req-alt", "req-ast"
        }
    assert receipts[0].completion is receipts[1].completion
    assert receipts[0].page_result.handwritten.disposition.value == "found"
    assert (receipts[0].page_result.handwritten.candidates[0].text
            == " 医生批注：ALT 异常已核查，CS ")
    assert receipts[0].page_result.handwritten.candidates[0].coordinate_convention \
        == "unverified"
    assert receipts[1].page_result.handwritten.disposition.value == "not_found"


def test_batch_same_quote_for_different_targets_preserved():
    scope_a = _scope("req-alt")
    scope_b = _scope("req-ast")
    same_quote = "同一处批注原文，与两个目标相关"
    text = _batch_text({
        "req-alt": ("found", [same_quote]),
        "req-ast": ("found", [same_quote]),
    })
    fake, _ = _fake(text)
    receipts = _run(
        _page_input(), _route(),
        _targets((scope_a, _TARGET_A), (scope_b, _TARGET_B)), fake,
    )
    assert receipts[0].page_result.handwritten.candidates[0].text == same_quote
    assert receipts[1].page_result.handwritten.candidates[0].text == same_quote
    # 相同文本是各自来源绑定的独立候选：不降级、不合并、不拒绝。


def test_batch_fenced_complete_json_accepted():
    scope_a = _scope("req-alt")
    scope_b = _scope("req-ast")
    text = _batch_text({
        "req-alt": ("not_found", []),
        "req-ast": ("not_found", []),
    }, fence=True)
    fake, _ = _fake(text)
    receipts = _run(
        _page_input(), _route(),
        _targets((scope_a, _TARGET_A), (scope_b, _TARGET_B)), fake,
    )
    assert len(receipts) == 2


# --------------------------------------------------------------------------- 回答无效


def test_batch_missing_extra_duplicate_ids_fail_with_raw_response():
    scope_a = _scope("req-alt")
    scope_b = _scope("req-ast")
    page_input = _page_input()
    full = {"req-alt": ("not_found", []), "req-ast": ("not_found", [])}
    missing = {"req-alt": ("not_found", [])}
    extra = {**full, "req-unknown": ("not_found", [])}
    duplicate_text = json.dumps({"results": [
        {"requirement_id": "req-alt", "handwritten": _channel("not_found"),
         "printed_analysis": _channel("not_found")},
        {"requirement_id": "req-alt", "handwritten": _channel("not_found"),
         "printed_analysis": _channel("not_found")},
        {"requirement_id": "req-ast", "handwritten": _channel("not_found"),
         "printed_analysis": _channel("not_found")},
    ]}, ensure_ascii=False)
    for bad_text in (
        _batch_text(missing), _batch_text(extra), duplicate_text,
    ):
        fake, calls = _fake(bad_text)
        with pytest.raises(JudgmentSearchReaderError) as error:
            _run(page_input, _route(),
                 _targets((scope_a, _TARGET_A), (scope_b, _TARGET_B)), fake)
        assert error.value.failure_kind == "batch_shape"
        assert error.value.completion is not None
        assert error.value.completion.text == bad_text
        assert len(calls) == 1


def test_batch_nonstop_finish_rejected_with_raw_response():
    scope_a = _scope("req-alt")
    scope_b = _scope("req-ast")
    fake, calls = _fake(
        _batch_text({"req-alt": ("not_found", []), "req-ast": ("not_found", [])}),
        finish="length",
    )
    with pytest.raises(JudgmentSearchReaderError) as error:
        _run(_page_input(), _route(),
             _targets((scope_a, _TARGET_A), (scope_b, _TARGET_B)), fake)
    assert error.value.failure_kind == "length"
    assert error.value.completion is not None
    assert len(calls) == 1


# --------------------------------------------------------------------------- 调用前拒绝


def test_batch_page_membership_and_image_drift_fail_before_request(tmp_path):
    scope_a = _scope("req-alt")
    scope_b = _scope("req-ast")
    fake, calls = _fake(_batch_text(full := {
        "req-alt": ("not_found", []), "req-ast": ("not_found", [])
    }))
    with pytest.raises(JudgmentSearchReaderError, match="不在冻结检索页域"):
        _run(_page_input("pa-9", 9), _route(), _targets((scope_a, _TARGET_A),
                                                        (scope_b, _TARGET_B)), fake)
    image_path = tmp_path / "page.png"
    image_path.write_bytes(_IMAGE)
    drifting_input = _page_input(path=image_path)
    image_path.write_bytes(b"replaced-image-bytes")
    with pytest.raises(JudgmentSearchReaderError, match="拒绝发送|不一致"):
        _run(drifting_input, _route(),
             _targets((scope_a, _TARGET_A), (scope_b, _TARGET_B)), fake)
    assert calls == []


def test_batch_cross_authority_and_page_set_fail_before_request():
    fake, calls = _fake(_batch_text({
        "req-alt": ("not_found", []), "req-ast": ("not_found", [])
    }))
    route = _route()
    with pytest.raises(JudgmentSearchReaderError, match="权威"):
        _run(_page_input(), route,
             _targets((_scope("req-alt"), _TARGET_A),
                      (_scope("req-ast", authority_project="proj-2"), _TARGET_B)),
             fake)
    with pytest.raises(JudgmentSearchReaderError, match="页域"):
        _run(_page_input(), route,
             _targets((_scope("req-alt"), _TARGET_A),
                      (_scope("req-ast", extra_page=True), _TARGET_B)), fake)
    with pytest.raises(JudgmentSearchReaderError, match="重复"):
        _run(_page_input(), route,
             _targets((_scope("req-alt"), _TARGET_A),
                      (_scope("req-alt"), _TARGET_B)), fake)
    with pytest.raises(JudgmentSearchReaderError, match="不得为空"):
        _run(_page_input(), route, [], fake)
    with pytest.raises(JudgmentSearchReaderError, match="空白"):
        _run(_page_input(), route,
             _targets((_scope("req-alt"), "   ")), fake)
    assert calls == []


# --------------------------------------------------------------------------- 单版本不变


def test_single_prompt_version_and_messages_unchanged():
    assert JUDGMENT_SEARCH_PROMPT_VERSION == "judgment-search-reader/v4"
    assert JUDGMENT_SEARCH_BATCH_PROMPT_VERSION == "judgment-search-batch/v1"
