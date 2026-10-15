"""Explicit source-backed targets for a control-wide temporal constraint."""
from typing import Literal

from pydantic import Field, model_validator

from .common import ContractModel


class ControlTimeBinding(ContractModel):
    layer: Literal["applicability", "trigger", "obligation", "exception"]
    atom_id: str = Field(min_length=1)
    source_span_ids: list[str] = Field(min_length=1)
    source_excerpts: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_sources(self):
        if (len(self.source_span_ids) != len(self.source_excerpts)
                or len(set(self.source_span_ids)) != len(self.source_span_ids)
                or any(not value.strip() for value in (
                    self.atom_id, *self.source_span_ids, *self.source_excerpts))):
            raise ValueError("时间要求的对应条目及原文必须明确且逐项对应")
        return self


def validate_control_time_bindings(control, *, require_explicit=False):
    """Validate declarations, never infer targets or copy a window into atoms.

    Target atoms retain their own executable window and purpose. Thus the same
    qualified atom identity is consumed by arithmetic and composition, without
    an implicit inherited constraint that is absent from its frozen body.
    """
    bindings = control.control_time_bindings
    constraint = control.control_time_constraint
    if not bindings:
        if require_explicit and constraint is not None:
            raise ValueError("控制级时间要求尚未明确对应条目，不能忽略后继续审核")
        return
    if constraint is None:
        raise ValueError("时间要求对应清单缺少控制级时间约束")
    atoms = {}
    for layer in ("applicability", "trigger", "obligation", "exception"):
        expression = getattr(control, f"{layer}_expression")
        if expression is not None:
            for group in expression.groups:
                for atom in group.atoms:
                    atom_id = atom.obligation_id if layer == "obligation" else atom.condition_atom_id
                    key = (layer, atom_id)
                    if key in atoms:
                        raise ValueError("时间要求对应条目的身份重复")
                    atoms[key] = atom
    seen = set()
    for binding in bindings:
        key = (binding.layer, binding.atom_id)
        if key in seen or key not in atoms:
            raise ValueError("时间要求必须引用唯一且存在的具体条目")
        seen.add(key)
        atom = atoms[key]
        if atom.time_constraint != constraint:
            raise ValueError("对应条目必须显式保留同一时间约束，不得在计算时隐式补写")
        spec = atom.evaluation
        if spec is None or spec.time_purpose not in {
            "event_membership", "interval_condition", "source_validity",
        }:
            raise ValueError("对应条目尚未明确时间要求的用途")
        sources = tuple(zip(atom.source_span_ids, atom.source_excerpts, strict=True))
        if any(not any(owner_span == span and excerpt in owner_excerpt for owner_span, owner_excerpt in sources)
               for span, excerpt in zip(binding.source_span_ids, binding.source_excerpts, strict=True)):
            raise ValueError("时间要求的对应依据必须保留在该条目的方案原文中")
