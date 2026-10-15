from datetime import UTC, datetime
import hashlib

import pytest

from app.domain.contracts.evidence_normalizer import (
    EvidenceNormalizerOutput, EvidenceNormalizerInput, EvidenceNormalizerLocatorInput,
    EvidenceNormalizerPageInput, evidence_normalizer_input_scope_hash,
)
from app.domain.contracts.enums import FactPolarity, LocatorPrecision, LocatorSourceLayer
from app.domain.contracts.facts import AssertionBasis, ClinicalFactCandidateV2
from app.projections.normalizer_text_accounting import (
    UNACCOUNTED_TEXT_CODE, unaccounted_source_text, validate_text_accounting_items,
)
from tests.v2.agents.test_evidence_normalizer_adapter import _input


def freeze(text, *, localized=None, layer=LocatorSourceLayer.EFFECTIVE_TEXT, precision=LocatorPrecision.TEXT_RANGE):
    original = _input()
    digest = hashlib.sha256(text.encode()).hexdigest()
    page = EvidenceNormalizerPageInput(source_document_version_id="docv-A", page_artifact_id="page-1",
        page_number=1, effective_text=text, effective_text_sha256=digest, locator_ids=["loc-1"])
    locator = EvidenceNormalizerLocatorInput(locator_id="loc-1", page_number=1,
        source_layer=layer, precision=precision, source_text_sha256=digest,
        localized_text=None if precision == LocatorPrecision.PAGE_ONLY else (localized or text))
    values = original.model_dump()
    values.update(pages=[page], page_numbers=[1], available_locator_ids=["loc-1"], available_locators=[locator])
    values["input_scope_sha256"] = evidence_normalizer_input_scope_hash(
        authority=original.authority, logical_document_id=original.logical_document_id,
        manifest_sha256=original.manifest_sha256, context=original.context, related_requirements=[],
        completion_manifest_sha256=original.completion_manifest_sha256,
        page_numbers=[1], pages=[page], available_locator_ids=["loc-1"], available_locators=[locator])
    return EvidenceNormalizerInput.model_validate(values)


def proposal(evidence, quote=None):
    facts = []
    if quote:
        facts.append(ClinicalFactCandidateV2(candidate_id="f1", run_id=evidence.run_id,
            call_id=evidence.call_id, fact_type="recorded_finding", polarity=FactPolarity.AFFIRMED,
            asserted_object=quote, raw_value=quote, canonical_value=quote, locator_ids=["loc-1"],
            candidate_source_semantics="同期客观结果", model_uncertainty=0, created_at=datetime.now(UTC),
            assertion_basis=AssertionBasis(asserted_object=quote, assertion_text=quote, locator_id="loc-1",
                source_text_sha256=evidence.pages[0].effective_text_sha256)))
    return EvidenceNormalizerOutput(run_id=evidence.run_id, call_id=evidence.call_id,
        logical_document_id=evidence.logical_document_id, page_numbers=[1], fact_candidates=facts)


def test_whole_paragraph_locator_does_not_cover_unquoted_siblings():
    evidence = freeze("部位甲检查未做；项目乙为7单位；部位丙局部未及")
    items = unaccounted_source_text(evidence, proposal(evidence, "项目乙为7单位"))
    assert len(items) == 2
    assert "部位甲" in items[0].source_text_range.excerpt
    assert "部位丙" in items[1].source_text_range.excerpt
    assert all(item.gap_type is None and not item.affected_requirement_ids for item in items)
    validate_text_accounting_items(evidence, items)


@pytest.mark.parametrize("text", ["甲未做\n乙已做", "甲未做；乙已做", "甲未做  乙已做"])
def test_layout_variants_keep_missing_text_without_semantic_segmentation(text):
    evidence = freeze(text)
    items = unaccounted_source_text(evidence, proposal(evidence, "乙已做"))
    assert any("甲未做" in item.source_text_range.excerpt for item in items)


def test_complete_quote_is_accounted_not_certified():
    evidence = freeze("甲未做；乙已做")
    assert unaccounted_source_text(evidence, proposal(evidence, "甲未做；乙已做")) == []
    assert evidence.pages[0].effective_text == "甲未做；乙已做"


@pytest.mark.parametrize("text,localized,quote", [
    ("阴性\n阴性", "阴性", "阴性"),
    ("甲阴性、乙阴性", "甲阴性、乙阴性", "阴性"),
    ("甲未做", "甲未做", "甲 未做"),
])
def test_repeated_or_normalized_quote_does_not_borrow_position(text, localized, quote):
    evidence = freeze(text, localized=localized)
    assert unaccounted_source_text(evidence, proposal(evidence, quote))


def test_page_only_and_corrected_ocr_are_not_text_position_proofs():
    evidence = freeze("甲未做", precision=LocatorPrecision.PAGE_ONLY)
    assert unaccounted_source_text(evidence, proposal(evidence, "甲未做"))
    evidence = freeze("甲未做", layer=LocatorSourceLayer.RAW_OCR)
    evidence = evidence.model_copy(update={"available_locators": [evidence.available_locators[0].model_copy(
        update={"source_text_sha256": "a" * 64})]})
    assert unaccounted_source_text(evidence, proposal(evidence, "甲未做"))


def test_text_disposition_cannot_certify_visual_or_handwriting_coverage():
    evidence = freeze("甲未做")
    locator = evidence.available_locators[0].model_copy(update={"source_layer": LocatorSourceLayer.PAGE_REVIEW_VISUAL})
    evidence = evidence.model_copy(update={"available_locators": [locator]})
    assert unaccounted_source_text(evidence, proposal(evidence, "甲未做"))


def test_metadata_is_retained_not_declared_a_missing_procedure():
    evidence = freeze("页眉\n甲未做")
    items = unaccounted_source_text(evidence, proposal(evidence, "甲未做"))
    assert items[0].source_text_range.excerpt == "页眉\n"
    assert "不代表患者缺少检查" in items[0].reason
    assert items[0].code == UNACCOUNTED_TEXT_CODE


def test_no_threshold_silently_discards_short_or_many_lines():
    evidence = freeze("\n".join(str(index) for index in range(250)))
    assert len(unaccounted_source_text(evidence, proposal(evidence))) == 250


def test_stale_source_range_and_author_owned_coverage_are_rejected():
    evidence = freeze("甲未做")
    output = proposal(evidence)
    items = unaccounted_source_text(evidence, output)
    stale = items[0].model_copy(update={"source_text_range": items[0].source_text_range.model_copy(
        update={"effective_text_sha256": "a" * 64})})
    with pytest.raises(ValueError, match="冻结原文"):
        validate_text_accounting_items(evidence, [stale])
    with pytest.raises(ValueError, match="系统"):
        unaccounted_source_text(evidence, output.model_copy(update={"unresolved_items": items}))
