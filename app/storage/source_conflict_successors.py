"""Validate source-only conflict successors; never adjudicate member values."""

from app.storage.active_conflicts import current_conflict_heads
from app.storage.source_reference_successors import validate_source_fact_references


def validate_conflict_successor(session, group, repository):
    from app.storage.fact_repositories import (
        ClinicalEventV2Repository, MedicationExposureV2Repository,
        FactCrossEntityError, FactNormalizationRunRepository, FactGateResultRepository,
    )
    from app.storage.fact_correction_repository import FactCorrectionRepository

    prior = repository.get(group.source_revision_of)
    mutable = {
        "conflict_group_id", "source_revision_of", "revision", "run_id", "created_at",
        "fact_ids", "event_ids", "exposure_ids", "locator_ids",
    }
    if (
        group.model_dump(exclude=mutable) != prior.model_dump(exclude=mutable)
        or group.run_id == prior.run_id
        or group.revision != prior.revision + 1
        or prior.conflict_group_id not in {
            item.conflict_group_id for item in current_conflict_heads(session, group.authority)
        }
        or FactNormalizationRunRepository(session).get(group.run_id).authority != group.authority
    ):
        raise FactCrossEntityError("冲突来源衔接不得改变争议内容或引用旧版本")
    field = {"fact": "fact_ids", "event": "event_ids", "exposure": "exposure_ids"}[group.member_kind]
    if any(getattr(group, other) for other in ("fact_ids", "event_ids", "exposure_ids") if other != field):
        raise FactCrossEntityError("冲突来源衔接不得混入其他类型成员")
    old_ids, new_ids = getattr(prior, field), getattr(group, field)
    if len(old_ids) != len(new_ids) or len(set(new_ids)) != len(new_ids) or set(old_ids) == set(new_ids):
        raise FactCrossEntityError("冲突来源衔接须保留全部成员并实际更新来源")
    if group.member_kind == "fact":
        validate_source_fact_references(session, group.authority, old_ids, new_ids)
    else:
        member_repository, id_field = (
            (ClinicalEventV2Repository(session), "event_id") if group.member_kind == "event"
            else (MedicationExposureV2Repository(session), "exposure_id")
        )
        excluded = FactCorrectionRepository(session).superseded_entity_ids(group.authority)
        unmatched = set(old_ids)
        for member_id in new_ids:
            member = member_repository.get(member_id)
            parent_id = member_id if member_id in unmatched else member.source_revision_of
            if parent_id not in unmatched or member_id in excluded or parent_id in excluded:
                raise FactCrossEntityError("冲突成员缺少直接来源继承依据")
            parent = member_repository.get(parent_id)
            if member.authority != group.authority or parent.authority != group.authority:
                raise FactCrossEntityError("冲突成员跨审核节点")
            if member_id != parent_id:
                mutable_member = {id_field, "source_revision_of", "run_id", "revision", "created_at", "fact_ids"}
                if (
                    member.revision != parent.revision + 1
                    or member.model_dump(exclude=mutable_member) != parent.model_dump(exclude=mutable_member)
                ):
                    raise FactCrossEntityError("冲突来源衔接不能更改事件或用药内容")
                validate_source_fact_references(session, group.authority, parent.fact_ids, member.fact_ids)
            unmatched.remove(parent_id)
        if unmatched:
            raise FactCrossEntityError("冲突来源衔接遗漏原成员")
    members = repository._load_members(group)
    if set(group.locator_ids) != {locator for member in members for locator in member.locator_ids}:
        raise FactCrossEntityError("冲突来源必须保留全部成员定位")
    return FactGateResultRepository(session).get(prior.gate_id).run_id
