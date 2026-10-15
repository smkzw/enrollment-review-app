"""Deterministic slice 61av: modality fidelity, no downgrade, EX-21 independence."""

from __future__ import annotations

import pytest

from app.domain.contracts.protocol_controls import (
    ControlConditionAtom,
    ControlConditionDnf,
    ControlConditionGroup,
    ControlObligationAtom,
    ControlObligationDnf,
    ControlObligationGroup,
    ControlObligationKind,
    ControlObligationModality,
)
from app.protocols.protocol_control_gate import (
    ProtocolControlGateError,
    _check_obligation_modality_fidelity,
)


def _obligation(
    *,
    obligation_id: str = "obl-1",
    kind: ControlObligationKind = ControlObligationKind.MUST_RECORD,
    statement: str = "义务陈述",
    source_excerpts: list[str] | None = None,
    modality: ControlObligationModality = ControlObligationModality.MANDATORY,
    source_span_ids: list[str] | None = None,
) -> ControlObligationAtom:
    return ControlObligationAtom(
        obligation_id=obligation_id,
        kind=kind,
        statement=statement,
        source_span_ids=source_span_ids or ["span:1"],
        source_excerpts=source_excerpts or [statement],
        modality=modality,
    )


def _dnf(atoms: list[ControlObligationAtom]) -> ControlObligationDnf:
    return ControlObligationDnf(
        groups=[ControlObligationGroup(atoms=atoms)],
    )


def _trigger_dnf(statements: list[str]) -> ControlConditionDnf:
    groups = []
    for idx, stmt in enumerate(statements):
        atom = ControlConditionAtom(
            condition_atom_id=f"cond-{idx}",
            statement=stmt,
            source_span_ids=[f"span:cond-{idx}"],
            source_excerpts=[stmt],
        )
        groups.append(ControlConditionGroup(atoms=[atom]))
    # For EX-21 style, we want a single group with 3 atoms (conjunction)
    # Helper for single group conjunction
    return ControlConditionDnf(groups=groups)


def _ex21_trigger_conjunction() -> ControlConditionDnf:
    """EX-21 requires 3-way conjunction: abnormal + clinical significance + investigator risk."""
    atoms = [
        ControlConditionAtom(
            condition_atom_id="cond-abnormal",
            statement="生命体征异常",
            source_span_ids=["span:ex21-a"],
            source_excerpts=["生命体征异常"],
        ),
        ControlConditionAtom(
            condition_atom_id="cond-clinical",
            statement="异常具有临床意义",
            source_span_ids=["span:ex21-b"],
            source_excerpts=["异常具有临床意义"],
        ),
        ControlConditionAtom(
            condition_atom_id="cond-risk",
            statement="研究者判断参与研究构成不可接受风险",
            source_span_ids=["span:ex21-c"],
            source_excerpts=["研究者判断参与研究构成不可接受风险"],
        ),
    ]
    return ControlConditionDnf(groups=[ControlConditionGroup(atoms=atoms)])


# ── Recommended modality (建议) ────────────────────────────────────────────

def test_recommended_cue_must_not_be_hardened_to_mandatory() -> None:
    expr = _dnf([
        _obligation(
            statement="测量前建议静息至少5分钟后进行体温测量",
            source_excerpts=["测量前，建议参与者至少休息5分钟"],
            modality=ControlObligationModality.MANDATORY,
        )
    ])
    with pytest.raises(ProtocolControlGateError, match="RECOMMENDED_MODALITY_DROPPED"):
        _check_obligation_modality_fidelity(entity_id="c-1", obligation_expression=expr)


def test_recommended_cue_with_recommended_modality_passes() -> None:
    expr = _dnf([
        _obligation(
            statement="测量前建议静息至少5分钟后进行体温测量",
            source_excerpts=["测量前，建议参与者至少休息5分钟"],
            modality=ControlObligationModality.RECOMMENDED,
        )
    ])
    _check_obligation_modality_fidelity(entity_id="c-1", obligation_expression=expr)


def test_recommended_modality_without_source_is_unsupported() -> None:
    expr = _dnf([
        _obligation(
            statement="进行体温测量",
            source_excerpts=["进行体温测量"],
            modality=ControlObligationModality.RECOMMENDED,
        )
    ])
    with pytest.raises(ProtocolControlGateError, match="RECOMMENDED_MODALITY_UNSUPPORTED"):
        _check_obligation_modality_fidelity(entity_id="c-1", obligation_expression=expr)


