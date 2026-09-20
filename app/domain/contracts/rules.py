from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import AliasChoices, Field, StrictInt, model_serializer, model_validator

from .common import ContractModel, RevisionedModel, ScalarValue, VersionedModel
from .control_evidence_origin import ControlEvidenceOrigin
from .half_life_evidence import HalfLifeEvidence
from .occurrence_scope import OccurrenceScope
from .frequency_source_date import FrequencySourceDate
from .repeat_scheme import RepeatScheme, RepeatEvidenceRole, validate_repeat_evidence_roles
from .observation_selection import ObservationPolicy, validate_observation_window_order
from .enums import (
    AnchorType,
    CombinedWindowSelection,
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
    """相对命名锚点的时间窗。

    固定日历窗与半衰期倍数可同时出现，但必须显式声明
    ``combined_window_selection=longer_of_calendar_and_half_life``；
    不得仅因两类字段并存或原文含“或”而推断择长语义。
    锚点必须使用方案命名的日期类型（如 ``first_dose_date``），由调用方按原文填写。
    """

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
    lower_bound_inclusive: bool = True
    upper_bound_inclusive: bool = True
    half_life_multiplier: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    half_life_evidence: HalfLifeEvidence | None = None
    combined_window_selection: CombinedWindowSelection | None = None
    allow_partial_date: bool = False

    @model_validator(mode="after")
    def validate_window(self) -> "TimeConstraint":
        if self.half_life_evidence is not None and self.half_life_multiplier is None:
            raise ValueError("半衰期依据只用于方案明确要求半衰期倍数的时间窗")
        if self.lower_bound_days is not None and self.lower_bound is not None:
            raise ValueError("时间窗下界不能同时使用 lower_bound_days 和带单位数量")
        if self.upper_bound_days is not None and self.upper_bound is not None:
            raise ValueError("时间窗上界不能同时使用 upper_bound_days 和带单位数量")
        has_lower_bound = self.lower_bound_days is not None or self.lower_bound is not None
        has_upper_bound = self.upper_bound_days is not None or self.upper_bound is not None
        if not has_lower_bound and not self.lower_bound_inclusive:
            raise ValueError("没有时间窗下界时不能声明下界为开区间")
        if not has_upper_bound and not self.upper_bound_inclusive:
            raise ValueError("没有时间窗上界时不能声明上界为开区间")
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
                self.combined_window_selection,
            )
        ):
            raise ValueError("on 仅表示与锚点同一日，不能携带时间窗或半衰期参数")
        if (
            self.anchor_type == AnchorType.REVIEW_NODE_DATE
            and self.direction == TimeDirection.ON
        ):
            raise ValueError(
                "审核节点日期锚点不能用作 on 同日约束；审核阶段本身由资料要求的"
                " due_stage 表达，不得编码成日期约束"
            )
        has_calendar_bound = any(
            value is not None
            for value in (
                self.lower_bound_days,
                self.upper_bound_days,
                self.lower_bound,
                self.upper_bound,
            )
        )
        has_half_life = self.half_life_multiplier is not None
        if has_calendar_bound and has_half_life:
            if (
                self.combined_window_selection
                != CombinedWindowSelection.LONGER_OF_CALENDAR_AND_HALF_LIFE
            ):
                raise ValueError(
                    "固定窗口与半衰期并存时必须显式声明 combined_window_selection="
                    "longer_of_calendar_and_half_life，不得从原文推断"
                )
        elif self.combined_window_selection is not None:
            raise ValueError(
                "combined_window_selection 仅用于固定窗口与半衰期并存的择长语义，"
                "不能单独搭配其中一类窗口"
            )
        return self

    @model_serializer(mode="wrap")
    def preserve_historical_duration(self, handler):
        payload = handler(self)
        if self.half_life_evidence is None:
            payload.pop("half_life_evidence", None)
        return payload

    @property
    def lower_bound_quantity(self) -> TimeQuantity | None:
        """兼容调用方对新带单位下界的显式命名。"""

        return self.lower_bound

    @property
    def upper_bound_quantity(self) -> TimeQuantity | None:
        """兼容调用方对新带单位上界的显式命名。"""

        return self.upper_bound


class FrequencyRelativeHorizon(ContractModel):
    """Finite source-declared calendar range, without unrelated washout fields."""

    anchor_type: AnchorType
    direction: Literal["before", "after"]
    lower_bound: TimeQuantity | None = None
    upper_bound: TimeQuantity
    lower_bound_inclusive: bool | None = None
    upper_bound_inclusive: bool | None = None


