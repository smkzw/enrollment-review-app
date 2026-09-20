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

ACCOUNTING_V1 = "candidate-fact-accounting/v1"
ACCOUNTING_V2 = "candidate-fact-accounting/v2"
#: 新读取提示词使用 v2 分组处置；v1 记录保持可读、可回放，不升格为新证据。
ACCOUNTING_VERSION = ACCOUNTING_V2
_ACCOUNTING_VERSIONS = (ACCOUNTING_V1, ACCOUNTING_V2)

FactDisposition = Literal["has_candidates", "noncorrespondence", "uncertain"]

#: v2 分组处置的原因码：一条记录解释一组同因事实，替代逐事实长说明。
AccountingReasonCode = Literal[
    "different_object",
    "different_time_scope",
    "different_attribute",
    "category_match_only",
    "value_form_mismatch",
    "different_source_scope",
]


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


class FactGroupDisposition(ContractModel):
    """v2：一条记录给出一组共享同一原因码的事实处置。"""

    disposition: Literal["noncorrespondence", "uncertain"]
    fact_ids: list[str] = Field(min_length=1)
    reason_code: AccountingReasonCode
    source_locator_ids: list[str] = Field(default_factory=list)
    note: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def validate_group(self) -> "FactGroupDisposition":
        if len(self.fact_ids) != len(set(self.fact_ids)):
            raise ValueError("同一分组处置内的事实不得重复")
        if self.disposition == "noncorrespondence" and not self.source_locator_ids:
            raise ValueError("无对应分组必须引用已核对的具体来源定位")
        return self


class FactDefaultGroup(ContractModel):
    """v2 默认处置：声明一次，适用于未被候选或分组覆盖的全部剩余事实。"""

    disposition: Literal["noncorrespondence", "uncertain"]
    reason_code: AccountingReasonCode
    source_locator_ids: list[str] = Field(default_factory=list)
    note: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def validate_default(self) -> "FactDefaultGroup":
        # 默认处置是剩余桶：典型场景是"人口学/元数据事实与本条件无对象级
        # 关联"，属于结构性不对应，没有也不需要引用某条具体来源定位。
        # 候选与显式分组的定位强制保持不变；条件原文未核实时仍不得声称
        # noncorrespondence（在分组校验中执行）。
        return self


class IdentityFactAccounting(ContractModel):
    """One identity's consideration of exactly the facts supplied to its read.

    v1：逐事实一条 ``considered_facts`` 记录（历史 payload 保持可读可回放）。
    v2：候选事实由候选记录承担；其余事实按"同因一组"返回分组处置，
    覆盖规则与 v1 相同——候选 ∪ 分组 = 本次提供的全部事实。
    """

    accounting_version: Literal[ACCOUNTING_V1, ACCOUNTING_V2] = ACCOUNTING_V2
    considered_facts: list[FactConsideration] = Field(default_factory=list)
    grouped_dispositions: list[FactGroupDisposition] = Field(default_factory=list)
    default_group: FactDefaultGroup | None = None

    @model_validator(mode="after")
    def validate_accounting(self) -> "IdentityFactAccounting":
        ids = [item.fact_id for item in self.considered_facts]
        if len(ids) != len(set(ids)):
            raise ValueError("同一条件对同一事实只能有一条考虑记录")
        if self.accounting_version == ACCOUNTING_V2 and self.considered_facts:
            raise ValueError("v2 记录不得混用 v1 逐事实说明")
        grouped = [fact_id for group in self.grouped_dispositions for fact_id in group.fact_ids]
        if len(grouped) != len(set(grouped)):
            raise ValueError("同一事实只能出现在一个分组处置中")
        if self.accounting_version == ACCOUNTING_V1 and (self.grouped_dispositions or self.default_group):
            raise ValueError("v1 记录不得混用 v2 分组处置")
        if self.accounting_version == ACCOUNTING_V1 and self.default_group is not None:
            raise ValueError("v1 记录不得使用默认处置")
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
    if accounting.accounting_version == ACCOUNTING_V2:
        _validate_grouped_accounting(
            accounting=accounting,
            fact_universe=fact_universe,
            candidates_by_fact=candidates_by_fact,
            source_locators=source_locators,
            condition_verified=condition_verified,
            where=where,
        )
        return
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


def _validate_grouped_accounting(
    *,
    accounting: IdentityFactAccounting,
    fact_universe: dict[str, Any],
    candidates_by_fact: dict[str, Any],
    source_locators: dict[str, Any],
    condition_verified: bool,
    where: str,
) -> None:
    """v2 分组处置：候选事实不进组；分组（或默认处置）须覆盖全部剩余事实。

    允许 default_group 声明默认处置：未被候选或分组覆盖的事实按默认处置计，
    避免跨条件重复罗列同一批事实标识。
    """
    grouped: dict[str, "FactGroupDisposition"] = {}
    for group in accounting.grouped_dispositions:
        for fact_id in group.fact_ids:
            if fact_id in grouped:
                raise ValueError(f"{where}事实{fact_id}出现在多个分组处置中")
            grouped[fact_id] = group
    candidate_fact_ids = set(candidates_by_fact)
    overlap = candidate_fact_ids & set(grouped)
    if overlap:
        raise ValueError(
            f"{where}提出候选的事实{sorted(overlap)[:3]}不得再进入分组处置"
        )
    extra = sorted(set(grouped) - set(fact_universe))
    if extra:
        raise ValueError(f"{where}分组处置引用了未提供的事实{extra[:3]}")
    covered = candidate_fact_ids | set(grouped)
    default = accounting.default_group
    if default is None:
        missing = sorted(set(fact_universe) - covered)
        if missing:
            raise ValueError(
                f"{where}分组处置加候选必须恰好覆盖本次提供的全部事实"
                f"（缺失{len(missing)}条{missing[:3]}）；无默认处置时不得留空"
            )
    else:
        if default.disposition == "noncorrespondence" and not condition_verified:
            raise ValueError(f"{where}条件原文未核实时默认处置不得为noncorrespondence")
        if default.disposition == "noncorrespondence" and any(
            locator_id not in source_locators
            or not (source_locators[locator_id].excerpt or "").strip()
            for locator_id in default.source_locator_ids
        ):
            raise ValueError(f"{where}默认无对应处置必须具有本次提供的可读原文依据")
    for group in accounting.grouped_dispositions:
        locators = set()
        for fact_id in group.fact_ids:
            fact = fact_universe[fact_id]
            locators.update(fact.locator_ids)
        if any(key not in locators for key in group.source_locator_ids):
            raise ValueError(f"{where}分组{group.reason_code}引用了不属于该组事实的来源定位")
        if group.disposition == "noncorrespondence":
            if not condition_verified:
                raise ValueError(
                    f"{where}条件原文未核实时不得声称无对应，该组应保留uncertain"
                )
            if any(
                locator_id not in source_locators
                or not (source_locators[locator_id].excerpt or "").strip()
                for locator_id in group.source_locator_ids
            ):
                raise ValueError(f"{where}无对应分组必须具有本次提供的可读原文依据")
