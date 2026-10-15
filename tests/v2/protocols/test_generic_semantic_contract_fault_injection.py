"""通用中文语义合同反过拟合故障注入与回归测试（全部合成条款）。

对应执行任务 ``phase5-generic-semantic-contract-repair-20260902`` 工作项 3：
使用本文件发明的合成中文条款（``SYN-001`` 合成方案）验证方案语义提示合同
与确定性门禁之间的通用中文表达一致性，不包含任何真实项目的方案原文、
编号、药物、疾病或时间点特异规则。

两层断言：

- 反过拟合回归（防假阳性）：非限制性人群描述（如“男女不限”）、结构引导语、
  原文明示“之一”的替代关系、绑定到每个分支的共享期间、绑定到被断言对象的
  否定，都不得被确定性门禁误报为结构缺陷；
- 故障注入（防漏报）：在全部十二项检查通过的合成基线上逐项注入真实遗漏、
  虚构任选关系、跨来源绑定和未绑定时间窗，门禁必须以确定性 issue code
  拒绝，且同一注入在不同合成条款族上表现一致（条款不可过拟合）。
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.agents.protocol_deconstructor import _SYSTEM_CONTRACT
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
    AnchorType,
    CatalogItemKind,
    CatalogKind,
    Comparator,
    DatePrecision,
    DocumentPart,
    LogicalOperator,
    MetadataResolutionStatus,
    ReviewStage,
    RuleKind,
    SourceLocatorPrecision,
    StudyPhase,
    TimeDirection,
)
from app.domain.contracts.normalization import CoverageSummary
from app.domain.contracts.protocol_ingestion import (
    FrozenCatalogItem,
    FrozenProtocolCatalog,
    ProtocolSourceSpan,
)
from app.domain.contracts.protocol_metadata import (
    ProtocolIdentityDecision,
    StudyPhaseSelection,
)
from app.domain.contracts.rules import (
    AtomicExpression,
    AtomicPredicate,
    EvidenceRequirement,
    LogicalExpression,
    Rule,
    RuleComponent,
    TimeConstraint,
    TimeQuantity,
    TimeUnit,
    WorkflowStage,
)
from app.domain.publication import canonical_hash
from app.protocols.deconstruction_gate import (
    ProtocolDeconstructionGate,
    _branches_have_source_disjunction,
    _substantive_obligation_segments,
)


NOW = datetime(2026, 9, 2, tzinfo=timezone.utc)
SHA = "b" * 64


# --------------------------------------------------------------------------- 合成条款族
#
# 以下全部条款文字均为本测试文件发明的通用合成中文条款，专用于验证门禁的
# 通用中文语义处理；任何真实方案都不包含这些句子。

FAMILY_PREGNANCY = {
    "alternative_with_huo": "满足下列条件之一：处于妊娠期或哺乳期",
    "alternative_dunhao_only": "满足下列条件之一：处于妊娠期、哺乳期",
    "term_list_without_marker": "处于妊娠期、哺乳期",
    "branch_a": "处于妊娠期",
    "branch_b": "哺乳期",
}

FAMILY_MEDICATION = {
    "alternative_with_huo": "满足下列条件之一：正在使用试验药甲或试验药乙",
    "alternative_dunhao_only": "满足下列条件之一：正在使用试验药甲、试验药乙",
    "term_list_without_marker": "正在使用试验药甲、试验药乙",
    "branch_a": "正在使用试验药甲",
    "branch_b": "试验药乙",
}


# --------------------------------------------------------------------------- 构建工具


def _catalog(kind, items):
    payload = {
        "catalog_id": f"catalog:{kind.value}",
        "snapshot_id": "snapshot-syn",
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


def _span(span_id, order, excerpt):
    return ProtocolSourceSpan(
        source_span_id=span_id,
        snapshot_id="snapshot-syn",
        source_ref=f"body.p{order}",
        document_part=DocumentPart.BODY,
        section_index=0,
        block_order=order,
        render_artifact_id="render-syn",
        render_page=order + 1,
        text_start=0,
        text_end=10,
        excerpt=excerpt,
        precision=SourceLocatorPrecision.TEXT_RANGE,
        alignment_status=AlignmentStatus.ALIGNED,
        degradation_reason=None,
    )


def _material(span_id, order, text):
    return ProtocolSourceMaterial(
        source_span_id=span_id,
        source_ref=f"body.p{order}",
        block_order=order,
        text=text,
    )


def _exists_expression(pid, attribute, clauses):
    kwargs = {"source_clauses": clauses} if len(clauses) > 1 else {"source_clause": clauses[0]}
    return AtomicExpression(
        predicate=AtomicPredicate(
            predicate_id=pid,
            subject="受试者",
            attribute=attribute,
            source_term=attribute,
            comparator=Comparator.EXISTS,
            **kwargs,
        )
    )


def _requirement(rid, component_id, stage=ReviewStage.SCREENING):
    return EvidenceRequirement(
        requirement_id=rid,
        rule_component_id=component_id,
        fact_type="方案要求事实",
        due_stage=stage,
        description="核对正式原始资料和研究者记录",
    )


def _procedure_requirement(rid, catalog_item_id, stage):
    return EvidenceRequirement(
        requirement_id=rid,
        procedure_catalog_item_id=catalog_item_id,
        fact_type="方案要求事实",
        due_stage=stage,
        description="核对正式原始资料和研究者记录",
    )


def _baseline():
    """构建一个全部十二项检查通过的合成基线草稿。

    合成父规则覆盖五个语义维度：
    - IN-01 数值阈值；
    - IN-02 结构引导语 + 并列义务（并且）；
    - EX-01 明确“之一”替代关系（或连接）；
    - EX-02 绑定到每个分支的共享期间（和/或）；
    - EX-03 绑定到被断言对象的否定（无…史）+ 随机锚点时间窗。
    """
    parent_items = [
        FrozenCatalogItem(
            item_id="parent:syn-in01",
            kind=CatalogItemKind.PARENT_RULE,
            official_code="IN-01",
            label="年龄≥18周岁",
            position=0,
            source_span_ids=["span-in1"],
        ),
        FrozenCatalogItem(
            item_id="parent:syn-in02",
            kind=CatalogItemKind.PARENT_RULE,
            official_code="IN-02",
            label="符合下列所有条件",
            position=1,
            source_span_ids=["span-in2a", "span-in2b"],
        ),
        FrozenCatalogItem(
            item_id="parent:syn-ex01",
            kind=CatalogItemKind.PARENT_RULE,
            official_code="EX-01",
            label=FAMILY_PREGNANCY["alternative_with_huo"],
            position=2,
            source_span_ids=["span-ex1"],
        ),
        FrozenCatalogItem(
            item_id="parent:syn-ex02",
            kind=CatalogItemKind.PARENT_RULE,
            official_code="EX-02",
            label="筛选前3个月内有镇静类药物成瘾史和/或药物滥用史",
            position=3,
            source_span_ids=["span-ex2"],
        ),
        FrozenCatalogItem(
            item_id="parent:syn-ex03",
            kind=CatalogItemKind.PARENT_RULE,
            official_code="EX-03",
            label="随机前6个月内无活动性结核病史",
            position=4,
            source_span_ids=["span-ex3"],
        ),
    ]
    procedure_items = [
        FrozenCatalogItem(
            item_id="procedure:syn:screening:lab",
            kind=CatalogItemKind.REQUIRED_PROCEDURE,
            label="实验室常规检查",
            visit_instance="筛选期 D-28~D-1",
            review_stage=ReviewStage.SCREENING,
            position=0,
            source_span_ids=["span-proc-screen"],
        ),
        FrozenCatalogItem(
            item_id="procedure:syn:baseline:lab",
            kind=CatalogItemKind.REQUIRED_PROCEDURE,
            label="实验室常规检查",
            visit_instance="基线 D1",
            review_stage=ReviewStage.BASELINE,
            position=1,
            source_span_ids=["span-proc-base"],
        ),
    ]
    identity = ProtocolIdentityDecision(
        identity_decision_id="identity-syn",
        snapshot_id="snapshot-syn",
        project_name="合成验证研究",
        project_code="SYN",
        protocol_code="SYN-001",
        official_version="V1.0",
        official_date=DateValue(value=date(2026, 9, 2), precision=DatePrecision.DAY),
        study_phase=StudyPhase.PHASE_II,
        selected_candidate_ids=["candidate-syn"],
        status=MetadataResolutionStatus.CONFIRMED,
        confirmation_required=False,
        confirmed_by="医学监查员",
        confirmed_at=NOW,
    )
    selection = StudyPhaseSelection(
        selection_id="phase-selection-syn",
        snapshot_id="snapshot-syn",
        selected_phase=StudyPhase.PHASE_II,
        candidate_ids=["phase-candidate-syn"],
        status=MetadataResolutionStatus.CONFIRMED,
        confirmed_by="医学监查员",
        confirmed_at=NOW,
    )

    span_texts = {
        "span-in1": "年龄≥18周岁",
        "span-in2a": "符合下列所有条件",
        "span-in2b": "能够与研究者良好沟通并且能够遵守研究要求",
        "span-ex1": FAMILY_PREGNANCY["alternative_with_huo"],
        "span-ex2": "筛选前3个月内有镇静类药物成瘾史和/或药物滥用史",
        "span-ex3": "随机前6个月内无活动性结核病史",
        "span-proc-screen": "筛选期实验室常规检查",
        "span-proc-base": "基线实验室常规检查",
    }
    source_spans = {
        span_id: _span(span_id, order, text)
        for order, (span_id, text) in enumerate(span_texts.items())
    }
    source_input = ProtocolDeconstructionInput(
        project_id="project-syn",
        protocol_version_id="protocol-version-syn",
        protocol_file_sha256=SHA,
        extraction_snapshot_id="snapshot-syn",
        phase_projection_id="projection-syn",
        selected_phase=StudyPhase.PHASE_II,
        identity_decision=identity,
        phase_selection=selection,
        allowed_source_span_ids=list(source_spans),
        source_materials=[
            _material(span_id, span.block_order, span_texts[span_id])
            for span_id, span in source_spans.items()
        ],
        parent_rule_catalog=_catalog(CatalogKind.OFFICIAL_PARENT_RULES, parent_items),
        required_procedure_catalog=_catalog(
            CatalogKind.REQUIRED_PROCEDURES, procedure_items
        ),
    )

    req_in1 = _requirement("req-syn-in1", "component-in1")
    req_in2a = _requirement("req-syn-in2a", "component-in2")
    req_in2b = _requirement("req-syn-in2b", "component-in2")
    req_ex1 = _requirement("req-syn-ex1", "component-ex1")
    req_ex2 = _requirement("req-syn-ex2", "component-ex2")
    req_ex3_base = _requirement(
        "req-syn-ex3-base", "component-ex3", ReviewStage.BASELINE
    )
    proc_screen = _procedure_requirement(
        "req-syn-proc-screen", "procedure:syn:screening:lab", ReviewStage.SCREENING
    )
    proc_base = _procedure_requirement(
        "req-syn-proc-base", "procedure:syn:baseline:lab", ReviewStage.BASELINE
    )

    component_in1 = RuleComponent(
        rule_component_id="component-in1",
        parent_rule_id="rule-syn-in1",
        display_code="IN-01a",
        title="年龄要求",
        expression=AtomicExpression(
            predicate=AtomicPredicate(
                predicate_id="predicate-syn-age",
                subject="受试者",
                attribute="年龄",
                source_term="年龄",
                comparator=Comparator.GTE,
                value=18,
                unit="岁",
                source_clause="年龄≥18周岁",
            )
        ),
        evidence_requirements=[req_in1],
    )
    component_in2 = RuleComponent(
        rule_component_id="component-in2",
        parent_rule_id="rule-syn-in2",
        display_code="IN-02a",
        title="沟通与依从要求",
        expression=LogicalExpression(
            operator=LogicalOperator.ALL,
            children=[
                _exists_expression(
                    "predicate-syn-communicate",
                    "与研究者良好沟通",
                    ["能够与研究者良好沟通"],
                ),
                _exists_expression(
                    "predicate-syn-comply",
                    "遵守研究要求",
                    ["能够遵守研究要求"],
                ),
            ],
        ),
        evidence_requirements=[req_in2a, req_in2b],
    )
    component_ex1 = RuleComponent(
        rule_component_id="component-ex1",
        parent_rule_id="rule-syn-ex1",
        display_code="EX-01a",
        title="妊娠或哺乳",
        expression=LogicalExpression(
            operator=LogicalOperator.ANY,
            children=[
                _exists_expression(
                    "predicate-syn-pregnant",
                    FAMILY_PREGNANCY["branch_a"],
                    ["满足下列条件之一", FAMILY_PREGNANCY["branch_a"]],
                ),
                _exists_expression(
                    "predicate-syn-lactation",
                    FAMILY_PREGNANCY["branch_b"],
                    ["满足下列条件之一", FAMILY_PREGNANCY["branch_b"]],
                ),
            ],
        ),
        evidence_requirements=[req_ex1],
    )
    component_ex2 = RuleComponent(
        rule_component_id="component-ex2",
        parent_rule_id="rule-syn-ex2",
        display_code="EX-02a",
        title="物质成瘾或滥用",
        expression=LogicalExpression(
            operator=LogicalOperator.ANY,
            children=[
                AtomicExpression(
                    predicate=AtomicPredicate(
                        predicate_id="predicate-syn-sedative",
                        subject="受试者",
                        attribute="有镇静类药物成瘾史",
                        source_term="有镇静类药物成瘾史",
                        comparator=Comparator.EXISTS,
                        source_clauses=["筛选前3个月内", "有镇静类药物成瘾史"],
                    ),
                    time_constraint=TimeConstraint(
                        anchor_type=AnchorType.SCREENING_DATE,
                        direction=TimeDirection.BEFORE,
                        upper_bound=TimeQuantity(value=3, unit=TimeUnit.MONTH),
                    ),
                ),
                AtomicExpression(
                    predicate=AtomicPredicate(
                        predicate_id="predicate-syn-drugabuse",
                        subject="受试者",
                        attribute="药物滥用史",
                        source_term="药物滥用史",
                        comparator=Comparator.EXISTS,
                        source_clauses=["筛选前3个月内", "药物滥用史"],
                    ),
                    time_constraint=TimeConstraint(
                        anchor_type=AnchorType.SCREENING_DATE,
                        direction=TimeDirection.BEFORE,
                        upper_bound=TimeQuantity(value=3, unit=TimeUnit.MONTH),
                    ),
                ),
            ],
        ),
        evidence_requirements=[req_ex2],
    )
    component_ex3 = RuleComponent(
        rule_component_id="component-ex3",
        parent_rule_id="rule-syn-ex3",
        display_code="EX-03a",
        title="活动性结核病史",
        expression=LogicalExpression(
            operator=LogicalOperator.NOT,
            children=[
                AtomicExpression(
                    predicate=AtomicPredicate(
                        predicate_id="predicate-syn-tb",
                        subject="受试者",
                        attribute="活动性结核病史",
                        source_term="活动性结核病史",
                        comparator=Comparator.EXISTS,
                        source_clauses=["随机前6个月内", "无活动性结核病史"],
                    ),
                    time_constraint=TimeConstraint(
                        anchor_type=AnchorType.RANDOMIZATION_DATE,
                        direction=TimeDirection.BEFORE,
                        upper_bound=TimeQuantity(value=6, unit=TimeUnit.MONTH),
                    ),
                )
            ],
        ),
        evidence_requirements=[req_ex3_base],
    )
    rules = [
        Rule(
            rule_id="rule-syn-in1",
            official_code="IN-01",
            kind=RuleKind.INCLUSION,
            source_text="年龄≥18周岁",
            study_phase=StudyPhase.PHASE_II,
            components=[component_in1],
        ),
        Rule(
            rule_id="rule-syn-in2",
            official_code="IN-02",
            kind=RuleKind.INCLUSION,
            source_text="符合下列所有条件",
            study_phase=StudyPhase.PHASE_II,
            components=[component_in2],
        ),
        Rule(
            rule_id="rule-syn-ex1",
            official_code="EX-01",
            kind=RuleKind.EXCLUSION,
            source_text=FAMILY_PREGNANCY["alternative_with_huo"],
            study_phase=StudyPhase.PHASE_II,
            components=[component_ex1],
        ),
        Rule(
            rule_id="rule-syn-ex2",
            official_code="EX-02",
            kind=RuleKind.EXCLUSION,
            source_text="筛选前3个月内有镇静类药物成瘾史和/或药物滥用史",
            study_phase=StudyPhase.PHASE_II,
            components=[component_ex2],
        ),
        Rule(
            rule_id="rule-syn-ex3",
            official_code="EX-03",
            kind=RuleKind.EXCLUSION,
            source_text="随机前6个月内无活动性结核病史",
            study_phase=StudyPhase.PHASE_II,
            components=[component_ex3],
        ),
    ]
    draft = ProtocolDeconstructionDraft(
        draft_id="draft-syn",
        project_id="project-syn",
        protocol_version_id="protocol-version-syn",
        selected_phase=StudyPhase.PHASE_II,
        draft_revision=1,
        proposed_rules=rules,
        proposed_workflow_stages=[
            WorkflowStage(
                workflow_stage_id="stage-syn-screening",
                stage=ReviewStage.SCREENING,
                display_name="筛选期审核",
                visit_instance="筛选期 D-28~D-1",
                due_requirement_ids=[
                    "req-syn-in1",
                    "req-syn-in2a",
                    "req-syn-in2b",
                    "req-syn-ex1",
                    "req-syn-ex2",
                    "req-syn-proc-screen",
                ],
            ),
            WorkflowStage(
                workflow_stage_id="stage-syn-baseline",
                stage=ReviewStage.BASELINE,
                display_name="基线审核",
                visit_instance="基线 D1",
                due_requirement_ids=["req-syn-ex3-base", "req-syn-proc-base"],
            ),
        ],
        protocol_metadata=ProtocolMetadataDraft(
            protocol_code_candidate="SYN-001",
            title_candidate="合成验证研究",
            version_candidate="V1.0",
            date_candidate="2026-09-02",
            study_phase_candidates=["Ⅱ期"],
            source_refs=["span-in1"],
        ),
        component_drafts=[
            RuleComponentDraft(
                draft_component_id="draft-component-in1",
                parent_official_code="IN-01",
                proposed_component=component_in1,
                source_refs=["span-in1"],
                source_excerpts=["年龄≥18周岁"],
            ),
            RuleComponentDraft(
                draft_component_id="draft-component-in2",
                parent_official_code="IN-02",
                proposed_component=component_in2,
                source_refs=["span-in2a", "span-in2b"],
                source_excerpts=[
                    "符合下列所有条件",
                    "能够与研究者良好沟通并且能够遵守研究要求",
                ],
            ),
            RuleComponentDraft(
                draft_component_id="draft-component-ex1",
                parent_official_code="EX-01",
                proposed_component=component_ex1,
                source_refs=["span-ex1"],
                source_excerpts=[FAMILY_PREGNANCY["alternative_with_huo"]],
            ),
            RuleComponentDraft(
                draft_component_id="draft-component-ex2",
                parent_official_code="EX-02",
                proposed_component=component_ex2,
                source_refs=["span-ex2"],
                source_excerpts=["筛选前3个月内有镇静类药物成瘾史和/或药物滥用史"],
            ),
            RuleComponentDraft(
                draft_component_id="draft-component-ex3",
                parent_official_code="EX-03",
                proposed_component=component_ex3,
                source_refs=["span-ex3"],
                source_excerpts=["随机前6个月内无活动性结核病史"],
            ),
        ],
        evidence_requirement_drafts=[
            EvidenceRequirementDraft(
                draft_requirement_id="draft-req-syn-in1",
                draft_component_id="draft-component-in1",
                proposed_requirement=req_in1,
                source_refs=["span-in1"],
            ),
            EvidenceRequirementDraft(
                draft_requirement_id="draft-req-syn-in2a",
                draft_component_id="draft-component-in2",
                proposed_requirement=req_in2a,
                source_refs=["span-in2a", "span-in2b"],
            ),
            EvidenceRequirementDraft(
                draft_requirement_id="draft-req-syn-in2b",
                draft_component_id="draft-component-in2",
                proposed_requirement=req_in2b,
                source_refs=["span-in2a", "span-in2b"],
            ),
            EvidenceRequirementDraft(
                draft_requirement_id="draft-req-syn-ex1",
                draft_component_id="draft-component-ex1",
                proposed_requirement=req_ex1,
                source_refs=["span-ex1"],
            ),
            EvidenceRequirementDraft(
                draft_requirement_id="draft-req-syn-ex2",
                draft_component_id="draft-component-ex2",
                proposed_requirement=req_ex2,
                source_refs=["span-ex2"],
            ),
            EvidenceRequirementDraft(
                draft_requirement_id="draft-req-syn-ex3-base",
                draft_component_id="draft-component-ex3",
                proposed_requirement=req_ex3_base,
                source_refs=["span-ex3"],
            ),
            EvidenceRequirementDraft(
                draft_requirement_id="draft-req-syn-proc-screen",
                procedure_catalog_item_id="procedure:syn:screening:lab",
                proposed_requirement=proc_screen,
                source_refs=["span-proc-screen"],
            ),
            EvidenceRequirementDraft(
                draft_requirement_id="draft-req-syn-proc-base",
                procedure_catalog_item_id="procedure:syn:baseline:lab",
                proposed_requirement=proc_base,
                source_refs=["span-proc-base"],
            ),
        ],
        parent_catalog_mappings=[
            ParentRuleCatalogMapping(
                catalog_item_id="parent:syn-in01",
                proposed_rule_id="rule-syn-in1",
                source_span_ids=["span-in1"],
            ),
            ParentRuleCatalogMapping(
                catalog_item_id="parent:syn-in02",
                proposed_rule_id="rule-syn-in2",
                source_span_ids=["span-in2a", "span-in2b"],
            ),
            ParentRuleCatalogMapping(
                catalog_item_id="parent:syn-ex01",
                proposed_rule_id="rule-syn-ex1",
                source_span_ids=["span-ex1"],
            ),
            ParentRuleCatalogMapping(
                catalog_item_id="parent:syn-ex02",
                proposed_rule_id="rule-syn-ex2",
                source_span_ids=["span-ex2"],
            ),
            ParentRuleCatalogMapping(
                catalog_item_id="parent:syn-ex03",
                proposed_rule_id="rule-syn-ex3",
                source_span_ids=["span-ex3"],
            ),
        ],
        procedure_catalog_mappings=[
            ProcedureCatalogMapping(
                catalog_item_id="procedure:syn:screening:lab",
                proposed_requirement_ids=["req-syn-proc-screen"],
                proposed_workflow_stage_id="stage-syn-screening",
                source_span_ids=["span-proc-screen"],
            ),
            ProcedureCatalogMapping(
                catalog_item_id="procedure:syn:baseline:lab",
                proposed_requirement_ids=["req-syn-proc-base"],
                proposed_workflow_stage_id="stage-syn-baseline",
                source_span_ids=["span-proc-base"],
            ),
        ],
        coverage=CoverageSummary(processed_refs=list(source_spans)),
        source_refs=list(source_spans),
        created_by_agent_call_id="agent-call-syn",
    )
    return source_input, draft, source_spans


def _material_text(source_input, span_id):
    return next(
        item
        for item in source_input.source_materials
        if item.source_span_id == span_id
    ).text


def _set_material_text(source_input, span_id, text):
    next(
        item
        for item in source_input.source_materials
        if item.source_span_id == span_id
    ).text = text


def _set_parent_label(source_input, item_id, label):
    source_input.parent_rule_catalog = (
        source_input.parent_rule_catalog.model_copy(
            update={
                "items": tuple(
                    item.model_copy(update={"label": label})
                    if item.item_id == item_id
                    else item
                    for item in source_input.parent_rule_catalog.items
                )
            }
        )
    )


def _evaluate(source_input, draft, spans):
    return ProtocolDeconstructionGate().evaluate(source_input, draft, source_spans=spans)


def _issues(result, check_name):
    return next(
        item for item in result.checks if item.check_name == check_name
    ).issues


def _codes(result, check_name):
    return {item.issue_code for item in _issues(result, check_name)}


# --------------------------------------------------------------------------- 基线回归


def test_synthetic_baseline_passes_all_twelve_checks():
    """全合成基线：三个维度（之一替代、共享期间、否定对象）零误报。"""
    source_input, draft, spans = _baseline()
    result = _evaluate(source_input, draft, spans)
    for check in result.checks:
        assert not check.issues, (
            f"{check.check_name} 出现误报: "
            f"{[issue.issue_code for issue in check.issues]}"
        )
    assert result.publishable is True


# --------------------------------------------------------------------------- 防假阳性：非限制性人群描述


@pytest.mark.parametrize(
    "text",
    [
        "性别不限",
        "男女不限",
        "年龄不限",
        "种族不限",
        "民族不限",
        "可以入组本研究",
        "可以参加本研究",
    ],
)
def test_nonrestrictive_population_segments_are_not_obligations(text):
    """非限制性人群描述本身不是可判定义务，不得要求原子条件承接。"""
    assert _substantive_obligation_segments(text) == []


def test_nonrestrictive_segment_inside_parent_source_does_not_block_publishing():
    source_input, draft, spans = _baseline()
    text = "年龄≥18周岁\n男女不限"
    _set_material_text(source_input, "span-in1", text)
    _set_parent_label(source_input, "parent:syn-in01", text)

    result = _evaluate(source_input, draft, spans)

    coverage_codes = _codes(result, "source_coverage")
    assert "PARENT_RULE_OBLIGATION_NOT_COVERED" not in coverage_codes
    assert "PARENT_SOURCE_SEMANTIC_COVERAGE_MISSING" not in coverage_codes


# --------------------------------------------------------------------------- 防假阳性：结构引导语


@pytest.mark.parametrize(
    "text",
    [
        "符合下列所有条件：",
        "符合下列入选条件",
        "满足以下全部标准",
        "正在使用或有以下治疗史",
        "包括以下情况",
        "筛选时和基线时需满足以下标准",
        "整个研究期间（从签署知情同意到末次给药后3个月）",
        "根据日常作息推断",
        "患有以下疾病或疾病史",
        "包括但不限于",
        "或者以下列出的相关疾病",
    ],
)
def test_structural_lead_in_segments_are_not_obligations(text):
    """结构引导语不构成独立可判定义务，不得要求原子条件逐字承接。"""
    assert _substantive_obligation_segments(text) == []


def test_disjunction_checks_later_nonoverlapping_anchor_candidates():
    """共用事件文字会先产生重叠定位，不得在第一个候选失败后提前返回。"""
    expression = LogicalExpression(
        operator=LogicalOperator.ANY,
        children=[
            _exists_expression(
                "predicate-syn-history",
                "接受方案药物",
                ["确认前3个月内", "接受方案药物"],
            ),
            _exists_expression(
                "predicate-syn-plan",
                "计划在研究期间接受方案药物",
                ["计划在研究期间接受方案药物"],
            ),
        ],
    )

    assert _branches_have_source_disjunction(
        expression,
        "确认前3个月内或计划在研究期间接受方案药物",
    )


def test_numbered_noun_phrase_explicitly_supports_one_of_branches():
    expression = LogicalExpression(
        operator=LogicalOperator.ANY,
        children=[
            _exists_expression("predicate-syn-a", "症状甲", ["症状甲、症状乙和症状丙三种症状之一"]),
            _exists_expression("predicate-syn-b", "症状乙", ["症状甲、症状乙和症状丙三种症状之一"]),
            _exists_expression("predicate-syn-c", "症状丙", ["症状甲、症状乙和症状丙三种症状之一"]),
        ],
    )

    assert _branches_have_source_disjunction(
        expression,
        "症状甲、症状乙和症状丙三种症状之一",
    )


def test_lead_in_plus_uncovered_real_clause_still_rejected():
    """引导语可以不承接，但引导语之后的实质条款遗漏必须拒绝（防漏报）。"""
    source_input, draft, spans = _baseline()
    text = "符合下列所有条件\n能够与研究者良好沟通并且能够遵守研究要求\n既往存在器官移植史"
    _set_material_text(source_input, "span-in2b", text)
    _set_parent_label(source_input, "parent:syn-in02", "符合下列所有条件")

    result = _evaluate(source_input, draft, spans)

    assert "PARENT_RULE_OBLIGATION_NOT_COVERED" in _codes(result, "source_coverage")


# --------------------------------------------------------------------------- 防假阳性：明确“之一”替代关系


@pytest.mark.parametrize("family", [FAMILY_PREGNANCY, FAMILY_MEDICATION])
def test_explicit_zhiyi_alternatives_with_huo_remain_valid(family):
    """原文明示“之一”并以“或”连接分支时，ANY 不得被判为虚构任选。"""
    source_input, draft, spans = _baseline()
    text = family["alternative_with_huo"]
    _set_material_text(source_input, "span-ex1", text)
    _set_parent_label(source_input, "parent:syn-ex01", text)
    component = draft.proposed_rules[2].components[0]
    component.expression = LogicalExpression(
        operator=LogicalOperator.ANY,
        children=[
            _exists_expression(
                f"{child.predicate.predicate_id}-x",
                attribute,
                ["满足下列条件之一", attribute],
            )
            for child, attribute in (
                (component.expression.children[0], family["branch_a"]),
                (component.expression.children[1], family["branch_b"]),
            )
        ],
    )
    draft.component_drafts[2].proposed_component = component
    draft.component_drafts[2].source_excerpts = [text]

    result = _evaluate(source_input, draft, spans)

    boolean_codes = _codes(result, "boolean_logic")
    assert "DISJUNCTION_NOT_BOUND_TO_SOURCE" not in boolean_codes
    assert "CONJUNCTION_CHANGED_TO_DISJUNCTION" not in boolean_codes


@pytest.mark.parametrize("family", [FAMILY_PREGNANCY, FAMILY_MEDICATION])
def test_explicit_zhiyi_with_dunhao_list_is_not_fabricated_alternative(family):
    """原文明示“之一”的顿号列举是明确替代关系，不得误报为虚构任选。"""
    source_input, draft, spans = _baseline()
    text = family["alternative_dunhao_only"]
    _set_material_text(source_input, "span-ex1", text)
    _set_parent_label(source_input, "parent:syn-ex01", text)
    component = draft.proposed_rules[2].components[0]
    component.expression = LogicalExpression(
        operator=LogicalOperator.ANY,
        children=[
            _exists_expression(
                f"{child.predicate.predicate_id}-y",
                attribute,
                ["满足下列条件之一", attribute],
            )
            for child, attribute in (
                (component.expression.children[0], family["branch_a"]),
                (component.expression.children[1], family["branch_b"]),
            )
        ],
    )
    draft.component_drafts[2].proposed_component = component
    draft.component_drafts[2].source_excerpts = [text]

    result = _evaluate(source_input, draft, spans)

    boolean_codes = _codes(result, "boolean_logic")
    assert "DISJUNCTION_NOT_BOUND_TO_SOURCE" not in boolean_codes
    assert "CONJUNCTION_CHANGED_TO_DISJUNCTION" not in boolean_codes


def test_semantic_prompt_contract_names_explicit_alternative_marker():
    """语义提示合同必须把“之一”列为与“或/任一”同级的明示替代连接语。"""
    assert "之一" in _SYSTEM_CONTRACT


# --------------------------------------------------------------------------- 故障注入 1：真实遗漏


def test_injected_omission_of_substantive_clause_is_rejected():
    source_input, draft, spans = _baseline()
    omitted = "随机前1年内曾有深度麻醉镇静史"
    _set_material_text(source_input, "span-ex3", "随机前6个月内无活动性结核病史\n" + omitted)
    _set_parent_label(
        source_input, "parent:syn-ex03", "随机前6个月内无活动性结核病史"
    )

    result = _evaluate(source_input, draft, spans)

    omission_issues = [
        issue
        for issue in _issues(result, "source_coverage")
        if issue.issue_code == "PARENT_RULE_OBLIGATION_NOT_COVERED"
    ]
    assert omission_issues
    assert any(
        f"未承接：{omitted}" in detail
        for issue in omission_issues
        for detail in issue.affected_refs
    )


def test_injected_span_level_omission_is_rejected():
    source_input, draft, spans = _baseline()
    extra_span = _span("span-ex1b", 21, "既往存在器官移植史")
    spans["span-ex1b"] = extra_span
    source_input.allowed_source_span_ids.append("span-ex1b")
    source_input.source_materials.append(_material("span-ex1b", 21, "既往存在器官移植史"))
    source_input.parent_rule_catalog = (
        source_input.parent_rule_catalog.model_copy(
            update={
                "items": tuple(
                item.model_copy(
                    update={
                        "source_span_ids": list(item.source_span_ids)
                        + ["span-ex1b"]
                    }
                )
                    if item.item_id == "parent:syn-ex01"
                    else item
                    for item in source_input.parent_rule_catalog.items
                )
            }
        )
    )

    result = _evaluate(source_input, draft, spans)

    assert "PARENT_SOURCE_SEMANTIC_COVERAGE_MISSING" in _codes(
        result, "source_coverage"
    )


# --------------------------------------------------------------------------- 故障注入 2：虚构任选关系


@pytest.mark.parametrize("family", [FAMILY_PREGNANCY, FAMILY_MEDICATION])
def test_injected_any_from_term_list_without_marker_is_rejected(family):
    """同一对分支：原文明示“之一”时合法（防假阳性），原文无任何替代连接语时必须拒绝。"""
    source_input, draft, spans = _baseline()
    text = family["term_list_without_marker"]
    _set_material_text(source_input, "span-ex1", text)
    _set_parent_label(source_input, "parent:syn-ex01", text)
    component = draft.proposed_rules[2].components[0]
    component.expression = LogicalExpression(
        operator=LogicalOperator.ANY,
        children=[
            _exists_expression(
                f"{child.predicate.predicate_id}-z", attribute, [attribute]
            )
            for child, attribute in (
                (component.expression.children[0], family["branch_a"]),
                (component.expression.children[1], family["branch_b"]),
            )
        ],
    )
    draft.component_drafts[2].proposed_component = component
    draft.component_drafts[2].source_excerpts = [text]

    result = _evaluate(source_input, draft, spans)

    assert "DISJUNCTION_NOT_BOUND_TO_SOURCE" in _codes(result, "boolean_logic")


def test_injected_any_from_conjunction_is_rejected():
    source_input, draft, spans = _baseline()
    component = draft.proposed_rules[1].components[0]
    component.expression = LogicalExpression(
        operator=LogicalOperator.ANY,
        children=[
            _exists_expression(
                "predicate-syn-communicate-fab",
                "与研究者良好沟通",
                ["能够与研究者良好沟通"],
            ),
            _exists_expression(
                "predicate-syn-comply-fab",
                "遵守研究要求",
                ["能够遵守研究要求"],
            ),
        ],
    )
    draft.component_drafts[1].proposed_component = component

    result = _evaluate(source_input, draft, spans)

    assert "CONJUNCTION_CHANGED_TO_DISJUNCTION" in _codes(result, "boolean_logic")


# --------------------------------------------------------------------------- 故障注入 3：跨来源


def test_injected_component_source_from_another_parent_is_rejected():
    source_input, draft, spans = _baseline()
    draft.component_drafts[2].source_refs = ["span-ex1", "span-in1"]

    result = _evaluate(source_input, draft, spans)

    assert "COMPONENT_SOURCE_OUTSIDE_PARENT" in _codes(result, "source_coverage")


def test_injected_predicate_clause_from_another_parent_is_rejected():
    source_input, draft, spans = _baseline()
    component = draft.proposed_rules[2].components[0]
    pregnancy = component.expression.children[0]
    pregnancy.predicate.source_clauses = [
        "满足下列条件之一",
        "处于妊娠期",
        "年龄≥18周岁",
    ]
    draft.component_drafts[2].proposed_component = component

    result = _evaluate(source_input, draft, spans)

    assert "PREDICATE_CLAUSE_NOT_IN_SOURCE" in _codes(result, "source_coverage")


def test_injected_requirement_source_from_another_component_is_rejected():
    source_input, draft, spans = _baseline()
    draft.evidence_requirement_drafts[4].source_refs = ["span-ex2", "span-ex1"]

    result = _evaluate(source_input, draft, spans)

    assert "REQUIREMENT_SOURCE_OUTSIDE_ORIGIN" in _codes(result, "source_coverage")


# --------------------------------------------------------------------------- 故障注入 4：未绑定时间窗


def test_injected_dropped_time_qualifier_is_rejected():
    source_input, draft, spans = _baseline()
    component = draft.proposed_rules[4].components[0]
    child = component.expression.children[0]
    child.time_constraint = None
    child.predicate.source_clauses = ["无活动性结核病史"]
    draft.component_drafts[4].proposed_component = component
    draft.component_drafts[4].source_excerpts = ["随机前6个月内无活动性结核病史"]

    result = _evaluate(source_input, draft, spans)

    assert "TIME_QUALIFIER_DROPPED" in _codes(result, "temporal_semantics")


def test_injected_unbound_shared_window_is_rejected_per_branch():
    source_input, draft, spans = _baseline()
    component = draft.proposed_rules[3].components[0]
    for child in component.expression.children:
        branch = child.predicate.source_clauses[1]
        child.predicate.source_clauses = [branch]
    draft.component_drafts[3].proposed_component = component

    result = _evaluate(source_input, draft, spans)

    shared_issues = [
        issue
        for issue in _issues(result, "temporal_semantics")
        if issue.issue_code == "SHARED_TIME_QUALIFIER_NOT_BOUND"
    ]
    assert len(shared_issues) == 2


def test_invented_time_window_is_rejected():
    source_input, draft, spans = _baseline()
    component = draft.proposed_rules[0].components[0]
    child = component.expression
    child.time_constraint = TimeConstraint(
        anchor_type=AnchorType.RANDOMIZATION_DATE,
        direction=TimeDirection.BEFORE,
        upper_bound=TimeQuantity(value=6, unit=TimeUnit.MONTH),
    )
    component.evidence_requirements.append(
        _requirement("req-syn-in1-base", "component-in1", ReviewStage.BASELINE)
    )
    baseline_stage = next(
        stage
        for stage in draft.proposed_workflow_stages
        if stage.workflow_stage_id == "stage-syn-baseline"
    )
    baseline_stage.due_requirement_ids.append("req-syn-in1-base")
    draft.evidence_requirement_drafts.append(
        EvidenceRequirementDraft(
            draft_requirement_id="draft-req-syn-in1-base",
            draft_component_id="draft-component-in1",
            proposed_requirement=component.evidence_requirements[-1],
            source_refs=["span-in1"],
        )
    )

    result = _evaluate(source_input, draft, spans)

    assert "TIME_CONSTRAINT_NOT_IN_SOURCE" in _codes(result, "temporal_semantics")
