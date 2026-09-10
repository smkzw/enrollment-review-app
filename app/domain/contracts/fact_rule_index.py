"""Phase 5 规则索引合同与确定性推导（Slice 5.4，worker_02）。

设计书 §5.1：事实到已发布 ``RuleComponent`` / ``EvidenceRequirement`` 的双向索引
只基于已发布 ``fact_type`` / ``RuleComponent`` / ``EvidenceRequirement`` 的明确身份
和版本化映射建立；禁止自由文本模糊相似度（title/description/asserted_object 一律
不参与匹配）；索引可完全重建且不写回方案规则。

``FactRuleLink`` 严格镜像 ``fact_rule_links_v2`` 表的八个规范化列，frozen 不可变。
该表是确定性投影、没有独立 payload 列，因此 ``link_id`` 是对身份字段的确定性内容
哈希（:func:`fact_rule_link_id`），作为不可变性锚点：任何列值漂移都会使重建的
``link_id`` 失配，读取与重建即拒绝。

:func:`derive_fact_rule_links` 是纯确定性推导：

- 事实只与其权威元组相同 ``(rule_set_id, rule_set_revision)`` 的已发布资料要求匹配，
  绝不跨规则集修订建链；
- 仅当事实显式绑定资料要求 ID，且资料要求 ``fact_type`` 与事实 ``fact_type`` 完全相等时建立
  ``evidence_requirement`` 链接；
- 仅当该要求显式携带 ``rule_component_id`` 时才通过该显式身份追加
  ``rule_component`` 链接；流程必做项目录来源（无组件）不捏造组件链接；
- 结果按 ``(fact_id, target_kind, target_id)`` 稳定排序，幂等可重建。
"""
from __future__ import annotations

from typing import Literal, NamedTuple, Sequence

from pydantic import ConfigDict, Field, model_validator

from app.domain.contracts.common import ContractModel
from app.domain.contracts.facts import ClinicalFactV2
from app.domain.publication import canonical_hash

FactRuleTargetKind = Literal["rule_component", "evidence_requirement"]


class PublishedRequirement(NamedTuple):
    """已发布资料要求的索引所需最小身份（来自 ``evidence_requirements`` 规范化列）。

    ``rule_component_id`` 为 None 表示流程必做项目录来源，不产生组件链接。
    """

    requirement_id: str
    rule_component_id: str | None
    fact_type: str


