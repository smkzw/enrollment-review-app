from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import replace

import pytest

from app.domain.contracts.enums import Comparator, RuleKind, StudyPhase
from app.domain.contracts.page_review import PageCoverageEntry, PageDisposition, PageReviewLane
from app.domain.contracts.rules import (
    AtomicExpression,
    AtomicPredicate,
    Rule,
    RuleComponent,
    RuleSet,
)
from app.domain.page_normalization import (
    fact_normalization_key,
    handwriting_normalization_key,
)
from app.llm.independent_vlm import PageVisionInput
from app.llm.page_review_harness import (
    PageCompletion,
    PageReviewHarnessError,
    PageReviewInput,
    require_page_reader_routes,
)
from app.projections.clause_pack import project_clause_pack
from app.services.page_review_execution import (
    build_subject_page_coverage,
    reconcile_completed_reads,
    review_page,
    review_pages,
)


def _routes(**_kwargs):
    return require_page_reader_routes(
        {
            "INDEPENDENT_VLM_API_KEY": "a",
            "CMS_SMK_API_KEY": "b",
            "PAGE_REVIEW_MAIN_B_PROVIDER": "cms-smk",
            "PAGE_REVIEW_MAIN_B_MODEL": "MiniMax-M3",
            "PAGE_REVIEW_MAIN_B_BASE_URL": "https://new-api.mediportal.com.cn/v1",
            "PAGE_REVIEW_CLOUD_CONCURRENCY": "2",
        }
    )


def _pack():
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


def _page(index: int = 1) -> PageReviewInput:
    image = f"page-{index}".encode()
    return PageReviewInput(
        page_artifact_id=f"page-{index}",
        source_document_version_id="document-1",
        page_number=index,
        page_image_sha256=hashlib.sha256(image).hexdigest(),
        page=PageVisionInput(
            source_ref=f"page-{index}",
            page_ordinal=index,
            image_bytes=image,
        ),
    )


def _fact_payload(*, handwriting: bool = False) -> str:
    key, value, unit = fact_normalization_key("检查值", "4.2 x10^9/L")
    payload = {
        "has_eligibility_value": True,
        "facts": [
            {
                "observation_id": "fact-1",
                "field_name": "检查值",
                "raw_text": "检查值 4.2 x10^9/L",
                "raw_value": "4.2 x10^9/L",
                "normalized_value": value,
                "normalized_unit": unit,
                "normalization_key": key,
                "region": {"excerpt": "检查值 4.2 x10^9/L"},
                "context": {"target_text": "检查值"},
            }
        ],
        "clause_signals": [],
        "handwriting": [],
    }
    if handwriting:
        hkey, text = handwriting_normalization_key("cs_ncs_judgment", "NCS")
        payload["handwriting"] = [
            {
                "observation_id": "handwriting-1",
                "kind": "cs_ncs_judgment",
                "raw_text": "NCS",
                "normalized_text": text,
                "normalization_key": hkey,
                "region": {"excerpt": "NCS"},
                "context": {"target_text": "检查值"},
            }
        ]
    return json.dumps(payload, ensure_ascii=False)


@pytest.mark.parametrize("has_value", [False, True])
@pytest.mark.parametrize("changes", [
    {"source_document_version_id": "another-document"},
    {"page_number": 2},
    {"page_image_sha256": "0" * 64},
    {"clause_pack_id": "clause-pack:" + "0" * 32},
    {"contract_version": "page-review/v2"},
])
def test_persisted_main_reads_must_match_input_before_any_disposition(has_value, changes):
    async def completion(route, _messages, _max_tokens):
        payload = (_fact_payload() if has_value else json.dumps({
            "has_eligibility_value": False, "facts": [],
            "clause_signals": [], "handwriting": [],
        }))
        return PageCompletion(payload, "stop", {})

    result = asyncio.run(review_page(_routes(), _page(), _pack(), completion=completion))
    # Both lanes agree on the wrong source: mutual agreement is not input binding.
    records = [record.model_copy(update=changes) for record in result.records]

    async def must_not_call(*args):
        pytest.fail("来源不符时不得继续调用模型")

    with pytest.raises(ValueError, match="主读结果与当前页面或条款包不一致"):
        asyncio.run(reconcile_completed_reads(
            _page(), _pack(), records,
        ))


def test_two_main_readers_are_the_only_lanes_and_dual_source_handwriting_is_accepted() -> None:
    calls: list[PageReviewLane] = []

    async def completion(route, _messages, _max_tokens):
        calls.append(route.lane)
        return PageCompletion(_fact_payload(handwriting=True), "stop", {})

    result = asyncio.run(
        review_page(_routes(), _page(), _pack(), completion=completion)
    )

    assert set(calls) == {PageReviewLane.MAIN_A, PageReviewLane.MAIN_B}
    assert len(calls) == 2
    assert result.coverage_entry.disposition == PageDisposition.ACCEPTED
    assert len(result.records) == 2
    assert result.reconciliation is not None
    assert result.reconciliation.contract_version == "page-reconciliation/v4"
    assert len(result.reconciliation.accepted_handwriting) == 1
    assert result.reconciliation.handwriting_conflicts == []


