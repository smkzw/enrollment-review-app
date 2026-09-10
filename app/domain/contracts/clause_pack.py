"""Compact, content-addressed rule input for page review models."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from .common import VersionedModel
from .enums import RuleKind, StableEnum, StudyPhase
from .rules import EvidenceRequirement, RuleExpression

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
    evidence_requirements: list[EvidenceRequirement] = Field(default_factory=list)
    determination_mode: DeterminationMode


class ClausePack(VersionedModel):
    projection_version: Literal["clause-pack/v1"] = "clause-pack/v1"
    clause_pack_id: str = Field(pattern=r"^clause-pack:[0-9a-f]{32}$")
    clause_pack_sha256: str = Field(pattern=_SHA256)
    rule_set_id: str = Field(min_length=1)
    rule_set_revision: int = Field(ge=1)
    protocol_version_id: str = Field(min_length=1)
    study_phase: StudyPhase
    clauses: list[ClausePackClause] = Field(min_length=1)


__all__ = ["ClausePack", "ClausePackClause", "DeterminationMode"]
