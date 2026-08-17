from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

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
    ProtocolPeriod,
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
    OccurrenceWindow,
    ProspectiveWindow,
    ProspectivePeriod,
    Rule,
    RuleComponent,
    TimeConstraint,
    TimeQuantity,
    TimeUnit,
    WorkflowStage,
)
from app.domain.publication import canonical_hash
from app.protocols.deconstruction_gate import ProtocolDeconstructionGate


NOW = datetime(2026, 8, 14, tzinfo=timezone.utc)
SHA = "a" * 64


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


def _span(span_id, order, *, degraded=False):
    return ProtocolSourceSpan(
        source_span_id=span_id,
        snapshot_id="snapshot-1",
        source_ref=f"body.p{order}",
        document_part=DocumentPart.BODY,
        section_index=0,
        block_order=order,
        render_artifact_id="render-1",
        render_page=order + 1,
        text_start=None if degraded else 0,
        text_end=None if degraded else 10,
        excerpt=None if degraded else "正式方案原文",
        precision=(
            SourceLocatorPrecision.PAGE_ONLY
            if degraded
            else SourceLocatorPrecision.TEXT_RANGE
        ),
        alignment_status=(
            AlignmentStatus.DEGRADED if degraded else AlignmentStatus.ALIGNED
        ),
        degradation_reason="仅作页面定位提示" if degraded else None,
    )


def _predicate(
    pid,
    attribute,
    value,
    unit,
    *,
    time=None,
    judgment=False,
    source_clause=None,
):
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
            requires_professional_judgment=judgment,
        ),
        time_constraint=time,
    )


def _requirement(rid, component_id, stage=ReviewStage.SCREENING):
    return EvidenceRequirement(
        requirement_id=rid,
        rule_component_id=component_id,
        fact_type="方案要求事实",
        due_stage=stage,
        description="核对正式原始资料和研究者记录",
    )


def _fixture():
    parent_items = [
        FrozenCatalogItem(
            item_id="parent:in01",
            kind=CatalogItemKind.PARENT_RULE,
            official_code="IN-01",
            label="年龄≥18岁",
            position=0,
            source_span_ids=["span-in"],
        ),
        FrozenCatalogItem(
            item_id="parent:ex01",
            kind=CatalogItemKind.PARENT_RULE,
            official_code="EX-01",
            label="ALT或AST≥1.5×ULN",
            position=1,
            source_span_ids=["span-ex"],
        ),
    ]
    procedure_items = [
        FrozenCatalogItem(
            item_id="procedure:screening:lab",
            kind=CatalogItemKind.REQUIRED_PROCEDURE,
            label="血生化检查",
            visit_instance="筛选期 D-28~D-1",
            review_stage=ReviewStage.SCREENING,
            position=0,
            source_span_ids=["span-proc-screen"],
        ),
        FrozenCatalogItem(
            item_id="procedure:baseline:lab",
            kind=CatalogItemKind.REQUIRED_PROCEDURE,
            label="血生化检查",
            visit_instance="基线 D1",
            review_stage=ReviewStage.BASELINE,
            position=1,
            source_span_ids=["span-proc-base"],
        ),
    ]
    identity = ProtocolIdentityDecision(
        identity_decision_id="identity-1",
        snapshot_id="snapshot-1",
        project_name="测试研究",
        project_code="TEST",
        protocol_code="TEST-001",
        official_version="V1.0",
        official_date=DateValue(
            value=date(2026, 8, 14), precision=DatePrecision.DAY
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
                    "span-in": "年龄≥18岁",
                    "span-ex": "ALT或AST≥1.5×ULN",
                    "span-proc-screen": "筛选期血生化检查",
                    "span-proc-base": "基线血生化检查",
                }[span_id],
            )
            for span_id, span in source_spans.items()
        ],
        parent_rule_catalog=_catalog(CatalogKind.OFFICIAL_PARENT_RULES, parent_items),
        required_procedure_catalog=_catalog(
            CatalogKind.REQUIRED_PROCEDURES, procedure_items
        ),
    )

    in_req = _requirement("req-in", "component-in")
    ex_req = _requirement("req-ex", "component-ex")
    proc_screen = EvidenceRequirement(
        requirement_id="req-proc-screen",
        procedure_catalog_item_id="procedure:screening:lab",
        fact_type="方案要求事实",
        due_stage=ReviewStage.SCREENING,
        description="核对正式原始资料和研究者记录",
    )
    proc_base = EvidenceRequirement(
        requirement_id="req-proc-base",
        procedure_catalog_item_id="procedure:baseline:lab",
        fact_type="方案要求事实",
        due_stage=ReviewStage.BASELINE,
        description="核对正式原始资料和研究者记录",
    )
    in_component = RuleComponent(
        rule_component_id="component-in",
        parent_rule_id="rule-in",
        display_code="IN-01a",
        title="年龄要求",
        expression=_predicate(
            "predicate-age", "年龄", 18, "岁", source_clause="年龄≥18岁"
        ),
        evidence_requirements=[in_req],
    )
    ex_component = RuleComponent(
        rule_component_id="component-ex",
        parent_rule_id="rule-ex",
        display_code="EX-01a",
        title="肝功能阈值",
        expression=LogicalExpression(
            operator=LogicalOperator.ANY,
            children=[
                _predicate(
                    "predicate-alt",
                    "ALT",
                    1.5,
                    "ULN",
                    source_clause="ALT或AST≥1.5×ULN",
                ),
                _predicate(
                    "predicate-ast",
                    "AST",
                    1.5,
                    "ULN",
                    source_clause="ALT或AST≥1.5×ULN",
                ),
            ],
        ),
        evidence_requirements=[ex_req],
    )
    rules = [
        Rule(
            rule_id="rule-in",
            official_code="IN-01",
            kind=RuleKind.INCLUSION,
            source_text="年龄≥18岁",
            study_phase=StudyPhase.PHASE_II,
            components=[in_component],
        ),
        Rule(
            rule_id="rule-ex",
            official_code="EX-01",
            kind=RuleKind.EXCLUSION,
            source_text="ALT或AST≥1.5×ULN",
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
                due_requirement_ids=["req-in", "req-ex", "req-proc-screen"],
            ),
            WorkflowStage(
                workflow_stage_id="stage-baseline",
                stage=ReviewStage.BASELINE,
                display_name="基线审核",
                visit_instance="基线 D1",
                due_requirement_ids=["req-proc-base"],
            ),
        ],
        protocol_metadata=ProtocolMetadataDraft(
            protocol_code_candidate="TEST-001",
            title_candidate="测试研究",
            version_candidate="V1.0",
            date_candidate="2026-08-14",
            study_phase_candidates=["Ⅱ期"],
            source_refs=["span-in"],
        ),
        component_drafts=[
            RuleComponentDraft(
                draft_component_id="draft-component-in",
                parent_official_code="IN-01",
                proposed_component=in_component,
                source_refs=["span-in"],
                source_excerpts=["年龄≥18岁"],
            ),
            RuleComponentDraft(
                draft_component_id="draft-component-ex",
                parent_official_code="EX-01",
                proposed_component=ex_component,
                source_refs=["span-ex"],
                source_excerpts=["ALT或AST≥1.5×ULN"],
            ),
        ],
        evidence_requirement_drafts=[
            EvidenceRequirementDraft(
                draft_requirement_id="draft-req-in",
                draft_component_id="draft-component-in",
                proposed_requirement=in_req,
                source_refs=["span-in"],
            ),
            EvidenceRequirementDraft(
                draft_requirement_id="draft-req-ex",
                draft_component_id="draft-component-ex",
                proposed_requirement=ex_req,
                source_refs=["span-ex"],
            ),
            EvidenceRequirementDraft(
                draft_requirement_id="draft-proc-screen",
                procedure_catalog_item_id="procedure:screening:lab",
                proposed_requirement=proc_screen,
                source_refs=["span-proc-screen"],
            ),
            EvidenceRequirementDraft(
                draft_requirement_id="draft-proc-base",
                procedure_catalog_item_id="procedure:baseline:lab",
                proposed_requirement=proc_base,
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
        coverage=CoverageSummary(processed_refs=list(source_spans)),
        source_refs=list(source_spans),
        created_by_agent_call_id="agent-call-1",
    )
    return source_input, draft, source_spans


def _issues(result, check_name):
    return next(item for item in result.checks if item.check_name == check_name).issues


def test_complete_draft_passes_all_twelve_checks():
    source_input, draft, spans = _fixture()
    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert result.publishable
    assert len(result.checks) == 12
    assert all(item.passed for item in result.checks)


def test_component_source_mapping_cannot_be_left_empty():
    source_input, draft, spans = _fixture()
    draft.component_drafts = []

    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )

    assert any(
        item.issue_code == "COMPONENT_DRAFT_COVERAGE_MISMATCH"
        for item in _issues(result, "tree_integrity")
    )


