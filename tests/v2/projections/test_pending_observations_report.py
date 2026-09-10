"""Pending observation retention 投影聚焦测试：纯函数、不触数据库、不调模型。"""

import hashlib
from datetime import datetime, timezone

from app.domain.contracts.evidence_normalizer import (
    EvidenceNormalizerContextInput,
    EvidenceNormalizerInput,
    EvidenceNormalizerPageInput,
    EvidenceNormalizerPageReviewInput,
    evidence_normalizer_input_scope_hash,
    page_review_input_scope_hash,
)
from app.domain.contracts.enums import ReviewStage
from app.domain.contracts.facts import FactAuthority
from app.domain.contracts.page_review import (
    PageCoverageEntry,
    PageDisposition,
    PageFactObservation,
    PageReviewLane,
    PageReviewRecord,
)
from app.domain.page_normalization import fact_normalization_key
from app.domain.page_reconciliation import reconcile_page_reviews
from app.projections.pending_observations_report import (
    PENDING_RETENTION_CODE,
    pending_retention_items,
)
from tests.v2.domain.test_page_observation_context import _fact as _dated_fact
from tests.v2.domain.test_page_review_contracts import _fact as _default_fact
from tests.v2.domain.test_page_review_contracts import (
    _handwriting,
    _review_payload,
)

NOW = datetime(2026, 9, 9, 12, 0, 0, tzinfo=timezone.utc)
SHA = "a" * 64


def _review(lane, page=1, *, facts=(), handwriting=()):
    return PageReviewRecord(**{**_review_payload(),
                               "page_review_id": f"review-p{page}-{lane.value}",
                               "page_artifact_id": f"page-{page}",
                               "page_number": page,
                               "lane": lane,
                               "facts": list(facts),
                               "handwriting": list(handwriting)})


def _page_review(groups):
    reconciliations = [reconcile_page_reviews(pair, determination_modes={})
                       for pair in groups]
    reviews = [record for pair in groups for record in pair]
    entries = [
        PageCoverageEntry(
            page_artifact_id=pair[0].page_artifact_id,
            source_document_version_id=pair[0].source_document_version_id,
            page_number=pair[0].page_number,
            disposition=PageDisposition.ACCEPTED,
            reconciliation_id=reconciliation.reconciliation_id,
        )
        for pair, reconciliation in zip(groups, reconciliations)
    ]
    pack = reconciliations[0].clause_pack_sha256
    return EvidenceNormalizerPageReviewInput(
        coverage_id="coverage-1",
        clause_pack_sha256=pack,
        entries=entries,
        reviews=reviews,
        reconciliations=reconciliations,
        scope_sha256=page_review_input_scope_hash(
            coverage_id="coverage-1",
            clause_pack_sha256=pack,
            entries=entries,
            reviews=reviews,
            reconciliations=reconciliations,
        ),
    )


def _evidence_input(page_review):
    numbers = ([entry.page_number for entry in page_review.entries]
               if page_review is not None else [1])
    pages = []
    for number in numbers:
        text = f"第{number}页有效文本"
        pages.append(EvidenceNormalizerPageInput(
            source_document_version_id="document-1",
            page_artifact_id=f"page-{number}",
            page_number=number,
            effective_text=text,
            effective_text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        ))
    context = EvidenceNormalizerContextInput(
        source_document_version_id="document-1",
        metadata_revision_id="meta-1",
        document_type="筛选病历",
        source_party="研究者",
        current_review_stage=ReviewStage.SCREENING,
    )
    authority = FactAuthority(
        project_id="p1", subject_id="s1", review_episode_id="e1", episode_revision=1,
        protocol_version_id="pv1", rule_set_id="rs1", rule_set_revision=1,
        evidence_snapshot_v2_id="snap1", complete_processing_revision_id="rev1",
    )
    base = dict(
        run_id="run-1", call_id="call-1", authority=authority,
        logical_document_id="doc-1", context=context,
        manifest_sha256=SHA, completion_manifest_sha256=SHA,
        page_numbers=numbers, pages=pages, page_review=page_review,
        created_at=NOW,
    )
    base["input_scope_sha256"] = evidence_normalizer_input_scope_hash(
        authority=authority, logical_document_id="doc-1", context=context,
        related_requirements=[], manifest_sha256=SHA, completion_manifest_sha256=SHA,
        page_numbers=numbers, pages=pages, page_review=page_review,
        available_locator_ids=[], available_locators=[],
    )
    return EvidenceNormalizerInput(**base)


def _contextless_fact(day, observation_id):
    payload = _dated_fact(day).model_dump()
    payload["observation_id"] = observation_id
    payload["context"] = None
    payload["normalization_key"], payload["normalized_value"], payload["normalized_unit"] = (
        fact_normalization_key(payload["field_name"], payload["raw_value"])
    )
    return PageFactObservation.model_validate(payload)


def test_legacy_call_without_page_review_returns_no_items():
    assert pending_retention_items(_evidence_input(None)) == []


def test_fully_accepted_page_returns_no_items():
    reviews = [_review(PageReviewLane.MAIN_A, facts=[_dated_fact("2026-09-01")]),
               _review(PageReviewLane.MAIN_B, facts=[_dated_fact("2026-09-01")])]
    assert pending_retention_items(_evidence_input(_page_review([reviews]))) == []


