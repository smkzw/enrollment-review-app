"""Phase 5 不可变 Patient Profile revision 仓储（Slice 5.5，worker_02）。

在 ``facts_models.PatientProfileRevisionV2Record`` 之上提供追加写/读取的确定性仓储，
并在持久化边界强制（与 ``fact_repositories`` / ``evidence_expectation_repository``
同一套权威边界）：

- 写入前调用 :class:`~app.storage.fact_authority.FactAuthorityValidator` 复核不可变
  权威元组（活动快照/完整处理修订指针变化即拒绝，绝不写陈旧投影）；
- ``(review_episode_id, revision)`` 追加写：同内容确定性投影幂等返回最新行；内容/
  权威变化时只允许追加链头 +1，回退/跳号一律拒绝，绝不覆盖旧 revision（旧权威元组
  可回放，后期资料不静默改写早期节点 Profile）；
- 读取用 :func:`decode_contract` 还原并经镜像交叉核对（列 ↔ payload ↔ 权威元组），
  任何不一致抛 :class:`PersistedContractInvalid`，绝不返回空对象；
- 列表与链头查询先解码表中每条不可变 payload（``_decode_record`` 内部交叉核对镜像
  列）再按审核节点过滤，可能漂移的镜像列不能把坏行静默隐藏；
- ``succeeded`` 必须携带完整确定性投影，``generating`` / ``failed`` 是显式状态记录；
  ``stale`` 是服务层对照当前审核节点权威读取时派生的状态，本仓储 ``create`` 拒绝
  持久化 ``stale``。

旧 ``patient_profiles`` 占位表保持只读回归锚点，本模块不读取、不写入 legacy 表。
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.contracts.facts import FactAuthority
from app.domain.contracts.patient_profile_v2 import (
    PatientProfileRevisionV2,
    ProfileStatus,
)
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
    FactRevisionChainError,
    Phase5RepositoryError,
    authority_column_filters,
)
from app.storage.facts_models import PatientProfileRevisionV2Record
from app.storage.repositories import _flush_guarded, _get_required

__all__ = ["PatientProfileRevisionRepository"]


def _authority_columns(authority: FactAuthority) -> dict[str, Any]:
    """权威元组 -> 规范化列（Profile revision 与运行/发布实体表共用）。"""
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
    """容错取 payload 点路径；父节点缺失/为 None 时返回 None（用于可空嵌套镜像）。"""
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


def _profile_content(revision: PatientProfileRevisionV2) -> str:
    """Profile 的确定性投影内容（幂等比较键；不含行身份与时间戳）。

    ``generated_at`` / ``created_at`` 是生成时戳，不是临床内容；同权威元组同投影
    重算视为同内容并幂等复用，不追加重复 revision。``review_stage``、13 条泳道、
    首屏突出集合、待核对数与状态全部纳入比较。
    """
    payload = revision.model_dump(mode="json")
    for key in (
        "patient_profile_revision_id",
        "revision",
        "created_at",
        "generated_at",
    ):
        payload.pop(key, None)
    return json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )


class PatientProfileRevisionRepository:
    """不可变 Profile revision 仓储：权威复核 + 幂等追加 + 镜像交叉核对。"""

    def __init__(self, session: Session) -> None:
        self.session = session
        self._authority = FactAuthorityValidator(session)

    # ------------------------------------------------------------------ 写入

    def create(self, revision: PatientProfileRevisionV2) -> PatientProfileRevisionV2:
        """写一条不可变 Profile revision；同内容幂等返回最新行，变化只追加链头 +1。"""
        if revision.status == ProfileStatus.STALE:
            raise Phase5RepositoryError(
                "stale 是对照当前审核节点权威读取时派生的状态，绝不能持久化写入"
            )
        self._authority.validate(revision.authority)
        latest = self._latest_record(revision.authority.review_episode_id)
        if latest is not None:
            latest_contract = self._decode_record(latest)
            if _profile_content(latest_contract) == _profile_content(revision):
                return latest_contract
            if revision.revision != latest_contract.revision + 1:
                raise FactRevisionChainError(
                    f"Profile revision {revision.patient_profile_revision_id} 的编号必须是"
                    f"当前链头 {latest_contract.revision} + 1（得到 {revision.revision}），"
                    "回退/跳号一律拒绝"
                )
        elif revision.revision != 1:
            raise FactRevisionChainError(
                f"Profile revision {revision.patient_profile_revision_id} 的首个"
                " revision 必须为 1"
            )

        payload_json, payload_sha256 = encode_contract(revision)
        row = PatientProfileRevisionV2Record(
            patient_profile_revision_id=revision.patient_profile_revision_id,
            status=revision.status.value,
            generated_at=to_utc_naive(revision.generated_at),
            highlights_json=json.loads(payload_json)["highlights"],
            revision=revision.revision,
            created_at=to_utc_naive(revision.created_at),
            payload_json=payload_json,
            payload_sha256=payload_sha256,
            **_authority_columns(revision.authority),
        )
        self.session.add(row)
        _flush_guarded(self.session)
        return revision

    # ------------------------------------------------------------------ 读取

    def get(self, patient_profile_revision_id: str) -> PatientProfileRevisionV2:
        row = _get_required(
            self.session,
            PatientProfileRevisionV2Record,
            patient_profile_revision_id,
            "PatientProfileRevisionV2",
        )
        return self._decode_record(row)

    def list_item_source_refs(
        self, review_episode_id: str
    ) -> list[tuple[str, str, str]]:
        """历史 Profile 类型化条目反向索引。

        返回 ``(patient_profile_revision_id, kind, source_id)``。先解码全部不可变
        payload 再按审核节点过滤：``succeeded``/``stale`` 的条目进入索引，
        ``generating``/``failed`` 无投影故无条目。镜像列漂移的坏行在解码阶段
        大声失败，不能靠漂移列把历史 Profile 静默漏出反向索引。
        """
        contracts = self.list_by_episode(review_episode_id)
        refs: list[tuple[str, str, str]] = []
        for revision in contracts:
            for section in revision.lanes:
                for item in section.items:
                    refs.append(
                        (
                            revision.patient_profile_revision_id,
                            item.kind.value,
                            item.source_id,
                        )
                    )
        return sorted(set(refs))

    def list_for_authority(
        self, authority: FactAuthority
    ) -> list[PatientProfileRevisionV2]:
        rows = self.session.execute(
            select(PatientProfileRevisionV2Record).where(
                *authority_column_filters(PatientProfileRevisionV2Record, authority)
            )
        ).scalars().all()
        contracts = [self._decode_record(row) for row in rows]
        return sorted(
            (item for item in contracts if item.authority == authority),
            key=lambda item: (item.revision, item.patient_profile_revision_id),
        )

    def list_by_episode(
        self, review_episode_id: str
    ) -> list[PatientProfileRevisionV2]:
        """按 revision 升序返回该审核节点的全部 Profile revision。

        先解码表中每条不可变 payload 再过滤：镜像列漂移的行会在解码阶段大声失败，
        不能靠漂移的 ``review_episode_id`` 列把坏行静默隐藏（权威元组/镜像/历史/
        链头全部走同一套列/正文镜像校验）。
        """
        rows = self.session.execute(
            select(PatientProfileRevisionV2Record)
        ).scalars().all()
        contracts = [self._decode_record(row) for row in rows]
        return sorted(
            (
                item
                for item in contracts
                if item.authority.review_episode_id == review_episode_id
            ),
            key=lambda item: (item.revision, item.patient_profile_revision_id),
        )

    def latest_by_episode(
        self, review_episode_id: str
    ) -> PatientProfileRevisionV2 | None:
        """链头 Profile（最高 revision）；无记录返回 None。"""
        row = self._latest_record(review_episode_id)
        return self._decode_record(row) if row is not None else None

    def _latest_record(
        self, review_episode_id: str
    ) -> PatientProfileRevisionV2Record | None:
        """链头记录：解码全部行后按解码出的审核节点与 revision 取最大。"""
        rows = self.session.execute(
            select(PatientProfileRevisionV2Record)
        ).scalars().all()
        contracts = [self._decode_record(row) for row in rows]
        matching = [
            contract
            for contract in contracts
            if contract.authority.review_episode_id == review_episode_id
        ]
        if not matching:
            return None
        head = max(matching, key=lambda contract: contract.revision)
        return self.session.get(
            PatientProfileRevisionV2Record, head.patient_profile_revision_id
        )

    def _decode_record(
        self, row: PatientProfileRevisionV2Record
    ) -> PatientProfileRevisionV2:
        contract = decode_contract(
            PatientProfileRevisionV2, row.payload_json, row.payload_sha256
        )
        payload = json.loads(row.payload_json)
        _check_tolerant_mirrors(
            "PatientProfileRevisionV2",
            row,
            payload,
            {
                "patient_profile_revision_id": "patient_profile_revision_id",
                "status": "status",
                "generated_at": "generated_at",
                "highlights_json": "highlights",
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
        return contract
