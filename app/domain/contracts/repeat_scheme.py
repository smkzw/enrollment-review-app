"""Source-declared repeat policy, independent of models and observation dates."""
from decimal import Decimal
from typing import Literal

from pydantic import Field, StrictInt, model_serializer, model_validator

from .common import ContractModel
from .enums import AnchorType


class RepeatEvidenceRole(ContractModel):
    role: Literal["initial_observation", "preceding_observation", "target_observation", "external_context", "unresolved"]
    source_excerpts: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_role_source(self):
        if any(not text.strip() for text in self.source_excerpts):
            raise ValueError("复查取证范围的原文不得为空白")
        if self.role != "unresolved" and not self.source_excerpts:
            raise ValueError("明确复查取证范围须保留方案原文，不能由期限参照推断")
        return self


def validate_repeat_evidence_roles(roles, identifiers, source_excerpts=None):
    if not set(roles) <= set(identifiers):
        raise ValueError("复查取证范围不能引用本条件之外的子条件")
    if source_excerpts is not None and any(
        not any(quote in source for source in source_excerpts)
        for role in roles.values() for quote in role.source_excerpts
    ):
        raise ValueError("复查取证范围须来自本项复查要求的方案原文")


class RepeatEvidenceRoleReference(ContractModel):
    group_index: StrictInt = Field(ge=0)
    atom_index: StrictInt = Field(ge=0)
    evidence_role: RepeatEvidenceRole


def resolve_repeat_evidence_roles(references, groups, *, require_complete=False):
    roles = {}
    for reference in references:
        if (reference.group_index >= len(groups)
                or reference.atom_index >= len(groups[reference.group_index])):
            raise ValueError("复查取证范围引用了不存在的子条件")
        identity = groups[reference.group_index][reference.atom_index]
        if identity in roles:
            raise ValueError("同一复查子条件不能重复指定取证范围")
        roles[identity] = reference.evidence_role
    if require_complete and set(roles) != {identity for group in groups for identity in group}:
        raise ValueError("须逐项说明复查子条件的取证范围，原文未明时标为尚未核实")
    return roles


class RepeatDuration(ContractModel):
    value: Decimal = Field(ge=0, allow_inf_nan=False)
    unit: Literal["minute", "hour", "day", "week", "month", "year"]

    @model_validator(mode="after")
    def require_integral_calendar_duration(self):
        if self.unit in {"month", "year"} and self.value != self.value.to_integral_value():
            raise ValueError("复查的月、年期限须为完整日历数量，不能换成固定天数")
        return self


class RepeatTimeLimit(ContractModel):
    reference: Literal["initial_observation", "preceding_observation", "episode_anchor"]
    episode_anchor: AnchorType | None = None
    direction: Literal["before", "after"]
    lower_bound: RepeatDuration | None = None
    upper_bound: RepeatDuration | None = None
    lower_inclusive: bool = True
    upper_inclusive: bool = True

    @model_validator(mode="after")
    def validate_bounds(self):
        if (self.reference == "episode_anchor") != (self.episode_anchor is not None):
            raise ValueError("仅相对方案节点的复查期限可声明该节点；不得以节点代替初查日期")
        if self.lower_bound is None and self.upper_bound is None:
            raise ValueError("明确复查期限须至少保留一个界限")
        if self.lower_bound is None and not self.lower_inclusive:
            raise ValueError("未声明复查期限下界，不能指定其开闭区间")
        if self.upper_bound is None and not self.upper_inclusive:
            raise ValueError("未声明复查期限上界，不能指定其开闭区间")
        if (self.lower_bound is not None and self.upper_bound is not None
                and self.lower_bound.unit == self.upper_bound.unit
                and (self.lower_bound.value > self.upper_bound.value
                     or (self.lower_bound.value == self.upper_bound.value
                         and not (self.lower_inclusive and self.upper_inclusive)))):
            raise ValueError("复查期限上下界不能构成空区间")
        return self


