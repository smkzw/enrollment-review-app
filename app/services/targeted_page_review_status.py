"""Read auxiliary progress without initializing models or publishing facts."""

from app.domain.contracts.targeted_review_outcome import TargetedReviewOutcome
from app.services.evidence_app_errors import AppNotFoundError
from app.services.targeted_page_review_jobs import TARGETED_REVIEW_JOB_TYPE
from app.storage.codecs import verify_payload_sha256
from app.workflow.errors import JobNotFoundError
from app.workflow.jobstore import JobStore


def targeted_review_status(session_factory, *, subject_id, review_episode_id, job_id):
    with session_factory() as session:
        store = JobStore(session)
        try:
            job = store.get_job(job_id)
        except JobNotFoundError as exc:
            raise AppNotFoundError() from exc
        payload = verify_payload_sha256(job.payload_json, job.payload_sha256)
        authority = payload.get("authority", {})
        if (job.job_type != TARGETED_REVIEW_JOB_TYPE or authority.get("subject_id") != subject_id
                or authority.get("review_episode_id") != review_episode_id):
            raise AppNotFoundError()
        receipt = store.get_last_checkpoint(job_id, "compare:2") or store.get_last_checkpoint(job_id, "compare:1")
        data = dict(receipt[1]) if receipt else None
        if data is not None:
            data.pop("attempt", None)  # Runner envelope metadata is not a domain outcome.
        outcome = TargetedReviewOutcome.model_validate(data) if data is not None else None
        labels = {"candidate_agreement_unaccepted": "辅助读法一致，尚未采信",
                  "conflict_pending_user": "两轮复核后仍有分歧，请核对原件",
                  "conflict_preserved_read_failed": "部分复核未完成，原分歧保留",
                  "next_round_pending": "首轮仍有分歧，等待第二轮复核"}
        rounds_started = sum(any(store.get_last_checkpoint(job_id, f"read:{n}:{lane}")
                                and "round_skipped" not in store.get_last_checkpoint(job_id, f"read:{n}:{lane}")[1]
                                for lane in ("main-A", "main-B")) for n in (1, 2))
        interrupted_labels = {
            "cancel_requested": "正在停止复核，已有记录保留",
            "cancelled": "复核已停止，已有记录保留",
            "failed_retryable": "复核尚未完成，原分歧保留",
            "failed_final": "复核未完成，原分歧保留",
        }
        status_label = interrupted_labels.get(job.state)
        if status_label is None:
            status_label = labels[outcome.outcome_kind] if outcome else "正在复核原件"
        return {"job_id": job_id, "state": job.state, "round_budget": 2,
                "rounds_with_receipts": rounds_started,
                "original_reconciliation_id": payload["focus"]["original_reconciliation_id"],
                "status_label": status_label,
                "outcome": outcome.model_dump(mode="json") if outcome else None}