class FrequencyHorizon(ContractModel):
    """Source-declared domain of periods, never borrowed from an outer filter."""

    basis: Literal["explicit_dates", "anchor_span", "relative_window", "unbounded", "unresolved"]
    start: FrequencySourceDate | None = None
    end: FrequencySourceDate | None = None
    start_anchor: AnchorType | None = None
    end_anchor: AnchorType | None = None
    relative_window: FrequencyRelativeHorizon | None = None
    start_inclusive: bool | None = None
    end_inclusive: bool | None = None
    source_excerpts: list[str] = Field(min_length=1)
    unresolved_reason: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_horizon(self):
        fields = {"explicit_dates": (self.start, self.end),
                  "anchor_span": (self.start_anchor, self.end_anchor),
                  "relative_window": (self.relative_window,)}
        for basis, values in fields.items():
            if basis == self.basis and any(value is None for value in values):
                raise ValueError("统计范围须保留完整的起止或相对期间")
            if basis != self.basis and any(value is not None for value in values):
                raise ValueError("统计范围不能混用不同日期定义")
        if self.basis in {"unbounded", "unresolved"} and (
                self.start_inclusive is not None or self.end_inclusive is not None):
            raise ValueError("未定义日期范围不能补入起止当天规则")
        if self.basis == "relative_window" and (
                self.start_inclusive is not None or self.end_inclusive is not None):
            raise ValueError("相对期间使用自身开闭界限，不能重复定义")
        if any(not quote.strip() for quote in self.source_excerpts):
            raise ValueError("统计范围须有逐字依据")
        if self.basis == "unresolved":
            if not self.unresolved_reason or not self.unresolved_reason.strip():
                raise ValueError("统计范围不明须保留具体疑问")
        elif self.unresolved_reason is not None:
            raise ValueError("已声明统计范围不能同时标为未决")
        if any(value is not None and not any(value.excerpt in quote for quote in self.source_excerpts)
               for value in (self.start, self.end)):
            raise ValueError("统计日期须属于本范围的逐字依据")
        anchors = (self.start_anchor, self.end_anchor,
                   self.relative_window.anchor_type if self.relative_window is not None else None)
        if any(value in {AnchorType.REVIEW_NODE_DATE, AnchorType.EVENT_DATE} for value in anchors):
            raise ValueError("多期间范围须有明确命名节点，不能借用未指定事件或审核默认日期")
        return self


