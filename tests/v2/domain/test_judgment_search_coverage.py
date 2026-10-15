"""研究者书面判断检索候选合同与纯覆盖核验的合成测试。

只使用合成页身份，不接真实资料、仓储或模型。全部命名只说 candidate/coverage，
绝不声称 certified 或 accepted 临床证明。
"""
from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from app.domain.contracts.facts import FactAuthority
from app.domain.contracts.judgment_search import (
    JudgmentSearchChannel,
    JudgmentSearchChannelGap,
    JudgmentSearchChannelResult,
    JudgmentSearchCoverageStatus,
    JudgmentSearchCoverageSummary,
    JudgmentSearchDisposition,
    JudgmentSearchExcerptCandidate,
    JudgmentSearchLane,
    JudgmentSearchLaneResult,
    JudgmentSearchPageIdentity,
    JudgmentSearchPageResult,
    JudgmentSearchScope,
    judgment_search_scope_sha256,
)
from app.domain.judgment_search_coverage import (
    JudgmentSearchCoverageError,
    summarize_judgment_search_coverage,
)

_PROVIDER_A, _MODEL_A = "zhipu", "GLM-5.3"
_PROVIDER_B, _MODEL_B = "google", "gemini-2.5-pro"


def _sha(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def _authority() -> FactAuthority:
    return FactAuthority(
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


def _page(version: str, artifact: str, number: int) -> JudgmentSearchPageIdentity:
    return JudgmentSearchPageIdentity(
        source_document_version_id=version,
        page_artifact_id=artifact,
        page_number=number,
        page_image_sha256=_sha(f"{version}/{artifact}/{number}"),
    )


def _scope(pages, requirement_id: str = "EX-4") -> JudgmentSearchScope:
    ordered = tuple(sorted(pages, key=lambda item: item.order_key))
    return JudgmentSearchScope(
        authority=_authority(),
        requirement_id=requirement_id,
        pages=ordered,
        scope_sha256=judgment_search_scope_sha256(
            authority=_authority(), requirement_id=requirement_id, pages=ordered
        ),
    )


def _measurement_scope() -> JudgmentSearchScope:
    """两个文件：检验/测量报告两页 + 打印病历分析一页。"""
    return _scope([
        _page("docver-lab", "page-lab-1", 1),
        _page("docver-lab", "page-lab-2", 2),
        _page("docver-mr", "page-mr-1", 1),
    ])


def _excerpt(text: str, bbox=None) -> JudgmentSearchExcerptCandidate:
    return JudgmentSearchExcerptCandidate(text=text, bbox=bbox)


def _not_found() -> JudgmentSearchChannelResult:
    return JudgmentSearchChannelResult(disposition=JudgmentSearchDisposition.NOT_FOUND)


def _found(*texts: str) -> JudgmentSearchChannelResult:
    return JudgmentSearchChannelResult(
        disposition=JudgmentSearchDisposition.FOUND,
        candidates=tuple(_excerpt(text) for text in texts),
    )


def _unreadable() -> JudgmentSearchChannelResult:
    return JudgmentSearchChannelResult(disposition=JudgmentSearchDisposition.UNREADABLE)


def _ambiguous(*texts: str) -> JudgmentSearchChannelResult:
    return JudgmentSearchChannelResult(
        disposition=JudgmentSearchDisposition.AMBIGUOUS,
        candidates=tuple(_excerpt(text) for text in texts),
    )


def _page_result(
    identity: JudgmentSearchPageIdentity,
    *,
    handwritten: JudgmentSearchChannelResult | None = None,
    printed_analysis: JudgmentSearchChannelResult | None = None,
) -> JudgmentSearchPageResult:
    return JudgmentSearchPageResult(
        source_document_version_id=identity.source_document_version_id,
        page_artifact_id=identity.page_artifact_id,
        page_number=identity.page_number,
        page_image_sha256=identity.page_image_sha256,
        handwritten=handwritten or _not_found(),
        printed_analysis=printed_analysis or _not_found(),
    )


def _lane(
    scope: JudgmentSearchScope,
    lane: JudgmentSearchLane,
    page_results,
    *,
    provider: str = _PROVIDER_A,
    model: str = _MODEL_A,
    reasoning_effort: str = "high",
) -> JudgmentSearchLaneResult:
    return JudgmentSearchLaneResult(
        scope_sha256=scope.scope_sha256,
        lane=lane,
        provider=provider,
        model=model,
        reasoning_effort=reasoning_effort,
        page_results=tuple(page_results),
    )


def _all_not_found_pages(scope: JudgmentSearchScope):
    return [_page_result(page) for page in scope.pages]


def _both_lanes_all_not_found(scope: JudgmentSearchScope):
    return [
        _lane(scope, JudgmentSearchLane.MAIN_A, _all_not_found_pages(scope),
              provider=_PROVIDER_A, model=_MODEL_A),
        _lane(scope, JudgmentSearchLane.MAIN_B, _all_not_found_pages(scope),
              provider=_PROVIDER_B, model=_MODEL_B),
    ]


# --------------------------------------------------------------------------- 冻结页域


def test_empty_scope_is_rejected():
    with pytest.raises(ValidationError):
        _scope([])


def test_duplicate_page_identity_is_rejected():
    duplicated = _page("docver-lab", "page-lab-1", 1)
    with pytest.raises(ValidationError, match="重复"):
        _scope([duplicated, duplicated])


def test_unsorted_scope_members_are_rejected_and_order_is_deterministic():
    # 两个文档版本各用自己的页工件：同名工件跨文档属身份冲突，另行覆盖。
    first = _page("docver-a", "page-a-1", 1)
    second = _page("docver-b", "page-b-1", 1)
    with pytest.raises(ValidationError, match="排序"):
        JudgmentSearchScope(
            authority=_authority(),
            requirement_id="EX-4",
            pages=(second, first),
            scope_sha256=judgment_search_scope_sha256(
                authority=_authority(), requirement_id="EX-4", pages=(second, first)
            ),
        )
    forward = _scope([first, second])
    backward = _scope([second, first])
    assert forward.scope_sha256 == backward.scope_sha256
    assert [page.order_key for page in backward.pages] == sorted(
        page.order_key for page in backward.pages
    )


def test_scope_hash_binds_authority_requirement_and_pages():
    scope = _measurement_scope()
    assert scope.scope_sha256 == judgment_search_scope_sha256(
        authority=scope.authority,
        requirement_id=scope.requirement_id,
        pages=scope.pages,
    )
    other_requirement = _measurement_scope()
    other_requirement = JudgmentSearchScope(
        authority=scope.authority,
        requirement_id="IN-2",
        pages=scope.pages,
        scope_sha256=judgment_search_scope_sha256(
            authority=scope.authority, requirement_id="IN-2", pages=scope.pages
        ),
    )
    assert other_requirement.scope_sha256 != scope.scope_sha256
    stale_hash_page = JudgmentSearchPageIdentity(
        source_document_version_id="docver-lab",
        page_artifact_id="page-lab-1",
        page_number=1,
        page_image_sha256=_sha("stale-bytes"),
    )
    with pytest.raises(ValidationError, match="哈希"):
        JudgmentSearchScope(
            authority=scope.authority,
            requirement_id=scope.requirement_id,
            pages=(stale_hash_page,),
            scope_sha256=scope.scope_sha256,
        )


def test_scope_has_no_filter_field_to_silently_exclude_pages():
    """范围只接受显式逐页身份；不存在按可读性/日期/文档类别过滤的字段。"""
    assert set(JudgmentSearchScope.model_fields) == {
        "schema_version",
        "authority",
        "requirement_id",
        "pages",
        "scope_sha256",
    }
    assert set(JudgmentSearchPageIdentity.model_fields) == {
        "source_document_version_id",
        "page_artifact_id",
        "page_number",
        "page_image_sha256",
    }


# --------------------------------------------------------------------------- 逐页候选形状


def test_found_requires_excerpts_and_non_found_forbids_candidates():
    with pytest.raises(ValidationError, match="摘录"):
        JudgmentSearchChannelResult(disposition=JudgmentSearchDisposition.FOUND)
    for disposition in (
        JudgmentSearchDisposition.NOT_FOUND,
        JudgmentSearchDisposition.UNREADABLE,
    ):
        with pytest.raises(ValidationError, match="摘录"):
            JudgmentSearchChannelResult(
                disposition=disposition, candidates=(_excerpt("虚构摘录"),)
            )
    assert _ambiguous().candidates == ()
    assert [item.text for item in _ambiguous("暂定一", "暂定二").candidates] == [
        "暂定一",
        "暂定二",
    ]
    bbox = {"x0": 1, "y0": 2, "x1": 3, "y1": 4}
    found = _found("医生批注：该异常已核查，CS")
    found_with_bbox = JudgmentSearchChannelResult(
        disposition=JudgmentSearchDisposition.FOUND,
        candidates=(_excerpt("医生批注：该异常已核查，CS", bbox=bbox),),
    )
    assert found_with_bbox.candidates[0].bbox is not None
    assert found.candidates[0].bbox is None


def test_extra_judgment_or_eligibility_fields_are_rejected():
    with pytest.raises(ValidationError):
        JudgmentSearchChannelResult.model_validate({
            "disposition": "found",
            "candidates": [{"text": "逐字摘录"}],
            "eligibility": "satisfied",
        })
    with pytest.raises(ValidationError):
        JudgmentSearchChannelResult.model_validate({
            "disposition": "not_found",
            "professional_judgment": "absent",
        })
    with pytest.raises(ValidationError):
        JudgmentSearchPageResult.model_validate({
            **_page_result(_page("docver-lab", "page-lab-1", 1)).model_dump(mode="json"),
            "judgment_present": True,
        })
    with pytest.raises(ValidationError):
        JudgmentSearchScope.model_validate({
            **_scope([_page("docver-lab", "page-lab-1", 1)]).model_dump(mode="json"),
            "requirement_satisfied": True,
        })
    summary = summarize_judgment_search_coverage(
        _measurement_scope(), _both_lanes_all_not_found(_measurement_scope())
    )
    with pytest.raises(ValidationError):
        JudgmentSearchCoverageSummary.model_validate({
            **summary.model_dump(mode="json"),
            "requirement_satisfied": True,
        })


def test_duplicate_page_in_lane_result_is_rejected():
    scope = _measurement_scope()
    pages = _all_not_found_pages(scope)
    with pytest.raises(ValidationError, match="重复"):
        _lane(scope, JudgmentSearchLane.MAIN_A, [pages[0], pages[0], *pages[1:]])


# --------------------------------------------------------------------------- 覆盖核验


def test_all_supplied_pages_not_found_is_not_professional_judgment_absence_proof():
    scope = _measurement_scope()
    summary = summarize_judgment_search_coverage(
        scope, _both_lanes_all_not_found(scope)
    )
    assert summary.status == (
        JudgmentSearchCoverageStatus.ALL_SUPPLIED_PAGES_SEARCHED_WITHOUT_CANDIDATE
    )
    assert summary.source_scope_verified is False
    assert summary.product_acceptance is False
    assert summary.professional_judgment_absence_proven is False
    assert summary.found_candidates == ()
    assert summary.missing_lanes == ()
    assert summary.pages_without_lane_result == ()
    # 不变量字段类型锁定为 False：即使绕过 frozen 也无法写入 True。
    with pytest.raises(ValidationError):
        JudgmentSearchCoverageSummary.model_validate({
            **summary.model_dump(mode="json"),
            "professional_judgment_absence_proven": True,
        })
    with pytest.raises(ValidationError):
        JudgmentSearchCoverageSummary.model_validate({
            **summary.model_dump(mode="json"),
            "product_acceptance": True,
        })


def test_printed_analysis_on_non_measurement_page_blocks_all_not_found():
    scope = _measurement_scope()
    judgment_page = next(
        page for page in scope.pages
        if page.source_document_version_id == "docver-mr"
    )
    excerpt = "2026-08-30 病程记录：检验异常值已由医师评估，临床意义 CS"
    lane_results = [
        _lane(
            scope, JudgmentSearchLane.MAIN_A,
            [
                _page_result(page) for page in scope.pages
                if page != judgment_page
            ] + [_page_result(judgment_page, printed_analysis=_found(excerpt))],
            provider=_PROVIDER_A, model=_MODEL_A,
        ),
        _lane(
            scope, JudgmentSearchLane.MAIN_B,
            [
                _page_result(page) for page in scope.pages
                if page != judgment_page
            ] + [_page_result(judgment_page, printed_analysis=_found(excerpt))],
            provider=_PROVIDER_B, model=_MODEL_B,
        ),
    ]
    summary = summarize_judgment_search_coverage(scope, lane_results)
    assert summary.status == JudgmentSearchCoverageStatus.CANDIDATES_PRESENT
    assert len(summary.found_candidates) == 2
    assert all(
        candidate.channel == JudgmentSearchChannel.PRINTED_ANALYSIS
        and candidate.page_artifact_id == judgment_page.page_artifact_id
        and [item.text for item in candidate.candidates] == [excerpt]
        for candidate in summary.found_candidates
    )
    assert summary.product_acceptance is False
    assert summary.professional_judgment_absence_proven is False


def test_mixed_found_and_not_found_is_not_consensus_approval():
    scope = _measurement_scope()
    judgment_page = scope.pages[-1]
    lane_results = [
        _lane(
            scope, JudgmentSearchLane.MAIN_A,
            [
                _page_result(page) for page in scope.pages
                if page != judgment_page
            ] + [
                _page_result(judgment_page, handwritten=_found("手写：CS"))
            ],
            provider=_PROVIDER_A, model=_MODEL_A,
        ),
        _lane(scope, JudgmentSearchLane.MAIN_B, _all_not_found_pages(scope),
              provider=_PROVIDER_B, model=_MODEL_B),
    ]
    summary = summarize_judgment_search_coverage(scope, lane_results)
    assert summary.status == JudgmentSearchCoverageStatus.CANDIDATES_PRESENT
    assert len(summary.found_candidates) == 1
    assert summary.found_candidates[0].lane == JudgmentSearchLane.MAIN_A
    assert summary.product_acceptance is False


def test_unreadable_channel_in_one_lane_is_incomplete_second_channel():
    scope = _measurement_scope()
    second_page = scope.pages[1]
    lane_results = [
        _lane(scope, JudgmentSearchLane.MAIN_A, _all_not_found_pages(scope),
              provider=_PROVIDER_A, model=_MODEL_A),
        _lane(
            scope, JudgmentSearchLane.MAIN_B,
            [
                _page_result(page) for page in scope.pages
                if page != second_page
            ] + [_page_result(second_page, printed_analysis=_unreadable())],
            provider=_PROVIDER_B, model=_MODEL_B,
        ),
    ]
    summary = summarize_judgment_search_coverage(scope, lane_results)
    assert summary.status == JudgmentSearchCoverageStatus.COVERAGE_INCOMPLETE
    assert len(summary.unreadable_channels) == 1
    gap = summary.unreadable_channels[0]
    assert (gap.lane, gap.page_artifact_id, gap.channel) == (
        JudgmentSearchLane.MAIN_B, second_page.page_artifact_id,
        JudgmentSearchChannel.PRINTED_ANALYSIS,
    )
    assert gap.disposition == JudgmentSearchDisposition.UNREADABLE
    assert gap.tentative_excerpts == ()
    assert summary.professional_judgment_absence_proven is False


def test_unreadable_in_both_lanes_is_incomplete_not_absence():
    scope = _measurement_scope()
    first_page = scope.pages[0]
    lane_results = [
        _lane(
            scope, JudgmentSearchLane.MAIN_A,
            [_page_result(first_page, handwritten=_unreadable()),
             *(_page_result(page) for page in scope.pages[1:])],
            provider=_PROVIDER_A, model=_MODEL_A,
        ),
        _lane(
            scope, JudgmentSearchLane.MAIN_B,
            [_page_result(first_page, handwritten=_unreadable()),
             *(_page_result(page) for page in scope.pages[1:])],
            provider=_PROVIDER_B, model=_MODEL_B,
        ),
    ]
    summary = summarize_judgment_search_coverage(scope, lane_results)
    assert summary.status == JudgmentSearchCoverageStatus.COVERAGE_INCOMPLETE
    assert len(summary.unreadable_channels) == 2


def test_ambiguous_channel_is_incomplete_and_preserved():
    scope = _measurement_scope()
    judgment_page = scope.pages[-1]
    lane_results = [
        _lane(
            scope, JudgmentSearchLane.MAIN_A,
            [
                *(_page_result(page) for page in scope.pages
                  if page != judgment_page),
                _page_result(judgment_page, printed_analysis=_ambiguous()),
            ],
            provider=_PROVIDER_A, model=_MODEL_A,
        ),
        _lane(
            scope, JudgmentSearchLane.MAIN_B,
            [
                *(_page_result(page) for page in scope.pages
                  if page != judgment_page),
                _page_result(judgment_page, printed_analysis=_ambiguous()),
            ],
            provider=_PROVIDER_B, model=_MODEL_B,
        ),
    ]
    summary = summarize_judgment_search_coverage(scope, lane_results)
    assert summary.status == JudgmentSearchCoverageStatus.COVERAGE_INCOMPLETE
    assert len(summary.ambiguous_channels) == 2
    assert all(
        gap.disposition == JudgmentSearchDisposition.AMBIGUOUS
        and gap.tentative_excerpts == ()
        for gap in summary.ambiguous_channels
    )
    assert summary.found_candidates == ()


def test_omitted_page_is_incomplete_not_not_found():
    scope = _measurement_scope()
    omitted = scope.pages[1]
    lane_results = [
        _lane(scope, JudgmentSearchLane.MAIN_A, _all_not_found_pages(scope),
              provider=_PROVIDER_A, model=_MODEL_A),
        _lane(
            scope, JudgmentSearchLane.MAIN_B,
            [_page_result(page) for page in scope.pages if page != omitted],
            provider=_PROVIDER_B, model=_MODEL_B,
        ),
    ]
    summary = summarize_judgment_search_coverage(scope, lane_results)
    assert summary.status == JudgmentSearchCoverageStatus.COVERAGE_INCOMPLETE
    assert summary.pages_without_lane_result == (
        type(summary.pages_without_lane_result[0])(
            lane=JudgmentSearchLane.MAIN_B,
            source_document_version_id=omitted.source_document_version_id,
            page_artifact_id=omitted.page_artifact_id,
            page_number=omitted.page_number,
        ),
    )
    assert summary.professional_judgment_absence_proven is False


def test_single_lane_is_incomplete_with_missing_lane():
    scope = _measurement_scope()
    summary = summarize_judgment_search_coverage(scope, [
        _lane(scope, JudgmentSearchLane.MAIN_A, _all_not_found_pages(scope),
              provider=_PROVIDER_A, model=_MODEL_A),
    ])
    assert summary.status == JudgmentSearchCoverageStatus.COVERAGE_INCOMPLETE
    assert summary.missing_lanes == (JudgmentSearchLane.MAIN_B,)
    assert summary.professional_judgment_absence_proven is False


# --------------------------------------------------------------------------- 直接拒绝


def test_same_model_masquerading_as_second_lane_is_rejected():
    scope = _measurement_scope()
    with pytest.raises(JudgmentSearchCoverageError, match="相同 provider\\+model"):
        summarize_judgment_search_coverage(scope, [
            _lane(scope, JudgmentSearchLane.MAIN_A, _all_not_found_pages(scope),
                  provider=_PROVIDER_A, model=_MODEL_A),
            _lane(scope, JudgmentSearchLane.MAIN_B, _all_not_found_pages(scope),
                  provider=_PROVIDER_A, model=_MODEL_A),
        ])


def test_scope_hash_mismatch_is_rejected():
    scope = _measurement_scope()
    other_scope = _scope(scope.pages, requirement_id="IN-2")
    assert other_scope.scope_sha256 != scope.scope_sha256
    drifted = JudgmentSearchLaneResult(
        scope_sha256=other_scope.scope_sha256,
        lane=JudgmentSearchLane.MAIN_A,
        provider=_PROVIDER_A,
        model=_MODEL_A,
        reasoning_effort="high",
        page_results=tuple(_all_not_found_pages(scope)),
    )
    with pytest.raises(JudgmentSearchCoverageError, match="范围哈希"):
        summarize_judgment_search_coverage(
            scope,
            [drifted, _lane(scope, JudgmentSearchLane.MAIN_B,
                            _all_not_found_pages(scope),
                            provider=_PROVIDER_B, model=_MODEL_B)],
        )


def test_wrong_page_hash_is_rejected():
    scope = _measurement_scope()
    forged = JudgmentSearchPageResult(
        source_document_version_id=scope.pages[0].source_document_version_id,
        page_artifact_id=scope.pages[0].page_artifact_id,
        page_number=scope.pages[0].page_number,
        page_image_sha256=_sha("forged-bytes"),
        handwritten=_not_found(),
        printed_analysis=_not_found(),
    )
    with pytest.raises(JudgmentSearchCoverageError, match="页图哈希"):
        summarize_judgment_search_coverage(scope, [
            _lane(scope, JudgmentSearchLane.MAIN_A, [forged], provider=_PROVIDER_A,
                  model=_MODEL_A),
            _lane(scope, JudgmentSearchLane.MAIN_B, _all_not_found_pages(scope),
                  provider=_PROVIDER_B, model=_MODEL_B),
        ])


def test_extra_page_outside_scope_is_rejected():
    scope = _measurement_scope()
    outside = _page("docver-unknown", "page-x-9", 9)
    with pytest.raises(JudgmentSearchCoverageError, match="范围之外"):
        summarize_judgment_search_coverage(scope, [
            _lane(scope, JudgmentSearchLane.MAIN_A,
                  [*_all_not_found_pages(scope), _page_result(outside)],
                  provider=_PROVIDER_A, model=_MODEL_A),
            _lane(scope, JudgmentSearchLane.MAIN_B, _all_not_found_pages(scope),
                  provider=_PROVIDER_B, model=_MODEL_B),
        ])


def test_duplicate_lane_is_rejected():
    scope = _measurement_scope()
    lane_result = _lane(scope, JudgmentSearchLane.MAIN_A,
                        _all_not_found_pages(scope),
                        provider=_PROVIDER_A, model=_MODEL_A)
    with pytest.raises(JudgmentSearchCoverageError, match="重复"):
        summarize_judgment_search_coverage(
            scope,
            [lane_result, _lane(scope, JudgmentSearchLane.MAIN_A,
                                _all_not_found_pages(scope),
                                provider=_PROVIDER_B, model=_MODEL_B)],
        )


def test_more_than_two_lane_results_are_rejected():
    scope = _measurement_scope()
    lanes = [
        _lane(scope, JudgmentSearchLane.MAIN_A, _all_not_found_pages(scope),
              provider=_PROVIDER_A, model=_MODEL_A),
        _lane(scope, JudgmentSearchLane.MAIN_B, _all_not_found_pages(scope),
              provider=_PROVIDER_B, model=_MODEL_B),
    ]
    extra = _lane(scope, JudgmentSearchLane.MAIN_B, _all_not_found_pages(scope),
                  provider="other", model="other-model")
    with pytest.raises(JudgmentSearchCoverageError, match="至多"):
        summarize_judgment_search_coverage(scope, [*lanes, extra])


# --------------------------------------------------------------------------- 来源页身份冲突


def test_scope_rejects_two_artifacts_for_same_document_page():
    with pytest.raises(ValidationError, match="来源页身份冲突"):
        _scope([
            _page("docver-lab", "page-lab-1", 1),
            _page("docver-lab", "page-lab-1b", 1),
        ])


def test_scope_rejects_artifact_reuse_across_pages_and_documents():
    with pytest.raises(ValidationError, match="来源页身份冲突"):
        _scope([
            _page("docver-lab", "page-lab-1", 1),
            _page("docver-lab", "page-lab-1", 2),
        ])
    with pytest.raises(ValidationError, match="来源页身份冲突"):
        _scope([
            _page("docver-lab", "page-lab-1", 1),
            _page("docver-mr", "page-lab-1", 1),
        ])


def test_lane_result_rejects_source_page_identity_collisions():
    scope = _measurement_scope()
    base = _page_result(_page("docver-lab", "page-lab-1", 1))
    twin_artifact = _page_result(_page("docver-lab", "page-lab-1b", 1))
    with pytest.raises(ValidationError, match="来源页身份冲突"):
        _lane(scope, JudgmentSearchLane.MAIN_A, [base, twin_artifact])


# --------------------------------------------------------------------------- 多摘录保留


def test_multiple_same_page_candidates_are_all_retained():
    scope = _measurement_scope()
    judgment_page = scope.pages[-1]
    excerpts = ("批注一：该异常值已核查，CS", "批注二：同页第二处独立判断，CS")
    lane_results = [
        _lane(
            scope, lane,
            [
                _page_result(page, printed_analysis=_found(*excerpts))
                if page == judgment_page else _page_result(page)
                for page in scope.pages
            ],
            provider=provider, model=model,
        )
        for lane, provider, model in (
            (JudgmentSearchLane.MAIN_A, _PROVIDER_A, _MODEL_A),
            (JudgmentSearchLane.MAIN_B, _PROVIDER_B, _MODEL_B),
        )
    ]
    summary = summarize_judgment_search_coverage(scope, lane_results)
    assert summary.status == JudgmentSearchCoverageStatus.CANDIDATES_PRESENT
    assert len(summary.found_candidates) == 2
    for candidate in summary.found_candidates:
        assert [item.text for item in candidate.candidates] == list(excerpts)


def test_ambiguous_tentative_excerpts_are_preserved_and_stay_ambiguous():
    scope = _measurement_scope()
    judgment_page = scope.pages[-1]
    tentative = ("疑似批注（字迹模糊）", "疑似第二处（截断）")
    lane_results = [
        _lane(
            scope, lane,
            [
                _page_result(page, handwritten=_ambiguous(*tentative))
                if page == judgment_page else _page_result(page)
                for page in scope.pages
            ],
            provider=provider, model=model,
        )
        for lane, provider, model in (
            (JudgmentSearchLane.MAIN_A, _PROVIDER_A, _MODEL_A),
            (JudgmentSearchLane.MAIN_B, _PROVIDER_B, _MODEL_B),
        )
    ]
    summary = summarize_judgment_search_coverage(scope, lane_results)
    assert summary.status == JudgmentSearchCoverageStatus.COVERAGE_INCOMPLETE
    assert summary.found_candidates == ()
    assert len(summary.ambiguous_channels) == 2
    for gap in summary.ambiguous_channels:
        assert gap.disposition == JudgmentSearchDisposition.AMBIGUOUS
        assert [item.text for item in gap.tentative_excerpts] == list(tentative)
    assert summary.professional_judgment_absence_proven is False
    assert summary.product_acceptance is False


def test_unreadable_gap_cannot_carry_tentative_excerpts_and_gap_kinds_limited():
    base = dict(
        lane=JudgmentSearchLane.MAIN_A,
        source_document_version_id="docver-lab",
        page_artifact_id="page-lab-1",
        page_number=1,
        channel=JudgmentSearchChannel.HANDWRITTEN,
    )
    ok = JudgmentSearchChannelGap(disposition=JudgmentSearchDisposition.UNREADABLE, **base)
    assert ok.tentative_excerpts == ()
    with pytest.raises(ValidationError, match="unreadable 缺口"):
        JudgmentSearchChannelGap(
            disposition=JudgmentSearchDisposition.UNREADABLE,
            tentative_excerpts=(_excerpt("不应存在的摘录"),),
            **base,
        )
    for disposition in (JudgmentSearchDisposition.FOUND, JudgmentSearchDisposition.NOT_FOUND):
        with pytest.raises(ValidationError, match="只允许"):
            JudgmentSearchChannelGap(disposition=disposition, **base)


# --------------------------------------------------------------------------- 读道身份


def test_identity_strings_reject_whitespace_only_and_store_stripped():
    scope = _measurement_scope()
    pages = _all_not_found_pages(scope)
    with pytest.raises(ValidationError):
        _lane(scope, JudgmentSearchLane.MAIN_A, pages, provider="   ")
    with pytest.raises(ValidationError):
        _lane(scope, JudgmentSearchLane.MAIN_A, pages, model="\t\n ")
    with pytest.raises(ValidationError):
        _lane(scope, JudgmentSearchLane.MAIN_A, pages, reasoning_effort="  ")
    stripped = _lane(
        scope, JudgmentSearchLane.MAIN_A, pages,
        provider=" zhipu ", model=" GLM-5.3 ", reasoning_effort=" high ",
    )
    assert (stripped.provider, stripped.model, stripped.reasoning_effort) == (
        "zhipu", "GLM-5.3", "high",
    )


def test_reasoning_effort_is_required_and_not_part_of_identity():
    scope = _measurement_scope()
    pages = _all_not_found_pages(scope)
    with pytest.raises(ValidationError):
        JudgmentSearchLaneResult(
            scope_sha256=scope.scope_sha256,
            lane=JudgmentSearchLane.MAIN_A,
            provider=_PROVIDER_A,
            model=_MODEL_A,
            page_results=tuple(pages),
        )
    with pytest.raises(JudgmentSearchCoverageError, match="相同 provider\\+model"):
        summarize_judgment_search_coverage(scope, [
            _lane(scope, JudgmentSearchLane.MAIN_A, pages,
                  provider=_PROVIDER_A, model=_MODEL_A, reasoning_effort="low"),
            _lane(scope, JudgmentSearchLane.MAIN_B, pages,
                  provider=_PROVIDER_A, model=_MODEL_A, reasoning_effort="max"),
        ])


def test_case_difference_does_not_create_independence():
    scope = _measurement_scope()
    pages = _all_not_found_pages(scope)
    with pytest.raises(JudgmentSearchCoverageError, match="大小写"):
        summarize_judgment_search_coverage(scope, [
            _lane(scope, JudgmentSearchLane.MAIN_A, pages,
                  provider="Zhipu", model=_MODEL_A),
            _lane(scope, JudgmentSearchLane.MAIN_B, pages,
                  provider="zhipu", model="glm-5.3"),
        ])
