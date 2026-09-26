"""Source entailment candidates, separate from page reading and eligibility."""
from typing import Literal

from pydantic import Field, model_validator

from .common import ContractModel

PROPOSITION_EVIDENCE_VERSION = "proposition-evidence/v7"


class ActionCompletionWitness(ContractModel):
    """A source quote about the required action, not its clinical result."""

    status: Literal["completed", "explicit_not_completed", "not_established"]
    action_quote: str | None

    @model_validator(mode="after")
    def validate_quote(self):
        if (self.status == "not_established") != (self.action_quote is None):
            raise ValueError("操作完成或明确未做须有对应原文；未证实不得伪造原文")
        if self.action_quote is not None and not self.action_quote.strip():
            raise ValueError("操作依据原文不能为空")
        return self


class ProspectiveEvidenceCheck(ContractModel):
    """What the source states about a period, not proof of future conduct."""

    requirement_kind: Literal["statement_of_intent", "ongoing_conduct", "unresolved"]
    requirement_quote: str = Field(min_length=1)
    period_correspondence: Literal["supported", "partial", "unresolved"]
    period_quote: str | None

    @model_validator(mode="after")
    def validate_period_sources(self):
        if not self.requirement_quote.strip():
            raise ValueError("未来期间的要求须保留方案原文")
        if self.period_quote is not None and not self.period_quote.strip():
            raise ValueError("期间声明的原文不能是空白")
        if self.period_correspondence != "unresolved" and self.period_quote is None:
            raise ValueError("确认全部或部分期间须保留该记录的原文")
        return self

    def agreement_key(self):
        return self.requirement_kind, self.period_correspondence

    def unresolved_codes(self):
        reasons = []
        if self.requirement_kind == "ongoing_conduct":
            reasons.append("future_conduct_not_established")
        elif self.requirement_kind == "unresolved":
            reasons.append("prospective_requirement_unverified")
        if self.period_correspondence != "supported":
            reasons.append("prospective_statement_period_unverified")
        return reasons


class PropositionPairGap(ContractModel):
    pair_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    identity_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    fact_id: str = Field(min_length=1)
    locator_id: str = Field(min_length=1)
    reasons: list[str] = Field(min_length=1)


class PropositionEvidenceCheck(ContractModel):
    pair_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    proposition_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    scope: Literal["pair_local"]
    scope_correspondence: Literal["supported", "partial", "unresolved"]
    scope_quote: str | None
    assertion_extent: Literal["individual", "universal_over_declared_scope", "unresolved"]
    scope_population: Literal["nonempty", "empty", "unresolved"]
    population_quote: str | None
    prospective_evidence: ProspectiveEvidenceCheck | None
    action_witness: ActionCompletionWitness | None = None
    target_correspondence: Literal["supported", "rejected", "unresolved"]
    node_correspondence: Literal["supported", "rejected", "unresolved"]
    investigator_attribution: Literal["supported", "rejected", "unresolved", "not_applicable"]
    relation: Literal["entails", "contradicts", "undetermined"]
    basis: Literal["explicit_statement", "explicit_investigator_judgment", "insufficient"]
    quoted_evidence: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    unresolved_reasons: list[str]

    @model_validator(mode="after")
    def validate_basis(self):
        if (self.relation != "undetermined" and self.prospective_evidence is not None
                and self.prospective_evidence.unresolved_codes()):
            raise ValueError("期间要求或声明尚未核实，不能给出明确的命题关系")
        if self.scope_quote is not None and not self.scope_quote.strip():
            raise ValueError("观察范围引用不能是空白")
        if self.scope_correspondence == "supported" and self.scope_quote is None:
            raise ValueError("确认观察范围须保留对应原文")
        if self.population_quote is not None and not self.population_quote.strip():
            raise ValueError("观察集合引用不能是空白")
        if self.scope_population != "unresolved" and self.population_quote is None:
            raise ValueError("确认观察集合存在或为空须提供原文")
        if self.assertion_extent != "universal_over_declared_scope" and (
            self.scope_population != "unresolved" or self.population_quote is not None
        ):
            raise ValueError("单项原文不得补充整范围的观察集合声明")
        if self.assertion_extent == "universal_over_declared_scope" and (
            self.scope_correspondence != "supported" or self.relation == "undetermined"
        ):
            raise ValueError("整范围断言须有明确的范围及命题依据")
        if (not self.quoted_evidence.strip() or not self.explanation.strip()
                or any(not reason.strip() for reason in self.unresolved_reasons)):
            raise ValueError("命题核实须保留具体原文和说明")
        if self.relation == "undetermined":
            if not self.unresolved_reasons:
                raise ValueError("无法核实命题时须说明缺少的依据")
        elif self.basis == "insufficient" or self.unresolved_reasons:
            raise ValueError("依据不足时不能确认支持或反对命题")
        if self.relation != "undetermined" and (
            self.target_correspondence != "supported" or self.node_correspondence != "supported"
            or self.investigator_attribution in {"rejected", "unresolved"}
        ):
            raise ValueError("对象、节点或判断归属未核实时不能给出明确关系")
        return self

    def agreement_key(self):
        return (self.proposition_sha256, self.scope, self.relation, self.basis,
                self.target_correspondence, self.node_correspondence, self.investigator_attribution,
                self.scope_correspondence, self.assertion_extent, self.scope_population,
                self.prospective_evidence.agreement_key() if self.prospective_evidence else None,
                self.action_witness.status if self.action_witness else None)


class PropositionEvidencePayload(ContractModel):
    results: list[PropositionEvidenceCheck]

    @model_validator(mode="after")
    def unique_pairs(self):
        identifiers = [item.pair_id for item in self.results]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("命题核实配对不得重复")
        return self