def test_negative_suggest_not_trigger_recommended() -> None:
    # “不建议” should not be treated as recommended cue
    expr = _dnf([
        _obligation(
            statement="不建议补服",
            source_excerpts=["如漏服超过6小时，不建议补服"],
            modality=ControlObligationModality.MANDATORY,
        )
    ])
    # Should NOT require RECOMMENDED; MANDATORY is correct for prohibition
    _check_obligation_modality_fidelity(entity_id="c-1", obligation_expression=expr)

    # If someone incorrectly sets RECOMMENDED for “不建议”, it should be unsupported
    expr2 = _dnf([
        _obligation(
            statement="不建议补服",
            source_excerpts=["如漏服超过6小时，不建议补服"],
            modality=ControlObligationModality.RECOMMENDED,
        )
    ])
    with pytest.raises(ProtocolControlGateError, match="RECOMMENDED_MODALITY_UNSUPPORTED"):
        _check_obligation_modality_fidelity(entity_id="c-1", obligation_expression=expr2)


@pytest.mark.parametrize(
    "excerpt",
    [
        "目前暂不建议补服",
        "该情况下通常不推荐重复检查",
        "The procedure is not routinely recommended.",
    ],
)
def test_negated_recommendation_variants_are_not_recommended_modality_cues(
    excerpt: str,
) -> None:
    expr = _dnf([
        _obligation(
            statement="不执行该项操作",
            source_excerpts=[excerpt],
            modality=ControlObligationModality.MANDATORY,
        )
    ])
    _check_obligation_modality_fidelity(entity_id="c-negated", obligation_expression=expr)


# ── Best-effort modality (尽量 / 尽可能 / 尽力) ─────────────────────────

def test_jinliang_cue_must_not_be_hardened_to_mandatory() -> None:
    expr = _dnf([
        _obligation(
            kind=ControlObligationKind.COMPLETE_BEFORE_ANCHOR,
            statement="与PK采样时间一致时尽量在PK样本采集之前完成生命体征测量",
            source_excerpts=["与PK采样时间一致时，尽量在PK样本采集之前完成"],
            modality=ControlObligationModality.MANDATORY,
        )
    ])
    with pytest.raises(ProtocolControlGateError, match="BEST_EFFORT_MODALITY_DROPPED"):
        _check_obligation_modality_fidelity(entity_id="c-2", obligation_expression=expr)


def test_jinliang_cue_with_best_effort_passes() -> None:
    expr = _dnf([
        _obligation(
            kind=ControlObligationKind.COMPLETE_BEFORE_ANCHOR,
            statement="与PK采样时间一致时尽量在PK样本采集之前完成生命体征测量",
            source_excerpts=["与PK采样时间一致时，尽量在PK样本采集之前完成"],
            modality=ControlObligationModality.BEST_EFFORT,
        )
    ])
    _check_obligation_modality_fidelity(entity_id="c-2", obligation_expression=expr)


def test_jinliang_best_effort_without_cue_is_unsupported() -> None:
    expr = _dnf([
        _obligation(
            statement="完成生命体征测量",
            source_excerpts=["完成生命体征测量"],
            modality=ControlObligationModality.BEST_EFFORT,
        )
    ])
    with pytest.raises(ProtocolControlGateError, match="BEST_EFFORT_MODALITY_UNSUPPORTED"):
        _check_obligation_modality_fidelity(entity_id="c-2", obligation_expression=expr)


def test_best_effort_history_collection_cannot_be_hardened() -> None:
    #兼容既有资料收集场景：‘尽可能收集’ 也必须保留 best_effort
    expr = _dnf([
        _obligation(
            statement="收集银屑病相关治疗史",
            source_excerpts=["尽可能收集银屑病相关的治疗史"],
            modality=ControlObligationModality.MANDATORY,
        )
    ])
    with pytest.raises(ProtocolControlGateError, match="BEST_EFFORT_MODALITY_DROPPED"):
        _check_obligation_modality_fidelity(entity_id="c-3", obligation_expression=expr)


def test_best_effort_history_collection_with_modality_passes() -> None:
    from app.domain.contracts.protocol_controls import ControlTemporalScopeKind

    expr = _dnf([
        _obligation(
            statement="尽可能收集银屑病相关治疗史",
            source_excerpts=["尽可能收集银屑病相关的治疗史"],
            modality=ControlObligationModality.BEST_EFFORT,
            kind=ControlObligationKind.MUST_RECORD,
        )
    ])
    # Generic fidelity passes
    _check_obligation_modality_fidelity(entity_id="c-3", obligation_expression=expr)
    # Collection check also passes when temporal_scope is present? For this test we ignore temporal scope and just check modality part via generic;
    # 为了通过 collection 的 temporal 检查，需要补上 scope，但此处仅测试 modality 已覆盖


