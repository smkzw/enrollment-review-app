"""R3 视觉定位纯投影与类型化视觉溯源绑定测试（合成夹具，不触真实资料）。"""

from __future__ import annotations

import copy
import hashlib

import pytest
from pydantic import ValidationError

from app.domain.contracts.evidence import BoundingBox
from app.domain.contracts.evidence_locator import (
    EvidenceLocatorArtifact,
    PageReviewVisualProvenance,
    locator_anchor_hash,
)
from app.domain.contracts.enums import DisambiguationOutcome, LocatorPrecision
from app.domain.contracts.ocr import CoordinateFrame
from app.domain.contracts.page_review import (
    PageCoverageEntry,
    PageDisposition,
    PageReviewRecord,
    SubjectPageCoverage,
)
from app.domain.page_reconciliation import reconcile_page_reviews
from app.domain.page_review_evidence_sources import (
    PageVisualEvidenceSourceSet,
    materialize_page_visual_evidence_sources,
)
from app.projections.page_review_visual_locators import (
    VISUAL_LOCATOR_DEGRADATION_REASON,
    project_visual_locators,
    visual_locator_id,
)
from tests.v2.domain.test_page_review_contracts import _fact, _review_payload

_SHA = "a" * 64


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


def _coverage(reconciliation) -> SubjectPageCoverage:
    entry = PageCoverageEntry(
        page_artifact_id="page-1",
        source_document_version_id="document-1",
        page_number=1,
        disposition=PageDisposition.ACCEPTED,
        reconciliation_id=reconciliation.reconciliation_id,
    )
    return SubjectPageCoverage(
        coverage_id="coverage-1",
        subject_id="subject-1",
        review_episode_id="episode-1",
        evidence_snapshot_id="snapshot-1",
        evidence_processing_revision_id="revision-1",
        clause_pack_sha256="b" * 64,
        expected_page_artifact_ids=[entry.page_artifact_id],
        entries=[entry],
    )


def _source_set(**kwargs) -> PageVisualEvidenceSourceSet:
    a, b = _pair(kwargs.pop("a_overrides", None), kwargs.pop("b_overrides", None))
    reconciliation = kwargs.pop("reconciliation", None) or reconcile_page_reviews(
        [a, b], determination_modes={}
    )
    return materialize_page_visual_evidence_sources(
        [a, b],
        reconciliation,
        kwargs.pop("coverage", None) or _coverage(reconciliation),
        **kwargs,
    )


def _visual_locator() -> EvidenceLocatorArtifact:
    return project_visual_locators(_source_set())[0]


# --------------------------------------------------------------------------- 既有文本层不变


def test_text_layer_locator_serialization_unchanged():
    """新增可选字段在缺省时不得出现在旧定位的序列化里。"""
    artifact = EvidenceLocatorArtifact(
        locator_id="loc-1",
        page_artifact_id="pa-1",
        ocr_page_id="ocr-1",
        source_document_version_id="doc-1",
        page_number=1,
        source_layer="raw_ocr",
        source_text_sha256=_sha256("12345"),
        target_id="target-1",
        precision="text_range",
        text_start=0,
        text_end=5,
        excerpt="12345",
        disambiguation="unique_match",
        locator_algorithm_version="v1",
        authenticity="degraded",
        degradation_reason="text-only 路线无真实坐标",
        created_at="2026-09-09T00:00:00Z",
    )
    dumped = artifact.model_dump()
    assert "page_review_visual" not in dumped
    assert "page_review_visual" not in artifact.model_dump_json()
    assert EvidenceLocatorArtifact.model_validate(dumped) == artifact


# --------------------------------------------------------------------------- 层与溯源绑定的互斥/必带


def test_visual_layer_without_provenance_is_rejected():
    data = _visual_locator().model_dump()
    data.pop("page_review_visual")
    with pytest.raises(ValidationError, match="视觉溯源绑定"):
        EvidenceLocatorArtifact.model_validate(data)


def test_provenance_on_text_layer_is_rejected():
    data = _visual_locator().model_dump()
    data.update(
        source_layer="raw_ocr",
        precision="text_range",
        text_start=0,
        text_end=5,
    )
    with pytest.raises(ValidationError, match="不能携带视觉溯源绑定"):
        EvidenceLocatorArtifact.model_validate(data)