def test_procedure_requirement_requires_its_own_source_mapping():
    source_input, draft, spans = _fixture()
    draft.evidence_requirement_drafts = []

    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )

    assert any(
        item.issue_code == "PROCEDURE_REQUIREMENT_SOURCE_MAPPING_MISSING"
        for item in _issues(result, "evidence_coverage")
    )


def test_numeric_gate_uses_full_catalog_source_not_only_parent_heading():
    source_input, draft, spans = _fixture()
    source_input.parent_rule_catalog = source_input.parent_rule_catalog.model_copy(
        update={
            "items": (
                source_input.parent_rule_catalog.items[0].model_copy(
                    update={"label": "筛选时需满足以下标准"}
                ),
                source_input.parent_rule_catalog.items[1],
            )
        }
    )

    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )

    assert not any(
        item.issue_code in {"NUMERIC_VALUE_NOT_IN_SOURCE", "UNIT_NOT_IN_SOURCE"}
        and "IN-01" in item.problem
        for item in _issues(result, "numeric_semantics")
    )


def test_incidental_or_inside_one_condition_is_not_treated_as_top_level_or():
    source_input, draft, spans = _fixture()
    incidental_text = "既往病史≥2年，当前季节或同期检测结果阳性"
    source_input.parent_rule_catalog = source_input.parent_rule_catalog.model_copy(
        update={
            "items": (
                source_input.parent_rule_catalog.items[0].model_copy(
                    update={"label": incidental_text}
                ),
                source_input.parent_rule_catalog.items[1],
            )
        }
    )
    source_input.source_materials[0].text = incidental_text
    component = draft.proposed_rules[0].components[0]
    component.expression = LogicalExpression(
        operator=LogicalOperator.ALL,
        children=[
            _predicate("predicate-history", "病史年限", 2, "年"),
            _predicate("predicate-test", "检测结果", 1, "unitless"),
        ],
    )
    draft.component_drafts[0].proposed_component = component

    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )

    assert not any(
        item.issue_code == "DISJUNCTION_CHANGED_TO_CONJUNCTION"
        for item in _issues(result, "boolean_logic")
    )


def test_explicit_metric_alternatives_still_require_any_logic():
    source_input, draft, spans = _fixture()
    component = draft.proposed_rules[1].components[0]
    component.expression = LogicalExpression(
        operator=LogicalOperator.ALL,
        children=list(component.expression.children),
    )
    draft.component_drafts[1].proposed_component = component

    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )

    assert any(
        item.issue_code == "DISJUNCTION_CHANGED_TO_CONJUNCTION"
        for item in _issues(result, "boolean_logic")
    )


def test_frozen_catalog_stage_is_structural_not_agent_free_text():
    source_input, _draft, _spans = _fixture()
    procedure = source_input.required_procedure_catalog.items[0]
    with pytest.raises(ValueError, match="必须提供结构化审核阶段"):
        _catalog(
            CatalogKind.REQUIRED_PROCEDURES,
            [procedure.model_copy(update={"review_stage": None})],
        )

    parent = source_input.parent_rule_catalog.items[0]
    with pytest.raises(ValueError, match="不能携带审核阶段"):
        _catalog(
            CatalogKind.OFFICIAL_PARENT_RULES,
            [parent.model_copy(update={"review_stage": ReviewStage.SCREENING})],
        )


def test_two_spans_sharing_one_physical_range_are_not_formal_sources():
    source_input, draft, spans = _fixture()
    first = spans["span-in"]
    second = spans["span-ex"]
    spans["span-ex"] = second.model_copy(
        update={
            "render_artifact_id": first.render_artifact_id,
            "render_page": first.render_page,
            "text_start": first.text_start,
            "text_end": first.text_end,
        }
    )

    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )

    assert not result.publishable
    assert {
        issue.issue_code for issue in _issues(result, "source_coverage")
    } >= {
        "CATALOG_ITEM_WITHOUT_FORMAL_SOURCE",
        "DRAFT_SOURCE_NOT_FORMALLY_LOCATED",
    }


def test_and_mutated_to_or_is_rejected():
    source_input, draft, spans = _fixture()
    items = list(source_input.parent_rule_catalog.items)
    items[1] = items[1].model_copy(update={"label": "ALT且AST均≥1.5×ULN"})
    source_input.parent_rule_catalog = _catalog(
        CatalogKind.OFFICIAL_PARENT_RULES, items
    )
    next(
        material
        for material in source_input.source_materials
        if material.source_span_id == "span-ex"
    ).text = "ALT且AST均≥1.5×ULN"
    draft.component_drafts[1].source_excerpts = ["ALT且AST均≥1.5×ULN"]
    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert not result.publishable
    assert any(
        item.issue_code == "CONJUNCTION_CHANGED_TO_DISJUNCTION"
        for item in _issues(result, "boolean_logic")
    )


def test_metric_from_another_test_is_rejected():
    source_input, draft, spans = _fixture()
    predicate = draft.proposed_rules[1].components[0].expression.children[0].predicate
    predicate.attribute = "GGT"
    predicate.source_term = "GGT"
    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert any(
        item.issue_code == "METRIC_NOT_IN_SOURCE"
        for item in _issues(result, "numeric_semantics")
    )


def test_precise_excerpt_prevents_sibling_clause_contamination():
    source_input, draft, spans = _fixture()
    material = next(
        item
        for item in source_input.source_materials
        if item.source_span_id == "span-ex"
    )
    material.text = "ALT≥1.5×ULN；GGT异常或需研究者判断"
    component = draft.proposed_rules[1].components[0]
    component.expression = _predicate(
        "predicate-alt-only",
        "ALT",
        1.5,
        "ULN",
        source_clause="ALT≥1.5×ULN",
    )
    draft.component_drafts[1].proposed_component = component
    draft.component_drafts[1].source_excerpts = ["ALT≥1.5×ULN"]

    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )

    assert not any(
        issue.issue_code
        in {
            "DISJUNCTION_CHANGED_TO_CONJUNCTION",
            "INVESTIGATOR_JUDGMENT_DROPPED",
            "METRIC_NOT_IN_SOURCE",
        }
        for check in result.checks
        for issue in check.issues
    )


def test_precise_excerpt_requires_original_metric_binding():
    source_input, draft, spans = _fixture()
    draft.component_drafts[1].source_excerpts = ["ALT或AST≥1.5×ULN"]
    predicate = draft.proposed_rules[1].components[0].expression.children[0].predicate
    predicate.source_term = "GGT"
    draft.component_drafts[1].proposed_component = draft.proposed_rules[1].components[0]

    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )

    assert any(
        item.issue_code == "METRIC_NOT_IN_SOURCE"
        for item in _issues(result, "numeric_semantics")
    )


