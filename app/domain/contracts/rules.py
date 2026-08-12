from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import Field, model_validator

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
        return self


class AtomicPredicate(ContractModel):
    subject: str = Field(min_length=1)
    attribute: str = Field(min_length=1)
    comparator: Comparator
    value: ScalarValue | list[ScalarValue] | None = None
    unit: str | None = None
    applicable_population: str | None = None
    requires_professional_judgment: bool = False

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
        return self


class WorkflowStage(VersionedModel):
    workflow_stage_id: str = Field(min_length=1)
    stage: ReviewStage
    display_name: str = Field(min_length=1)
    visit_window: str | None = None
    review_required: bool = True
    due_requirement_ids: list[str] = Field(default_factory=list)


LogicalExpression.model_rebuild()
