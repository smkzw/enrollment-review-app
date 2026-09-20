"""Shared versioned per-fact consideration accounting for candidate reads.

Every condition identity must account for each fact supplied to its read: the
fact either carries candidates, carries a source-bound noncorrespondence
explanation, or remains explicitly uncertain. fact_type or clinical category
never proves a fact was considered; exact structural coverage is not semantic
correctness and is never proof of a complete patient history.
"""

from typing import Any, Literal

from pydantic import Field, model_validator

from app.domain.contracts.common import ContractModel

ACCOUNTING_VERSION = "candidate-fact-accounting/v1"

FactDisposition = Literal["has_candidates", "noncorrespondence", "uncertain"]


class FactConsideration(ContractModel):
    fact_id: str = Field(min_length=1)
    disposition: FactDisposition
    explanation: str = Field(min_length=1)
    source_locator_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_consideration(self) -> "FactConsideration":
        if not self.explanation.strip():
            raise ValueError("逐事实考虑说明不得为空白")
        if len(self.source_locator_ids) != len(set(self.source_locator_ids)):
            raise ValueError("同一考虑记录的来源定位不得重复")
        if self.disposition == "has_candidates" and self.source_locator_ids:
            raise ValueError("提出候选的事实的来源关联由候选记录承担，考虑记录不得另列来源")
        return self


class IdentityFactAccounting(ContractModel):
    """One identity's consideration of exactly the facts supplied to its read."""

    accounting_version: Literal[ACCOUNTING_VERSION]
    considered_facts: list[FactConsideration] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_accounting(self) -> "IdentityFactAccounting":
        ids = [item.fact_id for item in self.considered_facts]
        if len(ids) != len(set(ids)):
            raise ValueError("同一条件对同一事实只能有一条考虑记录")
        return self


def validate_identity_fact_accounting(
    *,
    accounting: IdentityFactAccounting,
    fact_universe: dict[str, Any],
    candidates_by_fact: dict[str, list[Any]],
    source_locators: dict[str, Any],
    condition_verified: bool = True,
    where: str = "",
) -> None:
    """Exact per-read coverage plus candidate/disposition consistency.

    fact_universe maps fact_id to the frozen fact supplied to this read (needs
    .locator_ids); candidates_by_fact groups the same result's candidate
    entries by fact_id. Missing, extra or duplicate accounting is rejected, as
    are forged locator associations and unexplained uncertainty. When the
    condition's verbatim source is unverified, a definite noncorrespondence is
    not allowed to smuggle semantic claims through the accounting lane.
    """
    considered = {item.fact_id: item for item in accounting.considered_facts}
    if len(considered) != len(accounting.considered_facts):
        raise ValueError(f"{where}逐事实考虑记录不得重复同一事实")
    if set(considered) != set(fact_universe):
        missing = len(set(fact_universe) - set(considered))
        extra = len(set(considered) - set(fact_universe))
        raise ValueError(
            f"{where}逐事实考虑记录必须恰好覆盖本次读取提供的全部事实"
            f"（缺失{missing}条，多出{extra}条）"
        )
    for fact_id in sorted(considered):
        consideration = considered[fact_id]
        fact = fact_universe[fact_id]
        locators = set(fact.locator_ids)
        has_candidates = bool(candidates_by_fact.get(fact_id))
        if has_candidates != (consideration.disposition == "has_candidates"):
            raise ValueError(f"{where}事实{fact_id}的候选存在情况与考虑处置互相矛盾")
        if any(key not in locators for key in consideration.source_locator_ids):
            raise ValueError(f"{where}事实{fact_id}的考虑记录引用了不属于该事实的来源定位")
        if consideration.disposition == "noncorrespondence":
            if not consideration.source_locator_ids:
                raise ValueError(f"{where}事实{fact_id}声称无对应时必须引用已核对的具体来源定位")
            if not condition_verified:
                raise ValueError(f"{where}条件原文未核实时不得声称事实{fact_id}无对应，应保留uncertain")
            if any(
                locator_id not in source_locators
                or not (source_locators[locator_id].excerpt or "").strip()
                for locator_id in consideration.source_locator_ids
            ):
                raise ValueError(f"{where}无对应的说明必须具有本次提供的可读原文依据")
