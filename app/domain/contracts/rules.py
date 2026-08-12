from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import ConfigDict, Field, model_validator

from .common import ContractModel, RevisionedModel, ScalarValue, VersionedModel
from .enums import (
    AnchorType,
    Comparator,
    LogicalOperator,
    ReviewStage,
    RuleKind,
    StudyPhase,
    TimeDirection,
)


class TimeConstraint(ContractModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "allOf": [
                {
                    "if": {
                        "properties": {"direction": {"const": "on"}},
                        "required": ["direction"],
                    },
                    "then": {
                        "properties": {
                            "lower_bound_days": {"type": "null"},
                            "upper_bound_days": {"type": "null"},
                            "half_life_multiplier": {"type": "null"},
                        }
                    },
                }
            ]
        },
    )
    anchor_type: AnchorType
    direction: TimeDirection
    lower_bound_days: int | None = Field(default=None, ge=0)
    upper_bound_days: int | None = Field(default=None, ge=0)
    half_life_multiplier: float | None = Field(default=None, gt=0)
    allow_partial_date: bool = False

    @model_validator(mode="after")
    def validate_window(self) -> "TimeConstraint":
        if (
            self.lower_bound_days is not None
            and self.upper_bound_days is not None
            and self.lower_bound_days > self.upper_bound_days
        ):
            raise ValueError("时间窗下界不能大于上界")
        if self.direction == TimeDirection.ON and any(
            value is not None
            for value in (
                self.lower_bound_days,
                self.upper_bound_days,
                self.half_life_multiplier,
            )
        ):
            raise ValueError("on 仅表示与锚点同一日，不能携带时间窗或半衰期参数")
        return self


class AtomicPredicate(ContractModel):
    predicate_id: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    attribute: str = Field(min_length=1)
    comparator: Comparator
    value: ScalarValue | list[ScalarValue] | None = None
    unit: str | None = None
    applicable_population: str | None = None
    requires_professional_judgment: bool = False
    unit_match_policy: Literal["exact_canonical_label"] = "exact_canonical_label"

    @model_validator(mode="after")
    def validate_comparator_value(self) -> "AtomicPredicate":
        if self.comparator == "exists" and self.value is not None:
            raise ValueError("exists 比较器不接受 value")
        if self.comparator != "exists" and self.value is None:
            raise ValueError("非 exists 比较器必须提供 value")
        if self.comparator in {"in", "not_in"} and not isinstance(self.value, list):
            raise ValueError("in/not_in 比较器必须提供值列表")
        if self.comparator not in {"in", "not_in"} and isinstance(self.value, list):
            raise ValueError("只有 in/not_in 比较器可以使用值列表")
        values = self.value if isinstance(self.value, list) else [self.value]
        has_numeric_value = any(
            isinstance(item, (int, float)) and not isinstance(item, bool)
            for item in values
            if item is not None
        )
        if has_numeric_value and not self.unit:
            raise ValueError("数值谓词必须声明单位；无量纲值显式使用 unitless")
        return self


class AtomicExpression(ContractModel):
    kind: Literal["predicate"] = "predicate"
    predicate: AtomicPredicate
    time_constraint: TimeConstraint | None = None


class LogicalExpression(ContractModel):
    kind: Literal["logical"] = "logical"
    operator: LogicalOperator
    children: list["RuleExpression"]

    @model_validator(mode="after")
    def validate_arity(self) -> "LogicalExpression":
        if self.operator == LogicalOperator.NOT and len(self.children) != 1:
            raise ValueError("NOT 必须且只能包含一个子表达式")
        if self.operator in {LogicalOperator.ALL, LogicalOperator.ANY} and len(self.children) < 2:
            raise ValueError("ALL/ANY 至少包含两个子表达式")
        return self


RuleExpression = Annotated[
    Union[AtomicExpression, LogicalExpression], Field(discriminator="kind")
]


def iter_atomic_predicates(expression: RuleExpression):
    if expression.kind == "predicate":
        yield expression.predicate
        return
    for child in expression.children:
        yield from iter_atomic_predicates(child)


class EvidenceRequirement(VersionedModel):
    requirement_id: str = Field(min_length=1)
    rule_component_id: str = Field(min_length=1)
    fact_type: str = Field(min_length=1)
    required_source_types: list[str] = Field(default_factory=list)
    allows_screening_record_transcription: bool = True
    requires_contemporaneous_objective_source: bool = False
    due_stage: ReviewStage
    description: str = Field(min_length=1)


