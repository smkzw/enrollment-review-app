"""Select explicit source-revision heads without resolving any conflict."""

from app.storage.repositories import InvalidReferenceError


def source_conflict_heads(groups):
    by_id = {group.conflict_group_id: group for group in groups}
    if len(by_id) != len(groups):
        raise InvalidReferenceError("冲突记录存在重复编号")
    children = {}
    for group in groups:
        parent_id = group.source_revision_of
        if parent_id is None:
            continue
        parent = by_id.get(parent_id)
        if (
            parent is None or parent_id in children
            or group.authority != parent.authority
            or group.member_kind != parent.member_kind
            or group.gate_id != parent.gate_id
            or group.resolution_revision != parent.resolution_revision
            or group.revision != parent.revision + 1
        ):
            raise InvalidReferenceError("冲突来源修订缺少上一版或存在分叉")
        children[parent_id] = group.conflict_group_id
    return sorted(
        (group for group in groups if group.conflict_group_id not in children),
        key=lambda group: group.conflict_group_id,
    )


def current_conflict_heads(session, authority):
    from app.storage.fact_repositories import ClinicalConflictGroupV2Repository
    from app.storage.fact_correction_commit_repository import FactCorrectionCommitRepository

    groups = ClinicalConflictGroupV2Repository(session).list_for_authority(authority)
    excluded = FactCorrectionCommitRepository(session).superseded_conflict_ids(authority)
    # Exclude only after folding so removal cannot revive an ancestor.
    return [
        group for group in source_conflict_heads(groups)
        if group.conflict_group_id not in excluded
    ]
