"""R3 视觉事实来源合同与纯物化器测试（合成夹具，不触真实资料）。"""

from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from app.domain.contracts.evidence import BoundingBox
from app.domain.contracts.page_review import (
    ObservationContext,
    PageCoverageEntry,
    PageDisposition,
    PageFactObservation,
    PageRegion,
    PageReconciliation,
    PageReviewLane,
    PageReviewRecord,
    ReconciliationConflict,
)
from app.domain.page_normalization import fact_normalization_key
from app.domain.page_reconciliation import reconcile_page_reviews
from app.domain.page_review_evidence_sources import (
    PageVisualEvidenceSourceError,
    VisualFactReading,
    VisualFactSource,
    VisualHandwritingReading,
    VisualHandwritingSource,
    VisualPageExcerptLocator,
    materialize_page_visual_evidence_sources,
    visual_fact_source_id,
    visual_handwriting_source_id,
)
from app.domain.page_source_association import PageAssociationSource
from tests.v2.domain.test_page_review_contracts import (
    _fact,
    _handwriting,
    _review_payload,
)

_ASSOC_TEXT = "序号1：白细胞 4.2 x10^9/L，参考区间正常。"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _pair(a_overrides=None, b_overrides=None):
    a = PageReviewRecord(**{**_review_payload(), **(a_overrides or {})})
    b = PageReviewRecord(**{
        **_review_payload(),
        "page_review_id": "review-b",
        "lane": "main-B",
        "provider": "provider-b",
        "model": "model-b",
        **(b_overrides or {}),
    })
    return a, b


def _coverage(reconciliation, *, entry=None, clause_pack_sha256="b" * 64):
    if entry is None:
        entry = PageCoverageEntry(
            page_artifact_id="page-1",
            source_document_version_id="document-1",
            page_number=1,
            disposition=PageDisposition.ACCEPTED,
            reconciliation_id=reconciliation.reconciliation_id,
        )
    from app.domain.contracts.page_review import SubjectPageCoverage

    return SubjectPageCoverage(
        coverage_id="coverage-1",
        subject_id="subject-1",
        review_episode_id="episode-1",
        evidence_snapshot_id="snapshot-1",
        evidence_processing_revision_id="revision-1",
        clause_pack_sha256=clause_pack_sha256,
        expected_page_artifact_ids=[entry.page_artifact_id],
        entries=[entry],
    )


def _materialize(a, b, reconciliation=None, coverage=None, **kwargs):
    reconciliation = reconciliation or reconcile_page_reviews([a, b], determination_modes={})
    coverage = coverage or _coverage(reconciliation)
    return materialize_page_visual_evidence_sources([a, b], reconciliation, coverage, **kwargs)


def _fact_reading(lane, observation, *, provider):
    excerpt = observation.region.excerpt
    return VisualFactReading(
        lane=lane,
        page_review_id="review-a" if lane == PageReviewLane.MAIN_A else "review-b",
        provider=provider,
        model=f"model-{provider}",
        reasoning_effort="high",
        prompt_version="page-review-r3/v1",
        response_sha256="c" * 64,
        observation=observation,
        locator=VisualPageExcerptLocator(excerpt=excerpt, excerpt_sha256=_sha256(excerpt)),
    )


def _handwriting_reading(lane, observation, *, provider):
    excerpt = observation.region.excerpt
    return VisualHandwritingReading(
        lane=lane,
        page_review_id="review-a" if lane == PageReviewLane.MAIN_A else "review-b",
        provider=provider,
        model=f"model-{provider}",
        reasoning_effort="high",
        prompt_version="page-review-r3/v1",
        response_sha256="c" * 64,
        observation=observation,
        locator=VisualPageExcerptLocator(excerpt=excerpt, excerpt_sha256=_sha256(excerpt)),
    )


