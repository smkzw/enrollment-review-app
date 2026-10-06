"""Synthetic source integration, not clinical validation or automatic adoption."""
import base64
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from app.domain.contracts.enums import GateOutcome, LocatorAuthenticity, LocatorPrecision
from app.domain.contracts.evidence import BoundingBox
from app.domain.contracts.local_region_read import LocalRegionRelativeBox
from app.evidence.local_region_position_trial import proposed_field_bbox
from app.evidence.reading_view import make_reading_region, make_reading_view
from app.services.local_region_source_link import link_local_region_trial_to_text
from app.storage.evidence_locator_repositories import (
    CompleteEvidenceProcessingRevisionRepository, EvidenceLocatorRepository,
)
from tests.v2.services.test_local_region_comparison import frozen_trial, _put


def _subreads(store, trial, visual, parent_request):
    source = trial["source_region"]["reading_view"]
    view = make_reading_view(
        store.read_by_sha("page_image", source["source_image_sha256"]),
        source_page_artifact_id=source["source_page_artifact_id"],
        source_image_sha256=source["source_image_sha256"], clockwise_degrees=0,
    )
    reads = []
    for index, item in enumerate(visual["structured_read"]["items"]):
        field = make_reading_region(view, proposed_field_bbox(
            BoundingBox.model_validate(trial["source_region"]["view_bbox"]),
            LocalRegionRelativeBox.model_validate(item["proposed_bbox"]),
        ))
        request = deepcopy(parent_request)
        request["page"]["page_input_sha256"] = field.identity()["region_image_sha256"]
        request["image"].update(sha256=field.identity()["region_image_sha256"],
                                data_base64=base64.b64encode(field.image_bytes).decode())
        response = {"model": request["model_id"], "choices": [{
            "finish_reason": "stop", "message": {"content": item["excerpt"]},
        }]}
        reads.append({"item_index": index, "source_region": field.identity(),
                      "image_ref": store.put("reading_view_image", field.image_bytes).storage_ref,
                      "ocr_request_ref": _put(store, request, "raw_request"),
                      "ocr": {"status": "read", "text": item["excerpt"],
                              "response_ref": _put(store, response, "raw_response")}})
    return reads


