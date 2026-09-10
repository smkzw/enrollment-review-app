import pytest

from app.domain.contracts.page_review import HandwritingKind, HandwritingObservation
from app.domain.page_normalization import handwriting_normalization_key
from app.projections.written_judgment_evidence import written_judgment_locator_ids
from app.projections.page_review_visual_locators import project_visual_locators
from tests.v2.domain.test_page_review_contracts import _handwriting
from tests.v2.domain.test_page_review_evidence_sources import _materialize, _pair


def test_only_exact_accepted_annotation_locators_cover_the_object():
    source = _materialize(*_pair())
    actual = written_judgment_locator_ids(source, asserted_object="白细胞")
    assert len(actual) == 2
    assert actual == frozenset(
        item.locator_id for item in project_visual_locators(source)
        if item.target_id == source.handwriting_sources[0].handwriting_source_id
    )


@pytest.mark.parametrize("target", ["", "另一检查", "检验报告"])
def test_no_same_page_or_generic_object_propagation(target):
    assert not written_judgment_locator_ids(_materialize(*_pair()), asserted_object=target)


def test_single_read_and_conflict_are_not_written_judgment_proof():
    source = _materialize(*_pair(b_overrides={"handwriting": []}))
    assert not written_judgment_locator_ids(source, asserted_object="白细胞")


@pytest.mark.parametrize("kind", [HandwritingKind.NOTE, HandwritingKind.OTHER])
def test_generic_note_is_not_a_clinical_meaning_assessment(kind):
    item = _handwriting().model_dump()
    item["kind"] = kind
    item["normalization_key"], item["normalized_text"] = handwriting_normalization_key(
        kind.value, item["raw_text"], context=item["context"],
    )
    note = HandwritingObservation.model_validate(item)
    source = _materialize(*_pair({"handwriting": [note]}, {"handwriting": [note]}))
    assert not written_judgment_locator_ids(source, asserted_object="白细胞")