def test_materializes_accepted_facts_and_handwriting_with_full_provenance():
    a, b = _pair()
    reconciliation = reconcile_page_reviews([a, b], determination_modes={})
    result = _materialize(a, b, reconciliation)

    assert [item.normalization_keys for item in result.fact_sources] == [
        (key,) for key in sorted(reconciliation.accepted_fact_keys)
    ]
    fact_source = result.fact_sources[0]
    readings = {item.lane: item for item in fact_source.readings}
    assert set(readings) == {PageReviewLane.MAIN_A, PageReviewLane.MAIN_B}
    assert readings[PageReviewLane.MAIN_A].page_review_id == "review-a"
    assert readings[PageReviewLane.MAIN_B].page_review_id == "review-b"
    assert readings[PageReviewLane.MAIN_A].provider == "provider-a"
    assert readings[PageReviewLane.MAIN_B].provider == "provider-b"
    assert readings[PageReviewLane.MAIN_A].response_sha256 == a.response_sha256
    assert readings[PageReviewLane.MAIN_B].response_sha256 == b.response_sha256
    assert readings[PageReviewLane.MAIN_A].observation.raw_value == "4.2 x10^9/L"
    assert readings[PageReviewLane.MAIN_A].observation.region.excerpt == "原始资料摘录"
    assert readings[PageReviewLane.MAIN_A].locator.excerpt == "原始资料摘录"
    assert readings[PageReviewLane.MAIN_A].locator.precision == "page_excerpt"
    assert readings[PageReviewLane.MAIN_A].locator.excerpt_sha256 == _sha256("原始资料摘录")
    assert readings[PageReviewLane.MAIN_B].observation.context.target_text == "白细胞"

    handwriting = result.handwriting_sources[0]
    assert handwriting.kind.value == "cs_ncs_judgment"
    assert handwriting.normalized_text == "ncs"
    assert {item.lane for item in handwriting.readings} == {
        PageReviewLane.MAIN_A,
        PageReviewLane.MAIN_B,
    }
    assert handwriting.readings[0].locator.excerpt_sha256 == _sha256("原始资料摘录")

    assert result.page_artifact_id == "page-1"
    assert result.source_document_version_id == "document-1"
    assert result.page_number == 1
    assert result.page_image_sha256 == a.page_image_sha256
    assert result.clause_pack_id == a.clause_pack_id
    assert result.clause_pack_sha256 == a.clause_pack_sha256
    assert result.reconciliation_id == reconciliation.reconciliation_id
    assert result.coverage_id == "coverage-1"
    assert result.evidence_snapshot_id == "snapshot-1"
    assert result.evidence_processing_revision_id == "revision-1"


def test_visual_excerpt_is_preserved_literally_without_ocr_substring_requirement():
    excerpt = "白细胞 4.2↑（手写补记）…"
    a, b = _pair(b_overrides={"facts": [
        {**_fact().model_dump(), "region": {"excerpt": excerpt}},
    ]})
    result = _materialize(a, b)
    reading_b = next(
        item for item in result.fact_sources[0].readings
        if item.lane == PageReviewLane.MAIN_B
    )
    assert reading_b.observation.region.excerpt == excerpt
    assert reading_b.locator.excerpt == excerpt
    assert reading_b.locator.excerpt_sha256 == _sha256(excerpt)


def test_content_addressing_is_stable_and_sensitive_to_source_content():
    a, b = _pair()
    first = _materialize(a, b)
    second = _materialize(b, a)
    assert first.source_set_id == second.source_set_id

    _, changed_response = _pair(b_overrides={"response_sha256": "d" * 64})
    assert _materialize(a, changed_response).source_set_id != first.source_set_id

    _, changed_excerpt = _pair(b_overrides={"facts": [
        {**_fact().model_dump(), "region": {"excerpt": "另一段视觉摘录"}},
    ]})
    assert _materialize(a, changed_excerpt).source_set_id != first.source_set_id

    changed_binding = _coverage(reconcile_page_reviews([a, b], determination_modes={}))
    changed_binding.evidence_snapshot_id = "snapshot-2"
    rebound = materialize_page_visual_evidence_sources(
        [a, b], reconcile_page_reviews([a, b], determination_modes={}), changed_binding
    )
    assert rebound.source_set_id != first.source_set_id