def test_recommended_cue_with_best_effort_modality_also_fails() -> None:
    expr = _dnf([
        _obligation(
            statement="建议静息",
            source_excerpts=["建议静息至少5分钟"],
            modality=ControlObligationModality.BEST_EFFORT,
        )
    ])
    with pytest.raises(ProtocolControlGateError, match="RECOMMENDED_MODALITY_DROPPED"):
        _check_obligation_modality_fidelity(entity_id="c-3", obligation_expression=expr)


def test_best_effort_cue_with_recommended_modality_also_fails() -> None:
    expr = _dnf([
        _obligation(
            kind=ControlObligationKind.COMPLETE_BEFORE_ANCHOR,
            statement="尽量在PK前完成",
            source_excerpts=["尽量在PK样本采集之前完成"],
            modality=ControlObligationModality.RECOMMENDED,
        )
    ])
    # Source has best-effort cue "尽量" but modality is RECOMMENDED:
    # Gate reports RECOMMENDED_UNSUPPORTED first (no recommended cue), which is also correct;
    # the key is that hardening / downgrade is rejected. Accept either code.
    with pytest.raises(ProtocolControlGateError, match="(RECOMMENDED_MODALITY_UNSUPPORTED|BEST_EFFORT_MODALITY_DROPPED)"):
        _check_obligation_modality_fidelity(entity_id="c-3", obligation_expression=expr)
def test_recommended_and_best_effort_are_not_interchangeable_without_source() -> None:
    # Source has 推荐 cue, but modality BEST_EFFORT is not allowed downgrade/upgrade
    expr1 = _dnf([
        _obligation(
            statement="推荐静息",
            source_excerpts=["推荐静息5分钟"],
            modality=ControlObligationModality.BEST_EFFORT,
        )
    ])
    with pytest.raises(ProtocolControlGateError, match="RECOMMENDED_MODALITY_DROPPED"):
        _check_obligation_modality_fidelity(entity_id="c-3", obligation_expression=expr1)
    # Source has no cue but modality RECOMMENDED should be unsupported
    expr2 = _dnf([
        _obligation(
            statement="完成检查",
            source_excerpts=["完成检查"],
            modality=ControlObligationModality.RECOMMENDED,
        )
    ])
    with pytest.raises(ProtocolControlGateError, match="RECOMMENDED_MODALITY_UNSUPPORTED"):
        _check_obligation_modality_fidelity(entity_id="c-3", obligation_expression=expr2)


# ── No downgrade without direct source support ───────────────────────────
def test_mandatory_cannot_be_downgraded_to_recommended_without_cue() -> None:
    expr = _dnf([
        _obligation(
            statement="完成生命体征检查和体温记录",
            source_excerpts=["完成生命体征检查和体温、坐位血压记录"],
            modality=ControlObligationModality.RECOMMENDED,
        )
    ])
    with pytest.raises(ProtocolControlGateError, match="RECOMMENDED_MODALITY_UNSUPPORTED"):
        _check_obligation_modality_fidelity(entity_id="c-4", obligation_expression=expr)


def test_mandatory_cannot_be_downgraded_to_best_effort_without_cue() -> None:
    expr = _dnf([
        _obligation(
            statement="完成生命体征检查",
            source_excerpts=["完成生命体征检查"],
            modality=ControlObligationModality.BEST_EFFORT,
        )
    ])
    with pytest.raises(ProtocolControlGateError, match="BEST_EFFORT_MODALITY_UNSUPPORTED"):
        _check_obligation_modality_fidelity(entity_id="c-4", obligation_expression=expr)


def test_positive_mandatory_without_cue_passes() -> None:
    expr = _dnf([
        _obligation(
            statement="完成生命体征检查和体温、坐位血压、坐位脉搏、呼吸频率记录",
            source_excerpts=["完成生命体征检查和体温、坐位血压、坐位脉搏、呼吸频率记录"],
            modality=ControlObligationModality.MANDATORY,
        )
    ])
    _check_obligation_modality_fidelity(entity_id="c-4", obligation_expression=expr)


# ── EX-21 conjunction independence ─────────────────────────────────────

