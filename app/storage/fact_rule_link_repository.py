"""Phase 5 规则索引仓储（Slice 5.4，worker_02）。

在 ``fact_rule_links_v2`` 之上提供不可变双向索引的确定性读写与可重建投影：

- 推导只来自已发布事实显式绑定的资料要求 ID、已发布资料要求
  （``evidence_requirements``）的精确 ``fact_type`` 以及要求显式
  ``rule_component_id``；绝不使用自由文本模糊匹配；
- ``rebuild_for_episode`` 先对每个既有行做完整校验（父列自洽、``link_id``
  内容哈希、父实体/父要求可推导）再删除/替换；任何漂移整批拒绝，绝不清扫；
- 幂等：二次重建无差异即无操作；所有查询稳定排序。

``fact_rule_links_v2`` 没有独立 payload 列；``link_id`` 是对身份字段的确定性
内容哈希（:func:`~app.domain.contracts.fact_rule_index.fact_rule_link_id`），作为
不可变性锚点。读取与重建都会复核它，列漂移、``link_id`` 漂移或父实体/父要求不再
可推导即抛 :class:`FactRuleLinkDriftError`，绝不返回漂移对象。

不写回方案规则；不读取 legacy ``clinical_facts`` 占位表。
"""
from __future__ import annotations

from typing import Sequence

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.contracts.fact_rule_index import (
    FactRuleLink,
    PublishedRequirement,
    derive_fact_rule_links,
    fact_rule_link_id,
)
from app.domain.contracts.facts import ClinicalFactV2
from app.storage.fact_repositories import ClinicalFactV2Repository
from app.storage.active_facts import current_fact_heads
from app.storage.facts_models import FactRuleLinkV2Record
from app.storage.models import EvidenceRequirementRecord
from app.storage.repositories import (
    RepositoryError,
    _flush_guarded,
    _get_required,
    get_evidence_requirement,
)

__all__ = [
    "FactRuleIndexError",
    "FactRuleLinkDriftError",
    "FactRuleLinkV2Repository",
]


class FactRuleIndexError(RepositoryError):
    """规则索引领域错误：无已发布事实/跨规则集修订/漂移等，拒绝重建或读取。"""


class FactRuleLinkDriftError(FactRuleIndexError):
    """链接行漂移：父列自洽、``link_id`` 内容哈希或父实体/父要求不再可推导。"""


