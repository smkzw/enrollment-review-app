"""Discover concrete read conflicts without launching any reread."""

from app.domain.targeted_page_review import explicit_conflict_fields
from app.domain.targeted_handwriting_review import handwriting_needs_review
from app.services.page_review_status import page_review_status
from app.services.evidence_app_errors import AppNotFoundError
from app.storage.codecs import verify_payload_sha256
from app.storage.evidence_repositories import SourceDocumentRepository
from app.storage.page_review_repository import PageReviewRepository
from app.workflow.jobstore import JobStore


def targeted_review_candidates(session_factory, *, subject_id, review_episode_id, job_id):
    status = page_review_status(session_factory, subject_id=subject_id,
                                review_episode_id=review_episode_id, job_id=job_id)
    if status["state"] != "completed":
        return {"job_id": job_id, "pages": []}
    with session_factory() as session:
        store = JobStore(session)
        job = store.get_job(job_id)
        payload = verify_payload_sha256(job.payload_json, job.payload_sha256)
        repository = PageReviewRepository(session)
        pages = []
        for index, page in enumerate(payload["pages"]):
            receipt = store.get_last_checkpoint(job_id, f"reconcile:{index}")
            identity = receipt[1]["entry"].get("reconciliation_id") if receipt else None
            if not identity:
                continue
            reconciliation = repository.get_reconciliation(identity)
            if (reconciliation.page_artifact_id != page["page_artifact_id"]
                    or reconciliation.clause_pack_sha256 != payload["clause_pack"]["clause_pack_sha256"]):
                raise AppNotFoundError("判读记录与原件不一致，暂不能列出分歧。")
            records = [repository.get_review(key) for key in reconciliation.page_review_ids]
            records = [record for record in records if record.lane.value in ("main-A", "main-B")]
            if len(records) != 2:
                continue
            if any(record.page_image_sha256 != page["page_image_sha256"] for record in records):
                raise AppNotFoundError("判读图像与原件不一致，暂不能列出分歧。")
            fields = explicit_conflict_fields(records)
            handwriting = handwriting_needs_review(records)
            if fields or handwriting:
                document = SourceDocumentRepository(session).get(page["source_document_version_id"])
                pages.append({"page_index": index, "file_name": document.file_name,
                              "page_number": page["page_number"], "field_count": len(fields) + int(handwriting)})
        return {"job_id": job_id, "pages": pages}