def test_noncontiguous_predicate_source_is_kept_as_exact_fragments():
    source_input, draft, spans = _fixture()
    text = "筛选访视前7天内需要全身性抗菌药、抗病毒药或抗真菌药治疗的感染"
    next(
        item
        for item in source_input.source_materials
        if item.source_span_id == "span-ex"
    ).text = text
    component = draft.proposed_rules[1].components[0]
    component.expression = AtomicExpression(
        predicate=AtomicPredicate(
            predicate_id="antiviral-infection",
            subject="受试者",
            attribute="需要全身性抗病毒药治疗的感染",
            source_clauses=["筛选访视前7天内需要全身性", "抗病毒药", "治疗的感染"],
            comparator=Comparator.EQ,
            value=True,
        ),
        time_constraint=TimeConstraint(
            anchor_type=AnchorType.SCREENING_DATE,
            direction=TimeDirection.BEFORE,
            upper_bound=TimeQuantity(value=7, unit=TimeUnit.DAY),
        ),
    )
    draft.component_drafts[1].proposed_component = component
    draft.component_drafts[1].source_excerpts = [text]

    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )

    assert not any(
        issue.issue_code == "PREDICATE_CLAUSE_NOT_IN_SOURCE"
        for check in result.checks
        for issue in check.issues
    )


def test_shared_time_qualifier_must_be_bound_to_each_or_branch():
    source_input, draft, spans = _fixture()
    text = "筛选前3个月内有酗酒史和/或药物滥用史"
    next(
        item
        for item in source_input.source_materials
        if item.source_span_id == "span-ex"
    ).text = text
    component = draft.proposed_rules[1].components[0]
    component.expression = LogicalExpression(
        operator=LogicalOperator.ANY,
        children=[
            AtomicExpression(
                predicate=AtomicPredicate(
                    predicate_id="alcohol-abuse",
                    subject="受试者",
                    attribute="有酗酒史",
                    source_clause="有酗酒史",
                    comparator=Comparator.EQ,
                    value=True,
                ),
                time_constraint=TimeConstraint(
                    anchor_type=AnchorType.SCREENING_DATE,
                    direction=TimeDirection.BEFORE,
                    upper_bound=TimeQuantity(value=3, unit=TimeUnit.MONTH),
                ),
            ),
            AtomicExpression(
                predicate=AtomicPredicate(
                    predicate_id="drug-abuse",
                    subject="受试者",
                    attribute="药物滥用史",
                    source_clause="药物滥用史",
                    comparator=Comparator.EQ,
                    value=True,
                ),
                time_constraint=TimeConstraint(
                    anchor_type=AnchorType.SCREENING_DATE,
                    direction=TimeDirection.BEFORE,
                    upper_bound=TimeQuantity(value=3, unit=TimeUnit.MONTH),
                ),
            ),
        ],
    )
    draft.component_drafts[1].proposed_component = component
    draft.component_drafts[1].source_excerpts = [text]

    missing_binding = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert len(
        [
            issue
            for issue in _issues(missing_binding, "temporal_semantics")
            if issue.issue_code == "SHARED_TIME_QUALIFIER_NOT_BOUND"
        ]
    ) == 2

    for child in component.expression.children:
        branch = child.predicate.source_clause
        child.predicate.source_clause = None
        child.predicate.source_clauses = ["筛选前3个月内", branch]
    accepted = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert not _issues(accepted, "temporal_semantics")


def test_noncontiguous_source_cannot_be_fabricated_as_one_clause():
    with pytest.raises(ValueError, match="不能同时使用"):
        AtomicPredicate(
            predicate_id="fabricated",
            subject="受试者",
            attribute="需要全身性抗病毒药治疗的感染",
            source_clause="筛选访视前7天内需要全身性抗病毒药治疗的感染",
            source_clauses=["筛选访视前7天内需要全身性", "抗病毒药", "治疗的感染"],
            comparator=Comparator.EQ,
            value=True,
        )


def test_each_atomic_clause_owns_only_its_own_time_anchor():
    source_input, draft, spans = _fixture()
    text = "随机前3个月内接种活疫苗，或计划在研究期间接种活疫苗"
    next(
        item
        for item in source_input.source_materials
        if item.source_span_id == "span-ex"
    ).text = text
    component = draft.proposed_rules[1].components[0]
    component.expression = LogicalExpression(
        operator=LogicalOperator.ANY,
        children=[
            AtomicExpression(
                predicate=AtomicPredicate(
                    predicate_id="recent-vaccine",
                    subject="受试者",
                    attribute="近期接种活疫苗",
                    source_clause="随机前3个月内接种活疫苗",
                    comparator=Comparator.EQ,
                    value=True,
                ),
                time_constraint=TimeConstraint(
                    anchor_type=AnchorType.RANDOMIZATION_DATE,
                    direction=TimeDirection.BEFORE,
                    upper_bound=TimeQuantity(value=3, unit=TimeUnit.MONTH),
                ),
            ),
            AtomicExpression(
                predicate=AtomicPredicate(
                    predicate_id="planned-vaccine",
                    subject="受试者",
                    attribute="计划接种活疫苗",
                    source_clause="计划在研究期间接种活疫苗",
                    comparator=Comparator.EQ,
                    value=True,
                    prospective_period=ProspectivePeriod(
                        period=ProtocolPeriod.STUDY_PERIOD
                    ),
                )
            ),
        ],
    )
    draft.component_drafts[1].proposed_component = component
    draft.component_drafts[1].source_excerpts = [text]

    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )

    assert not _issues(result, "temporal_semantics")


def test_future_plan_protocol_period_cannot_be_omitted():
    source_input, draft, spans = _fixture()
    text = "计划在治疗期间接种活疫苗"
    component = draft.proposed_rules[1].components[0]
    component.expression = _predicate(
        "planned-vaccine",
        "计划接种活疫苗",
        True,
        "unitless",
        source_clause=text,
    )
    draft.component_drafts[1].proposed_component = component
    draft.component_drafts[1].source_excerpts = [text]
    next(
        item
        for item in source_input.source_materials
        if item.source_span_id == "span-ex"
    ).text = text

    missing = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert any(
        issue.issue_code == "PROSPECTIVE_PERIOD_NOT_STRUCTURED"
        for issue in _issues(missing, "temporal_semantics")
    )

    component.expression.predicate.prospective_period = ProspectivePeriod(
        period=ProtocolPeriod.TREATMENT_PERIOD
    )
    accepted = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert not any(
        issue.issue_code.startswith("PROSPECTIVE_PERIOD")
        for issue in _issues(accepted, "temporal_semantics")
    )


def test_any_time_alternatives_may_keep_compound_event_inside_each_predicate():
    source_input, draft, spans = _fixture()
    text = "随机前12周或5个药物半衰期内参加过其他试验且使用过研究药物"
    next(
        item
        for item in source_input.source_materials
        if item.source_span_id == "span-ex"
    ).text = text
    component = draft.proposed_rules[1].components[0]
    component.expression = LogicalExpression(
        operator=LogicalOperator.ANY,
        children=[
            AtomicExpression(
                predicate=AtomicPredicate(
                    predicate_id="fixed-window",
                    subject="受试者",
                    attribute="参加过其他试验且使用过研究药物",
                    source_clause=text,
                    comparator=Comparator.EQ,
                    value=True,
                ),
                time_constraint=TimeConstraint(
                    anchor_type=AnchorType.RANDOMIZATION_DATE,
                    direction=TimeDirection.BEFORE,
                    upper_bound=TimeQuantity(value=12, unit=TimeUnit.WEEK),
                ),
            ),
            AtomicExpression(
                predicate=AtomicPredicate(
                    predicate_id="half-life-window",
                    subject="受试者",
                    attribute="参加过其他试验且使用过研究药物",
                    source_clause=text,
                    comparator=Comparator.EQ,
                    value=True,
                ),
                time_constraint=TimeConstraint(
                    anchor_type=AnchorType.RANDOMIZATION_DATE,
                    direction=TimeDirection.BEFORE,
                    half_life_multiplier=5,
                ),
            ),
        ],
    )
    draft.component_drafts[1].proposed_component = component
    draft.component_drafts[1].source_excerpts = [text]

    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )

    assert not any(
        issue.issue_code == "CONJUNCTION_CHANGED_TO_DISJUNCTION"
        for check in result.checks
        for issue in check.issues
    )


