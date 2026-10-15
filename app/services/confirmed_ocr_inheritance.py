"""Reuse exact confirmed page identities, never rewrite an older OCR cache entry."""
from types import MappingProxyType

from sqlalchemy import func, select

from app.domain.contracts.enums import OCRPageStatus
from app.storage.evidence_locator_repositories import CompleteEvidenceProcessingRevisionRepository
from app.storage.ocr_repositories import OcrPageRepository
from app.storage.codecs import verify_payload_sha256
from app.storage.models import JobRecord
from app.workflow.jobstore import JobStore

CONTRACT = "confirmed-ocr/v1"


def stored_inheritance(session, base):
    """Resolve the producing job, not the node's possibly newer active pointer."""
    matches = []
    reprocessed = False
    for job in session.scalars(select(JobRecord).where(
        JobRecord.job_type.in_(("evidence_processing", "evidence_reprocess")),
        func.json_extract(JobRecord.payload_json, "$.snapshot_id") == base.evidence_snapshot_id,
    )):
        checkpoint = JobStore(session).get_last_checkpoint(job.job_id, "evidence_processing")
        if checkpoint is None or checkpoint[1].get("revision_id") != base.evidence_processing_revision_id:
            continue
        payload = verify_payload_sha256(job.payload_json, job.payload_sha256)
        if job.job_type == "evidence_reprocess":
            # A no-op native-text attempt does not supersede the producing upload's lineage.
            reprocessed = True
        elif "ocr_inheritance_contract" in payload:
            matches.append({key: payload.get(key) for key in ("ocr_inheritance_contract", "inherited_processing_revision_id")})
    if not matches:
        return {"ocr_inheritance_contract": CONTRACT, "inherited_processing_revision_id": None} if reprocessed else None
    if any(item != matches[0] for item in matches):
        raise ValueError("本次识别的沿用来源存在分歧，请核对处理记录")
    return matches[0]


def confirmed_revision(session, snapshot, revision_id):
    prior = CompleteEvidenceProcessingRevisionRepository(session).get(revision_id)
    if (prior.project_id, prior.subject_id, prior.review_episode_id, prior.evidence_snapshot_id) != (
        snapshot.project_id, snapshot.subject_id, snapshot.review_episode_id, snapshot.comparison_snapshot_id
    ):
        raise ValueError("上一确认版本与本次资料来源不一致")
    return prior


def load_confirmed_pages(session, snapshot, payload):
    if "ocr_inheritance_contract" not in payload:
        return MappingProxyType({})
    if payload["ocr_inheritance_contract"] != CONTRACT or "inherited_processing_revision_id" not in payload:
        raise ValueError("资料沿用记录不完整或版本不支持")
    revision_id = payload["inherited_processing_revision_id"]
    if revision_id is None:
        return MappingProxyType({})
    if not isinstance(revision_id, str) or not revision_id:
        raise ValueError("上一确认版本标识无效")
    prior = confirmed_revision(session, snapshot, revision_id)
    versions = {member.source_document_version_id for member in snapshot.members}
    pages = {}
    for entry in prior.manifest:
        if entry.source_document_version_id not in versions or entry.ocr_page_id is None:
            continue
        page = OcrPageRepository(session).get(entry.ocr_page_id)
        if (page.page_artifact_id, page.page_number) != (entry.page_artifact_id, entry.page_number):
            raise ValueError("上一确认识别页与原件不一致")
        if page.status != OCRPageStatus.SUCCEEDED:
            raise ValueError("上一确认识别页尚未完成")
        pages[(entry.source_document_version_id, entry.page_artifact_id)] = page
    return MappingProxyType(pages)
