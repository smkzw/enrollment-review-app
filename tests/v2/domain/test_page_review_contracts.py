from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.contracts.page_review import (
    ClauseEvidenceSignal,
    EvidenceSignal,
    HandwritingKind,
    HandwritingObservation,
    PageCoverageEntry,
    PageDisposition,
    PageFactObservation,
    PageLaneFailure,
    PageRegion,
    PageReviewLane,
    PageReviewRecord,
    ObservationContext,
    SubjectPageCoverage,
)
from app.domain.contracts.clause_pack import DeterminationMode
from app.domain.page_reconciliation import (
    PageReconciliationError,
    reconcile_page_reviews,
)
from app.domain.page_normalization import (
    fact_normalization_key,
    handwriting_normalization_key,
    normalize_field_name,
    normalize_scalar,
)

HASH = "a" * 64


@pytest.mark.parametrize("marks,accepted", [(('↑', '↓'), False), (('↑', ''), False), (('↓', '↓'), True)])
def test_equal_numbers_do_not_erase_source_annotation_disagreement(marks, accepted):
    records = []
    for lane, mark in zip(("main-A", "main-B"), marks):
        payload = _review_payload()
        fact = _fact().model_dump()
        fact["raw_value"] = f"4.2 {mark} x10^9/L"
        key, value, unit = fact_normalization_key(fact["field_name"], fact["raw_value"], context=fact["context"])
        fact.update(normalization_key=key, normalized_value=value, normalized_unit=unit)
        payload.update(lane=lane, page_review_id=lane, facts=[fact])
        records.append(PageReviewRecord.model_validate(payload))
    result = reconcile_page_reviews(records, determination_modes={})
    assert bool(result.accepted_fact_keys) == accepted
    if not accepted:
        assert "异常标记" in result.fact_conflicts[0].reason


def _region() -> PageRegion:
    return PageRegion(excerpt="原始资料摘录")


def _fact() -> PageFactObservation:
    context = ObservationContext(target_text="白细胞")
    key, value, unit = fact_normalization_key("实验室检查值", "4.2 x10^9/L", context=context.model_dump())
    return PageFactObservation(
        observation_id="fact-1",
        field_name="实验室检查值",
        raw_text="白细胞 4.2 x10^9/L",
        raw_value="4.2 x10^9/L",
        normalized_value=value,
        normalized_unit=unit,
        normalization_key=key,
        region=_region(),
        context=context,
    )


def _handwriting() -> HandwritingObservation:
    context = ObservationContext(target_text="白细胞")
    key, value = handwriting_normalization_key(
        HandwritingKind.CS_NCS_JUDGMENT.value, "NCS", context=context.model_dump()
    )
    return HandwritingObservation(
        observation_id="handwriting-1",
        kind=HandwritingKind.CS_NCS_JUDGMENT,
        raw_text="NCS",
        normalized_text=value,
        normalization_key=key,
        region=_region(),
        context=context,
    )


def _review_payload() -> dict:
    return {
        "page_review_id": "review-a",
        "page_artifact_id": "page-1",
        "source_document_version_id": "document-1",
        "page_number": 1,
        "page_image_sha256": HASH,
        "clause_pack_id": "clause-pack:" + "b" * 32,
        "clause_pack_sha256": "b" * 64,
        "lane": PageReviewLane.MAIN_A,
        "provider": "provider-a",
        "model": "model-a",
        "reasoning_effort": "high",
        "endpoint_base_url": "https://provider.example/v1",
        "fallback_used": False,
        "finish_reason": "stop",
        "usage": {"total_tokens": 100},
        "prompt_version": "page-review-r3/v1",
        "response_sha256": "c" * 64,
        "has_eligibility_value": True,
        "facts": [_fact()],
        "clause_signals": [
            ClauseEvidenceSignal(
                clause_id="component-1",
                signal=EvidenceSignal.MENTIONS,
                region=_region(),
            )
        ],
        "handwriting": [_handwriting()],
    }


@pytest.mark.parametrize("forbidden", ["exclusion_triggered", "supports_not_met"])
def test_page_review_rejects_determination_words(forbidden: str) -> None:
    payload = _review_payload()
    payload[forbidden] = True
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        PageReviewRecord.model_validate(payload)


def test_handwriting_is_required_even_when_empty() -> None:
    payload = _review_payload()
    del payload["handwriting"]
    with pytest.raises(ValidationError, match="handwriting"):
        PageReviewRecord.model_validate(payload)


