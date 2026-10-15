"""判断检索回执→当前目标绑定装配测试。

回执全部经真实 v4 ``read_judgment_search_page``（注入 fake completion、内存页
字节、真实合同 scope）产生；对抗反例用 model_copy 变造自洽回执。
"""
from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import json

import pytest

from app.domain.contracts.facts import FactAuthority
from app.domain.contracts.judgment_search import (
    JudgmentSearchCoverageStatus,
    JudgmentSearchPageIdentity,
    JudgmentSearchScope,
    judgment_search_scope_sha256,
)
from app.domain.contracts.page_review import PageReviewLane
from app.llm.independent_vlm import PageVisionInput
from app.llm.judgment_search_reader import (
    JUDGMENT_SEARCH_PROMPT_VERSION,
    JudgmentSearchReaderReceipt,
    read_judgment_search_page,
)
from app.llm.page_review_harness import (
    PageCompletion,
    PageReaderRoute,
    PageReviewInput,
)
from app.services.judgment_search_results import (
    JudgmentSearchResultsError,
    assemble_judgment_search_coverage,
)

_IMAGE_A = b"\x89PNG-judgment-page-a"
_IMAGE_B = b"\x89PNG-judgment-page-b"
_TARGET = "ALT 5.6 mmol/L 的研究者临床意义判断"
_PROVIDER_A, _MODEL_A = "zhipu-coding-plan", "GLM-5.3-Flash"
_PROVIDER_B, _MODEL_B = "google", "gemini-3.7-flash"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _scope(pages) -> JudgmentSearchScope:
    ordered = tuple(sorted(pages, key=lambda page: page.order_key))
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


def _scope_two() -> JudgmentSearchScope:
    return _scope([
        JudgmentSearchPageIdentity(
            source_document_version_id="doc-1",
            page_artifact_id="pa-1",
            page_number=1,
            page_image_sha256=hashlib.sha256(_IMAGE_A).hexdigest(),
        ),
        JudgmentSearchPageIdentity(
            source_document_version_id="doc-1",
            page_artifact_id="pa-2",
            page_number=2,
            page_image_sha256=hashlib.sha256(_IMAGE_B).hexdigest(),
        ),
    ])


def _route(lane: PageReviewLane, provider: str = _PROVIDER_A,
           model: str = _MODEL_A, effort: str = "high") -> PageReaderRoute:
    return PageReaderRoute(
        lane=lane, provider=provider, base_url="https://endpoint.example",
        api_key="secret-key", model=model, reasoning_effort=effort,
        max_tokens=2048, max_concurrency=2,
    )


def _channel(disposition: str, candidates=()) -> dict:
    return {"disposition": disposition, "candidates": list(candidates)}


def _not_found_payload(page_number: int = 0) -> str:
    return json.dumps({
        "handwritten": _channel("not_found"),
        "printed_analysis": _channel("not_found"),
    }, ensure_ascii=False)


def _found_payload(page_number: int = 0) -> str:
    return json.dumps({
        "handwritten": _channel("found", [{
            "text": " 医生批注：该异常已核查，CS ",
            "coordinate_convention": "unverified",
        }]),
        "printed_analysis": _channel("not_found"),
    }, ensure_ascii=False)


def _ambiguous_payload(page_number: int = 0) -> str:
    return json.dumps({
        "handwritten": _channel("not_found"),
        "printed_analysis": _channel("ambiguous", [{
            "text": "疑似病程记录判断（指向不明）",
            "uncertainty_note": "作者与日期不可辨",
            "coordinate_convention": "unverified",
        }]),
    }, ensure_ascii=False)


def _fake(text: str, model: str):
    async def fake(route, messages, max_tokens):
        return PageCompletion(
            text=text, finish_reason="stop", usage={},
            response_model=model, response_id=f"resp-{model}-{id(text)}",
        )

    return fake


