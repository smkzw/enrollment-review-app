"""Deterministic authority rules for protocol interpretation material."""
from __future__ import annotations

from collections.abc import Iterable

from app.domain.contracts.enums import (
    AnchorResolutionMode,
    InterpretationAuthority,
    InterpretationChangeField,
    InterpretationConflictStatus,
)
from app.domain.contracts.protocol_metadata import (
    AnchorResolutionStatement,
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


def has_blocking_conflict(
    source: InterpretationSource,
    conflicts: Iterable[InterpretationConflict],
) -> bool:
    """Whether one interpretation source carries a publication-blocking conflict."""

    return any(
        item.interpretation_source_id == source.interpretation_source_id
        and item.blocks_publication
        and item.status != InterpretationConflictStatus.RESOLVED_BY_CURRENT_AMENDMENT
        for item in conflicts
    )


def clarification_anchor_resolutions(
    source: InterpretationSource,
    *,
    conflicts: Iterable[InterpretationConflict] = (),
) -> tuple[AnchorResolutionStatement, ...]:
    """Return the anchor resolutions a clarification source may contribute.

    只有来源明确的澄清级解释材料可以解析未命名回溯锚点：必须标注为方案
    模糊处补充说明，不得携带正式变更摘要，也不得与方案或当前修订案存在
    未解决冲突。解释越权时失败关闭（抛出 :class:`InterpretationAuthorityError`），
    而不是按来源优先级消解。窗口量、方向、阈值与官方编号不进入解析载荷；
    它们仍须逐字来自方案原文并由确定性门禁核验。
    """

    if not source.anchor_resolutions:
        return ()
    if authority_for_source(source) != InterpretationAuthority.CLARIFICATION_ONLY:
        raise InterpretationAuthorityError(
            "锚点解析只能由澄清级解释材料提供；当前修订案应直接修改方案原文"
        )
    if source.formal_change_summary:
        raise InterpretationAuthorityError(
            "携带锚点解析的解释材料不能同时声明正式规则变更"
        )
    if not source.clarifies_ambiguity:
        raise InterpretationAuthorityError(
            "携带锚点解析的解释材料必须明确标注为方案模糊处的补充说明"
        )
    if has_blocking_conflict(source, conflicts):
        raise InterpretationAuthorityError(
            "解释材料与方案或当前修订案存在未解决冲突时不得解析锚点"
        )
    covered = set(source.applies_to_rule_refs)
    for resolution in source.anchor_resolutions:
        if resolution.resolution_mode is not AnchorResolutionMode.CURRENT_REVIEW_NODE_DATE:
            raise InterpretationAuthorityError(
                "锚点解析只能使用当前审核节点日期这一项目无关模式"
            )
        if not set(resolution.affected_rule_refs) <= covered:
            raise InterpretationAuthorityError(
                "锚点解析影响的父规则必须在该解释材料声明的适用范围内"
            )
    return tuple(source.anchor_resolutions)


# Concise aliases for service/gate call sites.
check_interpretation_authority = assess_interpretation_authority
get_interpretation_authority = authority_for_source
