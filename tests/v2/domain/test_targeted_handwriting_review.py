from types import SimpleNamespace

import pytest

from app.domain.targeted_handwriting_review import (
    compare_handwriting_reads, handwriting_needs_review, pending_handwriting_excerpts,
)
from app.domain.contracts.page_review import PageReviewLane
from tests.v2.domain.test_page_review_contracts import _handwriting


def _pair(left, right):
    return [
        SimpleNamespace(lane=lane, handwriting=items, page_artifact_id="page",
                        page_image_sha256="a" * 64, source_document_version_id="doc",
                        page_number=1, clause_pack_sha256="b" * 64)
        for lane, items in zip((PageReviewLane.MAIN_A, PageReviewLane.MAIN_B), (left, right))
    ]


def test_two_empty_readings_are_not_proof_of_missing_judgment():
    pair = _pair([], [])
    assert not handwriting_needs_review(pair)
    assert not compare_handwriting_reads(pair)


def test_one_reader_omission_enters_review():
    pair = _pair([_handwriting()], [])
    assert handwriting_needs_review(pair)
    assert not compare_handwriting_reads(pair)


def test_matching_nonempty_owned_notes_are_candidates_only():
    pair = _pair([_handwriting()], [_handwriting()])
    assert not handwriting_needs_review(pair)
    assert compare_handwriting_reads(pair)


def test_same_text_without_target_remains_unverified():
    note = _handwriting().model_copy(update={"context": None})
    pair = _pair([note], [note])
    assert handwriting_needs_review(pair)
    assert not compare_handwriting_reads(pair)


def test_multiplicity_cannot_be_collapsed():
    pair = _pair([_handwriting(), _handwriting()], [_handwriting()])
    assert handwriting_needs_review(pair)
    assert not compare_handwriting_reads(pair)


def test_other_page_is_rejected():
    pair = _pair([_handwriting()], [_handwriting()])
    pair[1].page_number = 2
    with pytest.raises(ValueError):
        handwriting_needs_review(pair)


def test_equal_text_with_different_source_excerpt_is_not_agreement():
    from app.domain.contracts.page_review import PageRegion
    note = _handwriting()
    other = note.model_copy(update={"region": PageRegion(excerpt="另一处原文")})
    pair = _pair([note], [other])
    assert handwriting_needs_review(pair)
    assert not compare_handwriting_reads(pair)
    assert pending_handwriting_excerpts(pair) == (note.region.excerpt, "另一处原文")


def test_second_round_excludes_already_matching_notes():
    from app.domain.contracts.page_review import PageRegion
    note = _handwriting()
    extra = note.model_copy(update={"region": PageRegion(excerpt="待核实原文")})
    pair = _pair([note, extra], [note])
    assert pending_handwriting_excerpts(pair) == ("待核实原文",)