def test_duplicate_model_identity_in_two_lanes_is_not_independent():
    a, b = _pair(b_overrides={"provider": "provider-a", "model": "model-a"})
    reconciliation = reconcile_page_reviews([a, b], determination_modes={})
    with pytest.raises(PageVisualEvidenceSourceError, match="独立双读"):
        _materialize(a, b, reconciliation)


def test_materializer_rejects_lane_page_image_document_drift():
    image_a, image_b = _pair(b_overrides={"page_image_sha256": "f" * 64})
    stale = PageReconciliation(
        reconciliation_id="page-reconciliation:" + "0" * 32,
        page_artifact_id="page-1",
        clause_pack_sha256="b" * 64,
        page_review_ids=["review-a", "review-b"],
    )
    with pytest.raises(PageVisualEvidenceSourceError, match="同一页"):
        _materialize(image_a, image_b, stale)

    document_a, document_b = _pair(b_overrides={"source_document_version_id": "document-2"})
    with pytest.raises(PageVisualEvidenceSourceError, match="同一页"):
        _materialize(document_a, document_b, stale)


def test_reconciliation_page_and_review_id_bindings_are_enforced():
    a, b = _pair()
    other_page = _pair(
        a_overrides={"page_artifact_id": "page-2", "page_number": 2},
        b_overrides={"page_artifact_id": "page-2", "page_number": 2},
    )
    other_page_reconciliation = reconcile_page_reviews(list(other_page), determination_modes={})
    with pytest.raises(PageVisualEvidenceSourceError, match="不属于当前页工件"):
        _materialize(a, b, other_page_reconciliation)

    other_reviews = _pair(a_overrides={"page_review_id": "review-x"})
    other_review_reconciliation = reconcile_page_reviews(list(other_reviews), determination_modes={})
    with pytest.raises(PageVisualEvidenceSourceError, match="页审记录"):
        _materialize(a, b, other_review_reconciliation)

    stale_pack = PageReconciliation(
        reconciliation_id="page-reconciliation:" + "0" * 32,
        page_artifact_id="page-1",
        clause_pack_sha256="a" * 64,
        page_review_ids=["review-a", "review-b"],
    )
    with pytest.raises(PageVisualEvidenceSourceError, match="条款包版本不一致"):
        _materialize(a, b, stale_pack)


def test_stale_accepted_fact_key_without_matching_readings_is_rejected():
    a, b = _pair()
    reconciliation = reconcile_page_reviews([a, b], determination_modes={})
    poisoned = reconciliation.model_copy(update={
        "accepted_fact_keys": reconciliation.accepted_fact_keys + ["ghost|1|"],
    })
    with pytest.raises(PageVisualEvidenceSourceError, match="无匹配观察"):
        _materialize(a, b, poisoned)


def test_tampered_accepted_handwriting_representative_is_rejected():
    a, b = _pair()
    reconciliation = reconcile_page_reviews([a, b], determination_modes={})
    poisoned = reconciliation.model_copy(update={
        "accepted_handwriting": [
            reconciliation.accepted_handwriting[0].model_copy(
                update={"region": PageRegion(excerpt="被篡改摘录")}
            )
        ],
    })
    with pytest.raises(PageVisualEvidenceSourceError, match="不得由物化器合成"):
        _materialize(a, b, poisoned)