def _page_input(artifact: str, number: int, image_bytes: bytes) -> PageReviewInput:
    return PageReviewInput(
        page_artifact_id=artifact,
        source_document_version_id="doc-1",
        page_number=number,
        page_image_sha256=hashlib.sha256(image_bytes).hexdigest(),
        page=PageVisionInput(source_ref=f"src-{artifact}", page_ordinal=number,
                             image_bytes=image_bytes),
    )


def _read(scope, page_input, route, text,
          response_model: str | None = None) -> JudgmentSearchReaderReceipt:
    return asyncio.run(read_judgment_search_page(
        scope=scope, page_input=page_input, target_text=_TARGET,
        route=route,
        completion=_fake(text, response_model or route.model),
    ))


def _gather(scope: JudgmentSearchScope, lane_a_text=None, lane_b_text=None,
            route_a=None, route_b=None) -> list[JudgmentSearchReaderReceipt]:
    """两条读道各读范围内两页（文本按读道可选：常量或 (page_number) -> 文本）。"""
    receipts = []
    for lane, default_route, lane_text in (
        (PageReviewLane.MAIN_A, _route(PageReviewLane.MAIN_A), lane_a_text),
        (PageReviewLane.MAIN_B,
         _route(PageReviewLane.MAIN_B, _PROVIDER_B, _MODEL_B), lane_b_text),
    ):
        route = (route_a if lane == PageReviewLane.MAIN_A else route_b) \
            or default_route
        for artifact, number, image in (
            ("pa-1", 1, _IMAGE_A), ("pa-2", 2, _IMAGE_B),
        ):
            text = lane_text(number) if callable(lane_text) \
                else (lane_text or _not_found_payload())
            receipts.append(
                _read(scope, _page_input(artifact, number, image), route, text)
            )
    return receipts


def _assemble(scope, receipts, target: str = _TARGET):
    return assemble_judgment_search_coverage(scope, target, receipts)


# --------------------------------------------------------------------------- 正常路径


def test_full_not_found_pair_binds_to_native_absence_status():
    summary = _assemble(_scope_two(), _gather(_scope_two()))
    assert summary.status == (
        JudgmentSearchCoverageStatus.ALL_SUPPLIED_PAGES_SEARCHED_WITHOUT_CANDIDATE
    )
    assert summary.source_scope_verified is False
    assert summary.product_acceptance is False
    assert summary.professional_judgment_absence_proven is False


def test_found_and_ambiguous_preserved_with_unverified_coordinates():
    receipts = _gather(
        _scope_two(),
        lane_a_text=lambda page_number: (
            _found_payload() if page_number == 1 else _not_found_payload()
        ),
        lane_b_text=lambda page_number: (
            _ambiguous_payload() if page_number == 1 else _not_found_payload()
        ),
    )
    summary = _assemble(_scope_two(), receipts)
    assert summary.status == JudgmentSearchCoverageStatus.CANDIDATES_PRESENT
    found = summary.found_candidates
    assert len(found) == 1
    assert found[0].candidates[0].text == " 医生批注：该异常已核查，CS "
    assert found[0].candidates[0].coordinate_convention == "unverified"
    ambiguous = summary.ambiguous_channels
    assert len(ambiguous) == 1
    assert ambiguous[0].tentative_excerpts[0].uncertainty_note == "作者与日期不可辨"
    assert ambiguous[0].tentative_excerpts[0].coordinate_convention == "unverified"


def test_identical_text_candidates_are_not_treated_as_contamination():
    receipts = _gather(
        _scope_two(),
        lane_a_text=lambda page_number: (
            _found_payload() if page_number == 1 else _not_found_payload()
        ),
        lane_b_text=lambda page_number: (
            _found_payload() if page_number == 2 else _not_found_payload()
        ),
    )
    summary = _assemble(_scope_two(), receipts)
    assert summary.status == JudgmentSearchCoverageStatus.CANDIDATES_PRESENT
    assert len(summary.found_candidates) == 2
    assert (summary.found_candidates[0].candidates[0].text
            == summary.found_candidates[1].candidates[0].text)