class FactRuleLinkV2Repository:
    """事实到已发布 RuleComponent/EvidenceRequirement 的确定性双向索引。"""

    def __init__(self, session: Session) -> None:
        self.session = session
        self._facts = ClinicalFactV2Repository(session)

    # ------------------------------------------------------------------ 推导

    def _published_requirements(
        self, rule_set_id: str, rule_set_revision: int
    ) -> list[PublishedRequirement]:
        """已发布资料要求的最小身份；一次装载该规则集修订，先解码验真再投影。"""
        rows = self.session.execute(
            select(EvidenceRequirementRecord).where(
                EvidenceRequirementRecord.rule_set_id == rule_set_id,
                EvidenceRequirementRecord.rule_set_revision == rule_set_revision,
            )
        ).scalars().all()
        contracts = [
            get_evidence_requirement(
                self.session,
                row.rule_set_id,
                row.rule_set_revision,
                row.requirement_id,
            )
            for row in rows
        ]
        return [
            PublishedRequirement(
                requirement_id=requirement.requirement_id,
                rule_component_id=requirement.rule_component_id,
                fact_type=requirement.fact_type,
            )
            for requirement in contracts
        ]

    def derive_links(
        self,
        facts: Sequence[ClinicalFactV2],
        *,
        rule_set_id: str,
        rule_set_revision: int,
    ) -> list[FactRuleLink]:
        """基于已发布事实与已发布资料要求做确定性推导（无模糊匹配）。"""
        requirements = self._published_requirements(rule_set_id, rule_set_revision)
        return derive_fact_rule_links(
            facts,
            requirements,
            rule_set_id=rule_set_id,
            rule_set_revision=rule_set_revision,
        )

    # ------------------------------------------------------------ 漂移校验

    def _decode_row(self, row: FactRuleLinkV2Record) -> FactRuleLink:
        """父列自洽 + ``link_id`` 内容哈希复核；任何漂移拒绝还原。"""
        try:
            contract = FactRuleLink(
                link_id=row.link_id,
                fact_id=row.fact_id,
                target_kind=row.target_kind,
                rule_set_id=row.rule_set_id,
                rule_set_revision=row.rule_set_revision,
                target_id=row.target_id,
                rule_component_id=row.rule_component_id,
                evidence_requirement_id=row.evidence_requirement_id,
            )
        except (ValidationError, ValueError) as exc:
            raise FactRuleLinkDriftError(
                f"链接 {row.link_id} 父列自洽校验失败（列漂移），拒绝还原合同"
            ) from exc
        expected_id = fact_rule_link_id(
            fact_id=row.fact_id,
            target_kind=row.target_kind,
            rule_set_id=row.rule_set_id,
            rule_set_revision=row.rule_set_revision,
            target_id=row.target_id,
        )
        if contract.link_id != expected_id:
            raise FactRuleLinkDriftError(
                f"链接 {row.link_id} 的 link_id 与身份字段内容哈希不一致"
                "（payload 漂移），拒绝还原合同"
            )
        return contract

    def _assert_link_parent(self, row: FactRuleLinkV2Record) -> None:
        """父实体/父要求可推导：事实存在、规则集修订一致、可由精确身份推导。"""
        try:
            fact = self._facts.get(row.fact_id)
        except RepositoryError as exc:
            raise FactRuleLinkDriftError(
                f"链接 {row.link_id} 的父事实 {row.fact_id} 不存在，拒绝还原"
            ) from exc
        if (fact.authority.rule_set_id, fact.authority.rule_set_revision) != (
            row.rule_set_id,
            row.rule_set_revision,
        ):
            raise FactRuleLinkDriftError(
                f"链接 {row.link_id} 的规则集修订与父事实权威元组不一致"
                "（跨修订链接），拒绝还原"
            )
        derived = self.derive_links(
            [fact],
            rule_set_id=row.rule_set_id,
            rule_set_revision=row.rule_set_revision,
        )
        if row.link_id not in {link.link_id for link in derived}:
            raise FactRuleLinkDriftError(
                f"链接 {row.link_id} 不再由已发布事实类型与资料要求推导"
                "（父链接漂移），拒绝还原"
            )

    def _checked_contract(self, row: FactRuleLinkV2Record) -> FactRuleLink:
        """完整读取校验：父列自洽 + ``link_id`` 内容哈希 + 父实体/父要求可推导。"""
        contract = self._decode_row(row)
        self._assert_link_parent(row)
        return contract

    # ------------------------------------------------------------ 读取查询

    def _all_checked(self) -> list[FactRuleLink]:
        rows = self.session.execute(select(FactRuleLinkV2Record)).scalars().all()
        return [self._checked_contract(row) for row in rows]

    def get(self, link_id: str) -> FactRuleLink:
        row = _get_required(self.session, FactRuleLinkV2Record, link_id, "FactRuleLinkV2")
        return self._checked_contract(row)

    def list_for_fact(self, fact_id: str) -> list[FactRuleLink]:
        """事实 -> 全部 RuleComponent/EvidenceRequirement 链接（双向索引之一）。"""
        return self.list_for_facts([fact_id]).get(fact_id, [])

    def list_for_facts(
        self,
        fact_ids: Sequence[str],
        *,
        facts: Sequence[ClinicalFactV2] | None = None,
    ) -> dict[str, list[FactRuleLink]]:
        """批量读取请求事实的规则链接：一次取链接行，批量还原事实，按规则集修订
        一次装载资料要求并推导期望链接，再逐行对照持久化行。

        不走 ``_all_checked`` / 逐链接 ``_assert_link_parent``。``get`` 与重建
        仍使用 ``_checked_contract``。
        """
        wanted = list(dict.fromkeys(fact_ids))
        grouped: dict[str, list[FactRuleLink]] = {fact_id: [] for fact_id in wanted}
        if not wanted:
            return grouped
        rows = self.session.execute(
            select(FactRuleLinkV2Record)
            .where(FactRuleLinkV2Record.fact_id.in_(wanted))
            .order_by(
                FactRuleLinkV2Record.fact_id,
                FactRuleLinkV2Record.target_kind,
                FactRuleLinkV2Record.target_id,
            )
        ).scalars().all()
        if not rows:
            return grouped

        provided = {fact.fact_id: fact for fact in facts or ()}
        needed_fact_ids = sorted({row.fact_id for row in rows})
        missing_ids = [fact_id for fact_id in needed_fact_ids if fact_id not in provided]
        loaded = self._facts.get_many(missing_ids) if missing_ids else {}
        facts_by_id = {**provided, **loaded}
        absent = [fact_id for fact_id in needed_fact_ids if fact_id not in facts_by_id]
        if absent:
            raise FactRuleLinkDriftError(
                f"链接的父事实 {absent} 不存在，拒绝还原"
            )

        facts_by_revision: dict[tuple[str, int], list[ClinicalFactV2]] = {}
        for fact_id in needed_fact_ids:
            fact = facts_by_id[fact_id]
            key = (fact.authority.rule_set_id, fact.authority.rule_set_revision)
            facts_by_revision.setdefault(key, []).append(fact)
        derived_ids: dict[tuple[str, int], set[str]] = {}
        for (rule_set_id, rule_set_revision), group in facts_by_revision.items():
            derived = self.derive_links(
                group,
                rule_set_id=rule_set_id,
                rule_set_revision=rule_set_revision,
            )
            derived_ids[(rule_set_id, rule_set_revision)] = {
                link.link_id for link in derived
            }

        for row in rows:
            contract = self._decode_row(row)
            fact = facts_by_id[row.fact_id]
            key = (fact.authority.rule_set_id, fact.authority.rule_set_revision)
            if key != (row.rule_set_id, row.rule_set_revision):
                raise FactRuleLinkDriftError(
                    f"链接 {row.link_id} 的规则集修订与父事实权威元组不一致"
                    "（跨修订链接），拒绝还原"
                )
            if contract.link_id not in derived_ids[key]:
                raise FactRuleLinkDriftError(
                    f"链接 {row.link_id} 不再由已发布事实类型与资料要求推导"
                    "（父链接漂移），拒绝还原"
                )
            grouped[row.fact_id].append(contract)
        for fact_id, links in grouped.items():
            grouped[fact_id] = sorted(
                links, key=lambda item: (item.target_kind, item.target_id)
            )
        return grouped

    def list_for_rule_set(
        self, rule_set_id: str, rule_set_revision: int
    ) -> list[FactRuleLink]:
        """规则集修订内的全部链接，稳定排序。"""
        return sorted(
            (
                link
                for link in self._all_checked()
                if link.rule_set_id == rule_set_id
                and link.rule_set_revision == rule_set_revision
            ),
            key=lambda link: (link.fact_id, link.target_kind, link.target_id),
        )

    def list_facts_for_requirement(
        self, rule_set_id: str, rule_set_revision: int, requirement_id: str
    ) -> list[FactRuleLink]:
        """资料要求 -> 覆盖它的事实链接（双向索引的另一方向）。"""
        return sorted(
            (
                link
                for link in self._all_checked()
                if link.rule_set_id == rule_set_id
                and link.rule_set_revision == rule_set_revision
                and link.target_kind == "evidence_requirement"
                and link.target_id == requirement_id
            ),
            key=lambda link: link.fact_id,
        )

    def list_facts_for_component(
        self, rule_set_id: str, rule_set_revision: int, rule_component_id: str
    ) -> list[FactRuleLink]:
        """RuleComponent -> 覆盖它的事实链接。"""
        return sorted(
            (
                link
                for link in self._all_checked()
                if link.rule_set_id == rule_set_id
                and link.rule_set_revision == rule_set_revision
                and link.target_kind == "rule_component"
                and link.target_id == rule_component_id
            ),
            key=lambda link: link.fact_id,
        )

    # ------------------------------------------------------------ 重建

    def rebuild_for_authority(
        self, authority, *, run_id: str | None = None
    ) -> list[FactRuleLink]:
        """按当前权威元组的活动修订链头重建可重建索引。

        被人工修订替代的事实仍作为不可变历史保留，但其规则索引行在漂移校验后
        从活动索引中删除，避免后续影响范围把旧链接当成当前闭包。
        run_id兼容已有调用，仅描述触发批次，不缩小整个权威范围的重建集合。
        """
        facts = [
            fact
            for fact in self._facts.list_by_episode(authority.review_episode_id)
            if fact.authority == authority
        ]
        active = current_fact_heads(self.session, authority, facts=facts)
        stale_ids = {fact.fact_id for fact in facts} - {fact.fact_id for fact in active}
        return self._rebuild_facts(
            active,
            scope_label=f"权威元组 {authority.review_episode_id} r{authority.episode_revision}",
            stale_fact_ids=stale_ids,
        )

    def rebuild_for_episode(self, review_episode_id: str) -> list[FactRuleLink]:
        """兼容性入口：仅当审核节点事实共享一个权威元组时重建。"""
        facts = self._facts.list_by_episode(review_episode_id)
        authorities = {fact.authority.model_dump_json() for fact in facts}
        if len(authorities) > 1:
            raise FactRuleIndexError(
                f"审核节点 {review_episode_id} 的事实跨多个不可变权威元组，"
                "请按权威元组重建索引"
            )
        return self._rebuild_facts(facts, scope_label=f"审核节点 {review_episode_id}")

    def _rebuild_facts(
        self,
        facts: Sequence[ClinicalFactV2],
        *,
        scope_label: str,
        stale_fact_ids: set[str] | None = None,
    ) -> list[FactRuleLink]:
        """按给定已发布事实重建规则索引；幂等、确定性排序、漂移整批拒绝。

        流程：

        1. 读当前审核节点全部已发布事实；它们必须共享同一规则集修订；
        2. 由已发布事实与已发布资料要求确定性推导目标链接集合；
        3. 对每个既有行先做完整校验（父列自洽 + ``link_id`` 内容哈希 + 父实体/
           父要求可推导）；任何漂移整批抛 :class:`FactRuleLinkDriftError`，
           不删除任何行；
        4. 校验全部通过后再删除不在派生集合中的陈旧行、插入缺失行（保持确定性
           顺序）；二次重建无差异即无操作。

        索引只读已发布事实/资料要求，不写回方案规则。
        """
        stale_fact_ids = set(stale_fact_ids or ())
        identities = {
            (fact.authority.rule_set_id, fact.authority.rule_set_revision)
            for fact in facts
        }
        if not identities:
            if not stale_fact_ids:
                raise FactRuleIndexError(
                    f"{scope_label} 没有已发布事实，无索引可重建"
                )
            all_existing = self.session.execute(select(FactRuleLinkV2Record)).scalars().all()
            for row in all_existing:
                self._checked_contract(row)
                if row.fact_id in stale_fact_ids:
                    self.session.delete(row)
            _flush_guarded(self.session)
            return []
        if len(identities) > 1:
            raise FactRuleIndexError(
                f"{scope_label} 的事实跨多个规则集修订，拒绝重建索引"
            )
        rule_set_id, rule_set_revision = next(iter(identities))
        derived = self.derive_links(
            facts, rule_set_id=rule_set_id, rule_set_revision=rule_set_revision
        )
        derived_by_id = {link.link_id: link for link in derived}
        fact_ids = {fact.fact_id for fact in facts}
        all_existing = self.session.execute(select(FactRuleLinkV2Record)).scalars().all()
        checked_existing = [(row, self._checked_contract(row)) for row in all_existing]
        existing = [row for row, link in checked_existing if link.fact_id in fact_ids]

        # 先校验每个既有行，任何漂移整批拒绝（绝不先删后验）。
        for row in existing:
            if row.link_id not in derived_by_id:
                raise FactRuleLinkDriftError(
                    f"链接 {row.link_id} 不再由已发布事实类型与资料要求推导"
                    "（父链接漂移），拒绝重建索引"
                )

        existing_by_id = {row.link_id: row for row in existing}
        missing = [
            link for link in derived if link.link_id not in existing_by_id
        ]
        for link in missing:
            self.session.add(
                FactRuleLinkV2Record(
                    link_id=link.link_id,
                    fact_id=link.fact_id,
                    target_kind=link.target_kind,
                    rule_set_id=link.rule_set_id,
                    rule_set_revision=link.rule_set_revision,
                    target_id=link.target_id,
                    rule_component_id=link.rule_component_id,
                    evidence_requirement_id=link.evidence_requirement_id,
                )
            )
        if stale_fact_ids:
            for row, link in checked_existing:
                if link.fact_id in stale_fact_ids:
                    self.session.delete(row)
        _flush_guarded(self.session)
        return derived
