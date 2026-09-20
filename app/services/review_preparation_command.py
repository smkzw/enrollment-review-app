"""Freeze a source-bound review input once; never infer, approve or publish."""
from datetime import UTC, datetime
from uuid import uuid4

from app.domain.contracts.facts import FactAuthority
from app.domain.contracts.review_context_v2 import ReviewContextSnapshotV2
from app.domain.publication import canonical_hash
from app.services.frozen_review_calculation import EVALUATOR_VERSION
from app.services.review_context_assembly import assemble_review_context
from app.storage.fact_authority import FactAuthorityValidator
from app.storage.idempotency import IdempotencyRepository, STATUS_COMMITTED
from app.storage.repositories import ScopeViolationError
from app.storage.review_context_repository import ReviewContextV2Repository


def prepare_review(
    session, artifact_store, *, subject_id: str, review_episode_id: str,
    expected_authority: FactAuthority, idempotency_key: str,
) -> ReviewContextSnapshotV2:
    """Caller owns commit. Repeated requests retrieve the original frozen input.

    A new operation must match the selected active revision. Historical retry
    does not reactivate it; the publication service independently checks currency.
    """
    authority = FactAuthority.model_validate(expected_authority.model_dump(mode="json"))
    if (authority.subject_id != subject_id
            or authority.review_episode_id != review_episode_id
            or not idempotency_key.strip()):
        raise ScopeViolationError("请重新确认本次受试者、审核节点及所选资料")
    scope = f"review-preparation:{review_episode_id}"
    request_hash = canonical_hash({
        "version": "review-preparation/v1", "authority": authority.model_dump(mode="json"),
        "evaluator_version": EVALUATOR_VERSION,
    })
    contexts = ReviewContextV2Repository(session)
    with session.begin_nested():
        # Claim the request before assembling so a concurrent retry creates no orphan.
        receipt, created = IdempotencyRepository(session).resolve(
            scope=scope, idempotency_key=idempotency_key, submitted_hash=request_hash,
            result_type="review_context_v2", result_id=f"review-context-v2:{uuid4().hex}",
        )
        if receipt.result_type != "review_context_v2" or receipt.status != STATUS_COMMITTED:
            raise ScopeViolationError("原审核准备记录不完整，未创建重复记录")
        if not created:
            context = contexts.get(receipt.result_id)
            if context.authority != authority or context.evaluator_version != EVALUATOR_VERSION:
                raise ScopeViolationError("原审核准备记录与本次选择不一致，未替换原资料")
            return context
        FactAuthorityValidator(session).validate(authority)
        context = assemble_review_context(
            session, artifact_store, review_episode_id=review_episode_id,
            review_run_id=f"review-run:{uuid4().hex}", evaluator_version=EVALUATOR_VERSION,
            created_at=datetime.now(UTC), context_id=receipt.result_id,
        )
        if context.authority != authority:
            raise ScopeViolationError("所选资料版本已变化，请重新确认后开始审核")
        return contexts.save(context)
