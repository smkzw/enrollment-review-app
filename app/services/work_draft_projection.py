"""Read saved working results; never rerun inference while rendering."""
from sqlalchemy import select

from app.domain.publication import canonical_hash
from app.storage.models import ReviewRunRecord
from app.storage.repositories import AppendRepository, REVIEW_RUN_CONFIG
from app.storage.review_context_repository import ReviewContextV2Repository
from app.storage.work_draft_repository import WorkDraftRepository
from app.services.work_draft_calculation import LABELS


def project_work_draft(session, *, authority, rule_set, clause_pack, artifact_store=None):
    from app.services.eligibility_review_projection import (
        EligibilityClauseProjection, EligibilityFactRef, EligibilityReviewProjection,
    )
    from app.services.work_draft_review import CALCULATION_VERSION
    ids = session.scalars(select(ReviewRunRecord.review_run_id).where(
        ReviewRunRecord.review_episode_id == authority.review_episode_id,
        ReviewRunRecord.run_kind == "work_draft").order_by(ReviewRunRecord.created_at.desc())).all()
    rows, issues, run_id, state = [], (), None, "not_started"
    if ids:
        run = AppendRepository(session, REVIEW_RUN_CONFIG).get(ids[0])
        frozen = ReviewContextV2Repository(session).get(run.context_id)
        if frozen.evaluator_version != CALCULATION_VERSION:
            state = "method_changed"
        elif frozen.authority != authority or frozen.rule_set_sha256 != canonical_hash(rule_set.model_dump(mode="json")):
            state = "source_changed"
        else:
            from app.services.review_context_assembly import assemble_review_context
            current = assemble_review_context(session, artifact_store, review_episode_id=authority.review_episode_id,
                review_run_id=frozen.review_run_id, evaluator_version=CALCULATION_VERSION,
                created_at=frozen.created_at, context_id=frozen.context_id, work_draft=True)
            if current.context_sha256 != frozen.context_sha256:
                state = "source_changed"
            else:
                rows = WorkDraftRepository(session).list_for_run(run.review_run_id)
                issues, run_id, state = tuple(run.system_issues), run.review_run_id, "current"
    clauses, components = [], []
    if rows:
        for item in rows:
            refs = tuple(EligibilityFactRef(**ref.model_dump(mode="json")) for ref in item.evidence_refs)
            projection = EligibilityClauseProjection(rule_component_id=item.item_id, rule_code=item.official_code,
                rule_kind=item.rule_kind.value, text_summary=item.title, source_text=item.source_text,
                parent_rule_code=item.official_code if item.rule_component_id is not None else None, decision=item.decision.value if item.decision else "system_issue",
                decision_label=LABELS[item.decision] if item.decision else "系统问题", reason=item.reason_text,
                fact_refs=refs, gap_type=None, determination_mode="restricted" if item.system_issue else "deterministic",
                confidence=item.confidence, confidence_reason=item.confidence_reason)
            (components if item.rule_component_id is not None else clauses).append(projection)
    else:
        for rule in rule_set.rules:
            clauses.append(EligibilityClauseProjection(rule_component_id=rule.rule_id, rule_code=rule.official_code,
                rule_kind=rule.kind.value, text_summary=rule.source_text, source_text=rule.source_text,
                parent_rule_code=None, decision="system_issue", decision_label="尚未生成工作稿",
                reason="请开始审核；旧结果和资料仍会保留。", fact_refs=(), gap_type=None, determination_mode="restricted"))
    return EligibilityReviewProjection(subject_id=authority.subject_id, review_episode_id=authority.review_episode_id,
        rule_set_id=authority.rule_set_id, rule_set_revision=authority.rule_set_revision,
        evidence_snapshot_v2_id=authority.evidence_snapshot_v2_id,
        complete_processing_revision_id=authority.complete_processing_revision_id,
        clauses=tuple(clauses), work_draft_state=state, review_run_id=run_id, system_issues=issues,
        verification_only=rule_set.verification_only, component_clauses=tuple(components))