def test_coverage_binding_is_enforced():
    a, b = _pair()
    reconciliation = reconcile_page_reviews([a, b], determination_modes={})
    with pytest.raises(PageVisualEvidenceSourceError, match="未找到当前页工件"):
        _materialize(a, b, reconciliation, _coverage(reconciliation, entry=PageCoverageEntry(
            page_artifact_id="page-9",
            source_document_version_id="document-1",
            page_number=9,
            disposition=PageDisposition.ACCEPTED,
            reconciliation_id=reconciliation.reconciliation_id,
        )))
    with pytest.raises(PageVisualEvidenceSourceError, match="资料版本或页码"):
        _materialize(a, b, reconciliation, _coverage(reconciliation, entry=PageCoverageEntry(
            page_artifact_id="page-1",
            source_document_version_id="document-2",
            page_number=1,
            disposition=PageDisposition.ACCEPTED,
            reconciliation_id=reconciliation.reconciliation_id,
        )))
    with pytest.raises(PageVisualEvidenceSourceError, match="已采信页面"):
        _materialize(a, b, reconciliation, _coverage(reconciliation, entry=PageCoverageEntry(
            page_artifact_id="page-1",
            source_document_version_id="document-1",
            page_number=1,
            disposition=PageDisposition.DISCARDED_NO_ELIGIBILITY_VALUE,
            discard_reason="仅含空白封底。",
        )))
    with pytest.raises(PageVisualEvidenceSourceError, match="对账记录不一致"):
        _materialize(a, b, reconciliation, _coverage(reconciliation, entry=PageCoverageEntry(
            page_artifact_id="page-1",
            source_document_version_id="document-1",
            page_number=1,
            disposition=PageDisposition.ACCEPTED,
            reconciliation_id="page-reconciliation:" + "0" * 32,
        )))
    with pytest.raises(PageVisualEvidenceSourceError, match="条款包版本不一致"):
        _materialize(a, b, reconciliation, _coverage(reconciliation, clause_pack_sha256="a" * 64))


def test_clause_only_page_materializes_nothing_and_excludes_clause_signals():
    clause_only = {
        **_review_payload(),
        "facts": [],
        "handwriting": [],
        "clause_signals": [
            {"clause_id": "component-1", "signal": "mentions", "region": {"excerpt": "原始资料摘录"}}
        ],
    }
    a = PageReviewRecord(**clause_only)
    b = PageReviewRecord(**{
        **clause_only,
        "page_review_id": "review-b",
        "lane": "main-B",
        "provider": "provider-b",
        "model": "model-b",
    })
    reconciliation = reconcile_page_reviews([a, b], determination_modes={})
    assert reconciliation.accepted_clause_signals
    result = _materialize(a, b, reconciliation)
    assert result.fact_sources == ()
    assert result.handwriting_sources == ()
    assert "component-1" not in result.model_dump_json()


def test_conflicts_and_single_reader_content_are_never_materialized():
    a, b = _pair(b_overrides={"facts": [], "handwriting": []})
    reconciliation = reconcile_page_reviews([a, b], determination_modes={})
    assert reconciliation.accepted_fact_keys == []
    assert reconciliation.fact_conflicts
    assert reconciliation.handwriting_conflicts
    result = _materialize(a, b, reconciliation)
    assert result.fact_sources == ()
    assert result.handwriting_sources == ()


def test_raw_observation_keeps_model_bbox_but_locator_is_coordinate_free():
    plain_a, plain_b = _pair()
    plain = _materialize(plain_a, plain_b)
    bbox = BoundingBox(x0=10, y0=20, x1=110, y1=40)
    boxed_a, boxed_b = _pair(a_overrides={"facts": [
        {**_fact().model_dump(), "region": {
            "excerpt": "原始资料摘录",
            "bbox": bbox.model_dump(),
        }},
    ]})
    boxed = _materialize(boxed_a, boxed_b)
    boxed_readings = {item.lane: item for item in boxed.fact_sources[0].readings}
    plain_readings = {item.lane: item for item in plain.fact_sources[0].readings}
    assert boxed_readings[PageReviewLane.MAIN_A].observation.region.bbox == bbox
    assert "bbox" not in boxed_readings[PageReviewLane.MAIN_A].locator.model_dump()
    assert (
        boxed_readings[PageReviewLane.MAIN_A].locator.excerpt_sha256
        == plain_readings[PageReviewLane.MAIN_A].locator.excerpt_sha256
    )
    assert boxed.fact_sources[0].fact_source_id != plain.fact_sources[0].fact_source_id
    assert boxed.source_set_id != plain.source_set_id


