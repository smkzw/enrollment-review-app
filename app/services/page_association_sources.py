"""Build source associations from the selected immutable processing revision."""

from app.domain.page_source_association import PageAssociationSource
from app.evidence.effective_text import project_effective_text
from app.storage.evidence_locator_repositories import CorrectionRepository
from app.storage.ocr_repositories import OcrPageRepository


def page_association_sources(session, revision):
    corrections = [CorrectionRepository(session).get(key) for key in revision.correction_ids]
    sources = {}
    for entry in revision.manifest:
        if entry.ocr_page_id is None:
            continue
        ocr = OcrPageRepository(session).get(entry.ocr_page_id)
        if (ocr.page_artifact_id, ocr.page_number) != (entry.page_artifact_id, entry.page_number):
            raise ValueError("来源关联 OCR 与当前原件页不一致")
        projection = project_effective_text(ocr.raw_text, [item for item in corrections if item.ocr_page_id == entry.ocr_page_id])
        sources[entry.page_artifact_id] = PageAssociationSource(
            source_document_version_id=entry.source_document_version_id, page_number=entry.page_number,
            text=projection.effective_text, text_sha256=projection.effective_text_sha256)
    return sources
