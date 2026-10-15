"""Resolve an action's control source from the original stored review only."""
from app.domain.control_action_directives import control_action_targets
from app.storage.review_control_repository import ReviewControlRepository


def validate_control_action_origin(session, action):
    from app.storage.repositories import ScopeViolationError

    origin = action.control_origin
    snapshot = ReviewControlRepository(session).get_or_none(action.review_run_id)
    if origin is None or snapshot is None:
        raise ScopeViolationError("办理事项缺少本次保存的补充要求结果")
    item = next((item for control in snapshot.outcomes
                 if control.protocol_control_id == origin.protocol_control_id
                 for item in control_action_targets(control)
                 if (item.obligation_id, item.obligation_group_id)
                 == (origin.obligation_id, origin.obligation_group_id)), None)
    if (item is None or item.modality != origin.modality
            or item.obligation_id != origin.obligation_id or item.obligation_group_id != origin.obligation_group_id
            or action.gap_type != item.gap_type
            or (action.trigger_locator_id is not None and action.trigger_locator_id not in item.locator_ids)):
        raise ScopeViolationError("办理事项与原补充要求、核对问题或原件归属不一致")
    return item