class RepeatMultiInitialPolicy(ContractModel):
    mode: Literal["per_initial_then_all", "per_initial_then_any", "unresolved"]
    source_excerpts: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def require_source(self):
        if any(not text.strip() for text in self.source_excerpts):
            raise ValueError("多组初查的结果采用顺序须保留非空方案原文")
        return self


class RepeatScheme(ContractModel):
    version: Literal["repeat-scheme/v1", "repeat-scheme/v2", "repeat-scheme/v3", "repeat-scheme/v4"] = "repeat-scheme/v4"
    scope: str = Field(min_length=1)
    source_span_ids: list[str] = Field(min_length=1)
    source_excerpts: list[str] = Field(min_length=1)
    permission: Literal["required", "optional", "forbidden", "investigator_discretion", "unresolved"]
    trigger: Literal["unconditional", "source_condition", "unresolved"]
    trigger_excerpt: str | None = Field(default=None, min_length=1)
    trigger_condition_id: str | None = Field(default=None, min_length=1)
    permission_condition_id: str | None = Field(default=None, min_length=1)
    count_status: Literal["specified", "not_specified", "unresolved"]
    maximum_repeats: StrictInt | None = Field(default=None, ge=0)
    count_scope: Literal["per_initial_acquisition", "per_current_episode", "unresolved"] | None = None
    time_status: Literal["specified", "not_specified", "unresolved"]
    time_limit: RepeatTimeLimit | None = None
    result_use: Literal[
        "retain_initial", "use_single_repeat", "use_last_repeat", "combine", "not_specified", "unresolved"
    ]
    result_combine: Literal["sum", "mean", "minimum", "maximum", "all", "any", "unresolved"] | None = None
    result_population: Literal["initial_and_repeats", "repeats_only", "unresolved"] | None = None
    no_repeat_result_use: Literal["retain_initial", "retain_initial_when_trigger_false", "no_result", "unresolved"] | None = None
    multi_initial_result: RepeatMultiInitialPolicy | None = None

    @model_serializer(mode="wrap")
    def preserve_old_scheme(self, handler):
        value = handler(self)
        if self.permission_condition_id is None:
            value.pop("permission_condition_id", None)
        if self.no_repeat_result_use is None:
            value.pop("no_repeat_result_use", None)
        if self.version != "repeat-scheme/v4":
            value.pop("multi_initial_result", None)
        if self.version not in {"repeat-scheme/v3", "repeat-scheme/v4"}:
            value.pop("result_population", None)
        if self.version == "repeat-scheme/v1":
            for field in ("trigger_condition_id", "count_scope", "result_combine"):
                value.pop(field, None)
        return value

    @model_validator(mode="after")
    def validate_source_contract(self):
        additions = (self.trigger_condition_id, self.count_scope, self.result_combine)
        if self.version != "repeat-scheme/v4" and self.multi_initial_result is not None:
            raise ValueError("历史复查规则不能补入多组初查的结果采用顺序")
        if self.multi_initial_result is not None and any(
            not any(quote in source for source in self.source_excerpts)
            for quote in self.multi_initial_result.source_excerpts
        ):
            raise ValueError("多组初查的结果采用要求须来自本项方案原文")
        if self.version == "repeat-scheme/v1" and any(value is not None for value in additions):
            raise ValueError("历史复查规则不能补入新条件、计数范围或计算方式冒充原记录")
        if self.version not in {"repeat-scheme/v3", "repeat-scheme/v4"} and self.result_population is not None:
            raise ValueError("历史复查规则不能补入原先未保存的结果计算范围")
        if self.version not in {"repeat-scheme/v3", "repeat-scheme/v4"} and self.no_repeat_result_use is not None:
            raise ValueError("历史复查规则不能补入原先未保存的无复查结果政策")
        if self.no_repeat_result_use == "retain_initial_when_trigger_false" and self.trigger != "source_condition":
            raise ValueError("条件未触发时采用初查须引用方案明确的完整触发条件")
        if self.permission_condition_id is not None:
            if self.version not in {"repeat-scheme/v3", "repeat-scheme/v4"} or not self.permission_condition_id.strip():
                raise ValueError("复查许可条件须使用当前来源合同及明确身份")
            if self.permission == "forbidden" or self.permission_condition_id == self.trigger_condition_id:
                raise ValueError("复查许可须与触发条件分别核实，禁止复查不能夹带采用许可")
        if self.version in {"repeat-scheme/v3", "repeat-scheme/v4"} and (
                (self.result_use == "combine") != (self.result_population is not None)):
            raise ValueError("合并结果须明确是否包含初查；原文不明时保留未核实，不默认参与范围")
        if self.version in {"repeat-scheme/v2", "repeat-scheme/v3", "repeat-scheme/v4"}:
            if (self.trigger == "source_condition") != (self.trigger_condition_id is not None):
                raise ValueError("条件性复查须关联独立的完整触发条件，其他状态不得夹带条件引用")
            if self.trigger_condition_id is not None and not self.trigger_condition_id.strip():
                raise ValueError("复查条件引用不得为空白")
            if (self.count_status == "specified") != (self.count_scope is not None):
                raise ValueError("明确复查次数须同时保留计数范围；范围未明须明确保留未核实")
            if (self.result_use == "combine") != (self.result_combine is not None):
                raise ValueError("合并复查结果须保留原文计算方式，不能默认平均或选取有利结果")
        if (len(self.source_span_ids) != len(self.source_excerpts)
                or len(set(self.source_span_ids)) != len(self.source_span_ids)
                or any(not item.strip() for item in (self.scope, *self.source_span_ids, *self.source_excerpts))):
            raise ValueError("复查要求的范围及逐字来源须非空、逐项对应且来源编号不重复")
        if self.trigger == "source_condition" and self.trigger_excerpt is None:
            raise ValueError("条件性复查须保留触发条件原文，不得改成无条件许可")
        if self.trigger == "unconditional" and self.trigger_excerpt is not None:
            raise ValueError("无条件复查不能夹带尚待核实的触发条件")
        if self.trigger_excerpt is not None and (
            not self.trigger_excerpt.strip()
            or not any(self.trigger_excerpt in source for source in self.source_excerpts)
        ):
            raise ValueError("复查触发条件须逐字属于该复查要求的方案来源")
        if (self.count_status == "specified") != (self.maximum_repeats is not None):
            raise ValueError("复查次数须区分原文明示、未规定与尚未核实，不能默认一次或无限次")
        if (self.time_status == "specified") != (self.time_limit is not None):
            raise ValueError("复查期限须区分原文明示、未规定与尚未核实，不能补造时限")
        if self.permission == "forbidden" and self.maximum_repeats not in {None, 0}:
            raise ValueError("禁止复查与允许的正次数相互矛盾")
        return self

    @property
    def ancillary_condition_ids(self) -> tuple[str, ...]:
        return tuple(value for value in (self.trigger_condition_id, self.permission_condition_id)
                     if value is not None)

    def require_current_extraction(self) -> None:
        if self.version != "repeat-scheme/v4":
            raise ValueError("本次解构须明确复查结果的计算范围，不能沿用旧规格")
        if self.permission == "investigator_discretion" and self.permission_condition_id is None:
            raise ValueError("研究者决定是否复查时，须单列原文支持的许可条件，不能以普通签名代替")
        if self.no_repeat_result_use is None:
            raise ValueError("须说明没有复查记录时原文允许采用什么结果；原文不明用unresolved，不默认退回初查")


def validate_repeat_source(scheme, source_span_ids, source_excerpts):
    if scheme is None:
        return
    sources = dict(zip(source_span_ids, source_excerpts, strict=True))
    if any(span not in sources or excerpt not in sources[span]
           for span, excerpt in zip(scheme.source_span_ids, scheme.source_excerpts, strict=True)):
        raise ValueError("复查要求不得借用其他条件或其他方案的来源")
