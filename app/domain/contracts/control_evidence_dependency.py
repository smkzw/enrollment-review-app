"""Source-declared evidence dependencies within one frozen control expression."""
from typing import Literal

from pydantic import ConfigDict, Field, model_serializer, model_validator

from .common import ContractModel


def control_atom_reference_key(layer, group_index, atom_index, condition_id=None):
    key = (layer, group_index, atom_index)
    return (*key, condition_id) if layer == "repeat_trigger" else key


class ControlEvidenceAtomReference(ContractModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    layer: Literal["applicability", "trigger", "obligation", "exception", "repeat_trigger"]
    group_index: int = Field(ge=0, strict=True)
    atom_index: int = Field(ge=0, strict=True)
    condition_id: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_condition_reference(self):
        if (self.layer == "repeat_trigger") != (self.condition_id is not None):
            raise ValueError("复查条件引用必须且只能携带所属条件编号")
        if self.condition_id is not None and not self.condition_id.strip():
            raise ValueError("复查条件编号不能为空")
        return self

    @model_serializer(mode="wrap")
    def preserve_legacy_reference(self, handler):
        value = handler(self)
        if self.condition_id is None:
            value.pop("condition_id", None)
        return value

    @property
    def key(self) -> tuple:
        return control_atom_reference_key(self.layer, self.group_index, self.atom_index, self.condition_id)


def validate_control_evidence_dependencies(control, *, require_explicit: bool = True) -> None:
    """Validate references, not whether the semantic association is correct.

    Positions refer only to this immutable expression; publication hashes bind
    ordering. They are never reused across a changed catalog or matched by text.
    """
    for evidence in control.minimum_evidence:
        if require_explicit and not evidence.atom_refs:
            raise ValueError("资料要求尚未明确用于核实哪项条件或要求")
        keys = [ref.key for ref in evidence.atom_refs]
        if len(keys) != len(set(keys)):
            raise ValueError("同一资料要求的条件引用不能重复")
        for ref in evidence.atom_refs:
            if ref.layer == "repeat_trigger":
                condition = next((item for item in control.repeat_trigger_conditions
                                  if item.condition_id == ref.condition_id), None)
                expression = condition.expression if condition is not None else None
            else:
                expression = getattr(control, f"{ref.layer}_expression")
            if expression is None or ref.group_index >= len(expression.groups):
                raise ValueError("资料要求引用了不存在的条件组")
            if ref.atom_index >= len(expression.groups[ref.group_index].atoms):
                raise ValueError("资料要求引用了不存在的条件或要求")