@pytest.mark.parametrize("frozen_trial", [{
    "read_format": "localized_candidate", "focus": True, "complete": True,
    "raw_text": "报告正文\n年龄：50岁\n其他资料",
}], indirect=True)
def test_saved_text_locator_enters_new_complete_revision_not_old_or_fact_approval(
    frozen_trial, session_factory, monkeypatch,
):
    from app.domain.gates.fact_evidence_closure import validate_locator_and_text_hash
    from app.services.evidence_revision_workflow import EvidenceRevisionBuildRequest, EvidenceRevisionWorkflow

    store, trial, visual, parent_request, _ = frozen_trial
    reads = _subreads(store, trial, visual, parent_request)
    def forbidden(*args, **kwargs):
        raise AssertionError("source linking must not request a new model reading")
    monkeypatch.setattr("app.llm.independent_vlm.independent_vlm_page_chat", forbidden)
    trial_ref = _put(store, trial)
    original = store.read(trial_ref)
    result_ref = link_local_region_trial_to_text(store, trial_ref, reads, session_factory=session_factory, focused=True)
    result = json.loads(store.read(result_ref.storage_ref))
    assert result["items"][0]["status"] == "text_linked_candidate"
    assert not result["source_position_verified"] and not result["formal_adoption_authorized"]
    lid = result["items"][0]["locator_id"]
    with session_factory() as session:
        locator = EvidenceLocatorRepository(session, store).get(lid)
        old = CompleteEvidenceProcessingRevisionRepository(session, store).get(result["evidence_processing_revision_id"])
        old_json = old.model_dump_json()
        assert locator.precision == LocatorPrecision.TEXT_RANGE
        assert locator.authenticity == LocatorAuthenticity.DEGRADED and locator.bbox is None
        assert locator.excerpt == "年龄：50岁" and locator.text_start == len("报告正文\n")
        assert validate_locator_and_text_hash(session, SimpleNamespace(locator_ids=[lid]), old)[0] == GateOutcome.REJECTED
    workflow = EvidenceRevisionWorkflow(session_factory, store)
    candidate = workflow.start(EvidenceRevisionBuildRequest(
        evidence_snapshot_id=old.evidence_snapshot_id, base_processing_revision_id=old.base_processing_revision_id,
        project_id=old.project_id, subject_id=old.subject_id, review_episode_id=old.review_episode_id,
        expected_revision=1, idempotency_key="synthetic-linked-source", created_by="synthetic-reviewer",
        selected_locator_ids=[lid],
    ))
    built = workflow.run_build(candidate.candidate_id)
    with session_factory() as session:
        complete = CompleteEvidenceProcessingRevisionRepository(session, store).get(built.complete_revision_id)
        assert validate_locator_and_text_hash(session, SimpleNamespace(locator_ids=[lid]), complete)[0] == GateOutcome.ACCEPTED
        assert CompleteEvidenceProcessingRevisionRepository(session, store).get(old.evidence_processing_revision_id).model_dump_json() == old_json
    from app.domain.contracts.enums import LocatorSourceLayer
    from app.domain.contracts.evidence_locator import SOURCE_LINE_TARGET_PREFIX
    from app.services.evidence_locator_service import EvidenceLocatorService, LocatorRequest
    from app.storage.evidence_locator_repositories import RevisionClosureError

    later = EvidenceLocatorService(session_factory, store).create_locator(LocatorRequest(
        page_artifact_id=locator.page_artifact_id, ocr_page_id=locator.ocr_page_id,
        source_layer=LocatorSourceLayer.RAW_OCR, source_text_sha256=locator.source_text_sha256,
        target_id=SOURCE_LINE_TARGET_PREFIX + "later-synthetic-line", excerpt="其他资料",
    ))
    with session_factory() as session:
        repo = CompleteEvidenceProcessingRevisionRepository(session, store)
        assert repo.get(old.evidence_processing_revision_id).model_dump_json() == old_json
        assert later.locator_id not in repo.get(complete.evidence_processing_revision_id).locator_ids
        with pytest.raises(RevisionClosureError, match="定位集合"):
            repo._verify_candidate_binding(
                old.model_copy(update={"locator_ids": sorted([*old.locator_ids, lid])}),
                require_processing=False, require_current_locators=False,
            )
    assert store.read(trial_ref) == original
    assert link_local_region_trial_to_text(store, trial_ref, reads, session_factory=session_factory, focused=True).storage_ref == result_ref.storage_ref


@pytest.mark.parametrize("frozen_trial", [
    {"read_format": "localized_candidate", "focus": True, "raw_text": text}
    for text in ("年龄：51岁", "50岁", "年龄：50岁\n年龄：50岁", "年龄:50岁")
], indirect=True)
def test_missing_conflicting_repeated_or_reconstructed_field_is_not_a_text_anchor(
    frozen_trial, session_factory,
):
    store, trial, visual, parent_request, _ = frozen_trial
    result = json.loads(store.read(link_local_region_trial_to_text(
        store, _put(store, trial), _subreads(store, trial, visual, parent_request),
        session_factory=session_factory, focused=True,
    ).storage_ref))
    assert result["items"][0]["status"] == "unresolved" and result["items"][0]["locator_id"] is None


