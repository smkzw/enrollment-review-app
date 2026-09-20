"""Read saved product work without starting inference or granting adoption."""
from sqlalchemy import func, select

from app.services.review_runtime_ownership import OWNER, OWNED_TYPES
from app.storage.codecs import verify_payload_sha256
from app.storage.models import JobRecord
from app.storage.repositories import ScopeViolationError
from app.storage.review_context_repository import ReviewContextV2Repository


TASK_KINDS = {
    "predicate_binding_candidates": "predicate_candidates",
    "control_binding_candidates": "control_candidates",
    "binding_qualification": "qualification",
    "judgment_content": "judgment_content",
    "proposition_evidence": "proposition_evidence",
    "observation_relation": "observation_relation",
    "frequency_evidence": "frequency_evidence",
}


def read_prepared_review_progress(session, *, subject_id, review_episode_id, context_id,
                                  after_job_id=None, limit=50):
    if not 1 <= limit <= 100:
        raise ScopeViolationError("每次读取的审核记录数量不正确")
    context = ReviewContextV2Repository(session).get(context_id)
    if (context.authority.subject_id != subject_id
            or context.authority.review_episode_id != review_episode_id):
        raise ScopeViolationError("审核准备记录不属于当前受试者及节点")
    # Historical progress is readable even after new evidence changes authority.
    conditions = [
        JobRecord.job_type.in_(OWNED_TYPES),
        func.json_extract(JobRecord.payload_json, "$.execution_owner") == OWNER,
        func.json_extract(JobRecord.payload_json, "$.review_context_id") == context_id,
    ]
    if after_job_id is not None:
        conditions.append(JobRecord.job_id > after_job_id)
    rows = list(session.scalars(select(JobRecord).where(*conditions)
                               .order_by(JobRecord.job_id).limit(limit + 1)))
    items = []
    for row in rows[:limit]:
        payload = verify_payload_sha256(row.payload_json, row.payload_sha256)
        if payload.get("review_context_sha256") != context.context_sha256:
            raise ScopeViolationError("审核进度与本次保存的资料不一致，请核对原记录")
        candidate_id = payload.get("candidate_job_id")
        follows_candidate = row.job_type in {"binding_qualification", "judgment_content", "proposition_evidence", "observation_relation", "frequency_evidence"}
        if follows_candidate != (isinstance(candidate_id, str) and bool(candidate_id.strip())):
            raise ScopeViolationError("审核进度缺少对应的前一步记录，请核对原记录")
        items.append({
            "job_id": row.job_id, "kind": TASK_KINDS[row.job_type],
            "candidate_job_id": candidate_id,
            "state": row.state, "progress_completed": row.progress_completed,
            "progress_total": row.progress_total,
        })
    return {"context_id": context_id, "context_sha256": context.context_sha256,
            "items": items, "next_cursor": rows[limit - 1].job_id if len(rows) > limit else None}