def test_qualitative_randomization_checkpoint_does_not_invent_time_window():
    source_input, draft, spans = _fixture()
    text = "无法满足方案规定的随机前药物洗脱周期"
    next(
        item
        for item in source_input.source_materials
        if item.source_span_id == "span-ex"
    ).text = text
    component = draft.proposed_rules[1].components[0]
    component.expression = AtomicExpression(
        predicate=AtomicPredicate(
            predicate_id="cannot-complete-washout",
            subject="受试者",
            attribute="无法满足药物洗脱周期",
            source_clause=text,
            comparator=Comparator.EQ,
            value=True,
        )
    )
    draft.component_drafts[1].proposed_component = component
    draft.component_drafts[1].source_excerpts = [text]

    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )

    assert not any(
        issue.issue_code == "TIME_ANCHOR_MISSING"
        for check in result.checks
        for issue in check.issues
    )


def test_future_plan_cannot_invent_randomization_date_constraint():
    source_input, draft, spans = _fixture()
    text = "随机前3个月内接种活疫苗，或计划在研究期间接种活疫苗"
    next(
        item
        for item in source_input.source_materials
        if item.source_span_id == "span-ex"
    ).text = text
    component = draft.proposed_rules[1].components[0]
    component.expression = AtomicExpression(
        predicate=AtomicPredicate(
            predicate_id="planned-vaccine",
            subject="受试者",
            attribute="计划接种活疫苗",
            source_clause="计划在研究期间接种活疫苗",
            comparator=Comparator.EQ,
            value=True,
        ),
        time_constraint=TimeConstraint(
            anchor_type=AnchorType.RANDOMIZATION_DATE,
            direction=TimeDirection.AFTER,
        ),
    )
    draft.component_drafts[1].proposed_component = component
    draft.component_drafts[1].source_excerpts = [text]

    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )

    assert any(
        item.issue_code == "TIME_CONSTRAINT_NOT_IN_SOURCE"
        for item in _issues(result, "temporal_semantics")
    )


def test_screening_and_baseline_are_stage_requirements_not_date_constraints():
    source_input, draft, spans = _fixture()
    text = "筛选或基线时，ALT或AST≥1.5×ULN"
    next(
        item
        for item in source_input.source_materials
        if item.source_span_id == "span-ex"
    ).text = text
    component = draft.proposed_rules[1].components[0]
    component.evidence_requirements = [
        _requirement("req-ex-screening", "component-ex", ReviewStage.SCREENING),
        _requirement("req-ex-baseline", "component-ex", ReviewStage.BASELINE),
    ]
    draft.component_drafts[1].proposed_component = component
    draft.component_drafts[1].source_excerpts = [text]

    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )

    assert not any(
        issue.issue_code
        in {
            "REVIEW_STAGE_REQUIREMENT_MISSING",
            "REVIEW_STAGE_USED_AS_DATE_CONSTRAINT",
        }
        for issue in _issues(result, "temporal_semantics")
    )


def test_stage_cue_cannot_be_represented_as_baseline_date_constraint():
    source_input, draft, spans = _fixture()
    text = "筛选或基线时，ALT或AST≥1.5×ULN"
    next(
        item
        for item in source_input.source_materials
        if item.source_span_id == "span-ex"
    ).text = text
    component = draft.proposed_rules[1].components[0]
    component.evidence_requirements = [
        _requirement("req-ex-screening", "component-ex", ReviewStage.SCREENING),
        _requirement("req-ex-baseline", "component-ex", ReviewStage.BASELINE),
    ]
    component.expression.children[0].time_constraint = TimeConstraint(
        anchor_type=AnchorType.BASELINE_DATE,
        direction=TimeDirection.ON,
    )
    draft.component_drafts[1].proposed_component = component
    draft.component_drafts[1].source_excerpts = [text]

    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )

    assert any(
        issue.issue_code == "REVIEW_STAGE_USED_AS_DATE_CONSTRAINT"
        for issue in _issues(result, "temporal_semantics")
    )


def test_first_dose_anchor_is_distinct_from_generic_event_date():
    source_input, draft, spans = _fixture()
    text = "首次给药前7天内使用过抗菌药"
    next(
        item
        for item in source_input.source_materials
        if item.source_span_id == "span-ex"
    ).text = text
    component = draft.proposed_rules[1].components[0]
    component.expression = AtomicExpression(
        predicate=AtomicPredicate(
            predicate_id="recent-antibiotic",
            subject="受试者",
            attribute="使用过抗菌药",
            source_clause=text,
            comparator=Comparator.EQ,
            value=True,
        ),
        time_constraint=TimeConstraint(
            anchor_type=AnchorType.FIRST_DOSE_DATE,
            direction=TimeDirection.BEFORE,
            upper_bound=TimeQuantity(value=7, unit=TimeUnit.DAY),
        ),
    )
    draft.component_drafts[1].proposed_component = component
    draft.component_drafts[1].source_excerpts = [text]

    accepted = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert not _issues(accepted, "temporal_semantics")

    component.expression.time_constraint.anchor_type = AnchorType.EVENT_DATE
    rejected = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert any(
        issue.issue_code == "TIME_ANCHOR_CHANGED"
        for issue in _issues(rejected, "temporal_semantics")
    )


def test_missing_baseline_stage_requirement_is_blocked():
    source_input, draft, spans = _fixture()
    text = "筛选或基线时，ALT或AST≥1.5×ULN"
    next(
        item
        for item in source_input.source_materials
        if item.source_span_id == "span-ex"
    ).text = text
    draft.component_drafts[1].source_excerpts = [text]

    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )

    assert any(
        issue.issue_code == "REVIEW_STAGE_REQUIREMENT_MISSING"
        for issue in _issues(result, "temporal_semantics")
    )


def test_component_source_may_use_multiple_exact_noncontiguous_fragments():
    source_input, draft, spans = _fixture()
    text = "筛选前3个月内献血或失血≥400mL"
    next(
        item
        for item in source_input.source_materials
        if item.source_span_id == "span-ex"
    ).text = text
    draft.component_drafts[1].source_excerpts = ["筛选前3个月内", "失血≥400mL"]

    accepted = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert not any(
        issue.issue_code == "COMPONENT_EXCERPT_NOT_IN_SOURCE"
        for issue in _issues(accepted, "source_coverage")
    )

    draft.component_drafts[1].source_excerpts = ["筛选前3个月内失血≥400mL"]
    rejected = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert any(
        issue.issue_code == "COMPONENT_EXCERPT_NOT_IN_SOURCE"
        for issue in _issues(rejected, "source_coverage")
    )


def test_comparator_direction_cannot_be_reversed():
    source_input, draft, spans = _fixture()
    predicate = draft.proposed_rules[0].components[0].expression.predicate
    predicate.comparator = Comparator.LT
    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert any(
        item.issue_code == "COMPARATOR_CHANGED"
        for item in _issues(result, "numeric_semantics")
    )


