"""Verify source-only dependent revisions without inventing normalization calls."""

from app.storage.fact_correction_repository import FactCorrectionRepository


def source_successor_origin_run(session, entity, repository, *, id_field):
    from app.storage.fact_repositories import (
        FactCrossEntityError,
        FactGateResultRepository, FactNormalizationRunRepository,
    )

    prior = repository.get(entity.source_revision_of)
    excluded = FactCorrectionRepository(session).superseded_entity_ids(entity.authority)
    mutable = {id_field, "source_revision_of", "run_id", "revision", "created_at", "fact_ids"}
    if (
        entity.model_dump(exclude=mutable) != prior.model_dump(exclude=mutable)
        or entity.run_id == prior.run_id
        or entity.revision != prior.revision + 1
        or getattr(prior, id_field) in excluded
        or not entity.source_candidate_ids
        or not entity.gate_ids
        or FactNormalizationRunRepository(session).get(entity.run_id).authority != entity.authority
    ):
        raise FactCrossEntityError("来源衔接不得改变原记录内容、来源或审核节点")
    validate_source_fact_references(
        session, entity.authority, prior.fact_ids, entity.fact_ids
    )
    # The immutable original gate remains original; it is not a new model decision.
    return FactGateResultRepository(session).get(prior.gate_id).run_id


def validate_source_fact_references(session, authority, prior_ids, current_ids):
    from app.storage.fact_repositories import ClinicalFactV2Repository, FactCrossEntityError

    excluded = FactCorrectionRepository(session).superseded_entity_ids(authority)
    facts = ClinicalFactV2Repository(session)
    unmatched = set(prior_ids)
    for target_id in current_ids:
        target = facts.get(target_id)
        if target.fact_id not in unmatched:
            if (
                target.fact_id in excluded
                or target.inherited_from_fact_id not in unmatched
            ):
                raise FactCrossEntityError("事实引用必须衔接到原记录的直接下一版本")
            parent = facts.get(target.inherited_from_fact_id)
            if (
                target.authority != authority
                or parent.authority != authority
                or target.stable_identity != parent.stable_identity
                or target.revision != parent.revision + 1
                or not set(parent.locator_ids) <= set(target.locator_ids)
                or not set(parent.source_candidate_ids) <= set(target.source_candidate_ids)
                or not set(parent.gate_ids) <= set(target.gate_ids)
            ):
                raise FactCrossEntityError("事实继承路径改变了内容或丢失来源")
            target = parent
        if target.fact_id in excluded or target.authority != authority:
            raise FactCrossEntityError("不能衔接已更正或其他节点的事实")
        unmatched.remove(target.fact_id)
    if unmatched or current_ids == prior_ids:
        raise FactCrossEntityError("来源衔接必须完整保留原事实引用并实际增加版本")
