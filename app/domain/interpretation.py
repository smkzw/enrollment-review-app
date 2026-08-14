"""Deterministic authority rules for protocol interpretation material."""
from __future__ import annotations

from collections.abc import Iterable

from app.domain.contracts.enums import (
    InterpretationAuthority,
    InterpretationChangeField,
    InterpretationConflictStatus,
)
from app.domain.contracts.protocol_metadata import (
    InterpretationAssessment,
    InterpretationConflict,
    InterpretationSource,
)


class InterpretationAuthorityError(ValueError):
    """解释材料试图越过方案/当前修订案权威边界。"""


FORMAL_CHANGE_FIELDS = frozenset(
    {
        InterpretationChangeField.FORMAL_REQUIREMENT,
        InterpretationChangeField.OFFICIAL_CODE,
        InterpretationChangeField.THRESHOLD,
        InterpretationChangeField.BOOLEAN_LOGIC,
        InterpretationChangeField.WORKFLOW_NODE,
        InterpretationChangeField.DUE_STAGE,
    }
)


def authority_for_source(source: InterpretationSource) -> InterpretationAuthority:
    """Return authority from source type/current amendment state only."""

    if source.is_current_amendment and source.source_type.value == "amendment":
        return InterpretationAuthority.FORMAL_REQUIREMENT
    return InterpretationAuthority.CLARIFICATION_ONLY


def _normalize_changes(changes: Iterable[InterpretationChangeField | str]) -> set[InterpretationChangeField]:
    result: set[InterpretationChangeField] = set()
    for item in changes:
        result.add(item if isinstance(item, InterpretationChangeField) else InterpretationChangeField(item))
    return result


def assess_interpretation_authority(
    source: InterpretationSource,
    *,
    protocol_is_ambiguous: bool,
    requested_changes: Iterable[InterpretationChangeField | str] = (),
    conflicts_with_protocol: bool = False,
) -> InterpretationAssessment:
    """Check whether interpretation material may be attached to a draft.

    Current amendments may change formal requirements.  Q&A, letters, email
    and medical interpretations may only add a note for an ambiguous protocol;
    they can never alter official code, threshold, boolean logic, workflow node
    or due stage.  A conflict is returned explicitly and is a publication
    blocker, rather than being resolved by source precedence.
    """

    authority = authority_for_source(source)
    changes = _normalize_changes(requested_changes)
    forbidden = sorted(
        (item.value for item in changes if item in FORMAL_CHANGE_FIELDS),
    )
    conflict_ids: list[str] = []
    if conflicts_with_protocol:
        conflict_ids.append("protocol-conflict")
    if authority == InterpretationAuthority.FORMAL_REQUIREMENT:
        if forbidden or not conflicts_with_protocol:
            return InterpretationAssessment(
                allowed=True,
                authority=authority,
                clarification_only=False,
                conflicts=conflict_ids,
                forbidden_changes=[],
                message="当前修订案可以改变正式方案要求；仍需按当前修订案重新建立来源闭包。",
            )
        # The amendment itself is the formal authority.  The conflict record
        # remains useful as history but cannot block the current amendment.
        return InterpretationAssessment(
            allowed=True,
            authority=authority,
            clarification_only=False,
            conflicts=conflict_ids,
            forbidden_changes=[],
            message="当前修订案替代旧要求，正式规则变化须绑定当前修订案来源。",
        )

    if forbidden:
        return InterpretationAssessment(
            allowed=False,
            authority=authority,
            clarification_only=True,
            conflicts=conflict_ids or ["interpretation-formal-change-forbidden"],
            forbidden_changes=forbidden,
            message="解释材料只能说明方案模糊处，不能改写正式编号、阈值、逻辑或流程。",
        )
    if conflicts_with_protocol:
        return InterpretationAssessment(
            allowed=False,
            authority=authority,
            clarification_only=True,
            conflicts=conflict_ids,
            forbidden_changes=[],
            message="解释材料与方案或当前修订案冲突，相关规则必须停在需要核对状态。",
        )
    if not source.clarifies_ambiguity:
        return InterpretationAssessment(
            allowed=False,
            authority=authority,
            clarification_only=True,
            conflicts=["interpretation-not-clarification"],
            forbidden_changes=[],
            message="非当前修订案材料必须明确标注为方案模糊处的补充说明。",
        )
    if not protocol_is_ambiguous:
        return InterpretationAssessment(
            allowed=False,
            authority=authority,
            clarification_only=True,
            conflicts=["protocol-not-ambiguous"],
            forbidden_changes=[],
            message="方案已有明确要求，解释材料不能替代或弱化正式要求。",
        )
    return InterpretationAssessment(
        allowed=True,
        authority=authority,
        clarification_only=True,
        conflicts=[],
        forbidden_changes=[],
        message="可作为来源明确的补充说明，不改变正式方案要求。",
    )


def validate_interpretation_authority(
    source: InterpretationSource,
    *,
    protocol_is_ambiguous: bool,
    requested_changes: Iterable[InterpretationChangeField | str] = (),
    conflicts_with_protocol: bool = False,
) -> InterpretationAssessment:
    assessment = assess_interpretation_authority(
        source,
        protocol_is_ambiguous=protocol_is_ambiguous,
        requested_changes=requested_changes,
        conflicts_with_protocol=conflicts_with_protocol,
    )
    if not assessment.allowed:
        raise InterpretationAuthorityError(assessment.message)
    return assessment


def build_interpretation_conflict(
    *,
    conflict_id: str,
    source: InterpretationSource,
    affected_rule_refs: list[str],
    protocol_source_refs: list[str],
    reason: str,
    impact: str,
) -> InterpretationConflict:
    """Create an explicit blocking conflict for non-amendment disagreement."""

    return InterpretationConflict(
        conflict_id=conflict_id,
        protocol_version_id=source.protocol_version_id,
        interpretation_source_id=source.interpretation_source_id,
        affected_rule_refs=affected_rule_refs,
        protocol_source_refs=protocol_source_refs,
        reason=reason,
        impact=impact,
        status=InterpretationConflictStatus.OPEN,
        blocks_publication=True,
    )


def publication_blockers(conflicts: Iterable[InterpretationConflict]) -> list[str]:
    """Return open conflict IDs in stable order for the publication gate."""

    return sorted(
        item.conflict_id
        for item in conflicts
        if item.blocks_publication
        and item.status != InterpretationConflictStatus.RESOLVED_BY_CURRENT_AMENDMENT
    )


# Concise aliases for service/gate call sites.
check_interpretation_authority = assess_interpretation_authority
get_interpretation_authority = authority_for_source