def test_randomization_anchor_cannot_be_replaced_by_screening():
    source_input, draft, spans = _fixture()
    items = list(source_input.parent_rule_catalog.items)
    items[0] = items[0].model_copy(update={"label": "随机前28天内年龄≥18岁"})
    source_input.parent_rule_catalog = _catalog(
        CatalogKind.OFFICIAL_PARENT_RULES, items
    )
    next(
        material
        for material in source_input.source_materials
        if material.source_span_id == "span-in"
    ).text = "随机前28天内年龄≥18岁"
    draft.component_drafts[0].source_excerpts = ["随机前28天内年龄≥18岁"]
    draft.proposed_rules[0].components[0].expression.predicate.source_clause = (
        "随机前28天内年龄≥18岁"
    )
    draft.proposed_rules[0].components[0].expression.time_constraint = TimeConstraint(
        anchor_type=AnchorType.SCREENING_DATE,
        direction=TimeDirection.BEFORE,
        upper_bound_days=28,
    )
    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert any(
        item.issue_code == "TIME_ANCHOR_CHANGED"
        for item in _issues(result, "temporal_semantics")
    )


def test_screening_and_baseline_procedure_instances_cannot_be_merged():
    source_input, draft, spans = _fixture()
    draft.procedure_catalog_mappings.pop()
    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert any(
        item.issue_code == "PROCEDURE_CATALOG_NOT_EXACTLY_COVERED"
        for item in _issues(result, "workflow_coverage")
    )


def test_wrong_visit_instance_on_mapped_stage_is_blocked():
    """目录项是「筛选期 D-28~D-1」，映射到「基线 D1」节点 -> 访视错配。"""
    source_input, draft, spans = _fixture()
    mapping = draft.procedure_catalog_mappings[0]
    draft.procedure_catalog_mappings[0] = mapping.model_copy(
        update={"proposed_workflow_stage_id": "stage-baseline"}
    )
    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    issues = _issues(result, "workflow_coverage")
    assert any(item.issue_code == "PROCEDURE_REVIEW_STAGE_MISMATCH" for item in issues)
    assert any(item.issue_code == "PROCEDURE_VISIT_INSTANCE_MISMATCH" for item in issues)


def test_node_without_visit_instance_cannot_host_frozen_procedure():
    """冻结必做项目必带 visit_instance；无访视实例的节点不能承载。"""
    source_input, draft, spans = _fixture()
    draft.proposed_workflow_stages[0] = (
        draft.proposed_workflow_stages[0].model_copy(update={"visit_instance": None})
    )
    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert any(
        item.issue_code == "PROCEDURE_VISIT_INSTANCE_MISMATCH"
        for item in _issues(result, "workflow_coverage")
    )


def test_same_stage_two_visit_instances_cannot_collide_identity():
    """同一 ReviewStage 的两个访视实例必须各自独立节点；重复身份被拒。"""
    source_input, draft, spans = _fixture()
    draft.proposed_workflow_stages.append(
        draft.proposed_workflow_stages[0].model_copy(
            update={
                "workflow_stage_id": "stage-screening-visit-2",
                "due_requirement_ids": [],
            }
        )
    )
    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    issues = _issues(result, "workflow_coverage")
    assert any(item.issue_code == "DUPLICATE_VISIT_NODE_IDENTITY" for item in issues)


def test_same_stage_second_visit_cannot_overwrite_first_mapping():
    """同阶段多访视：两个目录项（筛选 D-28~D-1 与筛选 D1）必须映射到各自
    访视实例节点，不能被最后一个节点覆盖。"""
    source_input, draft, spans = _fixture()
    # 增加第二个筛选访视目录项与对应节点、映射、资料要求。
    second_visit_item = source_input.required_procedure_catalog.items[0].model_copy(
        update={
            "item_id": "procedure:screening:lab:visit-2",
            "visit_instance": "筛选期 D1",
            "position": 2,
            "source_span_ids": ["span-proc-screen-2"],
        }
    )
    source_input.required_procedure_catalog = (
        source_input.required_procedure_catalog.model_copy(
            update={
                "items": (
                    *source_input.required_procedure_catalog.items,
                    second_visit_item,
                )
            }
        )
    )
    spans["span-proc-screen-2"] = _span("span-proc-screen-2", 5)
    source_input.allowed_source_span_ids.append("span-proc-screen-2")
    source_input.source_materials.append(
        ProtocolSourceMaterial(
            source_span_id="span-proc-screen-2",
            source_ref="body.p5",
            block_order=5,
            text="筛选 D1 血生化检查",
        )
    )
    second_requirement = EvidenceRequirement(
        requirement_id="req-proc-screen-2",
        procedure_catalog_item_id="procedure:screening:lab:visit-2",
        fact_type="方案要求事实",
        due_stage=ReviewStage.SCREENING,
        description="核对筛选 D1 血生化正式原始资料",
    )
    draft.proposed_workflow_stages.append(
        WorkflowStage(
            workflow_stage_id="stage-screening-v2",
            stage=ReviewStage.SCREENING,
            display_name="筛选 D1 审核",
            visit_instance="筛选期 D1",
            due_requirement_ids=["req-proc-screen-2"],
        )
    )
    draft.procedure_catalog_mappings.append(
        ProcedureCatalogMapping(
            catalog_item_id="procedure:screening:lab:visit-2",
            proposed_requirement_ids=["req-proc-screen-2"],
            proposed_workflow_stage_id="stage-screening-v2",
            source_span_ids=["span-proc-screen-2"],
        )
    )
    draft.evidence_requirement_drafts.append(
        EvidenceRequirementDraft(
            draft_requirement_id="draft-proc-screen-2",
            procedure_catalog_item_id="procedure:screening:lab:visit-2",
            proposed_requirement=second_requirement,
            source_refs=["span-proc-screen-2"],
        )
    )
    # 两个筛选访视实例分别映射到各自节点 -> 全部检查通过
    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert not _issues(result, "workflow_coverage"), "同阶段两个访视实例应各自保留"

    # 把第二个目录项改绑到第一个筛选节点 -> 访视实例错配（不能覆盖/合并）
    draft.procedure_catalog_mappings[2] = (
        draft.procedure_catalog_mappings[2].model_copy(
            update={"proposed_workflow_stage_id": "stage-screening"}
        )
    )
    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert any(
        item.issue_code == "PROCEDURE_VISIT_INSTANCE_MISMATCH"
        for item in _issues(result, "workflow_coverage")
    )


def test_procedure_requirement_listed_in_wrong_node_is_blocked():
    """流程资料要求必须列在其目录映射指向的同一节点。"""
    source_input, draft, spans = _fixture()
    draft.proposed_workflow_stages[1] = (
        draft.proposed_workflow_stages[1].model_copy(
            update={"due_requirement_ids": ["req-proc-screen"]}
        )
    )
    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert any(
        item.issue_code == "PROCEDURE_REQUIREMENT_WRONG_NODE"
        for item in _issues(result, "workflow_coverage")
    )


def test_requirement_due_stage_mismatch_with_listing_node_is_blocked():
    """资料要求 due_stage 必须与所列举节点阶段一致。"""
    source_input, draft, spans = _fixture()
    draft.proposed_workflow_stages[0] = (
        draft.proposed_workflow_stages[0].model_copy(
            update={"due_requirement_ids": ["req-proc-base"]}
        )
    )
    draft.proposed_workflow_stages[1] = (
        draft.proposed_workflow_stages[1].model_copy(
            update={"due_requirement_ids": []}
        )
    )
    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert any(
        item.issue_code == "REQUIREMENT_DUE_STAGE_MISMATCH"
        for item in _issues(result, "workflow_coverage")
    )


def test_parent_mapping_cannot_rebind_to_foreign_catalog_source():
    """父规则映射来源必须等于冻结目录项来源；换绑其他目录来源被拒。"""
    source_input, draft, spans = _fixture()
    draft.parent_catalog_mappings[0] = (
        draft.parent_catalog_mappings[0].model_copy(
            update={"source_span_ids": ["span-ex"]}
        )
    )
    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert any(
        item.issue_code == "PARENT_MAPPING_SOURCE_MISMATCH"
        for item in _issues(result, "parent_catalog")
    )