# --------------------------------------------------------------------------- 哈希与目标绑定


def test_excerpt_hash_tampering_rejected_even_with_recomputed_anchor():
    original = _visual_locator()
    tampered = original.model_dump()
    tampered["source_text_sha256"] = "f" * 64
    with pytest.raises(ValidationError, match="摘录和消歧结果确定性计算"):
        EvidenceLocatorArtifact.model_validate(tampered)
    tampered["anchor_hash"] = locator_anchor_hash(
        page_artifact_id=tampered["page_artifact_id"],
        source_layer=tampered["source_layer"],
        source_text_sha256=tampered["source_text_sha256"],
        precision=LocatorPrecision.PAGE_EXCERPT,
        target_id=tampered["target_id"],
        excerpt=tampered["excerpt"],
        disambiguation=DisambiguationOutcome.UNIQUE_MATCH,
        degradation_reason=tampered["degradation_reason"],
    )
    with pytest.raises(ValidationError, match="真实 sha256"):
        EvidenceLocatorArtifact.model_validate(tampered)


def test_provenance_target_must_agree_with_locator_target():
    data = _visual_locator().model_dump()
    data["page_review_visual"]["source_target_id"] = "visual-fact:" + "0" * 32
    with pytest.raises(ValidationError, match="来源目标必须与定位目标一致"):
        EvidenceLocatorArtifact.model_validate(data)


def test_image_hash_never_enters_text_hash_and_binding_stays_separate():
    for locator in project_visual_locators(_source_set()):
        assert locator.source_text_sha256 == _sha256(locator.excerpt)
        assert locator.source_text_sha256 != locator.page_review_visual.page_image_sha256


# --------------------------------------------------------------------------- 视觉层禁带项


@pytest.mark.parametrize(
    "field,value",
    [
        ("bbox", BoundingBox(x0=0, y0=0, x1=10, y1=10)),
        ("coordinate_frame", CoordinateFrame(
            space="pdf_points", page_width=595.0, page_height=842.0,
            rotation=0, transform_version="t/v1",
        )),
        ("sidecar_sha256", _SHA),
        ("ocr_page_id", "ocr-1"),
        ("text_start", 0),
        ("text_end", 5),
        ("match_confidence", 1.0),
        ("processing_revision_id", "revision-x"),
        ("effective_text_sha256", _SHA),
    ],
)
def test_visual_layer_rejects_bbox_ocr_sidecar_ranges_and_fiction(field, value):
    data = _visual_locator().model_dump()
    data[field] = value
    with pytest.raises(ValidationError):
        EvidenceLocatorArtifact.model_validate(data)


def test_visual_layer_rejects_non_degraded_and_non_chinese_reason():
    data = _visual_locator().model_dump()
    data["authenticity"] = "rejected"
    with pytest.raises(ValidationError, match="诚实降级"):
        EvidenceLocatorArtifact.model_validate(data)
    data = _visual_locator().model_dump()
    data["degradation_reason"] = "no real coordinates available"
    with pytest.raises(ValidationError, match="中文降级原因"):
        EvidenceLocatorArtifact.model_validate(data)


# --------------------------------------------------------------------------- 纯投影行为


def test_projection_covers_both_readers_with_distinct_ids_and_provenance():
    source_set = _source_set()
    locators = project_visual_locators(source_set)

    # 1 个事实来源 + 1 个手写来源，每个来源两条主读读道 → 4 个定位。
    assert len(source_set.fact_sources) == 1
    assert len(source_set.handwriting_sources) == 1
    assert len(locators) == 4
    assert len({item.locator_id for item in locators}) == len(locators)

    fact_target = source_set.fact_sources[0].fact_source_id
    fact_locators = [item for item in locators if item.target_id == fact_target]
    assert {item.page_review_visual.page_review_id for item in fact_locators} == {
        "review-a",
        "review-b",
    }
    by_review = {item.page_review_visual.page_review_id: item for item in fact_locators}
    assert by_review["review-a"].page_review_visual.source_set_id == source_set.source_set_id
    assert by_review["review-a"].page_review_visual.coverage_id == source_set.coverage_id
    assert (
        by_review["review-a"].page_review_visual.processing_revision_id
        == source_set.evidence_processing_revision_id
    )
    assert by_review["review-a"].page_review_visual.source_target_id == fact_target
    assert by_review["review-a"].page_review_visual.page_image_sha256 == source_set.page_image_sha256

    for locator in locators:
        assert locator.source_layer.value == "page_review_visual"
        assert locator.precision == LocatorPrecision.PAGE_EXCERPT
        assert locator.authenticity.value == "degraded"
        assert locator.degradation_reason == VISUAL_LOCATOR_DEGRADATION_REASON
        assert locator.bbox is None and locator.coordinate_frame is None
        assert locator.ocr_page_id is None and locator.match_confidence is None
        assert locator.created_at == source_set.created_at
        assert "page_review_visual" in locator.model_dump()
        assert locator.anchor_hash == locator_anchor_hash(
            page_artifact_id=locator.page_artifact_id,
            source_layer=locator.source_layer,
            source_text_sha256=locator.source_text_sha256,
            precision=locator.precision,
            target_id=locator.target_id,
            excerpt=locator.excerpt,
            disambiguation=locator.disambiguation,
            degradation_reason=locator.degradation_reason,
        )