def test_handwriting_disagreement_between_main_reads_is_preserved_not_accepted() -> None:
    async def completion(route, _messages, _max_tokens):
        if route.lane == PageReviewLane.MAIN_B:
            return PageCompletion(_fact_payload(), "stop", {})
        return PageCompletion(_fact_payload(handwriting=True), "stop", {})

    result = asyncio.run(
        review_page(_routes(), _page(), _pack(), completion=completion)
    )

    assert result.coverage_entry.disposition == PageDisposition.ACCEPTED
    assert result.reconciliation is not None
    assert result.reconciliation.accepted_handwriting == []
    assert len(result.reconciliation.handwriting_conflicts) == 1


def test_failed_main_lane_is_not_replaced_by_another_reader() -> None:
    async def completion(route, _messages, _max_tokens):
        if route.lane == PageReviewLane.MAIN_A:
            raise PageReviewHarnessError("端点失败", failure_kind="endpoint")
        return PageCompletion(_fact_payload(), "stop", {})

    result = asyncio.run(
        review_page(_routes(), _page(), _pack(), completion=completion)
    )

    assert result.reconciliation is None
    assert result.coverage_entry.disposition == PageDisposition.FAILED_PENDING_REREAD
    assert [item.lane for item in result.coverage_entry.lane_failures] == [
        PageReviewLane.MAIN_A
    ]


def test_mtplx_second_main_reader_never_adds_a_third_vote():
    from dataclasses import replace
    routes = _routes()
    routes[PageReviewLane.MAIN_B] = replace(routes[PageReviewLane.MAIN_B],
        provider="mtplx", model="mtplx-flash-next-optimized-speed")
    calls = []

    async def completion(route, *_):
        calls.append(route.lane)
        assert route.lane != PageReviewLane.HANDWRITING_C
        return PageCompletion(_fact_payload(handwriting=True), "stop", {})

    result = asyncio.run(review_page(routes, _page(), _pack(), completion=completion))
    assert set(calls) == {PageReviewLane.MAIN_A, PageReviewLane.MAIN_B}
    assert len(result.records) == 2
    assert result.reconciliation.accepted_handwriting
    assert {record.lane for record in result.records} == {
        PageReviewLane.MAIN_A, PageReviewLane.MAIN_B,
    }


def test_two_empty_main_reads_create_auditable_discard() -> None:
    async def completion(_route, _messages, _max_tokens):
        payload = {
            "has_eligibility_value": False,
            "facts": [],
            "clause_signals": [],
            "handwriting": [],
        }
        return PageCompletion(json.dumps(payload), "stop", {})

    result = asyncio.run(
        review_page(_routes(), _page(), _pack(), completion=completion)
    )
    assert result.coverage_entry.disposition == (
        PageDisposition.DISCARDED_NO_ELIGIBILITY_VALUE
    )
    assert result.coverage_entry.discard_reason


def test_batch_caps_each_cloud_lane_and_builds_exact_page_coverage() -> None:
    active = {PageReviewLane.MAIN_A: 0, PageReviewLane.MAIN_B: 0}
    peaks = dict(active)

    async def completion(route, _messages, _max_tokens):
        if route.lane in active:
            active[route.lane] += 1
            peaks[route.lane] = max(peaks[route.lane], active[route.lane])
            await asyncio.sleep(0.01)
            active[route.lane] -= 1
        return PageCompletion(_fact_payload(), "stop", {})

    pack = _pack()
    results = asyncio.run(
        review_pages(
            _routes(),
            [_page(index) for index in range(1, 7)],
            pack,
            completion=completion,
        )
    )
    coverage = build_subject_page_coverage(
        subject_id="subject-1",
        review_episode_id="episode-1",
        evidence_snapshot_id="snapshot-1",
        evidence_processing_revision_id="processing-1",
        clause_pack=pack,
        results=results,
    )

    assert peaks == {PageReviewLane.MAIN_A: 2, PageReviewLane.MAIN_B: 2}
    assert coverage.expected_page_artifact_ids == [f"page-{i}" for i in range(1, 7)]
    assert all(
        item.disposition == PageDisposition.ACCEPTED for item in coverage.entries
    )

    failed_results = list(results)
    failed_results[0] = replace(
        failed_results[0],
        coverage_entry=PageCoverageEntry(
            page_artifact_id="page-1",
            source_document_version_id="doc-1",
            page_number=1,
            disposition=PageDisposition.FAILED_PENDING_REREAD,
            lane_failures=[{"lane": "main-B", "failure_kind": "endpoint"}],
        ),
    )
    failed_coverage = build_subject_page_coverage(
        subject_id="subject-1",
        review_episode_id="episode-1",
        evidence_snapshot_id="snapshot-1",
        evidence_processing_revision_id="processing-1",
        clause_pack=pack,
        results=failed_results,
    )
    assert failed_coverage.coverage_id != coverage.coverage_id
