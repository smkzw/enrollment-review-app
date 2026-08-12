from __future__ import annotations

from app.domain.contracts.enums import BlockingLevel, GapType
from app.domain.contracts.review import ActionRequest


class ActionGateError(ValueError):
    pass


def derive_action_blocking_level(gap_type: GapType) -> BlockingLevel:
    if gap_type == GapType.PROVENANCE_FOLLOWUP:
        return BlockingLevel.NONE
    if gap_type == GapType.FUTURE_STAGE_NOT_DUE:
        return BlockingLevel.ATTENTION
    return BlockingLevel.BLOCKING


def validate_action_request(action: ActionRequest) -> None:
    expected = derive_action_blocking_level(action.gap_type)
    if action.blocking_level != expected:
        raise ActionGateError(
            f"{action.gap_type.value} 的 blocking_level 必须由 Gate 推导为 {expected.value}"
        )