def test_missing_page_lane_and_empty_are_native_incomplete():
    scope = _scope_two()
    receipts = _gather(scope, lane_a_text=None, lane_b_text=None)
    partial = [r for r in receipts
               if r.requested.lane == PageReviewLane.MAIN_A or r.page.page_number == 1]
    summary = _assemble(scope, partial)
    assert summary.status == JudgmentSearchCoverageStatus.COVERAGE_INCOMPLETE
    assert summary.pages_without_lane_result

    single_lane = [r for r in receipts
                   if r.requested.lane == PageReviewLane.MAIN_A]
    summary = _assemble(scope, single_lane)
    assert summary.status == JudgmentSearchCoverageStatus.COVERAGE_INCOMPLETE
    assert summary.missing_lanes == (PageReviewLane.MAIN_B,)

    summary = _assemble(scope, [])
    assert summary.status == JudgmentSearchCoverageStatus.COVERAGE_INCOMPLETE
    assert summary.missing_lanes == (PageReviewLane.MAIN_A, PageReviewLane.MAIN_B)
    assert summary.professional_judgment_absence_proven is False


# --------------------------------------------------------------------------- 一致性拒绝


def test_current_target_and_scope_mismatch_rejected():
    scope = _scope_two()
    receipts = _gather(scope)
    with pytest.raises(JudgmentSearchResultsError, match="目标"):
        _assemble(scope, receipts, target="另一个目标文本")
    # 页域内容漂移后的另一合法 scope（可完整重验证，但哈希不同）→ 当前目标绑定拒绝。
    drifted = _scope([
        JudgmentSearchPageIdentity(
            source_document_version_id="doc-1",
            page_artifact_id="pa-1",
            page_number=1,
            page_image_sha256=hashlib.sha256(_IMAGE_A).hexdigest(),
        ),
        JudgmentSearchPageIdentity(
            source_document_version_id="doc-1",
            page_artifact_id="pa-2",
            page_number=2,
            page_image_sha256=_sha("drifted-page-b-bytes"),
        ),
    ])
    with pytest.raises(JudgmentSearchResultsError, match="范围哈希"):
        _assemble(drifted, receipts)


def test_foreign_page_rejected():
    scope = _scope_two()
    receipts = _gather(scope)
    foreign_identity = JudgmentSearchPageIdentity(
        source_document_version_id="doc-1",
        page_artifact_id="pa-9",
        page_number=9,
        page_image_sha256=hashlib.sha256(_IMAGE_A).hexdigest(),
    )
    forged_page_result = receipts[0].page_result.model_copy(update={
        "page_artifact_id": "pa-9", "page_number": 9,
    })
    tampered = receipts[0].model_copy(update={
        "page": foreign_identity,
        "page_result": forged_page_result,
    })
    with pytest.raises(JudgmentSearchResultsError, match="冻结页域成员"):
        _assemble(scope, [tampered, *receipts[1:]])


def test_duplicate_same_lane_page_rejected():
    scope = _scope_two()
    receipts = _gather(scope)
    lane_a = [r for r in receipts if r.requested.lane == PageReviewLane.MAIN_A]
    duplicated = [*lane_a, lane_a[0]]
    with pytest.raises(JudgmentSearchResultsError, match="重复"):
        _assemble(scope, duplicated)


def test_changed_page_result_beside_raw_response_rejected():
    scope = _scope_two()
    receipts = _gather(
        scope,
        lane_a_text=lambda page_number: (
            _found_payload() if page_number == 1 else _not_found_payload()
        ),
    )
    victim = next(r for r in receipts
                  if r.requested.lane == PageReviewLane.MAIN_A
                  and r.page.page_number == 1)
    drifted_candidate = victim.page_result.handwritten.candidates[0].model_copy(
        update={"text": "与原始回答无关的漂移摘录"}
    )
    drifted_channel = victim.page_result.handwritten.model_copy(update={
        "candidates": (drifted_candidate,),
    })
    forged_result = victim.page_result.model_copy(update={
        "handwritten": drifted_channel,
    })
    tampered = victim.model_copy(update={"page_result": forged_result})
    with pytest.raises(JudgmentSearchResultsError, match="原始回答"):
        _assemble(scope, [tampered, *(r for r in receipts if r is not victim)])