def test_requirement_source_outside_component_scope_is_blocked():
    """子规则资料要求来源超出其所属子规则来源范围被拒。"""
    source_input, draft, spans = _fixture()
    draft.evidence_requirement_drafts[0] = (
        draft.evidence_requirement_drafts[0].model_copy(
            update={"source_refs": ["span-ex"]}
        )
    )
    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert any(
        item.issue_code == "REQUIREMENT_SOURCE_OUTSIDE_COMPONENT"
        for item in _issues(result, "source_coverage")
    )


def test_procedure_requirement_source_outside_catalog_scope_is_blocked():
    """流程资料要求来源超出其必做项目录项来源范围被拒。"""
    source_input, draft, spans = _fixture()
    draft.evidence_requirement_drafts[2] = (
        draft.evidence_requirement_drafts[2].model_copy(
            update={"source_refs": ["span-proc-base"]}
        )
    )
    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert any(
        item.issue_code == "PROCEDURE_REQUIREMENT_SOURCE_OUTSIDE_CATALOG"
        for item in _issues(result, "source_coverage")
    )


def test_degraded_page_hint_cannot_satisfy_source_coverage():
    source_input, draft, spans = _fixture()
    spans["span-ex"] = _span("span-ex", 2, degraded=True)
    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert any(
        item.issue_code == "CATALOG_ITEM_WITHOUT_FORMAL_SOURCE"
        for item in _issues(result, "source_coverage")
    )


def test_screening_visit_before_window_requires_screening_anchor():
    source_input, draft, spans = _fixture()
    text = "筛选访视前7天内需要抗菌药治疗的感染"
    component = draft.proposed_rules[1].components[0]
    component.expression = _predicate(
        "predicate-infection",
        "需要抗菌药治疗的感染",
        True,
        "unitless",
        source_clause=text,
    )
    draft.component_drafts[1].proposed_component = component
    draft.component_drafts[1].source_excerpts = [text]
    next(
        item
        for item in source_input.source_materials
        if item.source_span_id == "span-ex"
    ).text = text

    missing = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert any(
        issue.issue_code == "TIME_ANCHOR_MISSING"
        for issue in _issues(missing, "temporal_semantics")
    )

    component.expression.time_constraint = TimeConstraint(
        anchor_type=AnchorType.SCREENING_DATE,
        direction=TimeDirection.BEFORE,
        upper_bound=TimeQuantity(value=7, unit=TimeUnit.DAY),
    )
    accepted = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert not any(
        issue.issue_code.startswith("TIME_ANCHOR")
        for issue in _issues(accepted, "temporal_semantics")
    )


def test_duration_without_named_anchor_is_kept_as_interpretation_gap():
    source_input, draft, spans = _fixture()
    text = "6个月内存在或疑似蠕虫感染"
    component = draft.proposed_rules[1].components[0]
    component.expression = _predicate(
        "predicate-helminth",
        "存在或疑似蠕虫感染",
        True,
        "unitless",
        source_clause=text,
    )
    draft.component_drafts[1].proposed_component = component
    draft.component_drafts[1].source_excerpts = [text]
    next(
        item
        for item in source_input.source_materials
        if item.source_span_id == "span-ex"
    ).text = text

    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert any(
        issue.issue_code == "TIME_ANCHOR_UNRESOLVED"
        for issue in _issues(result, "temporal_semantics")
    )


def test_component_time_qualifier_cannot_disappear_from_all_predicates():
    source_input, draft, spans = _fixture()
    text = "筛选时存在鼻部疾病（如1年内鼻术后状态），且可能影响疗效评价"
    component = draft.proposed_rules[1].components[0]
    component.expression = _predicate(
        "predicate-nasal-disease",
        "存在鼻部疾病且可能影响疗效评价",
        True,
        "unitless",
        source_clause="筛选时存在鼻部疾病",
    )
    draft.component_drafts[1].proposed_component = component
    draft.component_drafts[1].source_excerpts = [text]
    next(
        item
        for item in source_input.source_materials
        if item.source_span_id == "span-ex"
    ).text = text

    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert any(
        issue.issue_code == "TIME_QUALIFIER_DROPPED"
        for issue in _issues(result, "temporal_semantics")
    )


def test_parenthetical_time_note_only_applies_to_its_named_sibling():
    source_input, draft, spans = _fixture()
    text = (
        "筛选或基线时，生命体征、体格检查、12-导联心电图、"
        "胸部CT（可接受1个月内的CT检查结果）异常且有临床意义"
    )
    component = draft.proposed_rules[1].components[0]
    component.expression = LogicalExpression(
        operator=LogicalOperator.ANY,
        children=[
            _predicate(
                f"predicate-{index}",
                attribute,
                True,
                "unitless",
                source_clause=text,
            )
            for index, attribute in enumerate(
                ("生命体征", "体格检查", "12-导联心电图", "胸部CT"),
                start=1,
            )
        ],
    )
    draft.component_drafts[1].proposed_component = component
    draft.component_drafts[1].source_excerpts = [text]
    next(
        item
        for item in source_input.source_materials
        if item.source_span_id == "span-ex"
    ).text = text

    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    unresolved = [
        issue
        for issue in _issues(result, "temporal_semantics")
        if issue.issue_code == "TIME_ANCHOR_UNRESOLVED"
    ]
    assert len(unresolved) == 1
    assert unresolved[0].affected_refs == ["predicate-4"]


def test_frequency_definition_is_not_misread_as_review_lookback():
    source_input, draft, spans = _fixture()
    text = "复发性带状疱疹（2年内发生2次或以上）"
    component = draft.proposed_rules[1].components[0]
    component.expression = AtomicExpression(
        predicate=AtomicPredicate(
            predicate_id="predicate-recurrence",
            subject="受试者",
            attribute="复发性带状疱疹发生次数",
            comparator=Comparator.GTE,
            value=2,
            unit="次",
            occurrence_window=OccurrenceWindow(
                duration=TimeQuantity(value=2, unit=TimeUnit.YEAR)
            ),
            source_clause=text,
        )
    )
    draft.component_drafts[1].proposed_component = component
    draft.component_drafts[1].source_excerpts = [text]
    next(
        item
        for item in source_input.source_materials
        if item.source_span_id == "span-ex"
    ).text = text
    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert not any(
        issue.issue_code in {
            "TIME_ANCHOR_UNRESOLVED",
            "FREQUENCY_WINDOW_NOT_STRUCTURED",
        }
        for issue in _issues(result, "temporal_semantics")
    )


def test_frequency_definition_without_count_window_is_blocked():
    source_input, draft, spans = _fixture()
    text = "复发性带状疱疹（2年内发生2次或以上）"
    component = draft.proposed_rules[1].components[0]
    component.expression = _predicate(
        "predicate-recurrence", "复发性带状疱疹", True, "unitless", source_clause=text
    )
    draft.component_drafts[1].proposed_component = component
    draft.component_drafts[1].source_excerpts = [text]
    next(
        item for item in source_input.source_materials
        if item.source_span_id == "span-ex"
    ).text = text
    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert any(
        issue.issue_code == "FREQUENCY_WINDOW_NOT_STRUCTURED"
        for issue in _issues(result, "temporal_semantics")
    )


def test_nested_frequency_definition_is_preserved_on_boolean_history():
    source_input, draft, spans = _fixture()
    text = "有严重带状疱疹既往史（包括复发性带状疱疹（2年内发生2次或以上））"
    component = draft.proposed_rules[1].components[0]
    component.expression = AtomicExpression(
        predicate=AtomicPredicate(
            predicate_id="predicate-severe-history",
            subject="受试者",
            attribute="有严重带状疱疹既往史",
            comparator=Comparator.EQ,
            value=True,
            source_clause=text,
            occurrence_window=OccurrenceWindow(
                duration=TimeQuantity(value=2, unit=TimeUnit.YEAR),
                minimum_count=2,
            ),
        )
    )
    draft.component_drafts[1].proposed_component = component
    draft.component_drafts[1].source_excerpts = [text]
    next(
        item
        for item in source_input.source_materials
        if item.source_span_id == "span-ex"
    ).text = text

    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert not any(
        issue.issue_code.startswith("FREQUENCY_WINDOW")
        for issue in _issues(result, "temporal_semantics")
    )