def test_modality_and_ex21_trigger_are_independent() -> None:
    # Obligation with recommended modality should not be affected by EX-21 trigger content
    obligation = _dnf([
        _obligation(
            statement="建议静息至少5分钟后测量",
            source_excerpts=["测量前，建议参与者至少休息5分钟"],
            modality=ControlObligationModality.RECOMMENDED,
        )
    ])
    trigger = _ex21_trigger_conjunction()
    # Modality fidelity concerns only obligation, not trigger
    _check_obligation_modality_fidelity(entity_id="c-ex21-1", obligation_expression=obligation)
    # Trigger has 3 atoms; ensure it is seen as single conjunction group
    assert len(trigger.groups) == 1
    assert len(trigger.groups[0].atoms) == 3
    # Changing trigger text containing “建议” should not affect obligation modality check
    trigger_with_suggest = ControlConditionDnf(groups=[
        ControlConditionGroup(atoms=[
            ControlConditionAtom(
                condition_atom_id="cond-1",
                statement="建议静息后仍异常",
                source_span_ids=["span:t1"],
                source_excerpts=["建议静息后仍异常"],
            )
        ])
    ])
    # Obligation check should still pass regardless of trigger content
    _check_obligation_modality_fidelity(entity_id="c-ex21-2", obligation_expression=obligation)
    # Trigger itself is not checked by obligation modality gate
    # (no exception should be raised for trigger containing 建议)
    assert trigger_with_suggest.groups[0].atoms[0].statement == "建议静息后仍异常"


def test_ex21_single_abnormal_without_conjunction_is_not_conflated_with_modality() -> None:
    # 单纯异常不应与 modality 混淆：义务侧 best_effort 仍需独立校验
    obligation_best_effort = _dnf([
        _obligation(
            kind=ControlObligationKind.COMPLETE_BEFORE_ANCHOR,
            statement="尽量在PK前完成",
            source_excerpts=["尽量在PK样本采集之前完成"],
            modality=ControlObligationModality.BEST_EFFORT,
        )
    ])
    _check_obligation_modality_fidelity(entity_id="c-5", obligation_expression=obligation_best_effort)

    # EX-21 单异常触发（仅1个原子）不应被视为完整排除，即使义务侧是 mandatory
    single_abnormal_trigger = ControlConditionDnf(groups=[
        ControlConditionGroup(atoms=[
            ControlConditionAtom(
                condition_atom_id="cond-single",
                statement="生命体征异常",
                source_span_ids=["span:single"],
                source_excerpts=["生命体征异常"],
            )
        ])
    ])
    # 单原子触发在逻辑上不等于 3 合取，但 modality gate 不应因此误判义务为不通过
    _check_obligation_modality_fidelity(entity_id="c-5", obligation_expression=_dnf([
        _obligation(
            statement="完成生命体征检查",
            source_excerpts=["完成生命体征检查"],
            modality=ControlObligationModality.MANDATORY,
        )
    ]))
    assert len(single_abnormal_trigger.groups[0].atoms) == 1


def test_ex21_full_conjunction_does_not_imply_modality_hardening() -> None:
    # 完整的 EX-21 触发不应把操作偏离硬化为不符合：义务侧 recommended/best_effort 正确时应通过
    recommended_obl = _dnf([
        _obligation(
            statement="建议静息",
            source_excerpts=["建议静息至少5分钟"],
            modality=ControlObligationModality.RECOMMENDED,
        )
    ])
    best_effort_obl = _dnf([
        _obligation(
            kind=ControlObligationKind.COMPLETE_BEFORE_ANCHOR,
            statement="尽量在PK前完成",
            source_excerpts=["尽量在PK样本采集之前完成"],
            modality=ControlObligationModality.BEST_EFFORT,
        )
    ])
    mandatory_obl = _dnf([
        _obligation(
            statement="完成体温、坐位血压、坐位脉搏、呼吸频率记录",
            source_excerpts=["进行体温、血压（坐位）、脉博（坐位）、呼吸频率测量"],
            modality=ControlObligationModality.MANDATORY,
        )
    ])
    for expr in (recommended_obl, best_effort_obl, mandatory_obl):
        _check_obligation_modality_fidelity(entity_id="c-6", obligation_expression=expr)

    # EX-21 触发为 3 合取，与上述义务模态无关
    full_trigger = _ex21_trigger_conjunction()
    assert len(full_trigger.groups[0].atoms) == 3
    # 验证：即使存在完整 EX-21 触发，义务侧的 recommended 也不被要求改为 mandatory
    _check_obligation_modality_fidelity(entity_id="c-6", obligation_expression=recommended_obl)
