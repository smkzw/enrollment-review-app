"""Source closure for V2 references in the existing formal review records."""
from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.domain.contracts.facts import FactAuthority
from app.domain.contracts.review import ActionRequest, ActionTransition, ReviewEpisode, ReviewRun


def review_authority(run: ReviewRun, episode: ReviewEpisode) -> FactAuthority:
    if run.schema_version != "review/v2" or run.review_episode_id != episode.review_episode_id:
        raise ValueError("新版审核来源必须绑定同一审核节点")
    return FactAuthority(
        project_id=episode.project_id,
        subject_id=episode.subject_id,
        review_episode_id=run.review_episode_id,
        episode_revision=run.episode_revision,
        protocol_version_id=run.protocol_version_id,
        rule_set_id=episode.rule_set_id,
        rule_set_revision=run.rule_set_revision,
        evidence_snapshot_v2_id=run.evidence_snapshot_v2_id,
        complete_processing_revision_id=run.complete_processing_revision_id,
    )


def validate_review_references(
    session: Session,
    *,
    authority: FactAuthority,
    fact_ids: Sequence[str],
    locator_ids: Sequence[str],
) -> None:
    from app.storage.fact_authority import FactAuthorityValidator
    from app.storage.fact_repositories import ClinicalFactV2Repository
    from app.storage.repositories import ScopeViolationError

    if len(set(fact_ids)) != len(fact_ids) or len(set(locator_ids)) != len(locator_ids):
        raise ScopeViolationError("审核事实和原件定位不得重复")
    facts = ClinicalFactV2Repository(session).get_many(fact_ids)
    selected_locators = set(locator_ids)
    for fact in facts.values():
        if fact.authority != authority:
            raise ScopeViolationError("审核事实不属于本次冻结的资料及处理版本")
        if not selected_locators.intersection(fact.locator_ids):
            raise ScopeViolationError("审核引用的事实缺少对应原件定位")
    # This checks the frozen revision, not the current activity pointer, so old
    # reviews remain readable after new material is activated.
    FactAuthorityValidator(session).validate_locators(authority, list(locator_ids))


def validate_action_response(session: Session, action: ActionRequest, transition: ActionTransition) -> None:
    """A response uses its own retained source, never the original run's pages."""
    from app.storage.fact_authority import FactAuthorityValidator
    from app.storage.repositories import ScopeViolationError

    authority = transition.response_authority
    if authority is None:
        if transition.locator_ids:
            raise ScopeViolationError("办理原件缺少所属资料版本")
        return
    if (authority.project_id, authority.subject_id, authority.review_episode_id) != (
        action.project_id, action.subject_id, action.review_episode_id,
    ):
        raise ScopeViolationError("办理原件不属于本受试者的审核节点")
    validator = FactAuthorityValidator(session)
    validator.validate_frozen_source(authority)
    validator.validate_locators(authority, list(transition.locator_ids or ()))