def test_hash_response_identity_and_finish_drift_rejected():
    scope = _scope_two()
    receipts = _gather(scope)
    victim = receipts[0]
    completion = victim.completion
    cases = [
        (victim.model_copy(update={"completion_text_sha256": _sha("漂移")}), "哈希"),
        (victim.model_copy(update={"response_id": "resp-forged"}), "响应 ID"),
        (victim.model_copy(update={"response_model": None}), "响应模型"),
        (victim.model_copy(update={"response_model": "unknown-alias-model"}),
         "别名"),
        (victim.model_copy(update={"finish_reason": "length"}), "完整结束"),
        (victim.model_copy(update={"completion": dataclasses.replace(
            completion, response_model="other-model")}), "响应模型"),
        (victim.model_copy(update={"completion": dataclasses.replace(
            completion, response_id="resp-other")}), "响应 ID"),
        (victim.model_copy(update={"completion": dataclasses.replace(
            completion, finish_reason="length")}), "完整结束"),
    ]
    for tampered, keyword in cases:
        with pytest.raises(JudgmentSearchResultsError, match=keyword):
            _assemble(scope, [tampered, *(r for r in receipts if r is not victim)])


def test_same_model_two_lanes_rejected():
    scope = _scope_two()
    receipts = _gather(
        scope,
        route_b=_route(PageReviewLane.MAIN_B, _PROVIDER_A, _MODEL_A),
    )
    with pytest.raises(JudgmentSearchResultsError, match="独立双读"):
        _assemble(scope, receipts)


def test_unknown_response_model_from_production_rejected():
    """读道真实返回未知响应模型（网关别名）：装配拒绝，不做别名猜测。"""
    scope = _scope_two()
    route = _route(PageReviewLane.MAIN_A)
    receipt = asyncio.run(read_judgment_search_page(
        scope=scope, page_input=_page_input("pa-1", 1, _IMAGE_A),
        target_text=_TARGET, route=route,
        completion=_fake(_not_found_payload(), "Unknown-Gateway-Model"),
    ))
    with pytest.raises(JudgmentSearchResultsError, match="别名"):
        _assemble(scope, [receipt])


def test_mixed_effort_within_one_lane_rejected():
    scope = _scope_two()
    low_route = _route(PageReviewLane.MAIN_A, effort="low")
    receipts = [
        _read(scope, _page_input("pa-1", 1, _IMAGE_A),
              _route(PageReviewLane.MAIN_A), _not_found_payload()),
        _read(scope, _page_input("pa-2", 2, _IMAGE_B),
              low_route, _not_found_payload()),
    ]
    with pytest.raises(JudgmentSearchResultsError, match="不一致"):
        _assemble(scope, receipts)


def test_outdated_prompt_version_rejected_without_relabeling():
    scope = _scope_two()
    receipts = _gather(scope)
    stale = receipts[0].model_copy(update={
        "prompt_version": "judgment-search-reader/v3",
    })
    assert stale.prompt_version == "judgment-search-reader/v3"
    with pytest.raises(JudgmentSearchResultsError, match="不重标"):
        _assemble(scope, [stale, *(r for r in receipts if r is not stale)])


