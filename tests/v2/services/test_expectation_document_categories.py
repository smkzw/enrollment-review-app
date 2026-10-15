"""Document classification is not observation-level clinical judgment evidence."""

from types import SimpleNamespace

import pytest

from app.services import evidence_expectation_projection_service as projection


@pytest.mark.parametrize("document_type, expected", [
    ("investigator_assessment", []), (" INVESTIGATOR_ASSESSMENT ", []),
    ("检验报告", ["检验报告"]), ("病历资料", ["病历资料"]),
])
def test_document_category_never_certifies_written_judgment(monkeypatch, document_type, expected):
    revision = SimpleNamespace(metadata_revision_ids=["metadata"])
    metadata = SimpleNamespace(source_document_version_id="document", document_type=document_type)
    locator = SimpleNamespace(source_document_version_id="document")
    for name, record in (("CompleteEvidenceProcessingRevisionRepository", revision),
                         ("SourceDocumentMetadataRevisionRepository", metadata),
                         ("EvidenceLocatorRepository", locator)):
        monkeypatch.setattr(projection, name,
            lambda session, record=record: SimpleNamespace(get=lambda key: record))
    observations = []
    monkeypatch.setattr(projection, "CoverageObservation",
        lambda **kwargs: observations.append(kwargs) or kwargs)
    fact = SimpleNamespace(fact_id="fact", locator_ids=["locator"])
    projection.EvidenceExpectationProjectionService._observations(
        None, SimpleNamespace(complete_processing_revision_id="revision"), [fact])
    assert observations == [{"fact": fact, "source_types": expected}]


@pytest.mark.parametrize("target, expected", [("白细胞", True), ("另一检查", False)])
@pytest.mark.parametrize("fact_type", ["investigator_assessment", "lab_result"])
def test_accepted_object_bound_annotation_is_rebuilt_before_coverage(monkeypatch, target, expected, fact_type):
    from app.services import page_review_visual_sources
    from app.projections.page_review_visual_locators import project_visual_locators
    from tests.v2.domain.test_page_review_evidence_sources import _pair, _materialize

    group = _materialize(*_pair())
    locator = next(item for item in project_visual_locators(group)
                   if item.target_id == group.handwriting_sources[0].handwriting_source_id)
    revision = SimpleNamespace(metadata_revision_ids=["metadata"])
    metadata = SimpleNamespace(source_document_version_id=locator.source_document_version_id,
                               document_type="lab_report")
    for name, record in (("CompleteEvidenceProcessingRevisionRepository", revision),
                         ("SourceDocumentMetadataRevisionRepository", metadata),
                         ("EvidenceLocatorRepository", locator)):
        monkeypatch.setattr(projection, name,
            lambda session, record=record: SimpleNamespace(get=lambda key: record))
    calls = []
    monkeypatch.setattr(page_review_visual_sources, "rebuild_visual_sources",
        lambda session, authority, coverage_id: calls.append(coverage_id) or (group,))
    monkeypatch.setattr(projection, "CoverageObservation", lambda **kwargs: kwargs)
    fact = SimpleNamespace(fact_id="fact", locator_ids=[locator.locator_id],
                           fact_type=fact_type,
                           asserted_object=target, supported_requirement_ids=["requirement"])
    result = projection.EvidenceExpectationProjectionService._observations(
        None, SimpleNamespace(complete_processing_revision_id="revision"), [fact])
    assert calls == ([group.coverage_id] if fact_type == "investigator_assessment" else [])
    assert ("investigator_assessment" in result[0]["source_types"]) is (expected and fact_type == "investigator_assessment")
