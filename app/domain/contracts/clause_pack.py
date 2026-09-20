"""Compact, content-addressed rule input for page review models."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_serializer, model_validator

from .common import VersionedModel
from .control_catalog_publication import ControlCatalogPublication
from .enums import RuleKind, StableEnum, StudyPhase
from .rules import EvidenceRequirement, RepeatTriggerCondition, RuleExpression

_SHA256 = r"^[0-9a-f]{64}$"


class DeterminationMode(StableEnum):
    DETERMINISTIC = "deterministic"
    SEMANTIC = "semantic"
    INVESTIGATOR_JUDGMENT = "investigator_judgment"


class ClausePackClause(VersionedModel):
    clause_id: str = Field(min_length=1)
    rule_id: str = Field(min_length=1)
    rule_component_id: str = Field(min_length=1)
    official_code: str = Field(pattern=r"^(IN|EX|REQ)-\d{2}$")
    display_code: str = Field(min_length=1)
    kind: RuleKind
    title: str = Field(min_length=1)
    source_text: str = Field(min_length=1)
    expression: RuleExpression
    exception_expression: RuleExpression | None = None
    repeat_trigger_conditions: list[RepeatTriggerCondition] = Field(default_factory=list)
    evidence_requirements: list[EvidenceRequirement] = Field(default_factory=list)
    determination_mode: DeterminationMode

    @model_serializer(mode="wrap")
    def preserve_legacy_material(self, handler):
        data = handler(self)
        if not self.repeat_trigger_conditions:
            data.pop("repeat_trigger_conditions", None)
        return data


class ClausePack(VersionedModel):
    projection_version: Literal["clause-pack/v1", "clause-pack/v2", "clause-pack/v3"] = "clause-pack/v1"
    clause_pack_id: str = Field(pattern=r"^clause-pack:[0-9a-f]{32}$")
    clause_pack_sha256: str = Field(pattern=_SHA256)
    rule_set_id: str = Field(min_length=1)
    rule_set_revision: int = Field(ge=1)
    protocol_version_id: str = Field(min_length=1)
    study_phase: StudyPhase
    clauses: list[ClausePackClause] = Field(min_length=1)
    control_publication: ControlCatalogPublication | None = None

    @model_serializer(mode="wrap")
    def serialize_pack(self, handler):
        data = handler(self)
        # Preserve the canonical bytes of historical v1 packs.
        if self.control_publication is None:
            data.pop("control_publication", None)
        return data

    @model_validator(mode="after")
    def validate_control_scope(self) -> "ClausePack":
        publication = self.control_publication
        if ((self.projection_version == "clause-pack/v1" and publication is not None)
                or (self.projection_version == "clause-pack/v2" and publication is None)):
            raise ValueError("条款包版本与补充审核要求不一致")
        if self.projection_version != "clause-pack/v3" and any(
            item.repeat_trigger_conditions for item in self.clauses
        ):
            raise ValueError("旧版条款包不能补入复查条件")
        if publication is not None:
            if (publication.rule_set_id, publication.rule_set_revision,
                    publication.protocol_version_id, publication.catalog.study_phase) != (
                    self.rule_set_id, self.rule_set_revision,
                    self.protocol_version_id, self.study_phase):
                raise ValueError("补充审核要求与条款包所属方案修订不同")
            official_ids = {item.clause_id for item in self.clauses}
            if official_ids.intersection(item.protocol_control_id for item in publication.catalog.controls):
                raise ValueError("补充审核要求与官方条款身份重复")
        return self


__all__ = ["ClausePack", "ClausePackClause", "DeterminationMode"]