class RuleComponent(VersionedModel):
    rule_component_id: str = Field(min_length=1)
    parent_rule_id: str = Field(min_length=1)
    display_code: str = Field(min_length=1)
    title: str = Field(min_length=1)
    expression: RuleExpression
    exception_expression: RuleExpression | None = None
    evidence_requirements: list[EvidenceRequirement] = Field(default_factory=list)


class Rule(VersionedModel):
    rule_id: str = Field(min_length=1)
    official_code: str = Field(pattern=r"^(IN|EX|REQ)-\d{2}$")
    kind: RuleKind
    source_text: str = Field(min_length=1)
    study_phase: StudyPhase
    components: list[RuleComponent] = Field(min_length=1)


class RuleSet(RevisionedModel):
    rule_set_id: str = Field(min_length=1)
    protocol_version_id: str = Field(min_length=1)
    study_phase: StudyPhase
    rules: list[Rule] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_rule_tree(self) -> "RuleSet":
        rule_ids: set[str] = set()
        official_codes: set[str] = set()
        component_ids: set[str] = set()
        predicate_ids: set[str] = set()
        for rule in self.rules:
            if rule.rule_id in rule_ids or rule.official_code in official_codes:
                raise ValueError("RuleSet 中的规则 ID 和官方编号必须唯一")
            rule_ids.add(rule.rule_id)
            official_codes.add(rule.official_code)
            if rule.study_phase != self.study_phase:
                raise ValueError("规则期别必须与 RuleSet 期别一致")
            expected_prefix = {
                RuleKind.INCLUSION: "IN-",
                RuleKind.EXCLUSION: "EX-",
                RuleKind.REQUIRED_PROCEDURE: "REQ-",
            }[rule.kind]
            if not rule.official_code.startswith(expected_prefix):
                raise ValueError("官方编号前缀必须与规则类型一致")
            for component in rule.components:
                if component.rule_component_id in component_ids:
                    raise ValueError("RuleSet 中的组件 ID 必须唯一")
                component_ids.add(component.rule_component_id)
                if component.parent_rule_id != rule.rule_id:
                    raise ValueError("组件 parent_rule_id 必须指向所在父规则")
                if any(
                    requirement.rule_component_id != component.rule_component_id
                    for requirement in component.evidence_requirements
                ):
                    raise ValueError("证据要求必须指向所在规则组件")
                expressions = [component.expression]
                if component.exception_expression is not None:
                    expressions.append(component.exception_expression)
                for expression in expressions:
                    for predicate in iter_atomic_predicates(expression):
                        if predicate.predicate_id in predicate_ids:
                            raise ValueError("RuleSet 中的原子谓词 ID 必须唯一")
                        predicate_ids.add(predicate.predicate_id)
        return self


class WorkflowStage(VersionedModel):
    workflow_stage_id: str = Field(min_length=1)
    stage: ReviewStage
    display_name: str = Field(min_length=1)
    visit_window: str | None = None
    review_required: bool = True
    due_requirement_ids: list[str] = Field(default_factory=list)


class ProtocolAuthorityRecord(VersionedModel):
    authority_record_id: str = Field(min_length=1)
    protocol_version_id: str = Field(min_length=1)
    protocol_document_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    study_phase: StudyPhase
    official_rules: list[Rule] = Field(min_length=1)
    official_workflow_stages: list[WorkflowStage] = Field(min_length=1)
    rule_source_anchor_refs: dict[str, list[str]]
    verified_by: str = Field(min_length=1)
    verified_at: datetime
    verification_method: Literal["human_verified_official_protocol"]
    authority_record_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_authority_record(self) -> "ProtocolAuthorityRecord":
        from app.domain.publication import canonical_hash

        expected = canonical_hash(
            self.model_dump(mode="json", exclude={"authority_record_sha256"})
        )
        if self.authority_record_sha256 != expected:
            raise ValueError("ProtocolAuthorityRecord 哈希与正式方案权威结构不一致")
        codes = [item.official_code for item in self.official_rules]
        if set(self.rule_source_anchor_refs) != set(codes):
            raise ValueError("每条官方规则必须提供且只能提供自己的来源定位")
        if any(not self.rule_source_anchor_refs[code] for code in codes):
            raise ValueError("官方规则来源定位不能为空")
        expected_prefix = f"{self.protocol_version_id}:"
        if any(
            not source_ref.startswith(expected_prefix)
            for refs in self.rule_source_anchor_refs.values()
            for source_ref in refs
        ):
            raise ValueError("官方规则来源定位必须绑定当前 protocol_version_id")
        if any(item.study_phase != self.study_phase for item in self.official_rules):
            raise ValueError("权威规则期别必须与 AuthorityRecord 一致")
        stage_by_value = {
            workflow.stage: workflow for workflow in self.official_workflow_stages
        }
        if len(stage_by_value) != len(self.official_workflow_stages):
            raise ValueError("ProtocolAuthorityRecord 不得包含重复审核阶段")
        requirements = {
            requirement.requirement_id: requirement
            for rule in self.official_rules
            for component in rule.components
            for requirement in component.evidence_requirements
        }
        listed_due_stages: dict[str, ReviewStage] = {}
        for workflow in self.official_workflow_stages:
            for requirement_id in workflow.due_requirement_ids:
                if requirement_id in listed_due_stages:
                    raise ValueError("EvidenceRequirement 不得在多个阶段重复到期")
                if requirement_id not in requirements:
                    raise ValueError("WorkflowStage 引用了不存在的 EvidenceRequirement")
                listed_due_stages[requirement_id] = workflow.stage
        if set(listed_due_stages) != set(requirements):
            raise ValueError("每个 EvidenceRequirement 必须在 WorkflowStage 中且仅到期一次")
        if any(
            listed_due_stages[requirement_id] != requirement.due_stage
            for requirement_id, requirement in requirements.items()
        ):
            raise ValueError("WorkflowStage 到期阶段与 EvidenceRequirement.due_stage 不一致")
        return self


