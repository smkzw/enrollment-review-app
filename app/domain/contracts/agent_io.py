from __future__ import annotations

from pydantic import Field, model_serializer, model_validator

from .agents import AgentCallContract, CriticRun, GateResult, ModelConfigContract, PromptVersion
from .common import ContractModel, VersionedModel
from .evidence import EvidenceExpectation, EvidenceSpan
from .enums import CatalogKind, MetadataResolutionStatus, ReviewStage, StudyPhase
from .normalization import (
    ClinicalEventCandidate,
    CoverageSummary,
    EvidenceNormalizationCandidate,
    MedicationExposureCandidate,
    ReferencedDocumentCandidate,
    UnresolvedItem,
)
from .review import AssessmentCandidate
from .rules import (
    EvidenceRequirement,
    Rule,
    RuleComponent,
    RuleExpression,
    RepeatTriggerCondition,
    validate_repeat_trigger_conditions,
    TimeQuantity,
    WorkflowStage,
    iter_atomic_predicates,
)
from .protocol_ingestion import FrozenProtocolCatalog
from .protocol_metadata import (
    InterpretationSource,
    ProtocolIdentityDecision,
    StudyPhaseSelection,
)


class ProtocolMetadataDraft(VersionedModel):
    protocol_code_candidate: str = Field(min_length=1)
    title_candidate: str = Field(min_length=1)
    version_candidate: str = Field(min_length=1)
    date_candidate: str = Field(min_length=1)
    study_phase_candidates: list[str] = Field(min_length=1)
    source_refs: list[str] = Field(min_length=1)


class RuleComponentDraft(VersionedModel):
    draft_component_id: str = Field(min_length=1)
    parent_official_code: str = Field(min_length=1)
    proposed_component: RuleComponent
    source_refs: list[str] = Field(min_length=1)
    source_excerpts: list[str] = Field(default_factory=list)


class EvidenceRequirementDraft(VersionedModel):
    draft_requirement_id: str = Field(min_length=1)
    draft_component_id: str | None = Field(default=None, min_length=1)
    procedure_catalog_item_id: str | None = Field(default=None, min_length=1)
    proposed_requirement: EvidenceRequirement
    source_refs: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_requirement_origin(self) -> "EvidenceRequirementDraft":
        if (self.draft_component_id is None) == (
            self.procedure_catalog_item_id is None
        ):
            raise ValueError("资料要求草稿必须且只能绑定子规则或流程必做项目之一")
        if (
            self.procedure_catalog_item_id is not None
            and self.proposed_requirement.procedure_catalog_item_id
            != self.procedure_catalog_item_id
        ):
            raise ValueError("流程资料要求草稿与必做项目目录项不一致")
        return self


class ParentRuleCatalogMapping(VersionedModel):
    """One frozen official parent rule mapped to exactly one proposed Rule."""

    catalog_item_id: str = Field(min_length=1)
    proposed_rule_id: str = Field(min_length=1)
    source_span_ids: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_sources(self) -> "ParentRuleCatalogMapping":
        if len(self.source_span_ids) != len(set(self.source_span_ids)):
            raise ValueError("官方父规则映射的来源片段不得重复")
        return self


class ProcedureCatalogMapping(VersionedModel):
    """One frozen visit-operation instance mapped into the draft workflow."""

    catalog_item_id: str = Field(min_length=1)
    proposed_requirement_ids: list[str] = Field(min_length=1)
    proposed_workflow_stage_id: str = Field(min_length=1)
    source_span_ids: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_sources(self) -> "ProcedureCatalogMapping":
        if len(self.source_span_ids) != len(set(self.source_span_ids)):
            raise ValueError("必做项目映射的来源片段不得重复")
        return self


class ProtocolSourceMaterial(VersionedModel):
    """One selected-phase source block supplied to the semantic Agent."""

    source_span_id: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    block_order: int = Field(ge=0)
    text: str = Field(min_length=1)
    projection_text: str | None = None


