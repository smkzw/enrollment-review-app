"""Source-bound auxiliary excerpts for inspection, never a fact publication."""

from typing import Literal
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict

from app.domain.contracts.page_review import PageReviewRecord
from app.domain.page_normalization import normalize_field_name
from app.services.evidence_app_errors import AppNotFoundError
from app.services.targeted_page_review_status import targeted_review_status
from app.storage.codecs import verify_payload_sha256
from app.storage.evidence_locator_repositories import CompleteEvidenceProcessingRevisionRepository
from app.storage.evidence_repositories import SourceDocumentRepository
from app.storage.ocr_repositories import PageArtifactRepository
from app.storage.page_review_repository import PageReviewRepository
from app.workflow.jobstore import JobStore


class AuxiliaryExcerpt(BaseModel):
    model_config = ConfigDict(extra="forbid")
    round_number: Literal[0, 1, 2]
    read_number: Literal[1, 2]
    field_name: str
    raw_value: str
    excerpt: str
    target_text: str | None
    time_text: str | None
    location_text: str | None


class TargetedReviewEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_id: str
    file_name: str
    page_number: int
    image_path: str
    image_sha256: str
    excerpts: list[AuxiliaryExcerpt]
    candidate_auto_accept: Literal[False] = False


def targeted_review_evidence(session_factory, *, subject_id, review_episode_id, job_id):
    # Reuse the read-only task/scope check; no model configuration discovery.
    targeted_review_status(session_factory, subject_id=subject_id,
                           review_episode_id=review_episode_id, job_id=job_id)
    with session_factory() as session:
        store = JobStore(session)
        job = store.get_job(job_id)
        payload = verify_payload_sha256(job.payload_json, job.payload_sha256)
        page = payload["page"]
        revision_id = payload["authority"]["complete_processing_revision_id"]
        revision = CompleteEvidenceProcessingRevisionRepository(session).get(revision_id)
        entries = [entry for entry in revision.manifest
                   if entry.page_artifact_id == page["page_artifact_id"]]
        artifact = PageArtifactRepository(session).get(page["page_artifact_id"])
        if (len(entries) != 1 or artifact.page_image_sha256 != page["page_image_sha256"]
                or artifact.source_document_version_id != page["source_document_version_id"]
                or artifact.page_number != page["page_number"]):
            raise AppNotFoundError("复核记录与冻结原页不一致，暂不能显示。")
        document = SourceDocumentRepository(session).get(page["source_document_version_id"])
        repository = PageReviewRepository(session)
        reconciliation = repository.get_reconciliation(payload["focus"]["original_reconciliation_id"])
        records = [(0, repository.get_review(key)) for key in reconciliation.page_review_ids]
        for number in (1, 2):
            for lane in ("main-A", "main-B"):
                checkpoint = store.get_last_checkpoint(job_id, f"read:{number}:{lane}")
                raw = checkpoint[1].get("auxiliary_review") if checkpoint else None
                if raw is not None:
                    records.append((number, PageReviewRecord.model_validate(raw)))
        excerpts = []
        targets = set(payload["focus"]["targets"])
        for number, record in records:
            if record.lane.value not in ("main-A", "main-B"):
                continue
            if (record.page_image_sha256 != page["page_image_sha256"]
                    or record.page_artifact_id != page["page_artifact_id"]
                    or record.source_document_version_id != page["source_document_version_id"]
                    or record.page_number != page["page_number"]):
                raise AppNotFoundError("摘录与本次复核原页不一致，暂不能显示。")
            for fact in record.facts:
                if normalize_field_name(fact.field_name) not in targets:
                    continue
                context = fact.context
                excerpts.append(AuxiliaryExcerpt(
                    round_number=number, read_number=1 if record.lane.value == "main-A" else 2,
                    field_name=fact.field_name, raw_value=fact.raw_value,
                    excerpt=fact.region.excerpt,
                    target_text=context.target_text if context else None,
                    time_text=context.time_text if context else None,
                    location_text=context.location_text if context else None,
                ))
            if payload["focus"].get("handwriting_review"):
                labels = {"signature_initials_date": "手写签名与日期",
                          "cs_ncs_judgment": "临床意义批注", "note": "手写便签",
                          "table_cell": "手写表格内容", "other": "其他手写内容"}
                for note in record.handwriting:
                    context = note.context
                    excerpts.append(AuxiliaryExcerpt(
                        round_number=number, read_number=1 if record.lane.value == "main-A" else 2,
                        field_name=labels[note.kind.value], raw_value=note.raw_text,
                        excerpt=note.region.excerpt,
                        target_text=context.target_text if context else None,
                        time_text=context.time_text if context else None,
                        location_text=context.location_text if context else None,
                    ))
        return TargetedReviewEvidence(
            job_id=job_id, file_name=document.file_name, page_number=page["page_number"],
            image_path=f"/api/v2/evidence-processing-revisions/{quote(revision_id, safe='')}/pages/{quote(entries[0].entry_id, safe='')}/image",
            image_sha256=page["page_image_sha256"], excerpts=excerpts,
        )