def test_page_text_hash_stays_separate_from_page_image_hash():
    a, b = _pair()
    reconciliation = reconcile_page_reviews([a, b], determination_modes={})
    coverage = _coverage(reconciliation)
    with pytest.raises(PageVisualEvidenceSourceError, match="不得写入同一哈希"):
        materialize_page_visual_evidence_sources(
            [a, b], reconciliation, coverage, page_text_sha256=a.page_image_sha256
        )
    result = materialize_page_visual_evidence_sources(
        [a, b], reconciliation, coverage, page_text_sha256="e" * 64
    )
    assert result.page_text_sha256 == "e" * 64
    without_text = _materialize(a, b, reconciliation, coverage)
    assert without_text.page_text_sha256 is None
    assert result.source_set_id != without_text.source_set_id


def test_materializer_revalidates_mutated_inputs_via_dumps():
    a, b = _pair()
    reconciliation = reconcile_page_reviews([a, b], determination_modes={})
    coverage = _coverage(reconciliation)
    tampered_record = a.model_copy(update={
        "facts": [a.facts[0].model_copy(update={"normalization_key": "ghost|1|"})],
    })
    with pytest.raises(ValidationError):
        _materialize(tampered_record, b, reconciliation, coverage)
    tampered_reconciliation = reconciliation.model_copy(update={
        "accepted_handwriting": [
            reconciliation.accepted_handwriting[0].model_copy(update={"raw_text": "NCS（代签）"})
        ],
    })
    with pytest.raises(ValidationError):
        _materialize(a, b, tampered_reconciliation, coverage)


def test_accepted_target_also_listed_in_conflict_is_rejected():
    a, b = _pair()
    reconciliation = reconcile_page_reviews([a, b], determination_modes={})
    poisoned = reconciliation.model_copy(update={
        "fact_conflicts": list(reconciliation.fact_conflicts) + [ReconciliationConflict(
            field_name="实验室检查值",
            normalization_keys=[reconciliation.accepted_fact_keys[0]],
            page_review_ids=[a.page_review_id, b.page_review_id],
            reason="回归测试：已采信键同时记入冲突",
        )],
    })
    with pytest.raises(PageVisualEvidenceSourceError, match="同时记入冲突"):
        _materialize(a, b, poisoned)


def test_conflict_referencing_unknown_review_id_is_rejected():
    a, b = _pair()
    reconciliation = reconcile_page_reviews([a, b], determination_modes={})
    poisoned = reconciliation.model_copy(update={
        "handwriting_conflicts": [ReconciliationConflict(
            field_name="handwriting",
            normalization_keys=["k"],
            page_review_ids=["review-unknown"],
            reason="回归测试：冲突引用未知页审记录",
        )],
    })
    with pytest.raises(PageVisualEvidenceSourceError, match="未知页审记录"):
        _materialize(a, b, poisoned)


def _assoc_fact(observation_id, location_text, excerpt="白细胞 4.2 x10^9/L"):
    context = ObservationContext(
        target_text="白细胞", location_text=location_text, polarity="asserted",
    )
    key, value, unit = fact_normalization_key(
        "实验室检查值", "4.2 x10^9/L", context=context.model_dump()
    )
    return PageFactObservation(
        observation_id=observation_id,
        field_name="实验室检查值",
        raw_text="白细胞 4.2 x10^9/L",
        raw_value="4.2 x10^9/L",
        normalized_value=value,
        normalized_unit=unit,
        normalization_key=key,
        region=PageRegion(excerpt=excerpt),
        context=context,
    )


def _assoc_pair(facts_a=None, facts_b=None):
    a = PageReviewRecord(**{**_review_payload(), "facts": facts_a, "handwriting": []})
    b = PageReviewRecord(**{
        **_review_payload(),
        "page_review_id": "review-b",
        "lane": "main-B",
        "provider": "provider-b",
        "model": "model-b",
        "facts": facts_b,
        "handwriting": [],
    })
    return a, b


def _assoc_source(text=_ASSOC_TEXT):
    return PageAssociationSource(
        source_document_version_id="document-1",
        page_number=1,
        text=text,
        text_sha256=_sha256(text),
    )


