"""Phase 5 EvidenceExpectation v2 仓储（Slice 5.4，worker_03）。

在 ``facts_models.EvidenceExpectationV2Record`` 之上提供追加写/读取的确定性仓储，
并在持久化边界强制（与 ``fact_repositories`` 同一套权威边界）：

- 写入前调用 :class:`~app.storage.fact_authority.FactAuthorityValidator` 复核不可变
  权威元组与定位闭包（活动快照/完整处理修订指针变化即拒绝，绝不写陈旧投影）；
- 模板必须属于权威元组的规则集修订（当前审核节点绑定）；
- 覆盖事实必须是同权威元组、精确 ``fact_type`` 的已发布事实，且期望定位必须正好
  等于其覆盖事实定位闭包（定位只有一个真相源，链接表与 payload 双向镜像）；
- ``(review_episode_id, template_id, revision)`` 追加写：同内容重复投影幂等返回
  最新行；内容/权威变化时只允许追加链头 +1，回退/跳号一律拒绝，绝不覆盖旧投影
  （旧权威元组可回放）；
- 读取用 :func:`decode_contract` 还原并经镜像交叉核对（列 ↔ payload ↔ 定位链接表），
  任何不一致抛 :class:`PersistedContractInvalid`，绝不返回空对象。

旧 ``evidence_expectations`` 占位表保持只读回归锚点，本模块不读取、不写入 legacy 表。
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.contracts.evidence import EvidenceExpectationTemplate
from app.domain.contracts.evidence_expectations_v2 import EvidenceExpectationV2
from app.domain.contracts.facts import FactAuthority
from app.storage.codecs import (
    PersistedContractInvalid,
    decode_contract,
    encode_contract,
    mirror_values_equal,
    parse_datetime_column,
    to_utc_naive,
)
from app.storage.fact_authority import FactAuthorityValidator
from app.storage.fact_repositories import (
    ClinicalFactV2Repository,
    FactRevisionChainError,
    Phase5RepositoryError,
    authority_column_filters,
    prefetch_locator_link_ids,
)
from app.storage.facts_models import (
    EvidenceExpectationV2Record,
    FactEvidenceLocatorLinkRecord,
)
from app.storage.repositories import (
    _flush_guarded,
    _get_required,
    get_expectation_template,
)

__all__ = ["EvidenceExpectationV2Repository"]


def _authority_columns(authority: FactAuthority) -> dict[str, Any]:
    return {
        "project_id": authority.project_id,
        "subject_id": authority.subject_id,
        "review_episode_id": authority.review_episode_id,
        "episode_revision": authority.episode_revision,
        "protocol_version_id": authority.protocol_version_id,
        "rule_set_id": authority.rule_set_id,
        "rule_set_revision": authority.rule_set_revision,
        "evidence_snapshot_v2_id": authority.evidence_snapshot_v2_id,
        "complete_processing_revision_id": authority.complete_processing_revision_id,
    }


def _payload_path_opt(payload: dict, path: str) -> Any:
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, dict) or current.get(part) is None:
            return None
        current = current[part]
    return current


def _check_tolerant_mirrors(
    entity_name: str, record: Any, payload: dict, mirrors: dict[str, str]
) -> None:
    """镜像交叉核对（容忍可空嵌套：payload 路径缺失/为 None 时要求列也为 None）。"""
    for column_attr, payload_path in mirrors.items():
        column_value = getattr(record, column_attr)
        payload_value = _payload_path_opt(payload, payload_path)
        if isinstance(column_value, datetime) and isinstance(payload_value, str):
            try:
                parsed_payload = parse_datetime_column(payload_value)
            except ValueError:
                parsed_payload = payload_value
            equal = to_utc_naive(column_value) == parsed_payload
        else:
            equal = mirror_values_equal(column_value, payload_value)
        if not equal:
            raise PersistedContractInvalid(
                f"{entity_name} 列 {column_attr} 与已验证 payload 不一致，拒绝还原合同"
            )


def _coverage_content(expectation: EvidenceExpectationV2) -> tuple:
    """期望的语义内容（幂等比较用；不含 expectation_id/revision/created_at）。

    输入信号 provenance（``input_gap_signals``）属于语义内容：可见状态相同但
    输入来源变化（历史 None ↔ 明确无信号/具体信号清单）时必须追加新 revision，
    绝不静默复用旧行；None 与 [] 语义不同（来源未知 ≠ 确认无信号）。
    """
    input_provenance = expectation.input_gap_signals
    return (
        expectation.authority,
        expectation.status,
        expectation.gap_type,
        tuple(expectation.coverage_fact_ids),
        tuple(expectation.locator_ids),
        expectation.source_coverage,
        expectation.provenance_followup,
        expectation.provenance_reason,
        expectation.gap_detail,
        None
        if input_provenance is None
        else tuple(
            json.dumps(signal.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
            for signal in input_provenance
        ),
    )


class EvidenceExpectationV2Repository:
    """受试者级期望覆盖投影仓储：权威复核 + 模板绑定 + 覆盖闭包 + revision 追加。"""

    def __init__(self, session: Session) -> None:
        self.session = session
        self._authority = FactAuthorityValidator(session)

    # ------------------------------------------------------------------ 写入

    def project(self, expectation: EvidenceExpectationV2) -> EvidenceExpectationV2:
        """投影一条期望；同内容幂等返回最新行，变化时只允许追加链头 +1。"""
        if expectation.source_revision_of is not None:
            from app.storage.source_reference_successors import validate_source_fact_references
            prior = self.get(expectation.source_revision_of)
            mutable = {
                "expectation_id", "source_revision_of", "revision", "created_at",
                "coverage_fact_ids", "locator_ids",
            }
            if (
                expectation.model_dump(exclude=mutable) != prior.model_dump(exclude=mutable)
                or expectation.revision != prior.revision + 1
            ):
                raise Phase5RepositoryError("来源衔接不得改变原资料要求状态或缺口")
            validate_source_fact_references(
                self.session, expectation.authority,
                prior.coverage_fact_ids, expectation.coverage_fact_ids,
            )
        self._authority.validate(expectation.authority)
        self._authority.validate_locators(
            expectation.authority, expectation.locator_ids
        )
        template = self._require_bound_template(expectation)
        self._require_coverage_facts(expectation, template)
        self._require_locators_within_coverage(expectation)

        latest = self._latest_record(
            expectation.authority.review_episode_id, expectation.template_id
        )
        if latest is not None:
            latest_contract = self._decode_record(latest)
            if _coverage_content(latest_contract) == _coverage_content(expectation):
                return latest_contract
            if expectation.revision != latest_contract.revision + 1:
                raise FactRevisionChainError(
                    f"期望 {expectation.expectation_id} 的 revision 必须是当前链头 "
                    f"{latest_contract.revision} + 1（得到 {expectation.revision}），"
                    "回退/跳号一律拒绝"
                )
        elif expectation.revision != 1:
            raise FactRevisionChainError(
                f"期望 {expectation.expectation_id} 的首个 revision 必须为 1"
            )

        payload_json, payload_sha256 = encode_contract(expectation)
        row = EvidenceExpectationV2Record(
            expectation_id=expectation.expectation_id,
            template_id=expectation.template_id,
            status=expectation.status.value,
            gap_type=expectation.gap_type.value if expectation.gap_type else None,
            revision=expectation.revision,
            created_at=to_utc_naive(expectation.created_at),
            payload_json=payload_json,
            payload_sha256=payload_sha256,
            **_authority_columns(expectation.authority),
        )
        self.session.add(row)
        _flush_guarded(self.session)
        self._write_locator_links(
            "expectation", expectation.expectation_id, expectation.locator_ids
        )
        return expectation

    def _require_bound_template(
        self, expectation: EvidenceExpectationV2
    ) -> EvidenceExpectationTemplate:
        template = get_expectation_template(self.session, expectation.template_id)
        if (
            template.rule_set_id != expectation.authority.rule_set_id
            or template.rule_set_revision != expectation.authority.rule_set_revision
        ):
            raise Phase5RepositoryError(
                f"期望模板 {expectation.template_id} 不属于权威元组的规则集修订 "
                f"({expectation.authority.rule_set_id} "
                f"r{expectation.authority.rule_set_revision})，拒绝投影"
            )
        return template

    def _require_coverage_facts(
        self, expectation: EvidenceExpectationV2, template: EvidenceExpectationTemplate
    ) -> None:
        """覆盖事实必须同权威元组并明确绑定模板资料要求。"""
        repository = ClinicalFactV2Repository(self.session)
        for fact_id in sorted(set(expectation.coverage_fact_ids)):
            fact = repository.get(fact_id)
            if fact.authority != expectation.authority:
                raise Phase5RepositoryError(
                    f"覆盖事实 {fact_id} 与期望不属于同一不可变权威元组，拒绝投影"
                )
            if template.requirement_id not in fact.supported_requirement_ids:
                raise Phase5RepositoryError(
                    f"覆盖事实 {fact_id} 未显式绑定模板资料要求 "
                    f"{template.requirement_id}，拒绝投影"
                )

    def _require_locators_within_coverage(
        self, expectation: EvidenceExpectationV2
    ) -> None:
        """期望定位必须正好等于其覆盖事实的定位闭包（定位唯一真相源）。"""
        repository = ClinicalFactV2Repository(self.session)
        closure = sorted(
            {
                locator_id
                for fact_id in expectation.coverage_fact_ids
                for locator_id in repository.get(fact_id).locator_ids
            }
        )
        if expectation.locator_ids != closure:
            raise Phase5RepositoryError(
                f"期望 {expectation.expectation_id} 定位与覆盖事实定位闭包不一致"
                f"（期望 {expectation.locator_ids}，闭包 {closure}），拒绝投影"
            )

    # ------------------------------------------------------------------ 读取

    def get(self, expectation_id: str) -> EvidenceExpectationV2:
        row = _get_required(
            self.session, EvidenceExpectationV2Record, expectation_id,
            "EvidenceExpectationV2",
        )
        return self._decode_record(row)

    def latest_by_template(
        self, review_episode_id: str, template_id: str
    ) -> EvidenceExpectationV2 | None:
        row = self._latest_record(review_episode_id, template_id)
        return self._decode_record(row) if row is not None else None

    def list_for_authority(self, authority: FactAuthority) -> list[EvidenceExpectationV2]:
        rows = self.session.execute(
            select(EvidenceExpectationV2Record).where(
                *authority_column_filters(EvidenceExpectationV2Record, authority)
            )
        ).scalars().all()
        locators = prefetch_locator_link_ids(
            self.session, "expectation", [row.expectation_id for row in rows]
        )
        contracts = [
            self._decode_record(row, locator_ids=locators[row.expectation_id])
            for row in rows
        ]
        return sorted(
            (item for item in contracts if item.authority == authority),
            key=lambda item: (item.created_at, item.expectation_id),
        )

    def list_by_episode(
        self, review_episode_id: str
    ) -> list[EvidenceExpectationV2]:
        rows = self.session.execute(select(EvidenceExpectationV2Record)).scalars().all()
        contracts = [self._decode_record(row) for row in rows]
        return sorted(
            (
                item
                for item in contracts
                if item.authority.review_episode_id == review_episode_id
            ),
            key=lambda item: (item.created_at, item.expectation_id),
        )

    def list_covering_facts(self, fact_ids: Sequence[str]) -> list[EvidenceExpectationV2]:
        """覆盖事实 -> 期望（先解码验真，再按 ``coverage_fact_ids`` 反向过滤）。"""
        wanted = set(fact_ids)
        if not wanted:
            return []
        rows = self.session.execute(select(EvidenceExpectationV2Record)).scalars().all()
        contracts = [self._decode_record(row) for row in rows]
        return sorted(
            (
                item
                for item in contracts
                if wanted.intersection(item.coverage_fact_ids)
            ),
            key=lambda item: (item.created_at, item.expectation_id),
        )

    def _latest_record(
        self, review_episode_id: str, template_id: str
    ) -> EvidenceExpectationV2Record | None:
        rows = self.session.execute(select(EvidenceExpectationV2Record)).scalars().all()
        contracts = [self._decode_record(row) for row in rows]
        matching = [
            contract
            for contract in contracts
            if contract.authority.review_episode_id == review_episode_id
            and contract.template_id == template_id
        ]
        if not matching:
            return None
        head = max(matching, key=lambda contract: contract.revision)
        return self.session.get(EvidenceExpectationV2Record, head.expectation_id)

    def _decode_record(
        self,
        row: EvidenceExpectationV2Record,
        *,
        locator_ids: list[str] | None = None,
    ) -> EvidenceExpectationV2:
        contract = decode_contract(
            EvidenceExpectationV2, row.payload_json, row.payload_sha256
        )
        payload = json.loads(row.payload_json)
        _check_tolerant_mirrors(
            "EvidenceExpectationV2",
            row,
            payload,
            {
                "expectation_id": "expectation_id",
                "template_id": "template_id",
                "status": "status",
                "gap_type": "gap_type",
                "revision": "revision",
                "created_at": "created_at",
                "project_id": "authority.project_id",
                "subject_id": "authority.subject_id",
                "review_episode_id": "authority.review_episode_id",
                "episode_revision": "authority.episode_revision",
                "protocol_version_id": "authority.protocol_version_id",
                "rule_set_id": "authority.rule_set_id",
                "rule_set_revision": "authority.rule_set_revision",
                "evidence_snapshot_v2_id": "authority.evidence_snapshot_v2_id",
                "complete_processing_revision_id": (
                    "authority.complete_processing_revision_id"
                ),
            },
        )
        self._assert_link_mirror(
            "expectation",
            row.expectation_id,
            payload["locator_ids"],
            locator_ids=locator_ids,
        )
        return contract.model_copy(update={"locator_ids": payload["locator_ids"]})

    # ------------------------------------------------------------- 定位链接

    def _write_locator_links(
        self, entity_kind: str, entity_id: str, locator_ids: list[str]
    ) -> None:
        for position, locator_id in enumerate(locator_ids, start=1):
            self.session.add(
                FactEvidenceLocatorLinkRecord(
                    entity_kind=entity_kind,
                    entity_id=entity_id,
                    position=position,
                    locator_id=locator_id,
                    expectation_id=entity_id,
                )
            )
        _flush_guarded(self.session)

    def _locator_ids_for(self, entity_kind: str, entity_id: str) -> list[str]:
        rows = self.session.execute(
            select(FactEvidenceLocatorLinkRecord)
            .where(
                FactEvidenceLocatorLinkRecord.entity_kind == entity_kind,
                FactEvidenceLocatorLinkRecord.entity_id == entity_id,
            )
            .order_by(FactEvidenceLocatorLinkRecord.position)
        ).scalars().all()
        return [row.locator_id for row in rows]

    def _assert_link_mirror(
        self,
        entity_kind: str,
        entity_id: str,
        payload_ids: list[str],
        *,
        locator_ids: list[str] | None = None,
    ) -> None:
        links = (
            list(locator_ids)
            if locator_ids is not None
            else self._locator_ids_for(entity_kind, entity_id)
        )
        if links != payload_ids:
            raise PersistedContractInvalid(
                f"{entity_kind} {entity_id} 定位链接与 payload 定位不一致，拒绝还原合同"
            )