def test_mixed_page_retains_only_unaccepted_observations():
    accepted = _dated_fact("2026-09-01")
    pending = _dated_fact("2026-09-02")
    reviews = [_review(PageReviewLane.MAIN_A, facts=[accepted, pending]),
               _review(PageReviewLane.MAIN_B, facts=[accepted])]
    items = pending_retention_items(_evidence_input(_page_review([reviews])))
    assert len(items) == 1
    item = items[0]
    assert item.code == PENDING_RETENTION_CODE
    assert item.affected_pages == [1]
    assert item.affected_locator_ids == []
    assert item.affected_requirement_ids == []
    assert item.gap_type is None
    assert item.referenced_file_id is None
    assert item.message == "第1页有1条内容尚待核对，原文已保留。"
    assert "2026-09-02" in item.reason
    assert "「4.2」" in item.reason and "「检查值 4.2」" in item.reason
    assert "「检验项目」" in item.reason and "「2026-09-02」" in item.reason
    # 已采信观察不得被改标为待核对
    assert "2026-09-01" not in item.reason


def test_same_value_with_different_dates_is_never_merged():
    reviews = [_review(PageReviewLane.MAIN_A, facts=[_dated_fact("2026-09-02")]),
               _review(PageReviewLane.MAIN_B, facts=[_dated_fact("2026-09-03")])]
    items = pending_retention_items(_evidence_input(_page_review([reviews])))
    assert len(items) == 1
    assert "2条" in items[0].message
    assert "「2026-09-02」" in items[0].reason
    assert "「2026-09-03」" in items[0].reason


def test_same_value_with_different_objects_is_never_merged():
    first = _dated_fact("2026-09-02")
    second = first.model_copy(deep=True)
    second.observation_id = "other-object"
    second.context = second.context.model_copy(update={"target_text": "另一项目"})
    second.normalization_key, second.normalized_value, second.normalized_unit = (
        fact_normalization_key(second.field_name, second.raw_value,
                               context=second.context.model_dump())
    )
    reviews = [_review(PageReviewLane.MAIN_A, facts=[first]),
               _review(PageReviewLane.MAIN_B, facts=[second])]
    items = pending_retention_items(_evidence_input(_page_review([reviews])))
    assert len(items) == 1
    assert "2条" in items[0].message
    assert "「检验项目」" in items[0].reason
    assert "「另一项目」" in items[0].reason


def test_identical_reads_from_both_lanes_keep_distinct_identity():
    # 无所指对象的事实永远无法采信；两条读道内容一致时只保留一条，
    # 工程观察编号不参与身份。
    fact_a = _contextless_fact("2026-09-02", "read-a")
    fact_b = _contextless_fact("2026-09-02", "read-b")
    reviews = [_review(PageReviewLane.MAIN_A, facts=[fact_a]),
               _review(PageReviewLane.MAIN_B, facts=[fact_b])]
    items = pending_retention_items(_evidence_input(_page_review([reviews])))
    assert len(items) == 1
    assert "2条" in items[0].message
    assert items[0].reason.count("1．") == 1
    assert "读数原文「4.2」" in items[0].reason
    assert "read-a" not in items[0].reason and "read-b" not in items[0].reason


def test_pending_handwriting_is_retained_with_original_text():
    reviews = [_review(PageReviewLane.MAIN_A, facts=[], handwriting=[_handwriting()]),
               _review(PageReviewLane.MAIN_B, facts=[], handwriting=[])]
    items = pending_retention_items(_evidence_input(_page_review([reviews])))
    assert len(items) == 1
    assert "手写原文「NCS」" in items[0].reason
    assert "手写类别「CS/NCS 判断」" in items[0].reason
    assert "所指对象「白细胞」" in items[0].reason
    assert "手写内容及所指对象尚待核对" in items[0].reason


def test_input_source_is_not_mutated():
    reviews = [_review(PageReviewLane.MAIN_A, facts=[_dated_fact("2026-09-02")]),
               _review(PageReviewLane.MAIN_B, facts=[_dated_fact("2026-09-03")])]
    evidence_input = _evidence_input(_page_review([reviews]))
    before = evidence_input.model_dump_json()
    pending_retention_items(evidence_input)
    assert evidence_input.model_dump_json() == before


def test_repeated_calls_are_deterministic():
    accepted = _dated_fact("2026-09-01")
    reviews = [_review(PageReviewLane.MAIN_A,
                       facts=[accepted, _dated_fact("2026-09-02")],
                       handwriting=[_handwriting()]),
               _review(PageReviewLane.MAIN_B, facts=[accepted])]
    evidence_input = _evidence_input(_page_review([reviews]))
    first = [item.model_dump_json() for item in pending_retention_items(evidence_input)]
    second = [item.model_dump_json() for item in pending_retention_items(evidence_input)]
    assert first == second
    assert len(first) == 1
    assert "2条" in pending_retention_items(evidence_input)[0].message


def test_pending_items_are_grouped_per_page_across_pages():
    page1 = [_review(PageReviewLane.MAIN_A, 1, facts=[]),
             _review(PageReviewLane.MAIN_B, 1, facts=[_dated_fact("2026-09-02")])]
    page2 = [_review(PageReviewLane.MAIN_A, 2, facts=[_default_fact()]),
             _review(PageReviewLane.MAIN_B, 2, facts=[])]
    items = pending_retention_items(_evidence_input(_page_review([page1, page2])))
    assert [item.affected_pages for item in items] == [[1], [2]]
    assert "2026-09-02" in items[0].reason
    assert "2026-09-03" not in items[0].reason
    assert "「4.2 x10^9/L」" in items[1].reason
    assert items[1].message == "第2页有1条内容尚待核对，原文已保留。"