def test_model_copy_tampered_receipts_rejected():
    scope = _scope_two()
    receipts = _gather(scope)
    # 回执 scope 哈希列无 pattern：变造值通过重验证后仍被当前目标比对确定性拒绝。
    with pytest.raises(JudgmentSearchResultsError, match="范围哈希"):
        _assemble(scope, [receipts[0].model_copy(update={"scope_sha256": "nothex"})])
    # 页身份合同带 pattern：变造页图哈希在重验证期即拒绝。
    bad_page = receipts[0].page.model_copy(update={"page_image_sha256": "nothex"})
    bad_result = receipts[0].page_result.model_copy(
        update={"page_image_sha256": "nothex"}
    )
    with pytest.raises(JudgmentSearchResultsError, match="重验证"):
        _assemble(scope, [receipts[0].model_copy(update={
            "page": bad_page, "page_result": bad_result,
        })])
    zero_budget = receipts[0].model_copy(update={
        "requested": receipts[0].requested.model_copy(update={"max_tokens": 0}),
    })
    with pytest.raises(JudgmentSearchResultsError, match="预算"):
        _assemble(scope, [zero_budget, *(r for r in receipts if r is not receipts[0])])
    foreign = receipts[0].model_copy(update={
        "requested": receipts[0].requested.model_copy(update={"model": ""}),
    })
    with pytest.raises(JudgmentSearchResultsError, match="model 不得为空白"):
        _assemble(scope, [foreign, *(r for r in receipts if r is not receipts[0])])


# --------------------------------------------------------------------------- 批次回执绑定

_BATCH_TARGET_A = "ALT 5.6 mmol/L 的研究者临床意义判断"
_BATCH_TARGET_B = "AST 3.1 的研究者判断"


def _requirement_scope(requirement_id: str) -> JudgmentSearchScope:
    """同页域、不同 requirement 的合法批次 scope（哈希随内容变化）。"""
    from app.domain.contracts.judgment_search import judgment_search_scope_sha256

    base = _scope_two()
    ordered = tuple(sorted(base.pages, key=lambda page: page.order_key))
    return JudgmentSearchScope(
        authority=base.authority,
        requirement_id=requirement_id,
        pages=ordered,
        scope_sha256=judgment_search_scope_sha256(
            authority=base.authority,
            requirement_id=requirement_id,
            pages=ordered,
        ),
    )


def _batch_read_one_page(targets, text, route=None):
    from app.llm.judgment_search_reader import read_judgment_search_page_batch

    route = route or _route(PageReviewLane.MAIN_A)
    return asyncio.run(read_judgment_search_page_batch(
        page_input=_page_input("pa-1", 1, _IMAGE_A),
        route=route,
        targets=targets,
        completion=_fake(text, route.model),
    ))


def test_batch_receipt_binds_to_matching_scope_only():
    scope_alt = _requirement_scope("req-alt")
    scope_ast = _requirement_scope("req-ast")
    text = json.dumps({"results": [
        {"requirement_id": "req-alt",
         "handwritten": _channel("found", [{"text": " 医生批注：ALT 异常已核查，CS "}]),
         "printed_analysis": _channel("not_found")},
        {"requirement_id": "req-ast",
         "handwritten": _channel("not_found"),
         "printed_analysis": _channel("not_found")},
    ]}, ensure_ascii=False)
    receipts = _batch_read_one_page(
        [(scope_alt, _BATCH_TARGET_A), (scope_ast, "AST 3.1 的研究者判断")],
        text,
    )
    assert len(receipts) == 2
    summary = _assemble(scope_alt, [receipts[0]], target=_BATCH_TARGET_A)
    # 单回执含 found：found 优先于覆盖不完整（原生状态），候选保留、采信恒 False。
    assert summary.status == JudgmentSearchCoverageStatus.CANDIDATES_PRESENT
    assert summary.found_candidates[0].candidates[0].text == \
        " 医生批注：ALT 异常已核查，CS "
    assert summary.product_acceptance is False
    summary = _assemble(scope_ast, [receipts[1]], target="AST 3.1 的研究者判断")
    assert summary.status == JudgmentSearchCoverageStatus.COVERAGE_INCOMPLETE
    # 错位绑定：req-alt 回执配 req-ast scope/target → 范围/目标一致性核对拒绝。
    with pytest.raises(JudgmentSearchResultsError, match="范围哈希"):
        _assemble(scope_ast, [receipts[0]], target="AST 3.1 的研究者判断")