class OccurrenceWindow(ContractModel):
    """Frequency duration; absent historical scope is not an inferred rolling window."""

    duration: TimeQuantity
    minimum_count: int | None = Field(default=None, gt=0)
    scope: OccurrenceScope | None = None
    horizon: FrequencyHorizon | None = None

    @model_serializer(mode="wrap")
    def preserve_historical_scope(self, handler):
        payload = handler(self)
        if self.scope is None:
            payload.pop("scope", None)
        if self.horizon is None:
            payload.pop("horizon", None)
        return payload

    @model_validator(mode="after")
    def validate_horizon_scope(self):
        if self.horizon is not None and (self.scope is None or self.scope.quantifier == "single"):
            raise ValueError("多期间统计范围不能套入单个计数期间")
        if self.horizon is not None and self.scope.version != "occurrence-scope/v4":
            raise ValueError("旧期间声明不能补入未保存的统计范围")
        if self.scope is not None and self.scope.calendar_week_start is not None and self.duration.unit != TimeUnit.WEEK:
            raise ValueError("日历周起点不能用于非周周期")
        return self


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
    # 显式原文命题（来源含义核实）：条件本身是非确定性的语义判断，只能保留
    # 方案原文的原方向含义及其限定条件，不能伪装成数值、分类或日期比较。
    # 该字段不得由旧字段推断；为空时序列化省略，旧内容身份保持不变。
    semantic_proposition: str | None = Field(
        default=None,
        min_length=1,
        description=(
            "需要按方案来源核实原方向语义的命题；仅与 comparator=exists 且无 "
            "value、unit 的条件同时使用，不与研究者专业判断或发生频次混用。"
        ),
    )
    unit_match_policy: Literal["exact_canonical_label"] = "exact_canonical_label"
    observation_policy: ObservationPolicy | None = None
    repeat_scheme: RepeatScheme | None = None

    @model_serializer(mode="wrap")
    def serialize_optional_fields(self, handler):
        value = handler(self)
        if self.observation_policy is None:
            value.pop("observation_policy", None)
        if self.semantic_proposition is None:
            # 省略空命题：旧条件的规范化字节与其内容身份保持完全一致。
            value.pop("semantic_proposition", None)
        if self.repeat_scheme is None:
            value.pop("repeat_scheme", None)
        return value

    @model_validator(mode="after")
    def validate_comparator_value(self) -> "AtomicPredicate":
        if self.source_clause and self.source_clauses:
            raise ValueError("原子条件不能同时使用单段和多段原文定位")
        if len(self.source_clauses) != len(set(self.source_clauses)):
            raise ValueError("原子条件的多段原文定位不得重复")
        if self.repeat_scheme is not None and any(
            not any(excerpt in clause for clause in self.exact_source_clauses)
            for excerpt in self.repeat_scheme.source_excerpts
        ):
            raise ValueError("复查要求须保留在本条件逐字原文内，跨段依据须列入原文片段")
        if self.observation_policy is not None and any(
            not any(excerpt in clause for clause in self.exact_source_clauses)
            for excerpt in self.observation_policy.source_excerpts
        ):
            raise ValueError("观察选择须保留在本条件逐字原文内，跨段依据须列入原文片段")
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
            scope = self.occurrence_window.scope
            horizon = self.occurrence_window.horizon
            if horizon is not None and any(not any(text in clause for clause in self.exact_source_clauses)
                                           for text in horizon.source_excerpts):
                raise ValueError("多期间统计范围须属于本条件逐字原文")
            if scope is not None:
                if any(not any(text in clause for clause in self.exact_source_clauses)
                       for text in scope.source_excerpts):
                    raise ValueError("频次期间依据须保留在本条件逐字原文内")
                if self.repeat_scheme is not None or self.observation_policy is not None:
                    raise ValueError("频次计数不能与未定义先后关系的复查或观察选择混用")
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

    @model_validator(mode="after")
    def validate_semantic_proposition(self) -> "AtomicPredicate":
        """语义命题只声明来源含义待核实，不能承载或替代确定性计算。"""

        if self.semantic_proposition is None:
            return self
        if not self.semantic_proposition.strip():
            raise ValueError("语义命题必须是非空文字，不能用空白占位")
        if (
            self.comparator != "exists"
            or self.value is not None
            or self.unit is not None
        ):
            raise ValueError(
                "语义命题只能与 comparator=exists 且无 value、unit 的条件同时使用；"
                "数值、分类和日期判断仍须使用各自的确定性比较结构"
            )
        if self.requires_professional_judgment:
            raise ValueError(
                "语义命题不能与研究者专业判断混用；研究者判断仍走其专属判断链"
            )
        if self.occurrence_window is not None:
            raise ValueError(
                "语义命题不接受发生频次窗口；频次仍须用数值谓词或最小次数结构保留"
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

    @model_validator(mode="after")
    def validate_observation_window(self):
        validate_observation_window_order(self.predicate.observation_policy,
                                          has_time_constraint=self.time_constraint is not None)
        return self


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
    control_origin: ControlEvidenceOrigin | None = None
    fact_type: str = Field(min_length=1)
    required_source_types: list[str] = Field(default_factory=list)
    allows_screening_record_transcription: bool | None = True
    requires_contemporaneous_objective_source: bool | None = False
    due_stage: ReviewStage
    source_validity_window: TimeQuantity | None = None
    control_validity_status: Literal["specified", "not_specified", "unknown"] | None = None
    control_validity_constraint: TimeConstraint | None = None
    description: str = Field(min_length=1)
    # Optional explicit attribution to atomic predicates in the same component.
    # Absent/empty keeps legacy unattributed serialization; never infer from fact_type.
    predicate_ids: list[str] = Field(default_factory=list)

    @model_serializer(mode="wrap")
    def serialize_origin(self, handler):
        data = handler(self)
        if self.control_origin is None:
            data.pop("control_origin", None)
        for name in ("control_validity_status", "control_validity_constraint"):
            if getattr(self, name) is None:
                data.pop(name, None)
        if not self.predicate_ids:
            data.pop("predicate_ids", None)
        return data

    @model_validator(mode="after")
    def validate_requirement_origin(self) -> "EvidenceRequirement":
        if sum(value is not None for value in (
            self.rule_component_id, self.procedure_catalog_item_id, self.control_origin,
        )) != 1:
            raise ValueError("资料要求必须且只能绑定子规则、流程必做项目或已发布补充控制之一")
        if self.predicate_ids:
            if not {"allows_screening_record_transcription",
                    "requires_contemporaneous_objective_source"}.issubset(self.model_fields_set):
                raise ValueError("明确关联条件的资料要求须同时明确来源要求，不能沿用默认值")
            if any(not item.strip() for item in self.predicate_ids):
                raise ValueError("资料要求的谓词引用不得为空字符串")
            if len(self.predicate_ids) != len(set(self.predicate_ids)):
                raise ValueError("资料要求的谓词引用不得重复")
            if self.procedure_catalog_item_id is not None or self.control_origin is not None:
                raise ValueError("流程或补充控制资料要求不能声明官方谓词归属")
        if self.control_origin is not None:
            if self.control_validity_status is None or self.source_validity_window is not None:
                raise ValueError("补充资料须明确有效期状态，不能套用旧时间窗")
            if (self.control_validity_status == "specified") != (self.control_validity_constraint is not None):
                raise ValueError("补充资料的明确有效期必须保留完整时间约束")
        elif (
            self.control_validity_status is not None
            or self.control_validity_constraint is not None
            or self.allows_screening_record_transcription is None
            or self.requires_contemporaneous_objective_source is None
        ):
            raise ValueError("补充控制的来源状态不能用于既有规则资料要求")
        return self


class RepeatTriggerCondition(ContractModel):
    """Ancillary expression; never an eligibility trigger or exception."""

    condition_id: str = Field(min_length=1)
    expression: RuleExpression
    predicate_evidence_roles: dict[str, RepeatEvidenceRole] = Field(default_factory=dict)

    @model_serializer(mode="wrap")
    def preserve_legacy_roles(self, handler):
        value = handler(self)
        if not self.predicate_evidence_roles:
            value.pop("predicate_evidence_roles", None)
        return value

    @model_validator(mode="after")
    def validate_nonrecursive_condition(self):
        predicates = list(iter_atomic_predicates(self.expression))
        identifiers = [item.predicate_id for item in predicates]
        validate_repeat_evidence_roles(self.predicate_evidence_roles, identifiers)
        if not self.condition_id.strip() or len(identifiers) != len(set(identifiers)):
            raise ValueError("复查触发条件及其子条件身份须明确且不得重复")
        if any(item.repeat_scheme is not None for item in predicates):
            raise ValueError("复查触发条件不能再嵌套复查要求")
        return self


def validate_repeat_trigger_conditions(expression, exception_expression, repeat_trigger_conditions):
    owners = [predicate for root in (expression, exception_expression)
              if root is not None for predicate in iter_atomic_predicates(root)]
    conditions = {item.condition_id: item for item in repeat_trigger_conditions}
    if len(conditions) != len(repeat_trigger_conditions):
        raise ValueError("同一组件的复查触发条件不得重名")
    referenced = set()
    for owner in owners:
        scheme = owner.repeat_scheme
        if scheme is None:
            continue
        for condition_id in scheme.ancillary_condition_ids:
            referenced.add(condition_id)
            condition = conditions.get(condition_id)
            if condition is None:
                raise ValueError("复查要求引用的触发或许可条件不在本组件内")
            validate_repeat_evidence_roles(
                condition.predicate_evidence_roles,
                [item.predicate_id for item in iter_atomic_predicates(condition.expression)],
                scheme.source_excerpts,
            )
            for predicate in iter_atomic_predicates(condition.expression):
                if not predicate.exact_source_clauses or any(
                    not any(clause in excerpt for excerpt in scheme.source_excerpts)
                    for clause in predicate.exact_source_clauses
                ):
                    raise ValueError("复查条件须逐项来自该复查要求的方案原文")
    if referenced != set(conditions):
        raise ValueError("不得夹带未被本组件复查要求引用的附加条件")
    all_ids = [item.predicate_id for item in owners]
    all_ids.extend(predicate.predicate_id for item in repeat_trigger_conditions
                   for predicate in iter_atomic_predicates(item.expression))
    if conditions and len(all_ids) != len(set(all_ids)):
        raise ValueError("复查触发条件不能与入排条件或其他复查条件使用相同身份")


class RuleComponent(VersionedModel):
    rule_component_id: str = Field(min_length=1)
    parent_rule_id: str = Field(min_length=1)
    display_code: str = Field(min_length=1)
    title: str = Field(min_length=1)
    expression: RuleExpression
    exception_expression: RuleExpression | None = None
    repeat_trigger_conditions: list[RepeatTriggerCondition] = Field(default_factory=list)
    evidence_requirements: list[EvidenceRequirement] = Field(default_factory=list)

    @model_serializer(mode="wrap")
    def preserve_historical_repeat_conditions(self, handler):
        value = handler(self)
        if not self.repeat_trigger_conditions:
            value.pop("repeat_trigger_conditions", None)
        return value

    @model_validator(mode="after")
    def validate_repeat_condition_ownership(self):
        validate_repeat_trigger_conditions(self.expression, self.exception_expression, self.repeat_trigger_conditions)
        return self

    @model_validator(mode="after")
    def validate_evidence_predicate_links(self) -> "RuleComponent":
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
                raise ValueError("资料要求引用了本组件不存在的谓词")
        return self


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
                expressions.extend(item.expression for item in component.repeat_trigger_conditions)
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
