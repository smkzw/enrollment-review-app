"""节点相对回溯窗口机制的词汇中立合同、门禁与提示框架测试。

合成方案使用通用词汇（“目标既往疾病”），窗口量（2 个月）仅作为测试数据
来自“方案原文”，不构成任何共享代码常量；不出现任何项目特定疾病、编号
或固定窗口。覆盖：

- 合同类：``review_node_date`` 锚点的 on 约束拒绝；锚点解析声明的权威边界；
- 领域类：``clarification_anchor_resolutions`` 的失败关闭路径；
- 门禁类：无解释仍 ``TIME_ANCHOR_UNRESOLVED``、合法解析放行、越权/错配/
  目标节点缺失/资料要求缺口全部失败关闭；
- 输入合同与装配：解释来源必须整体携带且 ID 集合一致；
- 提示框架：解释澄清专用区与方案原文区分离。
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from app.domain.contracts.agent_io import (
    EvidenceRequirementDraft,
    ParentRuleCatalogMapping,
    ProcedureCatalogMapping,
    ProtocolDeconstructionDraft,
    ProtocolDeconstructionInput,
    ProtocolMetadataDraft,
    ProtocolSourceMaterial,
    RuleComponentDraft,
)
from app.domain.contracts.common import DateValue
from app.domain.contracts.enums import (
    AlignmentStatus,
    AnchorResolutionMode,
    AnchorType,
    CatalogItemKind,
    CatalogKind,
    Comparator,
    DatePrecision,
    DocumentPart,
    FactPolarity,
    InterpretationAuthority,
    InterpretationConflictStatus,
    InterpretationSourceType,
    LogicalOperator,
    MetadataResolutionStatus,
    ReviewStage,
    RuleKind,
    SourceLocatorPrecision,
    StudyPhase,
    TimeDirection,
    TruthValue,
)
from app.domain.contracts.evidence import ClinicalFact
from app.domain.contracts.normalization import CoverageSummary
from app.domain.contracts.protocol_ingestion import (
    FrozenCatalogItem,
    FrozenProtocolCatalog,
    ProtocolSourceSpan,
)
from app.domain.contracts.protocol_metadata import (
    AnchorResolutionStatement,
    InterpretationConflict,
    InterpretationSource,
    ProtocolIdentityDecision,
    StudyPhaseSelection,
)
from app.domain.contracts.rules import (
    AtomicExpression,
    AtomicPredicate,
    EvidenceRequirement,
    Rule,
    RuleComponent,
    TimeConstraint,
    TimeQuantity,
    TimeUnit,
    WorkflowStage,
)
from app.domain.interpretation import (
    InterpretationAuthorityError,
    clarification_anchor_resolutions,
)
from app.domain.expression import EvaluationContext, evaluate_expression
from app.domain.publication import canonical_hash
from app.agents.protocol_deconstructor import (
    _wire_time_constraint_schema,
    build_protocol_deconstruction_prompt,
    protocol_prompt_template_sha256,
)
from app.protocols.deconstruction_gate import ProtocolDeconstructionGate
from app.protocols.deconstruction_service import (
    ProtocolDeconstructionInputAssemblyError,
    ProtocolDeconstructionInputAssembler,
)


NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)
SHA = "a" * 64

# 合成方案原文：未命名回溯锚点 + 通用条件词汇（仅测试数据）。
AMBIGUOUS_TEXT = "既往2个月内存在目标既往疾病史"
NAMED_TEXT = "年龄≥18岁的受试者"


# ---------------------------------------------------------------------------
# 合同层
# ---------------------------------------------------------------------------


def _resolution(**overrides) -> AnchorResolutionStatement:
    payload = {
        "resolution_id": "res-1",
        "affected_rule_refs": ["EX-01"],
        "ambiguous_source_refs": ["span-ex"],
        "target_review_stages": [ReviewStage.SCREENING, ReviewStage.BASELINE],
        "resolution_mode": AnchorResolutionMode.CURRENT_REVIEW_NODE_DATE,
    }
    payload.update(overrides)
    return AnchorResolutionStatement(**payload)


def _source(**overrides) -> InterpretationSource:
    payload = {
        "interpretation_source_id": "interp-1",
        "protocol_version_id": "protocol-version-1",
        "source_type": InterpretationSourceType.QA,
        "file_sha256": "b" * 64,
        "source_ref": "qa-ref-1",
        "excerpt": "问：既往2个月内的疾病史从哪一天起算？",
        "explanation": "未命名回溯锚点按当前审核节点日期计算，筛选与基线分别评判。",
        "applies_to_rule_refs": ["EX-01"],
        "clarifies_ambiguity": True,
        "anchor_resolutions": [_resolution()],
    }
    payload.update(overrides)
    return InterpretationSource(**payload)


def test_review_node_date_rejects_on_direction_at_contract_level():
    with pytest.raises(ValidationError, match="审核节点日期锚点不能用作 on 同日约束"):
        TimeConstraint(
            anchor_type=AnchorType.REVIEW_NODE_DATE,
            direction=TimeDirection.ON,
        )


def test_review_node_date_before_window_is_contract_valid():
    constraint = TimeConstraint(
        anchor_type=AnchorType.REVIEW_NODE_DATE,
        direction=TimeDirection.BEFORE,
        upper_bound=TimeQuantity(value=2, unit=TimeUnit.MONTH),
    )
    assert constraint.anchor_type == AnchorType.REVIEW_NODE_DATE


def test_review_node_date_is_evaluated_independently_per_episode():
    expression = AtomicExpression(
        predicate=AtomicPredicate(
            predicate_id="predicate-history",
            subject="history",
            attribute="event_present",
            comparator=Comparator.EQ,
            value=True,
            source_clause=AMBIGUOUS_TEXT,
        ),
        time_constraint=TimeConstraint(
            anchor_type=AnchorType.REVIEW_NODE_DATE,
            direction=TimeDirection.BEFORE,
            upper_bound=TimeQuantity(value=2, unit=TimeUnit.MONTH),
        ),
    )

    def evaluate_episode(episode_id: str, anchor: date | None):
        fact_id = f"fact-{episode_id}"
        fact = ClinicalFact(
            fact_id=fact_id,
            project_id="project-1",
            subject_id="subject-1",
            review_episode_id=episode_id,
            evidence_snapshot_id=f"snapshot-{episode_id}",
            fact_type="history.event_present",
            value=True,
            polarity=FactPolarity.AFFIRMED,
            certainty=1,
            effective_date=DateValue(
                value=date(2026, 7, 15), precision=DatePrecision.DAY
            ),
            evidence_span_ids=[f"span-{episode_id}"],
        )
        return evaluate_expression(
            expression,
            EvaluationContext(
                project_id="project-1",
                subject_id="subject-1",
                review_episode_id=episode_id,
                evidence_snapshot_id=f"snapshot-{episode_id}",
                accepted_fact_ids=[fact_id],
                facts=[fact],
                anchor_dates=(
                    {
                        AnchorType.REVIEW_NODE_DATE: DateValue(
                            value=anchor, precision=DatePrecision.DAY
                        )
                    }
                    if anchor is not None
                    else {}
                ),
            ),
        )

    screening = evaluate_episode("episode-screening", date(2026, 9, 1))
    baseline = evaluate_episode("episode-baseline", date(2026, 10, 1))
    missing = evaluate_episode("episode-missing", None)

    assert screening.truth is TruthValue.TRUE
    assert baseline.truth is TruthValue.FALSE
    assert "above_time_window" in baseline.reason_codes
    assert missing.truth is TruthValue.UNKNOWN
    assert "date_or_anchor_missing" in missing.reason_codes


def test_anchor_resolution_cannot_carry_window_or_threshold_payload():
    # 结构性保证：解析合同没有窗口/方向/阈值字段，多余字段直接被拒。
    with pytest.raises(ValidationError):
        AnchorResolutionStatement(
            resolution_id="res-x",
            affected_rule_refs=["EX-01"],
            ambiguous_source_refs=["span-ex"],
            target_review_stages=[ReviewStage.SCREENING],
            resolution_mode=AnchorResolutionMode.CURRENT_REVIEW_NODE_DATE,
            upper_bound=TimeQuantity(value=2, unit=TimeUnit.MONTH),
        )


def test_amendment_source_cannot_carry_anchor_resolutions():
    with pytest.raises(ValidationError, match="澄清级"):
        _source(
            source_type=InterpretationSourceType.AMENDMENT,
            is_current_amendment=True,
        )


def test_unmarked_clarification_cannot_carry_anchor_resolutions():
    with pytest.raises(ValidationError, match="模糊处"):
        _source(clarifies_ambiguity=False)


def test_resolution_rule_ref_outside_declared_scope_is_rejected():
    with pytest.raises(ValidationError, match="适用范围"):
        _source(applies_to_rule_refs=["IN-01"])


def test_duplicate_target_review_stages_are_rejected():
    with pytest.raises(ValidationError, match="不得重复"):
        _resolution(
            target_review_stages=[ReviewStage.BASELINE, ReviewStage.BASELINE]
        )


def test_valid_resolution_source_keeps_clarification_authority():
    source = _source()
    assert source.authority == InterpretationAuthority.CLARIFICATION_ONLY


# ---------------------------------------------------------------------------
# 领域层：确定性权威检查
# ---------------------------------------------------------------------------


def _conflict_for(source: InterpretationSource) -> InterpretationConflict:
    return InterpretationConflict(
        conflict_id="conflict-1",
        protocol_version_id=source.protocol_version_id,
        interpretation_source_id=source.interpretation_source_id,
        affected_rule_refs=["EX-01"],
        protocol_source_refs=["span-ex"],
        reason="解释与方案正式条款冲突",
        impact="相关条款停在需要核对状态",
    )


def test_clarification_anchor_resolutions_returns_valid_bindings():
    source = _source()
    resolutions = clarification_anchor_resolutions(source)
    assert [item.resolution_id for item in resolutions] == ["res-1"]


def test_clarification_anchor_resolutions_empty_without_payload():
    assert clarification_anchor_resolutions(_source(anchor_resolutions=[])) == ()


def test_clarification_anchor_resolutions_fail_closed_on_open_conflict():
    source = _source()
    with pytest.raises(InterpretationAuthorityError, match="未解决冲突"):
        clarification_anchor_resolutions(source, conflicts=[_conflict_for(source)])


def test_clarification_anchor_resolutions_fail_closed_on_formal_change_summary():
    # formal_change_summary + 解析在合同层已被拒；此处直接验证领域检查的
    # 同等失败关闭（防御构造绕过）。
    source = _source().model_construct(
        **{
            **_source().model_dump(mode="python"),
            "formal_change_summary": "试图改写正式要求",
            "authority": InterpretationAuthority.CLARIFICATION_ONLY,
        }
    )
    with pytest.raises(InterpretationAuthorityError, match="正式规则变更"):
        clarification_anchor_resolutions(source)


# ---------------------------------------------------------------------------
# 门禁夹具（词汇中立合成方案）
# ---------------------------------------------------------------------------


def _catalog(kind, items):
    payload = {
        "catalog_id": f"catalog:{kind.value}",
        "snapshot_id": "snapshot-1",
        "catalog_kind": kind,
        "study_phase": StudyPhase.PHASE_II,
        "items": tuple(items),
        "frozen_at": NOW,
        "frozen_by": "deterministic_extractor/v1",
    }
    unhashed = FrozenProtocolCatalog.model_construct(
        **payload, catalog_sha256="0" * 64
    )
    payload["catalog_sha256"] = canonical_hash(
        unhashed.model_dump(mode="json", exclude={"catalog_sha256"})
    )
    return FrozenProtocolCatalog(**payload)


def _span(span_id, order):
    return ProtocolSourceSpan(
        source_span_id=span_id,
        snapshot_id="snapshot-1",
        source_ref=f"body.p{order}",
        document_part=DocumentPart.BODY,
        section_index=0,
        block_order=order,
        render_artifact_id="render-1",
        render_page=order + 1,
        text_start=0,
        text_end=10,
        excerpt="正式方案原文",
        precision=SourceLocatorPrecision.TEXT_RANGE,
        alignment_status=AlignmentStatus.ALIGNED,
        degradation_reason=None,
    )


def _numeric_predicate(pid, attribute, value, unit, *, source_clause):
    return AtomicExpression(
        predicate=AtomicPredicate(
            predicate_id=pid,
            subject="受试者",
            attribute=attribute,
            source_term=attribute,
            source_clause=source_clause,
            comparator=Comparator.GTE,
            value=value,
            unit=unit,
            requires_professional_judgment=False,
        ),
        time_constraint=None,
    )


def _lookback_predicate(pid, *, source_clause):
    return AtomicExpression(
        predicate=AtomicPredicate(
            predicate_id=pid,
            subject="受试者",
            attribute="目标既往疾病史",
            source_term="目标既往疾病史",
            source_clause=source_clause,
            comparator=Comparator.EXISTS,
            value=None,
            unit="unitless",
            requires_professional_judgment=False,
        ),
        time_constraint=None,
    )


def _requirement(rid, component_id, stage):
    return EvidenceRequirement(
        requirement_id=rid,
        rule_component_id=component_id,
        fact_type="方案要求事实",
        due_stage=stage,
        description="核对正式原始资料和研究者记录",
    )


def _fixture():
    """最小合成草稿：EX-01 携带未命名回溯缺口，IN-01 为普通数值条件。"""

    parent_items = [
        FrozenCatalogItem(
            item_id="parent:in01",
            kind=CatalogItemKind.PARENT_RULE,
            official_code="IN-01",
            label=NAMED_TEXT,
            position=0,
            source_span_ids=["span-in"],
        ),
        FrozenCatalogItem(
            item_id="parent:ex01",
            kind=CatalogItemKind.PARENT_RULE,
            official_code="EX-01",
            label=AMBIGUOUS_TEXT,
            position=1,
            source_span_ids=["span-ex"],
        ),
    ]
    procedure_items = [
        FrozenCatalogItem(
            item_id="procedure:screening:lab",
            kind=CatalogItemKind.REQUIRED_PROCEDURE,
            label="常规检查",
            visit_instance="筛选期 D-28~D-1",
            review_stage=ReviewStage.SCREENING,
            position=0,
            source_span_ids=["span-proc-screen"],
        ),
        FrozenCatalogItem(
            item_id="procedure:baseline:lab",
            kind=CatalogItemKind.REQUIRED_PROCEDURE,
            label="常规检查",
            visit_instance="基线 D1",
            review_stage=ReviewStage.BASELINE,
            position=1,
            source_span_ids=["span-proc-base"],
        ),
    ]
    identity = ProtocolIdentityDecision(
        identity_decision_id="identity-1",
        snapshot_id="snapshot-1",
        project_name="合成研究",
        project_code="SYN",
        protocol_code="SYN-001",
        official_version="V1.0",
        official_date=DateValue(
            value=date(2026, 9, 1), precision=DatePrecision.DAY
        ),
        study_phase=StudyPhase.PHASE_II,
        selected_candidate_ids=["candidate-1"],
        status=MetadataResolutionStatus.CONFIRMED,
        confirmation_required=False,
        confirmed_by="医学监查员",
        confirmed_at=NOW,
    )
    selection = StudyPhaseSelection(
        selection_id="phase-selection-1",
        snapshot_id="snapshot-1",
        selected_phase=StudyPhase.PHASE_II,
        candidate_ids=["phase-candidate-1"],
        status=MetadataResolutionStatus.CONFIRMED,
        confirmed_by="医学监查员",
        confirmed_at=NOW,
    )
    source_spans = {
        "span-in": _span("span-in", 1),
        "span-ex": _span("span-ex", 2),
        "span-proc-screen": _span("span-proc-screen", 3),
        "span-proc-base": _span("span-proc-base", 4),
    }
    source_input = ProtocolDeconstructionInput(
        project_id="project-1",
        protocol_version_id="protocol-version-1",
        protocol_file_sha256=SHA,
        extraction_snapshot_id="snapshot-1",
        phase_projection_id="projection-1",
        selected_phase=StudyPhase.PHASE_II,
        identity_decision=identity,
        phase_selection=selection,
        allowed_source_span_ids=list(source_spans),
        source_materials=[
            ProtocolSourceMaterial(
                source_span_id=span_id,
                source_ref=span.source_ref,
                block_order=span.block_order,
                text={
                    "span-in": NAMED_TEXT,
                    "span-ex": AMBIGUOUS_TEXT,
                    "span-proc-screen": "筛选期常规检查",
                    "span-proc-base": "基线常规检查",
                }[span_id],
            )
            for span_id, span in source_spans.items()
        ],
        parent_rule_catalog=_catalog(
            CatalogKind.OFFICIAL_PARENT_RULES, parent_items
        ),
        required_procedure_catalog=_catalog(
            CatalogKind.REQUIRED_PROCEDURES, procedure_items
        ),
    )

    in_component = RuleComponent(
        rule_component_id="component-in",
        parent_rule_id="rule-in",
        display_code="IN-01a",
        title="年龄要求",
        expression=_numeric_predicate(
            "predicate-age", "年龄", 18, "岁", source_clause=NAMED_TEXT
        ),
        evidence_requirements=[_requirement("req-in", "component-in", ReviewStage.SCREENING)],
    )
    ex_component = RuleComponent(
        rule_component_id="component-ex",
        parent_rule_id="rule-ex",
        display_code="EX-01a",
        title="既往疾病条件",
        expression=_lookback_predicate(
            "predicate-past-condition", source_clause=AMBIGUOUS_TEXT
        ),
        evidence_requirements=[
            _requirement("req-ex-screen", "component-ex", ReviewStage.SCREENING),
            _requirement("req-ex-base", "component-ex", ReviewStage.BASELINE),
        ],
    )
    rules = [
        Rule(
            rule_id="rule-in",
            official_code="IN-01",
            kind=RuleKind.INCLUSION,
            source_text=NAMED_TEXT,
            study_phase=StudyPhase.PHASE_II,
            components=[in_component],
        ),
        Rule(
            rule_id="rule-ex",
            official_code="EX-01",
            kind=RuleKind.EXCLUSION,
            source_text=AMBIGUOUS_TEXT,
            study_phase=StudyPhase.PHASE_II,
            components=[ex_component],
        ),
    ]
    draft = ProtocolDeconstructionDraft(
        draft_id="draft-1",
        project_id="project-1",
        protocol_version_id="protocol-version-1",
        selected_phase=StudyPhase.PHASE_II,
        draft_revision=1,
        proposed_rules=rules,
        proposed_workflow_stages=[
            WorkflowStage(
                workflow_stage_id="stage-screening",
                stage=ReviewStage.SCREENING,
                display_name="筛选期审核",
                visit_instance="筛选期 D-28~D-1",
                due_requirement_ids=[
                    "req-in",
                    "req-ex-screen",
                    "req-proc-screen",
                ],
            ),
            WorkflowStage(
                workflow_stage_id="stage-baseline",
                stage=ReviewStage.BASELINE,
                display_name="基线审核",
                visit_instance="基线 D1",
                due_requirement_ids=["req-ex-base", "req-proc-base"],
            ),
        ],
        protocol_metadata=ProtocolMetadataDraft(
            protocol_code_candidate="SYN-001",
            title_candidate="合成研究",
            version_candidate="V1.0",
            date_candidate="2026-09-01",
            study_phase_candidates=["Ⅱ期"],
            source_refs=["span-in"],
        ),
        component_drafts=[
            RuleComponentDraft(
                draft_component_id="draft-component-in",
                parent_official_code="IN-01",
                proposed_component=in_component,
                source_refs=["span-in"],
                source_excerpts=[NAMED_TEXT],
            ),
            RuleComponentDraft(
                draft_component_id="draft-component-ex",
                parent_official_code="EX-01",
                proposed_component=ex_component,
                source_refs=["span-ex"],
                source_excerpts=[AMBIGUOUS_TEXT],
            ),
        ],
        evidence_requirement_drafts=[
            EvidenceRequirementDraft(
                draft_requirement_id="draft-req-in",
                draft_component_id="draft-component-in",
                proposed_requirement=in_component.evidence_requirements[0],
                source_refs=["span-in"],
            ),
            EvidenceRequirementDraft(
                draft_requirement_id="draft-req-ex-screen",
                draft_component_id="draft-component-ex",
                proposed_requirement=ex_component.evidence_requirements[0],
                source_refs=["span-ex"],
            ),
            EvidenceRequirementDraft(
                draft_requirement_id="draft-req-ex-base",
                draft_component_id="draft-component-ex",
                proposed_requirement=ex_component.evidence_requirements[1],
                source_refs=["span-ex"],
            ),
            EvidenceRequirementDraft(
                draft_requirement_id="draft-proc-screen",
                procedure_catalog_item_id="procedure:screening:lab",
                proposed_requirement=EvidenceRequirement(
                    requirement_id="req-proc-screen",
                    procedure_catalog_item_id="procedure:screening:lab",
                    fact_type="方案要求事实",
                    due_stage=ReviewStage.SCREENING,
                    description="核对正式原始资料和研究者记录",
                ),
                source_refs=["span-proc-screen"],
            ),
            EvidenceRequirementDraft(
                draft_requirement_id="draft-proc-base",
                procedure_catalog_item_id="procedure:baseline:lab",
                proposed_requirement=EvidenceRequirement(
                    requirement_id="req-proc-base",
                    procedure_catalog_item_id="procedure:baseline:lab",
                    fact_type="方案要求事实",
                    due_stage=ReviewStage.BASELINE,
                    description="核对正式原始资料和研究者记录",
                ),
                source_refs=["span-proc-base"],
            ),
        ],
        parent_catalog_mappings=[
            ParentRuleCatalogMapping(
                catalog_item_id="parent:in01",
                proposed_rule_id="rule-in",
                source_span_ids=["span-in"],
            ),
            ParentRuleCatalogMapping(
                catalog_item_id="parent:ex01",
                proposed_rule_id="rule-ex",
                source_span_ids=["span-ex"],
            ),
        ],
        procedure_catalog_mappings=[
            ProcedureCatalogMapping(
                catalog_item_id="procedure:screening:lab",
                proposed_requirement_ids=["req-proc-screen"],
                proposed_workflow_stage_id="stage-screening",
                source_span_ids=["span-proc-screen"],
            ),
            ProcedureCatalogMapping(
                catalog_item_id="procedure:baseline:lab",
                proposed_requirement_ids=["req-proc-base"],
                proposed_workflow_stage_id="stage-baseline",
                source_span_ids=["span-proc-base"],
            ),
        ],
        coverage=CoverageSummary(
            processed_refs=["span-in", "span-ex", "span-proc-screen", "span-proc-base"],
            missing_refs=[],
            duplicate_refs=[],
        ),
        source_refs=["span-in", "span-ex", "span-proc-screen", "span-proc-base"],
        created_by_agent_call_id="call-1",
    )
    return source_input, draft, source_spans


def _issues(result, check_name):
    return next(
        item.issues for item in result.checks if item.check_name == check_name
    )


def _review_node_constraint(**bounds) -> TimeConstraint:
    payload = {
        "upper_bound": TimeQuantity(value=2, unit=TimeUnit.MONTH),
    }
    payload.update(bounds)
    return TimeConstraint(
        anchor_type=AnchorType.REVIEW_NODE_DATE,
        direction=TimeDirection.BEFORE,
        **payload,
    )


def _bind_review_node_constraint(draft):
    component = draft.proposed_rules[1].components[0]
    component.expression.time_constraint = _review_node_constraint()
    return component


def _interpretation_input(source_input, *sources):
    return source_input.model_copy(
        update={
            "interpretation_source_ids": [
                item.interpretation_source_id for item in sources
            ],
            "interpretation_sources": list(sources),
        }
    )


# ---------------------------------------------------------------------------
# 门禁：无解释仍失败关闭
# ---------------------------------------------------------------------------


def test_no_interpretation_still_reports_time_anchor_unresolved():
    source_input, draft, spans = _fixture()
    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert any(
        issue.issue_code == "TIME_ANCHOR_UNRESOLVED"
        for issue in _issues(result, "temporal_semantics")
    )
    assert not result.publishable


def test_review_node_anchor_without_interpretation_is_rejected():
    source_input, draft, spans = _fixture()
    _bind_review_node_constraint(draft)
    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    codes = {issue.issue_code for issue in _issues(result, "temporal_semantics")}
    assert "INTERPRETATION_ANCHOR_REJECTED" in codes
    assert not any(
        issue.issue_code == "TIME_ANCHOR_UNRESOLVED"
        for issue in _issues(result, "temporal_semantics")
    )
    assert not result.publishable


# ---------------------------------------------------------------------------
# 门禁：合法解释解析放行
# ---------------------------------------------------------------------------


def test_valid_resolution_publishes_single_condition_with_multi_node_requirements():
    source_input, draft, spans = _fixture()
    _bind_review_node_constraint(draft)
    bound_input = _interpretation_input(source_input, _source())
    result = ProtocolDeconstructionGate().evaluate(
        bound_input, draft, source_spans=spans
    )
    temporal = _issues(result, "temporal_semantics")
    assert temporal == []
    assert not any(
        issue.issue_code == "TIME_ANCHOR_UNRESOLVED" for issue in temporal
    )
    # 正式条件保持单一：原子条件仍只有一个，逐节点义务由既有 due_stage
    # 资料要求（screening + baseline）承载。
    assert len(draft.proposed_rules[1].components) == 1
    assert result.publishable


def test_resolution_without_constraint_keeps_unresolved_state():
    source_input, draft, spans = _fixture()
    bound_input = _interpretation_input(source_input, _source())
    result = ProtocolDeconstructionGate().evaluate(
        bound_input, draft, source_spans=spans
    )
    assert any(
        issue.issue_code == "TIME_ANCHOR_UNRESOLVED"
        for issue in _issues(result, "temporal_semantics")
    )
    assert not result.publishable


def test_review_node_anchor_after_direction_is_rejected():
    source_input, draft, spans = _fixture()
    component = draft.proposed_rules[1].components[0]
    component.expression.time_constraint = TimeConstraint(
        anchor_type=AnchorType.REVIEW_NODE_DATE,
        direction=TimeDirection.AFTER,
        upper_bound=TimeQuantity(value=2, unit=TimeUnit.MONTH),
    )
    bound_input = _interpretation_input(source_input, _source())
    result = ProtocolDeconstructionGate().evaluate(
        bound_input, draft, source_spans=spans
    )
    assert any(
        issue.issue_code == "INTERPRETATION_ANCHOR_REJECTED"
        for issue in _issues(result, "temporal_semantics")
    )


def test_review_node_window_must_stay_verbatim_from_source():
    source_input, draft, spans = _fixture()
    component = draft.proposed_rules[1].components[0]
    # 原文是 2 个月，模型试图写 3 个月——解释不得改写窗口量。
    component.expression.time_constraint = _review_node_constraint(
        upper_bound=TimeQuantity(value=3, unit=TimeUnit.MONTH)
    )
    bound_input = _interpretation_input(source_input, _source())
    result = ProtocolDeconstructionGate().evaluate(
        bound_input, draft, source_spans=spans
    )
    codes = {issue.issue_code for issue in _issues(result, "temporal_semantics")}
    assert {"TIME_BOUND_NOT_IN_SOURCE", "TIME_BOUND_UNIT_CHANGED"} <= codes


# ---------------------------------------------------------------------------
# 门禁：解释越权 / 错配 / 目标节点缺失
# ---------------------------------------------------------------------------


def test_open_conflict_fails_closed_and_rejects_anchor_resolution():
    source_input, draft, spans = _fixture()
    _bind_review_node_constraint(draft)
    source = _source()
    bound_input = _interpretation_input(source_input, source)
    result = ProtocolDeconstructionGate().evaluate(
        bound_input,
        draft,
        source_spans=spans,
        interpretation_conflicts=[_conflict_for(source)],
    )
    assert any(
        issue.issue_code == "INTERPRETATION_CONFLICT_OPEN"
        for issue in _issues(result, "interpretation_authority")
    )
    rejected = [
        issue
        for check in result.checks
        for issue in check.issues
        if issue.issue_code == "INTERPRETATION_ANCHOR_REJECTED"
    ]
    assert rejected
    assert not result.publishable


def test_resolution_claiming_rule_without_gap_is_overreach():
    source_input, draft, spans = _fixture()
    _bind_review_node_constraint(draft)
    # 解析声明 IN-01，但 IN-01 的原文锚点明确（随机前）——解释越权。
    overreach = _source(
        anchor_resolutions=[
            _resolution(
                resolution_id="res-over",
                affected_rule_refs=["IN-01"],
                ambiguous_source_refs=["span-in"],
            )
        ],
        applies_to_rule_refs=["IN-01", "EX-01"],
    )
    bound_input = _interpretation_input(source_input, overreach)
    result = ProtocolDeconstructionGate().evaluate(
        bound_input, draft, source_spans=spans
    )
    assert any(
        "没有未命名回溯缺口" in issue.problem
        for issue in _issues(result, "temporal_semantics")
    )
    assert not result.publishable


def test_resolution_targeting_missing_review_node_is_rejected():
    source_input, draft, spans = _fixture()
    _bind_review_node_constraint(draft)
    phantom = _source(
        anchor_resolutions=[
            _resolution(
                target_review_stages=[
                    ReviewStage.SCREENING,
                    ReviewStage.RUN_IN,
                ]
            )
        ]
    )
    bound_input = _interpretation_input(source_input, phantom)
    result = ProtocolDeconstructionGate().evaluate(
        bound_input, draft, source_spans=spans
    )
    assert any(
        "目标审核节点" in issue.problem and "不存在" in issue.problem
        for issue in _issues(result, "temporal_semantics")
    )


def test_resolution_binding_wrong_source_ref_is_rejected():
    source_input, draft, spans = _fixture()
    _bind_review_node_constraint(draft)
    # 解析声明的歧义来源是 span-in，而缺口条款在 span-ex——来源/规则不匹配。
    mismatched = _source(
        anchor_resolutions=[
            _resolution(ambiguous_source_refs=["span-in"]),
        ]
    )
    bound_input = _interpretation_input(source_input, mismatched)
    result = ProtocolDeconstructionGate().evaluate(
        bound_input, draft, source_spans=spans
    )
    assert any(
        "歧义来源不匹配" in issue.problem
        for issue in _issues(result, "temporal_semantics")
    )


def test_missing_due_stage_coverage_for_declared_targets_is_blocked():
    source_input, draft, spans = _fixture()
    component = draft.proposed_rules[1].components[0]
    component.expression.time_constraint = _review_node_constraint()
    # 删除基线资料要求：解释声明 screening+baseline，但组件只剩 screening。
    component.evidence_requirements = [
        requirement
        for requirement in component.evidence_requirements
        if requirement.due_stage != ReviewStage.BASELINE
    ]
    draft.evidence_requirement_drafts = [
        item
        for item in draft.evidence_requirement_drafts
        if item.draft_requirement_id != "draft-req-ex-base"
    ]
    bound_input = _interpretation_input(source_input, _source())
    result = ProtocolDeconstructionGate().evaluate(
        bound_input, draft, source_spans=spans
    )
    assert any(
        issue.issue_code == "INTERPRETATION_ANCHOR_REQUIREMENT_MISSING"
        for issue in _issues(result, "temporal_semantics")
    )
    assert not result.publishable


def test_named_anchor_still_authoritative_over_interpretation():
    source_input, draft, spans = _fixture()
    # 原文明确“随机前”时，模型不得用 review_node_date 替代命名锚点。
    component = draft.proposed_rules[1].components[0]
    component.expression.time_constraint = _review_node_constraint()
    bound_input = _interpretation_input(source_input, _source())
    # 把 EX 条款文本换成命名锚点，使解析声明与解构结果不一致。
    named_text = "随机前2个月内存在目标既往疾病史"
    ambiguous_span = next(
        item
        for item in bound_input.source_materials
        if item.source_span_id == "span-ex"
    )
    ambiguous_span.text = named_text
    draft.proposed_rules[1].source_text = named_text
    ex_draft = draft.component_drafts[1]
    ex_draft.source_excerpts = [named_text]
    ex_draft.proposed_component.expression.predicate.source_clause = named_text
    result = ProtocolDeconstructionGate().evaluate(
        bound_input, draft, source_spans=spans
    )
    codes = {issue.issue_code for issue in _issues(result, "temporal_semantics")}
    assert "INTERPRETATION_ANCHOR_REJECTED" in codes
    assert not result.publishable


# ---------------------------------------------------------------------------
# 输入合同与装配
# ---------------------------------------------------------------------------


def _validated_copy(source_input: ProtocolDeconstructionInput, **updates):
    """model_copy 不重跑校验器；输入合同测试必须走完整校验路径。"""

    return ProtocolDeconstructionInput.model_validate(
        {**source_input.model_dump(mode="python"), **updates}
    )


def test_input_rejects_bare_ids_without_objects():
    source_input, _draft, _spans = _fixture()
    with pytest.raises(ValidationError, match="ID 集合"):
        _validated_copy(
            source_input,
            interpretation_source_ids=["interp-1"],
        )


def test_input_rejects_id_set_mismatch_with_objects():
    source_input, _draft, _spans = _fixture()
    bound = _validated_copy(
        source_input,
        interpretation_source_ids=["interp-1"],
        interpretation_sources=[_source()],
    )
    assert bound.interpretation_source_ids == ["interp-1"]
    with pytest.raises(ValidationError, match="完全一致"):
        _validated_copy(
            bound,
            interpretation_source_ids=["interp-other"],
        )


def test_input_rejects_source_bound_to_other_protocol_version():
    source_input, _draft, _spans = _fixture()
    with pytest.raises(ValidationError, match="方案版本"):
        _validated_copy(
            source_input,
            interpretation_source_ids=["interp-1"],
            interpretation_sources=[
                _source(protocol_version_id="protocol-version-other")
            ],
        )


def test_assembler_helper_validates_protocol_binding_and_duplicates():
    assembler = ProtocolDeconstructionInputAssembler()
    # 直接调用校验函数，避免重建整包夹具。
    validated = assembler._validate_interpretation_sources(
        [_source()], protocol_version_id="protocol-version-1"
    )
    assert [item.interpretation_source_id for item in validated] == ["interp-1"]
    with pytest.raises(ProtocolDeconstructionInputAssemblyError) as mismatch:
        assembler._validate_interpretation_sources(
            [_source(protocol_version_id="other")],
            protocol_version_id="protocol-version-1",
        )
    assert mismatch.value.code == "interpretation_protocol_mismatch"
    with pytest.raises(ProtocolDeconstructionInputAssemblyError) as duplicate:
        assembler._validate_interpretation_sources(
            [_source(), _source()], protocol_version_id="protocol-version-1"
        )
    assert duplicate.value.code == "interpretation_source_duplicate"


# ---------------------------------------------------------------------------
# 提示框架
# ---------------------------------------------------------------------------


def _extract_payload(prompt: str) -> dict:
    marker = "输入："
    start = prompt.index(marker) + len(marker)
    tail = prompt[start:]
    end = start + (
        tail.index("输出结构：") if "输出结构：" in tail else len(tail)
    )
    return json.loads(prompt[start:end])


def test_prompt_places_interpretation_in_dedicated_section():
    source_input, _draft, _spans = _fixture()
    bound_input = _interpretation_input(source_input, _source())
    prompt = build_protocol_deconstruction_prompt(
        bound_input,
        prompt_template="解构合成方案。",
    )
    payload = _extract_payload(prompt)
    assert "interpretation_sources" not in payload
    clarifications = payload["interpretation_clarifications"]
    assert len(clarifications) == 1
    entry = clarifications[0]
    assert entry["explanation"] == "未命名回溯锚点按当前审核节点日期计算，筛选与基线分别评判。"
    assert entry["anchor_resolutions"][0]["affected_rule_refs"] == ["EX-01"]
    assert entry["anchor_resolutions"][0]["target_review_stages"] == [
        "screening",
        "baseline",
    ]
    assert entry["anchor_resolutions"][0]["resolution_mode"] == (
        "current_review_node_date"
    )
    # 解释文字不得进入方案原文区。
    for material in payload["source_materials"]:
        assert entry["explanation"] not in material["text"]
        assert entry["excerpt"] not in material["text"]


def test_prompt_without_interpretation_has_empty_clarification_section():
    source_input, _draft, _spans = _fixture()
    prompt = build_protocol_deconstruction_prompt(
        source_input,
        prompt_template="解构合成方案。",
    )
    payload = _extract_payload(prompt)
    assert payload["interpretation_clarifications"] == []
    assert "interpretation_clarifications" in prompt


def test_prompt_filters_clarifications_to_batch_rule_codes():
    source_input, _draft, _spans = _fixture()
    bound_input = _interpretation_input(source_input, _source())
    prompt = build_protocol_deconstruction_prompt(
        bound_input,
        prompt_template="解构合成方案。",
        requested_rule_codes=["IN-01"],
        batch_number=1,
        batch_total=2,
        compact=True,
    )
    payload = _extract_payload(prompt)
    # EX-01 的解析不进入 IN-01 批次，避免跨规则套用。
    assert payload["interpretation_clarifications"] == []


def test_prompt_declares_anchor_mechanism_and_wire_enum():
    source_input, _draft, _spans = _fixture()
    prompt = build_protocol_deconstruction_prompt(
        source_input,
        prompt_template="解构合成方案。",
    )
    assert "interpretation_clarifications 专用区" in prompt
    assert "review_node_date" in prompt
    schema = _wire_time_constraint_schema()
    assert "review_node_date" in schema["properties"]["anchor_type"]["enum"]
    # 提示模板哈希必须覆盖解释锚点合同文本。
    assert protocol_prompt_template_sha256("x") != protocol_prompt_template_sha256("y")