class SemanticEvidenceRequirement(ContractModel):
    fact_type: str = Field(min_length=1)
    required_source_types: list[str] = Field(default_factory=list)
    allows_screening_record_transcription: bool = True
    requires_contemporaneous_objective_source: bool = False
    due_stage: ReviewStage
    source_validity_window: TimeQuantity | None = None
    description: str = Field(min_length=1)
    predicate_ids: list[str] = Field(default_factory=list)

    @model_serializer(mode="wrap")
    def serialize_semantic_requirement(self, handler):
        data = handler(self)
        if not self.predicate_ids:
            data.pop("predicate_ids", None)
        return data

    @model_validator(mode="after")
    def validate_predicate_ids(self) -> "SemanticEvidenceRequirement":
        if self.predicate_ids:
            if not {"allows_screening_record_transcription",
                    "requires_contemporaneous_objective_source"}.issubset(self.model_fields_set):
                raise ValueError(
                    "明确关联条件时须显式填写 allows_screening_record_transcription 与 "
                    "requires_contemporaneous_objective_source；required_source_types "
                    "不能替代这两个字段，不能沿用默认值"
                )
            if any(not item.strip() for item in self.predicate_ids):
                raise ValueError("语义资料要求的谓词引用不得为空字符串")
            if len(self.predicate_ids) != len(set(self.predicate_ids)):
                raise ValueError("语义资料要求的谓词引用不得重复")
        return self


class SemanticRuleComponent(ContractModel):
    title: str = Field(min_length=1)
    expression: RuleExpression
    exception_expression: RuleExpression | None = None
    repeat_trigger_conditions: list[RepeatTriggerCondition] = Field(default_factory=list)
    evidence_requirements: list[SemanticEvidenceRequirement] = Field(min_length=1)
    source_span_ids: list[str] = Field(min_length=1)
    source_excerpts: list[str] = Field(min_length=1)

    @model_serializer(mode="wrap")
    def preserve_old_repeat_conditions(self, handler):
        value = handler(self)
        if not self.repeat_trigger_conditions:
            value.pop("repeat_trigger_conditions", None)
        return value

    @model_validator(mode="after")
    def validate_requirement_predicate_membership(self) -> "SemanticRuleComponent":
        validate_repeat_trigger_conditions(self.expression, self.exception_expression, self.repeat_trigger_conditions)
        predicate_ids = [
            predicate.predicate_id
            for expression in (self.expression, self.exception_expression,
                               *(item.expression for item in self.repeat_trigger_conditions))
            if expression is not None
            for predicate in iter_atomic_predicates(expression)
        ]
        component_predicate_ids = set(predicate_ids)
        if (any(item.predicate_ids for item in self.evidence_requirements)
                and len(predicate_ids) != len(component_predicate_ids)):
            raise ValueError("资料要求所引用的条件编号必须在本组件内唯一")
        for requirement in self.evidence_requirements:
            if not requirement.predicate_ids:
                continue
            unknown = [
                predicate_id
                for predicate_id in requirement.predicate_ids
                if predicate_id not in component_predicate_ids
            ]
            if unknown:
                raise ValueError("语义资料要求引用了本组件不存在的谓词")
        return self


class SemanticRule(ContractModel):
    official_code: str = Field(pattern=r"^(IN|EX)-\d{2}$")
    components: list[SemanticRuleComponent] = Field(min_length=1)