def test_frequency_definition_on_component_cannot_disappear_from_child_predicates():
    source_input, draft, spans = _fixture()
    text = (
        "有严重带状疱疹既往史（包括复发性带状疱疹"
        "（2年内发生2次或以上））或有感染现病史"
    )
    component = draft.proposed_rules[1].components[0]
    component.expression = LogicalExpression(
        operator=LogicalOperator.ANY,
        children=[
            _predicate(
                "predicate-history",
                "有严重带状疱疹既往史",
                True,
                "unitless",
                source_clause="有严重带状疱疹既往史",
            ),
            _predicate(
                "predicate-active",
                "有感染现病史",
                True,
                "unitless",
                source_clause="有感染现病史",
            ),
        ],
    )
    draft.component_drafts[1].proposed_component = component
    draft.component_drafts[1].source_excerpts = [text]
    next(
        item
        for item in source_input.source_materials
        if item.source_span_id == "span-ex"
    ).text = text

    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert any(
        issue.issue_code == "FREQUENCY_WINDOW_NOT_STRUCTURED"
        and issue.affected_refs == [component.rule_component_id]
        for issue in _issues(result, "temporal_semantics")
    )


def test_frequency_definition_bound_to_unrelated_sibling_is_still_blocked():
    source_input, draft, spans = _fixture()
    text = "复发性带状疱疹（2年内发生2次或以上）或有感染现病史"
    component = draft.proposed_rules[1].components[0]
    component.expression = LogicalExpression(
        operator=LogicalOperator.ANY,
        children=[
            _predicate(
                "predicate-recurrence",
                "复发性带状疱疹",
                True,
                "unitless",
                source_clause="复发性带状疱疹",
            ),
            AtomicExpression(
                predicate=AtomicPredicate(
                    predicate_id="predicate-active",
                    subject="受试者",
                    attribute="有感染现病史",
                    comparator=Comparator.EQ,
                    value=True,
                    source_clauses=["2年内发生2次或以上", "有感染现病史"],
                    occurrence_window=OccurrenceWindow(
                        duration=TimeQuantity(value=2, unit=TimeUnit.YEAR),
                        minimum_count=2,
                    ),
                )
            ),
        ],
    )
    draft.component_drafts[1].proposed_component = component
    draft.component_drafts[1].source_excerpts = [text]
    next(
        item
        for item in source_input.source_materials
        if item.source_span_id == "span-ex"
    ).text = text

    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert any(
        issue.issue_code == "FREQUENCY_WINDOW_NOT_STRUCTURED"
        and issue.affected_refs == [component.rule_component_id]
        for issue in _issues(result, "temporal_semantics")
    )


def test_parent_source_fragment_does_not_hide_frequency_on_next_fragment():
    source_input, draft, spans = _fixture()
    text = "有严重带状疱疹既往史，包括复发性带状疱疹（2年内发生2次或以上）"
    component = draft.proposed_rules[1].components[0]
    component.expression = AtomicExpression(
        predicate=AtomicPredicate(
            predicate_id="predicate-recurrence",
            subject="受试者",
            attribute="复发性带状疱疹发生次数",
            source_term="复发性带状疱疹",
            comparator=Comparator.GTE,
            value=2,
            unit="次",
            source_clauses=[
                "有严重带状疱疹既往史",
                "复发性带状疱疹（2年内发生2次或以上）",
            ],
            occurrence_window=OccurrenceWindow(
                duration=TimeQuantity(value=2, unit=TimeUnit.YEAR)
            ),
        )
    )
    draft.component_drafts[1].proposed_component = component
    draft.component_drafts[1].source_excerpts = [text]
    next(
        item
        for item in source_input.source_materials
        if item.source_span_id == "span-ex"
    ).text = text

    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert not any(
        issue.issue_code.startswith("FREQUENCY_WINDOW")
        for issue in _issues(result, "temporal_semantics")
    )


def test_occurrence_days_per_period_require_and_accept_rolling_window():
    source_input, draft, spans = _fixture()
    text = "白天户外活动十分有限，定义为1周≥4天无任何白天户外活动"
    component = draft.proposed_rules[1].components[0]
    component.expression = _predicate(
        "predicate-outdoor",
        "无任何白天户外活动的天数",
        4,
        "天",
        source_clause=text,
    )
    draft.component_drafts[1].proposed_component = component
    draft.component_drafts[1].source_excerpts = [text]
    next(
        item
        for item in source_input.source_materials
        if item.source_span_id == "span-ex"
    ).text = text

    missing = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert any(
        issue.issue_code == "FREQUENCY_WINDOW_NOT_STRUCTURED"
        for issue in _issues(missing, "temporal_semantics")
    )

    component.expression = AtomicExpression(
        predicate=AtomicPredicate(
            predicate_id="predicate-outdoor",
            subject="受试者",
            attribute="无任何白天户外活动的天数",
            source_term="无任何白天户外活动",
            comparator=Comparator.GTE,
            value=4,
            unit="天",
            source_clause=text,
            occurrence_window=OccurrenceWindow(
                duration=TimeQuantity(value=1, unit=TimeUnit.WEEK)
            ),
        )
    )
    draft.component_drafts[1].proposed_component = component
    preserved = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert not any(
        issue.issue_code.startswith("FREQUENCY_WINDOW")
        for issue in _issues(preserved, "temporal_semantics")
    )


def test_nested_any_inside_required_all_preserves_disjunction():
    source_input, draft, spans = _fixture()
    text = "治疗后血压仍控制不佳（收缩压≥160mmHg或舒张压≥100mmHg）"
    component = draft.proposed_rules[1].components[0]
    component.expression = LogicalExpression(
        operator=LogicalOperator.ALL,
        children=[
            _predicate(
                "predicate-treatment",
                "治疗后仍控制不佳",
                True,
                "unitless",
                source_clause="治疗后血压仍控制不佳",
            ),
            LogicalExpression(
                operator=LogicalOperator.ANY,
                children=[
                    _predicate(
                        "predicate-sbp",
                        "收缩压",
                        160,
                        "mmHg",
                        source_clause="收缩压≥160mmHg",
                    ),
                    _predicate(
                        "predicate-dbp",
                        "舒张压",
                        100,
                        "mmHg",
                        source_clause="舒张压≥100mmHg",
                    ),
                ],
            ),
        ],
    )
    draft.component_drafts[1].proposed_component = component
    draft.component_drafts[1].source_excerpts = [text]
    next(
        item
        for item in source_input.source_materials
        if item.source_span_id == "span-ex"
    ).text = text

    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert not any(
        issue.issue_code == "DISJUNCTION_CHANGED_TO_CONJUNCTION"
        for issue in _issues(result, "boolean_logic")
    )


def test_future_plan_window_requires_named_milestone_and_duration():
    source_input, draft, spans = _fixture()
    text = "研究完成后8周内计划接种减毒活疫苗"
    component = draft.proposed_rules[1].components[0]
    component.expression = _predicate(
        "predicate-vaccine-plan", "计划接种减毒活疫苗", True, "unitless", source_clause=text
    )
    draft.component_drafts[1].proposed_component = component
    draft.component_drafts[1].source_excerpts = [text]
    next(
        item for item in source_input.source_materials
        if item.source_span_id == "span-ex"
    ).text = text
    missing = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert any(
        issue.issue_code == "PROSPECTIVE_WINDOW_NOT_STRUCTURED"
        for issue in _issues(missing, "temporal_semantics")
    )
    component.expression.predicate.prospective_window = ProspectiveWindow(
        anchor_type=AnchorType.STUDY_COMPLETION_DATE,
        upper_bound=TimeQuantity(value=8, unit=TimeUnit.WEEK),
    )
    accepted = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert not any(
        issue.issue_code == "PROSPECTIVE_WINDOW_NOT_STRUCTURED"
        for issue in _issues(accepted, "temporal_semantics")
    )