def test_altered_batch_group_rejected_by_binder():
    scope_alt = _requirement_scope("req-alt")
    scope_ast = _requirement_scope("req-ast")
    text = json.dumps({"results": [
        {"requirement_id": "req-alt",
         "handwritten": _channel("not_found"),
         "printed_analysis": _channel("not_found")},
        {"requirement_id": "req-ast",
         "handwritten": _channel("not_found"),
         "printed_analysis": _channel("not_found")},
    ]}, ensure_ascii=False)
    receipts = _batch_read_one_page(
        [(scope_alt, _BATCH_TARGET_A), (scope_ast, "AST 3.1 的研究者判断")], text
    )
    altered = receipts[0].model_copy(
        update={"batch_targets": receipts[0].batch_targets[1:]}
    )
    # 变造后的组清单与原始回答 ID 集合先冲突：确定性拒绝，不做任何改写。
    with pytest.raises(JudgmentSearchResultsError, match="集合与请求不一致"):
        _assemble(scope_alt, [altered], target=_BATCH_TARGET_A)


def test_batch_version_without_group_rejected_by_binder():
    scope_alt = _requirement_scope("req-alt")
    scope_ast = _requirement_scope("req-ast")
    text = json.dumps({"results": [
        {"requirement_id": "req-alt",
         "handwritten": _channel("not_found"),
         "printed_analysis": _channel("not_found")},
        {"requirement_id": "req-ast",
         "handwritten": _channel("not_found"),
         "printed_analysis": _channel("not_found")},
    ]}, ensure_ascii=False)
    receipt = _batch_read_one_page(
        [(scope_alt, _BATCH_TARGET_A), (scope_ast, "AST 3.1 的研究者判断")], text
    )[0]
    stripped = receipt.model_copy(update={"batch_targets": ()})
    with pytest.raises(JudgmentSearchResultsError, match="缺少批次目标组"):
        _assemble(scope_alt, [stripped], target=_BATCH_TARGET_A)


def test_single_receipt_with_batch_metadata_rejected_by_binder():
    scope = _scope_two()
    receipts = _gather(scope)
    group = type(receipts[0].batch_targets) and None  # 占位防误用
    from app.llm.judgment_search_reader import JudgmentSearchBatchTargetIdentity

    forged_group = JudgmentSearchBatchTargetIdentity(
        requirement_id="EX-4",
        scope_sha256=scope.scope_sha256,
        target_sha256=_sha(_TARGET),
    )
    tampered = receipts[0].model_copy(update={"batch_targets": (forged_group,)})
    with pytest.raises(JudgmentSearchResultsError, match="不得携带批次目标组"):
        _assemble(scope, [tampered, *(r for r in receipts if r is not receipts[0])])


def test_batch_response_channel_drift_rejected_by_binder():
    scope_alt = _requirement_scope("req-alt")
    scope_ast = _requirement_scope("req-ast")
    text = json.dumps({"results": [
        {"requirement_id": "req-alt",
         "handwritten": _channel("found", [{"text": " 医生批注：ALT 异常已核查，CS "}]),
         "printed_analysis": _channel("not_found")},
        {"requirement_id": "req-ast",
         "handwritten": _channel("not_found"),
         "printed_analysis": _channel("not_found")},
    ]}, ensure_ascii=False)
    receipts = _batch_read_one_page(
        [(scope_alt, _BATCH_TARGET_A), (scope_ast, "AST 3.1 的研究者判断")], text
    )
    drifted_candidate = receipts[0].page_result.handwritten.candidates[0].model_copy(
        update={"text": "与原始回答无关的漂移摘录"}
    )
    forged = receipts[0].model_copy(update={
        "page_result": receipts[0].page_result.model_copy(update={
            "handwritten": receipts[0].page_result.handwritten.model_copy(
                update={"candidates": (drifted_candidate,)}
            ),
        }),
    })
    with pytest.raises(JudgmentSearchResultsError, match="原始回答"):
        _assemble(scope_alt, [forged], target=_BATCH_TARGET_A)