@pytest.mark.parametrize("frozen_trial", [{
    "read_format": "localized_candidate", "focus": True, "complete": True,
    "raw_text": "报告正文\n1 CODE ★示例项目 4.04 3.50--9.50 10^9/L\n其他资料",
    "plain_row": True,
}], indirect=True)
def test_headerless_literal_row_can_navigate_source_without_verifying_field_assignment(
    frozen_trial, session_factory,
):
    store, trial, visual, parent_request, _ = frozen_trial
    trial_ref = _put(store, trial)
    original = store.read(trial_ref)
    result = json.loads(store.read(link_local_region_trial_to_text(
        store, trial_ref, _subreads(store, trial, visual, parent_request),
        session_factory=session_factory, focused=True,
    ).storage_ref))
    item = result["items"][0]
    assert item["status"] == "transcript_navigation_candidate"
    assert item["reasons"] and not item["field_assignment_verified"]
    assert not item["source_position_verified"] and not item["formal_adoption_authorized"]
    comparison = json.loads(store.read(result["comparison_ref"]))
    assert comparison["items"][0]["literal_crop_transcription_agreement"]
    assert not comparison["items"][0]["single_field_transcription_agreement"]
    with session_factory() as session:
        locator = EvidenceLocatorRepository(session, store).get(item["locator_id"])
        assert locator.target_id.startswith("local-transcript:")
        assert locator.authenticity == LocatorAuthenticity.DEGRADED and locator.bbox is None
        assert locator.excerpt == "1 CODE ★示例项目 4.04 3.50--9.50 10^9/L"
        assert "仅用于寻找对应原文" in locator.degradation_reason
        assert locator.text_start == len("报告正文\n")
        old = CompleteEvidenceProcessingRevisionRepository(session, store).get(result["evidence_processing_revision_id"])
        old_json = old.model_dump_json()
    from app.domain.gates.fact_evidence_closure import validate_locator_and_text_hash
    from app.services.evidence_revision_workflow import EvidenceRevisionBuildRequest, EvidenceRevisionWorkflow

    workflow = EvidenceRevisionWorkflow(session_factory, store)
    candidate = workflow.start(EvidenceRevisionBuildRequest(
        evidence_snapshot_id=old.evidence_snapshot_id, base_processing_revision_id=old.base_processing_revision_id,
        project_id=old.project_id, subject_id=old.subject_id, review_episode_id=old.review_episode_id,
        expected_revision=1, idempotency_key="transcript-navigation-only", created_by="synthetic-reviewer",
        selected_locator_ids=[locator.locator_id],
    ))
    built = workflow.run_build(candidate.candidate_id)
    with session_factory() as session:
        complete = CompleteEvidenceProcessingRevisionRepository(session, store).get(built.complete_revision_id)
        assert locator.locator_id in complete.locator_ids
        outcome, reasons, affected = validate_locator_and_text_hash(
            session, SimpleNamespace(locator_ids=[locator.locator_id]), complete,
        )
        assert outcome == GateOutcome.REJECTED and affected == [locator.locator_id]
        assert any("仅供原文导航" in reason for reason in reasons)
        assert CompleteEvidenceProcessingRevisionRepository(session, store).get(old.evidence_processing_revision_id).model_dump_json() == old_json
    assert store.read(trial_ref) == original


@pytest.mark.parametrize("frozen_trial", [{
    "read_format": "localized_candidate", "focus": True, "complete": True, "plain_row": True,
    "raw_text": text,
} for text in (
    "1 CODE ★示例项目 4.04\n3.50--9.50 10^9/L",
    "1 CODE ★示例项目 4.04\u2028 3.50--9.50 10^9/L",
    "1 CODE ★示例项目 4.04\v 3.50--9.50 10^9/L",
    "1 CODE ★示例项目 4.04 3.50--9.50 10^9/L\n1 CODE ★示例项目 4.04 3.50--9.50 10^9/L",
    "11 CODE ★示例项目 4.04 3.50--9.50 10^9/L",
    "1 CODE ★示例项目 4.04 3.50--9.50 10^9/L2",
)], indirect=True)
def test_literal_navigation_does_not_join_rows_or_choose_ambiguous_partial_quote(
    frozen_trial, session_factory,
):
    store, trial, visual, parent_request, _ = frozen_trial
    result = json.loads(store.read(link_local_region_trial_to_text(
        store, _put(store, trial), _subreads(store, trial, visual, parent_request),
        session_factory=session_factory, focused=True,
    ).storage_ref))
    assert result["items"][0]["status"] == "unresolved"
    assert result["items"][0]["locator_id"] is None
    assert not result["items"][0]["field_assignment_verified"]