def test_component_level_parenthetical_exception_cannot_cover_any_branches():
    source_input, draft, spans = _fixture()
    text = "患有恶性肿瘤（皮肤原位癌除外）或淋巴组织增生性疾病"
    component = draft.proposed_rules[1].components[0]
    component.expression = LogicalExpression(
        operator=LogicalOperator.ANY,
        children=[
            _predicate("predicate-cancer", "恶性肿瘤", True, "unitless", source_clause="患有恶性肿瘤"),
            _predicate("predicate-lymph", "淋巴组织增生性疾病", True, "unitless", source_clause="淋巴组织增生性疾病"),
        ],
    )
    component.exception_expression = _predicate(
        "predicate-exception", "皮肤原位癌", True, "unitless", source_clause="皮肤原位癌除外"
    )
    draft.component_drafts[1].proposed_component = component
    draft.component_drafts[1].source_excerpts = [text]
    next(
        item for item in source_input.source_materials
        if item.source_span_id == "span-ex"
    ).text = text
    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert any(
        issue.issue_code == "EXCEPTION_SCOPE_CHANGED"
        for issue in _issues(result, "boolean_logic")
    )


def test_procedure_mapping_cannot_borrow_component_requirement():
    source_input, draft, spans = _fixture()
    draft.procedure_catalog_mappings[0].proposed_requirement_ids = ["req-in"]
    draft.proposed_workflow_stages[0].due_requirement_ids = [
        "req-in", "req-ex"
    ]
    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert any(
        issue.issue_code == "PROCEDURE_REQUIREMENT_NOT_FOUND"
        for issue in _issues(result, "evidence_coverage")
    )


def test_workflow_requirement_cannot_be_listed_twice():
    source_input, draft, spans = _fixture()
    draft.proposed_workflow_stages[0].due_requirement_ids.append("req-in")
    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert any(
        issue.issue_code == "DUPLICATE_WORKFLOW_REQUIREMENT"
        for issue in _issues(result, "workflow_coverage")
    )


def test_procedure_requirement_cannot_be_mapped_twice():
    source_input, draft, spans = _fixture()
    draft.procedure_catalog_mappings[1].proposed_requirement_ids.append(
        "req-proc-screen"
    )
    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert any(
        issue.issue_code == "DUPLICATE_PROCEDURE_REQUIREMENT_MAPPING"
        for issue in _issues(result, "evidence_coverage")
    )


def test_orphan_evidence_requirement_draft_is_blocked():
    source_input, draft, spans = _fixture()
    orphan = draft.evidence_requirement_drafts[2].model_copy(deep=True)
    orphan.draft_requirement_id = "draft-orphan"
    orphan.proposed_requirement.requirement_id = "req-orphan"
    draft.evidence_requirement_drafts.append(orphan)
    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert any(
        issue.issue_code == "EVIDENCE_REQUIREMENT_DRAFT_COVERAGE_MISMATCH"
        for issue in _issues(result, "evidence_coverage")
    )


def test_parenthetical_exception_cannot_leak_to_later_or_branch():
    source_input, draft, spans = _fixture()
    text = "首次给药前5年内患有恶性肿瘤（皮肤原位癌除外）或淋巴组织增生性疾病"
    component = draft.proposed_rules[1].components[0]
    component.expression = _predicate(
        "predicate-lymphoma",
        "淋巴组织增生性疾病",
        True,
        "unitless",
        source_clause="淋巴组织增生性疾病",
    )
    component.exception_expression = _predicate(
        "predicate-carcinoma-exception",
        "皮肤原位癌",
        True,
        "unitless",
        source_clause="皮肤原位癌除外",
    )
    draft.component_drafts[1].proposed_component = component
    draft.component_drafts[1].source_excerpts = [text]
    next(
        item
        for item in source_input.source_materials
        if item.source_span_id == "span-ex"
    ).text = text

    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert any(
        issue.issue_code == "EXCEPTION_SCOPE_CHANGED"
        for issue in _issues(result, "boolean_logic")
    )


def test_later_or_branch_exception_is_not_required_on_earlier_sibling():
    source_input, draft, spans = _fixture()
    text = "有淋巴增生性疾病病史，或患有恶性肿瘤（皮肤原位癌除外）"
    component = draft.proposed_rules[1].components[0]
    component.expression = _predicate(
        "predicate-lymph",
        "淋巴增生性疾病病史",
        True,
        "unitless",
        source_clause="有淋巴增生性疾病病史",
    )
    component.exception_expression = None
    draft.component_drafts[1].proposed_component = component
    draft.component_drafts[1].source_excerpts = [text]
    next(
        item
        for item in source_input.source_materials
        if item.source_span_id == "span-ex"
    ).text = text

    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert not any(
        issue.issue_code == "EXCEPTION_NOT_STRUCTURED"
        for issue in _issues(result, "boolean_logic")
    )


def test_chinese_and_or_cannot_be_mutated_to_all():
    source_input, draft, spans = _fixture()
    text = "筛选前3个月内有酗酒史和/或药物滥用史"
    component = draft.proposed_rules[1].components[0]
    component.expression = LogicalExpression(
        operator=LogicalOperator.ALL,
        children=[
            _predicate("predicate-alcohol", "酗酒史", True, "unitless", source_clause=text),
            _predicate("predicate-drug", "药物滥用史", True, "unitless", source_clause=text),
        ],
    )
    draft.component_drafts[1].proposed_component = component
    draft.component_drafts[1].source_excerpts = [text]
    next(
        item
        for item in source_input.source_materials
        if item.source_span_id == "span-ex"
    ).text = text

    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert any(
        issue.issue_code == "DISJUNCTION_CHANGED_TO_CONJUNCTION"
        for issue in _issues(result, "boolean_logic")
    )


@pytest.mark.parametrize(
    ("mutate", "check_name", "issue_code"),
    [
        (
            lambda draft: setattr(
                draft.proposed_rules[0].components[0], "parent_rule_id", "rule-ex"
            ),
            "tree_integrity",
            "COMPONENT_PARENT_RULE_MISMATCH",
        ),
        (
            lambda draft: draft.evidence_requirement_drafts.pop(0),
            "evidence_coverage",
            "COMPONENT_REQUIREMENT_DRAFT_COVERAGE_MISMATCH",
        ),
        (
            lambda draft: setattr(
                draft.evidence_requirement_drafts[0],
                "draft_component_id",
                "draft-component-ex",
            ),
            "evidence_coverage",
            "COMPONENT_REQUIREMENT_DRAFT_BINDING_MISMATCH",
        ),
        (
            lambda draft: draft.proposed_workflow_stages[0].due_requirement_ids.clear(),
            "workflow_coverage",
            "REQUIREMENT_WITHOUT_DUE_NODE",
        ),
        (
            lambda draft: draft.component_drafts[0].source_excerpts.clear(),
            "source_coverage",
            "COMPONENT_EXCERPT_MISSING",
        ),
    ],
)
def test_structural_contract_mutations_are_blocked(mutate, check_name, issue_code):
    source_input, draft, spans = _fixture()
    mutate(draft)
    result = ProtocolDeconstructionGate().evaluate(
        source_input, draft, source_spans=spans
    )
    assert any(
        issue.issue_code == issue_code
        for issue in _issues(result, check_name)
    )