def test_retired_third_lane_receipt_cannot_vote_in_reconciliation() -> None:
    payload = _review_payload()
    payload.update(
        lane=PageReviewLane.HANDWRITING_C,
        reasoning_effort="low",
        facts=[],
        clause_signals=[],
    )
    legacy_receipt = PageReviewRecord.model_validate(payload)

    first = PageReviewRecord.model_validate(_review_payload())
    second = PageReviewRecord.model_validate({**_review_payload(), "page_review_id": "review-b", "lane": "main-B"})
    with pytest.raises(PageReconciliationError, match="第三读"):
        reconcile_page_reviews([first, second, legacy_receipt], determination_modes={})


def test_signal_requires_excerpt_except_for_none() -> None:
    with pytest.raises(ValidationError, match="必须携带原文摘录"):
        ClauseEvidenceSignal(clause_id="component-1", signal=EvidenceSignal.FOR)
    with pytest.raises(ValidationError, match="不得携带摘录"):
        ClauseEvidenceSignal(
            clause_id="component-1", signal=EvidenceSignal.NONE, region=_region()
        )


def test_subject_page_coverage_requires_exactly_one_disposition_per_page() -> None:
    coverage = SubjectPageCoverage(
        coverage_id="coverage-1",
        subject_id="subject-1",
        review_episode_id="episode-1",
        evidence_snapshot_id="snapshot-1",
        evidence_processing_revision_id="revision-1",
        clause_pack_sha256=HASH,
        expected_page_artifact_ids=["page-1", "page-2", "page-3"],
        entries=[
            PageCoverageEntry(
                page_artifact_id="page-1",
                source_document_version_id="document-1",
                page_number=1,
                disposition=PageDisposition.ACCEPTED,
                reconciliation_id="reconciliation-1",
            ),
            PageCoverageEntry(
                page_artifact_id="page-2",
                source_document_version_id="document-1",
                page_number=2,
                disposition=PageDisposition.DISCARDED_NO_ELIGIBILITY_VALUE,
                discard_reason="仅含空白封底。",
            ),
            PageCoverageEntry(
                page_artifact_id="page-3",
                source_document_version_id="document-1",
                page_number=3,
                disposition=PageDisposition.FAILED_PENDING_REREAD,
                lane_failures=[
                    PageLaneFailure(
                        lane=PageReviewLane.MAIN_B,
                        failure_kind="endpoint",
                    )
                ],
            ),
        ],
    )
    assert len(coverage.entries) == 3

    payload = coverage.model_dump(mode="json")
    payload["entries"] = payload["entries"][:-1]
    with pytest.raises(ValidationError, match="每一预期页"):
        SubjectPageCoverage.model_validate(payload)


def test_reconciliation_accepts_two_source_facts_and_handwriting() -> None:
    first = PageReviewRecord.model_validate(_review_payload())
    second_payload = _review_payload()
    second_payload.update(page_review_id="review-b", lane=PageReviewLane.MAIN_B)
    second = PageReviewRecord.model_validate(second_payload)

    result = reconcile_page_reviews(
        [first, second],
        determination_modes={"component-1": DeterminationMode.SEMANTIC},
    )

    assert result.accepted_fact_keys == [_fact().normalization_key]
    assert [item.normalization_key for item in result.accepted_handwriting] == [
        _handwriting().normalization_key
    ]
    assert [item.signal for item in result.accepted_clause_signals] == [
        EvidenceSignal.MENTIONS
    ]
    assert not result.fact_conflicts
    assert result.contract_version == "page-reconciliation/v4"


def test_reconciliation_drops_deterministic_direction_signals() -> None:
    first = PageReviewRecord.model_validate(_review_payload())
    second_payload = _review_payload()
    second_payload.update(page_review_id="review-b", lane=PageReviewLane.MAIN_B)
    second = PageReviewRecord.model_validate(second_payload)

    result = reconcile_page_reviews(
        [first, second],
        determination_modes={"component-1": DeterminationMode.DETERMINISTIC},
    )

    assert result.accepted_clause_signals == []
    assert result.dropped_deterministic_signal_clause_ids == ["component-1"]


def test_handwriting_needs_two_distinct_lanes() -> None:
    first = PageReviewRecord.model_validate(_review_payload())
    second_payload = _review_payload()
    second_payload.update(
        page_review_id="review-b",
        lane=PageReviewLane.MAIN_B,
        handwriting=[],
    )
    second = PageReviewRecord.model_validate(second_payload)

    result = reconcile_page_reviews([first, second], determination_modes={})
    assert result.accepted_handwriting == []
    assert len(result.handwriting_conflicts) == 1


