"""Phase 5 人工临床事实修订仓储（Slice 5.7）。

- 权威与定位闭包在 ``FactAuthorityValidator`` 强制；
- 旧/新两侧实体必须已持久化、``target_kind`` 一致且 ``FactAuthority`` 完全相等；
- 旧/新语义快照经 ``fact_corrections.snapshot_for_kind`` 对实际合约计算并与
  记录的规范 JSON/哈希逐字节校验；
- 分支由 ``UNIQUE(target_id)`` 与 ``UNIQUE(new_entity_id)`` 在 DB 强制，仓储预检给出明确错误；
- 同稳定时新 ``revision == target_revision+1``，异稳定时新身份可从 1 新起（按其自身链头校验）；
- ``idempotency_key`` 全局唯一，重复提交幂等复用；
- 读取经 ``decode_contract`` + 镜像交叉核对，含类型化外键列。
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.contracts.fact_corrections import (
    FactCorrectionV2,
    canonical_json,
    snapshot_for_kind,
    to_beijing_aware as contract_to_beijing_aware,
    to_beijing_naive as contract_to_beijing_naive,
)
from app.domain.contracts.facts import ClinicalEventV2, ClinicalFactV2, FactAuthority, MedicationExposureV2
from app.storage.codecs import PersistedContractInvalid, decode_contract, encode_contract, to_utc_naive
from app.storage.fact_authority import FactAuthorityValidator
from app.storage.fact_repositories import (
    ClinicalEventV2Repository,
    ClinicalFactV2Repository,
    MedicationExposureV2Repository,
    Phase5RepositoryError,
)
from app.storage.facts_models import (
    ClinicalEventV2Record,
    ClinicalFactV2Record,
    FactCorrectionRecord,
    MedicationExposureV2Record,
)
from app.storage.repositories import RepositoryError, _flush_guarded, _get_required

__all__ = ["FactCorrectionRepository", "FactCorrectionRevisionError"]


class FactCorrectionRevisionError(Phase5RepositoryError):
    """修订链、分支或快照校验失败。"""


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


def _decode_record(record: FactCorrectionRecord) -> FactCorrectionV2:
    contract = decode_contract(FactCorrectionV2, record.payload_json, record.payload_sha256)
    canonical_payload_json, canonical_payload_sha256 = encode_contract(contract)
    if record.payload_json != canonical_payload_json or record.payload_sha256 != canonical_payload_sha256:
        raise PersistedContractInvalid(
            f"修订 {contract.correction_id} payload 不是规范 JSON，拒绝还原合同"
        )
    mirrors: dict[str, Any] = {
        "correction_id": contract.correction_id,
        "target_kind": contract.target_kind,
        "target_id": contract.target_id,
        "target_stable_identity": contract.target_stable_identity,
        "new_stable_identity": contract.new_stable_identity,
        "target_revision": contract.target_revision,
        "new_entity_id": contract.new_entity_id,
        "new_revision": contract.new_revision,
        "old_snapshot_json": contract.old_snapshot_json,
        "old_snapshot_sha256": contract.old_snapshot_sha256,
        "new_snapshot_json": contract.new_snapshot_json,
        "new_snapshot_sha256": contract.new_snapshot_sha256,
        "reason": contract.reason,
        "locator_ids_json": contract.locator_ids,
        "operator_id": contract.operator_id,
        "corrected_at": to_utc_naive(contract.corrected_at),
        "impact_scope_kind": contract.impact_scope.scope_kind,
        "impact_fallback_reason": contract.impact_scope.fallback_reason,
        "affected_locator_ids_json": contract.impact_scope.affected_locator_ids,
        "affected_document_ids_json": contract.impact_scope.affected_document_ids,
        "affected_fact_ids_json": contract.impact_scope.affected_fact_ids,
        "affected_event_ids_json": contract.impact_scope.affected_event_ids,
        "affected_exposure_ids_json": contract.impact_scope.affected_exposure_ids,
        "affected_conflict_group_ids_json": contract.impact_scope.affected_conflict_group_ids,
        "affected_rule_link_ids_json": contract.impact_scope.affected_rule_link_ids,
        "affected_expectation_ids_json": contract.impact_scope.affected_expectation_ids,
        "affected_profile_revision_ids_json": contract.impact_scope.affected_profile_revision_ids,
        "impact_scope_json": contract.impact_scope.model_dump(mode="json"),
        "idempotency_key": contract.idempotency_key,
        "target_fact_id": contract.target_id if contract.target_kind == "fact" else None,
        "target_event_id": contract.target_id if contract.target_kind == "event" else None,
        "target_exposure_id": contract.target_id if contract.target_kind == "exposure" else None,
        "new_fact_id": contract.new_entity_id if contract.target_kind == "fact" else None,
        "new_event_id": contract.new_entity_id if contract.target_kind == "event" else None,
        "new_exposure_id": contract.new_entity_id if contract.target_kind == "exposure" else None,
    }
    for col, value in _authority_columns(contract.authority).items():
        if getattr(record, col) != value:
            raise PersistedContractInvalid(f"修订 {contract.correction_id} 权威列 {col} 与 payload 不一致")
    for col, expected in mirrors.items():
        actual = getattr(record, col)
        if actual != expected:
            raise PersistedContractInvalid(f"修订 {contract.correction_id} 列 {col} 与 payload 不一致")
    if record.created_at != to_utc_naive(contract.created_at):
        raise PersistedContractInvalid(f"修订 {contract.correction_id} created_at 与 payload 不一致")
    return contract


def _to_beijing_naive(corrected_at: datetime) -> datetime:
    return contract_to_beijing_naive(corrected_at)


class FactCorrectionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session
        self._authority = FactAuthorityValidator(session)

    def create(self, contract: FactCorrectionV2) -> FactCorrectionV2:
        existing = self.session.execute(
            select(FactCorrectionRecord).where(FactCorrectionRecord.idempotency_key == contract.idempotency_key)
        ).scalars().first()
        if existing is not None:
            # A retry may arrive after the active pointer has advanced.  The
            # immutable idempotency key is the durable completion proof, so
            # replay it before re-validating the now-stale authority.
            decoded_existing = _decode_record(existing)
            # correction_id is a caller label; every other persisted field
            # must still match before an idempotent replay is accepted.
            same_idempotent_payload = decoded_existing.model_copy(
                update={"correction_id": contract.correction_id}
            )
            if same_idempotent_payload != contract:
                raise FactCorrectionRevisionError(
                    f"幂等键 {contract.idempotency_key} 已存在且内容不一致，拒绝隐藏的调用方损坏"
                )
            return decoded_existing

        by_id = self.session.execute(
            select(FactCorrectionRecord).where(FactCorrectionRecord.correction_id == contract.correction_id)
        ).scalars().first()
        if by_id is not None:
            decoded_by_id = _decode_record(by_id)
            if decoded_by_id == contract:
                return decoded_by_id
            raise FactCorrectionRevisionError(f"correction_id {contract.correction_id} 已存在且内容不一致，拒绝隐藏的调用方损坏")

        self._authority.validate(contract.authority)
        self._authority.validate_locators(contract.authority, contract.locator_ids)
        self._authority.validate_locators(
            contract.authority,
            contract.impact_scope.affected_locator_ids,
        )

        # 分支检查：单出边/单入边
        outgoing = self.session.execute(
            select(FactCorrectionRecord).where(FactCorrectionRecord.target_id == contract.target_id)
        ).scalars().first()
        if outgoing is not None:
            raise FactCorrectionRevisionError(f"目标 {contract.target_id} 已有修订，禁止分支")

        incoming = self.session.execute(
            select(FactCorrectionRecord).where(FactCorrectionRecord.new_entity_id == contract.new_entity_id)
        ).scalars().first()
        if incoming is not None:
            raise FactCorrectionRevisionError(f"新实体 {contract.new_entity_id} 已被其他修订指向，禁止汇聚分支")

        # 旧/新实体必须已存在且同 kind/同权威，快照必须匹配
        old_entity = self._get_entity(contract.target_kind, contract.target_id)
        new_entity = self._get_entity(contract.target_kind, contract.new_entity_id)

        if old_entity.authority != contract.authority or new_entity.authority != contract.authority:
            raise RepositoryError("修订目标与新实体必须与修订同属同一不可变权威元组")

        if old_entity.stable_identity != contract.target_stable_identity:
            raise RepositoryError("目标稳定身份与实际持久化合约不一致")
        if new_entity.stable_identity != contract.new_stable_identity:
            raise RepositoryError("新实体稳定身份与修订记录不一致")

        if old_entity.revision != contract.target_revision:
            raise RepositoryError("目标 revision 与实际持久化合约不一致")
        if new_entity.revision != contract.new_revision:
            raise RepositoryError("新实体 revision 与修订记录不一致")
        # 已发布实体仓库已保证每个实体的 contiguous 校验；此处仅验证 lineage 不陈旧且新为头
        self._require_chain_head_for_entity(contract.target_kind, contract.new_stable_identity, contract.new_revision)
        if contract.target_stable_identity == contract.new_stable_identity:
            if contract.new_revision != contract.target_revision + 1:
                raise FactCorrectionRevisionError("同稳定身份时新 revision 必须为目标 revision + 1")
            self._require_chain_head_for_entity(contract.target_kind, contract.target_stable_identity, contract.target_revision, allow_head_minus_one=True)
        else:
            self._require_chain_head_for_entity(contract.target_kind, contract.target_stable_identity, contract.target_revision)

        # 快照校验：对实际持久化合约做语义快照并比对
        old_snapshot = snapshot_for_kind(contract.target_kind, old_entity)
        new_snapshot = snapshot_for_kind(contract.target_kind, new_entity)
        old_json = canonical_json(old_snapshot)
        new_json = canonical_json(new_snapshot)
        if old_json != contract.old_snapshot_json:
            raise RepositoryError("旧快照 JSON 与实际持久化合约语义不一致")
        if new_json != contract.new_snapshot_json:
            raise RepositoryError("新快照 JSON 与实际持久化合约语义不一致")
        if contract.old_snapshot_sha256 != _snapshot_sha(old_json):
            raise RepositoryError("旧快照哈希与快照 JSON 不一致")
        if contract.new_snapshot_sha256 != _snapshot_sha(new_json):
            raise RepositoryError("新快照哈希与快照 JSON 不一致")

        payload_json, payload_sha256 = encode_contract(contract)

        # 类型化外键列
        target_fact_id = contract.target_id if contract.target_kind == "fact" else None
        target_event_id = contract.target_id if contract.target_kind == "event" else None
        target_exposure_id = contract.target_id if contract.target_kind == "exposure" else None
        new_fact_id = contract.new_entity_id if contract.target_kind == "fact" else None
        new_event_id = contract.new_entity_id if contract.target_kind == "event" else None
        new_exposure_id = contract.new_entity_id if contract.target_kind == "exposure" else None

        record = FactCorrectionRecord(
            correction_id=contract.correction_id,
            target_kind=contract.target_kind,
            target_id=contract.target_id,
            target_stable_identity=contract.target_stable_identity,
            new_stable_identity=contract.new_stable_identity,
            target_revision=contract.target_revision,
            new_entity_id=contract.new_entity_id,
            new_revision=contract.new_revision,
            target_fact_id=target_fact_id,
            target_event_id=target_event_id,
            target_exposure_id=target_exposure_id,
            new_fact_id=new_fact_id,
            new_event_id=new_event_id,
            new_exposure_id=new_exposure_id,
            old_snapshot_json=contract.old_snapshot_json,
            old_snapshot_sha256=contract.old_snapshot_sha256,
            new_snapshot_json=contract.new_snapshot_json,
            new_snapshot_sha256=contract.new_snapshot_sha256,
            reason=contract.reason,
            locator_ids_json=contract.locator_ids,
            operator_id=contract.operator_id,
            corrected_at=to_utc_naive(contract.corrected_at),
            impact_scope_kind=contract.impact_scope.scope_kind,
            impact_fallback_reason=contract.impact_scope.fallback_reason,
            affected_locator_ids_json=contract.impact_scope.affected_locator_ids,
            affected_document_ids_json=contract.impact_scope.affected_document_ids,
            affected_fact_ids_json=contract.impact_scope.affected_fact_ids,
            affected_event_ids_json=contract.impact_scope.affected_event_ids,
            affected_exposure_ids_json=contract.impact_scope.affected_exposure_ids,
            affected_conflict_group_ids_json=contract.impact_scope.affected_conflict_group_ids,
            affected_rule_link_ids_json=contract.impact_scope.affected_rule_link_ids,
            affected_expectation_ids_json=contract.impact_scope.affected_expectation_ids,
            affected_profile_revision_ids_json=contract.impact_scope.affected_profile_revision_ids,
            impact_scope_json=contract.impact_scope.model_dump(mode="json"),
            idempotency_key=contract.idempotency_key,
            payload_json=payload_json,
            payload_sha256=payload_sha256,
            created_at=to_utc_naive(contract.created_at),
            **_authority_columns(contract.authority),
        )
        self.session.add(record)
        _flush_guarded(self.session)
        return _decode_record(record)

    def _get_entity(self, kind: str, entity_id: str) -> ClinicalFactV2 | ClinicalEventV2 | MedicationExposureV2:
        return self._entity_repository(kind).get(entity_id)

    def _entity_repository(self, kind: str) -> Any:
        if kind == "fact":
            return ClinicalFactV2Repository(self.session)
        if kind == "event":
            return ClinicalEventV2Repository(self.session)
        if kind == "exposure":
            return MedicationExposureV2Repository(self.session)
        raise RepositoryError(f"不支持的修订目标类型 {kind}")

    def _require_chain_head_for_entity(self, kind: str, stable_identity: str, revision: int, allow_head_minus_one: bool = False) -> None:
        # 查询该稳定身份下所有 revision，判断给定 revision 是否为链头（或头-1）
        repository = self._entity_repository(kind)
        cls = {
            "fact": ClinicalFactV2Record,
            "event": ClinicalEventV2Record,
            "exposure": MedicationExposureV2Record,
        }[kind]
        rows = self.session.execute(select(cls)).scalars().all()
        revs: list[int] = []
        for row in rows:
            contract = repository._decode_record(row)
            if contract.stable_identity == stable_identity:
                revs.append(contract.revision)
        if not revs:
            if revision != 1:
                raise FactCorrectionRevisionError(f"稳定身份 {stable_identity} 首次 revision 必须为 1")
            return
        head = max(revs)
        if revision == head:
            return
        if allow_head_minus_one and revision == head - 1:
            return
        raise FactCorrectionRevisionError(f"稳定身份 {stable_identity} 当前链头 {head}，给定 revision {revision} 非法")

    def get(self, correction_id: str) -> FactCorrectionV2:
        record = _get_required(self.session, FactCorrectionRecord, correction_id, "人工事实修订")
        return _decode_record(record)

    def get_by_idempotency_key(self, idempotency_key: str) -> FactCorrectionV2 | None:
        record = self.session.execute(
            select(FactCorrectionRecord).where(FactCorrectionRecord.idempotency_key == idempotency_key)
        ).scalars().first()
        if record is None:
            return None
        return _decode_record(record)

    def list_by_authority(self, authority: FactAuthority) -> list[FactCorrectionV2]:
        rows = self.session.execute(select(FactCorrectionRecord)).scalars().all()
        contracts = [_decode_record(row) for row in rows]
        filtered = [c for c in contracts if c.authority == authority]
        return sorted(filtered, key=lambda c: (c.created_at, c.correction_id))

    def list_by_review_episode(self, review_episode_id: str) -> list[FactCorrectionV2]:
        """读取审核节点全部不可变历史，不受当前活动权威指针变化影响。"""
        rows = self.session.execute(select(FactCorrectionRecord)).scalars().all()
        contracts = [_decode_record(row) for row in rows]
        filtered = [
            item
            for item in contracts
            if item.authority.review_episode_id == review_episode_id
        ]
        return sorted(filtered, key=lambda item: (item.created_at, item.correction_id))

    def superseded_entity_ids(self, authority: FactAuthority) -> set[str]:
        return {item.target_id for item in self.list_by_authority(authority)}

    def outgoing(self, target_id: str) -> FactCorrectionV2 | None:
        row = self.session.execute(
            select(FactCorrectionRecord).where(FactCorrectionRecord.target_id == target_id)
        ).scalars().first()
        if row is None:
            return None
        return _decode_record(row)

    def list_by_target(self, target_stable_identity: str) -> list[FactCorrectionV2]:
        rows = self.session.execute(
            select(FactCorrectionRecord).where(FactCorrectionRecord.target_stable_identity == target_stable_identity)
        ).scalars().all()
        contracts = [_decode_record(row) for row in rows]
        return sorted(contracts, key=lambda c: (c.created_at, c.correction_id))

    def list_all(self) -> list[FactCorrectionV2]:
        rows = self.session.execute(select(FactCorrectionRecord)).scalars().all()
        contracts = [_decode_record(row) for row in rows]
        return sorted(contracts, key=lambda c: (c.created_at, c.correction_id))

    @staticmethod
    def to_beijing_naive(corrected_at: datetime) -> datetime:
        return _to_beijing_naive(corrected_at)

    @staticmethod
    def to_beijing_aware(corrected_at: datetime) -> datetime:
        return contract_to_beijing_aware(corrected_at)


def _snapshot_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