def test_source_associated_different_key_pair_materializes_with_bound_source():
    a, b = _assoc_pair(
        facts_a=[_assoc_fact("obs-a", "表格第一行")],
        facts_b=[_assoc_fact("obs-b", "血常规栏")],
    )
    source = _assoc_source()
    reconciliation = reconcile_page_reviews(
        [a, b], determination_modes={}, association_source=source
    )
    assert reconciliation.association_text_sha256 == source.text_sha256
    expected_keys = {a.facts[0].normalization_key, b.facts[0].normalization_key}
    assert set(reconciliation.accepted_fact_keys) == expected_keys
    result = materialize_page_visual_evidence_sources(
        [a, b], reconciliation, _coverage(reconciliation), association_source=source
    )
    assert len(result.fact_sources) == 1
    fact_source = result.fact_sources[0]
    assert fact_source.normalization_keys == tuple(sorted(expected_keys))
    by_lane = {item.lane: item for item in fact_source.readings}
    assert (
        by_lane[PageReviewLane.MAIN_A].observation.normalization_key
        == a.facts[0].normalization_key
    )
    assert (
        by_lane[PageReviewLane.MAIN_B].observation.normalization_key
        == b.facts[0].normalization_key
    )


def test_association_input_requires_reconciliation_hash_binding():
    a, b = _assoc_pair(
        facts_a=[_assoc_fact("obs-a", "表格第一行")],
        facts_b=[_assoc_fact("obs-b", "血常规栏")],
    )
    source = _assoc_source()
    reconciliation = reconcile_page_reviews(
        [a, b], determination_modes={}, association_source=source
    )
    coverage = _coverage(reconciliation)
    with pytest.raises(PageVisualEvidenceSourceError, match="PageAssociationSource"):
        materialize_page_visual_evidence_sources([a, b], reconciliation, coverage)
    unbound = reconcile_page_reviews([a, b], determination_modes={})
    with pytest.raises(PageVisualEvidenceSourceError, match="association_text_sha256"):
        materialize_page_visual_evidence_sources(
            [a, b], unbound, _coverage(unbound), association_source=source
        )
    other = _assoc_source(text=_ASSOC_TEXT + "另注。")
    with pytest.raises(PageVisualEvidenceSourceError, match="来源关联文本哈希"):
        materialize_page_visual_evidence_sources(
            [a, b], reconciliation, coverage, association_source=other
        )


def test_multi_range_same_value_preserves_exact_source_pairs():
    text = "首日白细胞 4.2 x10^9/L。复查白细胞 4.2 x10^9/L。"
    a, b = _assoc_pair(
        facts_a=[
            _assoc_fact("obs-a1", "初诊栏", excerpt="首日白细胞 4.2 x10^9/L"),
            _assoc_fact("obs-a2", "复查栏", excerpt="复查白细胞 4.2 x10^9/L"),
        ],
        facts_b=[
            _assoc_fact("obs-b1", "血常规一", excerpt="首日白细胞 4.2 x10^9/L"),
            _assoc_fact("obs-b2", "血常规二", excerpt="复查白细胞 4.2 x10^9/L"),
        ],
    )
    source = _assoc_source(text=text)
    reconciliation = reconcile_page_reviews(
        [a, b], determination_modes={}, association_source=source
    )
    assert len(reconciliation.accepted_fact_keys) == 4
    result = materialize_page_visual_evidence_sources(
        [a, b], reconciliation, _coverage(reconciliation), association_source=source
    )
    assert len(result.fact_sources) == 2
    assert {
        tuple(reading.observation.observation_id for reading in fact.readings)
        for fact in result.fact_sources
    } == {("obs-a1", "obs-b1"), ("obs-a2", "obs-b2")}


def test_duplicate_review_identity_is_not_two_sources():
    observation = _fact()
    first = _fact_reading(PageReviewLane.MAIN_A, observation, provider="provider-a")
    second = _fact_reading(PageReviewLane.MAIN_B, observation, provider="provider-b")
    second = second.model_copy(update={"page_review_id": first.page_review_id})
    readings = (first, second)
    values = dict(
        normalization_keys=(observation.normalization_key,),
        normalized_value=observation.normalized_value,
        normalized_unit=observation.normalized_unit,
        readings=readings,
    )
    with pytest.raises(ValidationError, match="不同的页级判读"):
        VisualFactSource(fact_source_id=visual_fact_source_id(**values), **values)