def test_reconciliation_requires_both_main_lanes() -> None:
    first = PageReviewRecord.model_validate(_review_payload())
    with pytest.raises(PageReconciliationError, match="main-A 与 main-B"):
        reconcile_page_reviews([first], determination_modes={})


@pytest.mark.parametrize("field,value", [
    ("page_image_sha256", "d" * 64),
    ("source_document_version_id", "other-version"),
    ("page_number", 2),
])
def test_same_page_id_cannot_hide_different_source_bytes(field, value):
    a = PageReviewRecord(**_review_payload())
    b = PageReviewRecord(**{**_review_payload(), "page_review_id": "b", "lane": "main-B", field: value})
    with pytest.raises(PageReconciliationError):
        reconcile_page_reviews([a, b], determination_modes={})


def test_repeated_equal_values_need_occurrence_association_before_acceptance():
    payload = _review_payload()
    duplicate = _fact().model_copy(update={"observation_id": "fact-second-occurrence"})
    a = PageReviewRecord(**{**payload, "facts": [_fact(), duplicate]})
    b = PageReviewRecord(**{**payload, "page_review_id": "b", "lane": "main-B"})
    result = reconcile_page_reviews([a, b], determination_modes={})
    assert result.accepted_fact_keys == []
    assert result.fact_conflicts


def test_ambiguous_handwriting_lane_does_not_vote_for_two_different_occurrences():
    payload = _review_payload()
    a = PageReviewRecord(**{**payload, "handwriting": [
        _handwriting(), _handwriting().model_copy(update={"observation_id": "second-position"}),
    ]})
    b = PageReviewRecord(**{**payload, "page_review_id": "b", "lane": "main-B"})
    result = reconcile_page_reviews([a, b], determination_modes={})
    assert result.accepted_handwriting == []
    assert result.handwriting_conflicts

    # A retired third lane cannot break the dual-source tie anymore.
    c = PageReviewRecord(**{**payload, "page_review_id": "c", "lane": "handwriting-C",
                           "reasoning_effort": "low", "facts": [], "clause_signals": []})
    with pytest.raises(PageReconciliationError, match="第三读"):
        reconcile_page_reviews([a, b, c], determination_modes={})


def test_reconciliation_identity_includes_determination_modes() -> None:
    first = PageReviewRecord(**_review_payload())
    second = PageReviewRecord(**{**_review_payload(), "page_review_id": "review-b", "lane": "main-B"})
    semantic = reconcile_page_reviews([first, second], determination_modes={"component-1": DeterminationMode.SEMANTIC})
    deterministic = reconcile_page_reviews([first, second], determination_modes={"component-1": DeterminationMode.DETERMINISTIC})
    assert semantic.reconciliation_id != deterministic.reconciliation_id
    repeated = reconcile_page_reviews([first, second], determination_modes={"component-1": DeterminationMode.SEMANTIC})
    assert repeated.reconciliation_id == semantic.reconciliation_id


def test_normalization_precedes_reconciliation() -> None:
    assert normalize_scalar(" ４.２０ mmol/L ↑ ") == ("4.2", "mmol/l")
    assert normalize_scalar("2026年9月2日") == ("2026-09-02", None)
    assert normalize_field_name(" 白细胞-计数 ") == "白细胞计数"
    assert normalize_field_name("WBC", {"wbc": "白细胞计数"}) == "白细胞计数"


def test_fact_contract_rejects_model_claimed_normalization_key() -> None:
    payload = _fact().model_dump(mode="json")
    payload["normalization_key"] = "模型自行声称的键"
    with pytest.raises(ValidationError, match="确定性规范化"):
        PageFactObservation.model_validate(payload)


def test_duplicate_signals_from_one_lane_do_not_count_as_two_sources() -> None:
    payload = _review_payload()
    payload["clause_signals"] *= 2
    first = PageReviewRecord.model_validate(payload)
    second_payload = _review_payload()
    second_payload.update(page_review_id="review-b", lane=PageReviewLane.MAIN_B,
                          clause_signals=[])
    second = PageReviewRecord.model_validate(second_payload)
    result = reconcile_page_reviews(
        [first, second],
        determination_modes={"component-1": DeterminationMode.SEMANTIC},
    )
    assert result.accepted_clause_signals == []
    assert len(result.signal_conflicts) == 1


@pytest.mark.parametrize("raw, expected", [
    (0, "0"),
    ("1.234567", "1.234567"),
    ("1.234568", "1.234568"),
    ("12345678901234567890", "12345678901234567890"),
    ("4.2000", "4.2"),
])
def test_numeric_normalization_preserves_exact_value(raw, expected) -> None:
    assert normalize_scalar(raw) == (expected, None)
