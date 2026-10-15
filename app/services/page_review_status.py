"""Read durable page progress without initializing a model runtime."""

from app.domain.contracts.page_review import PageCoverageEntry, PageDisposition
from app.services.evidence_app_errors import AppNotFoundError, app_error_boundary
from app.services.page_review_job_service import PAGE_REVIEW_JOB_TYPE
from app.storage.codecs import verify_payload_sha256
from app.workflow.errors import JobNotFoundError
from app.workflow.jobstore import JobStore
from app.workflow.states import TERMINAL_JOB_STATES


@app_error_boundary
def page_review_status(session_factory, *, subject_id, review_episode_id, job_id):
    with session_factory() as session:
        store = JobStore(session)
        try:
            job = store.get_job(job_id)
        except JobNotFoundError as exc:
            raise AppNotFoundError() from exc
        payload = verify_payload_sha256(job.payload_json, job.payload_sha256)
        authority = payload.get("authority", {})
        if (job.job_type != PAGE_REVIEW_JOB_TYPE or authority.get("subject_id") != subject_id
                or authority.get("review_episode_id") != review_episode_id):
            raise AppNotFoundError()
        entries = []
        for index in range(len(payload["pages"])):
            receipt = store.get_last_checkpoint(job_id, f"reconcile:{index}")
            if receipt is not None:
                entry = PageCoverageEntry.model_validate(receipt[1]["entry"])
                entries.append(entry)
        failed = sum(entry.disposition == PageDisposition.FAILED_PENDING_REREAD for entry in entries)
        accepted = sum(entry.disposition == PageDisposition.ACCEPTED for entry in entries)
        discarded = sum(entry.disposition == PageDisposition.DISCARDED_NO_ELIGIBILITY_VALUE for entry in entries)
        total = len(payload["pages"])
        coverage = store.get_last_checkpoint(job_id, "coverage")
        if job.state == "completed" and coverage is not None and len(entries) == total:
            status = "needs_reread" if failed else "ready"
        elif job.state in TERMINAL_JOB_STATES or job.state == "waiting_user":
            status = "stopped"
        else:
            status = "processing"
        labels = {"needs_reread": "部分资料需要重新判读", "ready": "资料页判读完成",
                  "stopped": "资料判读已中止", "processing": "正在判读资料"}
        exhausted = bool(payload.get("recovery", {}).get("length_override"))
        if exhausted and status == "needs_reread":
            labels[status] = "补读后仍有资料未读完，请核对原件"
        return {"job_id": job_id, "state": job.state, "review_status": status,
                "status_label": labels[status], "total_pages": total,
                "accepted_pages": accepted, "unrelated_pages": discarded,
                "failed_pages": failed, "pending_pages": total - len(entries),
                "can_reread": status == "needs_reread" and not exhausted,
                "coverage_id": coverage[1]["coverage_id"] if coverage else None,
                "predecessor_job_id": payload.get("recovery", {}).get("predecessor_job_id")}
