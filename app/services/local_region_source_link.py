"""Link isolated, corroborated fields to existing OCR text locators, not approvals."""
from __future__ import annotations

import json
import re

from app.domain.contracts.enums import LocatorSourceLayer
from app.domain.contracts.evidence_locator import TRANSCRIPT_NAVIGATION_TARGET_PREFIX
from app.domain.publication import canonical_hash
from app.evidence.artifacts import ArtifactStore, StoredArtifact
from app.services.evidence_locator_service import EvidenceLocatorService, LocatorRequest
from app.services.local_region_comparison import (
    evaluate_focused_localized_region_trial,
    evaluate_localized_region_trial,
)
from app.storage.evidence_locator_repositories import CompleteEvidenceProcessingRevisionRepository
from app.storage.ocr_models import EvidenceProcessingRevisionRecord
from app.storage.ocr_repositories import EvidenceProcessingRevisionRepository, OcrPageRepository


def link_local_region_trial_to_text(
    artifacts: ArtifactStore,
    trial_ref: str,
    subreads: list[dict],
    *,
    session_factory,
    focused: bool = False,
) -> StoredArtifact:
    """Recheck actual reads, then append field or transcript navigation locators.

    This does not select locators into an existing immutable revision, resolve
    OCR risks, publish facts, or claim that a proposed crop is a glyph box.
    """
    evaluate = evaluate_focused_localized_region_trial if focused else evaluate_localized_region_trial
    comparison_ref = evaluate(artifacts, trial_ref, subreads, session_factory=session_factory)
    comparison = json.loads(artifacts.read(comparison_ref.storage_ref))
    base = json.loads(artifacts.read(comparison["base_comparison_ref"]))
    visual = json.loads(artifacts.read(base["visual_receipt_ref"]))
    items = visual["structured_read"]["items"]
    locator_service = EvidenceLocatorService(session_factory, artifacts)

    with session_factory() as session, session.begin():
        revision_id = base["evidence_processing_revision_id"]
        record = session.get(EvidenceProcessingRevisionRecord, revision_id)
        if record is not None and record.revision_kind == "complete":
            revision = CompleteEvidenceProcessingRevisionRepository(session, artifacts).get(revision_id)
            source_base = EvidenceProcessingRevisionRepository(session).get(revision.base_processing_revision_id)
            if canonical_hash(source_base.model_dump(mode="json")) != base["base_revision_sha256"]:
                raise ValueError("文字关联的原图基础版本已不一致")
            expected_sha = base["evidence_revision_sha256"]
        else:
            revision = EvidenceProcessingRevisionRepository(session).get(revision_id)
            expected_sha = base["base_revision_sha256"]
        if canonical_hash(revision.model_dump(mode="json")) != expected_sha:
            raise ValueError("文字关联的资料版本已不一致")
        entries = [entry for entry in revision.manifest if entry.page_artifact_id == base["page_artifact_id"]]
        if len(entries) != 1 or entries[0].ocr_page_id is None:
            raise ValueError("文字关联必须有本资料版本中唯一的原始文字页")
        ocr = OcrPageRepository(session).get(entries[0].ocr_page_id)
        if ocr.raw_text_sha256 != visual["ocr_raw_text_sha256"]:
            raise ValueError("文字关联的原始文字已不一致")

        anchors = {}
        transcript_indexes = set()
        for outcome in comparison["items"]:
            index = outcome["item_index"]
            item = items[index]
            if outcome["single_field_transcription_agreement"] and (item["label"] or "").strip():
                excerpt = item["excerpt"].strip()
                start = ocr.raw_text.find(excerpt)
                # No normalization here: offsets must describe literal original
                # text, not an inferred table row or a reconstructed quotation.
                if start >= 0 and ocr.raw_text.find(excerpt, start + 1) < 0:
                    anchors[index] = (start, start + len(excerpt), excerpt)
            elif outcome.get("literal_crop_transcription_agreement") is True:
                # Only spacing may differ. Save the actual source substring
                # and offsets, never a normalized or reconstructed quotation.
                tokens = item["excerpt"].split()
                pattern = r"(?<!\S)" + r"[^\S\r\n]+".join(map(re.escape, tokens)) + r"(?!\S)"
                matches = list(re.finditer(pattern, ocr.raw_text))
                if len(matches) == 1 and len(matches[0].group().splitlines()) == 1:
                    match = matches[0]
                    anchors[index] = (match.start(), match.end(), match.group())
                    transcript_indexes.add(index)
        ranges = [(start, end) for start, end, _ in anchors.values()]
        linked_items = []
        for outcome in comparison["items"]:
            index = outcome["item_index"]
            result = {"item_index": index, "status": "unresolved", "locator_id": None,
                      "source_position_verified": False, "formal_adoption_authorized": False,
                      "field_assignment_verified": False,
                      "reasons": list(outcome["reasons"])}
            anchor = anchors.get(index)
            if anchor is None:
                result["reasons"].append("完整字段尚不能在本页原始文字中唯一对应")
            elif ranges.count(anchor[:2]) != 1:
                result["reasons"].append("多个读取项目对应同一原始文字范围，须核清归属")
            else:
                start, end, excerpt = anchor
                locator = locator_service.create_locator_in_session(session, LocatorRequest(
                    page_artifact_id=base["page_artifact_id"], ocr_page_id=ocr.ocr_page_id,
                    source_layer=LocatorSourceLayer.RAW_OCR,
                    source_text_sha256=ocr.raw_text_sha256,
                    target_id=(TRANSCRIPT_NAVIGATION_TARGET_PREFIX if index in transcript_indexes else "local-read:")
                        + canonical_hash({"trial": trial_ref, "item": index}),
                    target_text_start=start, target_text_end=end, excerpt=excerpt,
                ))
                result.update(status=("transcript_navigation_candidate" if index in transcript_indexes
                                      else "text_linked_candidate"), locator_id=locator.locator_id,
                              text_start=start, text_end=end, source_text_sha256=ocr.raw_text_sha256)
            linked_items.append(result)
        result = {
            "contract": "local-region-source-text-links/v2", "candidate_only": True,
            "formal_adoption_authorized": False, "source_position_verified": False,
            "source_trial_ref": trial_ref, "comparison_ref": comparison_ref.storage_ref,
            "evidence_processing_revision_id": revision_id,
            "evidence_revision_sha256": expected_sha,
            "page_artifact_id": base["page_artifact_id"], "ocr_page_id": ocr.ocr_page_id,
            "ocr_raw_text_sha256": ocr.raw_text_sha256, "items": linked_items,
            "unresolved": comparison["unresolved"], "unmatched_ocr": comparison["unmatched_ocr"],
        }
        return artifacts.put("evaluation_manifest", json.dumps(
            result, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode())
