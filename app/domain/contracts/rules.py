from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import AliasChoices, ConfigDict, Field, StrictInt, model_validator

from .common import ContractModel, RevisionedModel, ScalarValue, VersionedModel
from .enums import (
    AnchorType,
    Comparator,
    LogicalOperator,
    ProtocolPeriod,
    ReviewStage,
    RuleKind,
    StableEnum,
    StudyPhase,
    TimeDirection,
)


class TimeUnit(StableEnum):
    """时间窗使用的临床日历单位。

    月和年不是固定天数的别名；评估器会按日历边界处理它们。
    """

    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"


class TimeQuantity(ContractModel):
    """带单位的正整数时间数量，例如 ``3 个月``或 ``4 周``。"""

    value: StrictInt = Field(gt=0)
    unit: TimeUnit


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
                            "lower_bound": {"type": "null"},
                            "upper_bound": {"type": "null"},
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
    lower_bound: TimeQuantity | None = Field(
        default=None,
        validation_alias=AliasChoices("lower_bound", "lower_bound_quantity"),
    )
    upper_bound: TimeQuantity | None = Field(
        default=None,
        validation_alias=AliasChoices("upper_bound", "upper_bound_quantity"),
    )
    half_life_multiplier: float | None = Field(default=None, gt=0)
    allow_partial_date: bool = False

    @model_validator(mode="after")
    def validate_window(self) -> "TimeConstraint":
        if self.lower_bound_days is not None and self.lower_bound is not None:
            raise ValueError("时间窗下界不能同时使用 lower_bound_days 和带单位数量")
        if self.upper_bound_days is not None and self.upper_bound is not None:
            raise ValueError("时间窗上界不能同时使用 upper_bound_days 和带单位数量")
        if (
            self.lower_bound_days is not None
            and self.upper_bound_days is not None
            and self.lower_bound_days > self.upper_bound_days
        ):
            raise ValueError("时间窗下界不能大于上界")
        if (
            self.lower_bound is not None
            and self.upper_bound is not None
            and self.lower_bound.unit == self.upper_bound.unit
            and self.lower_bound.value > self.upper_bound.value
        ):
            raise ValueError("时间窗下界不能大于上界")
        if self.direction == TimeDirection.ON and any(
            value is not None
            for value in (
                self.lower_bound_days,
                self.upper_bound_days,
                self.lower_bound,
                self.upper_bound,
                self.half_life_multiplier,
            )
        ):
            raise ValueError("on 仅表示与锚点同一日，不能携带时间窗或半衰期参数")
        return self

    @property
    def lower_bound_quantity(self) -> TimeQuantity | None:
        """兼容调用方对新带单位下界的显式命名。"""

        return self.lower_bound

    @property
    def upper_bound_quantity(self) -> TimeQuantity | None:
        """兼容调用方对新带单位上界的显式命名。"""

        return self.upper_bound


class OccurrenceWindow(ContractModel):
    """Rolling duration used by frequency definitions."""

    duration: TimeQuantity
    minimum_count: int | None = Field(default=None, gt=0)


class ProspectiveWindow(ContractModel):
    """Future horizon anchored to a named protocol milestone."""

    anchor_type: AnchorType
    upper_bound: TimeQuantity

    @model_validator(mode="after")
    def validate_future_anchor(self) -> "ProspectiveWindow":
        if self.anchor_type not in {
            AnchorType.STUDY_DRUG_ADMINISTRATION_DATE,
            AnchorType.LAST_DOSE_DATE,
            AnchorType.STUDY_COMPLETION_DATE,
        }:
            raise ValueError("未来计划窗只允许研究药物给药日、末次给药日或研究完成日")
        return self


class ProspectivePeriod(ContractModel):
    """Named protocol interval used by a future plan or intended action."""

    period: ProtocolPeriod


