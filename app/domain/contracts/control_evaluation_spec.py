"""Source-backed evaluation instructions, not patient observations or verdicts."""
from typing import Literal

from pydantic import ConfigDict, Field, model_serializer, model_validator

from .common import ContractModel
from .rules import AtomicPredicate
from .repeat_scheme import RepeatScheme, validate_repeat_source
from .observation_selection import ObservationPolicy, validate_observation_window_order

ControlTimePurpose = Literal[
    "not_applicable", "event_membership", "interval_condition", "source_validity", "unresolved"
]


class ControlObservationPolicy(ObservationPolicy):
    """Source-declared aggregation, not proof that observations cover its scope."""

class ControlAtomEvaluationSpec(ContractModel):
    """The predicate expresses the atom itself; obligation kind never inverts it.

    A predicate is retained only for deterministic value comparisons. Its ID is
    local to this specification, not the published control atom identity. The
    owning atom and publication remain the authority for patient bindings.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
    version: Literal["control-atom-evaluation/v1", "control-atom-evaluation/v2", "control-atom-evaluation/v3", "control-atom-evaluation/v4"] = "control-atom-evaluation/v4"
    determination_mode: Literal["deterministic", "semantic", "investigator_judgment"]
    proposition: str = Field(min_length=1)
    operation: Literal["value_comparison", "time_constraint"] | None = None
    predicate: AtomicPredicate | None = None
    operand_attribute: Literal["value", "date_range", "record_time", "assertion_basis"] | None = None
    time_operand_attribute: Literal["date_range", "record_time"] | None = None
    time_purpose: ControlTimePurpose
    observation_policy: ControlObservationPolicy | None = None
    repeat_scheme: RepeatScheme | None = None
    source_span_ids: list[str] = Field(min_length=1)
    source_excerpts: list[str] = Field(min_length=1)

    @model_serializer(mode="wrap")
    def serialize_optional_policy(self, handler):
        value = handler(self)
        if self.observation_policy is None:
            value.pop("observation_policy", None)
        if self.repeat_scheme is None and self.version != "control-atom-evaluation/v4":
            value.pop("repeat_scheme", None)
        return value

    @model_validator(mode="after")
    def validate_specification(self):
        if self.repeat_scheme is not None and self.version != "control-atom-evaluation/v4":
            raise ValueError("历史求值规格不能补入新复查规则冒充原有记录")
        validate_repeat_source(self.repeat_scheme, self.source_span_ids, self.source_excerpts)
        if (self.determination_mode == "deterministic") != (self.operation is not None):
            raise ValueError("确定性求值须声明计算方式，其他模式不得夹带计算方式")
        if (self.operation == "value_comparison") != (self.predicate is not None):
            raise ValueError("值比较须提供比较条件，其他计算方式不得夹带值比较")
        if self.operation == "time_constraint" and (
            self.operand_attribute not in {"date_range", "record_time"}
            or self.time_purpose in {"not_applicable", "unresolved"}
        ):
            raise ValueError("时间计算须明确日期属性和约束用途")
        if len(self.source_span_ids) != len(self.source_excerpts):
            raise ValueError("求值规格原文与来源必须逐项对应")
        if len(set(zip(self.source_span_ids, self.source_excerpts))) != len(self.source_span_ids):
            raise ValueError("求值规格来源与摘录不得成对重复")
        if any(not value.strip() for value in (*self.source_span_ids, *self.source_excerpts)):
            raise ValueError("求值规格不得使用空白原文或来源")
        if self.predicate is not None:
            if self.predicate.observation_policy is not None:
                raise ValueError("补充要求的观察政策只能由所在求值规格声明，不得在比较条件内重复")
            if self.predicate.repeat_scheme is not None:
                raise ValueError("补充要求的复查规则只能由所在求值规格声明，不得在比较条件内重复")
            if (self.predicate.occurrence_window is not None
                    and self.predicate.occurrence_window.scope is not None
                    and (self.repeat_scheme is not None or self.observation_policy is not None)):
                raise ValueError("频次期间不能与未定义先后关系的观察选择或复查采用混用")
            if self.operand_attribute != "value":
                raise ValueError("普通值比较不能冒充日期间隔或书面判断计算")
            if self.predicate.requires_professional_judgment:
                raise ValueError("研究者书面判断不能伪装成确定性值比较")
            clauses = self.predicate.exact_source_clauses
            if not clauses or any(
                not any(clause in excerpt for excerpt in self.source_excerpts) for clause in clauses
            ):
                raise ValueError("比较条件必须保留求值规格内的逐字原文")
        return self


def validate_control_atom_evaluation(atom, *, require_explicit=False):
    """Verify source containment only; it does not prove semantic fidelity."""
    spec = atom.evaluation
    if spec is None:
        if require_explicit:
            raise ValueError("控制原子尚未提供求值规格")
        return
    spec = ControlAtomEvaluationSpec.model_validate(spec.model_dump(mode="json"))
    if spec.determination_mode == "investigator_judgment" and not atom.requires_professional_judgment:
        raise ValueError("研究者判断模式须与所在原子的判断要求一致")
    sources = tuple(zip(atom.source_span_ids, atom.source_excerpts, strict=True))
    if any(
        not any(owner_span == span and excerpt in owner_excerpt for owner_span, owner_excerpt in sources)
        for span, excerpt in zip(spec.source_span_ids, spec.source_excerpts, strict=True)
    ):
        raise ValueError("求值规格原文不属于所在控制原子")
    policy = spec.observation_policy
    validate_observation_window_order(policy, has_time_constraint=atom.time_constraint is not None,
                                      require_explicit=require_explicit)
    if (policy is not None and policy.selection is not None
            and spec.determination_mode != "deterministic" and spec.version not in {"control-atom-evaluation/v3", "control-atom-evaluation/v4"}):
        raise ValueError("历史求值规格不支持语义观察排序，请按原文重新解构，不能补推旧记录")
    declared_occurrence = (spec.predicate is not None
                           and spec.predicate.occurrence_window is not None
                           and spec.predicate.occurrence_window.scope is not None)
    if (require_explicit and policy is None and not declared_occurrence
            and (spec.determination_mode == "deterministic" or spec.version in {"control-atom-evaluation/v3", "control-atom-evaluation/v4"})):
        raise ValueError("求值规格须说明观察选择规则；原文不足时明确保留未核实")
    if policy is not None and any(
        not any(owner_span == span and excerpt in owner_excerpt for owner_span, owner_excerpt in sources)
        for span, excerpt in zip(policy.source_span_ids, policy.source_excerpts, strict=True)
    ):
        raise ValueError("观察选择的原文不属于所在控制原子")
    if atom.time_constraint is None and spec.time_purpose not in {"not_applicable", "unresolved"}:
        raise ValueError("未给出时间约束，不能声明已确定其计算用途")
    if atom.time_constraint is not None and spec.time_purpose == "not_applicable":
        raise ValueError("已有时间约束不能在求值规格中忽略")
    if spec.operation == "time_constraint" and atom.time_constraint is None:
        raise ValueError("时间计算缺少所在原子的时间约束")
    if spec.operation == "time_constraint" and spec.time_operand_attribute is not None:
        raise ValueError("单独时间计算使用已声明的日期操作数，不得再声明第二个日期属性")
    supports_semantic_time = (spec.version in {"control-atom-evaluation/v2", "control-atom-evaluation/v3", "control-atom-evaluation/v4"}
                              and spec.determination_mode != "deterministic")
    if (spec.operation == "value_comparison" or supports_semantic_time) and atom.time_constraint is not None:
        if spec.time_operand_attribute is None:
            raise ValueError("附时间条件的核对须单独声明日期属性")
    elif spec.time_operand_attribute is not None:
        raise ValueError("本规格没有支持的附加时间条件，不能夹带日期属性")


def validate_control_evaluations(control):
    from .control_time_binding import validate_control_time_bindings
    validate_control_time_bindings(control, require_explicit=True)
    validate_control_expression_evaluations(control)


def validate_control_expression_evaluations(control):
    """Check shared atom layers before or after formal control hydration."""
    for layer in ("applicability", "trigger", "obligation", "exception"):
        expression = getattr(control, f"{layer}_expression")
        if expression is not None:
            for group in expression.groups:
                for atom in group.atoms:
                    validate_control_atom_evaluation(atom, require_explicit=True)