class ProtocolDeconstructionInput(VersionedModel):
    project_id: str = Field(min_length=1)
    protocol_version_id: str = Field(min_length=1)
    protocol_file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    extraction_snapshot_id: str = Field(min_length=1)
    phase_projection_id: str = Field(min_length=1)
    selected_phase: StudyPhase
    identity_decision: ProtocolIdentityDecision
    phase_selection: StudyPhaseSelection
    allowed_source_span_ids: list[str] = Field(min_length=1)
    source_materials: list[ProtocolSourceMaterial] = Field(min_length=1)
    parent_rule_catalog: FrozenProtocolCatalog
    required_procedure_catalog: FrozenProtocolCatalog
    interpretation_source_ids: list[str] = Field(default_factory=list)
    interpretation_sources: list[InterpretationSource] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_interpretation_scope(self) -> "ProtocolDeconstructionInput":
        """解释来源必须携带经校验的完整对象，不能只传裸 ID。"""

        source_ids = [item.interpretation_source_id for item in self.interpretation_sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("解释来源不得重复")
        if self.interpretation_source_ids:
            if set(self.interpretation_source_ids) != set(source_ids):
                raise ValueError("解释来源 ID 集合必须与解释来源对象集合完全一致")
        elif self.interpretation_sources:
            raise ValueError(
                "解释来源必须同时提供与对象集合一致的 ID 集合，不能只携带对象"
            )
        for source in self.interpretation_sources:
            if source.protocol_version_id != self.protocol_version_id:
                raise ValueError("解释来源必须绑定本次解构的方案版本")
        return self

    @model_validator(mode="after")
    def validate_frozen_scope(self) -> "ProtocolDeconstructionInput":
        if self.selected_phase == StudyPhase.OTHER:
            raise ValueError("方案解构必须使用已确认的明确研究期别")
        if (
            self.identity_decision.status != MetadataResolutionStatus.CONFIRMED
            or self.identity_decision.snapshot_id != self.extraction_snapshot_id
            or self.identity_decision.study_phase != self.selected_phase
        ):
            raise ValueError("方案解构输入必须绑定本次快照已确认的方案身份和期别")
        if (
            self.phase_selection.status != MetadataResolutionStatus.CONFIRMED
            or self.phase_selection.snapshot_id != self.extraction_snapshot_id
            or self.phase_selection.selected_phase != self.selected_phase
        ):
            raise ValueError("方案解构输入必须绑定已确认的单一期别选择")
        catalogs = (self.parent_rule_catalog, self.required_procedure_catalog)
        expected_kinds = (
            CatalogKind.OFFICIAL_PARENT_RULES,
            CatalogKind.REQUIRED_PROCEDURES,
        )
        allowed = set(self.allowed_source_span_ids)
        if len(allowed) != len(self.allowed_source_span_ids):
            raise ValueError("允许的方案来源片段不得重复")
        material_ids = [item.source_span_id for item in self.source_materials]
        if len(material_ids) != len(set(material_ids)):
            raise ValueError("发送给方案解构的原文材料不得重复")
        if set(material_ids) != allowed:
            raise ValueError("允许引用的来源片段必须与实际发送的单期原文材料完全一致")
        for catalog, expected_kind in zip(catalogs, expected_kinds, strict=True):
            if catalog.catalog_kind != expected_kind:
                raise ValueError("方案解构输入的冻结目录类型不匹配")
            if catalog.study_phase != self.selected_phase:
                raise ValueError("冻结目录期别必须与本次解构期别一致")
            if catalog.snapshot_id != self.extraction_snapshot_id:
                raise ValueError("冻结目录必须来自本次提取快照")
            catalog_spans = {
                span_id for item in catalog.items for span_id in item.source_span_ids
            }
            if not catalog_spans <= allowed:
                raise ValueError("冻结目录引用了本次单期投影之外的来源片段")
        return self


class ProtocolDeconstructionDraft(VersionedModel):
    draft_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    protocol_version_id: str = Field(min_length=1)
    selected_phase: StudyPhase
    draft_revision: int = Field(ge=1)
    previous_draft_id: str | None = None
    proposed_rules: list[Rule]
    proposed_workflow_stages: list[WorkflowStage]
    protocol_metadata: ProtocolMetadataDraft
    component_drafts: list[RuleComponentDraft]
    evidence_requirement_drafts: list[EvidenceRequirementDraft]
    parent_catalog_mappings: list[ParentRuleCatalogMapping]
    procedure_catalog_mappings: list[ProcedureCatalogMapping]
    coverage: CoverageSummary
    structural_warnings: list[UnresolvedItem] = Field(default_factory=list)
    unresolved_items: list[UnresolvedItem] = Field(default_factory=list)
    source_refs: list[str] = Field(min_length=1)
    created_by_agent_call_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_mapping_identity(self) -> "ProtocolDeconstructionDraft":
        if self.selected_phase == StudyPhase.OTHER:
            raise ValueError("方案解构草稿必须绑定明确研究期别")
        if self.draft_revision == 1 and self.previous_draft_id is not None:
            raise ValueError("首稿不能引用前序草稿")
        if self.draft_revision > 1 and not self.previous_draft_id:
            raise ValueError("修订稿必须引用前序草稿")
        for name, values in (
            (
                "父规则目录映射",
                [item.catalog_item_id for item in self.parent_catalog_mappings],
            ),
            (
                "必做项目录映射",
                [item.catalog_item_id for item in self.procedure_catalog_mappings],
            ),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"{name}不得重复")
        return self


class ProtocolSemanticDeconstructionCandidate(VersionedModel):
    """Lean Agent output containing only non-deterministic rule semantics."""

    candidate_id: str = Field(min_length=1)
    proposed_rules: list[SemanticRule] = Field(min_length=1)
    structural_warnings: list[UnresolvedItem] = Field(default_factory=list)
    unresolved_items: list[UnresolvedItem] = Field(default_factory=list)
    created_by_agent_call_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_component_source_coverage(self) -> "ProtocolSemanticDeconstructionCandidate":
        codes = [rule.official_code for rule in self.proposed_rules]
        if len(codes) != len(set(codes)):
            raise ValueError("语义草稿中的官方父规则编号不得重复")
        return self


class ProtocolSemanticRuleRepair(VersionedModel):
    """Same-session replacement for only the parent rules named by the gate."""

    candidate_id: str = Field(min_length=1)
    replacement_rules: list[SemanticRule] = Field(min_length=1)
    replacement_structural_warnings: list[UnresolvedItem] = Field(default_factory=list)
    replacement_unresolved_items: list[UnresolvedItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_codes(self) -> "ProtocolSemanticRuleRepair":
        codes = [rule.official_code for rule in self.replacement_rules]
        if len(codes) != len(set(codes)):
            raise ValueError("局部修正中的官方父规则编号不得重复")
        return self


class EvidenceNormalizationInput(VersionedModel):
    project_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    review_episode_id: str = Field(min_length=1)
    evidence_snapshot_id: str = Field(min_length=1)
    source_document_version_ids: list[str] = Field(min_length=1)
    source_page_refs: list[str] = Field(min_length=1)


class EligibilityAssessmentInput(VersionedModel):
    project_id: str = Field(min_length=1)
    protocol_version_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    rule_set_id: str = Field(min_length=1)
    rule_set_revision: int = Field(ge=1)
    review_episode_id: str = Field(min_length=1)
    review_run_id: str = Field(min_length=1)
    evidence_snapshot_id: str = Field(min_length=1)
    rule_component_ids: list[str] = Field(min_length=1)
    fact_ids: list[str] = Field(default_factory=list)
    expectation_ids: list[str] = Field(default_factory=list)


class EligibilityAssessmentOutput(VersionedModel):
    project_id: str = Field(min_length=1)
    protocol_version_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    rule_set_id: str = Field(min_length=1)
    rule_set_revision: int = Field(ge=1)
    review_episode_id: str = Field(min_length=1)
    review_run_id: str = Field(min_length=1)
    evidence_snapshot_id: str = Field(min_length=1)
    candidates: list[AssessmentCandidate]
    coverage: CoverageSummary
    unresolved_items: list[UnresolvedItem] = Field(default_factory=list)
    created_by_agent_call_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_candidate_scope(self) -> "EligibilityAssessmentOutput":
        expected = (
            self.project_id,
            self.protocol_version_id,
            self.subject_id,
            self.rule_set_id,
            self.rule_set_revision,
            self.review_episode_id,
            self.review_run_id,
            self.evidence_snapshot_id,
            self.created_by_agent_call_id,
        )
        for candidate in self.candidates:
            actual = (
                candidate.project_id,
                candidate.protocol_version_id,
                candidate.subject_id,
                candidate.rule_set_id,
                candidate.rule_set_revision,
                candidate.review_episode_id,
                candidate.review_run_id,
                candidate.evidence_snapshot_id,
                candidate.agent_call_id,
            )
            if actual != expected:
                raise ValueError("EligibilityAssessmentOutput 与候选 scope/call 不一致")
        return self


class SafetyProvenanceCriticInput(VersionedModel):
    assessment_candidate_ids: list[str] = Field(min_length=1)
    fact_ids: list[str] = Field(default_factory=list)
    evidence_span_ids: list[str] = Field(default_factory=list)
    expectation_ids: list[str] = Field(default_factory=list)
    trigger_codes: list[str] = Field(min_length=1)
    input_scope_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class SafetyProvenanceCriticOutput(VersionedModel):
    project_id: str = Field(min_length=1)
    protocol_version_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    rule_set_id: str = Field(min_length=1)
    rule_set_revision: int = Field(ge=1)
    review_episode_id: str = Field(min_length=1)
    review_run_id: str = Field(min_length=1)
    evidence_snapshot_id: str = Field(min_length=1)
    created_by_agent_call_id: str = Field(min_length=1)
    critic_runs: list[CriticRun]

    @model_validator(mode="after")
    def validate_critic_call_binding(self) -> "SafetyProvenanceCriticOutput":
        if any(
            item.created_by_agent_call_id != self.created_by_agent_call_id
            for item in self.critic_runs
        ):
            raise ValueError("SafetyProvenanceCriticOutput 与 CriticRun call 不一致")
        return self


class AgentContractsV1(VersionedModel):
    prompt_version: PromptVersion
    model_configuration: ModelConfigContract
    agent_call: AgentCallContract
    gate_result: GateResult
    protocol_deconstruction_input: ProtocolDeconstructionInput
    protocol_deconstruction_output: ProtocolDeconstructionDraft
    evidence_normalization_input: EvidenceNormalizationInput
    evidence_normalization_output: EvidenceNormalizationCandidate
    eligibility_assessment_input: EligibilityAssessmentInput
    eligibility_assessment_output: EligibilityAssessmentOutput
    safety_provenance_critic_input: SafetyProvenanceCriticInput
    safety_provenance_critic_output: SafetyProvenanceCriticOutput