class AtomicPredicate(ContractModel):
    predicate_id: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    attribute: str = Field(min_length=1)
    source_term: str | None = Field(default=None, min_length=1)
    source_clause: str | None = Field(default=None, min_length=1)
    source_clauses: list[str] = Field(default_factory=list)
    comparator: Comparator
    value: ScalarValue | list[ScalarValue] | None = None
    unit: str | None = None
    applicable_population: str | None = None
    requires_professional_judgment: bool = False
    occurrence_window: OccurrenceWindow | None = None
    prospective_window: ProspectiveWindow | None = None
    prospective_period: ProspectivePeriod | None = None
    unit_match_policy: Literal["exact_canonical_label"] = "exact_canonical_label"

    @model_validator(mode="after")
    def validate_comparator_value(self) -> "AtomicPredicate":
        if self.source_clause and self.source_clauses:
            raise ValueError("原子条件不能同时使用单段和多段原文定位")
        if len(self.source_clauses) != len(set(self.source_clauses)):
            raise ValueError("原子条件的多段原文定位不得重复")
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
        if self.occurrence_window is not None:
            direct_count = has_numeric_value and self.unit == "次"
            occurrence_day_count = has_numeric_value and self.unit in {
                "天",
                "日",
                "day",
                "days",
            }
            nested_definition = self.occurrence_window.minimum_count is not None
            if not direct_count and not occurrence_day_count and not nested_definition:
                raise ValueError(
                    "频率窗口必须与带‘次’或发生天数单位的数值谓词配套，或声明括号定义的最小次数"
                )
        return self

    @property
    def exact_source_clauses(self) -> list[str]:
        """Return exact fragments without pretending they are contiguous prose."""

        if self.source_clauses:
            return list(self.source_clauses)
        return [self.source_clause] if self.source_clause else []


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
    rule_component_id: str | None = Field(default=None, min_length=1)
    procedure_catalog_item_id: str | None = Field(default=None, min_length=1)
    fact_type: str = Field(min_length=1)
    required_source_types: list[str] = Field(default_factory=list)
    allows_screening_record_transcription: bool = True
    requires_contemporaneous_objective_source: bool = False
    due_stage: ReviewStage
    source_validity_window: TimeQuantity | None = None
    description: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_requirement_origin(self) -> "EvidenceRequirement":
        if (self.rule_component_id is None) == (
            self.procedure_catalog_item_id is None
        ):
            raise ValueError("资料要求必须且只能绑定子规则或流程必做项目之一")
        return self


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
    # 访视实例身份（Phase 3 切片 4）：节点身份 = 选定期别 + visit_instance + stage。
    # 同一操作在筛选与基线分别执行时保留两个实例；同一 ReviewStage 下多个访视
    # 各自有独立 visit_instance，不能合并或由最后一个节点覆盖。
    visit_instance: str | None = None
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
    # Phase 3 slice 4: procedure-catalog-origin requirements are first-class
    # members of the published authority chain. They are not rule components,
    # so they are listed separately and still must be due exactly once.
    procedure_evidence_requirements: list[EvidenceRequirement] = Field(
        default_factory=list
    )
    procedure_requirement_source_anchor_refs: dict[str, list[str]] = Field(
        default_factory=dict
    )
    # Phase 3 slice 4 repair: 每条资料要求（子规则来源与流程必做来源）都必须
    # 逐条保存方案来源锚点，不能只覆盖父规则和流程要求。Gate 与发布侧校验
    # 锚点属于对应组件来源/允许范围，保证每条要求可回溯到方案原文。
    requirement_source_anchor_refs: dict[str, list[str]] = Field(
        default_factory=dict
    )
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
        workflow_stage_ids = [
            workflow.workflow_stage_id for workflow in self.official_workflow_stages
        ]
        if len(workflow_stage_ids) != len(set(workflow_stage_ids)):
            raise ValueError("ProtocolAuthorityRecord 的流程节点 ID 不得重复")
        # 节点身份 = 期别 + visit_instance + stage：同一审核阶段下多个访视
        # 实例各自有独立 (stage, visit_instance)，不能合并。
        stage_visit_keys = [
            (workflow.stage.value, workflow.visit_instance)
            for workflow in self.official_workflow_stages
        ]
        if len(stage_visit_keys) != len(set(stage_visit_keys)):
            raise ValueError(
                "ProtocolAuthorityRecord 不得包含重复的 (审核阶段, 访视实例) 节点身份"
            )
        procedure_requirement_ids = [
            item.requirement_id for item in self.procedure_evidence_requirements
        ]
        if len(procedure_requirement_ids) != len(set(procedure_requirement_ids)):
            raise ValueError("流程资料要求 ID 不得重复")
        for item in self.procedure_evidence_requirements:
            if item.rule_component_id is not None:
                raise ValueError("流程资料要求不能绑定规则组件")
            if not item.procedure_catalog_item_id:
                raise ValueError("流程资料要求必须绑定必做项目录项")
        if set(self.procedure_requirement_source_anchor_refs) != set(
            procedure_requirement_ids
        ):
            raise ValueError(
                "每条流程资料要求必须提供且只能提供自己的来源定位"
            )
        if any(
            not self.procedure_requirement_source_anchor_refs[requirement_id]
            for requirement_id in procedure_requirement_ids
        ):
            raise ValueError("流程资料要求来源定位不能为空")
        if any(
            not source_ref.startswith(expected_prefix)
            for refs in self.procedure_requirement_source_anchor_refs.values()
            for source_ref in refs
        ):
            raise ValueError("流程资料要求来源定位必须绑定当前 protocol_version_id")
        requirements = {
            requirement.requirement_id: requirement
            for rule in self.official_rules
            for component in rule.components
            for requirement in component.evidence_requirements
        }
        requirements.update(
            {
                requirement.requirement_id: requirement
                for requirement in self.procedure_evidence_requirements
            }
        )
        # 每条资料要求（含子规则来源）逐条保存来源锚点，闭包必须与要求全集一致。
        if set(self.requirement_source_anchor_refs) != set(requirements):
            raise ValueError(
                "每条资料要求必须且只能提供自己的来源定位（含子规则资料要求）"
            )
        if any(
            not self.requirement_source_anchor_refs[requirement_id]
            for requirement_id in requirements
        ):
            raise ValueError("资料要求来源定位不能为空")
        if any(
            not source_ref.startswith(expected_prefix)
            for refs in self.requirement_source_anchor_refs.values()
            for source_ref in refs
        ):
            raise ValueError("资料要求来源定位必须绑定当前 protocol_version_id")
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
