"""Append unresolved conflict versions after verified source-reference growth."""

from app.domain.publication import canonical_hash
from app.storage.active_conflicts import current_conflict_heads
from app.storage.fact_repositories import ClinicalConflictGroupV2Repository
from app.storage.repositories import InvalidReferenceError


def append_source_conflict_successors(session, *, authority, run_id, facts, events, exposures, created_at):
    replacements = {}
    for kind, entities, parent_field, id_field in (
        ("fact", facts, "inherited_from_fact_id", "fact_id"),
        ("event", events, "source_revision_of", "event_id"),
        ("exposure", exposures, "source_revision_of", "exposure_id"),
    ):
        mapping = {}
        for item in entities:
            parent_id = getattr(item, parent_field)
            if parent_id is None:
                continue
            if parent_id in mapping:
                raise InvalidReferenceError("同一来源存在多个后继，不能选择其中之一")
            mapping[parent_id] = getattr(item, id_field)
        replacements[kind] = mapping
    repository = ClinicalConflictGroupV2Repository(session)
    appended = []
    for prior in current_conflict_heads(session, authority):
        field = {"fact": "fact_ids", "event": "event_ids", "exposure": "exposure_ids"}[prior.member_kind]
        old_ids = getattr(prior, field)
        member_ids = sorted(replacements[prior.member_kind].get(item, item) for item in old_ids)
        if member_ids == old_ids:
            continue
        identity = canonical_hash({
            "contract": "source-conflict-successor/v1", "run_id": run_id,
            "prior": prior.model_dump(mode="json"), "members": member_ids,
        })
        successor = prior.model_copy(update={field: member_ids})
        locators = sorted({locator for member in repository._load_members(successor) for locator in member.locator_ids})
        successor = type(prior).model_validate({
            **prior.model_dump(), field: member_ids, "locator_ids": locators,
            "conflict_group_id": f"source-conflict:{identity}", "source_revision_of": prior.conflict_group_id,
            "run_id": run_id, "revision": prior.revision + 1, "created_at": created_at,
        })
        appended.append(repository.create(successor))
    return appended
