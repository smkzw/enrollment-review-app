"""单页判断候选读器测试（全部使用注入的 fake completion，无真实模型调用）。"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
from typing import Any

import pytest

from app.domain.contracts.judgment_search import (
    JudgmentSearchPageIdentity,
    JudgmentSearchScope,
    judgment_search_scope_sha256,
)
from app.domain.contracts.page_review import PageReviewLane
from app.llm.judgment_search_reader import (
    JudgmentSearchReaderError,
    read_judgment_search_page,
)
from app.llm.page_review_harness import (
    PageCompletion,
    PageReaderRoute,
    PageReviewInput,
)
from app.llm.independent_vlm import PageVisionInput

_IMAGE_BYTES = b"\x89PNG-fake-judgment-search-page-bytes"
_IMAGE_SHA = hashlib.sha256(_IMAGE_BYTES).hexdigest()
_OTHER_BYTES = b"\x89PNG-other-page-bytes"
_TARGET = "ALT 5.6 mmol/L 的临床意义判断"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _scope(pages) -> JudgmentSearchScope:
    ordered = tuple(sorted(pages, key=lambda page: page.order_key))
    from app.domain.contracts.facts import FactAuthority

    authority = FactAuthority(
        project_id="proj-1",
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
        requirement_id="EX-4",
        pages=ordered,
        scope_sha256=judgment_search_scope_sha256(
            authority=authority, requirement_id="EX-4", pages=ordered
        ),
    )


def _scope_one() -> JudgmentSearchScope:
    return _scope([
        JudgmentSearchPageIdentity(
            source_document_version_id="doc-1",
            page_artifact_id="pa-1",
            page_number=1,
            page_image_sha256=_IMAGE_SHA,
        )
    ])


def _page_input(
    *,
    doc: str = "doc-1",
    artifact: str = "pa-1",
    number: int = 1,
    image_bytes: bytes = _IMAGE_BYTES,
    image_sha: str | None = None,
    path=None,
) -> PageReviewInput:
    if path is not None:
        page = PageVisionInput(source_ref="file-src", page_ordinal=number,
                               image_path=str(path))
        recorded = hashlib.sha256(path.read_bytes()).hexdigest()
    else:
        page = PageVisionInput(source_ref="src-1", page_ordinal=number,
                               image_bytes=image_bytes)
        recorded = image_sha or hashlib.sha256(image_bytes).hexdigest()
    return PageReviewInput(
        page_artifact_id=artifact,
        source_document_version_id=doc,
        page_number=number,
        page_image_sha256=recorded,
        page=page,
    )


def _route(**overrides) -> PageReaderRoute:
    fields = dict(
        lane=PageReviewLane.MAIN_A,
        provider="zhipu-coding-plan",
        base_url="https://endpoint.example",
        api_key="secret-key-do-not-leak",
        model="GLM-5.3-Flash",
        reasoning_effort="high",
        max_tokens=2048,
        max_concurrency=2,
    )
    fields.update(overrides)
    return PageReaderRoute(**fields)


def _channel(disposition: str, texts=()) -> dict[str, Any]:
    return {
        "disposition": disposition,
        "candidates": [{"text": text} for text in texts],
    }


def _payload_text(**channels) -> str:
    return json.dumps(
        {"handwritten": channels.get("handwritten", _channel("not_found")),
         "printed_analysis": channels.get("printed_analysis", _channel("not_found"))},
        ensure_ascii=False,
    )


def _fake(text: str | None, *, response_model: str | None = "GLM-5.3-Flash",
          finish: str | None = "stop", exc: Exception | None = None):
    calls: list[tuple[PageReaderRoute, list[dict[str, Any]], int]] = []

    async def fake(route, messages, max_tokens):
        calls.append((route, messages, max_tokens))
        if exc is not None:
            raise exc
        return PageCompletion(
            text=text, finish_reason=finish, usage={},
            response_model=response_model, response_id="resp-1",
        )

    return fake, calls


def _reader(scope, page_input, *, target: str = _TARGET, route=None, completion=None):
    return asyncio.run(read_judgment_search_page(
        scope=scope,
        page_input=page_input,
        target_text=target,
        route=route or _route(),
        completion=completion or (_fake(_payload_text())[0]),
    ))


# --------------------------------------------------------------------------- 成功路径


@pytest.mark.parametrize("finish", [None, "content_filter", "tool_calls", "unknown"])
def test_nonterminal_response_never_becomes_not_found(finish):
    fake, calls = _fake(_payload_text(), finish=finish)
    with pytest.raises(JudgmentSearchReaderError) as error:
        _reader(_scope_one(), _page_input(), completion=fake)
    assert error.value.failure_kind == "incomplete"
    assert error.value.completion.finish_reason == finish
    assert len(calls) == 1


@pytest.mark.parametrize("wrap", [lambda body: "[" + body,
                                     lambda body: "[" + body + "]",
                                     lambda body: body + " []",
                                     lambda body: body + " trailing"])
def test_outer_truncation_and_trailing_payload_are_rejected(wrap):
    raw = wrap(_payload_text())
    fake, calls = _fake(raw)
    with pytest.raises(JudgmentSearchReaderError) as error:
        _reader(_scope_one(), _page_input(), completion=fake)
    assert error.value.completion.text == raw
    assert len(calls) == 1


def test_duplicate_channel_does_not_silently_overwrite_found():
    raw = '{"handwritten":{"disposition":"found","candidates":[{"text":"NCS"}]},' + _payload_text()[1:]
    fake, _ = _fake(raw)
    with pytest.raises(JudgmentSearchReaderError) as error:
        _reader(_scope_one(), _page_input(), completion=fake)
    assert error.value.failure_kind == "invalid_json"
    assert error.value.completion.text == raw


def test_success_preserves_full_completion_and_usage():
    response = PageCompletion(text=_payload_text(), finish_reason="stop",
                              usage={"completion_tokens": 200}, response_model="reported-model",
                              output_lengths={"reasoning_content_characters": 20})

    async def fake(*args):
        return response

    receipt = _reader(_scope_one(), _page_input(), completion=fake)
    assert receipt.completion == response
    assert receipt.completion.usage == {"completion_tokens": 200}
    assert receipt.completion.output_lengths == {"reasoning_content_characters": 20}


def test_complete_single_code_fence_preserves_payload_without_retry():
    text = _payload_text(printed_analysis=_channel("ambiguous", [" 原文\n逐字保留 "]))
    fake, calls = _fake("```json\n" + text + "\n```")
    receipt = _reader(_scope_one(), _page_input(), completion=fake)
    assert receipt.page_result.printed_analysis.candidates[0].text == " 原文\n逐字保留 "
    assert receipt.completion.text == "```json\n" + text + "\n```"
    assert len(calls) == 1


def test_uncertainty_is_separate_from_quote_and_coordinates_stay_unverified():
    raw = json.loads(_payload_text())
    raw["handwritten"] = {"disposition": "ambiguous", "candidates": [{
        "text": " 可读原文 ", "uncertainty_note": "前部字迹不清",
        "bbox": {"x0": 1, "y0": 2, "x1": 3, "y1": 4},
    }]}
    receipt = _reader(_scope_one(), _page_input(), completion=_fake(json.dumps(raw))[0])
    candidate = receipt.page_result.handwritten.candidates[0]
    assert candidate.text == " 可读原文 "
    assert candidate.uncertainty_note == "前部字迹不清"
    assert candidate.coordinate_convention == "unverified"
    raw["handwritten"]["candidates"][0]["coordinate_convention"] = "pixel_verified"
    with pytest.raises(JudgmentSearchReaderError):
        _reader(_scope_one(), _page_input(), completion=_fake(json.dumps(raw))[0])


def test_blank_quote_cannot_count_as_found():
    fake, _ = _fake(_payload_text(handwritten=_channel("found", [" \n "])))
    with pytest.raises(JudgmentSearchReaderError):
        _reader(_scope_one(), _page_input(), completion=fake)


@pytest.mark.parametrize("suffix", ["", "\n```\n{}", "\n```\nextra"])
def test_incomplete_or_extra_fenced_output_is_not_repaired(suffix):
    raw = "```json\n" + _payload_text() + suffix
    fake, _ = _fake(raw)
    with pytest.raises(JudgmentSearchReaderError):
        _reader(_scope_one(), _page_input(), completion=fake)


def test_both_channels_multiple_excerpts_preserved_verbatim():
    handwritten = _channel("found", [" 医生批注：该异常已核查，CS ",
                                     "第二处批注\n日期与判定保持原文"])
    printed = _channel("found", ["2026-08-30 病程记录：检验异常已由医师评估"])
    fake, calls = _fake(_payload_text(handwritten=handwritten, printed_analysis=printed))
    receipt = _reader(_scope_one(), _page_input(), completion=fake)
    assert len(calls) == 1
    result = receipt.page_result
    assert [item.text for item in result.handwritten.candidates] == [
        " 医生批注：该异常已核查，CS ",
        "第二处批注\n日期与判定保持原文",
    ]
    assert [item.text for item in result.printed_analysis.candidates] == [
        "2026-08-30 病程记录：检验异常已由医师评估"
    ]
    assert result.page_image_sha256 == _IMAGE_SHA
    assert receipt.product_acceptance is False


def test_ambiguous_tentative_excerpts_preserved():
    handwritten = _channel("ambiguous", ["疑似批注（作者不明）", "疑似第二处（指向不明）"])
    fake, _ = _fake(_payload_text(handwritten=handwritten))
    receipt = _reader(_scope_one(), _page_input(), completion=fake)
    assert receipt.page_result.handwritten.disposition.value == "ambiguous"
    assert len(receipt.page_result.handwritten.candidates) == 2
    assert receipt.page_result.printed_analysis.disposition.value == "not_found"


def test_no_candidates_is_still_not_clinical_proof():
    fake, calls = _fake(_payload_text())
    receipt = _reader(_scope_one(), _page_input(), completion=fake)
    assert len(calls) == 1
    assert receipt.page_result.handwritten.disposition.value == "not_found"
    assert receipt.page_result.printed_analysis.disposition.value == "not_found"
    assert receipt.page_result.handwritten.candidates == ()
    assert receipt.product_acceptance is False


def test_single_call_no_retry_and_no_fallback():
    fake, calls = _fake(_payload_text())
    _reader(_scope_one(), _page_input(), completion=fake)
    assert len(calls) == 1
    route_used, _, budget = calls[0]
    assert route_used is not None and budget == 2048


# --------------------------------------------------------------------------- 调用前拒绝


def test_tampered_scope_rejected_before_call():
    scope = _scope_one()
    tampered = scope.model_copy(update={"requirement_id": "IN-2"})
    fake, calls = _fake(_payload_text())
    with pytest.raises(JudgmentSearchReaderError, match="重验证"):
        _reader(tampered, _page_input(), completion=fake)
    assert calls == []


def test_page_outside_scope_rejected_before_call():
    fake, calls = _fake(_payload_text())
    with pytest.raises(JudgmentSearchReaderError, match="不在冻结检索页域"):
        _reader(_scope_one(), _page_input(number=2), completion=fake)
    assert calls == []


def test_input_hash_mismatch_rejected_before_call():
    fake, calls = _fake(_payload_text())
    with pytest.raises(JudgmentSearchReaderError, match="哈希"):
        _reader(
            _scope_one(),
            _page_input(image_bytes=_OTHER_BYTES),
            completion=fake,
        )
    assert calls == []


def test_changed_image_file_rejected_before_call(tmp_path):
    image_path = tmp_path / "page.png"
    image_path.write_bytes(_IMAGE_BYTES)
    page_input = _page_input(path=image_path)
    image_path.write_bytes(_OTHER_BYTES)
    fake, calls = _fake(_payload_text())
    with pytest.raises(JudgmentSearchReaderError, match="冻结"):
        _reader(_scope_one(), page_input, completion=fake)
    assert calls == []


def test_route_and_target_configuration_rejected_before_call():
    fake, calls = _fake(_payload_text())
    for route in (
        _route(lane=PageReviewLane.HANDWRITING_C),
        _route(provider="  "),
        _route(model=""),
        _route(reasoning_effort="\t "),
        _route(max_tokens=0),
    ):
        with pytest.raises(JudgmentSearchReaderError, match="读道|预算"):
            _reader(_scope_one(), _page_input(), route=route, completion=fake)
    with pytest.raises(JudgmentSearchReaderError, match="空白"):
        _reader(_scope_one(), _page_input(), target="   ", completion=fake)
    assert calls == []


# --------------------------------------------------------------------------- 响应校验


def test_extra_clinical_verdict_rejected_with_raw_response():
    payload = json.loads(_payload_text())
    payload["eligibility"] = "satisfied"
    sent_text = json.dumps(payload, ensure_ascii=False)
    fake, calls = _fake(sent_text)
    with pytest.raises(JudgmentSearchReaderError) as error:
        _reader(_scope_one(), _page_input(), completion=fake)
    assert error.value.failure_kind == "schema"
    assert error.value.completion is not None
    assert error.value.completion.text == sent_text
    assert len(calls) == 1


def test_empty_truncated_and_two_object_responses_rejected():
    valid = _payload_text()
    two_objects = valid + ' {"unrelated": 1}'
    truncated = '{"handwritten": {"disposition": "not_found"}, "printed_analys'
    for text, kind in (( "", "invalid_json"), (truncated, "invalid_json"),
                       (two_objects, "invalid_json")):
        fake, calls = _fake(text)
        with pytest.raises(JudgmentSearchReaderError) as error:
            _reader(_scope_one(), _page_input(), completion=fake)
        assert error.value.failure_kind == kind
        assert error.value.completion is not None
        assert error.value.completion.text == text
        assert len(calls) == 1


def test_partial_payload_rejected_with_raw_response():
    partial = json.dumps({"handwritten": _channel("found", ["批注"])},
                         ensure_ascii=False)
    fake, calls = _fake(partial)
    with pytest.raises(JudgmentSearchReaderError) as error:
        _reader(_scope_one(), _page_input(), completion=fake)
    assert error.value.failure_kind == "schema"
    assert error.value.completion.text == partial
    assert len(calls) == 1


def test_transport_exception_does_not_fabricate_result():
    fake, calls = _fake(None, exc=RuntimeError("endpoint down"))
    with pytest.raises(JudgmentSearchReaderError) as error:
        _reader(_scope_one(), _page_input(), completion=fake)
    assert error.value.failure_kind == "transport"
    assert error.value.completion is None
    assert len(calls) == 1


def test_length_truncation_rejected():
    fake, calls = _fake(_payload_text(), finish="length")
    with pytest.raises(JudgmentSearchReaderError) as error:
        _reader(_scope_one(), _page_input(), completion=fake)
    assert error.value.failure_kind == "length"
    assert len(calls) == 1


# --------------------------------------------------------------------------- 请求与回执


def test_request_uses_frozen_image_target_and_both_channels_without_clause_pack():
    fake, calls = _fake(_payload_text())
    _reader(_scope_one(), _page_input(), completion=fake)
    _, messages, _ = calls[0]
    dumped = json.dumps(messages, ensure_ascii=False)
    assert "clause_pack" not in dumped
    assert _TARGET in dumped
    assert "handwritten" in dumped and "printed_analysis" in dumped
    image_url = messages[1]["content"][0]["image_url"]["url"]
    assert image_url.startswith("data:") and ";base64," in image_url
    assert hashlib.sha256(
        base64.b64decode(image_url.split(",", 1)[1])
    ).hexdigest() == _IMAGE_SHA


def test_receipt_records_identity_and_never_contains_secrets():
    fake, _ = _fake(_payload_text(), response_model=None)
    receipt = _reader(_scope_one(), _page_input(), completion=fake)
    assert receipt.requested.model == "GLM-5.3-Flash"
    assert receipt.response_model is None
    assert receipt.response_id == "resp-1"
    assert receipt.prompt_version == "judgment-search-reader/v4"
    assert receipt.target_sha256 == _sha(_TARGET)
    assert receipt.scope_sha256 == _scope_one().scope_sha256
    dumped = receipt.model_dump_json()
    assert "secret-key-do-not-leak" not in dumped
    assert "endpoint.example" not in dumped


def test_receipt_hash_tracks_target_image_and_effort():
    fake_a, _ = _fake(_payload_text())
    receipt_a = _reader(_scope_one(), _page_input(), completion=fake_a)
    fake_b, _ = _fake(_payload_text())
    receipt_b = _reader(_scope_one(), _page_input(), target="另一目标文本",
                        completion=fake_b)
    assert receipt_b.messages_sha256 != receipt_a.messages_sha256
    assert receipt_b.target_sha256 != receipt_a.target_sha256

    other_scope = _scope([
        JudgmentSearchPageIdentity(
            source_document_version_id="doc-1",
            page_artifact_id="pa-1",
            page_number=1,
            page_image_sha256=hashlib.sha256(_OTHER_BYTES).hexdigest(),
        )
    ])
    fake_c, _ = _fake(_payload_text())
    receipt_c = _reader(
        other_scope,
        _page_input(image_bytes=_OTHER_BYTES),
        completion=fake_c,
    )
    assert receipt_c.messages_sha256 != receipt_a.messages_sha256

    fake_d, _ = _fake(_payload_text())
    receipt_d = _reader(_scope_one(), _page_input(),
                        route=_route(reasoning_effort="low"), completion=fake_d)
    assert receipt_d.requested.reasoning_effort == "low"
    assert receipt_d.model_dump() != receipt_a.model_dump()