class FactRuleLink(ContractModel):
    """事实到已发布 RuleComponent/EvidenceRequirement 的不可变双向索引行。

    父列判别与表上 ``ck_frl_target_parent`` 完全一致：

    - ``target_kind='rule_component'``：``rule_component_id == target_id`` 且
      ``evidence_requirement_id IS NULL``；
    - ``target_kind='evidence_requirement'``：``evidence_requirement_id == target_id``
      且 ``rule_component_id IS NULL``。

    任何父列自洽漂移都在合同层拒绝（列漂移），与数据库 CHECK 互为双保险。
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    link_id: str = Field(min_length=1)
    fact_id: str = Field(min_length=1)
    target_kind: FactRuleTargetKind
    rule_set_id: str = Field(min_length=1)
    rule_set_revision: int = Field(ge=1)
    target_id: str = Field(min_length=1)
    rule_component_id: str | None = Field(default=None, min_length=1)
    evidence_requirement_id: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_parent_columns(self) -> "FactRuleLink":
        if self.target_kind == "rule_component":
            if self.rule_component_id != self.target_id:
                raise ValueError(
                    "rule_component 链接必须 rule_component_id == target_id"
                )
            if self.evidence_requirement_id is not None:
                raise ValueError(
                    "rule_component 链接不得携带 evidence_requirement_id"
                )
        else:
            if self.evidence_requirement_id != self.target_id:
                raise ValueError(
                    "evidence_requirement 链接必须 evidence_requirement_id == target_id"
                )
            if self.rule_component_id is not None:
                raise ValueError(
                    "evidence_requirement 链接不得携带 rule_component_id"
                )
        return self


def fact_rule_link_id(
    *,
    fact_id: str,
    target_kind: str,
    rule_set_id: str,
    rule_set_revision: int,
    target_id: str,
) -> str:
    """确定性内容身份：身份字段任何漂移都会使重建的 ``link_id`` 失配。

    ``fact_rule_links_v2`` 没有 payload 列，这条内容哈希即不可变性锚点
    （等价于 payload 完整性校验）。
    """
    return canonical_hash(
        {
            "fact_id": fact_id,
            "target_kind": target_kind,
            "rule_set_id": rule_set_id,
            "rule_set_revision": rule_set_revision,
            "target_id": target_id,
        }
    )


def _make_link(
    *,
    fact_id: str,
    target_kind: FactRuleTargetKind,
    rule_set_id: str,
    rule_set_revision: int,
    target_id: str,
) -> FactRuleLink:
    return FactRuleLink(
        link_id=fact_rule_link_id(
            fact_id=fact_id,
            target_kind=target_kind,
            rule_set_id=rule_set_id,
            rule_set_revision=rule_set_revision,
            target_id=target_id,
        ),
        fact_id=fact_id,
        target_kind=target_kind,
        rule_set_id=rule_set_id,
        rule_set_revision=rule_set_revision,
        target_id=target_id,
        rule_component_id=target_id if target_kind == "rule_component" else None,
        evidence_requirement_id=(
            target_id if target_kind == "evidence_requirement" else None
        ),
    )


def derive_fact_rule_links(
    facts: Sequence[ClinicalFactV2],
    requirements: Sequence[PublishedRequirement],
    *,
    rule_set_id: str,
    rule_set_revision: int,
) -> list[FactRuleLink]:
    """纯确定性索引推导：只按显式身份 + 精确 ``fact_type`` 相等建立链接。

    - 事实的权威元组必须与 ``(rule_set_id, rule_set_revision)`` 一致，跨规则集
      修订的事实不参与；
    - 只有要求 ID 明确属于事实的 ``supported_requirement_ids``，且
      ``PublishedRequirement.fact_type == fact.fact_type`` 时才建
      ``evidence_requirement`` 链接；绝不使用 title/description/asserted_object
      等自由文本相似度；
    - 仅当要求显式 ``rule_component_id`` 非空时，经该显式身份追加
      ``rule_component`` 链接；流程必做项目录来源（无组件）不捏造组件；
    - 同一 ``(fact, target)`` 只产生一条链接（多条要求共享组件时去重）；
    - 返回按 ``(fact_id, target_kind, target_id)`` 稳定排序，重建前后等价。
    """
    links: list[FactRuleLink] = []
    seen: set[str] = set()
    for fact in facts:
        if (
            fact.authority.rule_set_id != rule_set_id
            or fact.authority.rule_set_revision != rule_set_revision
        ):
            continue
        for requirement in requirements:
            if (
                requirement.requirement_id not in fact.supported_requirement_ids
                or requirement.fact_type != fact.fact_type
            ):
                continue
            requirement_link = _make_link(
                fact_id=fact.fact_id,
                target_kind="evidence_requirement",
                rule_set_id=rule_set_id,
                rule_set_revision=rule_set_revision,
                target_id=requirement.requirement_id,
            )
            if requirement_link.link_id not in seen:
                links.append(requirement_link)
                seen.add(requirement_link.link_id)
            if requirement.rule_component_id is not None:
                component_link = _make_link(
                    fact_id=fact.fact_id,
                    target_kind="rule_component",
                    rule_set_id=rule_set_id,
                    rule_set_revision=rule_set_revision,
                    target_id=requirement.rule_component_id,
                )
                if component_link.link_id not in seen:
                    links.append(component_link)
                    seen.add(component_link.link_id)
    links.sort(key=lambda link: (link.fact_id, link.target_kind, link.target_id))
    return links
