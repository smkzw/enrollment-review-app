"""Frozen source identities for control atoms, not accepted clinical bindings."""
from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict, Field, model_serializer, model_validator

from .common import ContractModel
from .control_evidence_dependency import ControlEvidenceAtomReference
from .protocol_controls import ControlConditionAtom, ControlObligationAtom
from .control_catalog_publication import ControlCatalogPublication
from .predicate_binding import PredicateBindingFrozenInput
from app.domain.publication import canonical_hash


class FrozenControlAtomIdentity(ContractModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    publication_id: str = Field(min_length=1)
    catalog_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    protocol_control_id: str = Field(min_length=1)
    layer: Literal["applicability", "trigger", "obligation", "exception", "repeat_trigger"]
    condition_id: str | None = Field(default=None, min_length=1)
    group_index: int = Field(ge=0)
    atom_index: int = Field(ge=0)
    atom_id: str = Field(min_length=1)
    atom: ControlConditionAtom | ControlObligationAtom
    identity_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @property
    def reference(self) -> ControlEvidenceAtomReference:
        return ControlEvidenceAtomReference(layer=self.layer, group_index=self.group_index,
                                            atom_index=self.atom_index, condition_id=self.condition_id)

    @model_serializer(mode="wrap")
    def preserve_legacy_identity(self, handler):
        value = handler(self)
        if self.condition_id is None:
            value.pop("condition_id", None)
        return value

    @model_validator(mode="after")
    def validate_identity(self) -> "FrozenControlAtomIdentity":
        _ = self.reference
        obligation = isinstance(self.atom, ControlObligationAtom)
        if obligation != (self.layer == "obligation"):
            raise ValueError("控制原子类型与所属条件层不一致")
        atom_id = self.atom.obligation_id if obligation else self.atom.condition_atom_id
        if atom_id != self.atom_id:
            raise ValueError("控制原子身份与原始内容不一致")
        material = self.model_dump(mode="json", exclude={"identity_sha256"})
        if canonical_hash({"identity": "control_atom_binding/v1", **material}) != self.identity_sha256:
            raise ValueError("控制原子的冻结身份与来源内容不一致")
        return self


class ControlBindingFrozenInput(ContractModel):
    """Reuse the current source/fact snapshot; no second source selection pipeline.

    Construction must use the stored publication and verified binding snapshot.
    This contract checks scope/content identity, not clinical correspondence.
    """

    binding_input_version: Literal["control-binding-frozen-input/v1"] = "control-binding-frozen-input/v1"
    publication: ControlCatalogPublication
    evidence_input: PredicateBindingFrozenInput
    frozen_input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @property
    def facts(self):
        """共享当前事实快照；候选对应与逐事实处置都引用同一事实集合。"""
        return self.evidence_input.facts

    @property
    def components(self):
        return self.evidence_input.components

    @model_validator(mode="after")
    def validate_input(self) -> "ControlBindingFrozenInput":
        source = self.evidence_input
        publication = self.publication
        if (
            publication.project_id != source.authority.project_id
            or publication.protocol_version_id != source.protocol_version_id
            or publication.rule_set_id != source.rule_set_id
            or publication.rule_set_revision != source.rule_set_revision
            or publication.catalog.study_phase != source.study_phase
        ):
            raise ValueError("补充控制与当前事实资料不属于同一方案修订")
        if self.frozen_input_sha256 != control_binding_input_hash(publication, source):
            raise ValueError("补充控制证明输入与冻结内容不一致")
        return self


def control_binding_input_hash(
    publication: ControlCatalogPublication,
    evidence_input: PredicateBindingFrozenInput,
) -> str:
    return canonical_hash({
        "identity": "control-binding-frozen-input/v1",
        "publication": publication.model_dump(mode="json"),
        "evidence_input_sha256": evidence_input.frozen_input_sha256,
    })