def test_source_level_fields_must_match_readings_even_with_recomputed_id():
    observation = _fact()
    readings = (
        _fact_reading(PageReviewLane.MAIN_A, observation, provider="provider-a"),
        _fact_reading(PageReviewLane.MAIN_B, observation, provider="provider-b"),
    )
    forged_value = "9.9"
    forged_id = visual_fact_source_id(
        normalization_keys=(observation.normalization_key,),
        normalized_value=forged_value,
        normalized_unit=observation.normalized_unit,
        readings=readings,
    )
    with pytest.raises(ValidationError, match="规范值"):
        VisualFactSource(
            fact_source_id=forged_id,
            normalization_keys=(observation.normalization_key,),
            normalized_value=forged_value,
            normalized_unit=observation.normalized_unit,
            readings=readings,
        )
    valid = VisualFactSource(
        fact_source_id=visual_fact_source_id(
            normalization_keys=(observation.normalization_key,),
            normalized_value=observation.normalized_value,
            normalized_unit=observation.normalized_unit,
            readings=readings,
        ),
        normalization_keys=(observation.normalization_key,),
        normalized_value=observation.normalized_value,
        normalized_unit=observation.normalized_unit,
        readings=readings,
    )
    with pytest.raises(ValidationError):
        valid.normalized_value = "1.0"


def test_handwriting_source_level_text_must_match_readings_even_with_recomputed_id():
    observation = _handwriting()
    readings = (
        _handwriting_reading(PageReviewLane.MAIN_A, observation, provider="provider-a"),
        _handwriting_reading(PageReviewLane.MAIN_B, observation, provider="provider-b"),
    )
    forged_text = "cs"
    forged_id = visual_handwriting_source_id(
        kind=observation.kind,
        normalization_key=observation.normalization_key,
        normalized_text=forged_text,
        readings=readings,
    )
    with pytest.raises(ValidationError, match="规范文字"):
        VisualHandwritingSource(
            handwriting_source_id=forged_id,
            kind=observation.kind,
            normalization_key=observation.normalization_key,
            normalized_text=forged_text,
            readings=readings,
        )


def test_locator_must_match_raw_observation_excerpt_and_carry_real_hash():
    observation = _fact()
    with pytest.raises(ValidationError, match="完全一致"):
        _fact_reading(PageReviewLane.MAIN_A, observation, provider="provider-a").__class__(
            lane=PageReviewLane.MAIN_A,
            page_review_id="review-a",
            provider="provider-a",
            model="model-provider-a",
            reasoning_effort="high",
            prompt_version="page-review-r3/v1",
            response_sha256="c" * 64,
            observation=observation,
            locator=VisualPageExcerptLocator(excerpt="别的摘录", excerpt_sha256=_sha256("别的摘录")),
        )
    with pytest.raises(ValidationError, match="真实 sha256"):
        VisualPageExcerptLocator(excerpt="原始资料摘录", excerpt_sha256="0" * 64)


def test_materializer_requires_exactly_two_distinct_main_lanes():
    a, b = _pair()
    stale = PageReconciliation(
        reconciliation_id="page-reconciliation:" + "0" * 32,
        page_artifact_id="page-1",
        clause_pack_sha256="b" * 64,
        page_review_ids=["review-a", "review-b"],
    )
    with pytest.raises(PageVisualEvidenceSourceError, match="两条不同读道"):
        materialize_page_visual_evidence_sources([a, a], stale, _coverage(stale))
    _, single = _pair(b_overrides={"lane": "handwriting-C"})
    with pytest.raises(PageVisualEvidenceSourceError, match="main-A 与 main-B"):
        materialize_page_visual_evidence_sources([a, single], stale, _coverage(stale))