def test_projection_keeps_both_differing_excerpts_verbatim():
    excerpt_b = "白细胞 4.2↑（手写补记）…"
    source_set = _source_set(b_overrides={"facts": [
        {**_fact().model_dump(), "region": {"excerpt": excerpt_b}},
    ]})
    locators = project_visual_locators(source_set)
    fact_target = source_set.fact_sources[0].fact_source_id
    excerpts = sorted(item.excerpt for item in locators if item.target_id == fact_target)
    assert excerpts == sorted(["原始资料摘录", excerpt_b])
    for locator in locators:
        assert locator.source_text_sha256 == _sha256(locator.excerpt)


def test_projection_identity_is_deterministic_and_input_stays_unmutated():
    source_set = _source_set()
    before = copy.deepcopy(source_set.model_dump())
    first = project_visual_locators(source_set)
    second = project_visual_locators(source_set)
    assert [item.model_dump() for item in first] == [item.model_dump() for item in second]
    rebuilt = project_visual_locators(
        PageVisualEvidenceSourceSet.model_validate(source_set.model_dump())
    )
    assert [item.model_dump() for item in first] == [item.model_dump() for item in rebuilt]
    assert source_set.model_dump() == before


def test_locator_id_includes_source_set_target_reading_and_excerpt_hash():
    source_set = _source_set()
    fact = source_set.fact_sources[0]
    reading = fact.readings[0]
    excerpt_sha = _sha256(reading.observation.region.excerpt)
    assert any(
        locator.locator_id
        == visual_locator_id(
            source_set_id=source_set.source_set_id,
            source_target_id=fact.fact_source_id,
            page_review_id=reading.page_review_id,
            excerpt_sha256=excerpt_sha,
        )
        for locator in project_visual_locators(source_set)
    )
    assert visual_locator_id(
        source_set_id=source_set.source_set_id,
        source_target_id=fact.fact_source_id,
        page_review_id=reading.page_review_id,
        excerpt_sha256=excerpt_sha,
    ) != visual_locator_id(
        source_set_id=source_set.source_set_id,
        source_target_id=fact.fact_source_id,
        page_review_id="review-b",
        excerpt_sha256=excerpt_sha,
    )


def test_handwriting_sources_project_their_own_locators():
    source_set = _source_set()
    assert {
        locator.target_id for locator in project_visual_locators(source_set)
    } == {item.handwriting_source_id for item in source_set.handwriting_sources} | {
        item.fact_source_id for item in source_set.fact_sources
    }


def test_empty_source_set_yields_no_locators():
    clause_only = {
        **_review_payload(),
        "facts": [],
        "handwriting": [],
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
    source_set = materialize_page_visual_evidence_sources(
        [a, b], reconciliation, _coverage(reconciliation)
    )
    assert source_set.fact_sources == () and source_set.handwriting_sources == ()
    assert project_visual_locators(source_set) == ()


def test_projection_revalidates_mutated_input_via_dump():
    """上游合同未冻结：model_copy 改写可绕过验证器，投影入口按 dump 重验证兜底。"""
    source_set = _source_set()
    poisoned = source_set.model_copy(update={"page_image_sha256": "f" * 64})
    with pytest.raises(ValidationError):
        project_visual_locators(poisoned)
