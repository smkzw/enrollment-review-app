"""Follow-ups for unresolved control observations, without inferring missing care."""
from dataclasses import dataclass
from .contracts.control_review_outcome import ControlReviewOutcome
from .contracts.enums import GapType, TruthValue
from .contracts.protocol_controls import ControlObligationModality


@dataclass(frozen=True)
class ControlActionTarget:
    target_id: str
    obligation_id: str | None
    obligation_group_id: str | None
    modality: ControlObligationModality
    statement: str
    locator_ids: tuple[str, ...]
    gap_type: GapType = GapType.OBSERVATION_UNVERIFIED


def control_action_targets(outcome: ControlReviewOutcome) -> tuple[ControlActionTarget, ...]:
    """Group an unknown prerequisite; do not fan it out as missing observations.

    Membership in a disputed fact set alone does not prove a conflict in this
    requirement. Specific absence/conflict actions require a separate source proof.
    """
    groups = {}
    for item in outcome.obligations:
        groups.setdefault(item.obligation_group_id, []).append(item)
    targets = []
    for group_id, items in sorted(groups.items()):
        if len({item.activation for item in items}) != 1:
            raise ValueError("同组要求的适用条件结果不一致")
        if items[0].activation == TruthValue.UNKNOWN:
            modality = (ControlObligationModality.MANDATORY if any(item.modality == ControlObligationModality.MANDATORY for item in items)
                        else ControlObligationModality.RECOMMENDED if any(item.modality == ControlObligationModality.RECOMMENDED for item in items)
                        else ControlObligationModality.BEST_EFFORT)
            text = "；".join(dict.fromkeys(item.statement for item in items))
            targets.append(ControlActionTarget(group_id, None, group_id, modality,
                f"先核实以下要求的适用、触发及例外条件：{text}", ()))
            continue
        for item in items:
            if item.status == "unverified":
                gap = (GapType.PROFESSIONAL_JUDGMENT
                       if "professional_judgment_missing" in item.observation_reason_codes
                       else GapType.OBSERVATION_UNVERIFIED)
                targets.append(ControlActionTarget(item.obligation_id, item.obligation_id, None,
                    item.modality, item.statement, tuple(item.locator_ids), gap))
    return tuple(targets)