class ProtocolSourceRecord(VersionedModel):
    source_ref: str = Field(min_length=1)
    protocol_version_id: str = Field(min_length=1)
    protocol_document_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    locator: str = Field(min_length=1)
    source_record_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_source_record(self) -> "ProtocolSourceRecord":
        from app.domain.publication import canonical_hash

        if not self.source_ref.startswith(f"{self.protocol_version_id}:"):
            raise ValueError("方案来源定位必须绑定当前方案版本")
        expected = canonical_hash(
            self.model_dump(mode="json", exclude={"source_record_sha256"})
        )
        if self.source_record_sha256 != expected:
            raise ValueError("方案来源记录哈希无效")
        return self


class ServiceCommandEvent(VersionedModel):
    command_id: str = Field(min_length=1)
    action: Literal["accept_protocol_authority"] = "accept_protocol_authority"
    protocol_version_id: str = Field(min_length=1)
    authority_record_id: str = Field(min_length=1)
    authority_record_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    actor_id: str = Field(min_length=1)
    occurred_at: datetime
    recorded_by_service: Literal["enrollment-review-app"] = "enrollment-review-app"
    event_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_event_hash(self) -> "ServiceCommandEvent":
        from app.domain.publication import canonical_hash

        expected = canonical_hash(
            self.model_dump(mode="json", exclude={"event_sha256"})
        )
        if self.event_sha256 != expected:
            raise ValueError("应用服务操作事件哈希无效")
        return self


class ProtocolAuthorityConfirmation(VersionedModel):
    confirmation_id: str = Field(min_length=1)
    command_id: str = Field(min_length=1)
    protocol_version_id: str = Field(min_length=1)
    protocol_document_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    authority_record_id: str = Field(min_length=1)
    authority_record_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirmed_by: str = Field(min_length=1)
    confirmed_at: datetime
    action: Literal["accept_protocol_authority"] = "accept_protocol_authority"
    recorded_by_service: Literal["enrollment-review-app"] = "enrollment-review-app"
    confirmation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_confirmation_hash(self) -> "ProtocolAuthorityConfirmation":
        from app.domain.publication import canonical_hash

        expected = canonical_hash(
            self.model_dump(mode="json", exclude={"confirmation_sha256"})
        )
        if self.confirmation_sha256 != expected:
            raise ValueError("方案权威确认事件哈希无效")
        return self


class ProtocolIntegrityManifest(VersionedModel):
    manifest_id: str = Field(min_length=1)
    protocol_version_id: str = Field(min_length=1)
    protocol_document_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    study_phase: StudyPhase
    source_refs: list[str] = Field(min_length=1)
    authority_record_id: str = Field(min_length=1)
    authority_record_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    authoritative_rule_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    authoritative_workflow_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_manifest_hash(self) -> "ProtocolIntegrityManifest":
        from app.domain.publication import canonical_hash

        expected = canonical_hash(
            self.model_dump(mode="json", exclude={"manifest_sha256"})
        )
        if self.manifest_sha256 != expected:
            raise ValueError("ProtocolIntegrityManifest 与权威结构哈希不一致")
        return self


LogicalExpression.model_rebuild()