@pytest.mark.parametrize("frozen_trial", [{
    "read_format": "localized_candidate", "focus": True,
    "raw_text": "年龄：50岁\n体温：37℃", "two_items": True,
}], indirect=True)
def test_failed_subread_keeps_only_successful_source_link(frozen_trial, session_factory):
    store, trial, visual, parent_request, _ = frozen_trial
    reads = _subreads(store, trial, visual, parent_request)
    response = json.loads(store.read(reads[0]["ocr"]["response_ref"]))
    response["choices"][0]["finish_reason"] = "length"
    reads[0]["ocr"]["response_ref"] = _put(store, response, "raw_response")
    result = json.loads(store.read(link_local_region_trial_to_text(
        store, _put(store, trial), reads, session_factory=session_factory, focused=True,
    ).storage_ref))
    assert result["items"][0]["locator_id"] is None
    assert result["items"][1]["status"] == "text_linked_candidate"
    assert "患者资料缺失" in result["items"][0]["reasons"][0]
    assert not result["formal_adoption_authorized"]


@pytest.mark.parametrize("frozen_trial", [{
    "read_format": "localized_candidate", "focus": True, "raw_text": "年龄：50岁",
}], indirect=True)
def test_source_link_does_not_resolve_blocking_risk_or_approve_fact(frozen_trial, session_factory):
    from app.services.evidence_revision_workflow import (
        BuildNeedsAttentionError, EvidenceRevisionBuildRequest, EvidenceRevisionWorkflow,
    )
    from app.storage.evidence_locator_models import OCRRiskReviewRecord
    from app.storage.ocr_repositories import EvidenceProcessingRevisionRepository
    from app.domain.contracts.evidence_ingestion import SourceDocumentMetadataRevision
    from app.storage.evidence_repositories import SourceDocumentMetadataRevisionRepository
    from tests.v2.storage.test_ocr_repositories import FIXED_UTC

    store, trial, visual, parent_request, _ = frozen_trial
    result = json.loads(store.read(link_local_region_trial_to_text(
        store, _put(store, trial), _subreads(store, trial, visual, parent_request),
        session_factory=session_factory, focused=True,
    ).storage_ref))
    with session_factory() as session:
        base = EvidenceProcessingRevisionRepository(session).get(result["evidence_processing_revision_id"])
        assert session.query(OCRRiskReviewRecord).count() == 0
    with session_factory() as session, session.begin():
        SourceDocumentMetadataRevisionRepository(session).append(SourceDocumentMetadataRevision(
            metadata_revision_id="unreviewed-source-metadata", source_document_version_id="doc-svo-1",
            document_type="lab", source_party="hospital", reason="Synthetic fixture source",
            is_auto_suggestion=False, revision=1, created_at=FIXED_UTC, created_by="synthetic-reviewer",
        ))
    workflow = EvidenceRevisionWorkflow(session_factory, store)
    candidate = workflow.start(EvidenceRevisionBuildRequest(
        evidence_snapshot_id=base.evidence_snapshot_id, base_processing_revision_id=base.evidence_processing_revision_id,
        project_id=base.project_id, subject_id=base.subject_id, review_episode_id=base.review_episode_id,
        expected_revision=1, idempotency_key="unreviewed-linked-source", created_by="synthetic-reviewer",
        selected_locator_ids=[result["items"][0]["locator_id"]],
    ))
    with pytest.raises(BuildNeedsAttentionError):
        workflow.run_build(candidate.candidate_id)
